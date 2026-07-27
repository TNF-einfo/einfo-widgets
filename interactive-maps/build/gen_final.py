#!/usr/bin/env python3
"""產生 tokyo-bousai-map.html：都縣界+東京23區界+其他縣市町村界 + 更多地名(自動位移避讓)。
   瓦紙(washi)固定配色。"""
import os
BASE = os.path.dirname(os.path.abspath(__file__))   # geojson 與本檔同在 build/
kanto  = open(BASE + r"\kanto.geojson", encoding="utf-8").read()
ku     = open(BASE + r"\tokyo_ku.geojson", encoding="utf-8").read()
others = open(BASE + r"\others_muni.geojson", encoding="utf-8").read()

TPL = r"""<!-- 東京・防災・生態 另類旅遊地圖 — 環境資訊中心
     Leaflet + 內嵌行政區 GeoJSON（都縣界＋東京23區界＋鄰縣市町村界；無圖磚＝無道路，只留行政交界＋水域）。
     繁中地名（自動位移避讓、移太多才刪）、圖釘旁名稱、瓦紙固定配色、鎖死靜態、可 <iframe> 內嵌。
     界線/pin/地名皆以 Python 算圖核對。座標/文案/照片在 spots、地名在 places。 -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>東京・防災・生態 另類旅遊地圖｜環境資訊中心</title>
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
  .pin-name.left{ left:auto; right:27px }
  .pin-name.tr{ left:10px; top:auto; bottom:22px }   /* 右上：往上抬＋略右 */
  .pin-name.down{ top:10px }   /* 野鳥公園：名稱略往下，避開鄰近標籤（各版皆套用） */
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
    .pin-anchor{ transform:scale(.8) }   /* 圖釘＋名稱縮小（繞底尖縮放、尖點仍對準座標），免重疊 */
    .pin-name{ font-size:11px; left:25px } .pin-name.left{ right:25px }
    .info{ left:8px; bottom:8px; width:auto; max-width:44%; padding:8px; font-size:11px }
    .card img.photo{ height:64px; margin:5px 0 } .card h3{ font-size:12.5px }
  }
  /* 平板檔（對齊 e-info 528；區間 528–719.98）：地名 16、照片不裁切（原比例，popup 寬度維持、只有高度隨圖變） */
  @media (min-width:528px) and (max-width:719.98px){
    .pin-name{ font-size:16px }
    .card img.photo{ height:auto }
    .card[data-spot="1"] img.photo{ aspect-ratio:800/600 }   /* 地下神殿(①)原圖近正方，平板裁成 4:3、跟其他一樣大 */
  }
  /* 手機檔（對齊 e-info 352.8；≤527.98）：只留分類/照片/名稱、地名 15、popup 放大一點 */
  @media (max-width:527.98px){
    .card p.desc{ display:none }
    .card .area{ display:none }
    .pin-name{ font-size:15px }
    .info{ max-width:40%; padding:9px; font-size:12px; max-height:none; overflow:visible }   /* 手機 popup 縮小一點（寬 40%）；不要 scroll */
    .card img.photo{ height:70px } .card h3{ font-size:13px }
  }
  /* 桌機＋平板（≥528，即非手機）：北本自然觀察公園(②)名稱移到 pin 右側；手機維持右上 */
  @media (min-width:528px){
    .pin-name[data-spot="2"]{ left:27px; top:0; bottom:auto }
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
    <div class="mark">環境資訊中心</div>
    <h1>東京・防災・生態 另類旅遊地圖</h1>
  </div>
  <div class="legend" id="legend"></div>
  <div class="info" id="info"></div>
</div>

<script>
const KANTO = __KANTO__;
const KU = __KU__;
const OTHERS = __OTHERS__;

const CAT = {
  bousai:{ name:'防災探索', color:'#4a5ab0', emo:'⛑' },
  nature:{ name:'自然生態', color:'#5fae72', emo:'🌿' },
  shop:  { name:'採購名單', color:'#e07a9c', emo:'🛍' },
};
const spots = [
  { n:1, cat:'bousai', lat:35.997475, lng:139.8114455, area:'埼玉・春日部',
    zh:'地下神殿・龍Q館', ja:'首都圏外郭放水路 龍Q館',
    img:'https://e-info.org.tw/images/e29e8885-4ce9-49d3-b147-b292bccca37b-w800.webP',
    desc:'地底22公尺、面積是希臘帕德嫩神殿6.4倍的排水「調壓水槽」，防洪時排水、平時開放參觀。七種行程可選，還能俯瞰約70公尺深、可容納一架太空梭的豎井。',
    url:'https://e-info.org.tw/node/243576' },
  { n:2, cat:'nature', lat:36.0113203, lng:139.5091906, area:'埼玉・北本', pinTR:1,
    zh:'北本自然觀察公園', ja:'北本自然観察公園',
    img:'https://e-info.org.tw/images/8de3a00f-d626-4775-9a52-b45aec55f836-w800.webP',
    desc:'貼近里山風景的自然觀察公園，附設埼玉縣自然學習中心，入場免費，適合放慢腳步賞自然。',
    url:'https://e-info.org.tw/node/243428' },
  { n:3, cat:'bousai', lat:35.7280647, lng:139.7070079, area:'東京・池袋', pinTR:1,
    zh:'池袋防災館', ja:'池袋防災館（東京消防庁）',
    img:'https://e-info.org.tw/images/c0de1ff4-42e4-499b-942c-9eee4590eef1-w800.webP',
    desc:'逛街順路就能體驗的地震模擬──不是主題樂園式的尖叫，同事親身心得是：「我覺得快死掉了！」',
    url:'' },
  { n:4, cat:'bousai', lat:35.6349494, lng:139.7958032, area:'東京・有明',
    zh:'臨海廣域防災公園', ja:'東京臨海広域防災公園（そなエリア東京）',
    img:'https://e-info.org.tw/images/e5d34109-50bc-48c4-8181-970dee66e21f-w800.webP',
    desc:'東京的緊急避難地與災害指揮中心。長椅可當爐灶、涼亭變救護區；常設體驗「東京直下72小時」實境逃生，離豐洲市場不遠。',
    url:'' },
  { n:5, cat:'nature', lat:35.5838724, lng:139.7603075, area:'東京・大田', pinDown:1,
    zh:'東京港野鳥公園', ja:'東京港野鳥公園',
    img:'https://e-info.org.tw/images/f07f0241-5104-4121-ab91-dc3a497e9ddb-w800.webP',
    desc:'夾在批發市場與物流中心之間的生態聖域，是東京灣邊的賞鳥好去處。',
    url:'' },
  { n:6, cat:'shop', lat:35.7113, lng:139.8678, area:'東京・江戸川', short:'防災商品專賣店',
    zh:'防災商品專賣店 BOUSAI FARM', ja:'防災ファーム 江戸川中央店',
    img:'https://e-info.org.tw/images/9b881cf3-021e-4ab0-a886-a3d3bd205774-w800.webP',
    desc:'由防災士嚴選商品的防災專門店，記者專訪過的採購祕境，想找更專業裝備就來這。',
    url:'' },
];
const places = [
  { t:'埼玉縣', lat:35.95, lng:139.56, big:1 },
  { t:'千葉縣', lat:35.66, lng:139.905, big:1 },
  { t:'神奈川縣', lat:35.52, lng:139.62, big:1 },
  { t:'東京灣', lat:35.575, lng:139.85, big:1, sea:1 },
  { t:'春日部市', lat:35.975, lng:139.752 },
  { t:'越谷市', lat:35.891, lng:139.790 },
  { t:'草加市', lat:35.825, lng:139.805 },
  { t:'川口市', lat:35.808, lng:139.724 },
  { t:'埼玉市', lat:35.906, lng:139.624 },
  { t:'上尾市', lat:35.977, lng:139.593 },
  { t:'北本市', lat:36.027, lng:139.530 },
  { t:'三鄉市', lat:35.833, lng:139.872 },
  { t:'松戶市', lat:35.788, lng:139.903 },
  { t:'流山市', lat:35.856, lng:139.902 },
  { t:'川崎市', lat:35.531, lng:139.703 },
  { t:'武藏野市', lat:35.718, lng:139.566 },
  { t:'千代田區', lat:35.694, lng:139.753 },
  { t:'中央區', lat:35.667, lng:139.772 },
  { t:'港區', lat:35.658, lng:139.752 },
  { t:'新宿區', lat:35.694, lng:139.703 },
  { t:'文京區', lat:35.708, lng:139.752 },
  { t:'台東區', lat:35.713, lng:139.780 },
  { t:'墨田區', lat:35.710, lng:139.801 },
  { t:'江東區', lat:35.673, lng:139.817 },
  { t:'品川區', lat:35.609, lng:139.730 },
  { t:'目黑區', lat:35.641, lng:139.698 },
  { t:'大田區', lat:35.561, lng:139.716 },
  { t:'世田谷區', lat:35.646, lng:139.653 },
  { t:'澀谷區', lat:35.664, lng:139.698 },
  { t:'中野區', lat:35.707, lng:139.664 },
  { t:'杉並區', lat:35.700, lng:139.636 },
  { t:'豐島區', lat:35.726, lng:139.716 },
  { t:'北區', lat:35.753, lng:139.734 },
  { t:'荒川區', lat:35.736, lng:139.783 },
  { t:'板橋區', lat:35.751, lng:139.709 },
  { t:'練馬區', lat:35.735, lng:139.652 },
  { t:'足立區', lat:35.775, lng:139.805 },
  { t:'葛飾區', lat:35.744, lng:139.847 },
  { t:'江戶川區', lat:35.706, lng:139.868 },
];

const map = L.map('map', {
  zoomControl:false, attributionControl:true, zoomSnap:0,   // 允許小數縮放→填滿畫面（免整數化掉一級變太小）
  dragging:false, scrollWheelZoom:false, doubleClickZoom:false,
  touchZoom:false, boxZoom:false, keyboard:false, tap:false,
});
// 圖層：都縣界(陸地填色+縣界/海岸線)、其他縣市町村界(細線)、東京23區界(細線)
const landLayer = L.geoJSON(KANTO, {
  style:{ fillColor:'#f4eee0', fillOpacity:1, color:'#c8a98f', weight:1.3, opacity:.9 },
  attribution:'境界資料 © <a href="https://github.com/dataofjapan/land">dataofjapan/land</a>・<a href="https://github.com/smartnews-smri/japan-topography">japan-topography</a>'
}).addTo(map);
const muniOther = L.geoJSON(OTHERS, { style:{ fill:false, color:'#c3b39a', weight:0.6, opacity:.7 } }).addTo(map);
const muniKu    = L.geoJSON(KU,     { style:{ fill:false, color:'#c3b39a', weight:0.6, opacity:.75 } }).addTo(map);

const info = document.getElementById('info');

// 圖釘
const layers = { bousai:L.layerGroup(), nature:L.layerGroup(), shop:L.layerGroup() };
const bounds = [];
const cardHtml = {};   // 景點編號 → 資訊卡 HTML（給地名點擊委派用）
for (const s of spots){
  const c = CAT[s.cat];
  const icon = L.divIcon({
    className:'', iconSize:[23,23], iconAnchor:[11,23],
    html:`<div class="pin-anchor" data-spot="${s.n}">
            <div class="pin" style="background:${c.color}"><b>${s.n}</b></div>
            <span class="pin-name${s.pinLeft?' left':''}${s.pinTR?' tr':''}${s.pinDown?' down':''}" data-spot="${s.n}">${s.short||s.zh}</span>
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

// 繁中地名：自動位移避讓（圖釘優先；重疊就試位移，都塞不下才刪）。抽成函式＝縮放後可重算
const nearPin = (a,b) => Math.abs(a.x-b.x)<86 && Math.abs(a.y-b.y)<28;
const nearLbl = (a,b) => Math.abs(a.x-b.x)<60 && Math.abs(a.y-b.y)<20;
const CAND = [[0,0],[0,-15],[0,16],[-42,0],[44,0],[-42,-15],[44,-15],[-42,16],[44,16],[0,-30],[0,32],[-70,0],[72,0]];
let labelMarkers = [];
function placeLabels(){
  labelMarkers.forEach(m => map.removeLayer(m)); labelMarkers = [];
  const pinPts = spots.map(s => map.latLngToLayerPoint([s.lat, s.lng]));
  const lblPts = [];
  for (const p of places){
    const base = map.latLngToLayerPoint([p.lat, p.lng]);
    let chosen = null;
    for (const [dx,dy] of CAND){
      const pt = { x:base.x+dx, y:base.y+dy };
      if (!pinPts.some(q=>nearPin(pt,q)) && !lblPts.some(q=>nearLbl(pt,q))){ chosen = pt; break; }
    }
    if (!chosen) continue;
    lblPts.push(chosen);
    const cls = 'rlabel' + (p.big?' big':'') + (p.sea?' sea':'');
    const mk = L.marker(map.layerPointToLatLng([chosen.x, chosen.y]), {
      interactive:false, keyboard:false,
      icon:L.divIcon({ className:cls, html:p.t, iconSize:[120,20], iconAnchor:[60,10] })
    }).addTo(map);
    labelMarkers.push(mk);
  }
}
refit(); placeLabels();

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
syncCar();

map.on('resize', () => { refit(); placeLabels(); syncCar(); });   // 縮放/轉向後重 fit＋重算避讓＋輪播開關

// 圖例 + 篩選
const legend = document.getElementById('legend');
for (const [key,c] of Object.entries(CAT)){
  const chip = document.createElement('div');
  chip.className = 'chip'; chip.dataset.cat = key; chip.dataset.on = '1';
  chip.innerHTML = `<span class="dot" style="background:${c.color}">${c.emo}</span>${c.name}`;
  chip.addEventListener('click', () => {
    const on = chip.dataset.on === '1'; chip.dataset.on = on ? '0' : '1';
    if (on) map.removeLayer(layers[key]); else layers[key].addTo(map);
  });
  legend.appendChild(chip);
}
</script>
"""

html = TPL.replace("__KANTO__", kanto).replace("__KU__", ku).replace("__OTHERS__", others)
out = os.path.join(os.path.dirname(BASE), "tokyo-bousai-map.html")   # 寫到上一層專案夾 tokyo-bousai-map/
open(out, "w", encoding="utf-8").write(html)
print("wrote", out, "KB:", round(len(html.encode())/1024, 1))
