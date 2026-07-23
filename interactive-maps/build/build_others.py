#!/usr/bin/env python3
"""抓埼玉/千葉/神奈川/茨城市町村界，裁切視野+簡化，只留界線，存 compact geojson + 算圖核對。"""
import json, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw

B = r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad"
PREFS = ["08", "11", "12", "14"]   # 茨城 埼玉 千葉 神奈川
# 視野裁切框（比實際視野大一點，邊緣才完整）
VW = (139.34, 140.06, 35.40, 36.16)   # lngmin,lngmax,latmin,latmax

def fetch(pp):
    u = f"https://raw.githubusercontent.com/smartnews-smri/japan-topography/main/data/municipality/geojson/s0010/N03-21_{pp}_210101.json"
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"x"}), timeout=60).read())

def ring_bbox(ring):
    xs=[p[0] for p in ring]; ys=[p[1] for p in ring]
    return min(xs),max(xs),min(ys),max(ys)

def overlaps(bb):
    return not (bb[1]<VW[0] or bb[0]>VW[1] or bb[3]<VW[2] or bb[2]>VW[3])

def simplify(ring, tol=0.0016):
    out=[ring[0]]
    for pt in ring[1:]:
        lx,ly=out[-1]
        if abs(pt[0]-lx)+abs(pt[1]-ly)>=tol:
            out.append([round(pt[0],4),round(pt[1],4)])
    if out[-1]!=out[0]: out.append(out[0])
    return out if len(out)>=4 else None

feats=[]
for pp in PREFS:
    g=fetch(pp); kept=0
    for f in g["features"]:
        geom=f["geometry"]
        if geom is None: continue
        polys = geom["coordinates"] if geom["type"]=="MultiPolygon" else [geom["coordinates"]]
        newpolys=[]
        for poly in polys:
            outer=poly[0]
            if not overlaps(ring_bbox(outer)): continue     # 不在視野內的市町村整個丟掉
            rings=[]
            for r in poly:
                s=simplify(r)
                if s: rings.append(s)
            if rings: newpolys.append(rings)
        if newpolys:
            feats.append({"type":"Feature","properties":{"pref":pp},
                          "geometry":{"type":"MultiPolygon","coordinates":newpolys}})
            kept+=1
    print(f"pref {pp}: kept {kept}")

out={"type":"FeatureCollection","features":feats}
s=json.dumps(out,ensure_ascii=False,separators=(",",":"))
outp=B+r"\others_muni.geojson"; open(outp,"w",encoding="utf-8").write(s)
print("saved",outp,"KB:",round(len(s.encode())/1024,1),
      "feats:",len(feats),"pts:",sum(len(r) for f in feats for poly in f["geometry"]["coordinates"] for r in poly))

# 核對圖
kanto=json.load(open(B+r"\kanto.geojson",encoding="utf-8"))
ku=json.load(open(B+r"\tokyo_ku.geojson",encoding="utf-8"))
spots=[(1,35.997475,139.8114455),(2,36.0113203,139.5091906),(3,35.7280647,139.7070079),
       (4,35.6349494,139.7958032),(5,35.5838724,139.7603075),(6,35.7113,139.8678)]
W,H=1120,1000; LNG0,LNG1,LAT0,LAT1=139.42,139.98,35.48,36.06
def px(lng,lat): return ((lng-LNG0)/(LNG1-LNG0)*W,(1-(lat-LAT0)/(LAT1-LAT0))*H)
img=Image.new("RGB",(W,H),(182,211,223)); d=ImageDraw.Draw(img)
for f in kanto["features"]:
    for poly in f["geometry"]["coordinates"]:
        for ri,ring in enumerate(poly):
            d.polygon([px(x,y) for x,y in ring], fill=(244,238,224) if ri==0 else (182,211,223), outline=(200,169,143))
for f in feats:   # 其他縣市町村界
    for poly in f["geometry"]["coordinates"]:
        for ring in poly: d.line([px(x,y) for x,y in ring], fill=(176,162,176), width=1)
for f in ku["features"]:   # 東京23區界
    for poly in f["geometry"]["coordinates"]:
        for ring in poly: d.line([px(x,y) for x,y in ring], fill=(176,162,176), width=1)
for n,lat,lng in spots:
    x,y=px(lng,lat); r=11
    d.ellipse([x-r,y-r,x+r,y+r],fill=(220,30,60),outline="white",width=3); d.text((x-3,y-6),str(n),fill="white")
pngp=B+r"\others_check.png"; img.save(pngp); print("png",pngp)
