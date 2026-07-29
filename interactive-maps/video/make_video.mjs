// 東京地圖 → 直式影片（大遠景 → zoom 景點1 → pan 依序，上半地圖、下半 popup 大卡）。
// 用法：
//   node make_video.mjs --preview            # 只輸出幾張關鍵幀 PNG 檢查構圖（便宜）
//   node make_video.mjs --height 1920         # 全片 → out/tokyo_1080x1920.mp4
//   node make_video.mjs --height 1305
// 需要：Chrome（系統）＋ ffmpeg（系統 PATH）。
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { mkdirSync, createWriteStream } from "node:fs";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const MAP = "file:///C:/Research-Lab/einfo-scratch/tokyo-bousai-map/tokyo/tokyo-bousai-map.html";
const args = process.argv.slice(2);
const RAWH = +(args[args.indexOf("--height") + 1]) || 1920;
const HEIGHT = RAWH % 2 ? RAWH - 1 : RAWH;    // H.264/yuv420p 需偶數高；奇數自動 -1（差 1px、看不出來）
if (HEIGHT !== RAWH) console.log(`note: 高度 ${RAWH} 是奇數，改用 ${HEIGHT}（H.264 需偶數）`);
const W = 1080, FPS = 30, PREVIEW = args.includes("--preview");
const SAFE_TOP = 0.12, SAFE_X = 0.09;                  // 社群安全區（參颱風片 上12/左右9%），不畫綠框
const SAFE_BOT = HEIGHT >= 1600 ? 0.15 : 0.085;        // 下留白：4:5(1305) 縮小→popup 往下長（owner）
const POPUP_X = HEIGHT >= 1600 ? SAFE_X : 0.155;       // popup 左右留白：4:5(1305) 加大＝卡片變窄、照片不那麼寬扁（owner）
const POPUP_H = 0.36;                     // popup 卡高度（佔畫面比例）
const SPOT_Y = 0.30;                     // 景點目標 y（上半，避開下方 popup＋頂端標題）
const SPOT_ZOOM = 12.2;                  // 景點鏡頭 zoom
const ESTAB_OUT = HEIGHT >= 1600 ? 0.55 : 1.15;  // 大遠景在 fit 上再拉遠；短版(4:5/1305)縮更多（owner）
// 特寫垂直中心＝執行期實測「標題框下緣～該景點 popup 上緣」的中點（每景點卡高不同→逐點量；勿用寫死比例，4:5 會偏低）
const SEC = { estab: 2, zoom: 1.5, hold: 2, pan: 1.5, end: 1.2 };
const ease = t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;  // easeInOutQuad

// 影片模式 CSS：地圖填滿整幀 + 下方大 popup 卡（字級放大給 1080 寬）
const VIDEO_CSS = `
  html,body{margin:0;background:#fff}
  .frame{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;
    max-width:none!important;aspect-ratio:auto!important;border-radius:0!important;box-shadow:none!important}
  #map{width:100%!important;height:100%!important;border-radius:0!important}
  #info{display:none!important}                     /* 藏原本的小角卡 */
  .legend{ display:none!important }                 /* 移掉右上圖示範例（owner） */
  .titlebar{ left:50%!important; right:auto!important; transform:translateX(-50%)!important; top:${(SAFE_TOP*100).toFixed(1)}%!important; max-width:82%!important; padding:26px 44px!important; z-index:55!important }  /* 背景框置中；內文靠左（環境資訊中心/標題都靠左，owner） */
  .titlebar h1{ font-size:50px; line-height:1.1; white-space:nowrap }                  /* 標題不換行、縮字剛好一行 */
  .titlebar .mark{ font-size:22px }
  .rlabel{ font-size:25px; font-weight:800 } .rlabel.big{ font-size:28px; font-weight:800 }  /* 行政區地名：~10 個、放大（owner） */
  .pin-anchor{ transform:scale(2.1)!important; transform-origin:11px 23px!important }  /* pin 圖示＋地名放大 */
  .pin-name{ font-size:18px }   /* 原生 pin 名（會被抽到 #toplabels 浮層；此處只留基本樣式） */
  #toplabels{ position:absolute; inset:0; z-index:50; pointer-events:none; overflow:hidden }   /* pin 名浮層：在地圖之上、popup(z60) 之下 → 永遠壓在所有 pin 之上、框不被蓋 */
  .toplabel{ position:absolute; transform:translate(-50%,-50%); white-space:nowrap; font-size:38px; font-weight:800; color:#4a443b; background:#fff; padding:3px 18px; border-radius:40px; border:2px solid #e6ddcb; box-shadow:0 3px 10px rgba(0,0,0,.28) }
  .pin, .pin-anchor, .hi{ animation:none!important }                                  /* 停用輪播脈動 */
  .pin-anchor.hi{ transform:scale(2.1)!important; transform-origin:11px 23px!important }  /* 輪播高亮不要額外放大 pin（維持 base 尺寸） */
  #vpop{position:fixed;left:${(POPUP_X*100).toFixed(1)}%;right:${(POPUP_X*100).toFixed(1)}%;
    bottom:${(SAFE_BOT*100).toFixed(1)}%;max-height:${((1-SAFE_TOP-SAFE_BOT-0.16)*100).toFixed(1)}%;
    background:#fff;z-index:60;box-shadow:0 12px 40px rgba(90,70,40,.3);
    border-radius:26px;padding:30px 40px;box-sizing:border-box;display:none;overflow:hidden}
  #vpop.show{display:block}
  #vpop .card{display:block;overflow:visible}      /* 卡片高度隨內容自動＝描述完整不裁切（owner） */
  #vpop .vhdr{display:flex;align-items:center;gap:12px}            /* 種類標籤＋地名同一行、靠左上 */
  #vpop .card .tag{font-size:22px;padding:5px 16px;border-radius:20px;flex:none}
  #vpop .card .area{font-size:22px;color:#a2957f;flex:none;margin:0}
  #vpop .card img.photo{width:100%;height:19vh;object-fit:cover;border-radius:14px;margin:14px 0;display:block}
  #vpop .card h3{margin:2px 0 0;font-size:44px}
  #vpop .card .ja{margin:2px 0 8px;font-size:22px;color:#a2957f}
  #vpop .card p.desc{margin:0;font-size:30px;line-height:1.5;color:#4a443b}
`;

const b = await puppeteer.launch({ executablePath: CHROME, headless: true,
  userDataDir: "C:\\Users\\shawn\\AppData\\Local\\Temp\\claude-chrome-video",
  args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--hide-scrollbars", "--force-device-scale-factor=1"] });
const p = await b.newPage();
await p.setViewport({ width: W, height: HEIGHT, deviceScaleFactor: 1 });
await p.goto(MAP, { waitUntil: "networkidle0", timeout: 60000 });
await p.waitForFunction(() => typeof map !== "undefined" && document.querySelectorAll(".pin").length >= 6, { timeout: 30000 });

// 進影片模式：注入 CSS、建 #vpop、停輪播、地圖填滿、記住大遠景視野
await p.evaluate((css, out) => {
  const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  const vp = document.createElement("div"); vp.id = "vpop"; document.querySelector(".frame").appendChild(vp);
  try { stopCar(); } catch (e) {}
  map.off("resize");                    // 關鍵：移除地圖的 resize handler → invalidateSize 不會再觸發 syncCar 重啟輪播
  map.invalidateSize(true);
  if (typeof refit === "function") refit();
  try { stopCar(); } catch (e) {}       // 保險再殺一次
  const maxT = setInterval(() => {}, 1e9); for (let i = 1; i <= maxT; i++) clearInterval(i);  // 硬清所有 timer（輪播）
  document.querySelectorAll(".hi").forEach(e => e.classList.remove("hi"));  // 清掉輪播 pin 高亮
  window.__estab = { c: map.getCenter(), z: map.getZoom() - out };   // fit 後再拉遠 → 全景更小、留白多
}, VIDEO_CSS, ESTAB_OUT);

const estab = await p.evaluate(() => window.__estab);   // 景點相機(cams)移到 placeDistricts/liftPinNames 之後算（要先知道 pin 名偏移才能整體置中）

async function setCam(lat, lng, z) {   // 設視野＋把 pin 名浮層(#toplabels)貼回各 pin 的螢幕位置（固定偏移＝平滑不跳、永遠壓在 pin 上）
  await p.evaluate((lat, lng, z) => {
    map.setView([lat, lng], z, { animate: false });
    if (window.__pinlabels) {
      const fr = document.querySelector(".frame").getBoundingClientRect();
      for (const pl of window.__pinlabels) {
        const pin = document.querySelector('.pin-anchor[data-spot="' + pl.spot + '"] .pin');
        if (!pin) continue;
        const pr = pin.getBoundingClientRect();
        pl.el.style.left = ((pr.left + pr.right) / 2 - fr.left + pl.dx) + "px";
        pl.el.style.top = ((pr.top + pr.bottom) / 2 - fr.top + pl.dy) + "px";
      }
    }
  }, lat, lng, z);
}
async function liftPinNames() {   // pin 名抽到 #toplabels 浮層＋自做避讓：框不壓別的 pin icon（右→上→左→下，閃不掉才選壓最少）
  await p.evaluate(() => {
    const frame = document.querySelector(".frame");
    let top = document.getElementById("toplabels");
    if (!top) { top = document.createElement("div"); top.id = "toplabels"; frame.appendChild(top); }
    top.innerHTML = ""; window.__pinlabels = [];
    const fr = frame.getBoundingClientRect();
    const oA = (a, b) => Math.max(0, Math.min(a.x2, b.x2) - Math.max(a.x1, b.x1)) * Math.max(0, Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1));
    const anchors = [...document.querySelectorAll(".pin-anchor")];
    const pins = anchors.map(a => { const r = a.querySelector(".pin").getBoundingClientRect(); return { cx: (r.left + r.right) / 2, cy: (r.top + r.bottom) / 2, hw: (r.right - r.left) / 2, hh: (r.bottom - r.top) / 2, spot: +a.dataset.spot }; });
    anchors.forEach(a => { const name = a.querySelector(".pin-name"); if (!name) return; const lab = document.createElement("div"); lab.className = "toplabel"; lab.textContent = name.textContent; lab.dataset.spot = a.dataset.spot; top.appendChild(lab); name.style.display = "none"; });
    const tb = document.querySelector(".titlebar");   // 標題框也當障礙（owner：北本被標題壓）
    const titleBox = tb ? (() => { const r = tb.getBoundingClientRect(); return { x1: r.left - 6, y1: r.top - 6, x2: r.right + 6, y2: r.bottom + 6 }; })() : null;
    const placed = [];
    top.querySelectorAll(".toplabel").forEach(lab => {
      const spot = +lab.dataset.spot, P = pins.find(p => p.spot === spot);
      const lr = lab.getBoundingClientRect(), lw = lr.width / 2, lh = lr.height / 2, G = P.hw + 12, V = P.hh + 12;
      const cands = [[G + lw, 0], [0, -(V + lh)], [-(G + lw), 0], [0, V + lh], [G + lw, -(V + lh)], [-(G + lw), -(V + lh)]];  // 右→上→左→下→右上→左上
      let best = cands[0], bestPen = Infinity;
      for (const [ox, oy] of cands) {
        const bx = { x1: P.cx + ox - lw, y1: P.cy + oy - lh, x2: P.cx + ox + lw, y2: P.cy + oy + lh };
        let pen = 0;
        for (const q of pins) if (q.spot !== spot) pen += oA(bx, { x1: q.cx - q.hw - 4, y1: q.cy - q.hh - 4, x2: q.cx + q.hw + 4, y2: q.cy + q.hh + 4 }) * 8;  // 壓到別 pin＝重罰
        if (titleBox) pen += oA(bx, titleBox) * 8;   // 壓到標題框＝重罰（owner：北本被標題壓）
        for (const b of placed) pen += oA(bx, b);   // 壓到別名字＝輕罰
        pen += (Math.max(0, fr.left - bx.x1) + Math.max(0, bx.x2 - fr.right) + Math.max(0, fr.top - bx.y1) + Math.max(0, bx.y2 - fr.bottom)) * 3;
        if (pen === 0) { best = [ox, oy]; break; }
        if (pen < bestPen) { bestPen = pen; best = [ox, oy]; }
      }
      const [ox, oy] = best;
      placed.push({ x1: P.cx + ox - lw, y1: P.cy + oy - lh, x2: P.cx + ox + lw, y2: P.cy + oy + lh });
      lab.style.left = (P.cx - fr.left + ox) + "px"; lab.style.top = (P.cy - fr.top + oy) + "px";
      // 群組（pin 框＋名字框的聯集）中心相對 pin 中心的偏移 → 給相機置中用（名字寬度要算進去，否則長名字會偏右）
      const gx1 = Math.min(P.cx - P.hw, P.cx + ox - lw), gx2 = Math.max(P.cx + P.hw, P.cx + ox + lw);
      const gy1 = Math.min(P.cy - P.hh, P.cy + oy - lh), gy2 = Math.max(P.cy + P.hh, P.cy + oy + lh);
      window.__pinlabels.push({ el: lab, spot, dx: ox, dy: oy, gdx: (gx1 + gx2) / 2 - P.cx, gdy: (gy1 + gy2) / 2 - P.cy });
    });
  });
}
async function setPopup(n) {
  await p.evaluate((n) => {
    const vp = document.getElementById("vpop");
    if (n == null) { vp.classList.remove("show"); vp.innerHTML = ""; }
    else {
      vp.innerHTML = cardHtml[n];
      const card = vp.querySelector(".card");                       // 把 .tag＋.area 包進一行 header（左上）
      const tag = card.querySelector(".tag"), area = card.querySelector(".area");
      if (tag && area) { const h = document.createElement("div"); h.className = "vhdr";
        card.insertBefore(h, tag); h.appendChild(tag); h.appendChild(area); }
      vp.classList.add("show");
    }
  }, n);
}
const lerp = (a, b, t) => a + (b - a) * t;
async function placeDistricts() {   // 全景放一次：pin 名 auto-layout(避開 pin+彼此、遠景也顯示) ＋ 行政區 ~10 個(彼此不重疊；被 pin/名蓋到沒關係 owner)
  await p.evaluate(() => {   // ① 放置
    const fr = document.querySelector(".frame").getBoundingClientRect();
    const frame = { x1: fr.left, y1: fr.top, x2: fr.right, y2: fr.bottom };
    const occ = [];
    document.querySelectorAll(".pin").forEach(p => { const r = p.getBoundingClientRect(); occ.push({ x1: r.left - 8, y1: r.top - 8, x2: r.right + 8, y2: r.bottom + 8 }); });
    try { layoutPinNames(occ, frame); } catch (e) {}   // pin 地名自動避讓（避開 pin＋彼此）＝遠景也顯示
    try { placeLabels([], frame); } catch (e) {}        // 行政區排到滿（不避 pin/名＝被蓋沒關係），下一段再挑
    document.querySelectorAll(".hi").forEach(e => e.classList.remove("hi"));
  });
  await new Promise(r => setTimeout(r, 80));   // 等 render 才量得到真尺寸
  await p.evaluate(() => {   // ② 行政區用真實尺寸去重：只跟彼此不重疊、優先 big、近中心、最多 10（被 pin/名蓋到沒關係）
    const fr = document.querySelector(".frame").getBoundingClientRect();
    const cx = (fr.left + fr.right) / 2, cy = (fr.top + fr.bottom) / 2;
    const ov = (a, b) => a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1;
    const cands = labelMarkers.map(m => { const el = m.getElement(); const r = el && el.getBoundingClientRect();
      return r && r.width ? { m, big: el.classList.contains("big"), box: { x1: r.left - 6, y1: r.top - 6, x2: r.right + 6, y2: r.bottom + 6 } } : null; }).filter(Boolean);
    const ctr = b => [(b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2];
    const keptB = [], keptM = [];
    const tryAdd = c => { if (keptM.length < 10 && !keptB.some(k => ov(c.box, k))) { keptB.push(c.box); keptM.push(c.m); return true; } return false; };
    for (const c of cands.filter(c => c.big)) if (!tryAdd(c)) map.removeLayer(c.m);   // 先放 big（縣/市/灣，本就在邊緣＝四散）
    const pool = cands.filter(c => !c.big);   // 其餘用 farthest-point 填到 10＝四散全圖、不集中中間（owner）
    while (keptM.length < 10 && pool.length) {
      let bi = -1, bd = -1;
      for (let i = 0; i < pool.length; i++) {
        if (keptB.some(k => ov(pool[i].box, k))) continue;
        const [px, py] = ctr(pool[i].box);
        let md = keptB.length ? Infinity : 1e9;
        for (const k of keptB) { const [kx, ky] = ctr(k); md = Math.min(md, Math.hypot(px - kx, py - ky)); }
        if (md > bd) { bd = md; bi = i; }
      }
      if (bi < 0) break;
      const c = pool.splice(bi, 1)[0]; keptB.push(c.box); keptM.push(c.m);
    }
    pool.forEach(c => map.removeLayer(c.m));
    labelMarkers = keptM;
  });
}

// 全景版面放一次（行政區＋pin 名浮層），讀 pin 名偏移 → 算各景點相機（讓 pin＋名整體置中）
await setCam(estab.c.lat, estab.c.lng, estab.z); await placeDistricts(); await liftPinNames();
const noff = await p.evaluate(() => Object.fromEntries(window.__pinlabels.map(pl => [pl.spot, [pl.gdx, pl.gdy]])));
// 逐景點實測垂直中心：標題框下緣＋該景點 popup 上緣的中點（卡高隨內容變、4:5 占比又不同 → 不能用固定比例）
const titleBottom = await p.evaluate(() => document.querySelector(".titlebar").getBoundingClientRect().bottom);
const spotNs = await p.evaluate(() => spots.map(s => s.n));
const mcy = {};
for (const n of spotNs) {
  await setPopup(n);
  mcy[n] = await p.evaluate(tb => (tb + document.getElementById("vpop").getBoundingClientRect().top) / 2, titleBottom);
}
await setPopup(null);
const cams = await p.evaluate((SPOT_ZOOM, H, mcy, off) => {
  return spots.map(s => {
    const o = off[s.n] || [0, 0];   // o＝群組(pin框＋名字框聯集)中心相對 pin 的偏移
    const pt = map.project([s.lat, s.lng], SPOT_ZOOM);
    const want = { x: 540 - o[0], y: mcy[s.n] - o[1] };   // pin 落此 → 群組中心落在(540, 實測帶中點)＝標題與 popup 之間置中
    const centerPt = { x: pt.x + (540 - want.x), y: pt.y + (H / 2 - want.y) };
    const c = map.unproject([centerPt.x, centerPt.y], SPOT_ZOOM);
    return { n: s.n, lat: c.lat, lng: c.lng, z: SPOT_ZOOM };
  });
}, SPOT_ZOOM, HEIGHT, mcy, noff);

// 組鏡頭關鍵段（from→to 視野＋該段要不要顯示 popup）
const segs = [];
segs.push({ kind: "hold", from: estab, to: estab, pop: null, sec: SEC.estab });                 // 大遠景
segs.push({ kind: "move", from: estab, to: cams[0], pop: null, popAtEnd: cams[0].n, sec: SEC.zoom }); // zoom 到景點1
segs.push({ kind: "hold", from: cams[0], to: cams[0], pop: cams[0].n, sec: SEC.hold });
for (let i = 1; i < cams.length; i++) {
  segs.push({ kind: "move", from: cams[i - 1], to: cams[i], pop: cams[i - 1].n, popAtEnd: cams[i].n, sec: SEC.pan });
  segs.push({ kind: "hold", from: cams[i], to: cams[i], pop: cams[i].n, sec: SEC.hold });
}
segs.push({ kind: "move", from: cams.at(-1), to: estab, pop: null, sec: SEC.zoom });   // 結尾 zoom out 回大遠景（owner）：popup 先收、鏡頭拉回全圖
segs.push({ kind: "hold", from: estab, to: estab, pop: null, sec: SEC.end });

if (PREVIEW) {
  // 只截幾張關鍵幀：大遠景、景點1、景點2、景點3
  mkdirSync("out", { recursive: true });
  await setCam(estab.c.lat, estab.c.lng, estab.z); await setPopup(null);   // 版面已在上面放好
  await new Promise(r => setTimeout(r, 300)); await p.screenshot({ path: `out/preview_estab_${HEIGHT}.png` });
  for (const i of [0, 1, 2]) { await setCam(cams[i].lat, cams[i].lng, cams[i].z); await setPopup(cams[i].n);
    await new Promise(r => setTimeout(r, 300)); await p.screenshot({ path: `out/preview_spot${cams[i].n}_${HEIGHT}.png` }); }
  await b.close(); console.log(`wrote out/preview_*_${HEIGHT}.png`); process.exit(0);
}

// 全片：逐幀 setView + 截圖 → 管進 ffmpeg
mkdirSync("out", { recursive: true });
const outfile = `out/tokyo_1080x${HEIGHT}.mp4`;
const ff = spawn("ffmpeg", ["-y", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", outfile], { stdio: ["pipe", "inherit", "inherit"] });
await setCam(estab.c.lat, estab.c.lng, estab.z);   // 回全景起點（版面＝行政區＋pin 名浮層已在上面放好）
let popState = "init";
for (const seg of segs) {
  const nf = Math.max(1, Math.round(seg.sec * FPS));
  for (let f = 0; f < nf; f++) {
    const t = ease(nf === 1 ? 1 : f / (nf - 1));
    const c1 = seg.from.c ? { lat: seg.from.c.lat, lng: seg.from.c.lng, z: seg.from.z } : seg.from;
    const c2 = seg.to.c ? { lat: seg.to.c.lat, lng: seg.to.c.lng, z: seg.to.z } : seg.to;
    await setCam(lerp(c1.lat, c2.lat, t), lerp(c1.lng, c2.lng, t), lerp(c1.z, c2.z, t));
    const want = (seg.kind === "move" && seg.popAtEnd != null && t > .6) ? seg.popAtEnd : seg.pop;
    if (want !== popState) { await setPopup(want); popState = want; }
    const buf = await p.screenshot({ type: "png" });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  }
}
ff.stdin.end();
await new Promise(r => ff.on("close", r));
await b.close();
console.log("wrote", outfile);
