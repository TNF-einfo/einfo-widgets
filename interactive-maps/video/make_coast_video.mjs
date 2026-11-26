// 海岸線變化互動頁（tuvalu/coast/tuvalu-coast.html）→ 直式短影音 1080×1920。
// 頁面本身不改（它嵌在正式站 node/243890），影片版的版面用注入的 CSS 蓋過去；安全區照 make_video.mjs：上 12%、下 15%、左右 9%。
// 縮時：五個階段之間照時間平均抽、沒有雲的影像接續（tuvalu/coast/build_timelapse.py 產的，沒有就只用五個階段那五張），
// 到了階段那張字卡就換、不停；字卡上排目前那一格跟著跑年月，到下一個階段跳下一格；鏡頭固定（定：「不需要推進，保持固定鏡頭就好」）。
// 影像用 build_timelapse.py 另做的無損 PNG（五個階段也是），不用互動頁的有損 WebP。
// 用法（在 video/ 底下）：node make_coast_video.mjs            → out/tuvalu-coast_<VERSION>_1080x1920.mp4
//                        node make_coast_video.mjs --preview  → out/preview_coast_step<N>.png（五個階段停住那段的中間）
// 需要：Chrome（系統）＋ ffmpeg（系統 PATH）。
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = new URL("../tuvalu/coast/tuvalu-coast.html", import.meta.url).href;
const TIMELAPSE = fileURLToPath(new URL("../tuvalu/coast/img/timelapse/list.json", import.meta.url));
const OUT = fileURLToPath(new URL("out/", import.meta.url));
const W = 1080, H = 1920, FPS = 30, PREVIEW = process.argv.includes("--preview");
// 檔名的版號，重產新的一版就加一，舊的不會被蓋掉。v2（10-19）：抽掉有雲的影格；10-12 那版（64008c0）檔名沒有版號
const VERSION = "v2";
// 定：「一秒五幀好了」「字卡不要停好了，都給縮時」。相鄰兩個階段之間每段 3.5 秒，那段的縮時圖連同下一個階段那張平分
// （17 張就是一秒 5 張，每張六成時間淡入、四成停住），字卡到了階段那張就換、不停；第一張停 0.5 秒，最後多停 1.5 秒
const SEC = { first: .5, segment: 3.5, end: 1.5 };
// 新生地連同它左邊的地名，要落在標題框與字卡之間（北、西、南、東）：北端是 2026-09 北段新填地，南端是第二階段的尾巴。
// 鏡頭就定在剛好放得下這一塊的縮放（不小於影像鋪滿畫面），放得越小，10 公尺的影像看起來越不糊
const FOCUS = [-8.5120, 179.1830, -8.5315, 179.2005];
const OCEAN = [-8.5285, 179.2000];   // 「太平洋」：頁面上的位置在 1080 寬會落到右緣安全區外，影片版往內移到離岸約 400 公尺

const CSS = `
  html,body{ background:#0f2a22 }
  .frame{ position:fixed!important; inset:0!important; width:100vw!important; height:100vh!important; margin:0!important; border-radius:0!important }
  .frame, .frame *{ transition:none!important }   /* 淡入淡出改成逐幀自己算，CSS 過渡照實際時間跑、跟截圖對不上 */
  .stage{ z-index:0 }   /* 影像各有 z-index（晚的在上），關在 stage 裡，才不會蓋到標題框與字卡 */
  .lbl{ z-index:100 }
  .titlebar{ left:50%!important; top:12%!important; transform:translateX(-50%); padding:26px 44px 28px!important; border-radius:24px }
  .titlebar .logo{ height:58px!important; margin-bottom:6px!important }
  .titlebar h1{ font-size:50px!important; margin-top:6px!important; white-space:nowrap }
  .titlebar p{ font-size:26px!important; margin-top:8px!important }
  .card{ left:9%!important; right:9%!important; bottom:15%!important; width:auto!important; padding:16px 40px 34px!important; border-radius:28px }
  .tabs{ margin:0 -12px 12px!important }
  .tabs button{ font-size:28px!important; padding:10px 12px!important; flex:1; text-align:center; font-variant-numeric:tabular-nums }   /* 等寬，年月跑動時分頁才不會左右晃 */
  .card h2{ font-size:46px!important; margin-bottom:14px!important }
  .card p{ font-size:30px!important; line-height:1.6!important }
  .lbl{ font-size:32px; text-shadow:0 0 4px rgba(0,0,0,.95), 0 2px 7px rgba(0,0,0,.85), 0 0 22px rgba(0,0,0,.6) }
  .lbl.sea{ font-size:34px; letter-spacing:.4em }
  .attrib{ font-size:17px!important; padding:3px 10px!important }   /* Copernicus 出處是授權條件，要讀得到 */
`;

// 播放順序：縮時清單（照日期）；沒有就只用五個階段。src 相對於頁面
const list = existsSync(TIMELAPSE) ? JSON.parse(readFileSync(TIMELAPSE, "utf8")) : null;
const label = d => `${+d.slice(0, 4)}.${+d.slice(5, 7)}`;   // 2023-06-05 → 2023.6，跟字卡上排的日期一樣
const spec = list ? list.map(c => ({ src: "img/timelapse/" + c.file, label: label(c.date), key: c.key })) : null;

const b = await puppeteer.launch({ executablePath: CHROME, headless: true,
  userDataDir: "C:\\Users\\shawn\\AppData\\Local\\Temp\\claude-chrome-video",
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1"] });
const p = await b.newPage();
await p.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
await p.goto(PAGE, { waitUntil: "networkidle0", timeout: 60000 });

const cam = await p.evaluate(async (css, focus, ocean, W, H, spec) => {
  hold(); removeEventListener("resize", layout);   // 停掉自動輪播；畫框位置下面自己算
  document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);
  const oi = LABELS.findIndex(l => l.id === "ocean");
  labels[oi].style.left = fx(ocean[1]) * 100 + "%"; labels[oi].style.top = fy(ocean[0]) * 100 + "%";
  // 播放順序裡的每一張：五個階段沿用頁面原本的 <img>（換成無損 PNG），其餘新增在同一個 stage、同樣範圍；晚的疊在上面。
  // 第幾個階段照清單的 key 數，不比檔名：影片換掉的階段影像（build_timelapse.py 的 SWAP）日期跟頁面不同
  spec = spec || STEPS.map(s => ({ src: s.img, label: s.tab, key: true }));
  let step = 0;
  const seq = spec.map((s, r) => {
    const k = s.key ? step++ : -1;
    const im = k >= 0 ? imgs[k] : Object.assign(new Image(), { alt: "", decoding: "async" });
    im.src = s.src;
    if (k < 0) stage.insertBefore(im, labels[0]);
    im.style.zIndex = r + 1;
    return { im, k, label: s.label };
  });
  await Promise.all(seq.map(s => s.im.decode())); await document.fonts.ready;
  layout();
  // 新生地要放進的那一帶：左右安全區之間、標題框下緣到最高那張字卡的上緣（各留 24px）
  const cardTop = Math.min(...STEPS.map((s, i) => { go(i); return document.querySelector(".card").getBoundingClientRect().top; }));
  go(0);
  const x0 = W * .09, x1 = W * .91, y0 = document.querySelector(".titlebar").getBoundingClientRect().bottom + 24, y1 = cardTop - 24;
  const [n, w, s, e] = focus, fw = (fx(e) - fx(w)) * IW, fh = (fy(s) - fy(n)) * IH;
  // 固定鏡頭：剛好把新生地放進那一帶的縮放，但不小於影像鋪滿畫面（再小就露出影像邊緣）；新生地對準那一帶的中心
  const k = Math.max(W / IW, H / IH, Math.min((x1 - x0) / fw, (y1 - y0) / fh)), sw = IW * k, sh = IH * k;
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const left = clamp((x0 + x1) / 2 - (fx(w) + fx(e)) / 2 * sw, W - sw, 0), top = clamp((y0 + y1) / 2 - (fy(n) + fy(s)) / 2 * sh, H - sh, 0);
  Object.assign(stage.style, { width: sw + "px", height: sh + "px", left: left + "px", top: top + "px" });
  // 畫面停在第 a 張、第 b 張淡入到 t（0→1；b 是 null＝停住）。b 是五個階段之一時：新地名跟著淡入，
  // 字卡文字前四分之一淡出、換字、再淡入，分頁同時跳到下一格。縮時的年月顯示在目前那一格（過了一半換成 b 的），其他格照原本的日期
  window.__show = (a, b, t) => {
    const ease = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2, q = .25;
    seq.forEach((s, r) => { s.im.style.opacity = r === a ? 1 : r === b ? ease : 0; });
    const k = b === null ? -1 : seq[b].k;
    if (k >= 0) {
      if (t >= q && cur !== k) go(k);
      LABELS.forEach((l, j) => { if (l.from === k) labels[j].style.opacity = t < 1 ? ease : ""; });
      const c = t < q ? 1 - t / q : Math.min(1, (t - q) / q);
      for (const id of ["ctitle", "ctext"]) document.getElementById(id).style.opacity = c;
    }
    const shown = seq[b !== null && t >= (k >= 0 ? q : .5) ? b : a];
    btns.forEach((btn, j) => { btn.textContent = j === cur && shown.k < 0 ? shown.label : STEPS[j].tab; });
  };
  __show(0, null, 0);
  // view＝畫面露出的影像範圍（影像像素，左上右下），build_timelapse.py 的 VIEW 照這個算雲量
  return { k: +k.toFixed(3), band: [Math.round(y0), Math.round(y1)], keys: seq.map(s => s.k),
    view: [-left / k, -top / k, (W - left) / k, (H - top) / k].map(Math.round) };
}, CSS, FOCUS, OCEAN, W, H, spec);
console.log("鏡頭", JSON.stringify({ k: cam.k, band: cam.band, view: cam.view }),
  `共 ${cam.keys.length} 張（五個階段 ${cam.keys.filter(k => k >= 0).length} 張）`);

// 時間軸：第一張停一下 → 每段縮時連同下一個階段那張平分 3.5 秒 → 最後多停一下。清單的最後一張一定是階段
const segs = [{ a: 0, b: null, sec: SEC.first }];
for (let r = 1; r < cam.keys.length;) {
  let s = r;
  while (cam.keys[s] < 0) s++;   // s＝下一個階段
  const per = SEC.segment / (s - r + 1);
  for (let i = r; i <= s; i++) segs.push({ a: i - 1, b: i, sec: per * .6 }, { a: i, b: null, sec: per * .4 });
  r = s + 1;
}
segs.at(-1).sec += SEC.end;
const total = segs.reduce((a, s) => a + Math.round(s.sec * FPS), 0);

mkdirSync(OUT, { recursive: true });
if (PREVIEW) {
  let f = 0;
  for (const s of segs) {
    const n = Math.round(s.sec * FPS);
    if (s.b === null && cam.keys[s.a] >= 0) {
      await p.evaluate(a => { if (a > 0) __show(a - 1, a, 1); __show(a, null, 0); }, s.a);   // 先走完淡入，字卡與地名才會換
      await p.screenshot({ path: `${OUT}preview_coast_step${cam.keys[s.a]}.png` });
    }
    f += n;
  }
  await b.close(); console.log(`wrote ${OUT}preview_coast_step*.png`); process.exit(0);
}

const outfile = `${OUT}tuvalu-coast_${VERSION}_1080x${H}.mp4`;
// 壓縮品質：縮時每幀都在換、細節多，預設 CRF 23 會糊成方塊（10-12 回報：「影片畫質感覺有點差」），改 CRF 17＋slow
const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", outfile],
  { stdio: ["pipe", "inherit", "inherit"] });
let f = 0;
for (const s of segs) {
  const n = Math.round(s.sec * FPS);
  for (let j = 1; j <= n; j++, f++) {   // 縮時每 0.2 秒就換一張，停住的段落也只有幾幀，逐幀截就好
    await p.evaluate((a, bb, t) => __show(a, bb, t), s.a, s.b, s.b === null ? 0 : j / n);
    const buf = await p.screenshot({ type: "png", optimizeForSpeed: true });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  }
}
ff.stdin.end();
await new Promise(r => ff.on("close", r));
await b.close();
console.log("wrote", outfile, `${(total / FPS).toFixed(1)} 秒`);
