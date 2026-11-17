"""抓中選會選舉資料庫（db.cec.gov.tw）的 2022 縣市長與 2025 第 21 案公投結果，整理成地圖用的 JSON。

原始檔存 data/raw/cec_db/，已存在就跳過（加 --force 重抓）；整理好的寫 data/mayor_2022.json、data/referendum21_2025.json。
用法：python -I scripts/fetch_cec.py [--force]
請求匿名（User-Agent 只寫用途，不帶任何個人資訊），每個請求之間隔 2 秒。
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RAW = HERE / "data" / "raw" / "cec_db"
OUT = HERE / "data"
BASE = "https://db.cec.gov.tw/static"
UA = "einfo-election-map/0.1"  # 只寫用途、不放聯絡方式（.claude/rules/crawlers.md）
DELAY = 2.0
ALL = "00_000_00_000_0000"

# 主題代碼取自 /static/elections/list/ELC_C1.json、ELC_C2.json 與 /static/referendums/list/N.json（2026-11-17 下載）
THEMES = {
    "c1_2022": ("elections", "ELC/C1/00/05cc7b904c7a30cc7c88d5b10898c98e"),  # 111年直轄市長選舉 2022-11-26
    "c2_2022": ("elections", "ELC/C2/00/63615098f5afa8ec53159c4a86fc01d3"),  # 111年縣市長選舉 2022-11-26
    "c2_2022_chiayi": ("elections", "ELC/C2/00/1275d73551f2c0caf202e803b1766057"),  # 111年嘉義市長重行選舉 2022-12-18
    "ref21_2025": ("referendums", "N/67e0b4764145bc1edb0eb02f11b383ff"),  # 全國性公投第 21 案 2025-08-23
}
SIX = {"臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市"}
# 四色分組：藍＝國民黨、綠＝民進黨、眾＝台灣民眾黨，其他政黨與無黨籍一律灰（政黨代碼見 /static/webs/configs/party_colors.json）
GROUP = {1: "kmt", 16: "dpp", 350: "tpp"}

_last = 0.0


def get(url, dest, force):
    global _last
    if dest.exists() and not force:
        return json.loads(dest.read_text(encoding="utf-8"))
    wait = DELAY - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    _last = time.time()
    data = json.loads(body.decode("utf-8"))  # 先確定是 JSON 才落檔
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return data


def fetch(key, kind, force):
    section, path = THEMES[key]
    out = {}
    for kind_ in kind:
        url = f"{BASE}/{section}/data/{kind_}/{path}/C/{ALL}.json"
        out[kind_] = get(url, RAW / f"{key}_{kind_}_C.json", force)[ALL]
    return out


def code(row):
    return row["prv_code"] + row["city_code"]  # 跟國土測繪中心縣市界的 COUNTYCODE 同一套（例：63000 臺北市）


def mayors(force):
    counties = {}
    for key in ("c1_2022", "c2_2022", "c2_2022_chiayi"):
        d = fetch(key, ("tickets", "profiles"), force)
        prof = {code(p): p for p in d["profiles"]}
        for t in d["tickets"]:
            c = code(t)
            p = prof[c]
            if p["valid_ticket"] == 0:  # 嘉義市 11-26 停止選舉，資料以 12-18 重行選舉為準
                continue
            e = counties.setdefault(c, {
                "code": c, "name": t["area_name"], "six": t["area_name"] in SIX,
                "vote_date": {"c2_2022_chiayi": "2022-12-18"}.get(key, "2022-11-26"),
                "electorate": p["votable_population"], "votes_cast": p["vote_ticket"],
                "valid": p["valid_ticket"], "invalid": p["invalid_ticket"],
                "turnout": p["vote_to_elect"], "candidates": [],
            })
            e["candidates"].append({
                "no": t["cand_no"], "name": t["cand_name"], "party": t["party_name"],
                "party_code": t["party_code"], "group": GROUP.get(t["party_code"], "other"),
                "votes": t["ticket_num"], "pct": t["ticket_percent"],
                "elected": t["is_victor"].strip() == "*", "incumbent": t["is_current"] == "Y",
            })
    for e in counties.values():
        e["candidates"].sort(key=lambda x: -x["votes"])
        won = [x for x in e["candidates"] if x["elected"]]
        assert len(won) == 1, (e["name"], won)
        e["winner_group"] = won[0]["group"]
    rows = sorted(counties.values(), key=lambda e: e["code"])
    assert len(rows) == 22, len(rows)
    return rows


def referendum(force):
    d = fetch("ref21_2025", ("tickets", "profiles"), force)
    prof = {code(p): p for p in d["profiles"]}
    rows = {}
    for t in d["tickets"]:
        c = code(t)
        p = prof[c]
        r = rows.setdefault(c, {"code": c, "name": t["area_name"]})
        r.update(agree=t["agree_ticket"], disagree=t["disagree_ticket"], electorate=p["votable_population"],
                 votes_cast=p["vote_ticket"], valid=p["valid_ticket"], invalid=p["invalid_ticket"],
                 turnout=p["vote_to_votable"], agree_to_electorate=t["agree_to_votable"], passed=t["vote_result"] == "Y")
    for r in rows.values():
        # 環資 2025 年那張圖的配色依據：(同意票－不同意票)／投票總數（含無效票）
        r["margin"] = round((r["agree"] - r["disagree"]) / r["votes_cast"] * 100, 2)
    out = sorted(rows.values(), key=lambda r: r["code"])
    assert len(out) == 22, len(out)
    return out


def main():
    force = "--force" in sys.argv
    m = mayors(force)
    meta = {"source": "中央選舉委員會選舉及公投資料庫 https://db.cec.gov.tw/",
            "downloaded": time.strftime("%Y-%m-%d"), "license": "政府資料開放授權條款－第1版"}
    (OUT / "mayor_2022.json").write_text(json.dumps({"meta": meta, "counties": m}, ensure_ascii=False, indent=1), encoding="utf-8")
    r = referendum(force)
    (OUT / "referendum21_2025.json").write_text(json.dumps({"meta": meta, "counties": r}, ensure_ascii=False, indent=1), encoding="utf-8")
    tally = {}
    for e in m:
        tally[e["winner_group"]] = tally.get(e["winner_group"], 0) + 1
    print("mayor 2022 winners by group:", tally)
    print("referendum 21 agree total:", sum(x["agree"] for x in r), "disagree total:", sum(x["disagree"] for x in r))


if __name__ == "__main__":
    main()
