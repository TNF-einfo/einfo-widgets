#!/usr/bin/env python3
"""下載日本都道府縣 GeoJSON、取關東、簡化、存 compact geojson，並算圖核對。"""
import json, urllib.request, math, io
from PIL import Image, ImageDraw

URL = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"
# 要的都道府縣（關東，涵蓋我們的視野）：茨城8 栃木9 群馬10 埼玉11 千葉12 東京13 神奈川14
WANT = {8, 9, 10, 11, 12, 13, 14}

req = urllib.request.Request(URL, headers={"User-Agent": "boundary-build/1.0"})
data = json.loads(urllib.request.urlopen(req, timeout=30).read())
print("total features:", len(data["features"]))
print("sample props:", data["features"][0]["properties"])

def pid(f):
    p = f["properties"]
    for k in ("id", "ID", "pref", "code"):
        if k in p:
            try: return int(p[k])
            except: pass
    return None

def simplify_ring(ring, tol=0.0025):
    out = [ring[0]]
    for pt in ring[1:]:
        lx, ly = out[-1]
        if abs(pt[0]-lx) + abs(pt[1]-ly) >= tol:
            out.append([round(pt[0], 4), round(pt[1], 4)])
    if out[-1] != out[0]:
        out.append(out[0])
    return out if len(out) >= 4 else ring

feats = []
for f in data["features"]:
    i = pid(f)
    if i not in WANT:
        continue
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    newpolys = []
    for poly in polys:
        newrings = [simplify_ring(r) for r in poly]
        # 丟掉太小的碎島（點數少且面積小）
        newpolys.append(newrings)
    feats.append({"type": "Feature",
                  "properties": {"id": i, "name": f["properties"].get("nam_ja", "")},
                  "geometry": {"type": "MultiPolygon", "coordinates": newpolys}})

out_geo = {"type": "FeatureCollection", "features": feats}
outp = r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad\kanto.geojson"
s = json.dumps(out_geo, ensure_ascii=False, separators=(",", ":"))
open(outp, "w", encoding="utf-8").write(s)
print("saved geojson:", outp, "size KB:", round(len(s.encode())/1024, 1),
      "features:", len(feats),
      "total pts:", sum(len(r) for f in feats for poly in f["geometry"]["coordinates"] for r in poly))

# ---- 核對圖：視野 = 景點範圍 + margin ----
spots = [(1,35.997475,139.8114455),(2,36.0113203,139.5091906),(3,35.7280647,139.7070079),
         (4,35.6349494,139.7958032),(5,35.5838724,139.7603075),(6,35.7113,139.8678)]
W, H = 1000, 900
LNG0, LNG1 = 139.42, 139.98
LAT0, LAT1 = 35.48, 36.06
def px(lng, lat):
    x = (lng-LNG0)/(LNG1-LNG0)*W
    y = (1-(lat-LAT0)/(LAT1-LAT0))*H
    return x, y

img = Image.new("RGB", (W, H), (175, 205, 218))  # 海
d = ImageDraw.Draw(img)
for f in feats:
    for poly in f["geometry"]["coordinates"]:
        for ri, ring in enumerate(poly):
            pts = [px(x, y) for x, y in ring]
            if ri == 0:
                d.polygon(pts, fill=(244, 238, 224), outline=(190, 150, 110))
            else:
                d.polygon(pts, fill=(175, 205, 218))  # 洞
# 界線再描一次（清楚點）
for f in feats:
    for poly in f["geometry"]["coordinates"]:
        for ring in poly:
            pts = [px(x, y) for x, y in ring]
            d.line(pts, fill=(190, 150, 110), width=2)
for n, lat, lng in spots:
    x, y = px(lng, lat); r = 11
    d.ellipse([x-r, y-r, x+r, y+r], fill=(220, 30, 60), outline="white", width=3)
    d.text((x-3, y-6), str(n), fill="white")

pngp = r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad\boundary_check.png"
img.save(pngp)
print("saved png:", pngp)
