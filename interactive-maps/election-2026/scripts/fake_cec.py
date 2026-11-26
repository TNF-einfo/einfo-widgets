"""假的中選會開票網站，給開票夜彩排與 live_loop.py 的測試用（SPEC「首頁版即時更新」）。

照 2022 年的開票片段格式出 22 縣市的縣市長頁，候選人與政黨讀 data/candidates_2026.csv，票數全是假的。
選舉時鐘從 --start 開始、照 --speed 倍速走（4 倍＝16:00 到 24:00 走兩小時），票數與所數跟著時鐘長，開完才打 ◎。
頁面上的「資料更新時間」寫的是真的牆上時間：迴圈不收比現在晚 5 分鐘以上的資料，時鐘又跑得比較快，所以不印選舉時鐘。
一縣的數字沒變，資料時間也停在上次變的那一刻（迴圈才分得出「沒有新資料」）。

用法（在 election-2026 資料夾跑）：
  python -I scripts/fake_cec.py [--port 8799] [--start 16:00] [--speed 4] [--seed 1] [--no-specials]
  python -I scripts/fake_cec.py selftest
網址前綴是 http://127.0.0.1:8799/zh-TW/TC（給 fetch_live.py mayor-web 或 live_loop.py --prefix）。
另有 /_status（各縣市現在的狀態，JSON）與 /_set?t=HH:MM、/_set?speed=N（跳時鐘、改倍速，測試用）。

故意放的壞資料（選舉時鐘的時段，--no-specials 全關）：
  屏東 10013 開到七成就打 ◎（提早宣布當選）；連江 09007 開完同票、兩人都是「？」；宜蘭 10002 18:00–18:40 回 404；
  臺中 66000 19:30–19:50 回 18:30 的舊頁、資料時間早 20 分鐘；基隆 10017 20:00–20:20 資料時間晚 30 分鐘；
  新北 65000 20:30–20:50 票數與所數全是 0。延後的縣市由人在 overrides.csv 設，這裡照常出頁。
"""
import argparse
import csv
import json
import math
import random
import re
import sys
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent.parent
TPL = (HERE / "data/raw/cec_live_2022/TC_10013000000000000.html").read_text(encoding="utf-8")
SHARES = [50.8, 44.1, 2.9, 1.2, 0.6, 0.4]
SPECIAL = {   # 代碼: (開始, 結束, 種類)，選舉時鐘的分鐘
    "10002": (18 * 60, 18 * 60 + 40, "404"),
    "66000": (19 * 60 + 30, 19 * 60 + 50, "stale"),
    "10017": (20 * 60, 20 * 60 + 20, "future"),
    "65000": (20 * 60 + 30, 20 * 60 + 50, "zero"),
}
EARLY, TIE = "10013", "09007"
COUNTIES, SPECIALS, SEEN = {}, True, {}   # SEEN：每縣上次出的數字與那時的牆上時間


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def load(seed=1, specials=True):
    """每個縣市：應送所數、開始與開完的時間、每位候選人的最後票數與一點點走勢的晃動（都由 seed 決定，重跑一樣）"""
    global SPECIALS
    SPECIALS = specials
    cands = {}
    for r in csv.DictReader(open(HERE / "data/candidates_2026.csv", encoding="utf-8-sig")):
        party = "無黨籍及未經政黨推薦" if r["party"] == "無黨籍" else r["party"]
        cands.setdefault(r["code"], (r["county"], []))[1].append((r["name"], party))
    COUNTIES.clear()
    SEEN.clear()
    for i, (code, (county, people)) in enumerate(cands.items()):
        rng = random.Random(f"{seed}:{code}")
        total = {"09007": 10, "09020": 50}.get(code) or rng.randint(100, 1500)
        w = [SHARES[k] if k < len(SHARES) else 0.1 for k in range(len(people))]
        if i % 2:   # 一縣第一位贏、一縣第二位贏，兩黨都有當選的
            w[0], w[1] = w[1], w[0]
        votes = total * rng.randint(920, 1080)
        final = [max(1, round(votes * x / sum(w))) for x in w]
        if code == TIE:
            final[0] = final[1] = max(final[:2])
        COUNTIES[code] = {"county": county, "people": people, "total": total, "final": final,
                          "start": 16 * 60 + rng.randint(5, 30), "end": rng.randint(19 * 60, 23 * 60 + 40),
                          # 走勢：u + a·u(1−u) + b·sin(2πu)，斜率 ≥ 1 − 0.22 − 2π·0.025 > 0，票數只增不減、開完剛好是最後票數
                          "wobble": [(rng.uniform(-.22, .22), rng.uniform(-.025, .025)) for _ in people]}


def special(code, t):
    s = SPECIAL.get(code)
    return s[2] if SPECIALS and s and s[0] <= t < s[1] else ""


def counts(code, t):
    """選舉時鐘 t（分鐘）時這縣的 (已送, 各候選人票數, 各候選人註記, 特殊狀況)；404 時票數是 None"""
    c, sp = COUNTIES[code], special(code, t)
    if sp == "404":
        return 0, None, None, sp
    if sp == "zero":
        return 0, [0] * len(c["people"]), ["&nbsp;"] * len(c["people"]), sp
    if sp == "stale":
        t = SPECIAL[code][0] - 60   # 一小時前的那頁
    u = (t - c["start"]) / (c["end"] - c["start"])
    tot = c["total"]
    rep = 0 if u <= 0 else tot if u >= 1 else min(tot - 1, max(1, round(tot * u * u * (3 - 2 * u))))
    x = rep / tot
    votes = [f if rep == tot else round(f * (x + a * x * (1 - x) + b * math.sin(2 * math.pi * x))) for f, (a, b) in zip(c["final"], c["wobble"])]
    marks = ["&nbsp;"] * len(votes)
    win = max(range(len(votes)), key=lambda k: c["final"][k])
    if code == TIE and SPECIALS and rep == tot:
        marks[0] = marks[1] = "？"
    elif rep == tot or (code == EARLY and SPECIALS and rep >= 0.7 * tot and votes[win] == max(votes)):
        marks[win] = "◎"
    return rep, votes, marks, sp


def page(code, t, wall):
    """一縣的開票片段（2022 年格式）；404 時回 None。wall＝印在「資料更新時間」的牆上時間"""
    if code not in COUNTIES:
        return None
    rep, votes, marks, sp = counts(code, t)
    if votes is None:
        return None
    if not sp:   # 數字沒變，資料時間也不變（跟上次出這縣的頁比），迴圈才看得出「沒有新資料」
        sig = (rep, tuple(votes), tuple(marks))
        if SEEN.get(code, (None,))[0] != sig:
            SEEN[code] = (sig, wall)
        wall = SEEN[code][1]
    wall += {"stale": timedelta(minutes=-20), "future": timedelta(minutes=30)}.get(sp, timedelta())
    c, s = COUNTIES[code], sum(votes)
    rows = "".join(f'<tr><td class="electmark">{m}</td><td>{k}</td><td>{n}</td><td>男</td><td class="numeric">{v:,}</td>'
                   f'<td class="numeric">{(100 * v / s if s else 0):.2f}%</td><td>{p}</td></tr>'
                   for k, ((n, p), v, m) in enumerate(zip(c["people"], votes, marks), 1))
    h = re.sub(r"<tbody>.*?</tbody>", lambda _: f"<tbody>{rows}</tbody>", TPL, flags=re.S)
    h = re.sub(r"已送/應送: \d+/\d+", f"已送/應送: {rep}/{c['total']}", h).replace("屏東縣 縣長選舉", f"{c['county']} 首長選舉")
    return h.replace("11/26&nbsp;23:53:49", wall.strftime("%Y/%m/%d&nbsp;%H:%M:%S"))


def status(t):
    out = {}
    for code, c in COUNTIES.items():
        rep, votes, marks, sp = counts(code, t)
        st = "404" if votes is None else "final" if rep == c["total"] else "called" if marks and "◎" in marks else "pending" if not rep else "counting"
        out[code] = {"county": c["county"], "status": st, "reported": rep, "total": c["total"], "special": sp}
    return out


class Clock:
    def __init__(self, start, speed):
        self.base, self.mono, self.speed = hm(start), time.monotonic(), speed

    def now(self):
        return self.base + (time.monotonic() - self.mono) * self.speed / 60

    def set(self, t=None, speed=None):
        self.base, self.mono = hm(t) if t else self.now(), time.monotonic()
        self.speed = self.speed if speed is None else speed


def handler(clock):
    route = re.compile(r"^/zh-TW/TC/(\d{5})0{12}\.html$")

    class H(BaseHTTPRequestHandler):
        def log_message(self, f, *a):
            t = clock.now()
            print(f"[{int(t) // 60:02d}:{int(t) % 60:02d}] {self.path.split('?')[0]} {a[1] if len(a) > 1 else ''}", flush=True)

        def send(self, code, body, ctype="text/html; charset=utf-8"):
            try:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            u = urlparse(self.path)
            if m := route.match(u.path):
                h = page(m[1], clock.now(), datetime.now())
                return self.send(*(404, b"Not Found") if h is None else (200, h.encode("utf-8")))
            if u.path == "/_set":
                q = parse_qs(u.query)
                clock.set(q.get("t", [None])[0], float(q["speed"][0]) if "speed" in q else None)
            if u.path in ("/_set", "/_status"):
                t = clock.now()
                body = {"clock": f"{int(t) // 60:02d}:{int(t) % 60:02d}", "speed": clock.speed, "specials": SPECIALS, "counties": status(t)}
                return self.send(200, json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            self.send(404, b"Not Found")
    return H


def selftest():
    sys.path.insert(0, str(HERE / "scripts"))
    import fetch_live as fl
    load(1, True)
    wall = datetime(2026, 11, 27, 19, 45, 3)
    for code in COUNTIES:   # 一般縣市：所數、票數只增不減，◎ 只在開完；真的解析程式讀得懂每一頁
        prev = None
        for t in range(16 * 60, 24 * 60, 5):
            h = page(code, t, wall)
            if h is None or special(code, t):
                continue
            cands, (rep, tot), up = fl.parse_mayor(h, "2026-11-27")
            v = {c["name"]: fl.num(c["votes"]) for c in cands}
            assert up == "2026-11-27 19:45:03" and tot == COUNTIES[code]["total"]
            if prev:
                assert rep >= prev[0] and all(v[k] >= prev[1][k] for k in v), (code, t)
            assert code == EARLY or any(c["mark"] in ("◎", "？") for c in cands) == (rep == tot), (code, t, rep, tot)
            prev = (rep, v)
        assert prev[0] == COUNTIES[code]["total"], code
    st = lambda t: status(t)
    early = [st(t)[EARLY]["status"] for t in range(16 * 60, 24 * 60, 2)]
    assert "called" in early and early[-1] == "final", early
    cands, _, _ = fl.parse_mayor(page(TIE, 23 * 60 + 59, wall), "2026-11-27")
    assert [c["mark"] for c in cands[:2]] == ["？", "？"] and cands[0]["votes"] == cands[1]["votes"]
    assert fl.mayor_row(TIE, "連江縣", cands, (10, 10), "2026-11-27 23:59:00")["note"] == "同票，抽籤決定"
    assert page("10002", 18 * 60 + 15, wall) is None and page("10002", 17 * 60 + 55, wall)
    old = fl.parse_mayor(page("66000", 19 * 60 + 40, wall), "2026-11-27")
    assert old[1][0] == counts("66000", 18 * 60 + 30)[0] and old[2] == "2026-11-27 19:25:03"
    assert fl.parse_mayor(page("10017", 20 * 60 + 10, wall), "2026-11-27")[2] == "2026-11-27 20:15:03"
    z = fl.parse_mayor(page("65000", 20 * 60 + 35, wall), "2026-11-27")
    assert z[1][0] == 0 and not any(fl.num(c["votes"]) for c in z[0])
    print("fake_cec selftest OK：22 縣市所數與票數只增不減、開完才有記號；提早 ◎、同票、404、舊頁、未來時間、全 0 都照時段出現")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["selftest"])
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--start", default="16:00")
    ap.add_argument("--speed", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-specials", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    load(a.seed, not a.no_specials)
    srv = ThreadingHTTPServer((a.bind, a.port), handler(Clock(a.start, a.speed)))
    print(f"網址前綴 http://{a.bind}:{srv.server_address[1]}/zh-TW/TC（選舉時鐘 {a.start} 起、{a.speed:g} 倍速）", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
