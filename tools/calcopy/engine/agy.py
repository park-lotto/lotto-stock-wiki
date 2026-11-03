# -*- coding: utf-8 -*-
"""agy(구독 제미나이 CLI) 창구 — 한 곳(관제 319 D11). 영상 파일을 통째로 보여 주고 칸이 정해진 JSON 을 받는다.
명령 실행 권한은 주지 않는다(--mode plan). 실패는 조용히 넘기지 않고 error 로 돌려 서버가 멈추게 한다.
-p 는 반드시 맨 끝 플래그(앞에 두면 다음 플래그를 질문으로 먹는다 — 11-04 실측)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

RETRIES = 1


def find() -> str | None:
    p = shutil.which("agy")
    if p:
        return p
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin"
    for name in ("agy.exe", "agy"):
        cand = base / name
        if cand.exists():
            return str(cand)
    return None


def _call(args: list[str], run, timeout: int) -> dict:
    r = (run or subprocess.run)(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    try:
        return json.loads(r.stdout or "{}")
    except ValueError:
        return {"status": "BAD_OUTPUT", "response": (r.stdout or "")[:300]}


def logged_in(run=None) -> bool:
    exe = find()
    if not exe:
        return False
    out = _call([exe, "--output-format", "json", "--mode", "plan", "-p", 'JSON 하나로만 답: {"ok": true}'], run, 120)
    return out.get("status") == "SUCCESS"


def _json_of(text: str):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`").split("\n", 1)[-1]
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else None
    except ValueError:
        return None


def ask_video(video: Path, ask: str, schema: dict, run=None, timeout: int = 600) -> dict:
    exe = find()
    if not exe:
        return {"error": "agy_missing"}
    video = Path(video)
    prompt = (f"이 폴더의 {video.name} 영상 파일을 통째로 보고 들어라(장면 그림으로 자르지 말고, 명령어는 쓰지 마라). "
              f"{ask}\n답은 JSON 하나만.")
    args = [exe, "--output-format", "json", "--mode", "plan", "--json-schema", json.dumps(schema, ensure_ascii=False),
            "--add-dir", str(video.parent), "-p", prompt]
    t0 = time.time()
    out = {}
    for _ in range(RETRIES + 1):
        out = _call(args, run, timeout)
        ans = _json_of(out.get("response") or "") if out.get("status") == "SUCCESS" else None
        if ans is not None:
            return {"answer": ans, "sec": round(time.time() - t0, 1)}
    return {"error": f"agy_bad_answer:{out.get('status')}"}
