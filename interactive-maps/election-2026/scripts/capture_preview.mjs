// 選舉地圖的驗證截圖（只在本機跑，成品放 preview/shots/，不進 repo）。
// 地圖放在 iframe 裡照嵌入寬度截（352.8 這種小數寬只能這樣量），頁面帶 ?dev 用 window.__tour.seek(ms) 定在輪播的某一刻。
// 用法（在 election-2026/ 底下）：
//   node scripts/capture_preview.mjs preview/map.html preview/worst.html            # 四種尺寸全截；worst 給 - 就跳過
//   node scripts/capture_preview.mjs preview/map.html - 352.8x627,720x480           # 只截指定尺寸
//   node scripts/capture_preview.mjs preview/map.html --video 352.8x627             # 一輪輪播的 mp4（30fps，逐幀 seek，時間照頁面的時間軸）
// puppeteer 借用 ../video/node_modules；要有 Chrome（影片另要 ffmpeg）。每個尺寸會印出輪播各段的秒數。
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve, basename, dirname, relative } from "node:path";
import { pathToFileURL } from "node:url";

const puppeteer = createRequire(resolve("../video/package.json"))("puppeteer-core");
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const [map, worst, only] = process.argv.slice(2);
const SIZES = only ? only.split(",") : ["352.8x627", "528x760", "720x480", "528x352"];

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox", "--hide-scrollbars", "--allow-file-access-from-files"] });

async function open(mapFile, size) {
  const [w, h] = size.split("x").map(Number);
  const dir = resolve("preview/shots"); mkdirSync(dir, { recursive: true });
  const wrap = resolve(dir, `_wrap_${basename(mapFile, ".html")}_${size}.html`);   // 照嵌入的樣子：iframe 就是地圖框
  writeFileSync(wrap, `<!doctype html><body style="margin:0;background:#fff"><iframe src="${relative(dirname(wrap), resolve(mapFile)).replace(/\\/g, "/")}?dev" style="display:block;border:0;width:${w}px;height:${h}px"></iframe>`);
  const page = await browser.newPage();
  await page.setViewport({ width: Math.ceil(w), height: h, deviceScaleFactor: 2 });
  await page.goto(pathToFileURL(wrap).href, { waitUntil: "networkidle0" });
  const frame = page.frames().find(f => f !== page.mainFrame());
  await frame.waitForFunction(() => window.__tour && document.fonts.status === "loaded");
  const shot = async (path, fn, arg) => {
    await frame.evaluate(fn, arg);
    await frame.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    await page.screenshot({ path, clip: { x: 0, y: 0, width: w, height: h } });
  };
  return { page, frame, shot };
}
const seek = t => window.__tour.seek(t), select = c => window.__dev.select(c);

if (worst === "--video") {
  const [w, h] = only.split("x").map(Number), { page, frame } = await open(map, only), FPS = 30;
  const cycle = await frame.evaluate(() => window.__tour.cycle);
  const outfile = resolve("preview", `tour_${only}.mp4`);
  const ff = spawn("ffmpeg", ["-y", "-v", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", outfile], { stdio: ["pipe", "inherit", "inherit"] });
  const n = Math.round(cycle / 1000 * FPS);
  for (let f = 0; f < n; f++) {
    await frame.evaluate(seek, f * 1000 / FPS);
    const buf = await page.screenshot({ type: "png", optimizeForSpeed: true, clip: { x: 0, y: 0, width: w, height: h } });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  }
  ff.stdin.end(); await new Promise(r => ff.on("close", r));
  console.log(`wrote ${outfile}（${n} 幀 ÷ ${FPS} = ${(n / FPS).toFixed(2)} 秒；一輪 ${(cycle / 1000).toFixed(2)} 秒）`);
  await browser.close(); process.exit(0);
}

for (const size of SIZES) {
  const { page, frame, shot } = await open(map, size);
  const segs = await frame.evaluate(() => window.__tour.segs);
  console.log(size, `一輪 ${(segs.at(-1).t0 + segs.at(-1).dur) / 1000} 秒`, segs.map(s => `${s.card ?? "全景"} ${(s.dur / 1000).toFixed(2)}s${s.dip ? ` 拉遠 ${s.dip.toFixed(2)} 級` : ""}`).join("｜"));
  const out = n => resolve("preview/shots", `${basename(map, ".html")}_${size}_${n}.png`);
  await shot(out("00_pano"), seek, 1000);
  for (const s of segs.filter(s => s.dur === 6000)) await shot(out(`10_${s.card}`), seek, s.t0 + 3000);   // 每個六都停著的中段
  // 每段移動飛到一半（2022 資料量下來沒有一段要拉遠飛越，所以全截）
  for (const [i, s] of segs.entries()) if (s.dip || s.dur === 1500) await shot(out(`20_fly${i}_${s.card ?? "pano"}`), seek, s.t0 + s.dur / 2);
  for (const c of ["10020", "09020", "09007", "10018", "10016"]) await shot(out(`30_click_${c}`), select, c);   // 嘉義市、金門、連江、新竹市、澎湖
  await page.close();
  if (worst && worst !== "-") {
    const W = await open(worst, size), o = n => resolve("preview/shots", `${basename(worst, ".html")}_${size}_${n}.png`);
    await W.shot(o("00_pano"), seek, 1000);
    // 開票中、已確定、長姓名、罕用字、同票、同額、延後、代碼錯、七位數
    for (const c of ["63000", "67000", "10015", "10002", "10018", "09020", "10020", "10013", "65000"]) await W.shot(o(c), select, c);
    await W.page.close();
  }
}
console.log("wrote preview/shots/*.png");
await browser.close();
