# -*- coding: utf-8 -*-
"""서버 제미나이 창구 — 오디오/영상 파일 여러 개 + 프롬프트 → 서버(숏템 서비스)로 보내 **서비스 키 풀**(회원 풀 합류 + key_vault 로테이션)로
병렬 호출, 모델 2개 이상 교차 → JSON 결과만 받아 온다 (사장님 승인 2026-10-18 "제미니는 최대한 다 활용해", 관제 097).

★키 값은 PC로 오지 않는다·출력하지 않는다(mina_tts 꼴). 서버에서 shopping_shorts.keypool.resync_pools → pipeline.atoms.key_vault 가 키를 고른다.

CLI
    PYTHONUTF8=1 py tools/calcopy/hybrid/gemini_server.py asr  <파일1> [<파일2>…] [--spans "a-b,a-b"] [--models m1,m2] [--prompt …] [--json out.json]
    PYTHONUTF8=1 py tools/calcopy/hybrid/gemini_server.py video <mp4> [--spans "a-b,a-b"] --prompt "…" [--models …]      # 영상 토막(480p) 판독
    PYTHONUTF8=1 py tools/calcopy/hybrid/gemini_server.py text --prompt "…" [--models …]
    PYTHONUTF8=1 py tools/calcopy/hybrid/gemini_server.py ping
  --spans 는 파일마다 같은 구간을 자른다(파일 1개 + 구간 여럿 = 클립 여럿). 없으면 파일 통째.
  결과: {"jobs":[{"file","span","runs":[{"model","text"|"json","sec","tries"}|{"model","why"}]}], "sec"}  — runs 는 모델별(교차 확인).

파이썬
    from tools.calcopy.hybrid.gemini_server import ask_files, asr, texts
    r = asr(["a.wav", ("b.mp4", 3.2, 11.0)], prompt=None)        # (경로) 또는 (경로, a, b)
    texts(r["jobs"][0])  → 모델별 글 목록

받아쓰기 기본 프롬프트는 클립 단독·들리는 그대로·화자 수. 모델 기본 ("gemini-3-flash-preview", "gemini-flash-latest") — 10-18 서버 실측 둘 다 응답(2.5-flash 는 404).
한 모델이 끝까지 실패하면 그 자리에 {"why"} 가 남는다 — 조용히 한 모델로 줄이지 않는다. 서버 한 번 호출 = 작업 여러 개 × 모델 여러 개를 스레드로 동시에.
"""
from __future__ import annotations

import argparse
import base64
import json
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KEY = "C:/Users/CH/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.35.251.172"
REPO = "/home/ubuntu/lotto-stock-wiki"
MODELS = ("gemini-3-flash-preview", "gemini-flash-latest")
ASR_PROMPT = ('이 오디오의 한국어 말소리를 들리는 그대로 받아써라(배경음악·효과음은 빼고, 고치거나 보태지 마라). 말하는 사람 수도 세라. '
              '말이 없으면 text 는 빈 문자열.\nJSON만: {"text":"","speakers":1}')
MAX_INLINE = 19_000_000      # 제미나이 인라인 바이트 상한(20MB) 아래

REMOTE = r'''
import json, sys, time, base64
from concurrent.futures import ThreadPoolExecutor
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts import keypool
from pipeline.atoms import key_vault as kv
from google.genai import types
a = json.loads(sys.stdin.read())
store = Store(DB_PATH); keypool.resync_pools(store)
live = kv.get_live_keys_cascade("general")
def call(job, model):
    parts = [types.Part.from_bytes(data=base64.b64decode(p["b64"]), mime_type=p["mime"]) if p.get("b64") else p["text"] for p in job["parts"]]
    parts.append(job["prompt"])
    t0 = time.time(); tries = 0; last = None
    for key in kv.rotated(live):
        tries += 1
        if tries > a.get("max_tries", 8):
            break
        try:
            cfg = types.GenerateContentConfig(response_mime_type="application/json" if job.get("json", True) else None, temperature=0, seed=7)
            r = kv.get_client_for_key(key).models.generate_content(model=model, contents=parts, config=cfg)
            kv.note_success(key)
            out = {"model": model, "tries": tries, "sec": round(time.time() - t0, 1)}
            if job.get("json", True):
                try:
                    out["json"] = json.loads(r.text)
                except Exception:
                    out["text"] = r.text
            else:
                out["text"] = r.text
            return out
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:140]}"
            kv.note_failure(key, e)
            if "404" in str(e) or "NOT_FOUND" in str(e):
                return {"model": model, "why": "model_404 " + last, "tries": tries}
    return {"model": model, "why": last or "no_key", "tries": tries}
tasks = [(ji, m) for ji in range(len(a["jobs"])) for m in a["models"]]
with ThreadPoolExecutor(max_workers=min(12, max(1, len(tasks)))) as ex:
    res = list(ex.map(lambda t: (t[0], call(a["jobs"][t[0]], t[1])), tasks))
runs = [[] for _ in a["jobs"]]
for ji, r in res:
    runs[ji].append(r)
print("@@JSON@@" + json.dumps({"runs": runs}, ensure_ascii=False))
'''


def _ssh_py(code: str, payload: dict, timeout: int = 420):
    cmd = (f"cd {REPO} && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && timeout {timeout} python3 -c {shlex.quote(code)}")
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-i", KEY, HOST, cmd], input=json.dumps(payload, ensure_ascii=False),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout + 60)
    m = [ln for ln in r.stdout.splitlines() if ln.startswith("@@JSON@@")]
    if not m:
        raise RuntimeError(f"서버 실행 실패 rc={r.returncode}: {r.stdout[-400:]} {r.stderr[-800:]}")
    return json.loads(m[-1][len("@@JSON@@"):])


def _norm_jobs(files) -> list[tuple[str, float | None, float | None]]:
    out = []
    for f in files:
        if isinstance(f, (tuple, list)):
            out.append((str(f[0]), float(f[1]) if len(f) > 1 and f[1] is not None else None, float(f[2]) if len(f) > 2 and f[2] is not None else None))
        else:
            out.append((str(f), None, None))
    return out


def _audio_b64(src, a, b, td: Path, k: int) -> str:
    p = td / f"a{k}.mp3"
    cmd = ["ffmpeg", "-y", "-v", "error"] + (["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}"] if a is not None else []) + ["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(p)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True)
    return base64.b64encode(p.read_bytes()).decode()


def _video_b64(src, a, b, td: Path, k: int, height: int = 480) -> str:
    p = td / f"v{k}.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error"] + (["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}"] if a is not None else []) + \
          ["-i", str(src), "-vf", f"scale=-2:{height},fps=10", "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart", str(p)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True)
    if p.stat().st_size > MAX_INLINE:
        raise RuntimeError(f"영상 토막이 너무 크다({p.stat().st_size // 1_000_000}MB) — 구간을 나눠라: {src} {a}-{b}")
    return base64.b64encode(p.read_bytes()).decode()


def ask_files(files, prompt: str, mode: str = "audio", models=MODELS, json_out: bool = True, max_tries: int = 8) -> dict:
    """files = [경로 | (경로, a, b) …] → 작업마다(파일·구간) 모델별 응답. mode audio(16k mp3) / video(480p 10fps mp4) / text(파일 없음)."""
    if mode not in ("audio", "video", "text"):
        raise ValueError(f"mode 는 audio|video|text: {mode}")
    jobs_in = _norm_jobs(files) if mode != "text" else [(None, None, None)]
    if mode != "text" and not jobs_in:
        raise ValueError("파일이 없다")
    jobs = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for k, (src, a, b) in enumerate(jobs_in):
            parts = []
            if mode == "audio":
                parts.append({"mime": "audio/mp3", "b64": _audio_b64(src, a, b, td, k)})
            elif mode == "video":
                parts.append({"mime": "video/mp4", "b64": _video_b64(src, a, b, td, k)})
            jobs.append({"parts": parts, "prompt": prompt, "json": json_out})
    t0 = time.time()
    res = _ssh_py(REMOTE, {"jobs": jobs, "models": list(models), "max_tries": max_tries})
    out = {"jobs": [{"file": src, "span": [a, b] if a is not None else None, "runs": runs} for (src, a, b), runs in zip(jobs_in, res["runs"])],
           "sec": round(time.time() - t0, 1), "models": list(models)}
    for j in out["jobs"]:
        j["ok_models"] = [r["model"] for r in j["runs"] if "why" not in r]
    return out


def asr(files, prompt: str | None = None, models=MODELS) -> dict:
    """받아쓰기(클립 단독, 모델 교차). 반환 ask_files 꼴 — runs[i].json = {"text","speakers"}."""
    return ask_files(files, prompt or ASR_PROMPT, "audio", models)


def texts(job: dict) -> list[str]:
    """한 작업의 모델별 글(성공한 모델만)."""
    out = []
    for r in job.get("runs", []):
        if "why" in r:
            continue
        j = r.get("json")
        out.append((j.get("text") if isinstance(j, dict) else None) or r.get("text") or (json.dumps(j, ensure_ascii=False) if j is not None else ""))
    return out


def _spans(s: str):
    return [tuple(map(float, x.split("-"))) for x in s.split(",") if x] if s else []


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("asr", "video"):
        p = sub.add_parser(name); p.add_argument("files", nargs="+"); p.add_argument("--spans", default=""); p.add_argument("--models", default=",".join(MODELS)); p.add_argument("--prompt"); p.add_argument("--json"); p.add_argument("--raw-text", action="store_true")
    t = sub.add_parser("text"); t.add_argument("--prompt", required=True); t.add_argument("--models", default=",".join(MODELS)); t.add_argument("--json"); t.add_argument("--raw-text", action="store_true")
    sub.add_parser("ping")
    a = ap.parse_args()
    if a.cmd == "ping":
        r = ask_files([], "답은 JSON {\"ok\":true} 만.", "text")
        print(json.dumps(r, ensure_ascii=False)); return
    models = tuple(a.models.split(","))
    if a.cmd == "text":
        r = ask_files([], a.prompt, "text", models, json_out=not a.raw_text)
    else:
        sp = _spans(a.spans)
        files = [(f, s[0], s[1]) for f in a.files for s in sp] if sp else list(a.files)
        r = ask_files(files, a.prompt or ASR_PROMPT, "audio" if a.cmd == "asr" else "video", models, json_out=not a.raw_text)
    s = json.dumps(r, ensure_ascii=False, indent=1)
    if a.json:
        Path(a.json).write_text(s, encoding="utf-8")
    print(s)


if __name__ == "__main__":
    main()
