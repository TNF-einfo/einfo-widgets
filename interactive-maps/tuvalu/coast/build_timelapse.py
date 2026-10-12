# -*- coding: utf-8 -*-
"""海岸線影片的縮時用圖：2022-08 到 2026-09 每個月挑一景沒雲的 Sentinel-2，範圍、調色、放大銳化都跟 build_images.py 一樣。

   owner 2026-10-12 要的（「有沒有辦法你去多抓幾張圖，生成一個縮時感覺的」），只給影片用（video/make_coast_video.mjs），互動頁不用。
   挑法：每個月照整景雲量排，依序拉這個範圍的 SCL（場景分類）小圖，雲（8、9、10）與雲影（3）合計 2% 以下就用，
   試四景都沒有就取其中最少、但超過 5% 的月份跳過。五個階段的月份直接用 build_images.py 那五景。
   圖存 img/timelapse/（不進 repo，約 3 MB），挑片結果存 img/timelapse/list.json（進 repo）。
   有 list.json 就照它補抓缺的圖、不重挑（加 --reselect 才重挑）；小圖的雲量快取在同一夾。需連網，第一次約 10～15 分鐘。

   python interactive-maps/tuvalu/coast/build_timelapse.py [--reselect] [--max-cloud 0.075]
"""
import io, json, math, sys, time, urllib.request
from collections import defaultdict
import numpy as np
from PIL import Image, ImageFilter
from build_images import API, OUT, REF, RES, SCENES, W, S, E, N, match, merc

TL = OUT / "timelapse"
UA = {"User-Agent": "einfo-widgets-basemap/0.1"}   # 匿名：UA 只寫工具名
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
FIRST, LAST = "2022-08", "2026-09"
CLOUDY = {3, 8, 9, 10}   # SCL：雲影、雲（中、高機率）、卷雲
# 一個月裡最少雲的那景超過這個比例就跳過。SCL 會把浪花、白沙也算成雲，晴天也有 2～4%，所以不能壓到 2% 以下。
# 2026-10-12 用 --max-cloud 0.075 挑出 39 張，看過縮圖再剔掉下面這幾張（雲落在主島或新生地附近），那幾個月就空著
WORST = float(sys.argv[sys.argv.index("--max-cloud") + 1]) if "--max-cloud" in sys.argv else .05
EXCLUDE = {
    "2022-09-28": "雲影落在主島中段",
    "2023-01-26": "施工區上方有一層霧",
    "2023-04-21": "大片雲蓋住主島與施工區",
    "2023-05-31": "新生地旁有雲，看起來像白沙",
    "2024-06-09": "新生地旁的潟湖有幾朵雲",
    "2026-05-05": "第二階段旁的潟湖有一大朵雲",
}


def get(url, data=None):
    headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
    raw = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=180).read()
    time.sleep(1)   # 節流
    return raw


def grid():
    x1, y1 = merc(W, S)
    x2, y2 = merc(E, N)
    x1, y1 = math.floor(x1 / RES) * RES, math.floor(y1 / RES) * RES   # 跟 build_images.py 一樣對齊 10 公尺格網
    w, h = round((x2 - x1) / RES), round((y2 - y1) / RES)
    return f"{x1},{y1},{x1 + w * RES},{y1 + h * RES}", w, h


def cloud_frac(scl, mask):
    """SCL 小圖裡雲與雲影占有效像素的比例；有效像素不到九成（景的邊緣、缺資料）回 1。"""
    valid = mask > 0
    if valid.mean() < .9:
        return 1.0
    return float(np.isin(scl[valid], list(CLOUDY)).mean())


def pick(cands, frac, worst=.05):
    """cands 照整景雲量排；frac(item) 回雲量比例。回 (item, 雲量)，整個月都超過 worst 回 None。"""
    seen = []
    for c in cands[:4]:
        f = frac(c)
        if f <= .02:
            return c, f
        seen.append((f, c))
    f, c = min(seen)
    return (c, f) if f <= worst else None


def main():
    TL.mkdir(exist_ok=True)
    bbox, w, h = grid()
    if (TL / "list.json").exists() and "--reselect" not in sys.argv:   # 挑過了就照清單補抓缺的圖；要重挑加 --reselect
        fetch(json.loads((TL / "list.json").read_text(encoding="utf-8")), bbox, w, h)
        return
    body ={"collections": ["sentinel-2-l2a"], "bbox": [W, S, E, N], "limit": 1000,
            "datetime": f"{FIRST}-01T00:00:00Z/{LAST}-30T23:59:59Z", "query": {"eo:cloud_cover": {"lt": 70}}}
    feats = json.loads(get(STAC, json.dumps(body).encode()))["features"]
    months = defaultdict(list)
    for f in sorted(feats, key=lambda f: f["properties"]["eo:cloud_cover"]):
        months[f["properties"]["datetime"][:7]].append(f["id"])
    keys = {d[:7]: (d, item) for d, item in SCENES.items()}
    cache_file = TL / "scl_cache.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}

    def frac(item):
        if item not in cache:
            a = np.load(io.BytesIO(get(f"{API}/{bbox}/{w // 4}x{h // 4}.npy?collection=sentinel-2-l2a&item={item}"
                                       "&assets=SCL&coord_crs=epsg:3857&dst_crs=epsg:3857&resampling=nearest")))
            cache[item] = cloud_frac(a[0], a[1])
            cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        return cache[item]

    chosen = []
    for m in sorted(months):
        if not FIRST <= m <= LAST:
            continue
        if m in keys:
            d, item = keys[m]
            chosen.append({"date": d, "item": item, "key": True})
            continue
        got = pick(months[m], frac, WORST)
        d = got and got[0].split("_")[2]
        why = "雲多" if got is None else EXCLUDE.get(f"{d[:4]}-{d[4:6]}-{d[6:8]}")
        print(m, f"跳過（{why}）" if why else f"{got[0]} 雲 {got[1]:.1%}", flush=True)
        if not why:
            item, f = got
            chosen.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:8]}", "item": item, "key": False, "cloud": round(f, 4)})
    for c in chosen:
        c["file"] = (f"../s2_{c['date'].replace('-', '')}.webp" if c["key"] else f"s2_{c['date'].replace('-', '')}.webp")
    (TL / "list.json").write_text(json.dumps(chosen, indent=1, ensure_ascii=False), encoding="utf-8")
    fetch(chosen, bbox, w, h)


def fetch(chosen, bbox, w, h):
    """清單裡還沒有圖的抓下來：照 2026-01-05 那景調色、放大兩倍、銳化（同 build_images.py）。五個階段用 img/ 那五張。"""
    ref = None
    for c in chosen:
        out = TL / c["file"]
        if c["key"] or out.exists():
            continue
        if ref is None:   # 調色的參考景要原始解析度，跟 build_images.py 一樣是 2026-01-05 那景
            ref = np.asarray(Image.open(io.BytesIO(get(f"{API}/{bbox}/{w}x{h}.png?collection=sentinel-2-l2a&item={SCENES[REF]}"
                                                       "&assets=visual&coord_crs=epsg:3857&dst_crs=epsg:3857&reproject=lanczos"))).convert("RGB"))
        a = np.asarray(Image.open(io.BytesIO(get(f"{API}/{bbox}/{w}x{h}.png?collection=sentinel-2-l2a&item={c['item']}"
                                                 "&assets=visual&coord_crs=epsg:3857&dst_crs=epsg:3857&reproject=lanczos"))).convert("RGB"))
        big = Image.fromarray(match(a, ref)).resize((w * 2, h * 2), Image.LANCZOS)
        big.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2)).save(out, quality=85, method=6)
        print("寫出", out.name, flush=True)
    print(f"共 {len(chosen)} 張（五個階段 {sum(c['key'] for c in chosen)} 張）")


def selftest():
    scl = np.array([[6, 6, 8, 3], [6, 9, 6, 6]], np.uint8)
    assert cloud_frac(scl, np.ones_like(scl)) == .375
    assert cloud_frac(scl, np.array([[0, 0, 1, 1], [1, 1, 1, 1]])) == 1.0   # 缺資料超過一成
    fr = {"a": .3, "b": .01, "c": 0}.get
    assert pick(["a", "b", "c"], fr) == ("b", .01)                         # 第一個夠乾淨的就用
    assert pick(["a", "x"], {"a": .04, "x": .06}.get) == ("a", .04)        # 都不夠乾淨，取最少但要 5% 以下
    assert pick(["a"], {"a": .2}.get) is None
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
