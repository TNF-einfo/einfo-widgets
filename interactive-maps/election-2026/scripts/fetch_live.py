"""開票夜的資料：中選會開票網頁或手動抄的 CSV → 地圖用的 JSON（規格見 SPEC.md「開票當晚」）。

用法（在 election-2026 資料夾跑）：
  python -I scripts/fetch_live.py mayor-web <網址前綴>   # 主方案：22 縣市各抓一頁 → data/results_2026.csv → data/results_2026.json
  python -I scripts/fetch_live.py ref-web <網址前綴>     # 公投：同上 → data/referendum22_2026.csv → data/referendum22_2026.json
  python -I scripts/fetch_live.py mayor-csv [CSV]        # 備案一：手動抄的 CSV（預設 data/results_2026.csv）→ JSON
  python -I scripts/fetch_live.py ref-csv [CSV]          # 公投的手動 CSV（預設 data/referendum22_2026.csv）→ JSON
  python -I scripts/fetch_live.py selftest               # 用 2022 的開票頁與資料庫數字自我測試，產出只寫到 preview/
網址前綴＝開票頁讀縣市結果的網址去掉最後的區域碼。2022 年縣市長是 https://www.cec.gov.tw/zh-TW/TC，
頁面是 {前綴}/{縣市代碼}000000000000.html；2024、2025 年的開票頁也是這個規則，前綴開票當天從開票頁的網路請求看。
有人宣布當選、中選會還沒打 ◎：在 data/declared.csv（code,candidate）加一列再抓，地圖蓋章加「開票中」。
抓網頁時一縣一縣檢查：沒抓到、解析失敗、沒過檢查或比上一輪倒退的縣市沿用 CSV 裡上一輪的那列（第一輪補範本的未開票），
其他縣市照常更新；手動設的 postponed 不抓（規則見 SPEC「開票夜防呆」）。請求匿名（User-Agent 只寫用途），每頁間隔 3 秒，
原始頁存 data/raw/cec_live_2026/（收下的才存，沒收的存成 *_bad.html）。公投頁的表格 2025 年的存檔沒有抓到，解析是照表頭的字猜的，當天要先看一頁對過。
"""
import argparse
import csv
import functools
import http.server
import io
import json
import math
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
UA = "einfo-election-map/0.1"   # 只寫用途、不放聯絡方式（.claude/rules/crawlers.md）
DELAY = 3.0
DATE = "2026-11-28"
SOURCE = "中央選舉委員會開票網站"   # 公投地圖的出處列取第一個詞，不寫網址與輸入方式
STATUSES = ("pending", "counting", "called", "final", "postponed")
RANK = {"pending": 0, "counting": 1, "called": 2, "final": 3}   # 抓網頁時狀態只能往前走；postponed 只由人設
# SPEC「編輯填資料」的手動輸入格式，最後多一欄 others：第 3 名以後「姓名|政黨|票數|得票率」用 ; 隔開。
# 抓網頁時自動填；資訊卡列全部候選人，手動抄留空的話卡片只有前兩名
MAYOR_COLS = ["code", "county", "status", "updated", "stations_reported", "stations_total",
              "c1_name", "c1_party", "c1_votes", "c1_pct", "c2_name", "c2_party", "c2_votes", "c2_pct", "winner", "note", "others"]
REF_COLS = ["code", "county", "agree", "disagree", "valid", "invalid", "votes_cast", "electorate", "updated"]
# 第 22 案（中選會 115-08-28 公告）；簡稱 11-18 定為「廢除非核家園」，投票權人總額等中選會公告（null＝22 縣市加總）
CASE22 = {"no": 22, "short": "廢除非核家園", "topic": "你是否支持政府使用「核電」振興經濟，以廢除「非核家園」的能源政策？",
          "vote_date": DATE, "electorate": None}


def counties():
    """22 縣市代碼與名稱（跟縣市界、中選會同一套代碼）"""
    return {c["code"]: c["name"] for c in json.loads((DATA / "mayor_2022.json").read_text(encoding="utf-8"))["counties"]}


def party_codes():
    t = {p["party_name"]: int(p["party_code"]) for p in json.loads((DATA / "raw/cec_db/webs_configs_party_colors.json").read_text(encoding="utf-8"))}
    for alias in ("無黨籍及未經政黨推薦", "無黨籍", "無"):   # 開票頁與資料庫寫「及」，代碼表寫「與」
        t[alias] = t["無黨籍與未經政黨推薦"]
    return t


def finite(s):
    """字串 → 有限的浮點數；NaN、inf、Excel 的 #DIV/0! 都當錯，不讓它們上卡片"""
    try:
        v = float(s)
    except ValueError:
        v = math.nan
    if not math.isfinite(v):
        raise ValueError(f"看不懂的數字「{s}」")
    return v


def num(s):
    s = str(s).replace(",", "").strip()
    return int(finite(s)) if s not in ("", "-") else 0


def pct(s):
    s = str(s).replace("%", "").replace(",", "").strip()
    return finite(s) if s not in ("", "-") else 0.0


def norm_time(s, date):
    """開票頁或 Excel 的時間 →「2026-11-28 21:05:33」。認得「21:05」「21:05:33」「11/28 21:05:33」「2026-11-28 21:05」
    「2026/11/28 21:05」、民國年「115/11/28 23:53:49」、「11/28 下午 11:53」，全形的／與：也認"""
    s = " ".join(s.replace("／", "/").replace("：", ":").split())
    if not s:
        return ""
    m = re.fullmatch(r"(?:(?:(\d{3,4})[-/])?(\d{1,2})[-/](\d{1,2}))?\s*(上午|下午)?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if not m:
        raise ValueError(f"看不懂的時間「{s}」")
    y, mo, d = date.split("-")
    if m[2]:
        y, mo, d = m[1] or y, m[2], m[3]
    y, h = int(y), int(m[5])
    if y < 1911:   # 民國年
        y += 1911
    if m[4] == "下午" and h < 12:
        h += 12
    elif m[4] == "上午" and h == 12:
        h = 0
    return f"{y}-{int(mo):02d}-{int(d):02d} {h:02d}:{m[6]}:{m[7] or '00'}"


# ── 開票頁的 HTML 片段 ──
class Tables(HTMLParser):
    """收集每個 table 的列（每格的文字）與頁面上所有文字"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.open, self.cell, self.text = [], [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.open.append([])
        elif tag == "tr" and self.open:
            self.open[-1].append([])
        elif tag in ("td", "th") and self.open and self.open[-1]:
            self.cell = []
        elif tag == "img" and self.cell is not None:   # 當選註記是圖片時：alt 剛好是 ◎ 或「當選」才當成格子裡的字
            alt = (dict(attrs).get("alt") or "").strip()
            if alt in ("◎", "當選"):
                self.cell.append(f" {alt} ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.open[-1][-1].append(" ".join("".join(self.cell).split()))   # split() 也吃掉 &nbsp;
            self.cell = None
        elif tag == "table" and self.open:
            self.tables.append(self.open.pop())

    def handle_data(self, d):
        if self.cell is not None:
            self.cell.append(d)
        self.text.append(d)


def grid(page, *need):
    """表頭含 need 每個字的那張表 → (表頭, 資料列)、頁面文字。列寬不跟表頭比（表頭多一欄時候選人才不會整批消失），
    呼叫的人只留要用的欄都在的列"""
    p = Tables()
    p.feed(page)
    for t in p.tables:
        if t and all(any(n in h for h in t[0]) for n in need):
            return t[0], t[1:], " ".join("".join(p.text).split())
    raise ValueError(f"找不到表頭含 {'、'.join(need)} 的表，頁面上的表頭：{[t[0] for t in p.tables if t]}")


def col(head, key, avoid=()):
    for i, h in enumerate(head):
        if key in h and not any(a in h for a in avoid):
            return i
    raise ValueError(f"表頭沒有「{key}」：{head}")


def page_meta(text, date):
    """頁面文字 → (已送, 應送)（找不到是 None）、資料時間（找不到是 ''）。全形的／：、西元或民國年、上午／下午都認"""
    text = text.replace("／", "/").replace("：", ":")
    st = re.search(r"已送\s*/\s*應送\s*:?\s*([\d,]+)\s*/\s*([\d,]+)", text)
    up = re.search(r"資料更新時間\s*:?\s*((?:(?:\d{3,4}[-/])?\d{1,2}[-/]\d{1,2}\s*)?(?:[上下]午\s*)?\d{1,2}:\d{2}(?::\d{2})?)", text)
    return (num(st[1]), num(st[2])) if st else None, norm_time(up[1], date) if up else ""


def parse_mayor(page, date):
    """首長候選人得票數（2022 年的 TC）→ 依票數排好的候選人、(已送, 應送)、資料時間。
    找不到候選人、已送／應送或資料時間就丟 ValueError，這縣市沿用上一輪（不要變成 0/0 擋住整份 JSON）"""
    head, rows, text = grid(page, "姓名", "得票數")
    i = {"mark": col(head, "註記"), "name": col(head, "姓名"), "votes": col(head, "得票數"), "pct": col(head, "得票率"), "party": col(head, "政黨")}
    cands = []
    for r in rows:
        if len(r) <= max(i.values()):
            continue
        c = {k: r[v] for k, v in i.items()}
        if c["name"].endswith("◎") and c["name"][:-1].strip():   # 姓名格尾巴的 ◎（「周春米 ◎」）：從姓名拿掉，算當選註記
            c["name"], c["mark"] = c["name"][:-1].strip(), "◎"
        elif c["mark"] in ("◎", "當選"):   # 註記格整格就是 ◎ 或「當選」才算，不做部分比對，免得開票初期假當選
            c["mark"] = "◎"
        cands.append(c)
    if not cands:
        raise ValueError("表裡沒有候選人")
    cands.sort(key=lambda c: -num(c["votes"]))
    stations, updated = page_meta(text, date)
    if stations is None or not updated:
        raise ValueError("頁面上找不到已送／應送或資料更新時間")
    return cands, stations, updated


def declared():
    """開票夜編輯說「已宣布當選」、中選會還沒打 ◎ 的人：data/declared.csv（code,candidate）→ {縣市代碼: 姓名}，沒有檔就是空的"""
    path = DATA / "declared.csv"
    if not path.exists():
        return {}
    try:
        rows = csv_rows(path)
    except (ValueError, csv.Error) as e:   # 檔案壞了不擋整輪抓取
        print(f"錯誤：data/declared.csv 讀不了（{e}），這輪先不看宣布當選", file=sys.stderr)
        return {}
    return {r["code"]: r["candidate"].strip() for r in rows if (r.get("candidate") or "").strip()}


def mayor_row(code, name, cands, stations, updated, declared_name=None):
    """一個縣市 → results CSV 的一列。狀態照 SPEC「算開完」：◎ 且已送等於應送＝開完，◎ 但還沒送完＝當選已確定。
    頁面沒有 ◎ 但 declared.csv 列了這縣市的人，就當那人已宣布當選（還在開票時是 called，蓋章加開票中）；他不是目前最高票就先不標。
    當選人一定是最高票（並列最高可以）；開完卻是同票待抽籤（？）或未達最低當選票數（＜），是沒有當選人的 final"""
    rep, tot = stations
    top = max((num(c["votes"]) for c in cands), default=0)
    for c in cands:   # 中選會的 ◎ 打在票數不是最高的人身上：不採用這頁，這縣沿用上一輪
        if c["mark"] == "◎" and num(c["votes"]) < top:
            raise ValueError(f"中選會的 ◎ 打在票數不是最高的「{c['name']}」，不採用這頁")
    won = [k for k, c in enumerate(cands[:2]) if c["mark"] == "◎"]
    if not won and declared_name:
        won = [k for k, c in enumerate(cands[:2]) if c["name"] == declared_name]
        if not won:
            print(f"注意：{name} 宣布當選的「{declared_name}」不在得票前兩名的姓名裡，沒有標", file=sys.stderr)
        elif num(cands[won[0]]["votes"]) < top:   # 電視台常在只開兩三成時宣布，宣布的人可能暫時落後；照開票中更新，不會卡住
            print(f"注意：{name} 宣布當選的「{declared_name}」目前不是最高票，先不標，照開票中", file=sys.stderr)
            won = []
    tie, low = any("？" in c["mark"] for c in cands), any("＜" in c["mark"] for c in cands)
    note = "同票，抽籤決定" if tie else "未達最低當選票數" if low else ""
    if won:
        status = "final" if tot and rep == tot else "called"
    elif rep == 0 and not any(num(c["votes"]) for c in cands):
        status = "pending"
    elif tot and rep == tot and note:   # 開完了但同票或未達最低當選票數：final、沒有當選人，note 寫原因
        status = "final"
    else:
        status = "counting"
        if tot and rep == tot:
            print(f"錯誤：{name} 已送等於應送，頁面上卻沒有 ◎、當選、？、＜ 任何註記，先當開票中；請到開票頁看註記欄是不是改了寫法", file=sys.stderr)
    row = {"code": code, "county": name, "status": status, "updated": updated, "stations_reported": rep, "stations_total": tot,
           "winner": won[0] + 1 if won else "", "note": note,
           "others": ";".join(f"{c['name']}|{c['party']}|{num(c['votes'])}|{pct(c['pct'])}" for c in cands[2:])}
    for k, c in zip(("c1", "c2"), cands[:2]):
        row.update({f"{k}_name": c["name"], f"{k}_party": c["party"], f"{k}_votes": num(c["votes"]), f"{k}_pct": pct(c["pct"])})
    return row


def parse_ref(page, county, date):
    """公投的縣市結果 → 同意、不同意、有效、無效、投票數、投票權人數。2025 年的頁面沒存到，照表頭的字找欄，取「總計」或縣市名那列"""
    head, rows, text = grid(page, "同意", "不同意")
    i = {"agree": col(head, "同意", ("不同意", "%", "比")), "disagree": col(head, "不同意", ("%", "比")),
         "valid": col(head, "有效", ("同意", "%", "比")), "invalid": col(head, "無效"),
         "votes_cast": col(head, "投票數"), "electorate": col(head, "投票權人", ("%", "比"))}
    rows = [r for r in rows if len(r) > max(i.values())]
    norm = lambda s: "".join(s.split()).replace("台", "臺")   # 去掉空白（含全形空白）、台→臺 再比對
    row = next((r for r in rows if norm(r[0]) in ("總計", "合計", norm(county))), None)
    if row is None:   # 不退回第一列（那是某個鄉鎮市區，前後一致、檢查抓不到）
        raise ValueError(f"表裡找不到「總計」「合計」或「{county}」那列，第一欄有：{'、'.join(r[0] for r in rows[:5])}")
    return {k: num(row[v]) for k, v in i.items()}, page_meta(text, date)[1]


# ── 抓網頁 ──
_last = 0.0


def get(url, delay):
    global _last
    wait = delay - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    try:
        req = urllib.request.Request(f"{url}?_={int(time.time() * 1000)}", headers={"User-Agent": UA})   # 開票頁自己也加時間戳避開快取
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8")
    finally:
        _last = time.time()


def csv_rows(path):
    """手動編的 CSV → 每列一個 dict。Excel 存成 UTF-8（有沒有 BOM 都行）或 ANSI（cp950）都讀得了；
    代碼被 Excel 吃掉開頭的 0（09007 → 9007）補回 5 碼；代碼空白的列（尾巴的空列）跳過"""
    b = path.read_bytes()
    try:
        text = b.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = b.decode("cp950")
    rows = []
    for r in csv.DictReader(io.StringIO(text, newline="")):
        code = (r.get("code") or "").strip()
        if code:
            r["code"] = code.zfill(5) if code.isdigit() else code
            rows.append(r)
    return rows


def read_csv(path, errors=None):
    """CSV → {代碼: 那列}；同一個代碼出現兩次是錯誤（不默默留最後一列）。給 errors 就記進去，沒給就直接停"""
    out = {}
    for r in csv_rows(path) if path.exists() else []:
        if r["code"] in out:
            msg = f"{r['code']}：CSV 裡有兩列是同一個代碼"
            if errors is None:
                sys.exit("錯誤：" + msg)
            errors.append(msg)
        out[r["code"]] = r
    return out


def write_csv(path, cols, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:   # 加 BOM，Excel 打開不會亂碼
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)


def votes_of(r):
    """一列裡每位候選人的票數 {姓名: 票數}：c1、c2 加 others"""
    v = {(r.get(f"{k}_name") or "").strip(): num(r.get(f"{k}_votes") or 0) for k in ("c1", "c2")}
    for o in filter(None, (r.get("others") or "").split(";")):
        p = o.split("|")
        if len(p) == 4:
            v[p[0].strip()] = num(p[2])
    v.pop("", None)
    return v


def winner_of(r):
    w = str(r.get("winner") or "").strip()
    return (r.get(f"c{w}_name") or "").strip() if w in ("1", "2") else ""


def backwards(o, n, date, declared_name=None):
    """新抓的列 n 跟上一輪的列 o 比，倒退就回傳原因（整列不採用，沿用上一輪）。
    票數減少但資料時間較新、已送沒少，當成中選會更正照收，只印警告"""
    try:
        ot = norm_time(o.get("updated") or "", date)
        orep, otot, ov = num(o.get("stations_reported") or 0), num(o.get("stations_total") or 0), votes_of(o)
    except ValueError:
        return []   # 上一輪那列本身是壞的（手動填錯），拿新的蓋過去，免得這縣一整晚卡住
    ost, nst = (o.get("status") or "").strip() or "pending", n["status"]
    nt, nrep, ntot, nv = n["updated"], n["stations_reported"], n["stations_total"], votes_of(n)
    ow, nw = winner_of(o) if ost in ("called", "final") else "", winner_of(n)
    # 宣布當選的人一時落後：時間沒變舊、已送沒變少，就讓狀態 called 退回 counting、換當選人，免得卡死
    soft = ost == "called" and ow and ow == declared_name and nt >= ot and nrep >= orep
    why = []
    if nt < ot:
        why.append(f"資料時間 {nt or '（空白）'} 比上一輪 {ot} 舊")
    if nrep < orep:
        why.append(f"已送 {nrep} 比上一輪 {orep} 少")
    if ntot != otot and ost != "pending" and otot:
        why.append(f"應送從 {otot} 變成 {ntot}")
    if RANK.get(nst, 0) < RANK.get(ost, 0) and not (soft and nst == "counting"):
        why.append(f"狀態從 {ost} 退回 {nst}")
    if sum(ov.values()) and not sum(nv.values()):
        why.append("票數全部變成 0")
    if ow and nw and nw != ow and not soft:
        why.append(f"當選人從 {ow} 變成 {nw}")
    drop = [f"{k} {ov[k]:,}→{nv[k]:,}" for k in sorted(ov.keys() & nv.keys()) if nv[k] < ov[k]]
    if drop and nt <= ot:
        why.append(f"票數減少（{'、'.join(drop)}）但資料時間沒有比較新")
    elif drop and not why:
        print(f"注意：{n['county']} 票數減少（{'、'.join(drop)}），時間較新、已送沒少，當成中選會更正照收", file=sys.stderr)
    return why


def web(kind, prefix, csv_path, raw_dir, date, delay):
    """22 縣市各抓一頁、寫 CSV；沒抓到、解析失敗、檢查不過或比上一輪倒退的縣市沿用上一輪的那列（第一輪是未開票），其他縣市照常更新"""
    names, old, rows, fails = counties(), read_csv(csv_path), [], []
    dec = declared() if kind == "mayor" else {}
    pc = party_codes() if kind == "mayor" else {}
    if kind == "mayor":   # 第一輪還沒有 CSV：缺的縣市先放未開票的列（有範本用範本），抓不到也一定有 22 列
        tpl = read_csv(DATA / "results_2026_template.csv")
        for code, name in names.items():
            seed = tpl.get(code) or {"code": code, "county": name, "status": "pending"}
            old.setdefault(code, {k: seed.get(k) or "" for k in MAYOR_COLS})
    raw_dir.mkdir(parents=True, exist_ok=True)
    skipped = 0
    for code, name in sorted(names.items()):
        url = f"{prefix.rstrip('/')}/{code}000000000000.html"
        if kind == "mayor" and (old[code].get("status") or "").strip() == "postponed":   # 延後只由人設：這縣不抓、整列照留
            print(f"{name} 是手動設的 postponed，這輪不抓", file=sys.stderr)
            rows.append(old[code])
            skipped += 1
            continue
        page = None
        try:
            page = get(url, delay)
            if kind == "mayor":
                row = mayor_row(code, name, *parse_mayor(page, date), declared_name=dec.get(code))
                why = mayor_county(code, row, names, pc, date)[1] + backwards(old[code], row, date, dec.get(code))
                if why:   # 任一項檢查不過：這縣整列沿用上一輪
                    raise ValueError("新資料不採用：" + "；".join(why))
            else:
                v, updated = parse_ref(page, name, date)
                row = {"code": code, "county": name, **v, "updated": updated}
            (raw_dir / f"{kind}_{code}.html").write_text(page, encoding="utf-8")   # 收下了才存，維護頁不會蓋掉上一份好的
            rows.append(row)
        except Exception as e:   # 一個縣市失敗不擋其他縣市
            fails.append(f"{name}（{url}）：{e}")
            if page is not None:
                (raw_dir / f"{kind}_{code}_bad.html").write_text(page, encoding="utf-8")
            if code in old:
                rows.append(old[code])
    for f in fails:
        print("這輪沒更新，沿用上一輪：" + f if f.split("（")[0] in {r["county"] for r in rows} else "沒抓到：" + f, file=sys.stderr)
    write_csv(csv_path, MAYOR_COLS if kind == "mayor" else REF_COLS, rows)
    print(f"寫了 {csv_path}（{len(rows)} 縣市，這輪抓到 {22 - len(fails) - skipped} 個）")
    return len(fails)


# ── CSV → JSON ──
def mayor_county(code, r, names, pc, date):
    """CSV 的一列 → (地圖 JSON 的一個縣市, 錯誤清單)。mayor_json 與 web() 檢查新抓的列共用，抓網頁時一縣不過只擋那一縣"""
    name, errors = names[code], []
    try:
        st, note = (r.get("status") or "").strip() or "pending", (r.get("note") or "").strip()
        if st not in STATUSES:
            errors.append(f"{name}：狀態「{st}」不是 {'、'.join(STATUSES)} 之一")
        cands = []
        for k in ("c1", "c2"):
            nm, party = (r.get(f"{k}_name") or "").strip(), (r.get(f"{k}_party") or "").strip()
            if not nm:
                continue
            if party not in pc:
                errors.append(f"{name} {nm}：政黨「{party}」對不到中選會政黨代碼表（寫錯字，或在 party_codes() 補別名）")
                continue
            cands.append({"name": nm, "party": "無黨籍及未經政黨推薦" if pc[party] == 999 else party, "party_code": pc[party],
                          "votes": num(r[f"{k}_votes"]), "pct": pct(r[f"{k}_pct"]), "elected": str(r.get("winner", "")).strip() == k[1]})
        if len(cands) == 2 and cands[0]["votes"] < cands[1]["votes"]:
            errors.append(f"{name}：第 1 名的票數比第 2 名少，c1、c2 填反了？")
        for o in filter(None, (r.get("others") or "").split(";")):   # 第 3 名以後：小黨可能不在代碼表，地圖只查前兩名的代碼
            try:
                nm, party, votes, p = (x.strip() for x in o.split("|"))
            except ValueError:
                errors.append(f"{name}：others 的「{o}」要寫成 姓名|政黨|票數|得票率")
                continue
            if not party:
                errors.append(f"{name}：others 的 {nm} 沒填政黨（無黨籍寫「無黨籍」）")
            if cands and num(votes) > cands[-1]["votes"]:
                errors.append(f"{name}：others 的 {nm} 票數比前兩名多")
            cands.append({"name": nm, "party": "無黨籍及未經政黨推薦" if pc.get(party) == 999 else party, "party_code": pc.get(party),
                          "votes": num(votes), "pct": pct(p), "elected": False})
        won = [c for c in cands if c["elected"]]
        # 開完卻沒有當選人（同票待抽籤、未達最低當選票數）：winner 留空、note 寫明
        if st == "called" and len(won) != 1 or st == "final" and len(won) != 1 and not (not won and note):
            errors.append(f"{name}：狀態 {st} 要在 winner 填 1 或 2" + ("（開完沒有當選人的，winner 留空並在 note 寫原因）" if st == "final" else ""))
        if won and won[0]["votes"] < max(c["votes"] for c in cands):
            errors.append(f"{name}：當選的 {won[0]['name']} 不是最高票，winner 填錯了？")
        if sum(c["pct"] for c in cands) > 100.5:
            errors.append(f"{name}：得票率加起來 {sum(c['pct'] for c in cands):.2f}%，超過 100")
        rep, tot = num(r.get("stations_reported", "")), num(r.get("stations_total", ""))
        if rep > tot:
            errors.append(f"{name}：已送 {rep} 比應送 {tot} 多")
        if st == "final" and tot and rep != tot:
            errors.append(f"{name}：狀態 final 但只開了 {rep}／{tot} 所")
        try:
            updated = norm_time(r.get("updated") or "", date)
        except ValueError as e:
            errors.append(f"{name}：{e}")
            updated = ""
        if st in ("counting", "called") and not (tot and updated):
            errors.append(f"{name}：開票中要填 updated 與已送／應送")
    except ValueError as e:   # 票數、得票率看不懂（Excel 的 #DIV/0!、NaN）
        return None, errors + [f"{name}：{e}"]
    c = {"code": code, "name": name, "vote_date": date, "status": st, "candidates": cands, "note": note}
    if tot:
        c["stations"] = {"reported": rep, "total": tot}
    if updated:
        c["updated"] = updated
    return c, errors


def mayor_json(csv_path, out, date):
    names, pc, errors, res = counties(), party_codes(), [], {}
    for code, r in read_csv(csv_path, errors).items():
        if code not in names:
            errors.append(f"{code}：不是縣市代碼")
            continue
        res[code], errs = mayor_county(code, r, names, pc, date)
        errors += errs
    if names.keys() - res.keys():
        errors.append("缺這些縣市：" + "、".join(names[k] for k in sorted(names.keys() - res.keys())))
    if errors:
        sys.exit("\n".join("錯誤：" + e for e in errors))
    meta = {"source": SOURCE, "from": str(csv_path.name), "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    out.write_text(json.dumps({"meta": meta, "counties": [res[k] for k in sorted(res)]}, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    n = {s: sum(c["status"] == s for c in res.values()) for s in STATUSES}
    print(f"寫了 {out}：" + "、".join(f"{s} {v}" for s, v in n.items() if v))


def ref_json(csv_path, out, case):
    names, errors, res = counties(), [], {}
    for code, r in read_csv(csv_path, errors).items():
        if code not in names:
            errors.append(f"{code}：不是縣市代碼")
            continue
        try:   # 數字格看不懂（例如 #DIV/0!）記成一般的錯誤訊息
            v = {k: num(r.get(k) or "") for k in ("agree", "disagree", "valid", "invalid", "votes_cast", "electorate")}
        except ValueError as e:
            errors.append(f"{names[code]}：{e}")
            continue
        if v["agree"] + v["disagree"] != v["valid"]:
            errors.append(f"{names[code]}：同意加不同意 {v['agree'] + v['disagree']:,} 不等於有效票 {v['valid']:,}")
        if v["valid"] + v["invalid"] != v["votes_cast"]:
            errors.append(f"{names[code]}：有效加無效 {v['valid'] + v['invalid']:,} 不等於投票數 {v['votes_cast']:,}")
        if not v["votes_cast"] or not v["electorate"] or not v["valid"]:
            errors.append(f"{names[code]}：有效票、投票數或投票權人數是 0，還沒開完？")
        res[code] = {"code": code, "name": names[code], **v}
    if names.keys() - res.keys():
        errors.append("缺這些縣市：" + "、".join(names[k] for k in sorted(names.keys() - res.keys())))
    if errors:
        sys.exit("\n".join("錯誤：" + e for e in errors))
    meta = {"source": SOURCE, "from": str(csv_path.name), "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    out.write_text(json.dumps({"meta": meta, "case": case, "counties": [res[k] for k in sorted(res)]}, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    print(f"寫了 {out}：同意 {sum(c['agree'] for c in res.values()):,}、不同意 {sum(c['disagree'] for c in res.values()):,}")


# ── 自我測試：2022 年真實開票頁＋照它的結構做的 22 縣市假頁（本機伺服器），比對中選會資料庫的數字 ──
def selftest():
    prev = HERE / "preview"
    prev.mkdir(exist_ok=True)
    real = (DATA / "raw/cec_live_2022/TC_10013000000000000.html").read_text(encoding="utf-8")
    db = {c["code"]: c for c in json.loads((DATA / "mayor_2022.json").read_text(encoding="utf-8"))["counties"]}
    ref_db = json.loads((DATA / "referendum21_2025.json").read_text(encoding="utf-8"))
    assert party_codes()["無黨籍及未經政黨推薦"] == 999

    def same(a, b, n=2):   # 前 n 名的姓名、票數、得票率、當選；政黨代碼只比前兩名（代碼表缺幾個小黨，例如 2022 金門的龍黨）
        key = lambda c, i: (c["name"], c["votes"], c["pct"], c["elected"], c["party_code"] if i < 2 else c["party"])
        return [key(c, i) for i, c in enumerate(a[:n])] == [key(c, i) for i, c in enumerate(b[:n])]

    # 1. 真實的屏東縣頁：解析結果要跟資料庫一樣
    cands, st, up = parse_mayor(real, "2022-11-26")
    row = mayor_row("10013", "屏東縣", cands, st, up)
    assert (row["status"], st, up, row["winner"]) == ("final", (711, 711), "2022-11-26 23:53:49", 1), (row, st, up)
    assert [(row["c1_name"], row["c1_votes"], row["c1_pct"]), (row["c2_name"], row["c2_votes"], row["c2_pct"])] == \
        [(c["name"], c["votes"], c["pct"]) for c in db["10013"]["candidates"][:2]]
    print("1 真實的 2022 屏東縣開票頁：姓名、票數、得票率、當選、所數、資料時間都跟資料庫一樣")

    # 1b. 宣布當選：頁面還沒有 ◎ 時，declared.csv 列的人照樣當選、狀態是 called；名字對不上就不標
    half = [dict(c, mark="") for c in cands]
    r2 = mayor_row("10013", "屏東縣", half, (300, 711), up, declared_name=half[0]["name"])
    assert (r2["status"], r2["winner"]) == ("called", 1), r2
    r3 = mayor_row("10013", "屏東縣", half, (300, 711), up, declared_name="不在名單")
    assert (r3["status"], r3["winner"]) == ("counting", ""), r3
    print("1b 宣布當選：declared.csv 的人在開票中標成當選（called），名字對不上就照開票中")

    # 1c. 開票夜防呆（11-26 審查）：所數與時間的寫法、嚴格的當選記號、當選人要最高票、同票與未達最低當選票數
    def row_of(page, **kw):
        return mayor_row("10013", "屏東縣", *parse_mayor(page, "2026-11-28"), **kw)

    def raises(page):
        try:
            parse_mayor(page, "2026-11-28") and row_of(page)
        except ValueError:
            return True
        return False
    r = row_of(real.replace("已送/應送: 711/711", "已送／應送：711／711").replace("11/26&nbsp;23:53:49", "115/11/28&nbsp;下午&nbsp;11:53"))
    assert (r["status"], r["stations_total"], r["updated"]) == ("final", 711, "2026-11-28 23:53:00"), r
    assert norm_time("2026/11/28 21:05", DATE) == "2026-11-28 21:05:00" and norm_time("11/28 上午 12:10", DATE) == "2026-11-28 00:10:00"
    assert raises(real.replace("已送/應送: 711/711", "已送 711 應送 711")) and raises(real.replace("資料更新時間", "資料時間"))
    cell = '<td class="electmark">◎</td>'
    for mark in ('<img src="x.png" alt="◎">', "當選"):
        assert row_of(real.replace(cell, f'<td class="electmark">{mark}</td>'))["winner"] == 1, mark
    assert row_of(real.replace(cell, '<td class="electmark">&nbsp;</td>').replace("<td>周春米</td>", "<td>周春米 ◎</td>"))["c1_name"] == "周春米"
    assert row_of(real.replace(cell, '<td class="electmark">當選人待公告</td>'))["winner"] == ""   # 只認整格相等
    second = real.replace(cell, '<td class="electmark">&nbsp;</td>').replace("<td>蘇清泉</td>", "<td>蘇清泉 ◎</td>")
    assert raises(second)   # ◎ 打在第二名：這頁不採用
    assert (r := mayor_row("10013", "屏東縣", half, (300, 711), up, declared_name=half[1]["name"]))["winner"] == "" and r["status"] == "counting", r
    tie = [dict(c, mark="？") for c in cands]
    assert (r := mayor_row("10013", "屏東縣", tie, (711, 711), up))["status"] == "final" and r["winner"] == "" and r["note"] == "同票，抽籤決定", r
    print("1c 防呆：全形所數、民國年與下午的時間照讀，缺所數或時間就不採用；當選只認整格「◎」「當選」或圖片 alt、姓名格的 ◎ 拿掉；"
          "◎ 打在非最高票不採用，宣布當選的人落後先不標；開完同票是沒有當選人的 final")

    # 2. 照真實頁的結構做 22 縣市的假頁，放本機伺服器，走跟開票夜一樣的抓取與轉檔
    states = {"63000": "counting", "64000": "called", "10020": "pending"}   # 臺北開票中、高雄當選已確定、嘉義市還沒開
    tmp = Path(tempfile.mkdtemp())
    (tmp / "zh-TW/TC").mkdir(parents=True)
    for code, c in db.items():
        s = states.get(code, "final")
        tot = 700
        rep = {"final": tot, "called": 650, "counting": 300, "pending": 0}[s]
        k = rep / tot if s != "final" else 1
        body = "".join(f'<tr> <td class="electmark">{"◎" if p["elected"] and s in ("final", "called") else "&nbsp;"}</td> <td>{p["no"]}</td> '
                       f'<td>{p["name"]}</td> <td>男</td> <td class="numeric">{round(p["votes"] * k):,}</td> <td class="numeric">{p["pct"]:.2f}%</td> '
                       f'<td>{p["party"]}</td> </tr>' for p in c["candidates"])
        page = re.sub(r"<tbody>.*?</tbody>", f"<tbody>{body}</tbody>", real, flags=re.S)
        page = re.sub(r"已送/應送: \d+/\d+", f"已送/應送: {rep}/{tot}", page).replace("屏東縣 縣長選舉", f"{c['name']} 首長選舉")
        page = page.replace("11/26&nbsp;23:53:49", "11/26&nbsp;20:15:00" if s != "final" else "11/26&nbsp;23:53:49")
        (tmp / f"zh-TW/TC/{code}000000000000.html").write_text(page, encoding="utf-8")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(tmp)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/zh-TW"
    csv_p, json_p = prev / "selftest_results.csv", prev / "selftest_results.json"
    csv_p.unlink(missing_ok=True)
    assert web("mayor", f"{base}/TC", csv_p, prev / "selftest_raw", "2022-11-26", 0) == 0
    mayor_json(csv_p, json_p, "2022-11-26")
    got = {c["code"]: c for c in json.loads(json_p.read_text(encoding="utf-8"))["counties"]}
    for code, c in got.items():
        s = states.get(code, "final")
        assert c["status"] == s, (code, c["status"], s)
        assert [p["name"] for p in c["candidates"]] == [p["name"] for p in sorted(db[code]["candidates"], key=lambda p: -p["votes"])], code
        if s == "final":
            assert same(c["candidates"], db[code]["candidates"], 99), (code, c["candidates"], db[code]["candidates"])
    assert got["63000"]["stations"] == {"reported": 300, "total": 700} and got["63000"]["updated"] == "2022-11-26 20:15:00"
    print("2 22 縣市假頁（本機伺服器）：開完的 19 縣市每位候選人都跟資料庫一樣；臺北開票中、高雄當選已確定、嘉義市未開票都判對")

    # 3. 沒抓到的縣市沿用上一輪：把臺北的頁拿掉再抓一輪，CSV 裡的臺北要留著
    (tmp / "zh-TW/TC/63000000000000000.html").unlink()
    assert web("mayor", f"{base}/TC", csv_p, prev / "selftest_raw", "2022-11-26", 0) == 1
    assert read_csv(csv_p)["63000"]["stations_reported"] == "300"
    print("3 臺北那頁抓不到：其他 21 縣市更新，臺北沿用上一輪")

    # 3b. 只進不退：臺中換成比較舊的頁（時間早、所數少、沒有 ◎），新北換成全 0 的頁，兩縣都留上一輪的開完；
    #     臺南票數變少但時間較新、所數沒少，當成中選會更正照收；嘉義市以外手動設的延後不抓
    tc = lambda code: tmp / f"zh-TW/TC/{code}000000000000.html"
    before = read_csv(csv_p)
    tc("66000").write_text(tc("66000").read_text(encoding="utf-8").replace("已送/應送: 700/700", "已送/應送: 200/700")
                           .replace("11/26&nbsp;23:53:49", "11/26&nbsp;19:00:00").replace(">◎<", ">&nbsp;<"), encoding="utf-8")
    tc("65000").write_text(re.sub(r'class="numeric">[\d,]+<', 'class="numeric">0<', tc("65000").read_text(encoding="utf-8"))
                           .replace("已送/應送: 700/700", "已送/應送: 0/700").replace(">◎<", ">&nbsp;<"), encoding="utf-8")
    tc("67000").write_text(re.sub(r'class="numeric">([\d,]+)<', lambda m: f'class="numeric">{num(m[1]) - 1:,}<', tc("67000").read_text(encoding="utf-8"))
                           .replace("11/26&nbsp;23:53:49", "11/26&nbsp;23:59:00"), encoding="utf-8")
    rows3 = list(before.values())
    next(r for r in rows3 if r["code"] == "10002").update(status="postponed", note="測試延後")
    write_csv(csv_p, MAYOR_COLS, rows3)
    web("mayor", f"{base}/TC", csv_p, prev / "selftest_raw", "2022-11-26", 0)
    after = read_csv(csv_p)
    for code in ("66000", "65000"):
        assert after[code] == before[code], (code, after[code])
    assert num(after["67000"]["c1_votes"]) == num(before["67000"]["c1_votes"]) - 1 and after["67000"]["updated"] == "2022-11-26 23:59:00"
    assert (after["10002"]["status"], after["10002"]["note"]) == ("postponed", "測試延後")
    # 宣布當選的人暫時落後：上一輪是他當選的 called，這輪退回開票中照收，不卡住；沒宣布的 called 退回開票中就不收
    o = dict(after["64000"])
    n = dict(o, status="counting", winner="", updated="2022-11-26 21:00:00", stations_reported=660, stations_total=700)
    assert backwards(o, n, "2022-11-26", winner_of(o)) == [] and backwards(o, n, "2022-11-26")
    write_csv(csv_p, MAYOR_COLS, list(before.values()))
    print("3b 只進不退：舊頁、全 0 的頁不採用，票數變少但時間較新當成更正照收，延後不抓；宣布當選的人落後時照開票中更新")

    # 3c. 第一輪就少一縣（臺北那頁還是拿掉的）：從範本補 pending，22 縣照樣轉得出 JSON
    first = prev / "selftest_first.csv"
    first.unlink(missing_ok=True)
    assert web("mayor", f"{base}/TC", first, prev / "selftest_raw", "2022-11-26", 0) == 1
    assert len(read_csv(first)) == 22 and read_csv(first)["63000"]["status"] == "pending"
    mayor_json(first, first.with_suffix(".json"), "2022-11-26")
    print("3c 第一輪臺北抓不到：補範本的未開票，22 縣市照樣轉得出 JSON")

    # 4. 產生器吃得下：開票中的版本與手動 CSV 轉出的開完版本都出得了圖（寫到 preview/）
    run = lambda *a: subprocess.run([sys.executable, "-I", *map(str, a)], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    r = run("build_map.py", "--data", json_p, "--out", prev / "selftest_counting.html")
    assert r.returncode == 0, r.stderr
    groups = dict(l.split()[0::2] for l in r.stdout.splitlines() if re.match(r"\d{5} ", l))
    assert groups["63000"] == "pend" and groups["10020"] == "pend" and groups["64000"] == "dpp", groups
    manual = prev / "selftest_manual.csv"
    write_csv(manual, MAYOR_COLS, [{"code": k, "county": c["name"], "status": "final", "winner": 1, "note": "",
                                     **{f"{n}_{f}": p[g] for n, p in zip(("c1", "c2"), c["candidates"][:2])
                                        for f, g in (("name", "name"), ("party", "party"), ("votes", "votes"), ("pct", "pct"))}}
                                    for k, c in db.items()])
    mayor_json(manual, prev / "selftest_manual.json", "2022-11-26")
    got = {c["code"]: c for c in json.loads((prev / "selftest_manual.json").read_text(encoding="utf-8"))["counties"]}
    assert all(same(got[k]["candidates"], db[k]["candidates"]) for k in db)
    r = run("build_map.py", "--data", prev / "selftest_manual.json", "--out", prev / "selftest_final.html")
    assert r.returncode == 0, r.stderr
    print("4 產生器：開票中版本（臺北、嘉義市斜線，高雄已上色）與手動 CSV 的開完版本都出得了圖")

    # 5. 公投：手動 CSV（用 2025 第 21 案的數字）→ JSON → 公投地圖；全國加總要跟資料庫一樣
    ref_csv = prev / "selftest_ref.csv"
    write_csv(ref_csv, REF_COLS, [{"code": c["code"], "county": c["name"], **{k: c[k] for k in REF_COLS[2:8]}, "updated": ""}
                                  for c in ref_db["counties"]])
    ref_json(ref_csv, prev / "selftest_ref.json", ref_db["case"])
    r = run("build_referendum.py", "--data", prev / "selftest_ref.json", "--out", prev / "selftest_ref.html")
    assert r.returncode == 0 and "同意 4,341,432 不同意 1,511,693 門檻 5,000,523" in r.stdout, r.stdout + r.stderr
    # 公投頁的表格是猜的（2025 年沒存到）：照猜的表頭做一頁，至少確定解析程式本身沒問題
    (tmp / "zh-TW/RF").mkdir()
    for c in ref_db["counties"]:
        cells = [c["agree"], c["disagree"], c["valid"], c["invalid"], c["votes_cast"], c["electorate"]]
        (tmp / f"zh-TW/RF/{c['code']}000000000000.html").write_text(
            '<table><thead><tr><th>行政區別</th><th>同意票數</th><th>不同意票數</th><th>有效票數</th><th>無效票數</th><th>投票數</th>'
            '<th>投票權人數</th><th>投票率%</th></tr></thead><tbody><tr><td>總計</td>' + "".join(f"<td>{n:,}</td>" for n in cells)
            + f'<td>{c["turnout"]}%</td></tr></tbody></table>', encoding="utf-8")
    web_csv = prev / "selftest_ref_web.csv"
    web_csv.unlink(missing_ok=True)
    assert web("ref", f"{base}/RF", web_csv, prev / "selftest_raw", "2025-08-23", 0) == 0
    ref_json(web_csv, prev / "selftest_ref_web.json", ref_db["case"])
    print("5 公投：手動 CSV 轉出的地圖全國數字跟資料庫一樣；照猜的表頭做的假頁也抓得完（真的格式當天再對）")
    srv.shutdown()

    # 6. 2026 年的路：投票日換成 2026，產生器改讀 data/tags.csv，標籤要掛到當選人身上。
    #    票數是假的、政黨一律無黨籍（只看路通不通），只寫到 preview/，不能公開
    tg = list(csv.DictReader(open(DATA / "tags.csv", encoding="utf-8-sig")))
    rows = []
    for code, name in counties().items():
        names = [e["candidate"].strip() for e in tg if e["code"].strip() == code]   # 標籤表只有六都
        names += ["測試甲", "測試乙"][len(names):]
        rows.append({"code": code, "county": name, "status": "final", "winner": 1, "note": "",
                     **{f"{n}_{f}": v for n, nm, votes in zip(("c1", "c2"), names, (2000, 1000))
                        for f, v in (("name", nm), ("party", "無黨籍"), ("votes", votes), ("pct", votes / 30))},
                     "others": ";".join(f"{nm}|無黨籍|500|1.67" for nm in names[2:])})
    fake = prev / "selftest_2026_fake.csv"
    write_csv(fake, MAYOR_COLS, rows)
    mayor_json(fake, fake.with_suffix(".json"), DATE)
    r = run("build_map.py", "--data", fake.with_suffix(".json"), "--out", prev / "selftest_2026_fake.html")
    assert r.returncode == 0 and "對不到候選人名單" not in r.stderr, r.stderr
    page = (prev / "selftest_2026_fake.html").read_text(encoding="utf-8")
    want = len({e["code"].strip() for e in tg if e["tags"].strip()})   # 當選人是每縣市的第一位（winner=1），標籤表每縣市第一列就是他
    got_t = page.count('"tags":[')
    assert "2026 縣市長選舉結果" in page and got_t == want, (got_t, want)
    print(f"6 2026 年的路：標題換成 2026、改讀 tags.csv，假結果的 22 位當選人裡有標籤的 {want} 位都掛上了（假資料只在 preview/）")
    print("自我測試通過，產出都在 preview/selftest_*")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["mayor-web", "ref-web", "mayor-csv", "ref-csv", "selftest"])
    ap.add_argument("arg", nargs="?", help="web：網址前綴；csv：CSV 路徑")
    ap.add_argument("--date", default=DATE, help="投票日，也拿來補開票頁上沒寫的年份")
    ap.add_argument("--short", help=f"公投簡稱（地圖副標的粗體字），預設「{CASE22['short']}」")
    ap.add_argument("--electorate", type=int, help="中選會公告的投票權人總額（算門檻用）；沒給就用 22 縣市加總")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    mayor = a.cmd.startswith("mayor")
    csv_path = Path(a.arg) if a.cmd.endswith("csv") and a.arg else DATA / ("results_2026.csv" if mayor else "referendum22_2026.csv")
    if a.cmd.endswith("web"):
        if not a.arg:
            sys.exit("要給網址前綴，例：https://www.cec.gov.tw/zh-TW/TC")
        web("mayor" if mayor else "ref", a.arg, csv_path, DATA / "raw/cec_live_2026", a.date, DELAY)
    if mayor:
        mayor_json(csv_path, csv_path.with_suffix(".json"), a.date)
    else:
        ref_json(csv_path, csv_path.with_suffix(".json"), {**CASE22, "short": CASE22["short"] if a.short is None else a.short,
                                                           "vote_date": a.date, "electorate": a.electorate})


if __name__ == "__main__":
    main()
