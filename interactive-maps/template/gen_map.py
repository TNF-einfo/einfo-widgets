#!/usr/bin/env python3
"""地圖產生器（template）。用法: python template/gen_map.py [instance]（預設 tokyo）。
   讀 {instance}/spots.py（地點＋敘述）＋ {instance}/boundaries/*.geojson → 產 {instance}/<MAP_FILE>。
   無圖磚（無道路），只留行政界線＋水域；瓦紙固定配色。座標/文案/照片/地名全在 {instance}/spots.py。"""
import os, sys, json, math, base64, importlib.util, urllib.parse
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

# 2) 界線＋地名：cfg.TILES（圖磚底圖，例如衛星影像）設了就不畫向量陸地、也不抓界線；
#    否則 cfg.BOUNDARIES 有就用（如東京手調三層＋手列 PLACES），再否則自動抓
image = getattr(cfg, "IMAGE", None)   # 一張地理對齊的影像當底圖（Web Mercator 靜態圖）；有它就不用 TILES
tiles = None if image else getattr(cfg, "TILES", None)
if tiles or image:
    boundary_files, places = [], getattr(cfg, "PLACES", [])
elif getattr(cfg, "BOUNDARIES", None):
    boundary_files, places = cfg.BOUNDARIES, cfg.PLACES
else:
    boundary_files, places = fb.ensure_boundaries(IDIR, cfg.SPOTS)
boundaries = [open(os.path.join(_bd, f), encoding="utf-8").read() for f in boundary_files]
# 選用：UNDERLAY＝壓在陸地下面的填色層（例：環礁的礁盤）；有影像底圖就用不到
underlay = [] if tiles or image else [open(os.path.join(_bd, f), encoding="utf-8").read() for f in getattr(cfg, "UNDERLAY", [])]

def inset_data(conf, width=136):
    """小地圖：把 conf["layers"]（{geojson: 填色}）用跟主圖一樣的 Web Mercator 投影成寬 width 像素的 SVG，
       連同頁面換算座標要用的參數（主圖範圍框、offmap 的點由頁面自己算位置）一起回傳。"""
    merc = lambda lat: math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))
    feats = {f: json.load(open(os.path.join(_bd, f), encoding="utf-8"))["features"] for f in conf["layers"]}
    rings = lambda g: [r for poly in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]) for r in poly]
    pts = [p for fs in feats.values() for ft in fs for r in rings(ft["geometry"]) for p in r]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    m0, m1 = max(merc(p[1]) for p in pts), min(merc(p[1]) for p in pts)
    pad = (x1 - x0) * 0.08                       # 四邊留白
    x0, m0 = x0 - pad, m0 + pad
    s = width / (x1 - x0 + pad)                  # 每度幾像素
    xy = lambda lng, lat: (round((lng - x0) * s, 1), round((m0 - merc(lat)) * s, 1))
    svg = ""
    for f, fill in conf["layers"].items():
        for ft in feats[f]:                      # 一個地物一條 path，evenodd 才挖得出礁盤中間的洞
            d = ""
            for r in rings(ft["geometry"]):
                kept = [xy(*r[0])]
                for p in r[1:]:
                    q = xy(*p)
                    if abs(q[0] - kept[-1][0]) + abs(q[1] - kept[-1][1]) >= 0.8: kept.append(q)   # 不到一個像素的點省掉
                if len(kept) >= 3: d += "M" + "L".join(f"{x:g},{y:g}" for x, y in kept) + "Z"
            if d: svg += f'<path fill="{fill}" fill-rule="evenodd" d="{d}"/>'
    return {"svg": svg, "w": width, "h": round((m0 - m1 + pad) * s, 1), "lng0": x0, "m0": m0, "s": s, "title": conf.get("title", "")}
inset = inset_data(cfg.INSET) if getattr(cfg, "INSET", None) else None
if any(s.get("offmap") for s in cfg.SPOTS) and not inset:
    raise SystemExit("offmap 的點畫在小地圖上，spots.py 要設 INSET")
# 畫框尺寸：預設固定比例（東京 720/476，三檔寬度等比縮）；設 HEIGHT＝固定高度、寬度跟文章欄寬走
# （長型地圖用：手機上照樣這麼高，讀者往下捲著看，不會整張縮小）。嵌入碼的外框要跟著用同一條。
frame_size = f"height:{cfg.HEIGHT}px" if getattr(cfg, "HEIGHT", None) else "aspect-ratio:" + getattr(cfg, "ASPECT", "720/476")
attrib = getattr(cfg, "ATTRIB", 'boundaries © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')
# 衛星主題的標題與說明卡標題用思源宋體：Google Fonts 的 text= 只下載用得到的字（標題＋各地點名），幾 KB；載不到就退回系統宋體
font_link = ""
if tiles or image:
    glyphs = "".join(sorted(set(cfg.TITLE + "".join(s["zh"] for s in cfg.SPOTS))))
    font_link = (('\n<link rel="preconnect" href="https://' + urllib.parse.urlsplit(tiles["url"]).netloc + '">' if tiles else '')   # 圖磚主機趁 Leaflet 還在下載時先連線
                 + '\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                 '\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@700&display=swap&text='
                 + urllib.parse.quote(glyphs) + '">')

TPL = r"""<!-- 東京・防災・生態 另類旅遊地圖 — 環境資訊中心
     Leaflet + 內嵌行政區 GeoJSON（都縣界＋東京23區界＋鄰縣市町村界；無圖磚＝無道路，只留行政交界＋水域）。
     繁中地名（自動位移避讓、移太多才刪）、圖釘旁名稱、瓦紙固定配色、鎖死靜態、可 <iframe> 內嵌。
     界線/pin/地名皆以 Python 算圖核對。座標/文案/照片在 spots、地名在 places。 -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__｜__MARK__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">__FONT_LINK__
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
    display:flex; min-height:100vh; padding:0;
  }
  .frame{
    /* margin:auto 置中：畫面比地圖矮時（直接開網址看長型地圖）會貼齊頂端、往下捲；
       用 align-items:center 的話，這頁沒有 doctype（quirks mode），上緣會被切掉、捲不回去 */
    margin:auto; position:relative; width:720px; max-width:100%; __FRAME_SIZE__;
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
  .corner{ display:contents }   /* 標題框＋圖例的容器；預設不影響版面（插畫風各自定位），衛星主題才疊在右上 */
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
  /* 圖磚（衛星影像）底圖：拿掉紙紋；地名改白字深陰影，壓在深色影像上才讀得到 */
  .frame.tiles .paper-wash{ display:none }
  /* 圖磚多畫 1px 疊住鄰居（見下方 _initTile）；Leaflet 1.9 預設的 plus-lighter 會把疊住的那條加亮成白線，改回一般混色 */
  .frame.tiles .leaflet-container img.leaflet-tile{ mix-blend-mode:normal }
  .frame.tiles .rlabel{ color:#fff; text-shadow:0 1px 3px rgba(0,0,0,.75), 0 0 8px rgba(0,0,0,.45) }
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

  /* ── 衛星主題（有 TILES 時 .frame 加 .tiles；插畫風地圖不受影響）──
     配色取自環資颱風短影音（深綠＋黃）。原則是能拿掉的框線都拿掉（owner 09-29：圖示包太多框線）：
     圖釘只剩實心圓點＋一層淡陰影；地名白字深色描邊、不用底；卡片與標題框只靠陰影分邊。 */
  .frame.tiles{ --glass:rgba(16,42,31,.84); --cream:#f6f3e7; --mute:#aebfb5; --gold:#f0b429; --deep:#10231b;
    --serif:"Noto Serif TC","Source Han Serif TC","Songti TC","PMingLiU",serif; background:#0f2a22 }
  .frame.tiles #map, .frame.tiles .leaflet-container{ background:#0f2a22 }
  .frame.tiles .titlebar, .frame.tiles .legend, .frame.tiles .info{
    background:var(--glass); border:0; box-shadow:0 8px 24px rgba(0,0,0,.4); color:var(--cream);
    -webkit-backdrop-filter:blur(8px); backdrop-filter:blur(8px) }
  .frame.tiles .corner{ display:flex; flex-direction:column; align-items:flex-end; gap:8px; position:absolute; right:12px; top:12px; z-index:6;
    transition:top .3s ease-out }   /* POPUP_FLOAT 時跟著捲動（不能拖） */
  .frame.tiles .corner > .titlebar, .frame.tiles .corner > .legend{ position:static }   /* 標題疊在圖例上面、都靠右（owner 09-29） */
  .frame.tiles .titlebar{ padding:10px 14px 11px; border-radius:12px; text-align:right }
  .frame.tiles .info.float{ transition:top .3s ease-out; touch-action:none; cursor:grab; -webkit-user-select:none; user-select:none }   /* 浮動卡片：可拖曳、跟著捲動 */
  .frame.tiles .info.float img{ -webkit-touch-callout:none }   /* iOS 長按照片不跳「儲存圖片」選單，按住照片也能拖 */
  .frame.tiles .info.float.dragging{ transition:none; cursor:grabbing; box-shadow:0 14px 34px rgba(0,0,0,.5) }
  /* 小地圖（INSET）：Leaflet 右下角、自動疊在出處上面；框＝主圖範圍，點＝離主圖太遠的地點 */
  .frame.tiles .inset{ position:relative; width:136px; border-radius:12px; background:var(--glass); box-shadow:0 8px 24px rgba(0,0,0,.4);
    -webkit-backdrop-filter:blur(8px); backdrop-filter:blur(8px) }
  .frame.tiles .inset svg{ display:block; width:100%; height:auto }
  .frame.tiles .inset{ transition:opacity .2s }
  .frame.tiles.zoomed .inset{ opacity:0; pointer-events:none }   /* 放大中淡出：不擋地名、也不擋拖曳，彈回後再出現 */
  .frame.tiles .inset .view{ fill:rgba(255,255,255,.12); stroke:#fff; stroke-width:1.2; vector-effect:non-scaling-stroke }
  .frame.tiles .inset .cap{ position:absolute; left:9px; top:7px; color:var(--mute); font-size:10px; letter-spacing:.12em }
  .frame.tiles .ipin{ position:absolute; display:flex; align-items:center; gap:4px; transform:translate(-8px,-50%); cursor:pointer }
  .frame.tiles .ipin .pin{ width:16px; height:16px; flex:none }
  .frame.tiles .ipin .pin b{ font-size:9.5px }
  .frame.tiles .ipin span{ color:#fff; font-size:11.5px; font-weight:600; white-space:nowrap; transition:color .2s;
    text-shadow:0 0 2px rgba(0,0,0,.95), 0 1px 3px rgba(0,0,0,.85) }
  .frame.tiles .ipin.hi .pin{ transform:scale(1.35) }
  .frame.tiles .ipin.hi span{ color:var(--gold) }
  .vstrip{ position:absolute; left:0; width:1px; opacity:0; pointer-events:none }
  .frame.tiles .titlebar .mark{ color:var(--gold); font-size:10.5px; letter-spacing:.22em }
  .frame.tiles .titlebar h1{ font-family:var(--serif); font-size:22px; letter-spacing:.08em; margin-top:3px }
  .frame.tiles .legend{ border-radius:12px; gap:7px }
  .frame.tiles .chip{ color:var(--cream); font-weight:500; font-size:12px; letter-spacing:.04em }
  .frame.tiles .chip .dot{ width:10px; height:10px; font-size:0 }
  .frame.tiles .pin{ width:20px; height:20px; border-radius:50%; transform:none; border:0; box-shadow:0 1px 4px rgba(0,0,0,.55);
    transition:transform .2s ease-out }
  .frame.tiles .pin b{ transform:none; color:var(--deep); font-size:11px }
  .frame.tiles .pin-anchor{ width:20px; height:20px; transform-origin:50% 50% }
  .frame.tiles .pin-anchor.hi .pin{ transform:scale(1.35); animation:none }   /* 正在介紹的點：放大＋地名變黃，不加框 */
  .frame.tiles .toplabel{ background:none; border:0; box-shadow:none; padding:0 2px; color:#fff; font-weight:600; letter-spacing:.02em;
    text-shadow:0 0 2px rgba(0,0,0,.95), 0 1px 3px rgba(0,0,0,.85), 0 0 10px rgba(0,0,0,.6); transition:color .2s }
  .frame.tiles .toplabel.hi{ color:var(--gold) }
  .frame.tiles .rlabel.sea{ color:rgba(228,244,244,.9); font-weight:500; letter-spacing:.5em }
  .frame.tiles .info{ padding:0; border-radius:14px }
  .frame.tiles .card{ display:flex; flex-direction:column; padding:10px 13px 13px }
  .frame.tiles .card img.photo{ order:-1; width:calc(100% + 26px); margin:-10px -13px 10px; border-radius:14px 14px 0 0; background:#1d3a30;
    height:auto; aspect-ratio:3/2; object-fit:cover }   /* 3:2＝相機原圖比例（owner：固定高度裁得太扁） */
  .frame.tiles .card .meta{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap }
  .frame.tiles .card .tag{ background:transparent!important; padding:0; border-radius:0; color:var(--cream);
    font-size:10.5px; font-weight:600; letter-spacing:.14em; display:inline-flex; align-items:center; gap:6px }
  .frame.tiles .card .tag::before{ content:""; width:8px; height:8px; border-radius:50%; background:var(--tag) }
  .frame.tiles .card .emo{ display:none }
  .frame.tiles .card .area{ margin:0; color:var(--mute) }
  .frame.tiles .card h3{ font-family:var(--serif); font-size:18px; letter-spacing:.04em; color:#fff; margin:6px 0 0 }
  .frame.tiles .card .ja{ color:var(--mute); margin:2px 0 8px }
  .frame.tiles .card p.desc{ color:#e3ebe6 }
  .frame.tiles .info .x{ top:7px; right:7px; width:24px; height:24px; padding:0; border-radius:50%; background:rgba(8,20,16,.55);
    color:#fff; font-size:16px; line-height:24px; text-align:center; z-index:2 }
  .frame.tiles .info .x:focus-visible{ outline:2px solid var(--gold); outline-offset:2px }
  .frame.tiles .leaflet-control-attribution{ background:rgba(8,20,16,.55)!important; color:#c9d6cf }
  .frame.tiles .leaflet-control-attribution a{ color:#fff }
  /* 放大（雙指）：只有底圖（圖磚、影像）用 CSS scale 放大，畫面座標＝平移 (--ztx,--zty)＋倍率 --zs × 原座標（原點在畫框左上）；
     圖釘、地名不放大、只照放大後的位置移動（各自的錨點 --px/--py），字才不會糊（owner 09-29：放大時地名糊掉）。
     變數註冊成可過渡，彈回時底圖與圖釘同步；手指移動中（.zooming）不過渡才跟得上 */
  @property --zs { syntax:'<number>'; inherits:true; initial-value:1 }
  @property --ztx { syntax:'<length>'; inherits:true; initial-value:0px }
  @property --zty { syntax:'<length>'; inherits:true; initial-value:0px }
  .frame.tiles{ transition:--zs .3s ease-out, --ztx .3s ease-out, --zty .3s ease-out }
  .frame.tiles.zooming{ transition:none }
  .frame.tiles .leaflet-tile-pane, .frame.tiles .leaflet-overlay-pane{ transform-origin:0 0; scale:var(--zs); translate:var(--ztx) var(--zty) }
  .frame.tiles .leaflet-marker-icon, .frame.tiles .toplabel{
    translate:calc((var(--zs) - 1) * var(--px, 0px) + var(--ztx)) calc((var(--zs) - 1) * var(--py, 0px) + var(--zty)) }
  .frame.tiles #map{ touch-action:pan-x pan-y }   /* 單指照樣捲文章，雙指捏開交給頁面自己放大 */
  .frame.tiles #map, .frame.tiles #toplabels{ -webkit-user-select:none; user-select:none }   /* 按住拖著看時不要反白地名 */
  @media (prefers-reduced-motion:reduce){ .frame.tiles, .frame.tiles .pin, .frame.tiles .toplabel, .frame.tiles .corner, .frame.tiles .info.float{ transition:none } }
  @media (max-width:719.98px){
    .frame.tiles .titlebar{ display:block; padding:8px 12px 9px }   /* 手機、平板也放標題（owner 09-29），比桌機小一點；圖例照樣藏 */
    .frame.tiles .titlebar .mark{ font-size:10px; letter-spacing:.2em }
    .frame.tiles .titlebar h1{ font-size:19px; margin-top:2px }   /* 16px 太小（owner：「手機版標題大點」） */
    .frame.tiles .inset{ width:100px } .frame.tiles .inset .cap{ left:7px; top:5px; font-size:9px; letter-spacing:0 }
    .frame.tiles .ipin span{ font-size:10.5px }
    .frame.tiles .card{ padding:8px 9px 9px }
    .frame.tiles .card img.photo{ width:calc(100% + 18px); margin:-8px -9px 8px }
    .frame.tiles .card h3{ font-size:14px; margin-top:4px }
    .frame.tiles .card .ja{ margin-bottom:5px }
  }
  @media (max-width:527.98px){   /* 手機說明卡放大一點（owner 09-29）：寬 40% → 50%，名稱加大 */
    .frame.tiles .info{ width:50%; max-width:none }
    .frame.tiles .card h3{ font-size:15px }
  }
</style>

<div class="frame">
  <div id="map"></div>
  <div class="paper-wash"></div>
  <div class="corner">
    <div class="titlebar">
      <div class="mark">__MARK__</div>
      <h1>__TITLE__</h1>
    </div>
    <div class="legend" id="legend"></div>
  </div>
  <div class="info" id="info"></div>
</div>

<script>
const BOUNDARIES = __BOUNDARIES__;   // [0]=陸地(填色+粗界)，其餘=細界線
const UNDERLAY = __UNDERLAY__;       // 陸地下面的淺色填色層（礁盤等），可為空
const TILES = __TILES__;             // null＝無圖磚；{url, attribution, maxNativeZoom}＝圖磚底圖
const IMAGE = __IMAGE__;             // null＝無；{url, bounds, attribution}＝一張地理對齊的影像當底圖（有它就不用 TILES）
const SAT = !!(TILES || IMAGE);      // 衛星主題（圖釘、署名、放大都看這個，不要只看 TILES）
const ATTRIB = __ATTRIB__;

const CAT = __CAT__;
const spots = __SPOTS__;
const places = __PLACES__;
const POPUP_SIDE = __POPUP_SIDE__;   // null＝自動挑圖釘最少的角落；'left'／'right'＝固定在該側中段
const POPUP_FLOAT = __POPUP_FLOAT__; // true＝說明卡可按住拖曳；文章往下捲時說明卡、標題框＋圖例跟著停在看得到的那一段（長型地圖用）
const INSET = __INSET__;             // null＝沒有小地圖；有的話 offmap 的點畫在它上面

const map = L.map('map', {
  zoomControl:false, attributionControl:true, zoomSnap:0,   // 允許小數縮放→填滿畫面（免整數化掉一級變太小）
  dragging:false, scrollWheelZoom:false, doubleClickZoom:false,
  touchZoom:false, boxZoom:false, keyboard:false, tap:false,
});
// 圖層：有 TILES 就只鋪圖磚（衛星影像等），拿掉紙紋；否則 BOUNDARIES[0]＝陸地填色＋粗界（無圖磚＝無道路，只留行政界＋水域），其餘＝細界線
let tileLayer = null;
if (IMAGE){   // 一張 Web Mercator 靜態圖照四角拉伸就對得上，一個請求載完；衛星主題照用
  L.imageOverlay(IMAGE.url, IMAGE.bounds, { attribution:IMAGE.attribution }).addTo(map);
  document.querySelector('.frame').classList.add('tiles');
} else if (TILES){
  // 小數縮放時圖磚之間會露出細縫：每張圖磚多畫 1px 疊住鄰居（Leaflet #3575 的通用解），配上面 CSS 的 mix-blend-mode:normal
  const initTile = L.GridLayer.prototype._initTile;
  L.GridLayer.include({ _initTile(tile){ initTile.call(this, tile); const s = this.getTileSize();
    tile.style.width = (s.x + 1) + 'px'; tile.style.height = (s.y + 1) + 'px'; } });
  tileLayer = L.tileLayer(TILES.url, { attribution:TILES.attribution, maxZoom:22 }).addTo(map);   // 抓哪一級由 refit() 決定
  if (TILES.filter) map.getPane('tilePane').style.filter = TILES.filter;   // 影像調色（例如海太暗時提亮），CSS filter 字串
  document.querySelector('.frame').classList.add('tiles');
} else {
  UNDERLAY.forEach(g => L.geoJSON(g, { style:{ stroke:false, fillColor:'#d3e6ea', fillOpacity:1 }, interactive:false }).addTo(map));
  L.geoJSON(BOUNDARIES[0], {
    style:{ fillColor:'#f4eee0', fillOpacity:1, color:'#c8a98f', weight:1.3, opacity:.9 },
    attribution: ATTRIB
  }).addTo(map);
  BOUNDARIES.slice(1).forEach(g => L.geoJSON(g, { style:{ fill:false, color:'#c3b39a', weight:0.6, opacity:.72 } }).addTo(map));
}

const info = document.getElementById('info');

// 圖釘
const layers = {}; Object.keys(CAT).forEach(k => layers[k] = L.layerGroup());
const bounds = [];
const cardHtml = {};   // 景點編號 → 資訊卡 HTML（給地名點擊委派用）
for (const s of spots){
  const c = CAT[s.cat];
  const icon = L.divIcon({   // 衛星主題的圖釘是 20px 圓點，中心對準座標；插畫風是 23px 水滴針，尖端對準
    className:'', iconSize: SAT ? [20,20] : [23,23], iconAnchor: SAT ? [10,10] : [11,23],
    html:`<div class="pin-anchor" data-spot="${s.n}">
            <div class="pin" style="background:${c.color}"><b>${s.n}</b></div>
            <span class="pin-name" data-spot="${s.n}">${s.short||s.zh}</span>
          </div>`
  });
  const photo = s.img;
  // 這張圖刻意「不要」loading="lazy"（2026-08-25 修）：彈出視窗是 Leaflet 動態插進 DOM 的，
  // 惰性載入的 intersection observer 判不出它可見 → 照片永遠停在灰框、naturalWidth 0。
  // 而且 lazy 本來就沒必要——彈出視窗本身就是延遲機制，圖只有在使用者點開時才存在。
  const html =
    `<div class="card" data-spot="${s.n}">
       <div class="meta"><span class="tag" style="--tag:${c.color};background:${c.color}"><span class="emo">${c.emo}</span> ${c.name}</span> <span class="area">${s.area}</span></div>
       <img class="photo" src="${photo}" alt="${s.zh}" draggable="false">
       <h3>${s.zh}</h3><p class="ja">${s.ja}</p>
       <p class="desc">${s.desc}</p>
     </div>`;
  cardHtml[s.n] = html;
  if (s.offmap) continue;   // 太遠的點不進主圖（框進來會把其他點縮成一團），畫在小地圖上
  L.marker([s.lat, s.lng], { icon, keyboard:false, zIndexOffset:1000 })
    .on('click', () => jump(s.n))
    .addTo(layers[s.cat]);
  bounds.push([s.lat, s.lng]);
}
Object.values(layers).forEach(l => l.addTo(map));
// 小地圖（INSET）：整個環礁＋主圖範圍框（refit 時畫）＋offmap 的點，點了照樣開說明卡。投影跟主圖一樣（Web Mercator）
const insetXY = (lat, lng) => [(lng - INSET.lng0) * INSET.s, (INSET.m0 - Math.log(Math.tan(Math.PI/4 + lat*Math.PI/360)) * 180/Math.PI) * INSET.s];
if (INSET){
  const ctl = L.control({ position:'bottomright' });
  ctl.onAdd = () => {
    const d = L.DomUtil.create('div', 'inset');
    d.innerHTML = `<svg viewBox="0 0 ${INSET.w} ${INSET.h}">${INSET.svg}<rect class="view"/></svg><span class="cap">${INSET.title}</span>`
      + spots.filter(s => s.offmap).map(s => `<div class="ipin" data-spot="${s.n}" data-cat="${s.cat}">`   // 位置在 refit 算
          + `<div class="pin" style="background:${CAT[s.cat].color}"><b>${s.n}</b></div><span>${s.zh}</span></div>`).join('');
    L.DomEvent.disableClickPropagation(d);
    d.addEventListener('click', e => { const p = e.target.closest('.ipin'); if (p) jump(+p.dataset.spot); });
    return d;
  };
  ctl.addTo(map);
  if (SAT) map.attributionControl.addAttribution(ATTRIB);   // 小地圖的輪廓（例如 OSM）也要署名；插畫風主圖本來就掛著
}
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
  // 圖磚只抓剛好夠清楚的那一級：一個圖磚像素對到 1～2 個螢幕實體像素（視網膜算到 2 倍為止）。
  // 之前固定多抓一兩級，視網膜螢幕一次要載近 500 張；Leaflet 預設把縮放級四捨五入、最多放大 1.4 倍會糊，所以自己算
  if (tileLayer){
    const z = map.getBoundsZoom(L.latLngBounds(bounds), false, L.point(P.tl).add(P.br));
    tileLayer.options.minNativeZoom = tileLayer.options.maxNativeZoom =
      Math.min(TILES.maxNativeZoom || 18, Math.ceil(z + Math.log2(Math.min(window.devicePixelRatio || 1, 2)) - 0.1));
  }
  map.fitBounds(bounds, { paddingTopLeft:P.tl, paddingBottomRight:P.br, animate:false });
  if (INSET){   // 小地圖框出主圖現在的範圍；主圖比環礁寬（桌機）就把小地圖的視窗放大，框才不會被切掉
    const b = map.getBounds(), [x1, y1] = insetXY(b.getNorth(), b.getWest()), [x2, y2] = insetXY(b.getSouth(), b.getEast());
    const vx = Math.min(0, x1 - 3), vy = Math.min(0, y1 - 3), vw = Math.max(INSET.w, x2 + 3) - vx, vh = Math.max(INSET.h, y2 + 3) - vy;
    const svg = document.querySelector('.inset svg'), r = svg.querySelector('.view');
    svg.setAttribute('viewBox', `${vx} ${vy} ${vw} ${vh}`);
    r.setAttribute('x', x1); r.setAttribute('y', y1); r.setAttribute('width', x2 - x1); r.setAttribute('height', y2 - y1);
    document.querySelectorAll('.ipin').forEach(p => { const s = spots.find(s => s.n === +p.dataset.spot), [x, y] = insetXY(s.lat, s.lng);
      p.style.left = (x - vx) / vw * 100 + '%'; p.style.top = (y - vy) / vh * 100 + '%'; });
  }
}

// ── Auto Layout（量測法）：pin名/地名 自動避開 pin圖示＋popup＋彼此；碰撞優先上下移、換邊最後。
//    全用螢幕座標 getBoundingClientRect（旋轉/縮放/字級都量到實際值），不再手動移標籤。
const overlap = (a,b) => a.x1<b.x2 && a.x2>b.x1 && a.y1<b.y2 && a.y2>b.y1;
const overlapArea = (a,b) => Math.max(0, Math.min(a.x2,b.x2)-Math.max(a.x1,b.x1)) * Math.max(0, Math.min(a.y2,b.y2)-Math.max(a.y1,b.y1));
const asBox = r => ({ x1:r.left, y1:r.top, x2:r.right, y2:r.bottom });
let labelMarkers = [];
// 標題框、圖例、小地圖的框（地名要避開），各向外擴 pad。浮動的標題框＋圖例量它回到頂端（top 12px）時的位置，
// 捲到一半重排（篩選分類、轉向）才不會避錯地方
function fixedRects(pad){
  const fr = document.querySelector('.frame').getBoundingClientRect(), cr = document.querySelector('.corner').getBoundingClientRect();
  const dy = POPUP_FLOAT ? cr.top - fr.top - 12 : 0;
  return [...document.querySelectorAll('.titlebar, .legend, .inset')].map(el => ({ r:el.getBoundingClientRect(), d:el.closest('.corner') ? dy : 0 }))
    .filter(o => o.r.width > 1).map(({ r, d }) => ({ x1:r.left-pad, y1:r.top-d-pad, x2:r.right+pad, y2:r.bottom-d+pad }));
}

// 障礙基底（非 pin）：popup（先秀 spot1＝敘述最長那張、量其框）＋標題框。pin 由 layoutPinNames 自算，不在此重複放。
function baseObstacles(){
  const occ = [];
  try { stopCar(); } catch(e){}
  showSpot(1);
  const ir = document.getElementById('info').getBoundingClientRect();   // 浮動卡片會被拖走、跟著捲動，不當障礙
  if (ir.width > 1 && !POPUP_FLOAT) occ.push({ x1:ir.left-4, y1:ir.top-4, x2:ir.right+4, y2:ir.bottom+4 });
  // 標題框、圖例（＋小地圖）也當障礙（影片版定案；owner：北本被標題壓）——手機隱藏時 width≈0 自動略過
  occ.push(...fixedRects(6));
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
    let cands = [[G+lw,0],[0,-(V+lh)],[-(G+lw),0],[0,V+lh],[G+lw,-(V+lh)],[-(G+lw),-(V+lh)]];  // 右→上→左→下→右上→左上
    const sp = spots.find(s => s.n === spot) || {}, side = sp.label;   // spots.py 指定 "label": right／up／left／down 就只放那邊（owner 點名的）
    if (side){ const [ox, oy] = cands[['right', 'up', 'left', 'down'].indexOf(side)]; cands = [[ox, oy + (sp.label_dy || 0)]]; }   // label_dy：再上下微調幾 px，負＝往上
    let best = cands[0], bestPen = Infinity, bestOv = 0;
    for (const [ox,oy] of cands){
      const bx = { x1:P.cx+ox-lw, y1:P.cy+oy-lh, x2:P.cx+ox+lw, y2:P.cy+oy+lh };
      let pen = 0, ov = 0, a;
      for (const q of pins) if (q.spot !== spot){ a = overlapArea(bx, { x1:q.cx-q.hw-4, y1:q.cy-q.hh-4, x2:q.cx+q.hw+4, y2:q.cy+q.hh+4 }); pen += a * 8; ov += a; }  // 壓別 pin＝重罰
      // 名字離別的圖釘比離自己的近＝讀者會看錯是誰的名字（09-29：「TCap 2」排到 5 號正上方、貼著 2 號）→ 重罰但不禁止
      const dist = q => Math.hypot(Math.max(bx.x1 - q.cx, 0, q.cx - bx.x2), Math.max(bx.y1 - q.cy, 0, q.cy - bx.y2));
      for (const q of pins) if (q.spot !== spot && dist(q) < dist(P)) pen += 400;
      for (const o of occ){ a = overlapArea(bx, o); pen += a * 8; ov += a; }   // 壓標題框／popup（occ 內障礙）＝重罰
      for (const b of placed){ a = overlapArea(bx, b); pen += a; ov += a; }    // 壓別名字＝輕罰
      pen += (Math.max(0,fr.left-bx.x1)+Math.max(0,bx.x2-fr.right)+Math.max(0,fr.top-bx.y1)+Math.max(0,bx.y2-fr.bottom)) * 1000;  // 出框＝字被切掉，比壓到別人更糟
      if (pen === 0){ best = [ox,oy]; bestOv = 0; break; }
      if (pen < bestPen){ bestPen = pen; best = [ox,oy]; bestOv = ov; }
    }
    // 六個位置都會壓到別人超過一成（手機檔的密集區）→ 名字先藏，只留編號；點圖釘照樣開說明卡。指定邊的名字一律照放
    if (!side && bestOv > 0.1 * (4 * lw * lh)){ lab.style.display = 'none'; return; }
    const [ox,oy] = best;
    placed.push({ x1:P.cx+ox-lw, y1:P.cy+oy-lh, x2:P.cx+ox+lw, y2:P.cy+oy+lh });
    // 錨點放在圖釘中心、偏移寫進 transform：放大時（衛星主題的按住／雙指）名字照錨點 --px/--py 跟著圖釘移動，偏移不會被放大
    lab.style.left = (P.cx - fr.left) + 'px'; lab.style.top = (P.cy - fr.top) + 'px';
    lab.style.setProperty('--px', lab.style.left); lab.style.setProperty('--py', lab.style.top);
    lab.style.transform = `translate(${ox}px,${oy}px) translate(-50%,-50%)`;
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
  const avoid = fixedRects(6);   // 只避標題框、圖例、小地圖＋popup（地名可被 pin／pin 名蓋）；浮動卡片會移動，不避
  const ir = document.getElementById('info').getBoundingClientRect();
  if (ir.width > 1 && !POPUP_FLOAT) avoid.push({ x1:ir.left-4, y1:ir.top-4, x2:ir.right+4, y2:ir.bottom+4 });
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
  if (POPUP_FLOAT){ placeFloat(); return; }
  if (POPUP_SIDE){   // 長型地圖：卡片放左／右側中段（潟湖、外海那片空白），不去擠南北兩端的點
    const off = (window.matchMedia('(max-width:719.98px)').matches ? 8 : 12) + 'px';
    info.style.left = POPUP_SIDE === 'left' ? off : 'auto'; info.style.right = POPUP_SIDE === 'right' ? off : 'auto';
    info.style.top = '50%'; info.style.bottom = 'auto'; info.style.transform = 'translateY(-50%)';
    return;
  }
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
  highlight(curSpot);              // 浮層是重建的，把「正在介紹」的標記補回去
  placeDistricts(frame);           // 行政區 cap-10 + farthest-spread（可被 pin/名蓋）
  // 衛星主題放大時，圖釘與海面地名只照放大後的位置移動：每個 marker 記下自己在畫框裡的座標（CSS 的 --px/--py）
  map.eachLayer(l => { if (l._icon && l.getLatLng){ const p = map.latLngToContainerPoint(l.getLatLng());
    l._icon.style.setProperty('--px', p.x + 'px'); l._icon.style.setProperty('--py', p.y + 'px'); } });
}

// 說明輪播：桌機自動輪播 6 景點說明、對應圖釘加脈動高亮；手機不輪播並收起說明
function isSmall(){ return window.matchMedia('(max-width:719.98px)').matches; }
let carTimer = null, curSpot = 0;
function highlight(n){   // 圖釘、浮層地名、小地圖上的點一起標 .hi（衛星主題靠地名變色表示正在介紹哪一點）
  document.querySelectorAll('.pin-anchor.hi, .toplabel.hi, .ipin.hi').forEach(el => el.classList.remove('hi'));
  document.querySelectorAll('[data-spot="' + n + '"]').forEach(el => {
    if (el.matches('.pin-anchor, .toplabel, .ipin')) el.classList.add('hi'); });
}
function showSpot(n){
  curSpot = n;
  info.innerHTML = '<button class="x" aria-label="關閉">×</button>' + cardHtml[n];
  info.classList.add('show'); highlight(n);
  info.querySelector('.x').onclick = () => { stopCar(); info.classList.remove('show'); highlight(0); };
  if (POPUP_FLOAT){ placeFloat(); const im = info.querySelector('img.photo'); if (im && !im.complete) im.onload = placeFloat; }
}
// 浮動說明卡：讀者按住可拖到任何位置；文章往下捲時，卡片跟著停在地圖「看得到的那一段」的正中間（拖過就保留那個偏移）。
// 看得到哪一段：沿地圖高度鋪 108 條看不見的細條、用 IntersectionObserver 看哪幾條在畫面裡。
// 只觀察整張地圖不行：地圖比螢幕高時，捲到中段可見比例不變、不會通知。這招在跨網域 iframe 裡也拿得到，不必外頁配合。
const flt = { x:null, dy:0, visTop:0, visBot:null, dragged:false };
function floatBase(){   // 卡片置中於可見段落（可見段落比卡片矮時對齊上緣）；手機檔貼可見段落的下緣（owner 09-29：手機預設出現在左下角）
  const H = document.querySelector('.frame').clientHeight, bot = flt.visBot === null ? H : flt.visBot;
  if (!window.matchMedia('(max-width:527.98px)').matches) return flt.visTop + Math.max(0, (bot - flt.visTop - info.offsetHeight) / 2);
  const h = info.offsetHeight, w = info.offsetWidth, x = flt.x === null ? 8 : flt.x, top = flt.visTop + 8;
  const yMax = Math.max(top, bot - h - 22);   // 可見下緣會多算一條細條（10px），實際離底約 12px
  if (flt.dragged) return yMax;               // 讀者拖過就照他放的位置（下緣＋拖的偏移）
  // 會蓋到圖釘或名稱就每次往上 20px 找不蓋的地方，找不到取蓋最少的；正在介紹的點重罰、幾乎不會被蓋（owner 09-29：要記得不要被遮到）
  const fr = document.querySelector('.frame').getBoundingClientRect();
  const obs = [...document.querySelectorAll('.pin-anchor .pin, .toplabel')].filter(e => e.getClientRects().length).map(e => {
    const r = e.getBoundingClientRect(); return { x1:r.left - fr.left, y1:r.top - fr.top, x2:r.right - fr.left, y2:r.bottom - fr.top, w:e.closest('.hi') ? 100 : 1 }; });
  let best = yMax, bestPen = Infinity;
  for (let y = yMax; y >= top; y -= 20){
    const pen = obs.reduce((p, o) => p + o.w * Math.max(0, Math.min(x + w, o.x2) - Math.max(x, o.x1)) * Math.max(0, Math.min(y + h, o.y2) - Math.max(y, o.y1)), 0);
    if (pen === 0) return y;
    if (pen < bestPen){ bestPen = pen; best = y; }
  }
  return best;
}
function placeFloat(){
  const fr = document.querySelector('.frame'), W = fr.clientWidth, H = fr.clientHeight;
  const m = window.matchMedia('(max-width:719.98px)').matches ? 8 : 12;
  const ab = (document.querySelector('.leaflet-control-attribution') || {}).offsetHeight || 0;   // 捲到底時停在出處上面、不蓋住它
  if (flt.x === null) flt.x = POPUP_SIDE === 'right' ? W - info.offsetWidth - m : m;
  info.style.left = Math.min(Math.max(flt.x, m), W - info.offsetWidth - m) + 'px';
  info.style.top = Math.min(Math.max(floatBase() + flt.dy, m), Math.max(m, H - info.offsetHeight - m - ab)) + 'px';
  info.style.right = info.style.bottom = 'auto'; info.style.transform = 'none';
}
const corner = document.querySelector('.corner');
function placeCorner(){   // 標題框＋圖例：停在看得到那一段的上緣，跟著捲動但不能拖（owner 09-29）；手機檔本來就藏起來
  const H = document.querySelector('.frame').clientHeight;
  corner.style.top = Math.max(12, Math.min(flt.visTop + 12, H - corner.offsetHeight - 12)) + 'px';
}
function initFloat(){
  const fr = document.querySelector('.frame'), N = 108, vis = new Set();
  info.classList.add('float');
  const io = new IntersectionObserver(es => {
    for (const e of es) e.isIntersecting ? vis.add(+e.target.dataset.i) : vis.delete(+e.target.dataset.i);
    flt.visTop = vis.size ? Math.min(...vis) * fr.clientHeight / N : 0;
    flt.visBot = vis.size ? (Math.max(...vis) + 1) * fr.clientHeight / N : null;
    if (!info.classList.contains('dragging')) placeFloat();
    placeCorner();
  });
  for (let i = 0; i < N; i++){
    const s = document.createElement('div'); s.className = 'vstrip'; s.dataset.i = i;
    s.style.top = (i * 100 / N) + '%'; s.style.height = (100 / N) + '%'; fr.appendChild(s); io.observe(s);
  }
  let start = null;   // 拖曳：按住卡片（關閉鈕除外）移動；拖曳中暫停輪播，放開後繼續
  info.addEventListener('pointerdown', e => {
    if (e.target.closest('.x, a')) return;
    start = { px:e.clientX, py:e.clientY, x:info.offsetLeft, y:info.offsetTop };
    info.setPointerCapture(e.pointerId); info.classList.add('dragging'); stopCar();
  });
  info.addEventListener('pointermove', e => { if (!start) return;
    flt.dragged = true;   // 拖過就不再自動避開圖釘，照讀者放的位置
    flt.x = start.x + e.clientX - start.px; flt.dy = start.y + e.clientY - start.py - floatBase(); placeFloat(); });
  const end = () => { if (!start) return; start = null; info.classList.remove('dragging');
    stopCar(); carTimer = setInterval(carTick, carMs()); };
  info.addEventListener('pointerup', end); info.addEventListener('pointercancel', end);
}
if (POPUP_FLOAT) initFloat();
// 輪播時頁面跟著捲到正在介紹的點：owner 09-30 說不需要了，拿掉；做法留在 git 歷史 7c17240 的 followSpot。
// 把地圖裡高度 y（畫框座標）的地方平滑捲到畫面中間（放大彈回時用）。探針一定要放在 body 底下：放在 overflow:hidden 的地圖裡，
// scrollIntoView 會連地圖容器本身一起捲，整張圖內部被捲走。嵌在文章的 iframe 裡也捲得動外頁
const probe = document.createElement('div');
probe.style.cssText = 'position:absolute;left:0;width:1px;height:1px;visibility:hidden;pointer-events:none';
document.body.appendChild(probe);
function scrollFrameY(y){
  probe.style.top = (document.querySelector('.frame').getBoundingClientRect().top + scrollY + y) + 'px';
  probe.scrollIntoView({ block:'center', behavior:'smooth' });
}
function carMs(){ return window.matchMedia('(max-width:527.98px)').matches ? 2750 : 4200; }   // 手機檔 2.75s、其餘 4.2s
function carTick(){ showSpot(curSpot % spots.length + 1); }
function startCar(){ if (carTimer) return; carTick(); carTimer = setInterval(carTick, carMs()); }   // 桌機/手機都輪播
function stopCar(){ if (carTimer){ clearInterval(carTimer); carTimer = null; } }
function jump(n){ showSpot(n); stopCar(); carTimer = setInterval(carTick, carMs()); }   // 點某點：跳到它並重置輪播
function syncCar(){ startCar(); }

// 圖例 + 篩選（先建好再排標籤：圖例也是地名要避開的障礙）
const legend = document.getElementById('legend');
for (const [key,c] of Object.entries(CAT)){
  const chip = document.createElement('div');
  chip.className = 'chip'; chip.dataset.cat = key; chip.dataset.on = '1';
  chip.innerHTML = `<span class="dot" style="background:${c.color}">${c.emo}</span>${c.name}`;
  chip.addEventListener('click', () => {
    const on = chip.dataset.on === '1'; chip.dataset.on = on ? '0' : '1';
    if (on) map.removeLayer(layers[key]); else layers[key].addTo(map);
    document.querySelectorAll('.ipin[data-cat="' + key + '"]').forEach(p => p.style.display = on ? 'none' : '');   // 小地圖上的點一起藏
    relayout();   // 篩選後重排標籤
  });
  legend.appendChild(chip);
}

// 放大（衛星主題、觸控）：雙指捏開就放大、原地縮放；放手後停 0.5 秒再彈回原尺寸（owner 09-29：1.5 秒改 0.5 秒）。
// 只放大底圖（CSS 變數見 .frame.tiles），圖釘與地名只跟著移位置、字不糊；不動 Leaflet 的縮放級，彈回後不必重排。說明卡、標題、小地圖不動。
// 只做觸控（owner 09-29 晚：桌機不要放大；桌機按住放大的版本在 git 歷史 8ebbddb）。
if (SAT){
  const fr = document.querySelector('.frame'), mapEl = map.getContainer(), cur = { s:1, t:[0, 0] };
  let backT = null, drag = null, pinch = null;   // drag＝放大後單指拖 { p:起點, t:當時的平移 }；pinch＝雙指捏 { d:兩指距離, m:中點, s, t }
  const setZoom = (s, t = [0, 0], live = false) => {   // 畫面座標＝t＋s×原座標
    const W = fr.clientWidth, H = fr.clientHeight;   // 夾住平移：放大後的底圖一直蓋滿畫框，拖不出地圖邊界
    t = [Math.min(0, Math.max(W * (1 - s), t[0])), Math.min(0, Math.max(H * (1 - s), t[1]))];
    Object.assign(cur, { s, t });
    fr.classList.toggle('zooming', live);   // 拖曳、捏的當下不過渡；彈回照 CSS 過渡
    fr.classList.toggle('zoomed', s > 1);   // 放大中小地圖先淡出（owner 09-29：地名會跑到小地圖上、在上面也拖不動）
    [['--zs', s], ['--ztx', t[0] + 'px'], ['--zty', t[1] + 'px']].forEach(([k, v]) => fr.style.setProperty(k, v));
  };
  // 彈回時頁面跟著捲：看得到那一段正中間現在顯示的那塊地圖，彈回後捲到畫面中間，停在移動後的地方
  // （owner 09-29：放大移動後會彈回最初放大的地方）
  const springBack = () => { clearTimeout(backT); backT = setTimeout(() => {
    const H = fr.clientHeight, c = POPUP_FLOAT && flt.visBot !== null ? (flt.visTop + flt.visBot) / 2 : H / 2, qy = (c - cur.t[1]) / cur.s;
    if (Math.abs(qy - c) > 20) scrollFrameY(qy);
    setZoom(1);
  }, 500); };
  const frameXY = (x, y) => { const r = fr.getBoundingClientRect(); return [x - r.left, y - r.top]; };
  const mid = ts => frameXY((ts[0].clientX + ts[1].clientX) / 2, (ts[0].clientY + ts[1].clientY) / 2);
  const gap = ts => Math.hypot(ts[0].clientX - ts[1].clientX, ts[0].clientY - ts[1].clientY);
  const grab = t => ({ p:[t.clientX, t.clientY], t:cur.t });
  // 雙指捏開放大（最多 4 倍）、兩指一起移動可平移；放大中單指拖就移動畫面，彈回前再捏或拖都接著目前的狀態。
  // 沒放大時單指照樣捲文章，只有捏、或放大中的拖才擋瀏覽器預設
  mapEl.addEventListener('touchstart', e => {
    clearTimeout(backT);
    if (e.touches.length === 2){ drag = null; pinch = { d:gap(e.touches), m:mid(e.touches), s:cur.s, t:cur.t }; }
    else if (e.touches.length === 1 && cur.s > 1) drag = grab(e.touches[0]);
  }, { passive:true });
  mapEl.addEventListener('touchmove', e => {
    if (pinch && e.touches.length === 2){
      e.preventDefault();
      // 原地縮放：一開始捏的那一點底下的地圖，一直留在兩指中間（owner 09-29：縮小時不要跑回原本放大的地方）
      const s = Math.min(4, Math.max(1, pinch.s * gap(e.touches) / pinch.d)), m = mid(e.touches), k = s / pinch.s;
      setZoom(s, [m[0] - (pinch.m[0] - pinch.t[0]) * k, m[1] - (pinch.m[1] - pinch.t[1]) * k], true);
    } else if (drag && e.touches.length === 1){
      e.preventDefault();
      setZoom(cur.s, [drag.t[0] + e.touches[0].clientX - drag.p[0], drag.t[1] + e.touches[0].clientY - drag.p[1]], true);
    }
  }, { passive:false });
  const untouch = e => {
    if (pinch && e.touches.length < 2){   // 放開一指就接著用剩下那指拖
      pinch = null;
      if (e.touches.length === 1 && cur.s > 1) drag = grab(e.touches[0]); else springBack();
    } else if (drag && !e.touches.length){ drag = null; springBack(); }
  };
  mapEl.addEventListener('touchend', untouch); mapEl.addEventListener('touchcancel', untouch);
}

refit(); relayout(); syncCar();   // 初次：fit → 自動排標籤（此時 showSpot 已定義）→ 開輪播
// 直接開網址（不是嵌在文章裡）：一載入就定在第一個點，不要先停在北端、過半秒再滑下去（owner 09-29）。
// 嵌在文章裡不這樣做：外頁的捲動是讀者在控制，載入時硬跳會把人拉走
if (POPUP_FLOAT && window.self === window.top){
  const el = document.querySelector('.pin-anchor[data-spot="' + curSpot + '"]');
  if (el){ const r = el.getBoundingClientRect(); window.scrollTo({ top:r.top + scrollY - innerHeight / 2, behavior:'instant' }); }
}

map.on('resize', () => { refit(); relayout(); syncCar(); });   // 縮放/轉向後重 fit＋重算避讓＋輪播開關
</script>
"""

html = (TPL
        .replace("__BOUNDARIES__", "[" + ",".join(boundaries) + "]")
        .replace("__UNDERLAY__", "[" + ",".join(underlay) + "]")
        .replace("__TILES__", json.dumps(tiles, ensure_ascii=False))
        .replace("__IMAGE__", json.dumps(image, ensure_ascii=False))
        .replace("__FONT_LINK__", font_link)
        .replace("__FRAME_SIZE__", frame_size)
        .replace("__POPUP_SIDE__", json.dumps(getattr(cfg, "POPUP_SIDE", None)))
        .replace("__POPUP_FLOAT__", json.dumps(bool(getattr(cfg, "POPUP_FLOAT", False))))
        .replace("__INSET__", json.dumps(inset, ensure_ascii=False))
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
      .replace("__FRAME_SIZE__", frame_size)
      .replace("@@MAP_B64@@", b64))
ap_out = os.path.join(IDIR, "article-preview.html")
open(ap_out, "w", encoding="utf-8").write(ap)
print("wrote", ap_out, "KB:", round(len(ap.encode())/1024, 1))

# 純地圖外包一層 iframe（隔離＋自足）：整張地圖轉義塞進 <iframe srcdoc>，此檔可直接開預覽，
# 或複製 <div> 區塊貼進文章（等同 article-preview 的「複製完整嵌入碼」，但免開頁點鈕）。
esc = html.replace("&", "&amp;").replace('"', "&quot;")  # srcdoc 屬性用雙引號，需轉 & 與 "
embed = ('<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
         '<title>' + cfg.TITLE + '｜iframe 嵌入</title>\n'
         '<div style="position:relative;max-width:720px;margin:auto;' + frame_size + '">\n'
         '  <iframe loading="lazy" allowfullscreen srcdoc="' + esc + '"\n'
         '          style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px"></iframe>\n'
         '</div>\n</html>\n')
embed_out = os.path.join(IDIR, cfg.MAP_FILE.replace(".html", ".embed.html"))
open(embed_out, "w", encoding="utf-8").write(embed)
print("wrote", embed_out, "KB:", round(len(embed.encode())/1024, 1))
