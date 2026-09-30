// 檢查地圖的圖釘名稱排得好不好：每個寬度列出藏起來的名字、會看錯的名字（離別的圖釘比離自己近、又沒拉引線，指定邊的不算）、
// 名字壓到別的圖釘或別的名字、超出畫框，以及引線各接哪個點。有任何一項就回傳 1。放在 video/ 是因為 puppeteer 裝在這裡。
// 用法：node interactive-maps/video/check_labels.mjs <地圖 html> <寬:高,寬:高,...> [截圖檔名前綴]
//   例：node interactive-maps/video/check_labels.mjs interactive-maps/tuvalu/wide/tuvalu-map-wide.html 720:480,672:448
import path from "node:path";
import puppeteer from "puppeteer-core";

const [, , mapPath, sizes, shot] = process.argv;
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const b = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"] });
let bad = 0;
for (const s of sizes.split(",")) {
  const [w, h] = s.split(":").map(Number);
  const p = await b.newPage();
  await p.setViewport({ width: Math.ceil(w), height: Math.ceil(h), deviceScaleFactor: shot ? 2 : 1 });
  await p.goto("file:///" + path.resolve(mapPath).replace(/\\/g, "/"), { waitUntil: "networkidle0", timeout: 60000 });
  await p.evaluate(() => { try { stopCar(); } catch (e) {} });
  await new Promise(r => setTimeout(r, 300));
  const r = await p.evaluate(() => {
    const fr = document.querySelector(".frame").getBoundingClientRect();
    const pins = [...document.querySelectorAll(".pin-anchor .pin")].map(e => { const r = e.getBoundingClientRect();
      return { n: +e.closest(".pin-anchor").dataset.spot, cx: (r.left + r.right) / 2, cy: (r.top + r.bottom) / 2, x1: r.left, y1: r.top, x2: r.right, y2: r.bottom }; });
    const labs = [...document.querySelectorAll(".toplabel")];
    const vis = labs.filter(l => getComputedStyle(l).display !== "none");
    const led = new Set([...document.querySelectorAll(".leader")].map(e => +e.dataset.spot));
    const hit = (a, c) => a.left < c.x2 && a.right > c.x1 && a.top < c.y2 && a.bottom > c.y1;
    const out = { hidden: labs.filter(l => !vis.includes(l)).map(l => l.textContent), amb: [], hit: [],
      leaders: [...led].map(n => labs.find(l => +l.dataset.spot === n).textContent) };
    vis.forEach((l, i) => {
      const bx = l.getBoundingClientRect(), n = +l.dataset.spot;
      const d = q => Math.hypot(Math.max(bx.left - q.cx, 0, q.cx - bx.right), Math.max(bx.top - q.cy, 0, q.cy - bx.bottom));
      const own = d(pins.find(q => q.n === n)), near = pins.filter(q => q.n !== n && d(q) < own).map(q => q.n);
      const fixed = (spots.find(s => s.n === n) || {}).label;   // spots.py 指定邊的名字是 owner 點名的位置，不算
      if (near.length && !led.has(n) && !fixed) out.amb.push(`${l.textContent}→${near.join(",")}`);
      pins.forEach(q => { if (q.n !== n && hit(bx, q)) out.hit.push(`${l.textContent}壓${q.n}`); });
      vis.slice(i + 1).forEach(m => { const c = m.getBoundingClientRect(); if (hit(bx, { x1: c.left, y1: c.top, x2: c.right, y2: c.bottom })) out.hit.push(`${l.textContent}疊${m.textContent}`); });
      if (bx.left < fr.left || bx.top < fr.top || bx.right > fr.right || bx.bottom > fr.bottom) out.hit.push(`${l.textContent}出框`);
    });
    return out;
  });
  bad += r.hidden.length + r.amb.length + r.hit.length;
  console.log(`${w}x${h}  藏：${r.hidden.join("、") || "無"}｜會看錯：${r.amb.join(" ") || "無"}｜壓、疊、出框：${r.hit.join(" ") || "無"}｜引線：${r.leaders.join("、") || "無"}`);
  if (shot) await p.screenshot({ path: `${shot}-${Math.round(w)}.png` });
  await p.close();
}
await b.close();
process.exit(bad ? 1 : 0);
