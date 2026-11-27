"""開票夜的快車道：把迴圈寫好的 live.json 經 Tailscale Funnel 直接給讀者，不用等 Pages 部署（SPEC〈首頁版即時更新〉快車道）。

只服務一個檔：GET／HEAD `/live.json`（查詢字串不管），其他路徑一律 404，不列目錄；只綁 127.0.0.1，由 `tailscale funnel` 對外。
檔案放在記憶體裡，mtime 或大小變了才重讀：迴圈每輪換檔時伺服器幾乎不會開著那個檔（Windows 上開著就換不了名），換檔瞬間讀不到就給上一版。
回應帶 `Access-Control-Allow-Origin: *`（首頁版在 github.io，跨站抓）、`Cache-Control: no-cache`、`Last-Modified`，
`If-Modified-Since` 跟上次給的一樣就回 304；讀者收 gzip 就給壓過的（20 KB 壓成 4 KB，Funnel 有頻寬上限）。
連線 10 秒沒動靜就斷（擋慢速連線）；Windows 上把自己的優先權降到「低於標準」，讀者多時不搶迴圈的 CPU。

用法（在 election-2026 資料夾）：
  python -I scripts/fast_server.py <資料夾> [--port 18799] [--log]
  python -I scripts/fast_server.py selftest
對外：`tailscale funnel --bg 18799`；關掉：`tailscale funnel --https=443 off`。
"""
import argparse
import email.utils
import gzip
import os
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PATH = "/live.json"


def handler(folder, log=False):
    target = Path(folder) / "live.json"
    cur, lock = [None], threading.Lock()   # ((mtime_ns, 大小), 內容, gzip 過的內容, Last-Modified)：整組一起換，不會讀到一半新一半舊

    def snapshot():
        try:
            st = target.stat()
            key = (st.st_mtime_ns, st.st_size)
            if not cur[0] or cur[0][0] != key:
                with lock:
                    if not cur[0] or cur[0][0] != key:
                        body = target.read_bytes()
                        cur[0] = (key, body, gzip.compress(body, 6), email.utils.formatdate(st.st_mtime, usegmt=True))
        except OSError:   # 迴圈還沒寫過，或剛好在換檔：有上一版就給上一版
            pass
        return cur[0]

    class H(BaseHTTPRequestHandler):
        timeout = 10                     # 每條連線 10 秒沒動靜就斷（Funnel 那頭的慢速連線由 tailscaled 先擋，這裡管本機這段）
        protocol_version = "HTTP/1.1"
        server_version, sys_version = "fast", ""   # 不在 Server 標頭露出 Python 版本

        def _common(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Vary", "Accept-Encoding")
            if self.headers.get("Content-Length") or self.headers.get("Transfer-Encoding"):
                self.send_header("Connection", "close")   # 帶 body 的請求不重用連線：沒讀掉的 body 會被當成下一個請求（Funnel 共用連線時會錯位）

        def _empty(self, code):
            self.send_response(code)
            self._common()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_OPTIONS(self):            # 跨站預檢：照樣放行，一天內不用再問
            self.send_response(204)
            self._common()
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Max-Age", "86400")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_HEAD(self):
            self._serve(body=False)

        def do_GET(self):
            self._serve(body=True)

        def _serve(self, body):
            snap = snapshot() if self.path.split("?", 1)[0] == PATH else None
            if not snap:
                return self._empty(404)
            _, raw, gz, lm = snap
            if self.headers.get("If-Modified-Since") == lm:   # 瀏覽器原樣帶回上次的 Last-Modified：只比字串，不解析日期
                return self._empty(304)
            data = gz if "gzip" in self.headers.get("Accept-Encoding", "") else raw
            self.send_response(200)
            self._common()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Last-Modified", lm)
            if data is gz:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if body:
                self.wfile.write(data)

        def log_message(self, fmt, *args):
            if log:
                sys.stdout.write("%s %s\n" % (self.log_date_time_string(), fmt % args))
                sys.stdout.flush()

    return H


class Server(ThreadingHTTPServer):
    request_queue_size = 128   # listen() 在建構時就叫了，要寫在類別上才有效（預設 5）

    def handle_error(self, request, client_address):   # 讀者那頭先斷線（逾時放棄）很常見，不印整段 traceback
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


def serve(folder, port, log=False):
    if os.name == "nt":   # 低於標準（BELOW_NORMAL_PRIORITY_CLASS）：讀者一多也不搶迴圈的 CPU
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    return Server(("127.0.0.1", port), handler(folder, log))


def selftest():
    d = Path(tempfile.mkdtemp())
    srv = serve(d, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def req(path, method="GET", headers=None):
        r = urllib.request.Request(base + path, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    assert req(PATH)[0] == 404, "還沒有檔案時要 404"
    (d / "live.json").write_text('{"seq": 1}', encoding="utf-8")
    (d / "secret.txt").write_text("x", encoding="utf-8")
    code, h, b = req(PATH + "?t=1")
    assert code == 200 and b == b'{"seq": 1}', (code, b)
    assert h["Access-Control-Allow-Origin"] == "*" and h["Cache-Control"] == "no-cache" and "Last-Modified" in h, h
    assert "Python" not in h.get("Server", ""), h.get("Server")
    lm = h["Last-Modified"]
    assert req(PATH, headers={"If-Modified-Since": lm})[0] == 304, "沒變要回 304"
    for bad in ("Thu, 01 Jan 1970 00:00:00", "Mon, 01 Jan 9999 00:00:00 GMT", "garbage"):   # 怪日期不能打掛請求
        assert req(PATH, headers={"If-Modified-Since": bad})[0] == 200, bad
    code, h, b = req(PATH, headers={"Accept-Encoding": "gzip, deflate, br"})
    assert code == 200 and h.get("Content-Encoding") == "gzip" and gzip.decompress(b) == b'{"seq": 1}', (code, h)
    assert req(PATH, method="HEAD")[0] == 200
    for p in ("/", "/secret.txt", "/live.json/", "/LIVE.JSON", "/../secret.txt", "/%2e%2e/secret.txt"):
        assert req(p)[0] == 404, p
    assert req(PATH, method="POST")[0] == 501, "只收 GET、HEAD"
    r = urllib.request.Request(base + PATH, data=b"GET /", method="GET")   # 帶 body 的 GET：回完就關連線
    with urllib.request.urlopen(r, timeout=5) as resp:
        assert resp.status == 200 and resp.headers.get("Connection") == "close", dict(resp.headers)
    code, h, _ = req(PATH, method="OPTIONS")
    assert code == 204 and h["Access-Control-Allow-Origin"] == "*", (code, h)
    (d / "live.json").unlink()   # 換檔瞬間讀不到：給上一版，不回 404
    assert req(PATH) == req(PATH) and req(PATH)[2] == b'{"seq": 1}'
    time.sleep(1.1)
    (d / "live.json").write_text('{"seq": 2}', encoding="utf-8")
    code, _, b = req(PATH, headers={"If-Modified-Since": lm})
    assert code == 200 and b == b'{"seq": 2}', (code, b)
    srv.shutdown()
    print("fast_server selftest OK：只給 /live.json、其他路徑 404、跨站與不快取標頭都在、沒變回 304、怪日期照給、gzip、"
          "帶 body 就關連線、換檔瞬間給上一版、只收 GET／HEAD")


def main():
    if sys.argv[1:2] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--port", type=int, default=18799)
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()
    srv = serve(a.folder, a.port, a.log)
    print(f"快車道：http://127.0.0.1:{a.port}{PATH} ← {Path(a.folder) / 'live.json'}（對外用 tailscale funnel --bg {a.port}）", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
