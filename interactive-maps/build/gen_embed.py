#!/usr/bin/env python3
"""把整張地圖用 srcdoc 包進 iframe，打包成單一自足檔（上傳一支就能用、樣式隔離）。"""
import os
_D = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(_D, "..", "tokyo-bousai-map.html")
mp = open(src, encoding="utf-8").read()
esc = mp.replace("&", "&amp;").replace('"', "&quot;")   # 供 srcdoc 雙引號屬性用

out = ('<!doctype html>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<title>東京・私房防災旅遊地圖｜環境資訊中心</title>\n'
       '<style>html,body{margin:0}\n'
       '.tokyo-map-embed{position:relative;width:100%;max-width:720px;margin:auto;aspect-ratio:720/476}\n'
       '.tokyo-map-embed iframe{position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px}</style>\n'
       '<div class="tokyo-map-embed">\n'
       f'  <iframe title="東京・私房防災旅遊地圖｜環境資訊中心" loading="lazy" allowfullscreen srcdoc="{esc}"></iframe>\n'
       '</div>\n')

dst = os.path.join(_D, "..", "tokyo-map-embedded.html")
open(dst, "w", encoding="utf-8").write(out)
print("wrote", dst, "KB:", round(len(out.encode())/1024, 1))
