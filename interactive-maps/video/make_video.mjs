// gen_map.py 產出的地圖 → 直式影片（大遠景 → zoom 景點1 → pan 依序 → zoom out 收尾；上半地圖、下半 popup 大卡）。
// 模板：吃任何 gen_map.py 生的地圖（依賴其固定介面：spots／cardHtml／layoutPinNames／placeLabels／labelMarkers／refit／stopCar）。
// 用法：
//   node make_video.mjs --preview                       # 只輸出幾張關鍵幀 PNG 檢查構圖（便宜）
//   node make_video.mjs --height 1920                    # 全片 → out/<地圖名>_1080x1920.mp4
//   node make_video.mjs --map ../demo-kaohsiung/kaohsiung-map.html --height 1305
//   node make_video.mjs --map ../tuvalu/tuvalu-map.html --zoom 16 --estab-out 0.65 --height 1920 \
//     --image ../tuvalu/basemap/video/s2_20260105_atoll_2x.webp   # 範圍小的地圖要自己給景點 zoom；--image＝影片專用底圖
// 需要：Chrome（系統）＋ ffmpeg（系統 PATH）。
// 衛星主題的地圖（.frame.tiles，例如吐瓦魯）照地圖的深色卡片、白字地名。offmap 的點影片版也畫上主圖、鏡頭直接飛過去
// （owner 09-30：僅限影片版），所以底圖要鋪到那裡：--image 換掉地圖的 IMAGE，bounds 讀同名 .json（tuvalu/build_video_basemap.py 產的）。
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve, basename } from "node:path";
import { pathToFileURL } from "node:url";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const args = process.argv.slice(2);
const MAP_FILE = args.includes("--map") ? resolve(args[args.indexOf("--map") + 1])
  : "C:/Research-Lab/einfo-scratch/tokyo-bousai-map/tokyo/tokyo-bousai-map.html";
const MAP = pathToFileURL(MAP_FILE).href;
const NAME = basename(MAP_FILE, ".html").replace(/-map$|-bousai-map$/, "") || "map";   // tokyo-bousai-map→tokyo、kaohsiung-map→kaohsiung
const RAWH = +(args[args.indexOf("--height") + 1]) || 1920;
const HEIGHT = RAWH % 2 ? RAWH - 1 : RAWH;    // H.264/yuv420p 需偶數高；奇數自動 -1（差 1px、看不出來）
if (HEIGHT !== RAWH) console.log(`note: 高度 ${RAWH} 是奇數，改用 ${HEIGHT}（H.264 需偶數）`);
const W = 1080, FPS = 30, PREVIEW = args.includes("--preview");
const SAFE_TOP = 0.12, SAFE_X = 0.09;                  // 社群安全區（參颱風片 上12/左右9%），不畫綠框
const SAFE_BOT = HEIGHT >= 1600 ? 0.15 : 0.085;        // 下留白：4:5(1305) 縮小→popup 往下長（owner）
const POPUP_X = HEIGHT >= 1600 ? SAFE_X : 0.155;       // popup 左右留白：4:5(1305) 加大＝卡片變窄、照片不那麼寬扁（owner）
const POPUP_H = 0.36;                     // popup 卡高度（佔畫面比例）
const SPOT_Y = 0.30;                     // 景點目標 y（上半，避開下方 popup＋頂端標題）
const opt = (k, d) => args.includes(k) ? +args[args.indexOf(k) + 1] : d;
const IMAGE_FILE = args.includes("--image") ? resolve(args[args.indexOf("--image") + 1]) : null;
const SPOT_ZOOM = opt("--zoom", 12.2);   // 景點鏡頭 zoom（東京 12.2；吐瓦魯這種小範圍要 16 上下）
const ESTAB_OUT = opt("--estab-out", HEIGHT >= 1600 ? 0.55 : 1.15);  // 大遠景在 fit 上再拉遠；短版(4:5/1305)縮更多（owner）
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
  /* ── 衛星主題（.frame.tiles，例如吐瓦魯）：照地圖的深色無框卡片、白字描邊地名；插畫風地圖（東京）碰不到這段 ── */
  .frame.tiles, .frame.tiles *{ transition:none!important }   /* 地圖的過渡動畫照實際時間跑、跟逐幀截圖對不上，全關 */
  .frame.tiles .corner{ left:0!important; right:0!important; top:${(SAFE_TOP*100).toFixed(1)}%!important; align-items:center!important; z-index:55 }  /* 標題框在 .corner 裡、不能自己定位，改排 .corner（整行置中） */
  .frame.tiles .corner > .titlebar{ transform:none!important; text-align:left; border-radius:24px }
  .frame.tiles .titlebar .mark{ font-size:22px }
  .frame.tiles .titlebar h1{ font-size:50px; margin-top:6px }
  .frame.tiles .pin-anchor, .frame.tiles .pin-anchor.hi{ transform-origin:50% 50%!important }   /* 圓點圖釘的中心對準座標（水滴針才是尖端） */
  .frame.tiles .toplabel{ text-shadow:0 0 4px rgba(0,0,0,.95), 0 2px 7px rgba(0,0,0,.85), 0 0 22px rgba(0,0,0,.6) }
  .frame.tiles .rlabel{ text-shadow:0 2px 6px rgba(0,0,0,.75), 0 0 16px rgba(0,0,0,.45) }
  .frame.tiles #vpop{ background:var(--glass); color:var(--cream); padding:0; border-radius:28px; box-shadow:0 16px 48px rgba(0,0,0,.45);
    -webkit-backdrop-filter:blur(8px); backdrop-filter:blur(8px) }
  .frame.tiles #vpop .card{ display:flex; padding:24px 40px 34px }
  .frame.tiles #vpop .card img.photo{ width:calc(100% + 80px); height:22vh; margin:-24px -40px 24px; border-radius:28px 28px 0 0; aspect-ratio:auto }
  .frame.tiles #vpop .card .meta{ gap:20px }
  .frame.tiles #vpop .card .tag{ font-size:24px; padding:0; gap:12px }
  .frame.tiles #vpop .card .tag::before{ width:16px; height:16px }
  .frame.tiles #vpop .card .area{ font-size:24px; color:var(--mute) }
  .frame.tiles #vpop .card h3{ font-size:46px; margin:10px 0 0 }
  .frame.tiles #vpop .card .ja{ margin:4px 0 14px; color:var(--mute) }
  .frame.tiles #vpop .card p.desc{ color:#e3ebe6 }
  .frame.tiles .leaflet-control-attribution{ font-size:17px; padding:2px 10px }   /* Copernicus 出處是授權條件，要讀得到 */
  .frame.tiles .inset{ display:none }   /* 小地圖不用：offmap 的點影片版直接飛過去 */
`;

const b = await puppeteer.launch({ executablePath: CHROME, headless: true,
  userDataDir: "C:\\Users\\shawn\\AppData\\Local\\Temp\\claude-chrome-video",
  args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--hide-scrollbars", "--force-device-scale-factor=1"] });
const p = await b.newPage();
await p.setViewport({ width: W, height: HEIGHT, deviceScaleFactor: 1 });
await p.goto(MAP, { waitUntil: "networkidle0", timeout: 60000 });
await p.waitForFunction(() => typeof map !== "undefined" && typeof spots !== "undefined" && document.querySelectorAll(".pin").length >= spots.length, { timeout: 30000 });

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
  // offmap 的點（吐瓦魯的富納法拉）影片版也畫上主圖，鏡頭直接飛過去（owner 09-30：僅限影片版）；圖釘照地圖的寫法。
  // 不加進 fit 的範圍，大遠景還是主島那段
  for (const s of spots.filter(s => s.offmap)) {
    L.marker([s.lat, s.lng], { keyboard: false, zIndexOffset: 1000, icon: L.divIcon({ className: "",
      iconSize: SAT ? [20, 20] : [23, 23], iconAnchor: SAT ? [10, 10] : [11, 23],
      html: `<div class="pin-anchor" data-spot="${s.n}"><div class="pin" style="background:${CAT[s.cat].color}"><b>${s.n}</b></div>`
        + `<span class="pin-name" data-spot="${s.n}">${s.short || s.zh}</span></div>` }) }).addTo(map);
  }
  if (document.querySelector(".inset")) map.attributionControl.removeAttribution(ATTRIB);   // 小地圖收起了，它的 OSM 出處也拿掉
  window.__estab = { c: map.getCenter(), z: map.getZoom() - out };   // fit 後再拉遠 → 全景更小、留白多
}, VIDEO_CSS, ESTAB_OUT);
if (IMAGE_FILE) {   // 影片專用底圖：換掉地圖 IMAGE 的網址與範圍，等解碼完再開拍
  const { bounds } = JSON.parse(readFileSync(IMAGE_FILE.replace(/\.\w+$/, ".json"), "utf8"));
  await p.evaluate(async (url, bounds) => {
    let ov = null; map.eachLayer(l => { if (l instanceof L.ImageOverlay) ov = l; });
    if (!ov) throw new Error("--image 只給用 IMAGE 底圖的地圖");
    await new Promise(res => { ov.once("load", res); ov.setBounds(L.latLngBounds(bounds)); ov.setUrl(url); });
    await ov.getElement().decode();
  }, pathToFileURL(IMAGE_FILE).href, bounds);
}

const estab = await p.evaluate(() => window.__estab);   // 景點相機(cams)移到 placeDistricts/liftPinNames 之後算（要先知道 pin 名偏移才能整體置中）
await p.evaluate((E, S) => { window.__zr = [E, S]; }, estab.z, SPOT_ZOOM);   // 大遠景、特寫的 zoom：setCam 依此淡入名字

async function setCam(lat, lng, z) {   // 設視野＋把 pin 名浮層(#toplabels)貼回各 pin 的螢幕位置（固定偏移＝平滑不跳、永遠壓在 pin 上）
  await p.evaluate((lat, lng, z) => {
    map.setView([lat, lng], z, { animate: false });
    if (window.__pinlabels) {
      const fr = document.querySelector(".frame").getBoundingClientRect();
      const [E, S] = window.__zr, clamp = v => Math.min(1, Math.max(0, v));
      const k = clamp((z - E) / (S - E));        // 名字位置：大遠景那套（0）→ 特寫那套（1），東京兩套一樣
      const wide = clamp((z - E + 0.5) / 0.5);   // 比大遠景還遠（長距離飛越的途中）名字收起
      for (const pl of window.__pinlabels) {
        const pin = document.querySelector('.pin-anchor[data-spot="' + pl.spot + '"] .pin');
        if (!pin) continue;
        const pr = pin.getBoundingClientRect();
        pl.el.style.left = ((pr.left + pr.right) / 2 - fr.left + pl.fx + (pl.dx - pl.fx) * k) + "px";
        pl.el.style.top = ((pr.top + pr.bottom) / 2 - fr.top + pl.fy + (pl.dy - pl.fy) * k) + "px";
        pl.el.style.opacity = wide < 1 ? wide : "";
      }
      for (const m of labelMarkers) { const el = m.getElement(); if (el) el.style.opacity = wide < 1 ? wide : ""; }   // 海面地名也是（位置照大遠景排的）
    }
  }, lat, lng, z);
}
async function liftPinNames() {   // pin 名抽到 #toplabels 浮層＋自做避讓：框不壓別的 pin icon（右→上→左→下，閃不掉才選壓最少）
  await p.evaluate((SZ) => {
    const frame = document.querySelector(".frame");
    let top = document.getElementById("toplabels");
    if (!top) { top = document.createElement("div"); top.id = "toplabels"; frame.appendChild(top); }
    top.innerHTML = ""; window.__pinlabels = [];
    const fr = frame.getBoundingClientRect();
    const oA = (a, b) => Math.max(0, Math.min(a.x2, b.x2) - Math.max(a.x1, b.x1)) * Math.max(0, Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1));
    const pinBox = q => ({ x1: q.cx - q.hw - 4, y1: q.cy - q.hh - 4, x2: q.cx + q.hw + 4, y2: q.cy + q.hh + 4 });
    const dist = (b, q) => Math.hypot(Math.max(b.x1 - q.cx, 0, q.cx - b.x2), Math.max(b.y1 - q.cy, 0, q.cy - b.y2));
    const anchors = [...document.querySelectorAll(".pin-anchor")];
    const onScreen = () => anchors.map(a => { const r = a.querySelector(".pin").getBoundingClientRect(); return { cx: (r.left + r.right) / 2, cy: (r.top + r.bottom) / 2, hw: (r.right - r.left) / 2, hh: (r.bottom - r.top) / 2, spot: +a.dataset.spot }; });
    anchors.forEach(a => { const name = a.querySelector(".pin-name"); if (!name) return; const lab = document.createElement("div"); lab.className = "toplabel"; lab.textContent = name.textContent; lab.dataset.spot = a.dataset.spot; top.appendChild(lab); name.style.display = "none"; });
    const tb = document.querySelector(".titlebar");   // 標題框也當障礙（owner：北本被標題壓）
    const titleBox = tb ? (() => { const r = tb.getBoundingClientRect(); return { x1: r.left - 6, y1: r.top - 6, x2: r.right + 6, y2: r.bottom + 6 }; })() : null;
    const outFrame = bx => Math.max(0, fr.left - bx.x1) + Math.max(0, bx.x2 - fr.right) + Math.max(0, fr.top - bx.y1) + Math.max(0, bx.y2 - fr.bottom);
    const labs = [...top.querySelectorAll(".toplabel")].map(el => { const r = el.getBoundingClientRect(), spot = +el.dataset.spot;
      return { el, spot, lw: r.width / 2, lh: r.height / 2, side: (spots.find(s => s.n === spot) || {}).label }; });   // side：spots.py 指定 "label"（right／up／left／down），照地圖
    // 排名字：pins＝各圖釘中心，cands(L,P)＝候選偏移 [x, y, 額外罰分]（照偏好排），cost＝罰分；第一個 0 分的就用，否則取最低分。
    // passes＞0 時再排幾輪：每個名字看著其他所有名字重挑一次，先排的才不會把後排的卡死
    const place = (pins, cands, cost, passes = 0) => {
      const out = {}, boxes = {}, at = L => pins.find(q => q.spot === L.spot);
      const box = (P, L, [ox, oy]) => ({ x1: P.cx + ox - L.lw, y1: P.cy + oy - L.lh, x2: P.cx + ox + L.lw, y2: P.cy + oy + L.lh });
      const pick = (L, others) => { const P = at(L); let best = null, bestPen = Infinity;
        for (const [ox, oy, extra = 0] of cands(L, P)) {
          const bx = box(P, L, [ox, oy]);
          let pen = extra;
          for (const q of pins) if (q.spot !== L.spot) pen += oA(bx, pinBox(q)) * 8;   // 壓到別 pin＝重罰
          pen += cost(bx, P, pins, others);
          if (pen === 0) return [ox, oy];
          if (pen < bestPen) { bestPen = pen; best = [ox, oy]; }
        }
        return best; };
      for (const L of labs) { out[L.spot] = pick(L, Object.values(boxes)); boxes[L.spot] = box(at(L), L, out[L.spot]); }
      for (let i = 0; i < passes; i++) for (const L of labs) {
        out[L.spot] = pick(L, labs.filter(M => M !== L).map(M => boxes[M.spot])); boxes[L.spot] = box(at(L), L, out[L.spot]); }
      return out; };
    const six = (L, P) => { const G = P.hw + 12, V = P.hh + 12;   // 右→上→左→下→右上→左上；指定邊就只放那邊
      const c = [[G + L.lw, 0], [0, -(V + L.lh)], [-(G + L.lw), 0], [0, V + L.lh], [G + L.lw, -(V + L.lh)], [-(G + L.lw), -(V + L.lh)]];
      return L.side ? [c[["right", "up", "left", "down"].indexOf(L.side)]] : c; };
    const misread = w => (bx, P, pins) => pins.reduce((s, q) => s + (q.spot !== P.spot && dist(bx, q) < dist(bx, P) ? w : 0), 0);   // 名字離別的圖釘比較近＝會看錯是誰的（照地圖）
    const over = (bx, placed) => placed.reduce((s, b) => s + oA(bx, b), 0);
    const scr = onScreen(), sat = frame.classList.contains("tiles");
    let far, near;
    if (!sat) far = near = place(scr, six, (bx, P, pins, placed) =>   // 插畫風（東京）照原本：一套，在大遠景排
      over(bx, placed) + (titleBox ? oA(bx, titleBox) * 8 : 0) + outFrame(bx) * 3);
    else {
      // 衛星主題（吐瓦魯）點很密，遠景、特寫各排一套，setCam 依縮放在兩套之間滑動（owner 09-30：遠景名字不能不見）。
      // 特寫：照特寫縮放下的距離排（讀者在特寫時讀名字），標題框與畫框不管（每點的鏡頭不同）
      const atZ = scr.map(q => { const s = spots.find(s => s.n === q.spot), c = map.project([s.lat, s.lng], SZ); return { ...q, cx: c.x, cy: c.y }; });
      const nearMis = misread(400);
      near = place(atZ, six, (bx, P, pins, placed) => over(bx, placed) + nearMis(bx, P, pins));
      // 遠景：南端那群點擠在一起，名字要疊成左右兩欄，所以左右兩邊再各給上下錯開的位置。看錯是誰的名字最糟，其次是互疊、壓標題框、出框；
      // spots.py 指定的邊優先，那邊怎麼放都會看錯或互疊才換邊（友誼農場在遠景只能這樣）
      const farMis = misread(5000);
      far = place(scr, (L, P) => { const G = P.hw + 12, V = P.hh + 12, h = 2 * L.lh, c = [[G + L.lw, 0], [0, -(V + L.lh)], [-(G + L.lw), 0], [0, V + L.lh]];
        for (const k of [0.5, -0.5, 1, -1, 1.5, -1.5]) c.push([G + L.lw, k * h], [-(G + L.lw), k * h]);
        if (!L.side) return c;
        const on = ([x, y]) => ({ right: x > 0, left: x < 0, up: !x && y < 0, down: !x && y > 0 })[L.side];
        return [...c.filter(on), ...c.filter(v => !on(v)).map(([x, y]) => [x, y, 300])]; },
        (bx, P, pins, placed) => over(bx, placed) * 8 + farMis(bx, P, pins) + (titleBox ? oA(bx, titleBox) * 8 : 0) + outFrame(bx) * 1000, 3);
    }
    for (const L of labs) {
      const P = scr.find(q => q.spot === L.spot), [nx, ny] = near[L.spot], [fx, fy] = far[L.spot];
      // 群組（pin 框＋名字框的聯集）中心相對 pin 中心的偏移 → 給特寫的相機置中用（名字寬度要算進去，否則長名字會偏右）
      const gx1 = Math.min(-P.hw, nx - L.lw), gx2 = Math.max(P.hw, nx + L.lw), gy1 = Math.min(-P.hh, ny - L.lh), gy2 = Math.max(P.hh, ny + L.lh);
      window.__pinlabels.push({ el: L.el, spot: L.spot, dx: nx, dy: ny, fx, fy, gdx: (gx1 + gx2) / 2, gdy: (gy1 + gy2) / 2 });
      L.el.style.left = (P.cx - fr.left + fx) + "px"; L.el.style.top = (P.cy - fr.top + fy) + "px";   // 現在是大遠景
    }
  }, SPOT_ZOOM);
}
async function setPopup(n) {
  await p.evaluate(async (n) => {
    const fr = document.querySelector(".frame"), vp = document.getElementById("vpop");
    if (n == null) { vp.classList.remove("show"); vp.innerHTML = ""; }
    else {
      vp.innerHTML = cardHtml[n];
      const card = vp.querySelector(".card");                       // 把 .tag＋.area 包進一行 header（左上）；衛星主題的卡片本來就有 .meta 包著
      const tag = card.querySelector(".tag"), area = card.querySelector(".area");
      if (tag && area && tag.parentNode === card) { const h = document.createElement("div"); h.className = "vhdr";
        card.insertBefore(h, tag); h.appendChild(tag); h.appendChild(area); }
      vp.classList.add("show");
      const im = vp.querySelector("img"); if (im) await im.decode().catch(() => {});   // 照片解碼完再截，第一幀才不會是空框
    }
    if (fr.classList.contains("tiles") && typeof highlight === "function") highlight(n || 0);   // 衛星主題照地圖：正在介紹的點地名變黃、圖釘放大
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
// 兩點太遠（用兩端縮放的中間值量，超過 2000px；吐瓦魯 ⑧→⑨ 約 2900px、⑪→⑫ 富納法拉約 9000px）就中途先拉遠再推近，免得像甩鏡頭：
// 拉遠到中途的平移速度跟東京最遠那段（1344px）差不多，拉得越遠這段越長（每拉遠一級多 0.6 秒）。東京每段都不到 2000px，不受影響
const cam = c => c.c ? { lat: c.c.lat, lng: c.c.lng, z: c.z } : c;
const moves = segs.filter(s => s.kind === "move");
const dists = await p.evaluate(pairs => pairs.map(([a, b]) => { const z = (a.z + b.z) / 2; return map.project([a.lat, a.lng], z).distanceTo(map.project([b.lat, b.lng], z)); }),
  moves.map(s => [cam(s.from), cam(s.to)]));
moves.forEach((s, i) => { if (dists[i] > 2000) { s.dip = Math.log2(dists[i] / 1400); s.sec += s.dip * 0.6;
  console.log(`拉遠飛越：${s.from.n ?? "大遠景"}→${s.to.n ?? "大遠景"} ${Math.round(dists[i])}px，拉遠 ${s.dip.toFixed(2)} 級、${s.sec.toFixed(1)} 秒`); } });

if (PREVIEW) {
  // 只截關鍵幀：大遠景＋每個景點的特寫＋拉遠飛越的中點（看底圖有沒有鋪到）
  mkdirSync("out", { recursive: true });
  await setCam(estab.c.lat, estab.c.lng, estab.z); await setPopup(null);   // 版面已在上面放好
  await new Promise(r => setTimeout(r, 300)); await p.screenshot({ path: `out/preview_${NAME}_estab_${HEIGHT}.png` });
  for (const c of cams) { await setCam(c.lat, c.lng, c.z); await setPopup(c.n);
    await new Promise(r => setTimeout(r, 300)); await p.screenshot({ path: `out/preview_${NAME}_spot${c.n}_${HEIGHT}.png` }); }
  for (const s of moves.filter(s => s.dip)) { const a = cam(s.from), c = cam(s.to);
    await setCam((a.lat + c.lat) / 2, (a.lng + c.lng) / 2, (a.z + c.z) / 2 - s.dip); await setPopup(null);
    await new Promise(r => setTimeout(r, 300)); await p.screenshot({ path: `out/preview_${NAME}_fly${s.from.n ?? 0}-${s.to.n ?? 0}_${HEIGHT}.png` }); }
  await b.close(); console.log(`wrote out/preview_${NAME}_*_${HEIGHT}.png`); process.exit(0);
}

// 全片：逐幀 setView + 截圖 → 管進 ffmpeg
mkdirSync("out", { recursive: true });
const outfile = `out/${NAME}_1080x${HEIGHT}.mp4`;
const ff = spawn("ffmpeg", ["-y", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", outfile], { stdio: ["pipe", "inherit", "inherit"] });
await setCam(estab.c.lat, estab.c.lng, estab.z);   // 回全景起點（版面＝行政區＋pin 名浮層已在上面放好）
let popState = "init";
for (const seg of segs) {
  const nf = Math.max(1, Math.round(seg.sec * FPS));
  for (let f = 0; f < nf; f++) {
    const t = ease(nf === 1 ? 1 : f / (nf - 1));
    const c1 = cam(seg.from), c2 = cam(seg.to);
    await setCam(lerp(c1.lat, c2.lat, t), lerp(c1.lng, c2.lng, t), lerp(c1.z, c2.z, t) - (seg.dip || 0) * Math.sin(Math.PI * t));
    const want = seg.dip && t > .25 && t <= .6 ? null   // 拉遠飛越的途中收起說明卡，看得到飛過的地方
      : (seg.kind === "move" && seg.popAtEnd != null && t > .6) ? seg.popAtEnd : seg.pop;
    if (want !== popState) { await setPopup(want); popState = want; }
    const buf = await p.screenshot({ type: "png", optimizeForSpeed: true });   // 快速壓縮一樣是無損 PNG；衛星影像用預設壓縮每幀要慢三倍
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  }
}
ff.stdin.end();
await new Promise(r => ff.on("close", r));
await b.close();
console.log("wrote", outfile);
