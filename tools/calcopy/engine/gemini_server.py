# -*- coding: utf-8 -*-
"""서버 제미나이 창구(주인: tools/calcopy/engine — 10-18 hybrid 에서 옮김, hybrid/gemini_server.py 는 재수출) — 오디오/영상 파일 여러 개 + 프롬프트 → 서버(숏템 서비스)로 보내 **서비스 키 풀**(회원 풀 합류 + key_vault 로테이션)로
병렬 호출, 모델 2개 이상 교차 → JSON 결과만 받아 온다 (사장님 승인 2026-10-18 "제미니는 최대한 다 활용해", 관제 097).

★키 값은 PC로 오지 않는다·출력하지 않는다(mina_tts 꼴). 서버에서 shopping_shorts.keypool.resync_pools → pipeline.atoms.key_vault 가 키를 고른다.

CLI
    PYTHONUTF8=1 py tools/calcopy/engine/gemini_server.py asr  <파일1> [<파일2>…] [--spans "a-b,a-b"] [--models m1,m2] [--prompt …] [--json out.json]
    PYTHONUTF8=1 py tools/calcopy/engine/gemini_server.py video <mp4> [--spans "a-b,a-b"] --prompt "…" [--models …]      # 영상 토막(480p) 판독
    PYTHONUTF8=1 py tools/calcopy/engine/gemini_server.py text --prompt "…" [--models …]
    PYTHONUTF8=1 py tools/calcopy/engine/gemini_server.py ping
  --spans 는 파일마다 같은 구간을 자른다(파일 1개 + 구간 여럿 = 클립 여럿). 없으면 파일 통째.
  결과: {"jobs":[{"file","span","runs":[{"model","text"|"json","sec","tries"}|{"model","why"}]}], "sec"}  — runs 는 모델별(교차 확인).

파이썬
    from tools.calcopy.engine.gemini_server import ask_files, asr, texts
    r = asr(["a.wav", ("b.mp4", 3.2, 11.0)], prompt=None)        # (경로) 또는 (경로, a, b)
    texts(r["jobs"][0])  → 모델별 글 목록

받아쓰기 기본 프롬프트는 클립 단독·들리는 그대로·화자 수. 모델 기본 MODELS(측정으로 고른 빠른 2개) · 대체 FALLBACK_MODELS.
한 모델이 실패(429 끝까지·시간초과 REQ_TIMEOUT_SEC·404)하면 그 자리에 {"why"} 가 남고, 같은 작업에 **대체 모델을 차례로** 더 불러 성공 모델이 CROSS_N 개가
되게 한다. 그래도 모자라면 jobs[i].cross_ok=False — 조용히 한 모델로 줄이지 않는다(부르는 쪽이 '교차 확인 모자람'으로 적는다).
서버 한 번 호출 = 작업 여러 개 × 모델 여러 개를 스레드로 동시에(1차) → 모자란 작업만 대체 모델(2차).

모델 실측(2026-10-18 손태영 원음 2~3초 클립 3개, 서버 풀, 요청 상한 45초 — _hybrid_pipeline_test/손태영/asr/model_bench.json):
  gemini-3-flash-preview 3.8·9.6·4.2초(tries 1·4·1) 글 정상 / gemini-3.5-flash 4.1·4.6초 + 1클립 429(키 9개) · '금가루'→'콩가루' 1회
  gemini-flash-latest 8.5·8.5·4.3초(같은 날 새벽엔 177~304초 — 키 하나가 매달린 것, 그래서 상한) / gemini-3.5-flash-lite 2.5~2.8초, 짧은 클립 1개 빈 글
  gemini-2.5-flash 404. 15회 합계 12.5초(옛 2모델 3클립 215초).
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

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # 서버가 모자라 로컬 풀로 채울 때 tools.* 를 부른다 — 스크립트로 바로 돌리면 ModuleNotFoundError 였다(10-19)

KEY ="C:/Users/CH/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.35.251.172"
REPO = "/home/ubuntu/lotto-stock-wiki"
MODELS = ("gemini-3-flash-preview", "gemini-3.5-flash")          # 기본 2개(교차) — 10-18 서버 실측(아래 표) 3.8~9.6초 / 4.1~4.6초
FALLBACK_MODELS = ("gemini-flash-latest", "gemini-3.5-flash-lite")   # 기본 모델이 429·시간초과·404 면 이 순서로 대체(작업마다 성공 모델 CROSS_N 개가 될 때까지). 2.5-flash 는 404
REQ_TIMEOUT_SEC = 45         # 모델 1회 호출 상한 — 10-18 손태영: gemini-flash-latest 가 2초 클립에 177~304초(상한 없이 매달림)
CROSS_N = 2                  # '교차 확인' = 서로 다른 모델 이 개수 이상 성공. 못 채우면 jobs[i].cross_ok=False (조용히 1모델로 줄이지 않는다)
ASR_PROMPT = ('이 오디오의 한국어 말소리를 들리는 그대로 받아써라(배경음악·효과음은 빼고, 고치거나 보태지 마라). 말하는 사람 수도 세라. '
              '말이 없으면 text 는 빈 문자열.\nJSON만: {"text":"","speakers":1}')
MAX_INLINE = 19_000_000      # 제미나이 인라인 바이트 상한(20MB) 아래
WORKERS = 12                 # 서버 스레드 상한 — 유료 고객과 같은 풀이라 요청당 12 를 넘기지 않는다(10-18)

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
            cfg = types.GenerateContentConfig(response_mime_type="application/json" if job.get("json", True) else None, temperature=0, seed=7,
                                              http_options=types.HttpOptions(timeout=int(float(a.get("req_timeout", 45)) * 1000)))
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
            msg = str(e); code = getattr(e, "code", None)
            # 10-18: 140자로 잘라 어떤 한도(분당·하루·모델 혼잡)인지 안 남았다 → 한도 이름(quotaId)·다시 시도 초를 따로 남긴다
            import re as _re
            qid = ",".join(sorted(set(_re.findall(r"'quotaId': '([^']+)'", msg))))
            rd = (_re.findall(r"'retryDelay': '([^']+)'", msg) or [""])[0]
            last = f"{type(e).__name__}: {msg[:140]}" + (f" | quota={qid}" if qid else "") + (f" | retry={rd}" if rd else "")
            if code == 404 or (code is None and ("404 NOT_FOUND" in msg or msg.startswith("404"))):   # 10-18: 429 글 속 숫자 '404' 로 모델을 버린 오판 3건
                return {"model": model, "why": "model_404 " + last, "tries": tries}
            if "imeout" in type(e).__name__ or "timed out" in str(e).lower() or "ReadTimeout" in str(e):
                return {"model": model, "why": "timeout " + last, "tries": tries, "sec": round(time.time() - t0, 1)}   # 느린 모델은 키를 바꿔도 느리다 — 바로 대체 모델로
            kv.note_failure(key, e)
    return {"model": model, "why": last or "no_key", "tries": tries}
def batch(tasks):
    with ThreadPoolExecutor(max_workers=min(int(a.get("workers") or 12), 12, max(1, len(tasks)))) as ex:
        return list(ex.map(lambda t: (t[0], call(a["jobs"][t[0]], t[1])), tasks))
runs = [[] for _ in a["jobs"]]
for ji, r in batch([(ji, m) for ji in range(len(a["jobs"])) for m in a["models"]]):
    runs[ji].append(r)
need = int(a.get("cross_n", 2))
for fb in a.get("fallback") or []:                      # 2차: 성공 모델이 need 개 안 되는 작업만 대체 모델 하나씩(차례로)
    short = [ji for ji in range(len(a["jobs"])) if len({r["model"] for r in runs[ji] if "why" not in r}) < need
             and fb not in {r["model"] for r in runs[ji]}]
    if not short:
        break
    for ji, r in batch([(ji, fb) for ji in short]):
        r["fallback"] = True
        runs[ji].append(r)
print("@@JSON@@" + json.dumps({"runs": runs}, ensure_ascii=False))
'''


def _ssh_py(code: str, payload: dict, timeout: int = 420):
    cmd = (f"cd {REPO} && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && timeout {timeout} python3 -c {shlex.quote(code)}")
    # 10-18 03:20 옆 세션 순찰: rc=255·빈 출력(순간 SSH 끊김 — 동시 ssh 여럿·MaxStartups) → 5초 쉬고 다시(최대 2회).
    #   서버 쪽에서 돈 뒤 끊긴 게 아니라 접속 단계 실패(rc 255 + stdout 빔)일 때만 — 같은 작업을 두 번 돌리지 않게.
    for attempt in range(3):
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15", "-i", KEY, HOST, cmd],
                           input=json.dumps(payload, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout + 60)
        if not (r.returncode == 255 and not r.stdout.strip()) or attempt == 2:
            break
        time.sleep(5)
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


def ask_files(files, prompt: str, mode: str = "audio", models=MODELS, json_out: bool = True, max_tries: int = 8, workers: int = WORKERS,
              fallback=FALLBACK_MODELS, cross_n: int = CROSS_N, req_timeout: float = REQ_TIMEOUT_SEC) -> dict:
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
    try:
        res = _ssh_py(REMOTE, {"jobs": jobs, "models": list(models), "max_tries": max_tries, "workers": min(int(workers), WORKERS),
                               "fallback": list(fallback or ()), "cross_n": cross_n, "req_timeout": req_timeout})
        runs_all = res["runs"]
    except Exception as e:  # noqa: BLE001 — 서버가 통째로 막혀도 로컬 풀로 채운다(이유는 runs 에 남긴다)
        runs_all = [[{"model": "server", "why": f"server {type(e).__name__}: {str(e)[:160]}"}] for _ in jobs]
    out = {"jobs": [{"file": src, "span": [a, b] if a is not None else None, "runs": runs} for (src, a, b), runs in zip(jobs_in, runs_all)],
           "sec": round(time.time() - t0, 1), "models": list(models), "fallback": list(fallback or ()), "cross_n": cross_n}
    if json_out:
        _local_fill(jobs, out["jobs"], list(models) + list(fallback or ()), cross_n)
    for j in out["jobs"]:
        j["ok_models"] = sorted({r["model"] for r in j["runs"] if "why" not in r})
        j["cross_ok"] = len(j["ok_models"]) >= cross_n           # ★교차 확인 됐나 — 부르는 쪽은 이 표식으로만 판단한다
        j["failed"] = [{"model": r["model"], "why": r["why"]} for r in j["runs"] if "why" in r]
    out["sec"] = round(time.time() - t0, 1)
    return out


def _local_fill(jobs: list[dict], outs: list[dict], plan: list[str], cross_n: int) -> None:
    """서버 풀이 429·SSH 로 교차 확인을 못 채운 작업만 로컬 공용 풀(gemini_free._ask_local, 161키 장부)로 모자란 모델을 채운다.
    10-18 다섯 편 동시 제작: 서버 4모델 전부 429 → 작업자들이 손으로 로컬 풀을 불러 우회했다(김나영·서인영·스타픽룸). 이제 여기 한 곳에서."""
    import base64
    from concurrent.futures import ThreadPoolExecutor
    from tools.calcopy.engine import gemini_free as GF
    todo = []
    for job, o in zip(jobs, outs):
        ok = {r["model"] for r in o["runs"] if "why" not in r}
        if len(ok) >= cross_n:
            continue
        parts = [(base64.b64decode(p["b64"]), p["mime"]) if p.get("b64") else p["text"] for p in job["parts"]]
        miss = [m for m in plan if m not in ok][: cross_n - len(ok)]
        todo += [(o, parts, job["prompt"], m) for m in miss]
    if not todo:
        return

    def one(t):
        o, parts, prompt, m = t
        t0 = time.time()
        d, err = GF._ask_local(parts, prompt, tag=f"server_fill@{m}", models=(m,))
        if d is None:
            return o, {"model": m, "why": f"local {err}", "via": "local"}
        d.pop("_model", None)
        return o, {"model": m, "json": d, "sec": round(time.time() - t0, 1), "via": "local"}
    with ThreadPoolExecutor(max_workers=min(8, len(todo))) as ex:
        for o, r in ex.map(one, todo):
            o["runs"].append(r)


def ask_raw(jobs: list[dict], models=MODELS, max_tries: int = 8, workers: int = WORKERS, fallback=FALLBACK_MODELS, cross_n: int = 1,
            req_timeout: float = REQ_TIMEOUT_SEC) -> dict:
    """미리 만든 작업 목록을 그대로 서버로 — jobs = [{"parts":[{"mime","b64"}|{"text"}…], "prompt", "json":bool}].
    gemini_free.ask 의 서버 대체 경로가 쓴다(그림·소리·영상·글 전부, 첫 성공 모델 하나면 되므로 cross_n=1). 반환 {"runs":[[모델별 응답…]…], "sec"}."""
    t0 = time.time()
    res = _ssh_py(REMOTE, {"jobs": jobs, "models": list(models), "max_tries": max_tries, "workers": min(int(workers), WORKERS),
                           "fallback": list(fallback or ()), "cross_n": cross_n, "req_timeout": req_timeout})
    return {"runs": res["runs"], "sec": round(time.time() - t0, 1), "models": list(models)}


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
        p.add_argument("--no-fallback", action="store_true"); p.add_argument("--timeout", type=float, default=REQ_TIMEOUT_SEC)
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
        r = ask_files(files, a.prompt or ASR_PROMPT, "audio" if a.cmd == "asr" else "video", models, json_out=not a.raw_text,
                      fallback=() if a.no_fallback else FALLBACK_MODELS, req_timeout=a.timeout)
    s = json.dumps(r, ensure_ascii=False, indent=1)
    if a.json:
        Path(a.json).write_text(s, encoding="utf-8")
    print(s)


if __name__ == "__main__":
    main()
