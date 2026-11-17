"""把國土測繪中心「直轄市、縣市界線(TWD97經緯度)」SHP 轉成地圖用的 GeoJSON，並量不同簡化程度的檔案大小。

讀 data/raw/nlsc_county_1140318/county_shp_1140318.zip（不解壓），寫 data/counties.geojson。
用法：python -I scripts/build_counties.py [容差（度），預設 0.002]
簡化用 shapely.coverage_simplify：相鄰縣市共用的邊界一起簡化，不會裂出縫或互相重疊。
東沙、南沙、釣魚臺落在下面的範圍外，不畫（環資 2025 年核三公投地圖也只畫本島、澎湖、金馬）。
"""
import json
import struct
import sys
import zipfile
from pathlib import Path

import shapely
from shapely.geometry import Polygon, box, mapping

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "data" / "raw" / "nlsc_county_1140318" / "county_shp_1140318.zip"
OUT = HERE / "data" / "counties.geojson"
NAME = "COUNTY_MOI_1140318"
CLIP = box(118.0, 21.8, 122.1, 26.5)  # 本島、澎湖、金門、馬祖、綠島、蘭嶼、龜山島、小琉球


def read_dbf(b):
    n, hlen, rlen = struct.unpack("<IHH", b[4:12])
    fields, off = [], 32
    while b[off] != 0x0D:
        fields.append((b[off:off + 11].split(b"\0")[0].decode(), b[off + 16]))
        off += 32
    rows = []
    for i in range(n):
        rec, pos = b[hlen + i * rlen + 1: hlen + (i + 1) * rlen], 0
        row = {}
        for name, ln in fields:
            row[name] = rec[pos:pos + ln].decode("utf-8").strip()
            pos += ln
        rows.append(row)
    return rows


def read_shp(b):
    out, off = [], 100
    while off < len(b):
        clen = struct.unpack(">i", b[off + 4:off + 8])[0] * 2
        rec = b[off + 8: off + 8 + clen]
        off += 8 + clen
        assert struct.unpack("<i", rec[:4])[0] == 5, "只處理 Polygon"
        nparts, npts = struct.unpack("<ii", rec[36:44])
        parts = list(struct.unpack(f"<{nparts}i", rec[44:44 + 4 * nparts])) + [npts]
        pts = struct.unpack(f"<{2 * npts}d", rec[44 + 4 * nparts: 44 + 4 * nparts + 16 * npts])
        rings = [list(zip(pts[2 * a:2 * c:2], pts[2 * a + 1:2 * c:2])) for a, c in zip(parts, parts[1:])]
        # SHP 外環順時針、內環（洞，例如嘉義縣包住的嘉義市）逆時針
        outer = [Polygon(r) for r in rings if not shapely.LinearRing(r).is_ccw]
        holes = [Polygon(r) for r in rings if shapely.LinearRing(r).is_ccw]
        g = shapely.union_all(outer)
        if holes:
            g = g.difference(shapely.union_all(holes))
        out.append(shapely.make_valid(g))
    return out


def to_geojson(names, geoms, digits=4):
    feats = []
    for (code, name), g in zip(names, geoms):
        geo = json.loads(json.dumps(mapping(g)), parse_float=lambda s: round(float(s), digits))
        feats.append({"type": "Feature", "properties": {"code": code, "name": name}, "geometry": geo})
    return json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":"))


def main():
    tol = float(sys.argv[1]) if len(sys.argv) > 1 else 0.002
    z = zipfile.ZipFile(SRC)
    rows = read_dbf(z.read(NAME + ".dbf"))
    geoms = [g.intersection(CLIP) for g in read_shp(z.read(NAME + ".shp"))]
    names = [(r["COUNTYCODE"], r["COUNTYNAME"]) for r in rows]
    assert len(names) == 22 and all(not g.is_empty for g in geoms), len(names)
    cec = {c["code"] for c in json.loads((HERE / "data" / "mayor_2022.json").read_text(encoding="utf-8"))["counties"]}
    assert {c for c, _ in names} == cec, "縣市代碼對不上中選會"

    print("容差(度)  頂點數  GeoJSON KB  gzip KB")
    import gzip
    for t in (0, 0.0005, 0.001, 0.002, 0.004):
        gs = list(shapely.coverage_simplify(geoms, t)) if t else geoms
        s = to_geojson(names, gs)
        nv = sum(shapely.get_num_coordinates(g) for g in gs)
        print(f"{t:<9} {nv:>7} {len(s.encode()) / 1024:>10.0f} {len(gzip.compress(s.encode())) / 1024:>8.0f}")
        if t == tol:
            assert all(g.is_valid for g in gs)
            OUT.write_text(s, encoding="utf-8")
    print("wrote", OUT.name, "tolerance", tol)


if __name__ == "__main__":
    main()
