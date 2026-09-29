# -*- coding: utf-8 -*-
"""吐瓦魯・富納富提 地圖的資料（地點＋敘述）。改這裡就好，再跑 python template/gen_map.py tuvalu。
   底圖是環礁的島嶼＋礁盤（build_land.py 產生），不用行政界：富納富提的行政區把整個潟湖包進去。"""

TITLE = "吐瓦魯・富納富提"
MARK = "環境資訊中心"
MAP_FILE = "tuvalu-map.html"
HEIGHT = 1080                             # 長型：固定 1080 高、寬度跟文章欄寬走；手機上比螢幕高，往下捲著看
POPUP_SIDE = "left"                       # 說明卡固定在左側中段（潟湖那片空白），不去擠南端那一群點

BOUNDARIES = ["land.geojson"]             # 設了就不自動抓行政界
UNDERLAY = ["reef.geojson"]               # 礁盤，畫在陸地下面，環礁的形狀靠它看出來
PLACES = [
    {"t": "太平洋", "lat": -8.49, "lng": 179.205, "big": 1, "sea": 1},      # 貼近主島，手機檔才不會落到框外被略過
    {"t": "富納富提潟湖", "lat": -8.47, "lng": 179.172, "big": 1, "sea": 1},
]

CAT = {   # 分類是暫定的，等 owner 確認
    "adapt": {"name": "氣候調適", "color": "#4a5ab0", "emo": "🌊"},
    "site":  {"name": "環境現場", "color": "#c9803a", "emo": "📍"},
    "life":  {"name": "島上生活", "color": "#5fae72", "emo": "🏝"},
    "tw":    {"name": "臺灣援助", "color": "#e07a9c", "emo": "🤝"},
}

# 座標：owner 的 Google 文件表格（2026-09-29 匯出）裡的 Google Map 連結，取地點本身的 !3d/!4d，不取畫面中心 @。
# 照片：同一張表的雲端硬碟原檔，縮成 800px 寬放在 photos/（放哪裡託管還沒定，先不進版控）。
# offmap：離主島太遠、框進來會把主島縮到擠成一團的點，畫在畫面邊緣、朝真實方位，說明卡照樣用真實位置。
SPOTS = [
    {"n": 1, "cat": "life", "lat": -8.5238844, "lng": 179.1969495, "area": "", "short": "國際機場",
     "zh": "富納富提國際機場", "ja": "Funafuti International Airport", "img": "photos/DSC03594.jpg", "desc": ""},
    {"n": 2, "cat": "tw", "lat": -8.5278107, "lng": 179.1940009, "area": "",
     "zh": "友誼農場", "ja": "Happy Friendship Garden", "img": "photos/DSC03660.jpg", "desc": ""},
    {"n": 3, "cat": "life", "lat": -8.5243806, "lng": 179.194428, "area": "", "short": "政府大樓",
     "zh": "吐瓦魯政府大樓", "ja": "The Parliament of Tuvalu", "img": "photos/IMG_8620.jpg", "desc": ""},
    {"n": 4, "cat": "adapt", "lat": -8.5208195, "lng": 179.1947881, "area": "",
     "zh": "TCap 1", "ja": "", "img": "photos/DJI_0264.MP4_000337051.jpg", "desc": ""},
    {"n": 5, "cat": "adapt", "lat": -8.5294437, "lng": 179.1903839, "area": "",
     "zh": "TCap 2", "ja": "TCAP II", "img": "photos/DSC04644.jpg", "desc": ""},
    {"n": 6, "cat": "tw", "lat": -8.5147958, "lng": 179.2006125, "area": "", "short": "大使館",
     "zh": "中華民國駐吐瓦魯大使館", "ja": "", "img": "photos/IMG_6593.jpg", "desc": ""},
    {"n": 7, "cat": "adapt", "lat": -8.502527, "lng": 179.195511, "area": "",
     "zh": "TTCAP", "ja": "", "img": "photos/DJI_0255.MP4_000013219.jpg", "desc": ""},
    {"n": 8, "cat": "life", "lat": -8.516483, "lng": 179.198980, "area": "",
     "zh": "集會所", "ja": "", "img": "photos/DSC03746.jpg", "desc": ""},
    {"n": 9, "cat": "site", "lat": -8.457374, "lng": 179.183098, "area": "",
     "zh": "垃圾場", "ja": "", "img": "photos/DJI_0262.MP4_000208749.jpg", "desc": ""},
    {"n": 10, "cat": "site", "lat": -8.4717966, "lng": 179.1894988, "area": "", "short": "最窄點",
     "zh": "吐瓦魯最窄點", "ja": "The narrowest point on Fongafale Island", "img": "photos/DJI_0264.jpg", "desc": ""},
    {"n": 11, "cat": "site", "lat": -8.4482937, "lng": 179.1779476, "area": "",
     "zh": "柯飛演講點", "ja": "", "img": "photos/DSC06616.jpg", "desc": ""},
    {"n": 12, "cat": "life", "lat": -8.629211, "lng": 179.101125, "area": "", "offmap": 1,
     "short": "↙ 富納法拉 16 公里", "zh": "富納法拉", "ja": "Funafala",
     "img": "photos/DJI_0258.MP4_000113911.jpg", "desc": ""},
]
