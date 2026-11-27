"""開票夜的迴圈：抓中選會 → 一縣一縣合併與檢查 → 出首頁版與 live.json → 資料有變才 commit、push（SPEC「首頁版即時更新」）。

用法（在 election-2026 資料夾跑；工作排程器的設定在 scripts/live_loop_task.ps1）：
  python -I scripts/live_loop.py --prefix <網址前綴> --once --dry-run    # 乾跑一輪：抓、合併、產生，不碰 git；狀態與產出在 preview/realtime/state/<epoch>-dryrun/
  python -I scripts/live_loop.py --prefix <網址前綴> --once              # 跑一輪，有變就推（排程器每 30 秒叫一次）
  python -I scripts/live_loop.py --prefix <網址前綴>                     # 自己每 30 秒跑一輪（終端機開著跑）
  python -I scripts/live_loop.py selftest [--keep 資料夾]                # 假中選會＋乾跑十幾輪，檢查防呆；--keep 留下每輪的頁面給瀏覽器測試
選項：--epoch（頁面只收同一個 epoch，預設 2026-11-28，彩排用 rehearsal）、--date（投票日）、--out-dir（產出放哪，預設 election-2026 資料夾；
repo 外面只准 --dry-run）、--home-name（彩排用 index.html）、--article（文章版也一起重產、一起推，預設不做）、--poll-s（讀者多久抓一次，0＝停止開關）、
--heartbeat-min（沒變也隔多久推一次，免得頁面以為迴圈停了，預設 15）、--state-dir（預設 preview/realtime/state/<epoch>/）、
--test-banner（彩排：頁面加「測試資料」紅條與 noindex）、--fast-dir 與 --fast-url（快車道，見 scripts/fast_server.py；乾跑時 --fast-dir 改放
<state>/fast/，不碰正在給讀者的那個資料夾）。
人工介入：data/declared.csv（宣布當選，開完前的 ◎ 要列在這裡才發）、data/overrides.csv（code,action,candidate,note；action 是
postponed、reset、force）。狀態看 <state>/status.html（Tailscale 預覽伺服器 :8792 打得開），警告在 <state>/alerts.log。
"""
import argparse
import contextlib
import hashlib
import io
import json
import msvcrt
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
import fetch_live as fl   # noqa: E402

FUTURE = timedelta(minutes=5)   # 資料時間比這台電腦的時鐘晚 5 分鐘以上就不收
ARTICLE = "election-2026.html"
# 排程器用 pythonw 跑（沒有主控台）：子程序改用 python.exe、不開視窗，不然每分鐘閃好幾個黑視窗
PY = sys.executable.replace("pythonw.exe", "python.exe")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ── 鎖：系統檔案鎖，程序結束或重開機就自己放掉，不靠 PID（Windows 會重用 PID） ──
@contextlib.contextmanager
def locked(state):
    f = open(state / "loop.lock", "a+b")
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        yield False
        return
    (state / "loop.pid").write_text(str(os.getpid()), encoding="ascii")   # 給人看是哪個程序，鎖不看它
    try:
        yield True
    finally:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        f.close()


def load_state(state):
    p = state / "state.json"
    s = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {"round": 0, "seq": 0, "hash": "", "pub_ts": 0, "unpushed": False, "push": "", "commit": "", "consumed": [], "held": [], "last_msgs": [], **s}


def save_state(state, s):
    tmp = state / "state.json.tmp"
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, state / "state.json")


def blank(code, name):
    return {k: "" for k in fl.MAYOR_COLS} | {"code": code, "county": name, "status": "pending"}


def overrides(path):
    """data/overrides.csv → {代碼: {action: 那列}}；讀不了就當沒有（記警告），不擋整輪"""
    out, msgs = {}, []
    if path.exists():
        try:
            for r in fl.csv_rows(path):
                act = (r.get("action") or "").strip().lower()
                if act in ("postponed", "reset", "force"):
                    out.setdefault(r["code"], {})[act] = {k: (r.get(k) or "").strip() for k in ("candidate", "note")}
                else:
                    msgs.append(f"overrides.csv：{r['code']} 的 action「{act}」不認得（只有 postponed、reset、force）")
        except Exception as e:
            msgs.append(f"overrides.csv 讀不了（{e}），這輪不套用")
    return out, msgs


def when(s, date):
    try:
        return datetime.strptime(fl.norm_time(s, date), "%Y-%m-%d %H:%M:%S") if s else None
    except ValueError:
        return None


# ── 一輪 ──
def run_round(a, state, s, say):
    names = fl.counties()
    csv_p = state / "results.csv"
    if not csv_p.exists():   # 第一輪：22 縣都是範本的未開票
        tpl = fl.read_csv(fl.DATA / "results_2026_template.csv")
        fl.write_csv(csv_p, fl.MAYOR_COLS, [{**blank(c, n), **{k: v for k, v in tpl.get(c, {}).items() if k in fl.MAYOR_COLS and v}} for c, n in sorted(names.items())])
    rows = fl.read_csv(csv_p)
    ov, msgs = overrides(a.overrides)
    for m in msgs:
        say(m)

    # 抓之前：延後照 overrides 設（拿掉那列就回未開票重抓）；reset 把上一輪換成空白，這輪抓到什麼就收什麼（只用一次）
    saved, armed = {}, {}
    for code, r in rows.items():
        p = ov.get(code, {}).get("postponed")
        if p is not None:
            rows[code] = {**r, "status": "postponed", "winner": "", "note": p["note"] or "選舉延後"}
        elif r.get("status") == "postponed":
            rows[code] = blank(code, names[code])
            say(f"{names[code]}：overrides.csv 已沒有 postponed，改回未開票、重新抓")
        key = f"{code}|{ov.get(code, {}).get('reset', {}).get('note', '')}"   # 同一列只用一次；要再用就把 note 改成別的字（例如現在時間）
        if "reset" in ov.get(code, {}) and key not in s["consumed"] and rows[code].get("status") != "postponed":
            saved[code], armed[code] = rows[code], key
            rows[code] = blank(code, names[code])
    before = {c: dict(saved.get(c, r)) for c, r in rows.items()}
    fl.write_csv(csv_p, fl.MAYOR_COLS, [rows[c] for c in sorted(rows)])
    # 已開完的縣市每 5 輪才重抓一次：一輪越來越短，對中選會的請求也變少
    skip = set() if s["round"] % 5 == 0 else {c for c, r in rows.items() if r.get("status") == "final" and c not in armed}

    out, err = io.StringIO(), io.StringIO()
    t = time.time()
    raw = state / "raw" / datetime.now().strftime("%H%M%S")   # 原始頁照時間存，不互相蓋
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        failed = fl.web("mayor", a.prefix, csv_p, raw, a.date, a.delay, skip, a.declared)
    timing = {"fetch": round(time.time() - t, 1)}
    for line in err.getvalue().splitlines():
        if line.strip() and "這輪不抓" not in line:
            say(line.strip())

    # 抓之後：資料時間在未來 5 分鐘以上的不收；reset 的縣這輪沒抓到就還原、下一輪再用
    rows = fl.read_csv(csv_p)
    now = datetime.now()
    for code, r in rows.items():
        w = when(r.get("updated"), a.date)
        if w and w > now + FUTURE:
            say(f"{names[code]}：資料時間 {r['updated']} 比現在晚 5 分鐘以上，這輪不採用")
            rows[code] = before[code]
        elif code in armed:
            if r == blank(code, names[code]):
                rows[code] = saved[code]
            else:
                s["consumed"].append(armed[code])
                say(f"{names[code]}：reset 用掉了，這輪收下 {r.get('stations_reported')}／{r.get('stations_total')} 所、{r.get('updated')}")
    fl.write_csv(csv_p, fl.MAYOR_COLS, [rows[c] for c in sorted(rows)])

    # 要發佈的那份：開完前的 ◎ 要在 declared.csv 才發；force 由人決定照發（可以不是最高票）
    dec, pc = fl.declared(a.declared), fl.party_codes()
    pub, trailing, held = {}, set(), []
    for code, r in rows.items():
        p, name = dict(r), names[code]
        f = ov.get(code, {}).get("force")
        if f and p.get("status") != "postponed":
            slot = next((k for k in ("1", "2") if (p.get(f"c{k}_name") or "").strip() == f["candidate"]), "")
            full = p.get("stations_total") and p.get("stations_reported") == p.get("stations_total")
            if slot:
                p.update(winner=slot, status="final" if full else "called")
            errs = fl.mayor_county(code, p, names, pc, a.date, True)[1] if slot else []
            if not slot:
                say(f"{name}：overrides.csv 的 force「{f['candidate']}」不在得票前兩名，不套用")
            elif errs:
                say(f"{name}：套用 force 後不過檢查（{'；'.join(errs)}），不套用")
            else:
                trailing.add(code)
            if code not in trailing:
                p = dict(r)
        # force 沒套用的縣照樣過這一關：開完前的 ◎ 要在 declared.csv 才發
        if code not in trailing and p.get("status") == "called" and fl.winner_of(p) != dec.get(code):
            held.append(f"{name} {fl.winner_of(p)}")
            k = f"{code}|{fl.winner_of(p)}"
            if k not in s["held"]:
                s["held"].append(k)
                say(f"{name}：中選會開完前就打 ◎ 給 {fl.winner_of(p)}，先照開票中發；要發當選就把他寫進 data/declared.csv")
            p.update(status="counting", winner="")
        pub[code] = p
    pub_csv, pub_json = state / "publish.csv", state / "publish.json"
    fl.write_csv(pub_csv, fl.MAYOR_COLS, [pub[c] for c in sorted(pub)])
    try:
        with contextlib.redirect_stdout(out):
            fl.mayor_json(pub_csv, pub_json, a.date, trailing)
    except SystemExit as e:
        say(f"轉 JSON 失敗，這輪不發佈：{e}")
        return {"timing": timing, "failed": failed, "published": False, "held": held}

    # 資料有變才發；沒變但上次發佈超過 heartbeat 分鐘、還沒全部開完，也發一次（頁面看 published_at 判斷迴圈還活著）
    data = json.loads(pub_json.read_text(encoding="utf-8"))["counties"]
    h = hashlib.sha256(json.dumps([data, a.epoch, a.poll_s, a.article, a.test_banner, a.fast_url],ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    done = all(c["status"] in ("final", "postponed") for c in data)
    beat = h == s["hash"] and not done and time.time() - s["pub_ts"] >= a.heartbeat_min * 60
    res = {"timing": timing, "failed": failed, "skipped": len(skip), "held": held, "published": False,
           "status": dict(Counter(c["status"] for c in data))}
    if h != s["hash"] or beat:
        t = time.time()
        seq = max(int(t), s["seq"] + 1)   # Unix 秒數：換一台電腦接手也只會變大
        files = build(a, pub_json, seq, say)
        if not files:
            return res
        timing["build"] = round(time.time() - t, 1)
        s.update(seq=seq, hash=h, pub_ts=int(t), pub_at=now.strftime("%H:%M:%S"), unpushed=not a.dry_run)
        (state / "history").mkdir(exist_ok=True)
        shutil.copy(pub_json, state / "history" / f"publish_{seq}.json")   # 回滾用：拿舊的資料重出一版（新的 seq）
        res.update(published=True, heartbeat=beat, seq=seq, files=[str(f) for f in files])
        if a.keep:   # selftest：留下每輪的頁面給瀏覽器測試
            (a.keep / "rounds").mkdir(parents=True, exist_ok=True)
            n = len(list((a.keep / "rounds").glob("live_r*.json"))) + 1
            shutil.copy(a.out_dir / a.home_name, a.keep / "rounds" / f"home_r{n}.html")
            shutil.copy(a.out_dir / "live.json", a.keep / "rounds" / f"live_r{n}.json")
    if a.fast_dir and (a.out_dir / "live.json").exists():   # push 之前；每輪都對一次，上一輪換檔失敗或資料夾被清掉，這輪補上
        fast = a.fast_dir / "live.json"
        if not fast.exists() or fast.read_bytes() != (a.out_dir / "live.json").read_bytes():
            fast_copy(a.out_dir / "live.json", a.fast_dir, say)
    if not a.dry_run and s["unpushed"]:
        t = time.time()
        latest = max((c.get("updated", "") for c in json.loads(pub_json.read_text(encoding="utf-8"))["counties"]), default="")
        msg = f"chore(election-2026): update live results to {latest[11:16] or now.strftime('%H:%M')}" + (" (heartbeat)" if res.get("heartbeat") else "")
        res["git"] = publish(a, msg, s, say)
        timing["git"] = round(time.time() - t, 1)
    return res


def outputs(a):
    return [a.out_dir / a.home_name, a.out_dir / "live.json"] + ([a.out_dir / ARTICLE] if a.article else [])


def build(a, data, seq, say):
    py = [PY, "-I", str(HERE / "build_map.py"), "--data", str(data)] + (["--test-banner"] if a.test_banner else [])
    jobs = [py + ["--home", "--out", str(a.out_dir / a.home_name), "--live-json", str(a.out_dir / "live.json"), "--epoch", a.epoch, "--seq", str(seq)]
            + (["--poll-s", str(a.poll_s)] if a.poll_s is not None else []) + (["--fast-url", a.fast_url] if a.fast_url is not None else [])]
    if a.article:
        jobs.append(py + ["--out", str(a.out_dir / ARTICLE)])
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        r = subprocess.run(j, cwd=HERE, capture_output=True, text=True, encoding="utf-8", timeout=120, creationflags=NOWIN)
        if r.returncode:
            say(f"build_map.py 失敗，這輪不發佈：{r.stderr.strip()[-800:]}")
            return None
    return outputs(a)


def fast_copy(src, fast_dir, say):
    """快車道：push 之前先把 live.json 換進 fast_server 的資料夾，讀者不用等 Pages 部署。
    先寫暫存檔再換名，讀者不會讀到寫一半的檔；Windows 上伺服器剛好在讀時換名會被擋，等一下再試。換不成只寫警告，下一輪再換，Pages 那條照常。"""
    fast_dir.mkdir(parents=True, exist_ok=True)
    tmp = fast_dir / "live.json.tmp"
    shutil.copyfile(src, tmp)
    for _ in range(20):
        try:
            os.replace(tmp, fast_dir / "live.json")
            return True
        except PermissionError:
            time.sleep(0.05)
    say(f"快車道：{fast_dir / 'live.json'} 換不過去（一直被讀），這輪只有 Pages 有新資料")
    return False


def git(*args, cwd, timeout=30):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=timeout, creationflags=NOWIN)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, f"git {args[0]} 逾時（{timeout} 秒）"


def publish(a, msg, s, say):
    """只 add、commit 這幾個檔；push 被拒（遠端比較新）就 pull --rebase 再推一次；沒推成功下一輪再推"""
    g = lambda *x, **k: git(*x, cwd=a.out_dir, **k)
    gd = Path(g("rev-parse", "--absolute-git-dir")[1])
    if (gd / "rebase-merge").exists() or (gd / "rebase-apply").exists():   # 上一輪 rebase 到一半被砍：先退回去，不然一直卡在不是 main
        say("git：上一輪的 rebase 沒做完，先 rebase --abort")
        g("rebase", "--abort")
    rc, br = g("rev-parse", "--abbrev-ref", "HEAD")
    if br != "main":
        say(f"git：目前在 {br} 不是 main，不 commit、不推")
        return "not-main"
    top = Path(g("rev-parse", "--show-toplevel")[1]).resolve()
    g = lambda *x, **k: git(*x, cwd=top, **k)   # 路徑都從 repo 根算
    paths = [p.relative_to(top).as_posix() for p in outputs(a) if p.exists()]
    rc, o = g("add", "--", *paths)
    if rc:
        say(f"git add 失敗：{o}")
        return "add-failed"
    rc, o = g("diff", "--cached", "--quiet", "--", *paths)
    if rc:   # 有東西要 commit；-- paths 只 commit 這幾個檔，別人 stage 的不會被帶進去
        rc, o = g("commit", "-m", msg, "--", *paths)
        if rc:
            say(f"git commit 失敗：{o}")
            return "commit-failed"
        s["commit"] = g("rev-parse", "--short", "HEAD")[1]
    rc, o = g("push", "origin", "main")
    if rc and any(k in o for k in ("non-fast-forward", "fetch first", "rejected")):
        # -X theirs：rebase 時「theirs」是這台的 commit。遠端也改了同兩個檔（別台或人工推的），這台新產生的那版勝出，不會卡在衝突
        rc2, o2 = g("pull", "--rebase", "-X", "theirs", "--autostash", "origin", "main", timeout=60)
        if rc2:
            g("rebase", "--abort")
            say(f"git pull --rebase 失敗，下一輪再推：{o2}")
            return "rebase-failed"
        s["commit"] = g("rev-parse", "--short", "HEAD")[1]
        rc, o = g("push", "origin", "main")
    if rc:
        say(f"git push 失敗，下一輪再推：{o}")
        return "push-failed"
    s["unpushed"] = False
    return "pushed"


def status_page(a, state, s, res, alerts):
    rows = fl.read_csv(state / "results.csv") if (state / "results.csv").exists() else {}
    names = fl.counties()
    ov, _ = overrides(a.overrides)
    st = res.get("status") or {}
    lines = [f"第 {s['round']} 輪　{datetime.now():%H:%M:%S}　{a.epoch}{'　乾跑（不推）' if a.dry_run else ''}",
             "發佈的狀態：" + "、".join(f"{k} {v}" for k, v in sorted(st.items())),
             f"最近一次發佈：{s.get('pub_at', '—')}　seq {s['seq']}　這輪{'有' if res.get('published') else '沒有'}發佈" + ("（心跳）" if res.get("heartbeat") else ""),
             f"git：{s.get('push') or '—'}　commit {s.get('commit') or '—'}" + ("　⚠ 有 commit 還沒推上去" if s["unpushed"] and not a.dry_run else ""),
             "開完前打 ◎、等 declared.csv：" + ("、".join(res.get("held") or []) or "沒有"),
             "overrides.csv：" + ("；".join(f"{names.get(c, c)} {k} {v['candidate'] or v['note']}".strip() for c, d in ov.items() for k, v in d.items()) or "沒有"),
             f"這輪抓取 {res.get('timing', {}).get('fetch', '—')} 秒，沒更新 {res.get('failed', '—')} 縣，跳過（已開完）{res.get('skipped', '—')} 縣", "",
             "縣市　狀態　已送／應送　資料時間"]
    lines += [f"{r['county']}　{r['status']}　{r.get('stations_reported') or 0}／{r.get('stations_total') or 0}　{r.get('updated') or ''}" for r in rows.values()]
    lines += ["", "最近 10 則警告："] + alerts[-10:]
    page = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="30"><title>開票迴圈狀態</title>'
            f'<pre style="font:14px/1.5 ui-monospace,monospace;white-space:pre-wrap">{escape(chr(10).join(lines))}</pre>')
    (state / "status.html").write_text(page, encoding="utf-8")


def one(a):
    state = a.state_dir
    state.mkdir(parents=True, exist_ok=True)
    with locked(state) as ok:
        if not ok:
            print("另一輪還在跑（loop.lock 鎖著），這次不跑")
            return None
        s = load_state(state)
        s["round"] += 1
        msgs, t0 = [], time.time()
        try:
            res = run_round(a, state, s, msgs.append)
        except Exception as e:   # 一輪壞掉不留半套狀態：記下來，下一輪照常
            msgs.append(f"這輪出錯：{type(e).__name__}: {e}")
            res = {"published": False}
        new = [m for m in msgs if m not in s["last_msgs"]]   # 跟上一輪一樣的警告不重複寫進 alerts.log
        s["last_msgs"] = msgs
        stamp = datetime.now().strftime("%H:%M:%S")
        with open(state / "alerts.log", "a", encoding="utf-8") as f:
            f.writelines(f"{stamp} {m}\n" for m in new)
        if "git" in res:
            s["push"] = f"{res['git']} {stamp}"
        save_state(state, s)
        res.update(round=s["round"], time=stamp, total=round(time.time() - t0, 1), msgs=msgs)
        with open(state / "rounds.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
        alerts = (state / "alerts.log").read_text(encoding="utf-8").splitlines()
        status_page(a, state, s, res, alerts)
        print(f"第 {s['round']} 輪：{'發佈 seq ' + str(res.get('seq')) if res.get('published') else '沒有發佈'}"
              + (f"，git {res['git']}" if "git" in res else "") + (f"，{len(new)} 則新警告" if new else ""))
        return res


def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["selftest"])
    ap.add_argument("--prefix")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--every", type=int, default=30)   # 11-27 從 120 秒縮成 30 秒（每頁 1 秒，一輪約 26 秒）
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--state-dir", type=Path)
    ap.add_argument("--epoch", default=fl.DATE)
    ap.add_argument("--date", default=fl.DATE)
    ap.add_argument("--article", action="store_true")
    ap.add_argument("--home-name", default="election-2026-home.html")
    ap.add_argument("--poll-s", type=int)
    ap.add_argument("--heartbeat-min", type=float, default=15)
    ap.add_argument("--delay", type=float, default=fl.DELAY)
    ap.add_argument("--declared", type=Path, default=fl.DATA / "declared.csv")
    ap.add_argument("--overrides", type=Path, default=fl.DATA / "overrides.csv")
    ap.add_argument("--keep", type=Path, help="selftest：把每輪的頁面與 live.json 留在這個資料夾")
    ap.add_argument("--test-banner", action="store_true", help="頁面加「測試資料，非真實結果」與 noindex（彩排用）")
    ap.add_argument("--fast-dir", type=Path, help="快車道：每次發佈先把 live.json 換進這個資料夾（scripts/fast_server.py 給 Funnel 用）")
    ap.add_argument("--fast-url", help="快車道：烤進首頁版的網址（Funnel 上的 live.json）；給空字串就關掉讀者端的快車道")
    a = ap.parse_args(argv)
    # 乾跑另用一份狀態、產出放狀態資料夾裡：不動正式檔，也不讓乾跑記下的雜湊擋掉之後真的那一輪
    a.state_dir = (a.state_dir or HERE / "preview/realtime/state" / (a.epoch + ("-dryrun" if a.dry_run else ""))).resolve()
    a.out_dir = (a.out_dir or (a.state_dir / "out" if a.dry_run else HERE)).resolve()
    if a.dry_run and a.fast_dir:   # 快車道資料夾是讀者直接讀的：乾跑不換進去
        a.fast_dir = a.state_dir / "fast"
    if a.cmd != "selftest":
        if not a.prefix:
            ap.error("要給 --prefix（開票頁片段網址去掉 17 碼區域碼，2022 年是 https://www.cec.gov.tw/zh-TW/TC）")
        probe = next((p for p in (a.out_dir, *a.out_dir.parents) if p.exists()), HERE)
        if not a.dry_run and git("rev-parse", "--show-toplevel", cwd=probe)[0]:
            ap.error("--out-dir 不在 git repo 裡，只能配 --dry-run")
    return a


def main():
    for f in (sys.stdout, sys.stderr):   # pythonw 沒有主控台，這兩個是 None
        if f:
            f.reconfigure(encoding="utf-8")
    a = parse()
    if a.cmd == "selftest":
        return selftest(a.keep)
    while True:
        t = time.time()
        one(a)
        if a.once:
            return
        time.sleep(max(1, a.every - (time.time() - t)))


# ── 自我測試：假中選會（scripts/fake_cec.py，同一個程序裡）＋乾跑，產出都在暫存資料夾 ──
def selftest(keep=None):
    import threading
    from http.server import ThreadingHTTPServer
    import fake_cec as fc
    fc.load(1, True)
    clock = fc.Clock("16:00", 0)   # 0 倍速：時鐘只照測試跳
    srv = ThreadingHTTPServer(("127.0.0.1", 0), fc.handler(clock))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tmp = Path(keep).resolve() if keep else Path(tempfile.mkdtemp(prefix="live_loop_"))
    if keep and tmp.exists():   # git 的物件檔是唯讀的，先改可寫再刪
        shutil.rmtree(tmp, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    (tmp / "out").mkdir(parents=True)
    date = datetime.now().strftime("%Y-%m-%d")   # 假中選會印的是今天的牆上時間
    argv = ["--prefix", f"http://127.0.0.1:{srv.server_address[1]}/zh-TW/TC", "--dry-run", "--out-dir", str(tmp / "out"),
            "--state-dir", str(tmp / "state"), "--epoch", "selftest", "--date", date, "--delay", "0",
            "--declared", str(tmp / "declared.csv"), "--overrides", str(tmp / "overrides.csv")]
    a = parse(argv + (["--keep", str(tmp)] if keep else []))
    a.cmd = None
    names = fl.counties()
    rank = {"pending": 0, "counting": 1, "called": 2, "final": 3}
    seen, last = [], {}

    def at(hm, **kw):
        clock.set(hm)
        for k, v in kw.items():
            setattr(a, k, v)
        res = one(a)
        live =json.loads((a.out_dir / "live.json").read_text(encoding="utf-8"))
        c = {x["code"]: x for x in live["counties"]}
        if res["published"]:   # 只進不退：seq 變大；每縣狀態不退、已送不減（延後與 reset 例外）
            assert not seen or live["seq"] > seen[-1], (seen, live["seq"])
            seen.append(live["seq"])
            for code, x in c.items():
                o = last.get(code)
                if o and x["status"] != "postponed" and o["status"] != "postponed" and code not in a.reset_ok:
                    assert rank[x["status"]] >= rank[o["status"]], (hm, code, o["status"], x["status"])
                    assert (x["stations"] or {}).get("reported", 0) >= (o["stations"] or {}).get("reported", 0), (hm, code)
            last.update(c)
        if fc.status(fc.hm(hm))[fc.EARLY]["status"] == "called" and not a.declared.exists():
            early(hm, res)
        return res, c

    def early(hm, r):   # 屏東：中選會開完前打 ◎，先照開票中發；寫進 declared.csv 才發當選（哪一輪碰到就在哪一輪測）
        x = json.loads((a.out_dir / "live.json").read_text(encoding="utf-8"))["counties"]
        x = next(k for k in x if k["code"] == fc.EARLY)
        assert x["status"] == "counting" and not any(p["elected"] for p in x["cands"]) and "declared.csv" in alerts(r), (hm, x["status"], alerts(r))
        f = fc.COUNTIES[fc.EARLY]
        win = f["people"][f["final"].index(max(f["final"]))][0]
        a.declared.write_text(f"code,candidate\n{fc.EARLY},{win}\n", encoding="utf-8")
        _, c = at(hm)
        assert c[fc.EARLY]["status"] == "called" and [p["name"] for p in c[fc.EARLY]["cands"] if p["elected"]] == [win], c[fc.EARLY]
    alerts = lambda r: " ".join(r["msgs"])
    a.reset_ok = set()
    r, c = at("16:00")
    assert r["published"] and all(x["status"] == "pending" for x in c.values()) and len(c) == 22
    r, c = at("16:00")
    assert not r["published"], "資料沒變不該發佈"
    r, c = at("16:00", heartbeat_min=0)
    assert r["published"] and r["heartbeat"], "heartbeat 0 分鐘：沒變也要發"
    a.heartbeat_min = 15
    r, c = at("17:30")
    assert r["published"] and any(x["status"] == "counting" for x in c.values())
    ilan = dict(c["10002"])
    r, c = at("18:20")   # 宜蘭 404：沿用上一輪
    assert "宜蘭縣" in alerts(r) and c["10002"]["stations"] == ilan["stations"], alerts(r)
    taichung = dict(c["66000"])
    r, c = at("19:40")   # 臺中舊頁：不採用
    assert "臺中市" in alerts(r) and "新資料不採用" in alerts(r) and c["66000"]["stations"]["reported"] >= taichung["stations"]["reported"], alerts(r)
    # reset：人判斷合併擋錯了，臺中下一輪抓到什麼就收什麼（這裡收的是舊頁，所數變少），只用一次
    a.overrides.write_text("code,action,candidate,note\n66000,reset,,\n", encoding="utf-8")
    a.reset_ok = {"66000"}
    t_before = fl.read_csv(a.state_dir / "results.csv")["66000"]["updated"]
    r, c = at("19:40")
    t_after = fl.read_csv(a.state_dir / "results.csv")["66000"]["updated"]
    assert "reset 用掉了" in alerts(r) and t_after < t_before, (alerts(r), t_before, t_after)   # 收下了資料時間比較舊的那頁
    st = json.loads((a.state_dir / "state.json").read_text(encoding="utf-8"))
    assert any(k.startswith("66000|") for k in st["consumed"])
    r, c = at("19:45")
    assert "reset 用掉了" not in alerts(r)
    def until(hm, word):   # 已開完的縣市每 5 輪才重抓，壞頁最多要跑 5 輪才碰得到
        for _ in range(6):
            r, c = at(hm)
            if word in alerts(r):
                return r, c
        raise AssertionError(f"{hm} 跑了 5 輪都沒有「{word}」的警告")
    keelung = dict(c["10017"])
    r, c = until("20:10", "基隆市：資料時間")   # 基隆資料時間在未來：不採用
    assert "晚 5 分鐘" in alerts(r) and c["10017"]["updated"] == keelung["updated"], alerts(r)
    ntpc = dict(c["65000"])
    r, c = until("20:40", "新北市")   # 新北全 0：不採用
    assert c["65000"]["cands"] == ntpc["cands"], alerts(r)
    # 延後：人在 overrides.csv 設，抓到什麼都不蓋；reset：臺中下一輪收什麼都照收（一次）
    a.overrides.write_text("code,action,candidate,note\n10020,postponed,,選舉延後（測試）\n", encoding="utf-8")
    r, c = at("20:45")
    assert c["10020"]["status"] == "postponed" and c["10020"]["note"] == "選舉延後（測試）", c["10020"]
    # force：找一個還在開的縣，把第二名當成宣布當選的人照發（落後也發，由人決定）；名字不在前兩名就不套用
    r, c = at("21:00")
    code = next(k for k, x in sorted(c.items()) if x["status"] == "counting" and k not in fc.SPECIAL and k not in (fc.EARLY, fc.TIE))
    second = c[code]["cands"][1]["name"]
    a.overrides.write_text(f"code,action,candidate,note\n10020,postponed,,選舉延後（測試）\n{code},force,{second},\n10007,force,不存在的人,\n", encoding="utf-8")
    r, c = at("21:00")
    assert [p["name"] for p in c[code]["cands"] if p["elected"]] == [second] and c[code]["status"] == "called", c[code]
    assert "不存在的人" in alerts(r), alerts(r)
    a.reset_ok = {code}   # 拿掉 force 就退回開票中（人決定的，不算倒退）
    t_early = next(f"{t // 60:02d}:{t % 60:02d}" for t in range(16 * 60, 24 * 60) if fc.status(t)[fc.EARLY]["status"] == "called")
    if not a.declared.exists() and t_early > "21:00":
        at(t_early)
    assert a.declared.exists(), f"屏東提早 ◎ 的時段（{t_early} 起）沒有任何一輪碰到，換一組時間"
    # 開完：除了延後的嘉義市，21 縣 final；連江同票沒有當選人
    a.overrides.write_text("code,action,candidate,note\n10020,postponed,,選舉延後（測試）\n", encoding="utf-8")
    r, c = at("23:59", article=True, test_banner=True)
    assert all(x["status"] == "final" for k, x in c.items() if k != "10020"), {k: x["status"] for k, x in c.items()}
    assert "測試資料，非真實結果" in (a.out_dir / "election-2026-home.html").read_text(encoding="utf-8")
    assert c["09007"]["note"] == "同票，抽籤決定" and not any(p["elected"] for p in c["09007"]["cands"])
    assert (a.out_dir / ARTICLE).exists() and (a.out_dir / "election-2026-home.html").exists()
    # 快車道：給了 --fast-url 就算資料沒變也重發一版；live.json 換進快車道資料夾、內容一樣，首頁版與 live.json 都帶那個網址
    r, c = at("23:59", fast_dir=tmp / "fast", fast_url="https://fast.example/live.json")
    fast = (tmp / "fast" / "live.json").read_text(encoding="utf-8")
    assert r["published"] and fast == (a.out_dir / "live.json").read_text(encoding="utf-8"), "快車道的 live.json 要跟這輪發的一樣"
    assert json.loads(fast)["fast_url"] == "https://fast.example/live.json" and "fast.example" in (a.out_dir / "election-2026-home.html").read_text(encoding="utf-8")
    assert not (tmp / "fast" / "live.json.tmp").exists(), "暫存檔要換名換掉"
    (tmp / "fast" / "live.json").unlink()   # 快車道的檔不見了（或上一輪沒換成）：資料沒變也要補上
    r, c = at("23:59")
    assert not r["published"] and (tmp / "fast" / "live.json").read_text(encoding="utf-8") == fast, "沒發佈的輪也要把快車道補齊"
    assert parse(argv + ["--fast-dir", str(tmp / "real-fast")]).fast_dir == a.state_dir / "fast", "乾跑不能換進給讀者的資料夾"
    a.fast_dir = a.fast_url = None
    # 鎖：另一個程序拿著鎖的時候，這輪不跑
    with locked(a.state_dir) as ok:
        assert ok
        lock_src = f"import sys; sys.path.insert(0, {str(HERE / 'scripts')!r}); import live_loop as L; from pathlib import Path\nwith L.locked(Path({str(a.state_dir)!r})) as ok: print(ok)"
        assert subprocess.run([sys.executable, "-I", "-c", lock_src], capture_output=True, text=True).stdout.strip() == "False"
    # git：暫存的 bare repo 當遠端；另一個 clone 先推一個 commit，迴圈的 push 會被拒，要 pull --rebase 再推成功，commit 只含那兩個檔
    gt = tmp / "git"
    sh = lambda *x, cwd=gt: subprocess.run(["git", *x], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
    gt.mkdir()
    sh("init", "--bare", "-b", "main", "remote.git")
    for d in ("work", "other"):
        sh("clone", "remote.git", d)
        sh("config", "researchlab.lang", "en", cwd=gt / d)
    (gt / "work/README.md").write_text("test repo\n", encoding="utf-8")
    (gt / "work/stray.txt").write_text("someone else's change, not staged\n", encoding="utf-8")
    sh("add", "README.md", cwd=gt / "work")
    sh("commit", "-m", "chore(test): seed the test repository", cwd=gt / "work")
    sh("push", "origin", "main", cwd=gt / "work")
    sh("pull", "origin", "main", cwd=gt / "other")
    (gt / "other/other.txt").write_text("pushed from another clone\n", encoding="utf-8")
    (gt / "other/live").mkdir()
    (gt / "other/live/live.json").write_text('{"from":"another clone"}\n', encoding="utf-8")   # 同一個檔：rebase 會衝突，要由這台的版本勝出
    sh("add", "other.txt", "live/live.json", cwd=gt / "other")
    sh("commit", "-m", "chore(test): add a commit from another clone", cwd=gt / "other")
    sh("push", "origin", "main", cwd=gt / "other")
    (gt / "work/live").mkdir()
    b = parse([x for x in argv if x != "--dry-run"] + ["--out-dir", str(gt / "work/live"), "--state-dir", str(gt / "state")])   # 後寫的蓋過前面的
    b.cmd = None
    r = one(b)
    files = sh("show", "--name-only", "--format=%s", "HEAD", cwd=gt / "remote.git").splitlines()
    assert r["git"] == "pushed" and files[0].startswith("chore(election-2026): update live results to"), (r.get("git"), r["msgs"], files)
    assert sorted(files[2:]) == ["live/election-2026-home.html", "live/live.json"], files   # 只有這兩個檔，stray.txt 沒被帶進去
    assert (gt / "work/other.txt").exists() and "stray.txt" in sh("status", "--porcelain", cwd=gt / "work")
    assert json.loads(sh("show", "HEAD:live/live.json", cwd=gt / "remote.git"))["epoch"] == "selftest"   # 衝突時這台產生的那版勝出
    r = one(b)
    assert not r["published"] and "git" not in r, r
    srv.shutdown()
    if not keep:
        shutil.rmtree(tmp, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
        tmp = "（暫存資料夾已刪）"
    print(f"live_loop selftest OK：發佈 {len(seen)} 次、seq 一直變大、各縣不倒退；404、舊頁、未來時間、全 0 都擋下；延後、force、"
          f"提早 ◎ 等 declared.csv 都照規則；沒變不發、心跳會發；鎖有效；暫存 repo 的 push 被拒會 rebase 再推、只 commit 那兩個檔。產出在 {tmp}")


if __name__ == "__main__":
    main()
