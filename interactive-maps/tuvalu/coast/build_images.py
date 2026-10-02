# -*- coding: utf-8 -*-
"""富納富提海岸線變化用的衛星影像：同一個範圍、五個日期的 Sentinel-2，各存一張 WebP（img/s2_<日期>.webp）。

   做法跟主圖 basemap/s2_20260105_2x.webp 一樣：Planetary Computer 渲染 API 出 Web Mercator 10 公尺圖，
   放大兩倍、銳化（參數同 build_video_basemap.py）。範圍對齊 10 公尺格網，五張逐像素對得上，頁面才能直接疊著淡入淡出。
   各景的大氣、海況不同，原樣疊起來切換時整張忽明忽暗，所以每張都照主圖那一景（2026-01-05）做直方圖匹配，只調色、不動內容。
   景是 2026-10-02 從 2019 年起所有雲量低的景裡挑的（填海區上方沒雲、看得出那個階段），挑片紀錄見 README。
   五張都在就跳過，加 --force 重抓（調色要拿參考景比，所以一次重抓全部）。需連網。

   python interactive-maps/tuvalu/coast/build_images.py
"""
import io, json, math, pathlib, sys, time, urllib.request
import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).parent
OUT = HERE / "img"
SCENES = {   # 日期: Sentinel-2 L2A 景號
    "2022-08-09": "S2A_MSIL2A_20220809T222811_R072_T60LYR_20220811T084851",   # 填海之前（第一階段 2022 年底開工）
    "2023-06-05": "S2A_MSIL2A_20230605T222801_R072_T60LYR_20230606T031347",   # 第一階段施工中
    "2024-08-28": "S2A_MSIL2A_20240828T222751_R072_T60LYR_20240829T015044",   # 第一階段完工、第二階段還沒動工
    "2026-01-05": "S2B_MSIL2A_20260105T222759_R072_T60LYR_20260106T011006",   # 第二階段完工（跟主圖同一景）
    "2026-09-17": "S2C_MSIL2A_20260917T222801_R072_T60LYR_20260918T005311",   # 最新一景：北邊又多一片填地
}
REF = "2026-01-05"                               # 調色的參考景（owner 定案的主圖底圖）
W, S, E, N = 179.172, -8.550, 179.214, -8.500   # 瓦伊阿庫一帶，桌機、手機兩種畫框都從這張裡切
RES = 10
R = 20037508.342789244
API = "https://planetarycomputer.microsoft.com/api/data/v1/item/bbox"


def merc(lon, lat):
    return lon * R / 180, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R / math.pi


def lonlat(x, y):
    return x * 180 / R, math.degrees(2 * math.atan(math.exp(y * math.pi / R)) - math.pi / 2)


def match(src, ref):
    """每個色版照參考圖的直方圖重新對應（累積分布對齊），uint8 進、uint8 出。"""
    out = np.empty_like(src)
    for c in range(3):
        s, r = src[..., c].ravel(), ref[..., c].ravel()
        sv, si, sc = np.unique(s, return_inverse=True, return_counts=True)
        rv, rc = np.unique(r, return_counts=True)
        out[..., c] = np.interp(np.cumsum(sc) / s.size, np.cumsum(rc) / r.size, rv)[si].reshape(src.shape[:2]).round()
    return out


def main():
    x1, y1 = merc(W, S)
    x2, y2 = merc(E, N)
    x1, y1 = math.floor(x1 / RES) * RES, math.floor(y1 / RES) * RES   # 對齊 10 公尺格網
    w, h = round((x2 - x1) / RES), round((y2 - y1) / RES)
    OUT.mkdir(exist_ok=True)
    files = {d: OUT / f"s2_{d.replace('-', '')}.webp" for d in SCENES}
    if all(f.exists() for f in files.values()) and "--force" not in sys.argv:
        print("五張都在，跳過（加 --force 重抓）")
        return
    nat = {}
    for date, item in SCENES.items():
        url = (f"{API}/{x1},{y1},{x1 + w * RES},{y1 + h * RES}/{w}x{h}.png?collection=sentinel-2-l2a&item={item}"
               "&assets=visual&coord_crs=epsg:3857&dst_crs=epsg:3857&reproject=lanczos")
        req = urllib.request.Request(url, headers={"User-Agent": "einfo-widgets-basemap/0.1"})   # 匿名：UA 只寫工具名
        nat[date] = np.asarray(Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=180).read())).convert("RGB"))
        print("抓到", date)
        time.sleep(1)   # 節流
    for date, a in nat.items():
        im = Image.fromarray(a if date == REF else match(a, nat[REF]))
        big = im.resize((w * 2, h * 2), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
        big.save(files[date], quality=85, method=6)
        print("寫出", files[date].name, big.size, f"{files[date].stat().st_size / 1e3:.0f} KB")
    (lon1, lat1), (lon2, lat2) = lonlat(x1, y1), lonlat(x1 + w * RES, y1 + h * RES)
    meta = {"bounds": [[lat1, lon1], [lat2, lon2]], "size": [w * 2, h * 2], "scenes": SCENES}
    (OUT / "bounds.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print("範圍（頁面的 BOUNDS 要跟這個一樣）：", meta["bounds"])


def selftest():
    a = np.random.default_rng(0).integers(0, 200, (40, 50, 3)).astype(np.uint8)
    assert (match(a, a) == a).all()                                # 對自己匹配＝原圖
    assert abs(match(a, a + 30).mean() - (a.mean() + 30)) < 0.5    # 參考圖整體亮 30，結果也亮 30
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
