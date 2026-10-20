# -*- coding: utf-8 -*-
"""회원 PC 하이브리드(엔진 hybrid/customer.py) 개발 시험 — 엔진을 회원 모드로 띄우고, AI 요청은 Claude CLI(opus)가 회원 Claude 처럼 답한다.
MCP 를 거치지 않고 엔진 단계만 본다(단계 디버깅용). 진짜 회원 경로 시험은 live_episode.js.

    py test/hybrid_dev_run.py --engine <엔진 트랙> --data <없는 폴더> start --ref <URL> --version 키치잇판
    py test/hybrid_dev_run.py --engine <엔진 트랙> --data <같은 폴더> approve <sid> [--typecast-file f] [--eleven-file f]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

CLAUDE = os.environ.get("CLAUDE_BIN") or str(Path.home() / ".local" / "bin" / "claude.exe")


def answer_loop(q: Path, stop: threading.Event, log: Path):
    done = set()
    while not stop.is_set():
        for d in sorted(q.glob("*")) if q.exists() else []:
            rq = d / "request.json"
            if d.name in done or not rq.exists() or (d / "answer.json").exists() or (d / "done").exists():
                continue
            done.add(d.name)
            req = json.loads(rq.read_text(encoding="utf-8"))
            texts = [p["text"] for p in req.get("parts") or [] if p.get("kind") == "text"]
            imgs = [str(d / p["file"]) for p in req.get("parts") or [] if p.get("kind") == "image"]
            prompt = (req["prompt"] + ("\n\n" + "\n".join(texts) if texts else "") +
                      ("\n\n그림 파일(Read 로 열어 본다):\n" + "\n".join(imgs) if imgs else "") +
                      "\n\n답은 JSON 객체 하나만, 다른 글 없이.")
            t0 = time.time()
            r = subprocess.run([CLAUDE, "-p", prompt, "--model", "opus", "--allowedTools", "Read,WebSearch,WebFetch", "--output-format", "json",
                                "--max-turns", "30"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(d), timeout=1800)
            txt = ""
            try:
                txt = json.loads(r.stdout).get("result") or ""
            except Exception:  # noqa: BLE001
                txt = r.stdout
            s, e = txt.find("{"), txt.rfind("}")
            body = txt[s:e + 1] if s >= 0 else "{}"
            try:
                json.loads(body)
            except Exception:  # noqa: BLE001
                body = json.dumps({"_raw": txt[:2000]})
            (d / "answer.json.tmp").write_text(body, encoding="utf-8")
            (d / "answer.json.tmp").replace(d / "answer.json")
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"tag": req.get("tag"), "sec": round(time.time() - t0), "imgs": len(imgs), "answer_head": body[:300]}, ensure_ascii=False) + "\n")
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--typecast-file")
    ap.add_argument("--eleven-file")
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    data = Path(a.data); data.mkdir(parents=True, exist_ok=True)
    q = data / "ai"
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "CALCOPY_CUSTOMER_MODE": "1", "CALCOPY_GEMINI_BACKEND": "client",
           "SHORTEM_LLM_QUEUE": str(q), "CALCOPY_DATA_DIR": str(data / "창고")}
    for k, f in (("TYPECAST_API_KEY", a.typecast_file), ("ELEVENLABS_API_KEY", a.eleven_file)):
        if f:
            env[k] = Path(f).read_text(encoding="utf-8").strip()        # 값은 출력하지 않는다
    stop = threading.Event()
    th = threading.Thread(target=answer_loop, args=(q, stop, data / "answers.jsonl"), daemon=True)
    th.start()
    t0 = time.time()
    r = subprocess.run([sys.executable, str(Path(a.engine) / "tools/calcopy/make.py"), "--json", "hybrid", *a.rest], cwd=a.engine, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    stop.set()
    (data / "engine_stderr.txt").write_text(r.stderr, encoding="utf-8")
    last = (r.stdout.strip().splitlines() or ["{}"])[-1]
    print(json.dumps({"rc": r.returncode, "min": round((time.time() - t0) / 60, 1), "out": json.loads(last) if last.startswith("{") else last}, ensure_ascii=False))


if __name__ == "__main__":
    main()
