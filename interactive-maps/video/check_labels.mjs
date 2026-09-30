// 檢查地圖的圖釘名稱排得好不好：每個寬度列出平常藏著的名字（輪到那個點才出現）、會看錯的名字（離別的圖釘比離自己近，
// 指定邊的不算）、名字壓到別的圖釘或別的名字、超出畫框；藏著的名字另外逐一輪到它，確認出現時沒有別的名字疊在上面。
// 壓、疊、出框、出現時被疊到才算問題，有就回傳 1。放在 video/ 是因為 puppeteer 裝在這裡。
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
  await p.evaluate(() => {   // 停輪播、不標任何點：量平常的樣子；關掉淡入淡出，切換後馬上量得到
    const st = document.createElement("style"); st.textContent = "*{transition:none!important}"; document.head.appendChild(st);
    try { stopCar(); highlight(0); } catch (e) {}
  });
  await new Promise(r => setTimeout(r, 300));
  const r = await p.evaluate(() => {
    const fr = document.querySelector(".frame").getBoundingClientRect();
    const pins = [...document.querySelectorAll(".pin-anchor .pin")].map(e => { const r = e.getBoundingClientRect();
      return { n: +e.closest(".pin-anchor").dataset.spot, cx: (r.left + r.right) / 2, cy: (r.top + r.bottom) / 2, x1: r.left, y1: r.top, x2: r.right, y2: r.bottom }; });
    const labs = [...document.querySelectorAll(".toplabel")];
    const shown = () => labs.filter(l => getComputedStyle(l).display !== "none" && +getComputedStyle(l).opacity > 0);
    const box = l => { const r = l.getBoundingClientRect(); return { x1: r.left, y1: r.top, x2: r.right, y2: r.bottom }; };
    const hit = (a, c) => a.x1 < c.x2 && a.x2 > c.x1 && a.y1 < c.y2 && a.y2 > c.y1;
    const vis = shown();
    const out = { crowd: labs.filter(l => !vis.includes(l)).map(l => l.textContent), amb: [], hit: [] };
    vis.forEach((l, i) => {
      const bx = box(l), n = +l.dataset.spot;
      const d = q => Math.hypot(Math.max(bx.x1 - q.cx, 0, q.cx - bx.x2), Math.max(bx.y1 - q.cy, 0, q.cy - bx.y2));
      const own = d(pins.find(q => q.n === n)), near = pins.filter(q => q.n !== n && d(q) < own).map(q => q.n);
      const fixed = (spots.find(s => s.n === n) || {}).label;   // spots.py 指定邊的名字是 owner 點名的位置，不算
      if (near.length && !fixed) out.amb.push(`${l.textContent}→${near.join(",")}`);
      pins.forEach(q => { if (q.n !== n && hit(bx, q)) out.hit.push(`${l.textContent}壓${q.n}`); });
      vis.slice(i + 1).forEach(m => { if (hit(bx, box(m))) out.hit.push(`${l.textContent}疊${m.textContent}`); });
      if (bx.x1 < fr.left || bx.y1 < fr.top || bx.x2 > fr.right || bx.y2 > fr.bottom) out.hit.push(`${l.textContent}出框`);
    });
    for (const l of labs.filter(l => !vis.includes(l))) {   // 藏著的名字：輪到它時要出現，而且沒有別的名字疊在上面
      highlight(+l.dataset.spot);
      const now = shown(), bx = box(l);
      if (!now.includes(l)) out.hit.push(`${l.textContent}輪到也沒出現`);
      now.forEach(m => { if (m !== l && hit(bx, box(m))) out.hit.push(`${l.textContent}出現時疊${m.textContent}`); });
    }
    highlight(0);
    return out;
  });
  bad += r.hit.length;
  console.log(`${w}x${h}  輪到才出現：${r.crowd.join("、") || "無"}｜會看錯：${r.amb.join(" ") || "無"}｜壓、疊、出框：${r.hit.join(" ") || "無"}`);
  if (shot) await p.screenshot({ path: `${shot}-${Math.round(w)}.png` });
  await p.close();
}
await b.close();
process.exit(bad ? 1 : 0);
