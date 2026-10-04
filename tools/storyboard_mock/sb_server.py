# 시안 시험 서버(PC, 127.0.0.1:8790) — 페이지를 주고, [스토리보드 만들기]를 누르면 운영 서버에서 3.6(버텍스)을 실제로 돌려 결과를 받아 온다.
# 스타일마다 ssh 하나씩 동시에 돌린다(스타일당 약 35초). 운영 DB·라이브 화면은 바꾸지 않는다(읽기 전용 시험 도구).
import json, os, subprocess, threading, http.server, socketserver, urllib.parse
KEY = r"C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.35.251.172"
PAGE = r"C:/Users/TheRose/Desktop/1·2단계_페이지틀_20261004.html"


def run_one(jid, key, roles, out, extra="", prev=""):
    cmd = ("set -a; . /etc/shopping-shorts.env; set +a; cd /home/ubuntu/lotto-stock-wiki && "
           "timeout 300 python3 /tmp/storyboard_trial.py gen %s %s '' %s %s %s 2>/dev/null | grep '^RESULT' | cut -c8-") % (
        jid, key, "'" + roles.replace("'", "") + "'", "'" + "".join(ch for ch in extra if ch.isalnum() or ch == ",") + "'", "'" + "".join(ch for ch in prev if ch.isalnum() or ch in ",_") + "'")
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, HOST, cmd], capture_output=True, text=True, encoding="utf-8")
    try:
        out.update(json.loads(r.stdout.strip() or "{}"))
    except ValueError:
        out["_err_" + key] = (r.stderr or r.stdout)[-300:]


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = open(PAGE, "rb").read()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        q = json.loads(self.rfile.read(n) or b"{}")
        out, ths = {}, []
        for k in q.get("keys") or []:
            t = threading.Thread(target=run_one, args=(q["jid"], str(k), q.get("roles") or "", out, q.get("extra") or "", q.get("prev") or "")); t.start(); ths.append(t)
        for t in ths:
            t.join()
        b = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass


class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    S(("127.0.0.1", 8790), H).serve_forever()
