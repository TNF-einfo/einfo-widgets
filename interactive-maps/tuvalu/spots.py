# -*- coding: utf-8 -*-
"""吐瓦魯・富納富提 地圖的資料（地點＋敘述）。改這裡就好，再跑 python template/gen_map.py tuvalu。
   底圖是環礁的島嶼＋礁盤（build_land.py 產生），不用行政界：富納富提的行政區把整個潟湖包進去。"""

TITLE = "吐瓦魯・富納富提"
MARK = "環境資訊中心"
MAP_FILE = "tuvalu-map.html"
HEIGHT = 1080                             # 長型：固定 1080 高、寬度跟文章欄寬走；手機上比螢幕高，往下捲著看
POPUP_SIDE = "left"                       # 說明卡一開始放左側（潟湖那片空白），不去擠南端那一群點
POPUP_FLOAT = True                        # 說明卡可按住拖曳；往下捲時說明卡、標題框、圖例跟著停在看得到的那一段（owner 09-29）

BOUNDARIES = ["land.geojson"]             # 設了就不自動抓行政界
UNDERLAY = ["reef.geojson"]               # 礁盤，畫在陸地下面，環礁的形狀靠它看出來
# 衛星影像底圖：Sentinel-2 2026-01-05 單景（S2B_MSIL2A_20260105T222759_R072_T60LYR），10 公尺、放大兩倍並銳化，
# Web Mercator 靜態圖一張（WebP 280 KB），看得到 TCAP 新生地；授權可散布，要標 Copernicus 出處（見 README）。
# 經過：Esri 最新版有灰帶與暗塊拼接 → Sentinel-2 2024 無雲鑲嵌（owner 嫌「太模糊」）→ Esri Wayback 2022-06（看不到新生地）→
# Esri Wayback 2024-11（有雲、有拼接色塊，直接串 Esri 圖磚用在新聞網站的授權要問 Esri）→ owner 看了比較圖說「換銳化的看看」，
# 試過後定案（09-29：「現在的底圖可以」）。
# 設了 IMAGE 就不用下面的 TILES；拿掉 IMAGE 回到 Esri 2024-11，兩個都拿掉回到插畫風。
IMAGE = {"url": "basemap/s2_20260105_2x.webp", "bounds": [[-8.575, 179.14], [-8.415, 179.24]],
         "attribution": "Contains modified Copernicus Sentinel data 2026"}
# Esri 歷史影像庫（Wayback）2024-11-18 版（#49849）。抓哪一級圖磚由 gen_map 依畫面縮放與螢幕密度自動決定。
TILES = {"url": "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/49849/{z}/{y}/{x}",
         "attribution": "Imagery © Esri, Vantor, Earthstar Geographics, and the GIS User Community (Wayback 2024-11-18)",
         "maxNativeZoom": 18}
# 小地圖（右下角）：整個環礁，框出主圖範圍；offmap 的點畫在這裡。layers＝{geojson: 填色}，依序疊畫
INSET = {"title": "富納富提環礁", "layers": {"reef.geojson": "#4f8f88", "land.geojson": "#e9e3cc"}}
ATTRIB = 'inset © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'   # 小地圖的礁盤與島嶼取自 OSM（ODbL）
PLACES = [
    {"t": "太平洋", "lat": -8.49, "lng": 179.205, "big": 1, "sea": 1},      # 貼近主島，手機檔才不會落到框外被略過
    {"t": "富納富提潟湖", "lat": -8.455, "lng": 179.165, "big": 1, "sea": 1},   # 放高一點，避開說明卡預設停的潟湖中段
]

CAT = {   # 分類是暫定的，等 owner 確認。顏色挑在衛星影像（藍海、青綠潟湖、綠植被）上跳得出來的，
          # 數字一律深綠字（對比都在 6:1 以上）；原本的藍、綠會跟海和植被融在一起
    "adapt": {"name": "氣候調適", "color": "#f0b429", "emo": "🌊"},
    "site":  {"name": "環境現場", "color": "#ff7b5c", "emo": "📍"},
    "life":  {"name": "島上生活", "color": "#f6f3e7", "emo": "🏝"},
    "tw":    {"name": "台灣援助", "color": "#8fd0ff", "emo": "🤝"},
}

# 座標：owner 的 Google 文件表格（2026-09-29 匯出）裡的 Google Map 連結，取地點本身的 !3d/!4d，不取畫面中心 @。
# 照片：同一張表的雲端硬碟原檔，縮成 800px 寬放在 photos/（09-29 owner 要先看成果，已隨地圖推上公開 repo；託管方式未定）。
# 敘述：只寫〈吐瓦魯：海浪帶不走的家〉專題（e-info.org.tw/feature/36）六篇報導寫過的事，行尾註解是出處的 node 編號；
#       主島 Fongafale 照報導譯作「豐阿法萊」。
# offmap：離主島太遠、框進來會把主島縮到擠成一團的點，不畫在主圖，畫在右下角的小地圖（INSET）上，點了照樣開說明卡。
SPOTS = [
    {"n": 1, "cat": "life", "lat": -8.5238844, "lng": 179.1969495, "area": "豐阿法萊島", "short": "國際機場",  # 243891
     "zh": "富納富提國際機場", "ja": "Funafuti International Airport", "img": "photos/DSC03594.jpg",
     "desc": "機場很小、跑道很短，卻是島上少數平坦的道路。航班少，居民平常就在跑道上通行、運動、休閒，"
             "只有飛機起降時才退到兩旁等待，像一座飛機版的平交道。"},
    {"n": 2, "cat": "tw", "lat": -8.5278107, "lng": 179.1940009, "area": "豐阿法萊島", "label": "left",  # 243893；名字放右邊會被擋（owner 09-29）
     "zh": "友誼農場", "ja": "Happy Friendship Garden", "img": "photos/DSC03660.jpg",
     "desc": "台灣技術團在機場旁經營的農場，每週兩天清晨開市，居民排隊採買蔬菜。珊瑚礁土壤缺乏養分，"
             "技術團用進口河沙混有機肥自己做土，作物墊高40至50公分，避開漲潮時從地面冒出的海水。"},
    {"n": 3, "cat": "life", "lat": -8.5243806, "lng": 179.194428, "area": "豐阿法萊島", "short": "政府大樓",  # 243896、243893
     "zh": "吐瓦魯政府大樓", "ja": "The Parliament of Tuvalu", "img": "photos/IMG_8620.jpg",
     "desc": "台灣自2010年起推動「潔淨能源計畫」，富納富提的政府建築屋頂也鋪了來自台灣的光電板。"
             "台灣未來還將協助興建新的國會大樓。"},
    {"n": 4, "cat": "adapt", "lat": -8.5208195, "lng": 179.1947881, "area": "瓦伊阿庫村西側",  # 243890
     "zh": "TCap 1", "ja": "吐瓦魯海岸調適計畫（TCAP）第一階段", "img": "photos/DJI_0264.MP4_000337051.jpg",
     "desc": "吐瓦魯政府2017年展開的大型調適工程。第一階段在人口最密集的瓦伊阿庫村西側，2023年底完工，"
             "用潟湖砂土填出約7.3公頃新土地，依聯合國開發計劃署的設計標準，可抵禦2100年以前的海平面上升。"},
    {"n": 5, "cat": "adapt", "lat": -8.5294437, "lng": 179.1903839, "area": "南側潟湖",  # 243890、243894
     "zh": "TCap 2", "ja": "吐瓦魯海岸調適計畫（TCAP）第二階段", "img": "photos/DSC04644.jpg",
     "desc": "第二階段選在南側潟湖，用高強度沙袋堆成防波堤，再以潟湖砂土填出長約800公尺、約8公頃的新生地，"
             "2025年10月由聯合國開發計劃署正式移交。"},
    {"n": 6, "cat": "tw", "lat": -8.5147958, "lng": 179.2006125, "area": "豐阿法萊島", "short": "大使館",  # 243891、243893、243896
     "zh": "中華民國駐吐瓦魯大使館", "ja": "Embassy of the Republic of China (Taiwan)", "img": "photos/IMG_6593.jpg",
     "desc": "台吐建交已40餘年，大使為林東亨。兩國2025年底簽署《台吐團結共榮條約》，"
             "條約名稱的「Kaitasi」在吐瓦魯語是「至親家人」。"},
    {"n": 7, "cat": "adapt", "lat": -8.502527, "lng": 179.195511, "area": "豐阿法萊島",  # 243890、243893
     "zh": "TTCAP", "ja": "台吐海岸調適計畫", "img": "photos/DJI_0255.MP4_000013219.jpg",
     "desc": "台灣協助的海岸調適計畫，在富納富提更北端修築、加高防波堤，保護容易受浪潮衝擊的聚落。"
             "2026年完工，同年3月外交部長林佳龍以總統特使身分出席啟用典禮。"},
    {"n": 8, "cat": "life", "lat": -8.516483, "lng": 179.198980, "area": "豐阿法萊島",  # 243894
     "zh": "集會所", "ja": "Maneapa", "img": "photos/DSC03746.jpg",
     "desc": "吐瓦魯社群聚會、議事的地方。富納富提社群副首領提凱圖說，填海造陸、再把低窪土地墊高的"
             "氣候調適方案，長老們都在集會所討論過。"},
    {"n": 9, "cat": "site", "lat": -8.457374, "lng": 179.183098, "area": "豐阿法萊島北端",  # 243896
     "zh": "垃圾場", "ja": "", "img": "photos/DJI_0262.MP4_000208749.jpg",
     "desc": "全島的垃圾都集中在北端這座垃圾山，從汽機車殘骸到日常用品都有。當地沒有大型焚化爐，只能露天焚燒；"
             "台灣從2008年起協助推動環境教育，從垃圾分類、資源回收做起。"},
    {"n": 10, "cat": "site", "lat": -8.4717966, "lng": 179.1894988, "area": "豐阿法萊島北段", "short": "最窄點",  # 243891
     "zh": "吐瓦魯最窄點", "ja": "The narrowest point on Fongafale Island", "img": "photos/DJI_0264.jpg",
     "desc": "道路兩旁就是海水，浪花一波波拍打路基。在這裡遇到的青年基洛托努說，以前這裡有一片土地、"
             "還有椰子樹，現在全消失了，海岸線逼近了至少20公尺。"},
    {"n": 11, "cat": "site", "lat": -8.4482937, "lng": 179.1779476, "area": "豐阿法萊島最北端",  # 243890
     "zh": "柯飛演講點", "ja": "", "img": "photos/DSC06616.jpg",
     "desc": "2021年聯合國氣候大會（COP26）期間，時任外交部長柯飛穿西裝站在海水中演講的地方。"
             "他身後的水泥設施是二戰時美軍的大型防空砲基座，漲潮時會泡在海水裡。"},
    {"n": 12, "cat": "life", "lat": -8.629211, "lng": 179.101125, "area": "富納富提環礁的離島", "offmap": 1,  # 243891、243896
     "zh": "富納法拉", "ja": "Funafala",
     "img": "photos/DJI_0258.MP4_000113911.jpg",
     "desc": "只有寥寥幾戶人家的離島。每逢大潮，海水會直接淹上陸地，房屋和器具都泡在水裡；"
             "隨丈夫移居這裡的斐濟籍婦女瓦萊布魯說，當地人總是說「沒事啦，很正常」。"},
]
