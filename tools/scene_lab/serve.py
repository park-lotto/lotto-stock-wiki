# -*- coding: utf-8 -*-
"""실험 페이지용 정적 서버 — Range(구간 요청) 지원.

기본 http.server는 Range를 무시하고 200으로 전체를 준다. 그러면 <video>가
currentTime으로 특정 지점을 못 찾아(시크 불가) 미리보기가 안 돈다.
그래서 206 Partial Content를 직접 처리한다.
"""
import os
import re
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
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
