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


def run_insert(q):
    cmd = ("set -a; . /etc/shopping-shorts.env; set +a; cd /home/ubuntu/lotto-stock-wiki && "
           "timeout 300 python3 /tmp/storyboard_trial.py insert %s 2>/dev/null | grep '^RESULT' | cut -c8-") % "".join(ch for ch in q["jid"] if ch.isalnum())
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, HOST, cmd], input=json.dumps({"board": q["board"], "extra": q.get("extra") or []}, ensure_ascii=False),
                       capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(r.stdout.strip() or "{}")
    except ValueError:
        return {"_err": (r.stderr or r.stdout)[-300:]}


MEME_DIR = r"C:/Users/TheRose/Desktop/로또의 주식/research/meme_pack"   # 감정짤밈팩 트랙(관제 121)이 만드는 팩 — 실험실 8765가 파일을 준다


def meme_list():
    """밈팩 표 = library/manifest.json(쓸 수 있는 클립) + state.json(뷰어에서 지움·감정 옮김). 표는 여기서 만들지 않고 읽기만."""
    import os
    try:
        m = json.load(open(os.path.join(MEME_DIR, "library", "manifest.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {"clips": [], "err": "밈팩 표가 아직 없어요"}
    try:
        st = json.load(open(os.path.join(MEME_DIR, "state.json"), encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    out = []
    for c in m.get("clips") or []:
        s_ = st.get(c.get("id")) or {}
        if not c.get("usable") or s_.get("deleted"):
            continue
        out.append({"id": c["id"], "emotion": s_.get("emotion") or c.get("emotion"), "dur": c.get("dur"), "what": c.get("what") or ""})
    return {"clips": out, "base": "http://127.0.0.1:8765/library"}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/meme"):
            b = json.dumps(meme_list(), ensure_ascii=False).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.end_headers(); self.wfile.write(b)
            return
        body = open(PAGE, "rb").read()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        q = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/signals":      # 신호어 새 풀(관제 120) — 로컬 트랙 코드로 바로 적용(3.6 호출 없음, 판단은 storyboard.apply_signals 한 곳)
            import os as _os, sys as _sys
            _sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..")))
            from shopping_shorts import story_writer as _sw, storyboard as _sb
            tok = _sw.SIGNAL_POOL.set(bool(q.get("pool", True)))
            try:
                slots = [dict(x) for x in (q.get("board") or {}).get("slots") or []]
                words = _sb.apply_signals(slots, q.get("key") or "", int(q.get("nth") or 0), bool(q.get("yt", True)))
            finally:
                _sw.SIGNAL_POOL.reset(tok)
            b = json.dumps({"slots": slots, "words": words}, ensure_ascii=False).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.end_headers(); self.wfile.write(b)
            return
        if self.path == "/insert":
            b = json.dumps(run_insert(q), ensure_ascii=False).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.end_headers(); self.wfile.write(b)
            return
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
