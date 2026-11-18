"""公投結果地圖：讀縣市界與公投結果 JSON，產生單一自足的 HTML（規格見 SPEC.md「公投地圖」）。

用法：
  python -I build_referendum.py                                      # data/referendum21_2025.json → referendum-2026.html
  python -I build_referendum.py --data data/referendum22_2026.json   # 開票夜：換成第 22 案的資料檔，網址不變
資料檔格式同 data/referendum21_2025.json：case 寫案號、簡稱、主文、投票日、投票權人總額（null＝22 縣市加總），
counties 寫各縣市的同意、不同意、投票數、投票權人數；margin、turnout 沒寫就自己算。
標題、出處日期、門檻都照資料檔，不另外改程式。版面與鏡頭照選舉地圖，不輪播；共用的投影與路徑從 build_map.py 拿。
"""
import argparse
import html
import json
import math
import os
import sys
from pathlib import Path
from urllib.parse import quote

import shapely
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python -I 不把腳本所在資料夾放進 sys.path
from build_map import FRAME_SOUTH_OF, HERE, ISLES, bbox, font_text, geom_d, polys, proj  # noqa: E402

DEFAULT_OUT = HERE / "referendum-2026.html"
# 五階：（同意－不同意）／投票數（含無效票）×100，刻度 -10、0、30、60（SPEC「公投地圖」）
TIERS = [("n2", "不同意多 10% 以上"), ("n1", "不同意多 10% 以內"), ("y1", "同意多 30% 以內"), ("y2", "同意多 30% 到 60%"), ("y3", "同意多 60% 以上")]


def tier(m):
    # 剛好 0（同意等於不同意）歸到 y1；真的遇到再說
    return "n2" if m <= -10 else "n1" if m < 0 else "y1" if m < 30 else "y2" if m < 60 else "y3"


def f(n):
    return f"{n:,}"


def p2(x):
    return f"{x:.2f}%"


def bar(agree, disagree, scale, th=None):
    """同意對不同意的長條；th＝門檻票數，畫一條刻度（長條的全長取兩者總和與門檻較大的那個，門檻才不會畫出框）"""
    h = f'<div class="bar" aria-hidden="true"><i class="ya" style="width:{agree / scale * 100:.2f}%"></i><i class="na" style="width:{disagree / scale * 100:.2f}%"></i>'
    if th is None:
        return h + "</div>"
    x = th / scale * 100
    side = f"right:{100 - x:.2f}%" if x >= 50 else f"left:{x:.2f}%"   # 字寫在刻度靠內的那邊，不出框
    return h + f'<b style="left:{x:.2f}%"></b></div><p class="thl"><span style="{side}">門檻 {f(th)} 票</span></p>'


def rows(agree, disagree):
    valid = agree + disagree
    return ("<ol>" + "".join(
        f'<li><i class="sw {k}" aria-hidden="true"></i><span class="nm">{n}</span><span class="v">{f(v)}</span><span class="pc">{p2(v / valid * 100)}</span></li>'
        for k, n, v in (("ya", "同意", agree), ("na", "不同意", disagree))) + "</ol>")


def gap_text(c, sep="，"):
    d = c["agree"] - c["disagree"]
    who = "同意多" if d >= 0 else "不同意多"
    return f"{who} {f(abs(d))} 票{sep}占投票數 {abs(c['margin']):.2f}%"


def county_card(c):
    gap = gap_text(c, "<i>（") + "）</i>"   # 括號那段不拆行，窄的卡片在括號前換行
    return (f"<h2>{c['name']}</h2>" + bar(c["agree"], c["disagree"], c["agree"] + c["disagree"]) + rows(c["agree"], c["disagree"])
            + f'<dl><dt>差距</dt><dd>{gap}</dd><dt>投票率</dt><dd>{p2(c["turnout"])}</dd></dl>')


def overview_card(n, case):
    if n["passed"]:
        res = '<em class="ok">通過</em>'
    else:
        why = [w for ok, w in ((n["agree"] > n["disagree"], "同意票沒有多於不同意票"), (n["agree"] >= n["threshold"], "同意票未達門檻")) if not ok]
        res = '<em class="no">未通過</em><span>' + "、".join(why) + "</span>"
    scale = max(n["agree"] + n["disagree"], n["threshold"])
    return (f'<h2>全國{res}</h2>'   # 簡稱與主文在標題下的副標（11-18 改，原本放在這裡）
            + bar(n["agree"], n["disagree"], scale, n["threshold"]) + rows(n["agree"], n["disagree"])
            + f'<p class="kv"><span>投票率 <b>{p2(n["turnout"])}</b></span><span class="m">門檻是投票權人總額的四分之一</span></p>'
            + '<p class="note"><span>地圖顏色＝（同意票－不同意票）</span><span>÷ 投票數（含無效票）</span></p>')   # 11-18 補色條說明；兩段各自不換行


def load(path, codes):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    case, errors, res = raw["case"], [], {}
    for k in ("no", "topic", "vote_date"):
        if not case.get(k):
            errors.append(f"case 少了 {k}")
    by_code = {c["code"]: c for c in raw["counties"]}
    missing, extra = codes - by_code.keys(), by_code.keys() - codes
    if missing or extra:
        errors.append(f"縣市代碼對不上：缺 {sorted(missing)}，多 {sorted(extra)}")
    for code, c in by_code.items():
        if c["agree"] + c["disagree"] != c["valid"]:
            errors.append(f"{c['name']}：同意加不同意 {c['agree'] + c['disagree']} 不等於有效票 {c['valid']}")
        m = round((c["agree"] - c["disagree"]) / c["votes_cast"] * 100, 2)
        if "margin" in c and abs(c["margin"] - m) > 0.005:
            errors.append(f"{c['name']}：資料的 margin {c['margin']} 跟算出來的 {m} 不同")
        res[code] = {"code": code, "name": c["name"], "agree": c["agree"], "disagree": c["disagree"], "margin": m,
                     "turnout": c.get("turnout") or round(c["votes_cast"] / c["electorate"] * 100, 2), "tier": tier(m)}
    s = lambda k: sum(c[k] for c in raw["counties"])
    elec = case.get("electorate") or s("electorate")   # 投票權人總額：中選會公告了就填在 case，沒填用 22 縣市加總
    n = {"agree": s("agree"), "disagree": s("disagree"), "threshold": math.ceil(elec / 4), "turnout": s("votes_cast") / elec * 100}
    n["passed"] = n["agree"] > n["disagree"] and n["agree"] >= n["threshold"]
    return case, res, n, raw["meta"], errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "data" / "referendum21_2025.json"))
    ap.add_argument("--counties", default=str(HERE / "data" / "counties.geojson"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    out = Path(a.out).resolve()

    gj = json.loads(Path(a.counties).read_text(encoding="utf-8"))
    geoms = {ft["properties"]["code"]: shape(ft["geometry"]) for ft in gj["features"]}
    case, res, nat, meta, errors = load(a.data, set(geoms))
    if errors:
        sys.exit("\n".join("錯誤：" + e for e in errors))

    def aria(c):
        return f"{c['name']}，{gap_text(c)}"

    # 以下的路徑、小地圖、點擊圓照 build_map.py main() 抄（那支已上線，不改它）
    order = sorted(geoms, key=lambda k: -geoms[k].representative_point().y)
    paths, defs, hits = [], [], []
    nss = 'vector-effect="non-scaling-stroke"'
    for code in order:
        g, c = geoms[code], res[code]
        if code in ISLES:
            continue
        d = geom_d(g)
        attrs = f'data-code="{code}" tabindex="0" role="button" aria-label="{aria(c)}"'
        ps = polys(g)
        main_ = max(ps, key=lambda p: p.area)
        isl = [p for p in ps if p is not main_]
        if code == "10016":
            body = f'<path id="p{code}" class="isl" {nss} d="{d}"/>'
        elif isl:
            body = f'<path id="p{code}" {nss} d="{geom_d(main_)}"/><path id="i{code}" class="isl" {nss} d="{geom_d(shapely.MultiPolygon(isl))}"/>'
        else:
            body = f'<path id="p{code}" {nss} d="{d}"/>'
        paths.append(f'<g class="cty g-{c["tier"]}" {attrs}>{body}</g>')
        if any(p.interiors for p in polys(g)):
            defs.append(f'<path id="o{code}" {nss} d="{geom_d(g, holes=False)}"/>')
        c["bbox"] = bbox(g)
        if code in FRAME_SOUTH_OF:
            c["bbox"] = bbox(shapely.MultiPolygon([p for p in polys(g) if p.representative_point().y < FRAME_SOUTH_OF[code]]))
        if code == "10016":
            hits.append(f'<path class="hit" data-code="{code}" d="{geom_d(g.convex_hull)}"/>')
        elif max(c["bbox"][2] - c["bbox"][0], c["bbox"][3] - c["bbox"][1]) < 600:
            x, y = proj(*g.representative_point().coords[0])
            hits.append(f'<circle class="hit dot" data-code="{code}" cx="{x}" cy="{y}" r="0"/>')
    for code in ISLES:
        ps = polys(geoms[code])
        big = max(p.area for p in ps)
        res[code]["bbox"] = bbox(shapely.MultiPolygon([p for p in ps if p.area >= big * 0.05]))
    pano = bbox(shapely.MultiPolygon([p for k in geoms if k not in ISLES for p in polys(geoms[k]) if p.area >= 0.0004]))

    def inset_vb(b):
        p = round(max(b[2] - b[0], b[3] - b[1]) * 0.08)
        return f"{b[0] - p} {b[1] - p} {b[2] - b[0] + 2 * p} {b[3] - b[1] + 2 * p}"
    isles = "".join(
        f'<div class="isle" data-code="{k}" tabindex="0" role="button" aria-label="{aria(res[k])}">'
        f'<svg viewBox="{inset_vb(res[k]["bbox"])}" preserveAspectRatio="xMidYMid meet">'
        f'<g class="lf"><path class="g-{res[k]["tier"]}" d="{geom_d(geoms[k])}"/></g></svg><span>{res[k]["name"]}</span></div>'
        for k in ("09007", "09020"))

    date = case["vote_date"]
    # 地圖上的標題不放簡稱（352.8 寬會斷成兩行），簡稱與主文寫在標題下的副標（11-18）；分頁標題與螢幕閱讀器的表放全名
    title = f"{date[:4]} 公投第 {case['no']} 案結果"
    sub = (f"<b>{html.escape(case['short'])}</b>：" if case.get("short") else "") + html.escape(case["topic"])
    full = f"{date[:4]} 公投第 {case['no']} 案" + (f"（{case['short']}）" if case.get("short") else "") + "結果"
    source = meta["source"].split()[0].replace("中央選舉委員會", "中央選舉委員會<wbr>")   # 網址不印；字太長時在機關名後換行
    cards = {"TW": overview_card(nat, case), **{k: county_card(c) for k, c in res.items()}}
    table = "".join(f'<tr><th scope="row">{c["name"]}</th><td>同意 {f(c["agree"])} 票，不同意 {f(c["disagree"])} 票，{gap_text(c)}，投票率 {p2(c["turnout"])}</td></tr>'
                    for c in (res[k] for k in order))
    data = {"counties": [{"code": c["code"], "tier": c["tier"], "bbox": c["bbox"]} for c in res.values()],
            "cards": cards, "pano": pano, "isles": sorted(ISLES)}
    page = (HERE / "referendum_template.html").read_text(encoding="utf-8")
    for k, v in {
        "TITLE_FULL": full, "TITLE": title, "SUB": sub,
        "LOGO": Path(os.path.relpath(HERE.parent / "assets" / "eic-logo-green.svg", out.parent)).as_posix(),
        "ISLES": isles, "DEFS": "".join(defs), "PATHS": "".join(paths), "HITS": "".join(hits),
        "SRC": f"{source} <i>{date} 投票</i>", "TABLE": table,
        "DATA": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    }.items():
        page = page.replace("{{" + k + "}}", v)
    page = page.replace("{{FONT_TEXT}}", quote(font_text(page), safe=""))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    for k in order:
        print(f"{k} {res[k]['name']} {res[k]['margin']:.2f} {res[k]['tier']}")
    print("五階縣市數：" + "、".join(f"{n} {sum(c['tier'] == t for c in res.values())}" for t, n in TIERS))
    print(f"全國 同意 {f(nat['agree'])} 不同意 {f(nat['disagree'])} 門檻 {f(nat['threshold'])} 投票率 {nat['turnout']:.2f}% {'通過' if nat['passed'] else '未通過'}")
    print(f"wrote {out}（{len(page.encode()) / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
