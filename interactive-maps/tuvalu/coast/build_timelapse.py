# -*- coding: utf-8 -*-
"""海岸線影片的縮時用圖：五個階段之間照時間平均抽的 Sentinel-2，範圍、調色、放大銳化都跟 build_images.py 一樣。

   owner 2026-10-12 要的（「有沒有辦法你去多抓幾張圖，生成一個縮時感覺的」「多塞幾幀，一秒五幀好了」「有雲的沒差」
   「字卡停一秒，兩半秒給縮時如何」），只給影片用（video/make_coast_video.mjs），互動頁不用。
   挑法：相鄰兩個階段之間切成 --per-segment 格（預設 16），每格挑離中點最近、雲量不超過 --max-cloud（預設 25%）的一天，
   整格都太多雲就空著。雲量是拉這個範圍的 SCL（場景分類）小圖，算雲（8、9、10）與雲影（3）占的比例；
   SCL 會把浪花、白沙也算成雲，晴天也有 2～4%。同一天有兩個處理版本取雲少的。五個階段那天直接用 build_images.py 那五景。
   圖存 img/timelapse/（不進 repo），挑片結果存 img/timelapse/list.json（進 repo）。
   有 list.json 就照它補抓缺的圖、不重挑（加 --reselect 才重挑）；小圖的雲量快取在同一夾。需連網，第一次要半小時以上。

   python interactive-maps/tuvalu/coast/build_timelapse.py [--reselect] [--force] [--max-cloud 0.25] [--per-segment 16]
   --force 是調色方法改了要全部重做（原始圖在 img/timelapse/raw/，不用重抓）。
"""
import io, json, math, sys, time, urllib.request
from collections import defaultdict
from datetime import date
import numpy as np
from PIL import Image, ImageFilter
from build_images import API, OUT, REF, RES, SCENES, W, S, E, N, match, merc

TL = OUT / "timelapse"
RAW = TL / "raw"   # 每一景原始解析度的 RGB 與 SCL（各約 0.5 MB），一樣不進 repo
UA = {"User-Agent": "einfo-widgets-basemap/0.1"}   # 匿名：UA 只寫工具名
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
CLOUDY = {3, 8, 9, 10}   # SCL：雲影、雲（中、高機率）、卷雲
WORST = float(sys.argv[sys.argv.index("--max-cloud") + 1]) if "--max-cloud" in sys.argv else .25
# 相鄰兩個階段之間抽幾張：owner 要一秒 5 張、字卡不停（「字卡不要停好了，都給縮時」），每段 3.5 秒，扣掉階段那張 16 張
PER = int(sys.argv[sys.argv.index("--per-segment") + 1]) if "--per-segment" in sys.argv else 16


def iso(item):
    """景號裡的拍攝日期（UTC）：S2A_MSIL2A_20230605T222801_… → 2023-06-05。"""
    d = item.split("_")[2]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def get(url, data=None):
    """節流的 GET／POST；伺服器 5xx 或逾時就退避重試，第三次還失敗才丟出去（Planetary Computer 偶爾回 500）。"""
    headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
    for attempt in range(3):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=180).read()
            time.sleep(1)   # 節流
            return body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt == 2 or getattr(e, "code", 500) < 500:
                raise
            print(f"  {e}，{15 * (attempt + 1)} 秒後重試", flush=True)
            time.sleep(15 * (attempt + 1))


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
            try:
                a = np.load(io.BytesIO(get(f"{API}/{bbox}/{w // 4}x{h // 4}.npy?collection=sentinel-2-l2a&item={item}"
                                           "&assets=SCL&coord_crs=epsg:3857&dst_crs=epsg:3857&resampling=nearest")))
            except urllib.error.URLError as e:   # 重試後還是失敗：這次當作抓不到，不寫快取，下次再試
                print(iso(item), f"抓不到（{e}），先跳過", flush=True)
                return 1.0
            cache[item] = cloud_frac(a[0], a[1])
            cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            print(iso(item), f"雲 {cache[item]:.1%}", flush=True)
        return cache[item]

    chosen = select(items, frac, WORST, PER)
    (TL / "list.json").write_text(json.dumps(chosen, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"挑出 {len(chosen)} 張（五個階段 {sum(c['key'] for c in chosen)} 張）", flush=True)
    fetch(chosen, bbox, w, h)


def raw(item, bbox, w, h):
    """這一景原始解析度的 RGB，與「不是雲、不是雲影」的遮罩（SCL）。存在 raw/，重算顏色不用重抓。"""
    RAW.mkdir(exist_ok=True)
    png, npy = RAW / f"{item}.png", RAW / f"{item}_scl.npy"
    q = f"{bbox}/{w}x{h}"
    if not png.exists():
        png.write_bytes(get(f"{API}/{q}.png?collection=sentinel-2-l2a&item={item}&assets=visual"
                            "&coord_crs=epsg:3857&dst_crs=epsg:3857&reproject=lanczos"))
    if not npy.exists():
        npy.write_bytes(get(f"{API}/{q}.npy?collection=sentinel-2-l2a&item={item}&assets=SCL"
                            "&coord_crs=epsg:3857&dst_crs=epsg:3857&resampling=nearest"))
    a = np.load(npy)
    return np.asarray(Image.open(png).convert("RGB")), (a[1] > 0) & ~np.isin(a[0], list(CLOUDY))


def match_clear(src, ref, ms, mr):
    """直方圖匹配（同 build_images.match），但分布只拿沒雲的像素算。整張一起算的話，大片雲占掉亮部，
       陸地和海會被壓暗，看起來像晚上（owner 10-12：「你有用晚上的嗎？」）。雲比晴空最亮的還亮，對到參考圖的最亮。"""
    out = np.empty_like(src)
    for c in range(3):
        s, r = np.sort(src[..., c][ms]), np.sort(ref[..., c][mr])
        cdf = np.searchsorted(s, src[..., c], side="right") / s.size   # 每個像素在晴空像素裡的分位
        out[..., c] = np.interp(cdf, np.linspace(0, 1, r.size), r).round()
    return out


def fetch(chosen, bbox, w, h):
    """清單裡還沒有圖的做出來（加 --force 全部重做）：照 2026-01-05 那景調色（排除雲）、放大兩倍、銳化（同 build_images.py）。
       五個階段用 img/ 那五張。"""
    ref = None
    for c in chosen:
        out = TL / c["file"]
        if c["key"] or out.exists() and "--force" not in sys.argv:
            continue
        ref = ref or raw(SCENES[REF], bbox, w, h)   # 調色的參考景要原始解析度，跟 build_images.py 一樣是 2026-01-05 那景
        rgb, clear = raw(c["item"], bbox, w, h)
        if clear.mean() < .2:   # 幾乎整片是雲，排除後剩的太少，退回整張一起算
            clear = np.ones_like(clear)
        big = Image.fromarray(match_clear(rgb, ref[0], clear, ref[1])).resize((w * 2, h * 2), Image.LANCZOS)
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
    g = np.random.default_rng(0).integers(20, 150, (60, 60, 3)).astype(np.uint8)
    ok = np.ones((60, 60), bool)
    assert np.abs(match_clear(g, g, ok, ok).astype(int) - g).max() <= 1   # 沒雲時對自己匹配＝原圖
    cloudy, sky = g.copy(), ok.copy()
    cloudy[:30], sky[:30] = 255, False                                    # 上半片是雲
    out = match_clear(cloudy, g, sky, ok)
    assert abs(out[30:].mean() - g[30:].mean()) < 3 and out[:30].min() >= 140   # 晴空那半亮度不變，雲對到最亮
    assert match(cloudy, g)[30:].mean() < g[30:].mean() - 15             # 舊做法：整張一起算會把晴空壓暗
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
