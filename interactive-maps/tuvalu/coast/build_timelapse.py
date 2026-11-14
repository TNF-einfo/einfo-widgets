# -*- coding: utf-8 -*-
"""海岸線影片的縮時用圖：五個階段之間照時間平均抽的 Sentinel-2，範圍、調色、放大銳化都跟 build_images.py 一樣。

   2026-10-12 要的（「有沒有辦法你去多抓幾張圖，生成一個縮時感覺的」「多塞幾幀，一秒五幀好了」
   「字卡停一秒，兩半秒給縮時如何」），只給影片用（video/make_coast_video.mjs），互動頁不用。
   挑法：相鄰兩個階段之間切成 --per-segment 格（預設 16），每格挑離中點最近、雲量不超過 --max-cloud（預設 3%）、
   而且眼睛看過沒雲（不在 REJECT）的一天，整格都沒有就空著。同一天有兩個處理版本取雲少的。
   雲量是 SCL（場景分類）小圖在影片畫面露出的那塊（VIEW）裡，雲（8、9、10）與雲影（3）占的比例，扣掉浪花、白沙這些
   固定被判成雲的像素（見 cloud_fracs）。2026-10-19 要「把有雲的抽掉」，從整個範圍 25% 改成這樣；SCL 抓不到小積雲和霧，
   所以候選還是逐張裁成影片畫面看過，看到雲、雲影、霧的記進 REJECT。
   五個階段用 build_images.py 那五景，畫面裡有雲的換同一個月更晴的一景（SWAP，互動頁照舊），
   跟縮時圖一樣另做一張無損 PNG（互動頁那五張是有損 WebP，影片用了畫質會差）。
   圖存 img/timelapse/（不進 repo），挑片結果存 img/timelapse/list.json（進 repo）。
   有 list.json 就照它補抓缺的圖、不重挑（加 --reselect 才重挑，SCL 小圖存在 scl/，抓過不再抓）。需連網，第一次要半小時以上。

   python interactive-maps/tuvalu/coast/build_timelapse.py [--reselect] [--force] [--max-cloud 0.03] [--per-segment 16]
   --force 是調色方法改了要全部重做（原始圖在 img/timelapse/raw/，不用重抓）。
"""
import json, math, sys, time, urllib.request
from collections import defaultdict
from datetime import date
import numpy as np
from PIL import Image, ImageFilter
from build_images import API, OUT, REF, RES, SCENES, W, S, E, N, match, merc

TL = OUT / "timelapse"
RAW = TL / "raw"   # 每一景原始解析度的 RGB 與 SCL（各約 0.5 MB），一樣不進 repo
SCL = TL / "scl"   # 每一景整個範圍的 SCL 小圖（20 公尺，約 130 KB），算雲量用，一樣不進 repo
UA = {"User-Agent": "einfo-widgets-basemap/0.1"}   # 匿名：UA 只寫工具名
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
CLOUDY = {3, 8, 9, 10}   # SCL：雲影、雲（中、高機率）、卷雲
# 門檻：晴天扣掉固定誤判後多半在 0.1～0.7%；施工中剛填的白沙、濁水變得快，扣不掉，晴天也會到 2.5%（2025-02-14），所以放到 3%，
# 這一帶有雲的靠下面 REJECT 擋
WORST = float(sys.argv[sys.argv.index("--max-cloud") + 1]) if "--max-cloud" in sys.argv else .03
# 相鄰兩個階段之間抽幾張：要一秒 5 張、字卡不停（「字卡不要停好了，都給縮時」），每段 3.5 秒，扣掉階段那張 16 張
PER = int(sys.argv[sys.argv.index("--per-segment") + 1]) if "--per-segment" in sys.argv else 16
VIEW = (133, 0, 748, 1094)   # 影片畫面露出的範圍（2 倍影像的像素：左、上、右、下），make_coast_video.mjs 印的 view；鏡頭改了要跟著改
# 影片的階段影像，畫面裡看得到雲的換掉：原日期 → 換用的景號（互動頁照舊用 build_images.py 那五景）。
# 要換同一個月的，字卡上排的日期與內文（「2026年9月的影像上」）才對得上
SWAP = {"2026-09-17": "S2C_MSIL2A_20260907T222751_R072_T60LYR_20260908T004813"}   # 潟湖上兩團雲
# 雲量過了門檻、眼睛看還是有雲、雲影或霧的日子（2026-10-19 逐張裁成影片畫面看過）：日期 → 看到什麼
REJECT = {
    "2022-09-13": "潟湖與島上小雲", "2022-09-18": "整片灰濛的薄霧", "2022-09-28": "潟湖與外海小雲",
    "2022-10-28": "外海成片的雲與雲影", "2023-01-01": "左下外海一小團雲", "2023-01-11": "島上一團雲與雲影",
    "2023-02-05": "左上、右下小雲，潟湖有雲影", "2023-02-15": "潟湖成片小雲", "2023-02-20": "潟湖西南一小團雲",
    "2023-03-12": "下緣外海小雲與雲影", "2023-03-27": "左上潟湖一小團雲", "2023-04-06": "右上一團雲，整片薄霧",
    "2023-05-06": "右上外海小雲與雲影", "2023-05-11": "外海成片小雲", "2023-06-20": "右上外海小雲與雲影",
    "2023-07-25": "上緣潟湖一塊雲影", "2023-08-04": "左緣潟湖一小團雲", "2023-08-09": "外海四周小雲",
    "2023-09-18": "潟湖西北一道薄霧", "2023-12-02": "整片灰濛的薄霧", "2023-12-07": "左上一片帶彩邊的薄雲",
    "2023-12-17": "右側與下緣外海小雲", "2024-01-01": "下緣外海一小團雲與雲影", "2024-01-11": "上緣小雲、潟湖有雲影",
    "2024-01-21": "西南角與新生地上一層白霧", "2024-03-31": "下緣外海一小團雲", "2024-08-13": "潟湖上一片薄雲",
    "2024-09-12": "潟湖一團雲與雲影", "2024-10-27": "潟湖上成片薄雲", "2024-11-11": "左側潟湖小雲、左下雲影",
    "2024-11-16": "整片灰濛、左上小雲", "2025-01-15": "潟湖與外海小雲", "2025-01-20": "潟湖與外海幾小團雲",
    "2025-02-04": "右側外海小雲與雲影", "2025-03-11": "整片薄霧", "2025-05-10": "島上與外海小雲",
    "2025-05-15": "南段潟湖兩小團雲", "2025-05-30": "下緣外海一小團淡雲", "2025-06-04": "南段潟湖幾小團薄雲",
    "2025-06-09": "潟湖與外海小雲", "2025-06-29": "島上一團雲與雲影", "2025-08-08": "外海成片小雲",
    "2025-08-18": "潟湖成片小雲", "2025-09-12": "潟湖與外海小雲、雲影", "2025-09-17": "潟湖一片薄雲",
    "2025-10-17": "潟湖上成片薄雲", "2025-12-01": "潟湖與外海小雲", "2026-02-14": "下緣外海小雲",
    "2026-02-19": "潟湖成片小雲", "2026-03-21": "潟湖西側與外海小雲", "2026-04-10": "左上潟湖一小團雲",
    "2026-04-15": "南端潟湖成片小雲", "2026-05-20": "潟湖與外海小雲",
}


def iso(item):
    """景號裡的拍攝日期（UTC）：S2A_MSIL2A_20230605T222801_… → 2023-06-05。"""
    d = item.split("_")[2]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


KEYS = {iso(it): it for it in (SWAP.get(d, it) for d, it in SCENES.items())}   # 影片的五個階段：日期 → 景號


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


def scl(item, bbox, w, h):
    """這一景整個範圍的 SCL 小圖（20 公尺；第 0 層是分類、第 1 層是有沒有資料），存在 scl/。抓不到回 None，下次再試。"""
    SCL.mkdir(exist_ok=True)
    f = SCL / f"{item}.npy"
    if not f.exists():
        try:
            f.write_bytes(get(f"{API}/{bbox}/{w // 2}x{h // 2}.npy?collection=sentinel-2-l2a&item={item}"
                              "&assets=SCL&coord_crs=epsg:3857&dst_crs=epsg:3857&resampling=nearest"))
        except (urllib.error.URLError, TimeoutError) as e:   # 重試後還是失敗：這次當作沒有這一景
            print(iso(item), f"抓不到（{e}），先跳過", flush=True)
            return None
    return np.load(f)


def cloud_fracs(scls):
    """{景號: 影片畫面（VIEW）裡雲與雲影占有效像素的比例}；有效像素不到九成（景的邊緣、缺資料）算 1。
       SCL 會把浪花、白沙（連新填出來的地）也判成雲，晴天在畫面裡也有 1～9%，所以先扣掉固定的那些：前後 90 天內的其他景
       （不算同一天的另一個處理版本、不算雲量超過兩成的）有三成以上也判成雲的像素。雲會飄，浪花和白沙不會動。"""
    x0, y0, x1, y1 = (v // 4 for v in VIEW)   # 小圖是 2 倍影像的四分之一
    a = {it: s[:, y0:y1, x0:x1] for it, s in scls.items()}
    cloud = {it: np.isin(s[0], list(CLOUDY - {3})) for it, s in a.items()}
    shade = {it: s[0] == 3 for it, s in a.items()}
    ok = {it: s[1] > 0 for it, s in a.items()}
    raw = {it: float((cloud[it] | shade[it])[ok[it]].mean()) if ok[it].mean() >= .9 else 1.0 for it in a}
    day = {it: date.fromisoformat(iso(it)).toordinal() for it in a}
    out = {}
    for it in a:
        nb = [cloud[j] for j in a if 0 < abs(day[j] - day[it]) <= 90 and raw[j] <= .2]
        fixed = np.mean(nb, 0) >= .3 if nb else np.zeros_like(cloud[it])
        out[it] = 1.0 if raw[it] == 1.0 else float(((cloud[it] & ~fixed) | shade[it])[ok[it]].mean())
    return out


def select(items, frac, worst, n):
    """照日期排的清單：五個階段用 KEYS 那五景；相鄰兩個階段之間切成 n 格，每格挑離格子中點最近、雲量不超過 worst 的一天
       （同一天有兩個處理版本取雲少的），整格都沒有就空著。"""
    day = lambda d: date.fromisoformat(d).toordinal()
    byday = defaultdict(list)
    for item in items:
        byday[iso(item)].append(item)
    keys = sorted(KEYS.items())
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
    for c in out:   # 影片用無損 PNG（10-12 回報：「圖層畫質沒問題嗎」），五個階段也另做一張，不用互動頁那五張有損 WebP
        c["file"] = f"s2_{c['date'].replace('-', '')}.png"
    return out


def main():
    TL.mkdir(exist_ok=True)
    bbox, w, h = grid()
    if (TL / "list.json").exists() and "--reselect" not in sys.argv:   # 挑過了就照清單補抓缺的圖
        chosen = json.loads((TL / "list.json").read_text(encoding="utf-8"))
    else:
        # 不先用整幅的雲量篩：整幅 110 公里見方，六成是雲時這一小塊也可能是晴的（2026-09-07 就是）
        body = {"collections": ["sentinel-2-l2a"], "bbox": [W, S, E, N], "limit": 1000,
                "datetime": f"{min(KEYS)}T00:00:00Z/{max(KEYS)}T23:59:59Z"}
        items = [f["id"] for f in json.loads(get(STAC, json.dumps(body).encode()))["features"]]
        scls = {it: a for it in items if (a := scl(it, bbox, w, h)) is not None}
        fr = cloud_fracs(scls)
        chosen = select(list(scls), lambda it: 1.0 if iso(it) in REJECT else fr[it], WORST, PER)
        (TL / "list.json").write_text(json.dumps(chosen, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(scls)} 景裡挑出 {len(chosen)} 張（五個階段 {sum(c['key'] for c in chosen)} 張）", flush=True)
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
       陸地和海會被壓暗，看起來像晚上（10-12 回報：「你有用晚上的嗎？」）。雲比晴空最亮的還亮，對到參考圖的最亮。"""
    out = np.empty_like(src)
    for c in range(3):
        s, r = np.sort(src[..., c][ms]), np.sort(ref[..., c][mr])
        cdf = np.searchsorted(s, src[..., c], side="right") / s.size   # 每個像素在晴空像素裡的分位
        out[..., c] = np.interp(cdf, np.linspace(0, 1, r.size), r).round()
    return out


def fetch(chosen, bbox, w, h):
    """清單裡還沒有圖的做出來（加 --force 全部重做）：照 2026-01-05 那景調色（排除雲）、放大兩倍、銳化（同 build_images.py），
       存無損 PNG。五個階段也照同樣做法另做一張。"""
    ref = None
    for c in chosen:
        out = TL / c["file"]
        if out.exists() and "--force" not in sys.argv:
            continue
        ref = ref or raw(SCENES[REF], bbox, w, h)   # 調色的參考景要原始解析度，跟 build_images.py 一樣是 2026-01-05 那景
        rgb, clear = raw(c["item"], bbox, w, h)
        if clear.mean() < .2:   # 幾乎整片是雲，排除後剩的太少，退回整張一起算
            clear = np.ones_like(clear)
        big = Image.fromarray(match_clear(rgb, ref[0], clear, ref[1])).resize((w * 2, h * 2), Image.LANCZOS)
        big.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2)).save(out)
        print("寫出", out.name, flush=True)
    print(f"共 {len(chosen)} 張（五個階段 {sum(c['key'] for c in chosen)} 張）")


def selftest():
    it = lambda d, v: f"S2A_MSIL2A_{d}T222801_R072_T60LYR_{v}"
    def fake(cloud=False):   # SCL 小圖：全是水、都有資料，一條每景都有的浪花，cloud＝這一景多一塊雲
        a = np.full((2, 290, 240), 6, np.uint8)
        a[1], a[0][:, 40:44] = 1, 8
        if cloud:
            a[0][100:120, 100:120] = 9
        return a
    sc = {it("20230101", "a"): fake(), it("20230111", "a"): fake(), it("20230121", "a"): fake(True), it("20230121", "b"): fake(True)}
    fr = cloud_fracs(sc)
    assert fr[it("20230101", "a")] == 0                        # 浪花每景都判成雲，扣掉
    assert abs(fr[it("20230121", "a")] - 400 / (273 * 154)) < 1e-9   # 只有這一天有的雲照算；同一天的另一個版本不當鄰居
    sc[it("20230111", "a")][1][:60] = 0                         # 缺資料超過一成
    assert cloud_fracs(sc)[it("20230111", "a")] == 1.0
    # 第一段 2022-08-09～2023-06-05 切兩格，格子中點約 2022-10-23、2023-03-23
    fr = {it("20221020", "a"): .10, it("20221020", "b"): .05, it("20221025", "a"): .5,
          it("20230320", "a"): .3, it("20220801", "a"): 0, it("20230605", "a"): 0}
    got = select(list(fr), fr.get, .25, 2)
    oct_ = [c for c in got if c["date"].startswith("2022-10")]
    assert len(oct_) == 1 and oct_[0]["item"].endswith("_b")            # 離中點最近的那天雲太多，取下一天；同一天取雲少的版本
    assert not any(c["date"] in ("2023-03-20", "2022-08-01") for c in got)   # 整格都太多雲就空著；第一個階段之前不收
    assert [c for c in got if c["date"] == "2023-06-05"][0]["key"]      # 階段那天用那一景
    assert len(got) == len(KEYS) + 1
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
