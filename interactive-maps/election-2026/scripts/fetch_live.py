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
抓網頁時沒抓到的縣市沿用 CSV 裡上一輪的那列，不會倒退成空白。請求匿名（User-Agent 只寫用途），每頁間隔 3 秒，
原始頁存 data/raw/cec_live_2026/。公投頁的表格 2025 年的存檔沒有抓到，解析是照表頭的字猜的，當天要先看一頁對過。
"""
import argparse
import csv
import functools
import http.server
import json
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


def num(s):
    s = str(s).replace(",", "").strip()
    return int(float(s)) if s not in ("", "-") else 0


def pct(s):
    s = str(s).replace("%", "").replace(",", "").strip()
    return float(s) if s not in ("", "-") else 0.0


def norm_time(s, date):
    """「21:05」「21:05:33」「11/28 21:05:33」「2026-11-28 21:05:33」→「2026-11-28 21:05:33」"""
    s = s.strip()
    if not s:
        return ""
    m = re.fullmatch(r"(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})/(\d{1,2}))?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if not m:
        raise ValueError(f"看不懂的時間「{s}」")
    y, mo, d = (m[1], m[2], m[3]) if m[1] else (date[:4], m[4], m[5]) if m[4] else date.split("-")
    return f"{y}-{int(mo):02d}-{int(d):02d} {int(m[6]):02d}:{m[7]}:{m[8] or '00'}"


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
    """表頭含 need 每個字的那張表 → (表頭, 跟表頭一樣寬的資料列)、頁面文字"""
    p = Tables()
    p.feed(page)
    for t in p.tables:
        if t and all(any(n in h for h in t[0]) for n in need):
            return t[0], [r for r in t[1:] if len(r) == len(t[0])], " ".join("".join(p.text).split())
    raise ValueError(f"找不到表頭含 {'、'.join(need)} 的表，頁面上的表頭：{[t[0] for t in p.tables if t]}")


def col(head, key, avoid=()):
    for i, h in enumerate(head):
        if key in h and not any(a in h for a in avoid):
            return i
    raise ValueError(f"表頭沒有「{key}」：{head}")


def page_meta(text, date):
    st = re.search(r"已送/應送[:：]?\s*([\d,]+)\s*/\s*([\d,]+)", text)
    up = re.search(r"資料更新時間[:：]?\s*(\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)", text)
    return (num(st[1]), num(st[2])) if st else (0, 0), norm_time(up[1], date) if up else ""


def parse_mayor(page, date):
    """首長候選人得票數（2022 年的 TC）→ 依票數排好的候選人、(已送, 應送)、資料時間"""
    head, rows, text = grid(page, "姓名", "得票數")
    i = {"mark": col(head, "註記"), "name": col(head, "姓名"), "votes": col(head, "得票數"), "pct": col(head, "得票率"), "party": col(head, "政黨")}
    cands = sorted(({k: r[v] for k, v in i.items()} for r in rows), key=lambda c: -num(c["votes"]))
    return cands, *page_meta(text, date)


def declared():
    """開票夜編輯說「已宣布當選」、中選會還沒打 ◎ 的人：data/declared.csv（code,candidate）→ {縣市代碼: 姓名}，沒有檔就是空的"""
    path = DATA / "declared.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["code"].strip(): r["candidate"].strip() for r in csv.DictReader(f) if (r.get("code") or "").strip() and (r.get("candidate") or "").strip()}


def mayor_row(code, name, cands, stations, updated, declared_name=None):
    """一個縣市 → results CSV 的一列。狀態照 SPEC「算開完」：◎ 且已送等於應送＝開完，◎ 但還沒送完＝當選已確定。
    頁面沒有 ◎ 但 declared.csv 列了這縣市的人，就當那人已宣布當選（還在開票時是 called，蓋章加開票中）"""
    rep, tot = stations
    won = [k for k, c in enumerate(cands[:2]) if "◎" in c["mark"]]
    if not won and declared_name:
        won = [k for k, c in enumerate(cands[:2]) if c["name"] == declared_name]
        if not won:
            print(f"注意：{name} 宣布當選的「{declared_name}」不在得票前兩名的姓名裡，沒有標", file=sys.stderr)
    note = "同票，抽籤決定" if any("？" in c["mark"] for c in cands) else ""
    if won:
        status = "final" if tot and rep == tot else "called"
    elif rep == 0 and not any(num(c["votes"]) for c in cands):
        status = "pending"
    else:
        status = "counting"
        if tot and rep == tot:
            print(f"注意：{name} 已送等於應送，但頁面上沒有 ◎（同票或未達最低當選票數？），先當開票中", file=sys.stderr)
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
    row = next((r for r in rows if r[0] in ("總計", "合計", county)), rows[0] if rows else None)
    if row is None:
        raise ValueError("表裡沒有資料列")
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


def read_csv(path):
    return {r["code"].strip(): r for r in csv.DictReader(open(path, encoding="utf-8-sig"))} if path.exists() else {}


def write_csv(path, cols, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:   # 加 BOM，Excel 打開不會亂碼
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)


def web(kind, prefix, csv_path, raw_dir, date, delay):
    """22 縣市各抓一頁、寫 CSV；沒抓到或解析失敗的縣市沿用 CSV 裡上一輪的那列"""
    names, old, rows, fails = counties(), read_csv(csv_path), [], []
    dec = declared() if kind == "mayor" else {}
    raw_dir.mkdir(parents=True, exist_ok=True)
    for code, name in sorted(names.items()):
        url = f"{prefix.rstrip('/')}/{code}000000000000.html"
        try:
            page = get(url, delay)
            (raw_dir / f"{kind}_{code}.html").write_text(page, encoding="utf-8")
            if kind == "mayor":
                rows.append(mayor_row(code, name, *parse_mayor(page, date), declared_name=dec.get(code)))
            else:
                v, updated = parse_ref(page, name, date)
                rows.append({"code": code, "county": name, **v, "updated": updated})
        except Exception as e:   # 一個縣市失敗不擋其他縣市
            fails.append(f"{name}（{url}）：{e}")
            if code in old:
                rows.append(old[code])
    for f in fails:
        print("沒抓到，沿用上一輪：" + f if f.split("（")[0] in {r["county"] for r in rows} else "沒抓到：" + f, file=sys.stderr)
    write_csv(csv_path, MAYOR_COLS if kind == "mayor" else REF_COLS, rows)
    print(f"寫了 {csv_path}（{len(rows)} 縣市，這輪抓到 {22 - len(fails)} 個）")
    return len(fails)


# ── CSV → JSON ──
def mayor_json(csv_path, out, date):
    names, pc, errors, res = counties(), party_codes(), [], {}
    for code, r in read_csv(csv_path).items():
        if code not in names:
            errors.append(f"{code}：不是縣市代碼")
            continue
        name, st = names[code], (r.get("status") or "").strip() or "pending"
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
            if cands and num(votes) > cands[-1]["votes"]:
                errors.append(f"{name}：others 的 {nm} 票數比前兩名多")
            cands.append({"name": nm, "party": "無黨籍及未經政黨推薦" if pc.get(party) == 999 else party, "party_code": pc.get(party),
                          "votes": num(votes), "pct": pct(p), "elected": False})
        if st in ("called", "final") and sum(c["elected"] for c in cands) != 1:
            errors.append(f"{name}：狀態 {st} 要在 winner 填 1 或 2")
        rep, tot = num(r.get("stations_reported", "")), num(r.get("stations_total", ""))
        if rep > tot:
            errors.append(f"{name}：已送 {rep} 比應送 {tot} 多")
        try:
            updated = norm_time(r.get("updated") or "", date)
        except ValueError as e:
            errors.append(f"{name}：{e}")
            updated = ""
        if st in ("counting", "called") and not (tot and updated):
            errors.append(f"{name}：開票中要填 updated 與已送／應送")
        c = {"code": code, "name": name, "vote_date": date, "status": st, "candidates": cands, "note": (r.get("note") or "").strip()}
        if tot:
            c["stations"] = {"reported": rep, "total": tot}
        if updated:
            c["updated"] = updated
        res[code] = c
    if names.keys() - res.keys():
        errors.append("缺這些縣市：" + "、".join(names[k] for k in sorted(names.keys() - res.keys())))
    if errors:
        sys.exit("\n".join("錯誤：" + e for e in errors))
    meta = {"source": SOURCE, "from": str(csv_path.name), "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    out.write_text(json.dumps({"meta": meta, "counties": [res[k] for k in sorted(res)]}, ensure_ascii=False, indent=1), encoding="utf-8")
    n = {s: sum(c["status"] == s for c in res.values()) for s in STATUSES}
    print(f"寫了 {out}：" + "、".join(f"{s} {v}" for s, v in n.items() if v))


def ref_json(csv_path, out, case):
    names, errors, res = counties(), [], {}
    for code, r in read_csv(csv_path).items():
        if code not in names:
            errors.append(f"{code}：不是縣市代碼")
            continue
        v = {k: num(r.get(k, "")) for k in ("agree", "disagree", "valid", "invalid", "votes_cast", "electorate")}
        if v["agree"] + v["disagree"] != v["valid"]:
            errors.append(f"{names[code]}：同意加不同意 {v['agree'] + v['disagree']:,} 不等於有效票 {v['valid']:,}")
        if v["valid"] + v["invalid"] != v["votes_cast"]:
            errors.append(f"{names[code]}：有效加無效 {v['valid'] + v['invalid']:,} 不等於投票數 {v['votes_cast']:,}")
        if not v["votes_cast"] or not v["electorate"]:
            errors.append(f"{names[code]}：投票數或投票權人數是 0，還沒開完？")
        res[code] = {"code": code, "name": names[code], **v}
    if names.keys() - res.keys():
        errors.append("缺這些縣市：" + "、".join(names[k] for k in sorted(names.keys() - res.keys())))
    if errors:
        sys.exit("\n".join("錯誤：" + e for e in errors))
    meta = {"source": SOURCE, "from": str(csv_path.name), "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    out.write_text(json.dumps({"meta": meta, "case": case, "counties": [res[k] for k in sorted(res)]}, ensure_ascii=False, indent=1), encoding="utf-8")
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
