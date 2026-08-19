# -*- coding: utf-8 -*-
"""실험 페이지용 정적 서버 — Range(구간 요청) 지원.

기본 http.server는 Range를 무시하고 200으로 전체를 준다. 그러면 <video>가
currentTime으로 특정 지점을 못 찾아(시크 불가) 미리보기가 안 돈다.
그래서 206 Partial Content를 직접 처리한다.
"""
import json
import os
import re
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)   # retts를 import 하려고
# 인자 = job_id(=out/<job_id>) 또는 폴더 경로. 없으면 out/ 안에서 가장 최근 잡을 연다.
_arg = sys.argv[1] if len(sys.argv) > 1 else None
if _arg and os.path.isdir(_arg):
    BASE = os.path.abspath(_arg)
elif _arg:
    BASE = os.path.join(_HERE, "out", _arg)
else:
    _out = os.path.join(_HERE, "out")
    _dirs = [os.path.join(_out, d) for d in os.listdir(_out)] if os.path.isdir(_out) else []
    _dirs = [d for d in _dirs if os.path.isfile(os.path.join(d, "index.html"))]
    if not _dirs:
        sys.exit("열 잡이 없다 — 먼저 py tools/scene_lab/fetch.py 를 돌려라")
    BASE = max(_dirs, key=os.path.getmtime)
if not os.path.isfile(os.path.join(BASE, "index.html")):
    sys.exit(f"index.html이 없다: {BASE}\n먼저 fetch.py로 받아라")
PORT = int(os.environ.get("SCENE_LAB_PORT", "8777"))


class RangeHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        """★'음성·자막 다시 뽑기'(2026-08-14). 브라우저는 서버에 SSH를 못 하니 이 로컬 서버가
        대신 부른다. 라이브와 같은 코드(tts.synthesize_tts / _caption_segments)로 만들어
        받아오므로 자막이 어긋날 수 없다 — JS로 다시 나누면 두 벌이 된다(0순위-B)."""
        if self.path not in ("/retts", "/apply"):
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8"))
            job = os.path.basename(BASE)
            if self.path == "/apply":
                # ★서버 반영(2026-08-15 사장님 "거기서 어떻게 되는지를 보고 판단해야해").
                #   편성·트림·늘려채우기를 라이브 잡 edit_plan에 얹는다(apply.py가 SSH로).
                #   body["revert"]=true면 얹은 것만 걷어내 원래 편집안으로.
                import apply as _apply
                msg = _apply.apply(job, payload=body.get("payload"),
                                   revert=bool(body.get("revert")))
                out = json.dumps({"ok": True, "msg": str(msg)[-300:]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
                return
            import retts as _retts
            meta = _retts.retts(job, int(body["beat_idx"]), body["text"])
            out = json.dumps({"ok": True, "dur": meta["dur"],
                              "captions": meta["captions"]}).encode("utf-8")
            self.send_response(200)
        except (Exception, SystemExit) as e:       # 실패해도 페이지는 살아 있어야 한다
            # ★retts는 잘못된 입력에 sys.exit를 부른다(SystemExit는 Exception이 아니라
            #   BaseException이라 안 잡히면 응답이 통째로 비어 버린다, 실측 000).

            out = json.dumps({"ok": False, "error": str(e)[:300]}).encode("utf-8")
            self.send_response(500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()

        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().send_head()

        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return super().send_head()

        size = os.path.getsize(path)
        start_s, end_s = m.group(1), m.group(2)
        if start_s == "":                      # bytes=-N (끝에서 N바이트)
            start = max(0, size - int(end_s or 0))
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416)
            return None

        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()                     # Accept-Ranges는 end_headers가 붙인다
        self._range_left = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "_range_left", None)
        if left is None:
            return super().copyfile(source, outputfile)
        self._range_left = None
        while left > 0:
            chunk = source.read(min(64 * 1024, left))
            if not chunk:
                break
            outputfile.write(chunk)
            left -= len(chunk)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        SimpleHTTPRequestHandler.end_headers(self)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}/index.html"
    # ★윈도우 콘솔은 cp949라 em-dash 같은 문자에서 UnicodeEncodeError로 죽는다(실측).
    #   출력 때문에 서버가 안 뜨는 건 본말전도 — 인코딩 불가 문자는 조용히 흘린다.
    try:
        print(f"장면 실험실 - {os.path.basename(BASE)}\n{url}\n(끄려면 Ctrl+C)")
    except UnicodeEncodeError:
        print(url)
    try:
        webbrowser.open(url)
    except Exception:                       # 브라우저 자동열기 실패는 치명적이지 않다
        pass
    handler = partial(RangeHandler, directory=BASE)
    ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()
