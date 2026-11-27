"""2026 縣市長選舉當選地圖：讀縣市界、結果 JSON、當選人標籤 CSV，產生單一自足的 HTML（規格見 SPEC.md）。

用法：
  python -I build_map.py                                   # data/mayor_2022.json → election-2026.html（2022 沒有標籤檔，不顯示標籤）
  python -I build_map.py --data data/results_2026.json     # 開票夜：投票日是 2026，標籤改讀 data/tags.csv
  python -I build_map.py --data data/worst_case.json --keep-going --out preview/worst.html   # 最壞資料，只在本機看
  python -I build_map.py --theme night --out preview/map_night.html   # 深藍灰底的對照主題（預設 paper 淺底）
  python -I build_map.py --home [--data …]                 # 首頁「關鍵圖表」的 16:9 版 → election-2026-home.html（SPEC「首頁版」）
  python -I build_map.py --home --live-json live.json [--epoch 2026-11-28] [--seq N] [--poll-s 60]
                                                           # 首頁版另寫輪詢用的 live.json（SPEC「首頁版即時更新」），頁面烤進同一組 epoch、seq、published_at
標題年份、出處日期、標籤檔都照結果資料的投票日；標籤只顯示在當選人那一列下面，姓名要跟結果資料一字不差。
縣市界在建置時投影成 SVG（Web Mercator）內嵌，不載 Leaflet；鏡頭在頁面裡逐幀改 viewBox。
--keep-going 只給最壞資料看畫面用：不認得的政黨代碼照樣報錯，但不停下，該縣市畫成斜線並在資訊卡註明；不能寫到正式檔名。
"""
import argparse
import csv
import html
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import shapely
from shapely.geometry import shape

HERE = Path(__file__).resolve().parent
K = 2000          # 投影後每度經度 2000 單位：拉近臺北時一個螢幕像素約 2 單位，取整數不會看出鋸齒
LON0, LAT_TOP = 118.0, 26.6
SIX = ["63000", "65000", "68000", "66000", "67000", "64000"]   # 輪播順序：臺北、新北、桃園、臺中、臺南、高雄
ISLES = {"09020", "09007"}                                      # 金門、連江畫在左上角的小地圖
FRAME_SOUTH_OF = {"10017": 25.3}   # 拉近取景只算這個緯度以南：基隆的彭佳嶼、棉花嶼、花瓶嶼離本島 30 到 60 公里，算進去基隆會縮成一小塊
GROUP = {1: "kmt", 16: "dpp", 350: "tpp"}
SHORT = {"中國國民黨": "國民黨", "民主進步黨": "民進黨", "台灣民眾黨": "民眾黨", "無黨籍及未經政黨推薦": "無黨籍",
         "時代力量": "時力", "台灣基進": "基進", "台灣團結聯盟": "台聯", "社會民主黨": "社民黨"}
# 資訊卡的政黨徽章：簡稱的第一個字；民眾黨的「民」會跟民進黨撞，另寫「眾」。表裡沒有的政黨用中選會全名的第一個字
BADGE = {"台灣民眾黨": "眾"}
# 開票後才會出現的字（fetch_live 與這支寫的註記、出處、報讀文字）：首頁版 10:00 那版就要收進字型子集
LATE_TEXT = "同票，抽籤決定未達最低當選票數同額競選尚無當選人選舉延後尚未開票開票中開票結果資料時間重行選舉政黨代碼不認得產生器已報錯（），、；：0123456789%"


def short(party):   # 開票頁可能寫「臺灣民眾黨」：簡稱與徽章用「台」的寫法查（11-27）
    return SHORT.get(party) or SHORT.get(party.replace("臺", "台"), party)


def badge(party):
    return BADGE.get(party) or BADGE.get(party.replace("臺", "台")) or short(party)[:1]   # 政黨空白時給空徽章，不掛掉（fetch_live 轉 JSON 時也會擋）
STATUSES = {"pending", "counting", "called", "final", "postponed"}
DEFAULT_OUT = HERE / "election-2026.html"
HOME_OUT = HERE / "election-2026-home.html"   # 首頁「關鍵圖表」的 16:9 版（--home，SPEC「首頁版」）
TAGS = {"2026": HERE / "data" / "tags.csv"}   # 當選人的環境政見標籤，只有 2026 有；2022 版沒有檔就不顯示
TAG_KEYS = "ygpb"                              # 標籤四色：黃、綠、粉、藍（CSS 的 --tag-y/g/p/b）
TAG_FIXED = {"防災型都更": "p"}                 # 固定粉色；其餘照 tags.csv 第一次出現的順序輪流配色


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
        # 只查前兩名（決定顏色與當選）：第 3 名以後的小黨可能不在代碼表，塗灰、照中選會名稱顯示，不報錯
        for p in cands[:2]:
            pc = p.get("party_code")
            if pc is None or str(pc) not in party_table:
                errors.append(f"{c['name']} {p['name']}：政黨代碼 {pc}（{p['party']}）不在中選會政黨代碼表，不能默默塗灰")
                bad = True
        # 只在開完時補：開票中兩人同票（例如 force 在 0 比 0 時套用）不是抽籤（11-27）
        if len(cands) >= 2 and cands[0]["votes"] == cands[1]["votes"] and status == "final" and not c.get("note"):
            c["note"] = "同票，抽籤決定"
        winners = [p for p in cands if p.get("elected")]
        # 開完卻沒有當選人（同票待抽籤、未達最低當選票數）要有說明，照樣畫斜線
        if status in ("called", "final") and len(winners) != 1 and not (status == "final" and not winners and c.get("note")):
            errors.append(f"{c['name']}：狀態 {status} 但當選人數是 {len(winners)}")
            bad = True
        if len(cands) == 1 and not c.get("note"):
            c["note"] = "同額競選"
        if status in ("counting", "called") and not (c.get("stations") and c.get("updated")):
            errors.append(f"{c['name']}：開票中要有 stations 與 updated")
        group = "pend"
        if status in ("called", "final") and winners and not bad:
            group = GROUP.get(winners[0]["party_code"], "oth")
        out[code] = {
            "code": code, "name": c["name"], "six": code in SIX, "status": "error" if bad else status, "group": group,
            "stations": c.get("stations"), "updated": c.get("updated") or "",   # 先留完整時間給出處列比，main() 再裁成 HH:MM
            "note": html.escape(c.get("note") or ("政黨代碼不認得，產生器已報錯" if bad else "")),
            "vote_date": c.get("vote_date", ""),
            "cands": [{
                "name": html.escape(fix_name(p["name"])),
                "party": html.escape(short(p["party"])), "badge": html.escape(badge(p["party"])),
                "group": GROUP.get(p.get("party_code"), "oth"),
                "votes": p["votes"], "pct": p["pct"], "elected": bool(p.get("elected")) and status in ("called", "final"),
            } for p in cands],
        }
    return out


def tag_colors(lists):
    """標籤文字 → 色鍵：同一項政策每個縣市同一色；依第一次出現的順序輪流配色，盡量不跟同一列相鄰的標籤同色"""
    col, i = dict(TAG_FIXED), 0
    for ts in lists:
        for j, t in enumerate(ts):
            if t in col:
                continue
            near = {col.get(ts[k]) for k in (j - 1, j + 1) if 0 <= k < len(ts)}
            for s in range(len(TAG_KEYS)):
                k = TAG_KEYS[(i + s) % len(TAG_KEYS)]
                if k not in near:
                    break
            col[t] = k
            i = (i + s + 1) % len(TAG_KEYS)
    return col


def load_tags(path, res, errors):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    lists = [[t.strip() for t in r["tags"].split("、") if t.strip()] for r in rows]
    col = tag_colors(lists)
    clash = sum(col[a] == col[b] for ts in lists for a, b in zip(ts, ts[1:]))
    if clash:
        print(f"注意：標籤有 {clash} 組相鄰同色（同一項政策同一色，配不開）", file=sys.stderr)
    fake = {}   # 公開測試頁的假名字（候選人甲…）對不到真名：改放同樣個數、同樣顏色的「測試標籤」，真的政見一看就認得出是誰
    for row, ts in zip(rows, lists):
        code, cand = row["code"].strip(), fix_name(row["candidate"].strip())
        c = res.get(code)
        if not c:
            errors.append(f"標籤：{code} 對不到縣市")
            continue
        names = [html.unescape(p["name"]) for p in c["cands"]]
        if not names:   # 還沒有候選人名單（開票夜手動輸入、還沒抄的縣市）：沒得對，也不報
            continue
        if all(n.startswith("候選人") for n in names):   # 縣內兩人的標籤取比較多的那份，版面照最擠的測
            if len(ts) > len(fake.get(code, [])):
                fake[code] = ts
            continue
        if cand not in names:   # 表裡列全部候選人，只有姓名打錯才報；沒當選的照樣不顯示
            print(f"警告：{c['name']} 的「{cand}」對不到候選人名單（{'、'.join(names)}），這列標籤不顯示", file=sys.stderr)
            continue
        win = next((p for p in c["cands"] if p["elected"]), None)
        if win and html.unescape(win["name"]) == cand and ts:
            c["tags"] = [{"t": html.escape(t), "k": col[t]} for t in ts]
    for code, ts in fake.items():
        c = res[code]
        if any(p["elected"] for p in c["cands"]):
            c["tags"] = [{"t": f"測試標籤{'一二三四五六七八'[i]}", "k": col[t]} for i, t in enumerate(ts)]


def font_text(page):
    """網頁字體 text= 要載的字：頁面上所有非 ASCII 字（資料、資訊卡與按鈕的字串都在頁面裡），扣掉註解；ASCII 可見字元全收。
    shortcut: 程式碼字串裡不會顯示的中文也會收進來，多載幾個字而已；URL 太長被 Google Fonts 拒絕時再改成逐欄收集"""
    page = re.sub(r"<!--.*?-->|/\*.*?\*/|(?<![:\"'])//[^\n]*", "", page, flags=re.S)
    return "".join(sorted({ch for ch in page if ord(ch) > 0x7e} | set(map(chr, range(0x21, 0x7f)))))


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
    return c["name"] + {"postponed": "，選舉延後", "pending": "，尚未開票", "final": f"，{c['note'] or '尚無當選人'}"}.get(c["status"], "，開票中")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "data" / "mayor_2022.json"))
    ap.add_argument("--counties", default=str(HERE / "data" / "counties.geojson"))
    ap.add_argument("--out")
    ap.add_argument("--keep-going", action="store_true")
    ap.add_argument("--theme", choices=["paper", "night"], default="paper",
                    help="配色主題（SPEC「配色」）：paper 淺底（推薦、正式檔用這套），night 深藍灰底（對照）")
    ap.add_argument("--home", action="store_true",
                    help="首頁版：沒有標題、logo 與最下面那行，圖例、按鈕、卡片在右欄（預設寫 election-2026-home.html）")
    ap.add_argument("--live-json", help="首頁版：另寫輪詢用的 live.json（內容就是頁面烤進去的那包資料）")
    ap.add_argument("--epoch", help="首頁版：這一晚的名字，頁面只收同一個 epoch 的 live.json（預設是投票日；彩排用 rehearsal）")
    ap.add_argument("--seq", type=int, help="首頁版：發佈序號（預設現在的 Unix 秒數），也是 published_at")
    ap.add_argument("--poll-s", type=int, help="首頁版：讀者多久抓一次 live.json（預設 20）；0 是停止開關")
    ap.add_argument("--fast-url", help="首頁版：快車道的 live.json 網址（Funnel 上這台電腦給的），頁面先抓這裡、抓不到退回 Pages；不給或空字串就不用")
    ap.add_argument("--test-banner", action="store_true", help="頁面頂端加紅色「測試資料，非真實結果」、不讓搜尋引擎收錄（彩排用）")
    a = ap.parse_args()
    if a.live_json and not a.home:
        sys.exit("--live-json 只給首頁版（--home）用：輪詢只在首頁版")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    out = Path(a.out or (HOME_OUT if a.home else DEFAULT_OUT)).resolve()
    if a.keep_going and out in (DEFAULT_OUT, HOME_OUT):
        sys.exit("--keep-going 不能寫到正式檔名，請用 --out 指到 preview/")

    gj = json.loads(Path(a.counties).read_text(encoding="utf-8"))
    geoms = {f["properties"]["code"]: shape(f["geometry"]) for f in gj["features"]}
    # 2022 的中選會代碼表，加上 2026 才出現的小黨（data/party_codes_2026.json，代碼自訂；不在 GROUP 裡就塗灰）
    party_table = {str(p["party_code"]) for f in ("data/raw/cec_db/webs_configs_party_colors.json", "data/party_codes_2026.json")
                   for p in json.loads((HERE / f).read_text(encoding="utf-8"))}
    errors = []
    res = load_results(a.data, party_table, set(geoms), errors)
    # 標題、出處日期、標籤檔都跟著結果資料的投票日走（嘉義市 2022 年另有重行選舉日）
    dates = Counter(c["vote_date"] for c in res.values() if c["vote_date"])
    date = dates.most_common(1)[0][0] if dates else ""
    year = date[:4]
    if year in TAGS:   # 2022 沒有標籤檔，直接不放
        if TAGS[year].exists():
            load_tags(TAGS[year], res, errors)
        else:
            print(f"警告：沒有 {TAGS[year]}，不放標籤", file=sys.stderr)
    if errors:
        print("\n".join("錯誤：" + e for e in errors), file=sys.stderr)
        if not a.keep_going:
            sys.exit(1)

    # 縣市依中心由北到南排（Tab 順序）；金門、連江只放 defs 給小地圖用
    order = sorted(geoms, key=lambda k: -geoms[k].representative_point().y)
    paths, defs, hits = [], [], []
    # 線寬不跟著縮放：CSS 已經寫了，屬性再寫一次給不吃 CSS 的工具（外緣、浮起的板子在頁面裡複製 d，不用 <use>）
    nss = 'vector-effect="non-scaling-stroke"'
    for code in order:
        g, c = geoms[code], res[code]
        d = geom_d(g)
        attrs = f'data-code="{code}" tabindex="0" role="button" aria-label="{aria(c)}"'
        if code in ISLES:   # 金門、連江只畫在左上角的小地圖（下面的 isles）
            continue
        # 離島不畫白邊，浮起時也不框（11-18）：澎湖整個是 isl；其他縣市的 p 只放本島（連內環），
        # 綠島、蘭嶼、小琉球、龜山島、基隆外海小島放另一條 i、標 isl。浮起的板子用 p＋i，白色外框只用 p
        ps = polys(g)   # 只取一次：g.geoms 每次都產生新物件，分兩次取的話下面的 is 比對永遠不成立
        main = max(ps, key=lambda p: p.area)
        isl = [p for p in ps if p is not main]
        assert len(isl) == len(ps) - 1
        if code == "10016":
            body = f'<path id="p{code}" class="isl" {nss} d="{d}"/>'
        elif isl:
            body = f'<path id="p{code}" {nss} d="{geom_d(main)}"/><path id="i{code}" class="isl" {nss} d="{geom_d(shapely.MultiPolygon(isl))}"/>'
        else:
            body = f'<path id="p{code}" {nss} d="{d}"/>'
        paths.append(f'<g class="cty g-{c["group"]}" {attrs}>{body}</g>')
        if any(p.interiors for p in polys(g)):   # 外緣只框自己（新北不框到臺北、嘉義縣不框到嘉義市）
            defs.append(f'<path id="o{code}" {nss} d="{geom_d(g, holes=False)}"/>')
        c["bbox"] = bbox(g)
        if code in FRAME_SOUTH_OF:   # 拉近取景不算外海小島（島照樣畫）
            c["bbox"] = bbox(shapely.MultiPolygon([p for p in polys(g) if p.representative_point().y < FRAME_SOUTH_OF[code]]))
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
        f'<g class="lf"><path class="g-{res[k]["group"]}" d="{geom_d(geoms[k])}"/></g></svg><span>{res[k]["name"]}</span></div>'
        for k in ("09007", "09020"))

    groups = [c["group"] for c in res.values()]
    title = f"{year}九合一縣市長政黨版圖"   # 11-27 編輯定的大標
    live = any(c["status"] in ("counting", "called", "pending") for c in res.values())
    # 跨午夜要比完整的日期時間，最後才取 HH:MM（11-29 00:15 比 11-28 23:50 新）
    times = sorted(c["updated"] for c in res.values() if c["updated"])
    for c in res.values():
        c["updated"] = c["updated"][11:16]
    # 每個詞包一個不換行的 <i>：只在詞與詞之間換行，不會斷成「重行選／舉）」（平板 528 直式看到的，11-18）；
    # 整段包起來的話手機會多一行
    # 還沒有縣市開票（10:00 換版後到開票前、延後的不算）寫「尚未開票」；有縣市開了、還沒全部開完寫「開票中」（11-27：原本全部未開票時寫成「開票結果」）
    begun = any(c["status"] in ("counting", "called", "final") for c in res.values())
    if not begun:
        src_date = f"<i>{date}</i> <i>尚未開票</i>"
    elif live:
        src_date = f"<i>{date}</i> <i>開票中</i>" + (f"，<i>資料時間 {times[-1][11:16]}</i>" if times else "")
    else:
        src_date = f"<i>{date}</i> <i>開票結果</i>"
    src_date += "".join(f"<i>（{c['name']}</i> <i>{c['vote_date']}</i> <i>重行選舉）</i>" for c in res.values() if c["vote_date"] not in ("", date))
    legend = [("kmt", "國民黨"), ("dpp", "民進黨"), ("tpp", "民眾黨"), ("oth", "其他")]
    if "pend" in groups:   # 斜線圖例照實際出現的狀態寫，延後的嘉義市不會被寫成「開票中」
        st = {c["status"] for c in res.values() if c["group"] == "pend"}
        legend.append(("pend", "、".join(dict.fromkeys(n for s, n in (("pending", "未開票"), ("counting", "開票中"), ("error", "開票中"), ("final", "尚無當選人"), ("postponed", "延後")) if s in st))))
    n = Counter(groups)   # 首頁版的圖例在名稱後寫縣市數（22 縣市，含金門、連江）
    # 首頁版圖例的「各陣營領先狀況」：寬框是最上面的小標題，手機框由 CSS 排到右下角（11-27 主編定稿：數字照舊只算已當選）
    legend_of = lambda home: ('<li class="lgh">各陣營領先狀況</li>' if home else "") + \
        "".join(f'<li><i class="sw g-{g}"></i>{name}' + (f'<b class="n">{n[g]}</b>' if home else "") + "</li>" for g, name in legend)
    table = "".join(f"<tr><th scope=\"row\">{c['name']}</th><td>{summary(c)}</td></tr>" for c in (res[k] for k in order))
    src = src_date   # 11-27：出處、縣市界、製圖與免責聲明改寫在文章嵌入區塊的說明欄，圖裡只留開票狀態與資料時間
    data = {"counties": list(res.values()), "pano": pano, "six": SIX, "isles": sorted(ISLES), "date": date}
    extra = ""
    if a.home:   # 首頁版會輪詢：頁面與 live.json 烤同一組 epoch、seq、published_at（SPEC「首頁版即時更新」）
        seq = a.seq or int(time.time())
        data.update(epoch=a.epoch or date, seq=seq, published_at=seq, poll_s=a.poll_s, fast_url=a.fast_url or "")
        # 首頁版的資料時間：圖例下面那行小字；全部未開票時是空的
        data["dtime"] = f"資料時間 {times[-1][11:16]}" if times and begun else ""
        # 字型另收 2026 全部候選人與標籤：10:00 發的全是未開票，名字晚上才從 live.json 進來；
        # 產生器自己寫的字（註記、出處、報讀）也只在開票後才出現，一起收，不然晚上那幾個字會換成系統字型（11-27）
        extra = "".join(p.read_text(encoding="utf-8-sig") for p in (HERE / "data/candidates_2026.csv", TAGS["2026"]) if p.exists())
        extra += LATE_TEXT + "".join(SHORT.values()) + "".join(BADGE.values())
    page = (HERE / "map_template.html").read_text(encoding="utf-8")
    logo = {"paper": "eic-logo-green.svg", "night": "eic-logo.png"}[a.theme]   # 淺底用官網表頭的綠色 logo，深底用白色那張
    for k, v in {
        "THEME": a.theme, "TITLE": title, "VARIANT": "home" if a.home else "",
        # 標題太長時只在「九合一」後面換行，手機直式才不會剩一個「圖」掉到第二行
        "TITLE_H1": f"<span>{year}九合一</span><span>縣市長政黨版圖</span>",
        "LOGO": Path(os.path.relpath(HERE.parent / "assets" / logo, out.parent)).as_posix(),
        # 首頁版的放大鈕連到文章版（同一份資料夾的正式檔）；帶發佈序號，手機另開時不吃 CDN 與瀏覽器 10 分鐘的快取（11-27）
        "FULL": Path(os.path.relpath(DEFAULT_OUT, out.parent)).as_posix() + (f"?v={data['seq']}" if data.get("seq") else ""),
        "LEGEND": legend_of(a.home),
        "ISLES": isles, "DEFS": "".join(defs), "PATHS": "".join(paths), "HITS": "".join(hits),
        "SRC": src, "TABLE": table,
        "DATA": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    }.items():
        page = page.replace("{{" + k + "}}", v)
    if a.test_banner:   # 彩排的假資料：截圖外流也看得出是假的
        page = page.replace("</head>", '<meta name="robots" content="noindex,nofollow"></head>', 1).replace("<body>", (
            '<body><div style="position:fixed;top:0;left:50%;transform:translateX(-50%);z-index:99;background:#c0392b;color:#fff;'
            'font:700 13px/1.2 \'Noto Sans TC\',sans-serif;padding:5px 12px;border-radius:0 0 6px 6px;pointer-events:none">測試資料，非真實結果</div>'), 1)
    page = page.replace("{{FONT_TEXT}}", quote(font_text(page + extra), safe=""))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    if a.live_json:   # 輪詢用的那包：就是烤進頁面的資料，加上頁面要換的字串；顏色、標籤、註記都在這裡算好，頁面只換上去
        live = {"schema": 1, **{k: data[k] for k in ("epoch", "seq", "poll_s", "published_at", "counties", "dtime", "fast_url")},
                "aria": {k: aria(c) for k, c in res.items()}, "legend": legend_of(False), "legend_home": legend_of(True),
                "src": src, "table": table}
        Path(a.live_json).write_text(json.dumps(live, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        print(f"wrote {Path(a.live_json).resolve()}（seq {data['seq']}）")
    for k in order:
        print(f"{k} {res[k]['name']} {res[k]['group']}")
    print(f"wrote {out}（{len(page.encode()) / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
