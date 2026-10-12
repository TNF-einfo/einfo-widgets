// 海岸線變化互動頁（tuvalu/coast/tuvalu-coast.html）→ 直式短影音 1080×1920。
// 頁面本身不改（它嵌在正式站 node/243890），影片版的版面用注入的 CSS 蓋過去；安全區照 make_video.mjs：上 12%、下 15%、左右 9%。
// 五個日期依序淡入，字卡跟著換，每一步停 5 秒；鏡頭整支片從影像剛好鋪滿畫面慢慢推近 10%。
// 用法（在 video/ 底下）：node make_coast_video.mjs            → out/tuvalu-coast_1080x1920.mp4
//                        node make_coast_video.mjs --preview  → out/preview_coast_step<N>.png（每一步停住那段的中間）
// 需要：Chrome（系統）＋ ffmpeg（系統 PATH）。
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = new URL("../tuvalu/coast/tuvalu-coast.html", import.meta.url).href;
const OUT = fileURLToPath(new URL("out/", import.meta.url));
const W = 1080, H = 1920, FPS = 30, PREVIEW = process.argv.includes("--preview");
const SEC = { first: 5, fade: 1.2, hold: 5, end: 1.5 };
const PUSH = 1.10;   // 推近到起點的幾倍；推太多新生地會跑進標題框或字卡底下（會先被下面的 fit 擋住）
// 新生地連同它左邊的地名，要落在標題框與字卡之間（北、西、南、東）：北端是 2026-09 北段新填地，
// 南端取第二階段的地名一帶；再往南的尾巴推近到最後可以被字卡蓋到
const FOCUS = [-8.5120, 179.1830, -8.5300, 179.2005];
const OCEAN = [-8.5285, 179.2000];   // 「太平洋」：頁面上的位置在 1080 寬會落到右緣安全區外，影片版往內移到離岸約 400 公尺

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

const cam = await p.evaluate(async (css, focus, ocean, W, H, PUSH) => {
  hold(); removeEventListener("resize", layout);   // 停掉自動輪播；畫框位置下面自己算
  document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);
  const oi = LABELS.findIndex(l => l.id === "ocean");
  labels[oi].style.left = fx(ocean[1]) * 100 + "%"; labels[oi].style.top = fy(ocean[0]) * 100 + "%";
  await Promise.all(imgs.map(im => im.decode())); await document.fonts.ready;
  layout();
  // 新生地要放進的那一帶：左右安全區之間、標題框下緣到最高那張字卡的上緣（各留 24px）
  const cardTop = Math.min(...STEPS.map((s, i) => { go(i); return document.querySelector(".card").getBoundingClientRect().top; }));
  go(0);
  const x0 = W * .09, x1 = W * .91, y0 = document.querySelector(".titlebar").getBoundingClientRect().bottom + 24, y1 = cardTop - 24;
  const [n, w, s, e] = focus, fw = (fx(e) - fx(w)) * IW, fh = (fy(s) - fy(n)) * IH;
  const k0 = Math.max(W / IW, H / IH);   // 起點：影像剛好鋪滿畫面（再小就露出影像邊緣）
  const k1 = Math.max(k0, Math.min(k0 * PUSH, (x1 - x0) / fw, (y1 - y0) / fh));
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  window.__cam = u => {   // u：整支片的進度 0→1。新生地對準那一帶的中心，影像不能露出邊緣
    const k = k0 + (k1 - k0) * u, sw = IW * k, sh = IH * k;
    const left = clamp((x0 + x1) / 2 - (fx(w) + fx(e)) / 2 * sw, W - sw, 0);
    const top = clamp((y0 + y1) / 2 - (fy(n) + fy(s)) / 2 * sh, H - sh, 0);
    Object.assign(stage.style, { width: sw + "px", height: sh + "px", left: left + "px", top: top + "px" });
  };
  // 換到第 i 步的第 t（0→1）：影像與新出現的地名淡入；字卡文字前四分之一淡出、換字、再淡入
  window.__fade = (i, t) => {
    const ease = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2, q = .25;
    if (t >= q && cur !== i) go(i);
    imgs[i].style.opacity = t < 1 ? ease : "";
    LABELS.forEach((l, j) => { if (l.from === i) labels[j].style.opacity = t < 1 ? ease : ""; });
    const c = t < q ? 1 - t / q : Math.min(1, (t - q) / q);
    for (const id of ["ctitle", "ctext"]) document.getElementById(id).style.opacity = c;
  };
  return { k0: +k0.toFixed(3), k1: +k1.toFixed(3), band: [Math.round(y0), Math.round(y1)] };
}, CSS, FOCUS, OCEAN, W, H, PUSH);
console.log("鏡頭", JSON.stringify(cam), `推近 ${((cam.k1 / cam.k0 - 1) * 100).toFixed(1)}%`);

// 時間軸：第一步停住 → 每一步淡入再停住 → 最後多停一下。fade＝這段在淡入第幾步（停住的段落是 null）
const steps = await p.evaluate(() => STEPS.length);
const segs = [{ sec: SEC.first, fade: null, step: 0 }];
for (let i = 1; i < steps; i++) segs.push({ sec: SEC.fade, fade: i, step: i }, { sec: SEC.hold, fade: null, step: i });
segs.at(-1).sec += SEC.end;
const total = segs.reduce((a, s) => a + Math.round(s.sec * FPS), 0);

mkdirSync(OUT, { recursive: true });
if (PREVIEW) {
  let f = 0;
  for (const s of segs) {
    const n = Math.round(s.sec * FPS);
    if (s.fade === null) {
      await p.evaluate((i, u) => { go(i); __fade(i, 1); __cam(u); }, s.step, (f + n / 2) / (total - 1));
      await p.screenshot({ path: `${OUT}preview_coast_step${s.step}.png` });
    }
    f += n;
  }
  await b.close(); console.log(`wrote ${OUT}preview_coast_step*.png`); process.exit(0);
}

const outfile = `${OUT}tuvalu-coast_1080x${H}.mp4`;
const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", outfile], { stdio: ["pipe", "inherit", "inherit"] });
let f = 0;
for (const s of segs) {
  const n = Math.round(s.sec * FPS);
  for (let j = 1; j <= n; j++, f++) {   // 鏡頭一直在推，每一幀都要重截
    await p.evaluate((fade, t, u) => { if (fade !== null) __fade(fade, t); __cam(u); }, s.fade, j / n, f / (total - 1));
    const buf = await p.screenshot({ type: "png", optimizeForSpeed: true });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  }
}
ff.stdin.end();
await new Promise(r => ff.on("close", r));
await b.close();
console.log("wrote", outfile, `${(total / FPS).toFixed(1)} 秒`);
