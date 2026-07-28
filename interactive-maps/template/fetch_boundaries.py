# -*- coding: utf-8 -*-
"""任意城市界線抓取（Stage 2）：由實例 spots 的座標範圍 → Nominatim 補座標 + Overpass 抓
   boundary=administrative → osm2geojson 組成多邊形 → 寫成兩層 geojson（land 填色 + subdiv 細界）
   ＋自動導出地名標籤 places.json。快取進 {instance}/boundaries/，重跑離線可用。

用法（獨立測試）：python template/fetch_boundaries.py <instance>
被 gen_map 呼叫：ensure_boundaries(instance_dir, spots) → 需要時才抓、已有就跳過（idempotent）。
名稱優先 name:zh（繁中受眾），退 name。Overpass 走多鏡像 fallback（主站常 504）。"""
import urllib.request, urllib.parse, json, os, time

UA = {"User-Agent": "research-lab-map-template/0.1 (gassaofilm@gmail.com)"}
OVERPASS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

def _get(url, timeout=45):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()

def geocode(q):
    """地名 → {lat,lng}。Nominatim。"""
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1})
    d = json.loads(_get(u))
    time.sleep(1.1)  # Nominatim 使用政策：≤1 req/s
    if not d:
        return None
    return {"lat": float(d[0]["lat"]), "lng": float(d[0]["lon"])}

def _overpass(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for ep in OVERPASS:
        try:
            raw = urllib.request.urlopen(
                urllib.request.Request(ep, data=data, headers=UA), timeout=120).read()
            return json.loads(raw)
        except Exception as ex:
            last = ex; time.sleep(2)
    raise RuntimeError("all overpass mirrors failed: " + str(last))

def bbox_from_spots(spots, pad=0.18):
    las = [s["lat"] for s in spots]; lns = [s["lng"] for s in spots]
    dla = (max(las) - min(las)) or 0.05
    dln = (max(lns) - min(lns)) or 0.05
    return (min(las) - dla * pad, min(lns) - dln * pad,
            max(las) + dla * pad, max(lns) + dln * pad)  # s,w,n,e

def _name(tags):
    return tags.get("name:zh") or tags.get("name:zh-Hant") or tags.get("name") or ""

def _centroid(geom):
    """粗略：所有外環座標平均（標籤定位用，夠準）。"""
    pts = []
    def walk(c):
        if isinstance(c[0], (int, float)):
            pts.append(c)
        else:
            for x in c: walk(x)
    walk(geom["coordinates"])
    if not pts: return None
    return (sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts))  # lat,lng

def fetch(bbox, levels=(4, 6, 7)):
    """回傳 {level: [features]}（只留多邊形、有名字者）。"""
    import osm2geojson
    s, w, n, e = bbox
    lv = "|".join(str(x) for x in levels)
    q = (f'[out:json][timeout:90];'
         f'(relation["boundary"="administrative"]["admin_level"~"^({lv})$"]({s},{w},{n},{e}););'
         f'out geom;')
    gj = osm2geojson.json2geojson(_overpass(q))
    by = {}
    for f in gj["features"]:
        if f["geometry"]["type"] not in ("Polygon", "MultiPolygon"):
            continue
        t = f["properties"].get("tags", f["properties"])
        try:
            al = int(t.get("admin_level", 0))
        except (ValueError, TypeError):
            continue
        f["properties"] = {"name": _name(t), "admin_level": al}
        by.setdefault(al, []).append(f)
    return by

def ensure_boundaries(instance_dir, spots, force=False):
    """需要時抓界線寫入 {instance}/boundaries/（land.geojson + subdiv.geojson + places.json）。
       已存在且非 force 就跳過（idempotent）。回傳 (boundary_files, places)。"""
    bd = os.path.join(instance_dir, "boundaries")
    os.makedirs(bd, exist_ok=True)
    land_p = os.path.join(bd, "land.geojson")
    sub_p = os.path.join(bd, "subdiv.geojson")
    places_p = os.path.join(bd, "places.json")
    if not force and os.path.isfile(land_p) and os.path.isfile(sub_p) and os.path.isfile(places_p):
        return (["land.geojson", "subdiv.geojson"], json.load(open(places_p, encoding="utf-8")))

    bbox = bbox_from_spots(spots)
    by = fetch(bbox)
    if not by:
        raise RuntimeError("no admin boundaries found in bbox " + str(bbox))
    levels = sorted(by)
    land_lv = levels[0]                       # 最粗一級＝填色陸地
    sub_lv = levels[-1] if len(levels) > 1 else levels[0]   # 最細一級＝細界
    land = {"type": "FeatureCollection", "features": by[land_lv]}
    sub = {"type": "FeatureCollection", "features": by[sub_lv]}
    json.dump(land, open(land_p, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(sub, open(sub_p, "w", encoding="utf-8"), ensure_ascii=False)

    # 地名：每個多邊形放一個標籤（land 級＝big）
    places = []
    seen = set()
    for lv, feats in sorted(by.items()):
        for f in feats:
            nm = f["properties"]["name"]
            if not nm or nm in seen:
                continue
            c = _centroid(f["geometry"])
            if not c:
                continue
            seen.add(nm)
            places.append({"t": nm, "lat": round(c[0], 5), "lng": round(c[1], 5),
                           **({"big": 1} if lv == land_lv else {})})
    json.dump(places, open(places_p, "w", encoding="utf-8"), ensure_ascii=False)
    return (["land.geojson", "subdiv.geojson"], places)

if __name__ == "__main__":
    import sys, importlib.util
    inst = sys.argv[1]
    idir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), inst)
    sp = importlib.util.spec_from_file_location("cfg", os.path.join(idir, "spots.py"))
    cfg = importlib.util.module_from_spec(sp); sp.loader.exec_module(cfg)
    files, places = ensure_boundaries(idir, cfg.SPOTS, force="--force" in sys.argv)
    print("boundary files:", files, "| places:", len(places))
    print("sample places:", [p["t"] for p in places[:8]])
