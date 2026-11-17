"""2026 縣市長選舉當選地圖：讀縣市界、結果 JSON、政見金句 CSV，產生單一自足的 HTML（規格見 SPEC.md）。

用法：
  python -I build_map.py                                   # data/mayor_2022.json＋data/editorial_2022.csv → election-2026.html
  python -I build_map.py --data data/results_2026.json     # 開票夜：金句自動改讀 data/editorial.csv
  python -I build_map.py --editorial preview/editorial_test.csv --out preview/map.html     # 假引言只能出到 preview/
  python -I build_map.py --data data/worst_case.json --keep-going --out preview/worst.html   # 最壞資料，只在本機看
標題年份、出處日期、金句檔都照結果資料的投票日；金句只顯示當選者那一則，姓名要跟結果資料一字不差。
縣市界在建置時投影成 SVG（Web Mercator）內嵌，不載 Leaflet；鏡頭在頁面裡逐幀改 viewBox。
--keep-going 只給最壞資料看畫面用：不認得的政黨代碼照樣報錯，但不停下，該縣市畫成斜線並在資訊卡註明；不能寫到正式檔名。
"""
import argparse
import csv
import html
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import shapely
from shapely.geometry import shape

HERE = Path(__file__).resolve().parent
K = 2000          # 投影後每度經度 2000 單位：拉近臺北時一個螢幕像素約 2 單位，取整數不會看出鋸齒
LON0, LAT_TOP = 118.0, 26.6
SIX = ["63000", "65000", "68000", "66000", "67000", "64000"]   # 輪播順序：臺北、新北、桃園、臺中、臺南、高雄
ISLES = {"09020", "09007"}                                      # 金門、連江畫在左上角的小地圖
GROUP = {1: "kmt", 16: "dpp", 350: "tpp"}
SHORT = {"中國國民黨": "國民黨", "民主進步黨": "民進黨", "台灣民眾黨": "民眾黨", "無黨籍及未經政黨推薦": "無黨籍"}
STATUSES = {"pending", "counting", "called", "final", "postponed"}
DEFAULT_OUT = HERE / "election-2026.html"
EDITORIAL = {"2022": HERE / "data" / "editorial_2022.csv", "2026": HERE / "data" / "editorial.csv"}   # 公開版只讀當年當選者的金句


def merc(lat):
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


Y0 = merc(LAT_TOP)


def proj(lon, lat):
    return round((lon - LON0) * K), round((Y0 - merc(lat)) * K)


def ring_d(coords):
    pts = []
    for lon, lat in coords:
        p = proj(lon, lat)
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        return ""
    rel = " ".join(f"{x - px} {y - py}" for (px, py), (x, y) in zip(pts, pts[1:]))
    return f"M{pts[0][0]} {pts[0][1]}l{rel}z".replace(" -", "-")


def polys(g):
    return list(g.geoms) if g.geom_type == "MultiPolygon" else [g]


def geom_d(g, holes=True):
    out = []
    for p in polys(g):
        out.append(ring_d(p.exterior.coords))
        if holes:
            out += [ring_d(r.coords) for r in p.interiors]
    return "".join(out)


def bbox(g):
    x0, y0 = proj(g.bounds[0], g.bounds[3])
    x1, y1 = proj(g.bounds[2], g.bounds[1])
    return [x0, y0, x1, y1]


def fix_name(s):
    # 中選會把字型沒有的字寫成 @碼位@；轉回字元再 NFC（U+2F97F 相容字 → U+8070 聰）
    return unicodedata.normalize("NFC", re.sub(r"@([0-9A-Fa-f]+)@", lambda m: chr(int(m.group(1), 16)), s))


def load_results(path, party_table, codes, errors):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    by_code = {c["code"]: c for c in raw["counties"]}
    missing, extra = codes - by_code.keys(), by_code.keys() - codes
    if missing or extra:
        errors.append(f"縣市代碼對不上：缺 {sorted(missing)}，多 {sorted(extra)}")
    out = {}
    for code, c in by_code.items():
        status = c.get("status", "final")
        if status not in STATUSES:
            errors.append(f"{c['name']}：不認得的狀態 {status}")
        cands = sorted(c["candidates"], key=lambda p: -p["votes"])
        bad = False
        # 只查畫在地圖與資訊卡上的前兩名：代碼表缺 2022 年三個小黨（第 5、10 名），全查會擋掉真實資料
        for p in cands[:2]:
            pc = p.get("party_code")
            if pc is None or str(pc) not in party_table:
                errors.append(f"{c['name']} {p['name']}：政黨代碼 {pc}（{p['party']}）不在中選會政黨代碼表，不能默默塗灰")
                bad = True
        winners = [p for p in cands if p.get("elected")]
        if status in ("called", "final") and len(winners) != 1:
            errors.append(f"{c['name']}：狀態 {status} 但當選人數是 {len(winners)}")
            bad = True
        if len(cands) >= 2 and cands[0]["votes"] == cands[1]["votes"] and status in ("called", "final") and not c.get("note"):
            c["note"] = "同票，抽籤決定"
        if len(cands) == 1 and not c.get("note"):
            c["note"] = "同額競選"
        if status in ("counting", "called") and not (c.get("stations") and c.get("updated")):
            errors.append(f"{c['name']}：開票中要有 stations 與 updated")
        top = cands[:2]
        group = "pend"
        if status in ("called", "final") and not bad:
            group = GROUP.get(winners[0]["party_code"], "oth")
        out[code] = {
            "code": code, "name": c["name"], "six": code in SIX, "status": "error" if bad else status, "group": group,
            "stations": c.get("stations"), "updated": (c.get("updated") or "")[11:16],
            "note": html.escape(c.get("note") or ("政黨代碼不認得，產生器已報錯" if bad else "")),
            "vote_date": c.get("vote_date", ""),
            "cands": [{
                "name": html.escape(fix_name(p["name"])),
                "party": html.escape(SHORT.get(p["party"], p["party"])),
                "group": GROUP.get(p.get("party_code"), "oth"),
                "votes": p["votes"], "pct": p["pct"], "elected": bool(p.get("elected")) and status in ("called", "final"),
            } for p in top],
        }
    return out


def load_editorial(path, res, errors):
    if not path:
        return
    for row in csv.DictReader(open(path, encoding="utf-8-sig")):
        code, cand, text = row["code"].strip(), fix_name(row["candidate"].strip()), row["text"].strip()
        c = res.get(code)
        if not c or not c["six"]:
            errors.append(f"政見金句：{code} 不是六都")
            continue
        if len(text) > 60:
            print(f"警告：{c['name']} {cand} 的{row['kind']}有 {len(text)} 字，超過 60 字", file=sys.stderr)
        names = [html.unescape(p["name"]) for p in c["cands"]]
        if cand not in names:
            print(f"警告：{c['name']} 的「{cand}」對不到前兩名（{'、'.join(names)}），這則不顯示", file=sys.stderr)
            continue
        win = next((p for p in c["cands"] if p["elected"]), None)
        if win and html.unescape(win["name"]) == cand and text:
            c["quote"] = {"kind": html.escape(row["kind"].strip()), "text": html.escape(text), "source": html.escape(row["source"].strip())}


def summary(c):
    if c["status"] == "postponed":
        return "選舉延後"
    if c["status"] == "pending":
        return "尚未開票"
    parts = [f"{p['name']}（{p['party']}）{'當選，' if p['elected'] else ''}{p['votes']:,} 票，{p['pct']:.2f}%" for p in c["cands"]]
    pre = "開票中，" if c["status"] in ("counting", "called") else ""
    return pre + "；".join(parts)


def aria(c):
    win = next((p for p in c["cands"] if p["elected"]), None)
    if win:
        return f"{c['name']}，{win['name']}當選"
    return c["name"] + {"postponed": "，選舉延後", "pending": "，尚未開票"}.get(c["status"], "，開票中")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "data" / "mayor_2022.json"))
    ap.add_argument("--editorial", help="六都政見金句 CSV（格式照 data/editorial_template.csv）；不給就照資料年份讀 "
                    + "、".join(f"{y}→{p.relative_to(HERE).as_posix()}" for y, p in EDITORIAL.items()) + "，正式檔名只能用這份")
    ap.add_argument("--counties", default=str(HERE / "data" / "counties.geojson"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--keep-going", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    out = Path(a.out).resolve()
    if a.keep_going and out == DEFAULT_OUT:
        sys.exit("--keep-going 不能寫到正式檔名，請用 --out 指到 preview/")

    gj = json.loads(Path(a.counties).read_text(encoding="utf-8"))
    geoms = {f["properties"]["code"]: shape(f["geometry"]) for f in gj["features"]}
    party_table = {p["party_code"] for p in json.loads((HERE / "data/raw/cec_db/webs_configs_party_colors.json").read_text(encoding="utf-8"))}
    errors = []
    res = load_results(a.data, party_table, set(geoms), errors)
    # 標題、出處日期、金句檔都跟著結果資料的投票日走（嘉義市 2022 年另有重行選舉日）
    dates = Counter(c["vote_date"] for c in res.values() if c["vote_date"])
    date = dates.most_common(1)[0][0] if dates else ""
    year = date[:4]
    own = EDITORIAL.get(year)
    if out == DEFAULT_OUT and a.editorial and Path(a.editorial).resolve() != own:
        sys.exit(f"正式檔名的金句只能讀 {own}：測試用的假引言不能掛在真人名下公開，請用 --out 指到 preview/")
    a.editorial = a.editorial or (own and str(own))
    if not a.editorial or not Path(a.editorial).exists():
        print(f"警告：沒有 {a.editorial}，不放政見金句", file=sys.stderr)
        a.editorial = None
    load_editorial(a.editorial, res, errors)
    if errors:
        print("\n".join("錯誤：" + e for e in errors), file=sys.stderr)
        if not a.keep_going:
            sys.exit(1)

    # 縣市依中心由北到南排（Tab 順序）；金門、連江只放 defs 給小地圖用
    order = sorted(geoms, key=lambda k: -geoms[k].representative_point().y)
    paths, defs, hits = [], [], []
    for code in order:
        g, c = geoms[code], res[code]
        d = geom_d(g)
        attrs = f'data-code="{code}" tabindex="0" role="button" aria-label="{aria(c)}"'
        if code in ISLES:
            # 小地圖用 <use> 複製，CSS 的 vector-effect 不會跟過去，要寫成屬性外緣才是 2px
            defs.append(f'<path id="p{code}" vector-effect="non-scaling-stroke" d="{d}"/>')
            continue
        paths.append(f'<g class="cty g-{c["group"]}" {attrs}><path id="p{code}" d="{d}"/></g>')
        if any(p.interiors for p in polys(g)):   # 外緣只框自己（新北不框到臺北、嘉義縣不框到嘉義市）
            defs.append(f'<path id="o{code}" d="{geom_d(g, holes=False)}"/>')
        c["bbox"] = bbox(g)
        if code == "10016":   # 澎湖：點群島範圍
            hits.append(f'<path class="hit" data-code="{code}" d="{geom_d(g.convex_hull)}"/>')
        elif max(c["bbox"][2] - c["bbox"][0], c["bbox"][3] - c["bbox"][1]) < 600:   # 小縣市加看不見的點擊圓，半徑逐幀換算成 22px
            x, y = proj(*g.representative_point().coords[0])
            hits.append(f'<circle class="hit dot" data-code="{code}" cx="{x}" cy="{y}" r="0"/>')
    # 取景只看夠大的島：金門的烏坵、北邊的彭佳嶼這種小點會把畫面撐大（它們照樣畫在圖上）
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
        f'<use href="#p{k}" class="g-{res[k]["group"]}"/><use href="#p{k}" class="iol"/></svg><span>{res[k]["name"]}</span></div>'
        for k in ("09007", "09020"))

    groups = [c["group"] for c in res.values()]
    title = f"{year} 縣市長選舉結果"
    live = any(c["status"] in ("counting", "called", "pending") for c in res.values())
    times = sorted(c["updated"] for c in res.values() if c["updated"])
    src_date = f"<i>{date}</i> 開票中，資料時間 {times[-1]}" if live and times else f"<i>{date}</i> 開票結果"
    src_date += "".join(f"（{c['name']} <i>{c['vote_date']}</i> 重行選舉）" for c in res.values() if c["vote_date"] not in ("", date))
    legend = [("kmt", "國民黨"), ("dpp", "民進黨"), ("tpp", "民眾黨"), ("oth", "其他")]
    if "pend" in groups:   # 斜線圖例照實際出現的狀態寫，延後的嘉義市不會被寫成「開票中」
        st = {c["status"] for c in res.values() if c["group"] == "pend"}
        legend.append(("pend", "、".join(dict.fromkeys(n for s, n in (("pending", "未開票"), ("counting", "開票中"), ("error", "開票中"), ("postponed", "延後")) if s in st))))
    table = "".join(f"<tr><th scope=\"row\">{c['name']}</th><td>{summary(c)}</td></tr>" for c in (res[k] for k in order))
    font_text = "".join(sorted(set(title)))

    data = {"counties": list(res.values()), "pano": pano, "six": SIX, "isles": sorted(ISLES), "date": date}
    page = (HERE / "map_template.html").read_text(encoding="utf-8")
    for k, v in {
        "TITLE": title, "FONT_TEXT": font_text.replace(" ", "%20"),
        "LOGO": Path(__import__("os").path.relpath(HERE.parent / "assets" / "eic-logo.png", out.parent)).as_posix(),
        "LEGEND": "".join(f'<li><i class="sw g-{g}"></i>{n}</li>' for g, n in legend),
        "ISLES": isles, "DEFS": "".join(defs), "PATHS": "".join(paths), "HITS": "".join(hits),
        "SRC_DATE": src_date, "TABLE": table,
        "DATA": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    }.items():
        page = page.replace("{{" + k + "}}", v)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    for k in order:
        print(f"{k} {res[k]['name']} {res[k]['group']}")
    print(f"wrote {out}（{len(page.encode()) / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
