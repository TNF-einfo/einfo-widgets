#!/usr/bin/env python3
"""下載 Tokyo geojson、篩 23 特別區、簡化、存 compact geojson，並算圖核對（疊都縣界＋pin）。"""
import json, urllib.request, math, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw

URL = "https://raw.githubusercontent.com/dataofjapan/land/master/tokyo.geojson"
req = urllib.request.Request(URL, headers={"User-Agent": "ward-build/1.0"})
data = json.loads(urllib.request.urlopen(req, timeout=30).read())
print("total features:", len(data["features"]))
print("sample prop keys:", list(data["features"][0]["properties"].keys()))

def code(f):
    p = f["properties"]
    for k in ("code", "id", "N03_007", "CODE", "areaCode"):
        if k in p:
            try: return int(p[k])
            except: pass
    return None

def simplify_ring(ring, tol=0.0012):   # 區界較細，門檻小一點
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
    c = code(f)
    if c is None or not (13101 <= c // 10 <= 13123):   # 23 特別區（6 位含檢查碼）
        continue
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    newpolys = [[simplify_ring(r) for r in poly] for poly in polys]
    feats.append({"type": "Feature",
                  "properties": {"code": c, "name": f["properties"].get("ward_ja", "")},
                  "geometry": {"type": "MultiPolygon", "coordinates": newpolys}})

print("wards kept:", len(feats), [f["properties"]["name"] for f in feats][:5], "...")
out_geo = {"type": "FeatureCollection", "features": feats}
outp = r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad\tokyo_ku.geojson"
s = json.dumps(out_geo, ensure_ascii=False, separators=(",", ":"))
open(outp, "w", encoding="utf-8").write(s)
print("saved:", outp, "KB:", round(len(s.encode())/1024, 1),
      "pts:", sum(len(r) for f in feats for poly in f["geometry"]["coordinates"] for r in poly))

# 核對圖
kanto = json.load(open(r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad\kanto.geojson", encoding="utf-8"))
spots = [(1,35.997475,139.8114455),(2,36.0113203,139.5091906),(3,35.7280647,139.7070079),
         (4,35.6349494,139.7958032),(5,35.5838724,139.7603075),(6,35.7113,139.8678)]
W, H = 1000, 900
LNG0,LNG1,LAT0,LAT1 = 139.42,139.98,35.48,36.06
def px(lng,lat): return ((lng-LNG0)/(LNG1-LNG0)*W, (1-(lat-LAT0)/(LAT1-LAT0))*H)
img = Image.new("RGB",(W,H),(175,205,218)); d=ImageDraw.Draw(img)
for f in kanto["features"]:
    for poly in f["geometry"]["coordinates"]:
        for ri,ring in enumerate(poly):
            pts=[px(x,y) for x,y in ring]
            d.polygon(pts, fill=(244,238,224) if ri==0 else (175,205,218), outline=(190,150,110))
for f in feats:  # 區界（細藍灰）
    for poly in f["geometry"]["coordinates"]:
        for ring in poly:
            d.line([px(x,y) for x,y in ring], fill=(150,130,150), width=1)
for n,lat,lng in spots:
    x,y=px(lng,lat); r=11
    d.ellipse([x-r,y-r,x+r,y+r], fill=(220,30,60), outline="white", width=3); d.text((x-3,y-6),str(n),fill="white")
pngp = r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad\ward_check.png"
img.save(pngp); print("png:", pngp)
