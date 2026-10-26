# -*- coding: utf-8 -*-
"""엔진 흐름 진행판(사장님 10-27 "진행판을 보면서 수정하고 승인 / 어디서 막히는지 / 100% 자동도, 단계별 컨펌도").

flow_dev.py 가 작업 폴더에 남기는 기록(flow_log.jsonl · flow_state.json · job/reviews/* · sign.json)을 **읽기만** 해서 브라우저에 보여준다.
단계 이름·순서는 flow.FORMAT_STAGES·flow._stage 가 주인 — 이 파일은 단계를 새로 적지 않는다.
버튼은 flow_dev 를 그대로 다시 부른다: 승인 = --resume --approve · 다시 시도 = --resume --retry · 시작 = --ref --version.

    PYTHONUTF8=1 py -m tools.calcopy.hybrid.flow_board --work <작업 폴더> [--port 8765] [--open]
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import flow  # noqa: E402

HTML = Path(__file__).with_name("flow_board.html")
_proc: dict = {"p": None}


def read_log(W: Path) -> list[dict]:
    rows = []
    try:
        for ln in (W / "flow_log.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except ValueError:
                pass
    except OSError:
        pass
    return rows


def reviews(W: Path) -> list[dict]:
    out = []
    d = W / "job" / "reviews"
    for r in sorted(d.glob("*")) if d.exists() else []:
        if not r.is_dir():
            continue
        ask = (r / "ask.txt").read_text(encoding="utf-8") if (r / "ask.txt").exists() else ""
        ans = (r / "answer.json").read_text(encoding="utf-8") if (r / "answer.json").exists() else ""
        imgs = [str(p.relative_to(W)).replace("\\", "/") for p in sorted(r.iterdir()) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        out.append({"dir": r.name, "ask": ask[:4000], "answer": ans[:4000], "imgs": imgs})
    return out


def state(W: Path) -> dict:
    """화면 한 장에 필요한 것 — 단계표(엔진) · 지금 단계 · 기록 · 판정 · 사인 대기 · 끝."""
    log = read_log(W)
    st = {}
    try:
        st = json.loads((W / "flow_state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    start = next((r for r in log if "start" in r), {})
    stages = start.get("stages") or [t for _, t in flow.FORMAT_STAGES.get(st.get("fmt") or "", flow.STAGES)]
    hi = None                           # 세부 단계 → 회원에게 보이는 단계(엔진 함수 그대로). 한 실행 안에선 뒤로 가지 않는다
    for r in log:                       # (stopped·task_got 은 엔진 표에서 '준비 확인'이라 그대로 쓰면 멈춘 자리가 1단계로 보인다)
        if "start" in r:
            hi = None
        if r.get("phase"):
            try:
                s = flow._stage(r["phase"], st)
            except Exception:  # noqa: BLE001
                s = None
            if s and (hi is None or s["no"] >= hi["no"]):
                hi = s
            r["stage"] = hi
    cur = flow._stage(st["phase"], st) if st.get("phase") else None
    k = max((i for i, r in enumerate(log) if "start" in r), default=0)       # 끝·사인 대기는 마지막 실행(다시 시도·승인 뒤) 것만
    end = next((r for r in reversed(log[k:]) if "end" in r), None)
    wait = next((r for r in reversed(log[k:]) if "wait" in r), None)
    waiting = bool(wait and log and log[-1] is wait)
    if end and end.get("stage"):        # 멈춘 편 = 엔진이 끝 줄에 남긴 단계(flow 가 멈춘 자리)
        cur = end["stage"]
    sign = None
    if waiting and (W / "sign.json").exists():
        try:
            sign = json.loads((W / "sign.json").read_text(encoding="utf-8"))
        except ValueError:
            sign = None
    p = _proc["p"]
    return {"work": str(W), "version": start.get("version"), "ref": start.get("ref"), "fmt": start.get("start"), "slug": start.get("slug"),
            "stages": stages, "cur": cur, "phase": st.get("phase"), "log": log[-400:], "reviews": reviews(W),
            "waiting": waiting, "sign": sign, "end": end, "running": bool(p and p.poll() is None)}


def launch(W: Path, extra: list[str]) -> str:
    p = _proc["p"]
    if p and p.poll() is None:
        return "이미 돌고 있습니다"
    start = next((r for r in read_log(W) if "start" in r), {})
    args = [sys.executable, str(Path(__file__).with_name("flow_dev.py")), "--work", str(W)]
    if "--ref" not in extra:
        args += ["--ref", start.get("ref") or "", "--version", start.get("version") or ""]
    out = (W / "run_stdout.txt").open("a", encoding="utf-8")
    _proc["p"] = subprocess.Popen(args + extra, cwd=str(ROOT), stdout=out, stderr=subprocess.STDOUT,
                                  env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    return "시작했습니다"


def make_handler(W: Path):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                return self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self._send(200, json.dumps(state(W), ensure_ascii=False).encode("utf-8"))
            if u.path == "/file":
                p = (parse_qs(u.query).get("p") or [""])[0]
                f = Path(p) if Path(p).is_absolute() else (W / p)
                try:
                    f = f.resolve()
                except OSError:
                    return self._send(404, b"{}")
                ok = f.is_file() and (W.resolve() in f.parents or f.suffix.lower() == ".mp4")   # 작업 폴더 밖은 완성 영상만
                if not ok:
                    return self._send(404, b"{}")
                return self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or "application/octet-stream")
            return self._send(404, b"{}")

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/approve":
                msg = launch(W, ["--resume", "--approve"])
            elif u.path == "/api/retry":
                msg = launch(W, ["--resume", "--retry"])
            elif u.path == "/api/resume":
                msg = launch(W, ["--resume"] + (["--approve"] if body.get("auto") else []))
            elif u.path == "/api/start":
                msg = launch(W, ["--ref", body["ref"], "--version", body["version"]] + (["--approve"] if body.get("auto") else []))
            else:
                return self._send(404, b"{}")
            return self._send(200, json.dumps({"message": msg}, ensure_ascii=False).encode("utf-8"))
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    W = Path(a.work)
    W.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(W))
    url = f"http://127.0.0.1:{a.port}/"
    print("진행판", url, flush=True)
    if a.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
