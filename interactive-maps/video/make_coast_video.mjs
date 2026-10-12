// 海岸線變化互動頁（tuvalu/coast/tuvalu-coast.html）→ 直式短影音 1080×1920。
// 頁面本身不改（它嵌在正式站 node/243890），影片版的版面用注入的 CSS 蓋過去；安全區照 make_video.mjs：上 12%、下 15%、左右 9%。
// 鏡頭不動，五個日期依序淡入，字卡跟著換；每一步停的秒數跟互動頁的自動輪播一樣是 7 秒。
// 用法（在 video/ 底下）：node make_coast_video.mjs            → out/tuvalu-coast_1080x1920.mp4
//                        node make_coast_video.mjs --preview  → out/preview_coast_step<N>.png（每一步一張，看構圖）
// 需要：Chrome（系統）＋ ffmpeg（系統 PATH）。
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = new URL("../tuvalu/coast/tuvalu-coast.html", import.meta.url).href;
const OUT = fileURLToPath(new URL("out/", import.meta.url));
const W = 1080, H = 1920, FPS = 30, PREVIEW = process.argv.includes("--preview");
const SEC = { first: 7, fade: 1.2, hold: 7, end: 1.5 };
// 新生地連同它左邊的地名，要落在標題框與字卡之間（北、西、南、東）：北端是 2026-09 北段新填地，南端是第二階段的尾巴
const FOCUS = [-8.5120, 179.1830, -8.5315, 179.2005];
const OCEAN = [-8.5300, 179.2000];   // 「太平洋」：頁面上的位置在 1080 寬會落到右緣安全區外，影片版往內移

const CSS = `
  html,body{ background:#0f2a22 }
  .frame{ position:fixed!important; inset:0!important; width:100vw!important; height:100vh!important; margin:0!important; border-radius:0!important }
  .frame, .frame *{ transition:none!important }   /* 淡入淡出改成逐幀自己算，CSS 過渡照實際時間跑、跟截圖對不上 */
  .titlebar{ left:50%!important; top:12%!important; transform:translateX(-50%); padding:26px 44px 28px!important; border-radius:24px }
  .titlebar .logo{ height:58px!important; margin-bottom:6px!important }
  .titlebar h1{ font-size:50px!important; margin-top:6px!important; white-space:nowrap }
  .titlebar p{ font-size:26px!important; margin-top:8px!important }
  .card{ left:9%!important; right:9%!important; bottom:15%!important; width:auto!important; padding:16px 40px 34px!important; border-radius:28px }
  .tabs{ margin:0 -12px 12px!important }
  .tabs button{ font-size:28px!important; padding:10px 12px!important }
  .card h2{ font-size:46px!important; margin-bottom:14px!important }
  .card p{ font-size:30px!important; line-height:1.6!important }
  .lbl{ font-size:32px; text-shadow:0 0 4px rgba(0,0,0,.95), 0 2px 7px rgba(0,0,0,.85), 0 0 22px rgba(0,0,0,.6) }
  .lbl.sea{ font-size:34px; letter-spacing:.4em }
  .attrib{ font-size:17px!important; padding:3px 10px!important }   /* Copernicus 出處是授權條件，要讀得到 */
`;

const b = await puppeteer.launch({ executablePath: CHROME, headless: true,
  userDataDir: "C:\\Users\\shawn\\AppData\\Local\\Temp\\claude-chrome-video",
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1"] });
const p = await b.newPage();
await p.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
await p.goto(PAGE, { waitUntil: "networkidle0", timeout: 60000 });

const fit = await p.evaluate(async (css, focus, ocean, W, H) => {
  hold(); removeEventListener("resize", layout);   // 停掉自動輪播；畫框位置下面自己算
  document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);
  const oi = LABELS.findIndex(l => l.id === "ocean");
  labels[oi].style.left = fx(ocean[1]) * 100 + "%"; labels[oi].style.top = fy(ocean[0]) * 100 + "%";
  await Promise.all(imgs.map(im => im.decode())); await document.fonts.ready;
  layout();
  // 新生地要放進的那一帶：左右安全區之間、標題框下緣到最高那張字卡的上緣
  const cardTop = Math.min(...STEPS.map((s, i) => { go(i); return document.querySelector(".card").getBoundingClientRect().top; }));
  go(0);
  const band = { x0: W * .09, x1: W * .91, y0: document.querySelector(".titlebar").getBoundingClientRect().bottom + 24, y1: cardTop - 24 };
  const [n, w, s, e] = focus, fw = (fx(e) - fx(w)) * IW, fh = (fy(s) - fy(n)) * IH;
  const cover = Math.max(W / IW, H / IH), k = Math.max(cover, Math.min((band.x1 - band.x0) / fw, (band.y1 - band.y0) / fh));
  const sw = IW * k, sh = IH * k, clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const left = clamp((band.x0 + band.x1) / 2 - (fx(w) + fx(e)) / 2 * sw, W - sw, 0);
  const top = clamp((band.y0 + band.y1) / 2 - (fy(n) + fy(s)) / 2 * sh, H - sh, 0);
  Object.assign(stage.style, { width: sw + "px", height: sh + "px", left: left + "px", top: top + "px" });
  // 換到第 i 步的第 t（0→1）：影像與新出現的地名淡入；字卡文字前四分之一淡出、換字、再淡入
  window.__fade = (i, t) => {
    const ease = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2, q = .25;
    if (t >= q && cur !== i) go(i);
    imgs[i].style.opacity = t < 1 ? ease : "";
    LABELS.forEach((l, j) => { if (l.from === i) labels[j].style.opacity = t < 1 ? ease : ""; });
    const c = t < q ? 1 - t / q : Math.min(1, (t - q) / q);
    for (const id of ["ctitle", "ctext"]) document.getElementById(id).style.opacity = c;
  };
  return { k: k.toFixed(3), cover: cover.toFixed(3), band, fits: fw * k <= band.x1 - band.x0 + 1 && fh * k <= band.y1 - band.y0 + 1 };
}, CSS, FOCUS, OCEAN, W, H);
console.log("畫框", JSON.stringify(fit));
if (!fit.fits) console.log("注意：新生地塞不進標題框與字卡之間，看一下預覽");

mkdirSync(OUT, { recursive: true });
const steps = await p.evaluate(() => STEPS.length);
if (PREVIEW) {
  for (let i = 0; i < steps; i++) {
    await p.evaluate(i => { go(i); __fade(i, 1); }, i);
    await p.screenshot({ path: `${OUT}preview_coast_step${i}.png` });
  }
  await b.close(); console.log(`wrote ${OUT}preview_coast_step*.png`); process.exit(0);
}

const outfile = `${OUT}tuvalu-coast_1080x${H}.mp4`;
const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", outfile], { stdio: ["pipe", "inherit", "inherit"] });
const put = async (sec) => {   // 截一張、寫 sec 秒（停住的段落每幀都一樣，只截一次）
  const buf = await p.screenshot({ type: "png", optimizeForSpeed: true });
  for (let f = 0, n = Math.max(1, Math.round(sec * FPS)); f < n; f++) if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
};
await put(SEC.first);
for (let i = 1; i < steps; i++) {
  const nf = Math.round(SEC.fade * FPS);
  for (let f = 1; f <= nf; f++) { await p.evaluate((i, t) => __fade(i, t), i, f / nf); await put(1 / FPS); }
  await put(SEC.hold);
}
await put(SEC.end);
ff.stdin.end();
await new Promise(r => ff.on("close", r));
await b.close();
console.log("wrote", outfile);
