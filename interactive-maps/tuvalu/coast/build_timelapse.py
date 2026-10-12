# -*- coding: utf-8 -*-
"""海岸線影片的縮時用圖：五個階段之間照時間平均抽的 Sentinel-2，範圍、調色、放大銳化都跟 build_images.py 一樣。

   owner 2026-10-12 要的（「有沒有辦法你去多抓幾張圖，生成一個縮時感覺的」「多塞幾幀，一秒五幀好了」「有雲的沒差」
   「字卡停一秒，兩半秒給縮時如何」），只給影片用（video/make_coast_video.mjs），互動頁不用。
   挑法：相鄰兩個階段之間切成 --per-segment 格（預設 10），每格挑離中點最近、雲量不超過 --max-cloud（預設 25%）的一天，
   整格都太多雲就空著。雲量是拉這個範圍的 SCL（場景分類）小圖，算雲（8、9、10）與雲影（3）占的比例；
   SCL 會把浪花、白沙也算成雲，晴天也有 2～4%。同一天有兩個處理版本取雲少的。五個階段那天直接用 build_images.py 那五景。
   圖存 img/timelapse/（不進 repo），挑片結果存 img/timelapse/list.json（進 repo）。
   有 list.json 就照它補抓缺的圖、不重挑（加 --reselect 才重挑）；小圖的雲量快取在同一夾。需連網，第一次要半小時以上。

   python interactive-maps/tuvalu/coast/build_timelapse.py [--reselect] [--max-cloud 0.25] [--per-segment 10]
"""
import io, json, math, sys, time, urllib.request
from collections import defaultdict
from datetime import date
import numpy as np
from PIL import Image, ImageFilter
from build_images import API, OUT, REF, RES, SCENES, W, S, E, N, match, merc

TL = OUT / "timelapse"
UA = {"User-Agent": "einfo-widgets-basemap/0.1"}   # 匿名：UA 只寫工具名
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
CLOUDY = {3, 8, 9, 10}   # SCL：雲影、雲（中、高機率）、卷雲
WORST = float(sys.argv[sys.argv.index("--max-cloud") + 1]) if "--max-cloud" in sys.argv else .25
# 相鄰兩個階段之間抽幾張：owner 要縮時每段 2.5 秒、一秒 5 張，扣掉淡入階段那張約 10 張
PER = int(sys.argv[sys.argv.index("--per-segment") + 1]) if "--per-segment" in sys.argv else 10


def iso(item):
    """景號裡的拍攝日期（UTC）：S2A_MSIL2A_20230605T222801_… → 2023-06-05。"""
    d = item.split("_")[2]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


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


def select(items, frac, worst, n):
    """照日期排的清單：五個階段那天用那五景；相鄰兩個階段之間切成 n 格，每格挑離格子中點最近、雲量不超過 worst 的一天
       （同一天有兩個處理版本取雲少的），整格都太多雲就空著。frac 只對看過的景呼叫，小圖抓得少。"""
    day = lambda d: date.fromisoformat(d).toordinal()
    byday = defaultdict(list)
    for item in items:
        byday[iso(item)].append(item)
    keys = sorted(SCENES.items())
    out = [{"date": d, "item": item, "key": True} for d, item in keys]
    for (d0, _), (d1, _) in zip(keys, keys[1:]):
        slot = (day(d1) - day(d0)) / n
        for j in range(n):
            mid = day(d0) + (j + .5) * slot
            near = sorted((d for d in byday if d0 < d < d1 and abs(day(d) - mid) <= slot / 2), key=lambda d: abs(day(d) - mid))
            for d in near:
                best = min(byday[d], key=frac)
                if frac(best) <= worst:
                    out.append({"date": d, "item": best, "key": False, "cloud": round(frac(best), 4)})
                    break
    out.sort(key=lambda c: c["date"])
    for c in out:
        c["file"] = f"../s2_{c['date'].replace('-', '')}.webp" if c["key"] else f"s2_{c['date'].replace('-', '')}.webp"
    return out


def main():
    TL.mkdir(exist_ok=True)
    bbox, w, h = grid()
    if (TL / "list.json").exists() and "--reselect" not in sys.argv:   # 挑過了就照清單補抓缺的圖
        fetch(json.loads((TL / "list.json").read_text(encoding="utf-8")), bbox, w, h)
        return
    body = {"collections": ["sentinel-2-l2a"], "bbox": [W, S, E, N], "limit": 1000,
            "datetime": f"{min(SCENES)}T00:00:00Z/{max(SCENES)}T23:59:59Z", "query": {"eo:cloud_cover": {"lt": 70}}}
    items = [f["id"] for f in json.loads(get(STAC, json.dumps(body).encode()))["features"]]
    cache_file = TL / "scl_cache.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}

    def frac(item):
        if item not in cache:
            a = np.load(io.BytesIO(get(f"{API}/{bbox}/{w // 4}x{h // 4}.npy?collection=sentinel-2-l2a&item={item}"
                                       "&assets=SCL&coord_crs=epsg:3857&dst_crs=epsg:3857&resampling=nearest")))
            cache[item] = cloud_frac(a[0], a[1])
            cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            print(iso(item), f"雲 {cache[item]:.1%}", flush=True)
        return cache[item]

    chosen = select(items, frac, WORST, PER)
    (TL / "list.json").write_text(json.dumps(chosen, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"挑出 {len(chosen)} 張（五個階段 {sum(c['key'] for c in chosen)} 張）", flush=True)
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
    it = lambda d, v: f"S2A_MSIL2A_{d}T222801_R072_T60LYR_{v}"
    # 第一段 2022-08-09～2023-06-05 切兩格，格子中點約 2022-10-23、2023-03-23
    fr = {it("20221020", "a"): .10, it("20221020", "b"): .05, it("20221025", "a"): .5,
          it("20230320", "a"): .3, it("20220801", "a"): 0, it("20230605", "a"): 0}
    got = select(list(fr), fr.get, .25, 2)
    oct_ = [c for c in got if c["date"].startswith("2022-10")]
    assert len(oct_) == 1 and oct_[0]["item"].endswith("_b")            # 離中點最近的那天雲太多，取下一天；同一天取雲少的版本
    assert not any(c["date"] in ("2023-03-20", "2022-08-01") for c in got)   # 整格都太多雲就空著；第一個階段之前不收
    assert [c for c in got if c["date"] == "2023-06-05"][0]["key"]      # 階段那天用那一景
    assert len(got) == len(SCENES) + 1
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
