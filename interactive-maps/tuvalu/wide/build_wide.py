"""橫版的底圖與小地圖輪廓：把直版的 Sentinel-2 底圖轉 90 度（像素直接對調，不重新取樣），
環礁的 geojson 照 spots.py 的 rot() 換算。已存在就跳過，加 --force 重做。
用法：python interactive-maps/tuvalu/wide/build_wide.py"""
import importlib.util
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TALL = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("wide", os.path.join(HERE, "spots.py"))
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)
force = "--force" in sys.argv


def todo(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and not force:
        print("skip", path)
        return False
    return True


img = os.path.join(HERE, W.IMAGE["url"])
if todo(img):
    # ROTATE_270＝逆時針 270 度＝順時針 90 度，跟 rot() 同方向
    Image.open(os.path.join(TALL, W.B.IMAGE["url"])).transpose(Image.Transpose.ROTATE_270).save(img, quality=90, method=6)
    print("wrote", img, os.path.getsize(img) // 1024, "KB")


def rc(c):
    return [rc(x) for x in c] if isinstance(c[0], list) else list(reversed(W.rot(c[1], c[0])))


for name in W.INSET["layers"]:
    out = os.path.join(HERE, "boundaries", name)
    if todo(out):
        g = json.load(open(os.path.join(TALL, "boundaries", name), encoding="utf-8"))
        for f in g["features"]:
            f["geometry"]["coordinates"] = rc(f["geometry"]["coordinates"])
        json.dump(g, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        print("wrote", out)
