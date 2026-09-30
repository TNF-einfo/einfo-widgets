# -*- coding: utf-8 -*-
"""吐瓦魯・富納富提 橫版：地點與敘述跟直版同一份（讀 ../spots.py），整張圖順時針轉 90 度讓主島橫躺（北朝右）。
   座標、底圖、小地圖輪廓都照 rot() 換算成「轉過的經緯度」，產生器不必知道地圖轉過（只是多畫一個指北箭頭）。
   底圖與小地圖輪廓先跑 python interactive-maps/tuvalu/wide/build_wide.py，再跑 python template/gen_map.py tuvalu/wide。"""
import copy
import importlib.util
import math
import os

_spec = importlib.util.spec_from_file_location("tuvalu_tall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spots.py"))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

_R = 6378137.0
def merc(lat, lng): return math.radians(lng) * _R, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * _R
def unmerc(x, y): return math.degrees(2 * math.atan(math.exp(y / _R)) - math.pi / 2), math.degrees(x / _R)

(_s, _w), (_n, _e) = B.IMAGE["bounds"]
_x0, _y0 = merc(_s, _w)
_x1, _y1 = merc(_n, _e)
_cx, _cy = (_x0 + _x1) / 2, (_y0 + _y1) / 2   # 以直版底圖的中心為軸


def rot(lat, lng):
    """順時針轉 90 度（在 Web Mercator 平面上轉，形狀不變）：北→右、東→下，潟湖在上、外海在下。回傳 (lat, lng)。"""
    x, y = merc(lat, lng)
    return unmerc(_cx + (y - _cy), _cy - (x - _cx))


TITLE, MARK, CAT, ATTRIB = B.TITLE, B.MARK, B.CAT, B.ATTRIB
MAP_FILE = "tuvalu-map-wide.html"
ASPECT = "720/480"
# 主島南北 9 公里，橫放後寬度吃緊：左右只留 20～30px；上方那條潟湖留給說明卡、標題與圖例
FIT_PAD = {"desk": [30, 200, 30, 34], "small": [20, 180, 20, 30]}
CARD = "row"
NORTH = 90
INSET = B.INSET   # 輪廓讀本夾 boundaries/（build_wide.py 轉好的）
_hw, _hh = (_y1 - _y0) / 2, (_x1 - _x0) / 2   # 轉 90 度後寬高對調
IMAGE = dict(B.IMAGE, url="basemap/s2_20260105_2x_rot.webp",
             bounds=[list(unmerc(_cx - _hw, _cy - _hh)), list(unmerc(_cx + _hw, _cy + _hh))])

# 地名照直版換算；潟湖那個照換算會被圖例蓋到，改放島中段上方那塊空的潟湖（說明卡下緣與島之間、柯飛演講點左邊），座標是轉過的經緯度
_MOVED = {"富納富提潟湖": (-8.4868, 179.2115)}
PLACES = [dict(p, **dict(zip(("lat", "lng"), _MOVED.get(p["t"]) or rot(p["lat"], p["lng"])))) for p in B.PLACES]
SPOTS = []
for _sp in copy.deepcopy(B.SPOTS):
    _sp["lat"], _sp["lng"] = rot(_sp["lat"], _sp["lng"])
    _sp["img"] = "../" + _sp["img"]      # 照片跟直版共用 tuvalu/photos/
    _sp.pop("label", None)               # 直版手調的名字位置（左右上下）轉過之後不適用，先交給自動排
    _sp.pop("label_dy", None)
    SPOTS.append(_sp)

if __name__ == "__main__":   # 自我檢查：轉四次回到原點；正北的點轉到正右（經度變大、緯度不變）
    _p = (-8.5, 179.2)
    for _ in range(4):
        _p = rot(*_p)
    assert abs(_p[0] + 8.5) < 1e-9 and abs(_p[1] - 179.2) < 1e-9, _p
    _c = unmerc(_cx, _cy)
    _q = rot(_c[0] + 0.01, _c[1])
    assert _q[1] > _c[1] and abs(_q[0] - _c[0]) < 1e-9, _q
    print("ok")
