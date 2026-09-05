# 장면꾸미기 작업대 — 로컬 전용. 라이브 렌더 코드(deco_frame.render)를 그대로 불러 PNG를 돌려준다.
# 실행: 시작.bat  (또는 py server.py) → http://127.0.0.1:8766
import sys, os, io, json, hashlib, pathlib, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent            # 로또의 주식
TRACK = ROOT / ".tracks" / "장면꾸미기재편"   # ★코드 수정은 트랙 폴더에서(흡수 방지). 있으면 그 코드로 그린다
CODE_ROOT = TRACK if (TRACK / "shopping_shorts").exists() else ROOT
sys.path.insert(0, str(CODE_ROOT))
from shopping_shorts import deco_frame as d   # noqa: E402
from shopping_shorts import video_assemble as va   # noqa: E402
import tempfile

TPL_DIR = CODE_ROOT / "shopping_shorts" / "static" / "templates"
FONT_DIR = CODE_ROOT / "shopping_shorts" / "static" / "fonts"
_cache = {}

SAMPLE = {"channel": "살림킹왕짱", "title": "바닥 세정제 추천\n이거 하나면 끝나요", "ad_badge": True}

def _group(pid):
    if pid.startswith("sul_"): return "썰채널형"
    if pid.startswith("news_"): return "커뮤니티"
    if pid.startswith("plain_"): return "빈 틀"
    return "기타"

def presets():
    out = []
    for pid, p in d.PRESETS.items():
        n = d.normalize({"preset": pid})
        out.append({"id": pid, "name": p.get("name"), "group": _group(pid),
                    "bar": p.get("bar"), "on_bar": p.get("on_bar"), "bar_h": n.get("bar_h"),
                    "headcopy": p.get("headcopy"), "caption": p.get("caption")})
    return out

_BG = None
def _bg():
    global _BG
    if _BG is None:
        from PIL import Image
        _BG = Image.open(HERE / "bg.jpg").convert("RGBA")
    return _BG

def render_png(spec, size, on_bg=False):
    key = hashlib.md5((json.dumps(spec, sort_keys=True, ensure_ascii=False) + str(size) + str(on_bg)).encode()).hexdigest()
    if key in _cache: return _cache[key]
    im = d.render(spec)
    if on_bg:  # 카드 썸네일: 실제 영상 프레임 위에 얹어 결과물처럼 보이게
        base = _bg().resize(im.size); base.alpha_composite(im); im = base.convert("RGB")
    if size: im = im.resize(size)
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    _cache[key] = b.getvalue()
    return _cache[key]

def hc_png(hc, size):
    """헤드카피(큰 제목) 한 장 — 라이브와 같은 함수(video_assemble.headcopy_layer_png)로 굽는다."""
    try: open(str(HERE / "last_hc.json"), "w", encoding="utf-8").write(json.dumps(hc, ensure_ascii=False, indent=1))
    except Exception: pass
    key = "hc" + hashlib.md5((json.dumps(hc, sort_keys=True, ensure_ascii=False) + str(size)).encode()).hexdigest()
    if key in _cache: return _cache[key]
    from PIL import Image
    with tempfile.TemporaryDirectory() as w:
        out = va.headcopy_layer_png(hc, pathlib.Path(w) / "hc.png", w)
        if not out:
            im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        else:
            im = Image.open(out).convert("RGBA")
    if size: im = im.resize(size)
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    _cache[key] = b.getvalue()
    return _cache[key]

def cap_png(style, text, size):
    """자막 한 줄 — 라이브와 같은 함수(video_assemble._segmented_drawtext, single_line)로 굽는다.
    위치·크기 환산은 _caption_drawtexts와 같은 식(0순위-B: 값을 두 번 정하지 않는다)."""
    key = "cap" + hashlib.md5((json.dumps(style, sort_keys=True, ensure_ascii=False) + text + str(size)).encode()).hexdigest()
    if key in _cache: return _cache[key]
    from PIL import Image
    import shutil
    im = Image.new("RGBA", (va._OUT_W, va._OUT_H), (0, 0, 0, 0))
    if text.strip():
        with tempfile.TemporaryDirectory() as w:
            wp = pathlib.Path(w)
            f = va._resolve_font()
            if f: shutil.copy(f, wp / "font.ttf")
            sz = max(10, va._ui_px(style.get("size"), va._CAP_FONTSIZE))
            ypct = style.get("y_pct")
            if ypct is None:
                ypct = max(0.0, min(100.0, (va._OUT_H - 150 - sz * 0.6) / va._OUT_H * 100.0))
            xpct = style.get("x_pct"); xpct = 50.0 if xpct is None else max(0.0, min(100.0, float(xpct)))
            parts = va._segmented_drawtext(text, style, wp, "cap", xpct, ypct,
                                           highlight_rules=style.get("highlight_rules"),
                                           default_color="0xFFFFFF", single_line=True)
            out = wp / "cap.png"
            if parts:
                va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black@0.0:s={va._OUT_W}x{va._OUT_H}:d=1,format=rgba",
                                "-vf", ",".join(parts), "-frames:v", "1", str(out)], cwd=str(wp))
                if out.exists(): im = Image.open(out).convert("RGBA")
    if size: im = im.resize(size)
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    _cache[key] = b.getvalue()
    return _cache[key]

def _backup_state():
    """state.json을 덮어쓰기 직전에 backup/ 으로 복사한다.

    2026-09-05 사고: 다른 PC에서 마무리한 값을, 이 PC 브라우저를 여는 것만으로
    덮어써 잃을 뻔했다(hydrateFromFile은 파일이 더 새로울 때만 이긴다).
    되돌릴 수단이 하나도 없던 게 진짜 문제였다 — 그래서 여기서 무조건 남긴다.
    """
    src = HERE / "state.json"
    if not src.exists():
        return
    try:
        import shutil, time as _t
        bdir = HERE / "backup"
        bdir.mkdir(exist_ok=True)
        shutil.copy2(src, bdir / ("state_%s.json" % _t.strftime("%m%d_%H%M%S")))
        olds = sorted(bdir.glob("state_*.json"))
        for f in olds[:-20]:      # 최근 20벌만 남긴다
            f.unlink()
    except Exception:
        pass


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(HERE), **k)
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # 정적 파일도 캐시 금지 — 고치고 새로고침하면 바로 새 화면
        super().end_headers()
    def _send(self, body, ctype):
        self.send_response(200); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/state":   # 브라우저가 만진 값 전부(기본값·프리셋·자막세트·마지막 상태) → state.json
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n)
            try:
                json.loads(body.decode("utf-8"))
                _backup_state()          # ★덮어쓰기 전에 직전 값을 남긴다(2026-09-05 유실 사고)
                (HERE / "state.json").write_bytes(body)
                return self._send(b'{"ok":true}', "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": repr(e)}).encode(), "application/json")
        self.send_response(404); self.end_headers()
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/presets":
                return self._send(json.dumps(presets(), ensure_ascii=False).encode(), "application/json")
            if u.path == "/fonts":
                fs = sorted(f.name for f in FONT_DIR.iterdir() if f.suffix.lower() in (".ttf", ".otf"))
                return self._send(json.dumps(fs, ensure_ascii=False).encode(), "application/json")
            if u.path.startswith("/thumb/"):
                pid = u.path.split("/", 2)[2]
                return self._send(render_png(dict(SAMPLE, preset=pid), (135, 240), on_bg=True), "image/png")
            if u.path == "/render":
                spec = json.loads(q.get("spec", ["{}"])[0])
                return self._send(render_png(spec, (540, 960)), "image/png")
            if u.path == "/hc":
                hc = json.loads(q.get("hc", ["{}"])[0])
                return self._send(hc_png(hc, (540, 960)), "image/png")
            if u.path == "/fit":   # 썸네일의 '처음 한 번 폭에 맞추기' — 렌더 축소식(_SAFE_W·×1.5)과 같은 계산
                hc = json.loads(q.get("hc", ["{}"])[0])
                from PIL import ImageFont
                ui = float(hc.get("size") or 86); px = max(8, int(round(ui * 1.5)))
                fp = FONT_DIR / (hc.get("font") or "Pretendard-ExtraBold.otf")
                try: f = ImageFont.truetype(str(fp), px)
                except OSError: f = ImageFont.load_default()
                lines = [ln for ln in str(hc.get("text") or "").splitlines() if ln.strip()]
                widest = max((f.getlength(ln) for ln in lines), default=0)
                max_w = va._SAFE_W * va._OUT_W
                fit = ui if widest * 1.04 <= max_w or widest == 0 else max(8, int(ui * max_w / widest * 0.96))
                # keep=1 이면 크기는 그대로 두고, 그 크기에서 실제로 몇 줄로 접히는지 센다(띠 높이 계산용)
                keep = q.get("keep", ["0"])[0] == "1"
                use = ui if keep else fit
                try: f2 = ImageFont.truetype(str(fp), max(8, int(round(use * 1.5))))
                except OSError: f2 = f
                nlines = 0
                for ln in lines:
                    words = ln.split(" "); cur = ""; cnt = 1
                    for w in words:
                        cand = (cur + " " + w).strip()
                        if cur and f2.getlength(cand) > max_w: cnt += 1; cur = w
                        else: cur = cand
                    nlines += cnt
                return self._send(json.dumps({"size": use, "lines": max(1, nlines), "widest": int(widest), "max_w": int(max_w)}).encode(), "application/json")
            if u.path == "/cap":
                style = json.loads(q.get("style", ["{}"])[0]); text = q.get("text", [""])[0]
                return self._send(cap_png(style, text, (540, 960)), "image/png")
            if u.path == "/segs":   # 라이브와 같은 줄 나누기 규칙(_caption_segments)
                text = q.get("text", [""])[0]
                return self._send(json.dumps(va._caption_segments(text), ensure_ascii=False).encode(), "application/json")
            if u.path.startswith("/tpl/"):
                f = TPL_DIR / pathlib.Path(u.path).name
                return self._send(f.read_bytes(), "image/png")
        except Exception as e:  # 렌더 실패는 화면에서 보여야 한다
            body = json.dumps({"error": repr(e)}, ensure_ascii=False).encode()
            self.send_response(500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
        return super().do_GET()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    import socket
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _s.connect(("8.8.8.8", 80)); lan = _s.getsockname()[0]; _s.close()
    except Exception:
        lan = "(IP 확인 실패)"
    print(f"장면꾸미기 작업대: http://127.0.0.1:{port}/  (프리셋 {len(d.PRESETS)}종, 코드={CODE_ROOT})")
    print(f"  ★다른 PC에서 열기(같은 와이파이): http://{lan}:{port}/")
    # 0.0.0.0 = 같은 와이파이의 다른 PC(아무것도 안 깔린 PC)에서 브라우저만으로 접속 (2026-09-04)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
