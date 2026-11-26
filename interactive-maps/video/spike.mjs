// Spike: prove the tokyo map renders in headless Chrome and its Leaflet `map` is drivable.
// Run: node spike.mjs
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const MAP = "file:///C:/Research-Lab/einfo-scratch/tokyo-bousai-map/tokyo/tokyo-bousai-map.html";

const b = await puppeteer.launch({
  executablePath: CHROME, headless: true, dumpio: true,
  userDataDir: "C:\\Users\\shawn\\AppData\\Local\\Temp\\claude-chrome-video",
  args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
    "--hide-scrollbars", "--force-device-scale-factor=1"] });
const p = await b.newPage();
await p.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
await p.goto(MAP, { waitUntil: "networkidle0", timeout: 60000 });

// map is a top-level `const` in a classic <script> → reachable by bare name in evaluate
await p.waitForFunction(
  () => typeof map !== "undefined" && document.querySelectorAll(".pin").length >= 6,
  { timeout: 30000 });

const info = await p.evaluate(() => ({
  hasMap: typeof map !== "undefined",
  zoom: map.getZoom(),
  center: map.getCenter(),
  pins: document.querySelectorAll(".pin").length,
  spots: (typeof spots !== "undefined") ? spots.map(s => ({ n: s.n, zh: s.zh, lat: s.lat, lng: s.lng })) : null,
  fns: ["jump", "showSpot", "stopCar", "startCar", "refit"].filter(f => typeof window[f] === "function" || eval(`typeof ${f} === 'function'`)),
}));
console.log(JSON.stringify(info, null, 2));

// try driving the camera + a popup, then screenshot
await p.evaluate(() => { try { stopCar(); } catch (e) {} });
await p.screenshot({ path: "spike_establishing.png" });

await p.evaluate(() => {
  const s = spots[0];
  map.setView([s.lat, s.lng], map.getZoom() + 2, { animate: false });
  try { showSpot(s.n); } catch (e) {}
});
await new Promise(r => setTimeout(r, 400));
await p.screenshot({ path: "spike_spot1.png" });

await b.close();
console.log("wrote spike_establishing.png + spike_spot1.png");
