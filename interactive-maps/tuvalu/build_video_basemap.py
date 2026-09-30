# -*- coding: utf-8 -*-
"""影片版專用的衛星底圖：同一景 Sentinel-2（2026-01-05）切整個富納富提環礁，鏡頭才飛得到富納法拉
   （owner 2026-09-30：「富那法拉可以直接移動過去，僅限影片版」）。互動地圖照用 basemap/s2_20260105_2x.webp（只切主島那段）。

   做法跟主圖那張一樣：Planetary Computer 渲染 API 出 Web Mercator 10 公尺圖（分塊抓再拼），放大兩倍、銳化，存 WebP。
   銳化參數是拿主圖的原尺寸版與兩倍版反推的（UnsharpMask 半徑 1.5～1.8、50～60%）。
   輸出 basemap/video/（不進 repo，約 5 MB）：<名>.webp ＋ <名>.json（Leaflet bounds），給 video/make_video.mjs --image 用。
   已存在就跳過，加 --force 重抓。需連網。

   python interactive-maps/tuvalu/build_video_basemap.py
"""
import io, json, math, pathlib, sys, time, urllib.request
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).parent
OUT = HERE / "basemap" / "video" / "s2_20260105_atoll_2x.webp"
ITEM = "S2B_MSIL2A_20260105T222759_R072_T60LYR_20260106T011006"
# 整個環礁，加上鏡頭從北端（⑪）飛到富納法拉（⑫）中途拉遠時看得到的範圍
W, S, E, N = 179.02, -8.74, 179.26, -8.36
RES = 10          # 公尺／像素（Web Mercator），跟主圖同一個格網大小
TILE = 1400       # 每塊最多幾像素（主圖一次 1113×1801 沒問題）
R = 20037508.342789244
API = "https://planetarycomputer.microsoft.com/api/data/v1/item/bbox"


def merc(lon, lat):
    return lon * R / 180, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R / math.pi


def lonlat(x, y):
    return x * 180 / R, math.degrees(2 * math.atan(math.exp(y * math.pi / R)) - math.pi / 2)


def fetch(x1, y1, x2, y2, w, h):
    url = (f"{API}/{x1},{y1},{x2},{y2}/{w}x{h}.png?collection=sentinel-2-l2a&item={ITEM}&assets=visual"
           "&coord_crs=epsg:3857&dst_crs=epsg:3857&reproject=lanczos")
    req = urllib.request.Request(url, headers={"User-Agent": "einfo-widgets-basemap/0.1"})   # 匿名：UA 只寫工具名
    return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=180).read())).convert("RGB")


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print("已存在，跳過：", OUT)
        return
    x1, y1 = merc(W, S)
    x2, y2 = merc(E, N)
    w, h = round((x2 - x1) / RES), round((y2 - y1) / RES)
    x2, y2 = x1 + w * RES, y1 + h * RES          # 對齊 10 公尺格網，分塊才拼得剛好
    nat = Image.new("RGB", (w, h))
    cols, rows = math.ceil(w / TILE), math.ceil(h / TILE)
    for r in range(rows):
        for c in range(cols):
            px1, px2 = c * w // cols, (c + 1) * w // cols
            py1, py2 = r * h // rows, (r + 1) * h // rows   # 影像的列從北往南
            tile = fetch(x1 + px1 * RES, y2 - py2 * RES, x1 + px2 * RES, y2 - py1 * RES, px2 - px1, py2 - py1)
            nat.paste(tile, (px1, py1))
            print(f"塊 {r * cols + c + 1}/{rows * cols}")
            time.sleep(1)   # 節流
    big = nat.resize((w * 2, h * 2), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    big.save(OUT, quality=85, method=4)
    (lon1, lat1), (lon2, lat2) = lonlat(x1, y1), lonlat(x2, y2)
    OUT.with_suffix(".json").write_text(json.dumps({
        "item": ITEM, "bounds": [[lat1, lon1], [lat2, lon2]],
        "attribution": "Contains modified Copernicus Sentinel data 2026"}, indent=1), encoding="utf-8")
    print("寫出", OUT, big.size, f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
