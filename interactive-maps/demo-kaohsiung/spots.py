# -*- coding: utf-8 -*-
"""任意城市模板示範（高雄）：只編這個檔（地點＋敘述），跑 `python template/gen_map.py demo-kaohsiung`。
   沒設 BOUNDARIES → gen_map 自動由 spots 座標範圍抓行政界線（Nominatim+Overpass，快取進 boundaries/）。
   spot 可只給名字（省略 lat/lng）→ 自動地理編碼；這裡多半給了座標以求示範穩定。"""

TITLE = "高雄・藝文與自然 另類旅遊地圖"
MARK = "地圖模板示範"
MAP_FILE = "kaohsiung-map.html"

CAT = {
    "art":      {"name": "藝文空間", "color": "#4a5ab0", "emo": "🎨"},
    "nature":   {"name": "自然水岸", "color": "#5fae72", "emo": "🌿"},
    "landmark": {"name": "城市地標", "color": "#e07a9c", "emo": "📍"},
}

SPOTS = [
    {"n": 1, "cat": "art", "lat": 22.6203, "lng": 120.2817, "area": "高雄・鹽埕",
     "zh": "駁二藝術特區", "ja": "Pier-2 Art Center",
     "desc": "由舊倉庫群改造的濱海藝文聚落，常設裝置藝術、市集與展演，是高雄港邊最具代表性的創意基地。"},
    {"n": 2, "cat": "nature", "lat": 22.6533, "lng": 120.3617, "area": "高雄・鳥松",
     "zh": "澄清湖", "ja": "Chengcing Lake",
     "desc": "高雄最大的湖泊風景區，環湖步道與九曲橋景致宜人，兼具水源保護與休憩功能。"},
    {"n": 3, "cat": "landmark", "lat": 22.6197, "lng": 120.3003, "area": "高雄・前鎮",
     "zh": "高雄流行音樂中心", "ja": "Kaohsiung Music Center",
     "desc": "臨愛河灣的地標建築群，以珊瑚礁與海浪為設計語彙，是南台灣最大的流行音樂展演場域。"},
    {"n": 4, "cat": "nature", "lat": 22.6100, "lng": 120.2680, "area": "高雄・旗津",
     "zh": "旗津海水浴場", "ja": "Cijin Beach",
     "desc": "搭渡輪即達的離島沙灘，海岸線綿長，夕陽與海產小吃是在地人的假日日常。"},
    {"n": 5, "cat": "art", "lat": 22.6255, "lng": 120.3340, "area": "高雄・鳳山",
     "zh": "衛武營國家藝術文化中心", "ja": "Weiwuying",
     "desc": "由軍營改建的世界級表演藝術中心，流線屋頂下設有歌劇院、音樂廳與戶外榕園。"},
]
