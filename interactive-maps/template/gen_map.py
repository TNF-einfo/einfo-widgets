#!/usr/bin/env python3
"""地圖產生器（template）。用法: python template/gen_map.py [instance]（預設 tokyo）。
   讀 {instance}/spots.py（地點＋敘述）＋ {instance}/boundaries/*.geojson → 產 {instance}/<MAP_FILE>。
   無圖磚（無道路），只留行政界線＋水域；瓦紙固定配色。座標/文案/照片/地名全在 {instance}/spots.py。"""
import os, sys, json, base64, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_boundaries as fb
HERE = os.path.dirname(os.path.abspath(__file__))          # template/
ROOT = os.path.dirname(HERE)                               # 專案根
inst = sys.argv[1] if len(sys.argv) > 1 else "tokyo"
IDIR = os.path.join(ROOT, inst)
_spec = importlib.util.spec_from_file_location("cfg", os.path.join(IDIR, "spots.py"))
cfg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cfg)
_bd = os.path.join(IDIR, "boundaries"); os.makedirs(_bd, exist_ok=True)

# 1) 缺座標的 spot → Nominatim 地理編碼（快取 boundaries/geocode.json，之後離線）
_gcp = os.path.join(_bd, "geocode.json")
_gc = json.load(open(_gcp, encoding="utf-8")) if os.path.isfile(_gcp) else {}
for s in cfg.SPOTS:
    if "lat" not in s or "lng" not in s:
        key = s.get("geo") or s["zh"]
        if key not in _gc:
            g = fb.geocode(key)
            if not g: raise SystemExit("geocode failed: " + key)
            _gc[key] = g
        s["lat"], s["lng"] = _gc[key]["lat"], _gc[key]["lng"]
json.dump(_gc, open(_gcp, "w", encoding="utf-8"), ensure_ascii=False)

# 2) 界線＋地名：cfg.BOUNDARIES 有就用（如東京手調三層＋手列 PLACES），否則自動抓
if getattr(cfg, "BOUNDARIES", None):
    boundary_files, places = cfg.BOUNDARIES, cfg.PLACES
else:
    boundary_files, places = fb.ensure_boundaries(IDIR, cfg.SPOTS)
boundaries = [open(os.path.join(_bd, f), encoding="utf-8").read() for f in boundary_files]
attrib = getattr(cfg, "ATTRIB", 'boundaries © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

TPL = r"""<!-- 東京・防災・生態 另類旅遊地圖 — 環境資訊中心
     Leaflet + 內嵌行政區 GeoJSON（都縣界＋東京23區界＋鄰縣市町村界；無圖磚＝無道路，只留行政交界＋水域）。
     繁中地名（自動位移避讓、移太多才刪）、圖釘旁名稱、瓦紙固定配色、鎖死靜態、可 <iframe> 內嵌。
     界線/pin/地名皆以 Python 算圖核對。座標/文案/照片在 spots、地名在 places。 -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__｜__MARK__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root{
    --ink:#4a4038; --line:#e6d9c4;
    --paper:#f7efe0; --water:#b6d3df; --bodybg:#ece2cf;
    --label:#9a8b70; --labelbig:#83765f; --sealbl:#5a8ea0; --accent:#e07a9c;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{
    font-family:"Hiragino Maru Gothic ProN","Hiragino Sans","Noto Sans TC","Noto Sans JP",
                "PingFang TC","Microsoft JhengHei",system-ui,sans-serif;
    color:var(--ink); background:transparent;
    display:flex; align-items:center; justify-content:center; min-height:100vh; padding:0;
  }
  .frame{
    position:relative; width:720px; max-width:100%; aspect-ratio:720/476;
    border-radius:16px; overflow:hidden; background:var(--paper);   /* 不要框線/陰影，但保留圓角 */
  }
  #map{ position:absolute; inset:0; width:100%; height:100%; background:var(--water); z-index:1 }
  .leaflet-container{ background:var(--water) }
  .paper-wash{
    position:absolute; inset:0; z-index:2; pointer-events:none; mix-blend-mode:multiply;
    background:
      radial-gradient(120% 90% at 50% 40%, transparent 55%, rgba(120,90,50,.13) 100%),
      repeating-linear-gradient(135deg, rgba(255,255,255,.05) 0 3px, rgba(150,120,80,.04) 3px 6px);
  }
  .leaflet-control-attribution{ font-size:9px; background:rgba(255,255,255,.7)!important }
  .titlebar{
    position:absolute; left:12px; top:12px; z-index:6;
    background:rgba(255,255,255,.9); backdrop-filter:blur(3px);
    padding:8px 13px; border-radius:13px; border:1.5px solid #fff; box-shadow:0 4px 12px rgba(90,70,40,.14);
  }
  .titlebar .mark{ font-size:11px; letter-spacing:.15em; color:var(--accent); font-weight:800 }
  .titlebar h1{ margin:1px 0 0; font-size:18.5px; font-weight:800; letter-spacing:.02em }
  .legend{
    position:absolute; right:14px; top:14px; z-index:6; display:flex; flex-direction:column; gap:6px;
    background:rgba(255,255,255,.9); backdrop-filter:blur(3px);
    padding:10px 12px; border-radius:14px; border:2px solid #fff; box-shadow:0 5px 16px rgba(90,70,40,.16);
  }
  .chip{ display:flex; align-items:center; gap:7px; cursor:pointer; user-select:none; font-size:12.5px; font-weight:700 }
  .chip .dot{ width:13px; height:13px; border-radius:50%; flex:none; display:flex; align-items:center; justify-content:center; font-size:8px }
  .chip[data-on="0"]{ opacity:.35; text-decoration:line-through }
  .pin-anchor{ position:relative; width:23px; height:23px; transform-origin:11px 23px }
  .pin{
    width:23px; height:23px; border-radius:50% 50% 50% 0; transform:rotate(-45deg);
    border:2px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,.3);
    display:flex; align-items:center; justify-content:center;
  }
  .pin b{ transform:rotate(45deg); font-size:11px; color:#fff; font-weight:800; line-height:1 }
  .pin-anchor.hi .pin{ transform:rotate(-45deg) scale(1.25); animation:hipulse 1.6s ease-in-out infinite }
  @keyframes hipulse{
    0%,100%{ box-shadow:0 0 0 3px #fff, 0 0 0 6px rgba(224,122,156,.6), 0 5px 14px rgba(0,0,0,.35) }
    50%{ box-shadow:0 0 0 3px #fff, 0 0 0 10px rgba(224,122,156,.22), 0 5px 14px rgba(0,0,0,.35) }
  }
  .pin-name{
    position:absolute; left:27px; top:0; white-space:nowrap; font-size:14px; font-weight:800;
    color:var(--ink); background:rgba(255,255,255,.88); padding:1px 8px; border-radius:20px;
    border:1px solid var(--line); cursor:pointer; box-shadow:0 1px 3px rgba(0,0,0,.12);
  }
  /* pin 名浮層（影片版規則寫回）：抽到獨立層 → 永遠壓在所有 pin(z1)＋紙紋(z2) 之上、標題/圖例(z6)/popup(z8) 之下 */
  #toplabels{ position:absolute; inset:0; z-index:5; pointer-events:none; overflow:hidden }
  .toplabel{ position:absolute; transform:translate(-50%,-50%); white-space:nowrap; font-size:14px; font-weight:800;
    color:var(--ink); background:rgba(255,255,255,.88); padding:1px 8px; border-radius:20px;
    border:1px solid var(--line); cursor:pointer; box-shadow:0 1px 3px rgba(0,0,0,.12); pointer-events:auto }
  .rlabel{
    font-weight:800; letter-spacing:1px; font-size:12px; color:var(--label); opacity:.92; text-align:center;
    white-space:nowrap; pointer-events:none; text-shadow:0 1px 2px #fff,0 0 5px #fff,0 0 5px #fff;
  }
  .rlabel.big{ font-size:16px; letter-spacing:3px; color:var(--labelbig) }
  .rlabel.sea{ color:var(--sealbl) }
  .info{ position:absolute; left:12px; bottom:12px; z-index:8; width:282px; max-width:54%;
    max-height:75%; overflow:auto;   /* 上限＝地圖高的 3/4，超過就內部捲動不爆邊 */
    background:#fff; border-radius:13px; border:1.5px solid #fff; box-shadow:0 8px 24px rgba(90,70,40,.28);
    padding:13px; display:none; font-size:13px; line-height:1.6 }
  .info.show{ display:block }
  .info .x{ position:absolute; right:7px; top:4px; cursor:pointer; border:0; background:none;
    font-size:17px; color:#b3a894; line-height:1; padding:0 4px }
  .card .tag{ display:inline-block; font-size:10px; font-weight:800; color:#fff; padding:2px 8px; border-radius:20px }
  .card .area{ font-size:10.5px; color:#a2957f; margin-left:6px }
  .card img.photo{ width:100%; height:108px; object-fit:cover; border-radius:8px; margin:7px 0; display:block; background:#eee }   /* 照片裁切格式回到最初：固定高 108px、cover */
  .card h3{ margin:2px 0 0; font-size:15.5px }
  .card .ja{ margin:1px 0 5px; font-size:10.5px; color:#a2957f }
  .card p.desc{ margin:0 0 4px; color:#4a443b }
  .card a{ color:#4a5ab0; font-weight:800; font-size:12.5px; text-decoration:none; border-bottom:1.5px solid #c9cfea }
  /* 斷點依 e-info 三檔嵌入寬度對齊（桌機 720 / 平板 528 / 手機 352.8）；吃 iframe 自身寬度。
     小版（<720，即 e-info 平板＋手機）共用：拿掉標題/圖例、縮圖釘、地名先縮小 */
  @media (max-width:719.98px){
    .titlebar, .legend{ display:none }
    .rlabel{ font-size:11px; letter-spacing:0 } .rlabel.big{ font-size:13px; letter-spacing:1px }
    .pin-name, .toplabel{ font-size:11px }
    .info{ left:8px; bottom:8px; width:auto; max-width:44%; padding:8px; font-size:11px }
    .card img.photo{ height:64px; margin:5px 0 } .card h3{ font-size:12.5px }
  }
  /* 平板檔（對齊 e-info 528；區間 528–719.98）：地名 16、照片不裁切（原比例，popup 寬度維持、只有高度隨圖變） */
  @media (min-width:528px) and (max-width:719.98px){
    .pin-name, .toplabel{ font-size:16px }
    .card img.photo{ height:auto }
    .card[data-spot="1"] img.photo{ aspect-ratio:800/600 }   /* 地下神殿(①)原圖近正方，平板裁成 4:3、跟其他一樣大 */
  }
  /* 手機檔（對齊 e-info 352.8；≤527.98）：只留分類/照片/名稱、地名 15、popup 放大一點 */
  @media (max-width:527.98px){
    .card p.desc{ display:none }
    .card .area{ display:none }
    .pin-name, .toplabel{ font-size:15px }
    .pin-anchor{ transform:scale(.72) }   /* 手機：圖釘縮小免互相重疊（繞底尖縮放、尖點仍對準座標；量測法會吃到縮放後尺寸） */
    .info{ max-width:40%; padding:9px; font-size:12px; max-height:none; overflow:visible }   /* 手機 popup 縮小一點（寬 40%）；不要 scroll */
    .card img.photo{ height:70px } .card h3{ font-size:13px }
  }
  /* 桌機：防災商品專賣店(⑥)照片裁切範圍往上移一點 */
  @media (min-width:720px){
    .card[data-spot="6"] img.photo{ object-position:50% 30% }
  }
</style>

<div class="frame">
  <div id="map"></div>
  <div class="paper-wash"></div>
  <div class="titlebar">
    <div class="mark">__MARK__</div>
    <h1>__TITLE__</h1>
  </div>
  <div class="legend" id="legend"></div>
  <div class="info" id="info"></div>
</div>

<script>
const BOUNDARIES = __BOUNDARIES__;   // [0]=陸地(填色+粗界)，其餘=細界線
const ATTRIB = __ATTRIB__;

const CAT = __CAT__;
const spots = __SPOTS__;
const places = __PLACES__;

const map = L.map('map', {
  zoomControl:false, attributionControl:true, zoomSnap:0,   // 允許小數縮放→填滿畫面（免整數化掉一級變太小）
  dragging:false, scrollWheelZoom:false, doubleClickZoom:false,
  touchZoom:false, boxZoom:false, keyboard:false, tap:false,
});
// 圖層：BOUNDARIES[0]＝陸地填色＋粗界（無圖磚＝無道路，只留行政界＋水域），其餘＝細界線
const landLayer = L.geoJSON(BOUNDARIES[0], {
  style:{ fillColor:'#f4eee0', fillOpacity:1, color:'#c8a98f', weight:1.3, opacity:.9 },
  attribution: ATTRIB
}).addTo(map);
BOUNDARIES.slice(1).forEach(g => L.geoJSON(g, { style:{ fill:false, color:'#c3b39a', weight:0.6, opacity:.72 } }).addTo(map));

const info = document.getElementById('info');

// 圖釘
const layers = {}; Object.keys(CAT).forEach(k => layers[k] = L.layerGroup());
const bounds = [];
const cardHtml = {};   // 景點編號 → 資訊卡 HTML（給地名點擊委派用）
for (const s of spots){
  const c = CAT[s.cat];
  const icon = L.divIcon({
    className:'', iconSize:[23,23], iconAnchor:[11,23],
    html:`<div class="pin-anchor" data-spot="${s.n}">
            <div class="pin" style="background:${c.color}"><b>${s.n}</b></div>
            <span class="pin-name" data-spot="${s.n}">${s.short||s.zh}</span>
          </div>`
  });
  const photo = s.img;
  const html =
    `<div class="card" data-spot="${s.n}">
       <span class="tag" style="background:${c.color}">${c.emo} ${c.name}</span>
       <span class="area">${s.area}</span>
       <img class="photo" src="${photo}" alt="${s.zh}" loading="lazy">
       <h3>${s.zh}</h3><p class="ja">${s.ja}</p>
       <p class="desc">${s.desc}</p>
     </div>`;
  cardHtml[s.n] = html;
  L.marker([s.lat, s.lng], { icon, keyboard:false, zIndexOffset:1000 })
    .on('click', () => jump(s.n))
    .addTo(layers[s.cat]);
  bounds.push([s.lat, s.lng]);
}
Object.values(layers).forEach(l => l.addTo(map));
// 點圖釘旁的地名也開資訊卡（事件委派：地名溢出 icon 框、冒泡接不到，改在容器上聽 .pin-name）
map.getContainer().addEventListener('click', e => {
  const nm = e.target.closest && e.target.closest('.pin-name');
  if (nm && cardHtml[nm.dataset.spot]) jump(+nm.dataset.spot);
});

// 依畫面大小 fit（小螢幕留白縮小，內容才不會太小）；北本(②)在最西北、左上多留白免被標題框擋
function refit(){
  const small = window.matchMedia('(max-width:719.98px)').matches;   // 跟 CSS 斷點一致（非桌機＝<720）
  const phone = window.matchMedia('(max-width:527.98px)').matches;   // 手機檔（純寬度、與 CSS 一致）
  let P;
  if (small){
    const shift = phone ? map.getSize().x / 6 : 0;   // 手機檔：地圖往右移 1/6
    P = { tl:[36 + shift, 44], br:[64, 36] };
  } else {
    P = { tl:[124,114], br:[104,56] };   // 桌機：四邊留白＝縮小、左多＝右移、上避標題、右給 BOUSAI
  }
  map.fitBounds(bounds, { paddingTopLeft:P.tl, paddingBottomRight:P.br, animate:false });
}

// ── Auto Layout（量測法）：pin名/地名 自動避開 pin圖示＋popup＋彼此；碰撞優先上下移、換邊最後。
//    全用螢幕座標 getBoundingClientRect（旋轉/縮放/字級都量到實際值），不再手動移標籤。
const overlap = (a,b) => a.x1<b.x2 && a.x2>b.x1 && a.y1<b.y2 && a.y2>b.y1;
const overlapArea = (a,b) => Math.max(0, Math.min(a.x2,b.x2)-Math.max(a.x1,b.x1)) * Math.max(0, Math.min(a.y2,b.y2)-Math.max(a.y1,b.y1));
const asBox = r => ({ x1:r.left, y1:r.top, x2:r.right, y2:r.bottom });
let labelMarkers = [];

// 障礙基底（非 pin）：popup（先秀 spot1＝敘述最長那張、量其框）＋標題框。pin 由 layoutPinNames 自算，不在此重複放。
function baseObstacles(){
  const occ = [];
  try { stopCar(); } catch(e){}
  showSpot(1);
  const ir = document.getElementById('info').getBoundingClientRect();
  if (ir.width > 1) occ.push({ x1:ir.left-4, y1:ir.top-4, x2:ir.right+4, y2:ir.bottom+4 });
  const tb = document.querySelector('.titlebar');   // 標題框也當障礙（影片版定案；owner：北本被標題壓）——手機隱藏時 width≈0 自動略過
  if (tb){ const tr = tb.getBoundingClientRect();
    if (tr.width > 1) occ.push({ x1:tr.left-6, y1:tr.top-6, x2:tr.right+6, y2:tr.bottom+6 }); }
  return occ;
}

// ⚠ layoutPinNames／placeLabels＝ video/make_video.mjs 依賴的固定介面（簽名與行為勿改）；
//   gen_map 靜態圖的「影片版規則」（pin 名浮層＋行政區 cap/farthest）走下方 gen_map 專用的 liftPinNames／capDistricts。
// pin 地點名候選順序：右中→右上→右下→上→下→左中→左上→左下（碰撞優先上下移、換邊最後）
const NAME_POS = [
  { left:'34px', top:'50%', transform:'translateY(-50%)' },      // 右中（預設；34 = pin半徑16+外擴6+餘裕，clear 障礙框）
  { left:'34px', bottom:'16px' },                                 // 右上
  { left:'34px', top:'17px' },                                    // 右下
  { left:'50%', bottom:'34px', transform:'translateX(-50%)' },    // 正上
  { left:'50%', top:'34px', transform:'translateX(-50%)' },       // 正下
  { right:'34px', top:'50%', transform:'translateY(-50%)' },      // 左中
  { right:'34px', bottom:'16px' },                                // 左上
  { right:'34px', top:'17px' },                                   // 左下
];
function setPos(el, c){
  el.style.left = c.left || ''; el.style.right = c.right || '';
  el.style.top = c.top || ''; el.style.bottom = c.bottom || ''; el.style.transform = c.transform || '';
}
function layoutPinNames(occ, frame){   // 原介面（make_video 依賴）：就地定位 .pin-name span、避開 occ+彼此
  document.querySelectorAll('.pin-anchor').forEach(a => {
    const el = a.querySelector('.pin-name');
    let bestC = NAME_POS[0], bestBox = null, bestPen = Infinity, clear = false;
    for (const c of NAME_POS){
      setPos(el, c);
      const b = asBox(el.getBoundingClientRect());
      const outFrame = Math.max(0, frame.x1-b.x1) + Math.max(0, b.x2-frame.x2)
                     + Math.max(0, frame.y1-b.y1) + Math.max(0, b.y2-frame.y2);
      const pen = occ.reduce((s,o) => s + overlapArea(b,o), 0) + outFrame*80;
      if (pen === 0){ bestBox = b; clear = true; break; }
      if (pen < bestPen){ bestPen = pen; bestC = c; bestBox = b; }
    }
    if (!clear) setPos(el, bestC);
    occ.push(bestBox);
  });
}

// ── 以下 gen_map 靜態圖專用（make_video 不呼叫）：影片版標籤規則寫回 ──
// pin 名抽到 #toplabels 浮層 → 永遠壓在所有 pin(marker) 之上（跨 marker 的 z-index 對獨立 marker 無效，故抽出獨立層）；
// 自做避讓：候選順序右→上→左→下→右上→左上，閃不掉才選「壓最少」；避開 pin icon＋標題框/popup(occ)＋彼此，出框重罰。
function ensureTopLayer(){
  let top = document.getElementById('toplabels');
  if (!top){
    top = document.createElement('div'); top.id = 'toplabels';
    document.querySelector('.frame').appendChild(top);
    top.addEventListener('click', e => { const t = e.target.closest && e.target.closest('.toplabel');
      if (t && cardHtml[t.dataset.spot]) jump(+t.dataset.spot); });   // 點浮層名字＝開該景點資訊卡
  }
  return top;
}
function liftPinNames(occ, frame){
  const top = ensureTopLayer(); top.innerHTML = '';
  const fr = document.querySelector('.frame').getBoundingClientRect();
  const anchors = [...document.querySelectorAll('.pin-anchor')];
  const pins = anchors.map(a => { const r = a.querySelector('.pin').getBoundingClientRect();
    return { cx:(r.left+r.right)/2, cy:(r.top+r.bottom)/2, hw:(r.right-r.left)/2, hh:(r.bottom-r.top)/2, spot:+a.dataset.spot }; });
  anchors.forEach(a => { const nm = a.querySelector('.pin-name'); if (!nm) return;   // 原生 pin 名隱藏、改由浮層渲染
    const lab = document.createElement('div'); lab.className = 'toplabel'; lab.textContent = nm.textContent;
    lab.dataset.spot = a.dataset.spot; top.appendChild(lab); nm.style.display = 'none'; });
  const placed = [];
  top.querySelectorAll('.toplabel').forEach(lab => {
    const spot = +lab.dataset.spot, P = pins.find(p => p.spot === spot);
    const lr = lab.getBoundingClientRect(), lw = lr.width/2, lh = lr.height/2, G = P.hw + 12, V = P.hh + 12;
    const cands = [[G+lw,0],[0,-(V+lh)],[-(G+lw),0],[0,V+lh],[G+lw,-(V+lh)],[-(G+lw),-(V+lh)]];  // 右→上→左→下→右上→左上
    let best = cands[0], bestPen = Infinity;
    for (const [ox,oy] of cands){
      const bx = { x1:P.cx+ox-lw, y1:P.cy+oy-lh, x2:P.cx+ox+lw, y2:P.cy+oy+lh };
      let pen = 0;
      for (const q of pins) if (q.spot !== spot) pen += overlapArea(bx, { x1:q.cx-q.hw-4, y1:q.cy-q.hh-4, x2:q.cx+q.hw+4, y2:q.cy+q.hh+4 }) * 8;  // 壓別 pin＝重罰
      for (const o of occ) pen += overlapArea(bx, o) * 8;   // 壓標題框／popup（occ 內障礙）＝重罰
      for (const b of placed) pen += overlapArea(bx, b);    // 壓別名字＝輕罰
      pen += (Math.max(0,fr.left-bx.x1)+Math.max(0,bx.x2-fr.right)+Math.max(0,fr.top-bx.y1)+Math.max(0,bx.y2-fr.bottom)) * 3;  // 出框
      if (pen === 0){ best = [ox,oy]; break; }
      if (pen < bestPen){ bestPen = pen; best = [ox,oy]; }
    }
    const [ox,oy] = best;
    placed.push({ x1:P.cx+ox-lw, y1:P.cy+oy-lh, x2:P.cx+ox+lw, y2:P.cy+oy+lh });
    lab.style.left = (P.cx - fr.left + ox) + 'px'; lab.style.top = (P.cy - fr.top + oy) + 'px';
  });
}

// RCAND：地名候選位移（原點→上下→左右）——make_video 的 placeLabels 與 gen_map 的 placeDistricts 共用
const RCAND = [[0,0],[0,-18],[0,18],[0,-34],[0,34],[-44,0],[46,0],[-44,-18],[46,-18],[-44,18],[46,18],[-76,0],[78,0]];
function placeLabels(occ, frame){   // 原介面（make_video 依賴，勿改）：地名排到滿、避開 occ+彼此、塞不下略過
  labelMarkers.forEach(m => map.removeLayer(m)); labelMarkers = [];
  const cont = document.getElementById('map').getBoundingClientRect();
  for (const p of places){
    const cp = map.latLngToContainerPoint([p.lat, p.lng]);
    const bx = cont.left + cp.x, by = cont.top + cp.y;
    const fw = p.big ? 16 : 12, w = [...p.t].length * fw + 8, h = p.big ? 22 : 18;
    let chosen = null;
    for (const [dx,dy] of RCAND){
      const cx = bx+dx, cy = by+dy, box = { x1:cx-w/2, y1:cy-h/2, x2:cx+w/2, y2:cy+h/2 };
      const inFrame = box.x1 >= frame.x1+1 && box.y1 >= frame.y1+1 && box.x2 <= frame.x2-1 && box.y2 <= frame.y2-1;
      if (inFrame && !occ.some(o => overlap(box,o))){ chosen = {cx,cy,box}; break; }
    }
    if (!chosen) continue;
    occ.push(chosen.box);
    const cls = 'rlabel' + (p.big?' big':'') + (p.sea?' sea':'');
    const ll = map.containerPointToLatLng([chosen.cx - cont.left, chosen.cy - cont.top]);
    const mk = L.marker(ll, { interactive:false, keyboard:false,
      icon:L.divIcon({ className:cls, html:p.t, iconSize:[Math.ceil(w),Math.ceil(h)], iconAnchor:[Math.ceil(w/2),Math.ceil(h/2)] }) }).addTo(map);
    labelMarkers.push(mk);
  }
}

// gen_map 靜態圖專用（make_video 不呼叫）：行政區地名 只避「標題框＋popup」與彼此（**可被 pin／pin 名蓋，owner 定**）；
// 先為每個地名找框內候選位，再篩最多 10——先放 big（縣/市/灣＝本在邊緣＝四散），其餘 farthest-point 填、四散全圖不集中中間。
function placeDistricts(frame){
  labelMarkers.forEach(m => map.removeLayer(m)); labelMarkers = [];
  const cont = document.getElementById('map').getBoundingClientRect();
  const avoid = [];   // 只避標題框＋popup（地名可被 pin／pin 名蓋）
  const tb = document.querySelector('.titlebar');
  if (tb){ const tr = tb.getBoundingClientRect(); if (tr.width > 1) avoid.push({ x1:tr.left-6, y1:tr.top-6, x2:tr.right+6, y2:tr.bottom+6 }); }
  const ir = document.getElementById('info').getBoundingClientRect();
  if (ir.width > 1) avoid.push({ x1:ir.left-4, y1:ir.top-4, x2:ir.right+4, y2:ir.bottom+4 });
  const cand = [];
  for (const p of places){
    const cp = map.latLngToContainerPoint([p.lat, p.lng]);
    const bx = cont.left + cp.x, by = cont.top + cp.y;
    const fw = p.big ? 16 : 12, w = [...p.t].length * fw + 8, h = p.big ? 22 : 18;
    let chosen = null;
    for (const [dx,dy] of RCAND){
      const cx = bx+dx, cy = by+dy, box = { x1:cx-w/2, y1:cy-h/2, x2:cx+w/2, y2:cy+h/2 };
      const inFrame = box.x1 >= frame.x1+1 && box.y1 >= frame.y1+1 && box.x2 <= frame.x2-1 && box.y2 <= frame.y2-1;
      if (inFrame && !avoid.some(o => overlap(box,o))){ chosen = {cx,cy,box}; break; }
    }
    if (chosen) cand.push({ p, cx:chosen.cx, cy:chosen.cy, box:chosen.box, big:!!p.big, w, h });
  }
  const ctr = b => [(b.x1+b.x2)/2, (b.y1+b.y2)/2];
  const kept = [], keptBox = [];
  const tryAdd = c => { if (kept.length < 10 && !keptBox.some(k => overlap(c.box,k))){ kept.push(c); keptBox.push(c.box); return true; } return false; };
  for (const c of cand.filter(c => c.big)) tryAdd(c);        // 先放 big（本在邊緣）
  const pool = cand.filter(c => !c.big);
  while (kept.length < 10 && pool.length){                    // 其餘 farthest-point 填到 10＝四散全圖
    let bi = -1, bd = -1;
    for (let i = 0; i < pool.length; i++){
      if (keptBox.some(k => overlap(pool[i].box, k))) continue;
      const [px,py] = ctr(pool[i].box);
      let md = keptBox.length ? Infinity : 1e9;
      for (const k of keptBox){ const [kx,ky] = ctr(k); md = Math.min(md, Math.hypot(px-kx, py-ky)); }
      if (md > bd){ bd = md; bi = i; }
    }
    if (bi < 0) break;
    const c = pool.splice(bi,1)[0]; kept.push(c); keptBox.push(c.box);
  }
  for (const c of kept){
    const cls = 'rlabel' + (c.p.big?' big':'') + (c.p.sea?' sea':'');
    const ll = map.containerPointToLatLng([c.cx - cont.left, c.cy - cont.top]);
    const mk = L.marker(ll, { interactive:false, keyboard:false,
      icon:L.divIcon({ className:cls, html:c.p.t, iconSize:[Math.ceil(c.w),Math.ceil(c.h)], iconAnchor:[Math.ceil(c.w/2),Math.ceil(c.h/2)] }) }).addTo(map);
    labelMarkers.push(mk);
  }
}
// popup 自動選「圖釘最少」的角落（任意城市：spots 群聚時 popup 才不壓到 pin）
function pickPopupCorner(){
  const info = document.getElementById('info');
  const fr = document.querySelector('.frame').getBoundingClientRect();
  const cx = fr.left + fr.width/2, cy = fr.top + fr.height/2, cnt = { tl:0, tr:0, bl:0, br:0 };
  document.querySelectorAll('.pin').forEach(p => {
    const r = p.getBoundingClientRect();
    cnt[((r.top+r.bottom)/2 < cy ? 't':'b') + ((r.left+r.right)/2 < cx ? 'l':'r')]++;
  });
  const corner = ['bl','br','tl','tr'].sort((a,b) => cnt[a]-cnt[b])[0];   // 圖釘最少者；平手偏左下
  const off = (window.matchMedia('(max-width:719.98px)').matches ? 8 : 12) + 'px';
  info.style.top    = corner[0]==='t' ? off : 'auto';
  info.style.bottom = corner[0]==='b' ? off : 'auto';
  info.style.left   = corner[1]==='l' ? off : 'auto';
  info.style.right  = corner[1]==='r' ? off : 'auto';
}
function relayout(){
  const frame = asBox(document.querySelector('.frame').getBoundingClientRect());
  pickPopupCorner();
  const occ = baseObstacles();     // popup + 標題框（pin 由 liftPinNames 自算）
  liftPinNames(occ, frame);        // pin 名 → #toplabels 浮層（壓在所有 pin 之上）
  placeDistricts(frame);           // 行政區 cap-10 + farthest-spread（可被 pin/名蓋）
}

// 說明輪播：桌機自動輪播 6 景點說明、對應圖釘加脈動高亮；手機不輪播並收起說明
function isSmall(){ return window.matchMedia('(max-width:719.98px)').matches; }
let carTimer = null, curSpot = 0;
function highlight(n){
  document.querySelectorAll('.pin-anchor.hi').forEach(el => el.classList.remove('hi'));
  const el = document.querySelector('.pin-anchor[data-spot="' + n + '"]');
  if (el) el.classList.add('hi');
}
function showSpot(n){
  curSpot = n;
  info.innerHTML = '<button class="x" aria-label="關閉">×</button>' + cardHtml[n];
  info.classList.add('show'); highlight(n);
  info.querySelector('.x').onclick = () => { stopCar(); info.classList.remove('show'); highlight(0); };
}
function carMs(){ return window.matchMedia('(max-width:527.98px)').matches ? 2750 : 4200; }   // 手機檔 2.75s、其餘 4.2s
function carTick(){ showSpot(curSpot % spots.length + 1); }
function startCar(){ if (carTimer) return; carTick(); carTimer = setInterval(carTick, carMs()); }   // 桌機/手機都輪播
function stopCar(){ if (carTimer){ clearInterval(carTimer); carTimer = null; } }
function jump(n){ showSpot(n); stopCar(); carTimer = setInterval(carTick, carMs()); }   // 點某點：跳到它並重置輪播
function syncCar(){ startCar(); }
refit(); relayout(); syncCar();   // 初次：fit → 自動排標籤（此時 showSpot 已定義）→ 開輪播

map.on('resize', () => { refit(); relayout(); syncCar(); });   // 縮放/轉向後重 fit＋重算避讓＋輪播開關

// 圖例 + 篩選
const legend = document.getElementById('legend');
for (const [key,c] of Object.entries(CAT)){
  const chip = document.createElement('div');
  chip.className = 'chip'; chip.dataset.cat = key; chip.dataset.on = '1';
  chip.innerHTML = `<span class="dot" style="background:${c.color}">${c.emo}</span>${c.name}`;
  chip.addEventListener('click', () => {
    const on = chip.dataset.on === '1'; chip.dataset.on = on ? '0' : '1';
    if (on) map.removeLayer(layers[key]); else layers[key].addTo(map);
    relayout();   // 篩選後重排標籤
  });
  legend.appendChild(chip);
}
</script>
"""

html = (TPL
        .replace("__BOUNDARIES__", "[" + ",".join(boundaries) + "]")
        .replace("__ATTRIB__", json.dumps(attrib, ensure_ascii=False))
        .replace("__CAT__", json.dumps(cfg.CAT, ensure_ascii=False))
        .replace("__SPOTS__", json.dumps(cfg.SPOTS, ensure_ascii=False))
        .replace("__PLACES__", json.dumps(places, ensure_ascii=False))
        .replace("__TITLE__", cfg.TITLE).replace("__MARK__", cfg.MARK))
out = os.path.join(IDIR, cfg.MAP_FILE)
open(out, "w", encoding="utf-8").write(html)
print("wrote", out, "KB:", round(len(html.encode())/1024, 1))

# 文章內嵌示意頁：把整張地圖 base64 內嵌（複製鈕本地解碼、不需 fetch → file:// 也能用）
b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
ap = (open(os.path.join(HERE, "article_preview.tpl.html"), encoding="utf-8").read()
      .replace("__MAP_FILE__", cfg.MAP_FILE)
      .replace("__MAP_TITLE__", cfg.TITLE + "｜" + cfg.MARK)
      .replace("@@MAP_B64@@", b64))
ap_out = os.path.join(IDIR, "article-preview.html")
open(ap_out, "w", encoding="utf-8").write(ap)
print("wrote", ap_out, "KB:", round(len(ap.encode())/1024, 1))

# 純地圖外包一層 iframe（隔離＋自足）：整張地圖轉義塞進 <iframe srcdoc>，此檔可直接開預覽，
# 或複製 <div> 區塊貼進文章（等同 article-preview 的「複製完整嵌入碼」，但免開頁點鈕）。
esc = html.replace("&", "&amp;").replace('"', "&quot;")  # srcdoc 屬性用雙引號，需轉 & 與 "
embed = ('<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
         '<title>' + cfg.TITLE + '｜iframe 嵌入</title>\n'
         '<div style="position:relative;max-width:720px;margin:auto;aspect-ratio:720/476">\n'
         '  <iframe loading="lazy" allowfullscreen srcdoc="' + esc + '"\n'
         '          style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px"></iframe>\n'
         '</div>\n</html>\n')
embed_out = os.path.join(IDIR, cfg.MAP_FILE.replace(".html", ".embed.html"))
open(embed_out, "w", encoding="utf-8").write(embed)
print("wrote", embed_out, "KB:", round(len(embed.encode())/1024, 1))
