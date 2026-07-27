#!/usr/bin/env python3
"""抓真實圖磚、把 6 個景點座標畫上去存 PNG，用來肉眼核對座標是否正確。"""
import math, urllib.request, io
from PIL import Image, ImageDraw, ImageFont

spots = [
    (1, 35.997475, 139.8114455, "RYU-Q Kan"),
    (2, 36.0113203, 139.5091906, "Kitamoto"),
    (3, 35.7280647, 139.7070079, "Ikebukuro"),
    (4, 35.6349494, 139.7958032, "Rinkai"),
    (5, 35.5838724, 139.7603075, "Yacho"),
    (6, 35.7113, 139.8678, "Bousai Farm"),
]
Z = 12

def deg2xy(lat, lng, z):
    n = 2 ** z
    x = (lng + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y

xs = [deg2xy(s[1], s[2], Z)[0] for s in spots]
ys = [deg2xy(s[1], s[2], Z)[1] for s in spots]
xmin, xmax = math.floor(min(xs)) - 1, math.floor(max(xs)) + 1
ymin, ymax = math.floor(min(ys)) - 1, math.floor(max(ys)) + 1

W = (xmax - xmin + 1) * 256
H = (ymax - ymin + 1) * 256
canvas = Image.new("RGB", (W, H), (230, 230, 230))

for xt in range(xmin, xmax + 1):
    for yt in range(ymin, ymax + 1):
        url = f"https://a.basemaps.cartocdn.com/rastertiles/voyager/{Z}/{xt}/{yt}.png"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "map-verify/1.0"})
            data = urllib.request.urlopen(req, timeout=15).read()
            tile = Image.open(io.BytesIO(data)).convert("RGB")
            canvas.paste(tile, ((xt - xmin) * 256, (yt - ymin) * 256))
        except Exception as e:
            print("tile fail", xt, yt, e)

draw = ImageDraw.Draw(canvas)
ox, oy = xmin * 256, ymin * 256
for n, lat, lng, label in spots:
    gx, gy = deg2xy(lat, lng, Z)
    px, py = gx * 256 - ox, gy * 256 - oy
    r = 13
    draw.ellipse([px - r, py - r, px + r, py + r], fill=(220, 30, 60), outline="white", width=3)
    draw.text((px - 4, py - 7), str(n), fill="white")
    draw.text((px + r + 3, py - 6), f"{n} {label}", fill=(10, 10, 10))

out = r"C:\Users\shawn\AppData\Local\Temp\claude\C--Research-Lab\955dcd5e-2943-4739-8439-09aba45ba43a\scratchpad\map_check.png"
canvas.save(out)
print("saved", out, canvas.size)
