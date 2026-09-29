# -*- coding: utf-8 -*-
"""富納富提環礁底圖：OSM 島嶼（place=island|islet）→ land.geojson，礁盤（natural=reef）→ reef.geojson。
   環礁不能用 fetch_boundaries 的行政界（Funafuti 的行政區多邊形把整個潟湖都包進去，會畫成一整塊陸地），
   所以這個實例自己抓海岸輪廓，spots.py 再用 BOUNDARIES／UNDERLAY 指過來。
用法：python interactive-maps/tuvalu/build_land.py [--force]（輸出已存在就跳過；需連網）"""
import os, sys, json, urllib.request, urllib.parse
import osm2geojson
from shapely.geometry import shape, mapping, Polygon

BBOX = (-8.72, 178.98, -8.40, 179.26)          # s,w,n,e：整個環礁
UA = {"User-Agent": "research-lab-map-template/0.1"}  # 匿名：不放個人聯絡資訊（owner 2026-09-09）
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boundaries")
SIMPLIFY = 0.00003                              # 約 3 公尺；嵌入檔要小，這個比例尺看不出差別

def overpass():
    s, w, n, e = BBOX
    q = (f'[out:json][timeout:90];(nwr["place"~"^(island|islet)$"]({s},{w},{n},{e});'
         f'nwr["natural"="reef"]({s},{w},{n},{e}););out geom;')
    req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                 data=urllib.parse.urlencode({"data": q}).encode(), headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=120).read())

def as_polygon(f):
    """osm2geojson 只把它認得的面狀 tag 轉成面；place=islet 的封閉 way 會變成線，這裡補成面。"""
    g = f["geometry"]
    if g["type"] in ("Polygon", "MultiPolygon"):
        return shape(g)
    if g["type"] == "LineString" and len(g["coordinates"]) >= 4 and g["coordinates"][0] == g["coordinates"][-1]:
        return Polygon(g["coordinates"])
    return None

def feature(geom, **props):
    geom = geom.buffer(0).simplify(SIMPLIFY, preserve_topology=True)
    js = json.loads(json.dumps(mapping(geom)), parse_float=lambda x: round(float(x), 5))
    return {"type": "Feature", "properties": props, "geometry": js}

def main():
    land_p, reef_p = os.path.join(OUT, "land.geojson"), os.path.join(OUT, "reef.geojson")
    if os.path.isfile(land_p) and os.path.isfile(reef_p) and "--force" not in sys.argv:
        print("exists, skip (use --force to refetch)"); return
    land, reef = [], []
    for f in osm2geojson.json2geojson(overpass())["features"]:
        t = f["properties"].get("tags", {})
        poly = as_polygon(f)
        if poly is None or poly.is_empty:
            continue
        if t.get("place") in ("island", "islet"):
            land.append(feature(poly, name=t.get("name", "")))
        elif t.get("natural") == "reef":
            reef.append(feature(poly))
    os.makedirs(OUT, exist_ok=True)
    for p, fs in ((land_p, land), (reef_p, reef)):
        json.dump({"type": "FeatureCollection", "features": fs}, open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(os.path.basename(p), len(fs), "features,", round(os.path.getsize(p) / 1024, 1), "KB")
    assert len(land) >= 20, "島嶼數不對（2026-09-29 抓到 23 個島嶼多邊形），檢查 Overpass 回傳"

if __name__ == "__main__":
    main()
