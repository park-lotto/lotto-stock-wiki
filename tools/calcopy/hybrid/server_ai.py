# -*- coding: utf-8 -*-
"""서버(숏템 서비스)에서 제미나이·유튜브 Data API 를 **서비스 코드 경로**로 돌려 결과만 받아 온다 — mina_tts 꼴 (관제 097, 2026-10-18).

사장님 승인(10-18): "제미니는 최대한 다 활용해, 유튜브 키도 없으면 쓰고" — 서버 회원 풀(keypool.resync_pools → key_vault 로테이션)을 쓴다.
★키 값은 절대 PC로 오지 않는다·출력하지 않는다. 서버에서 서비스 모듈(shopping_shorts.keypool · pipeline.atoms.key_vault · shopping_shorts.youtube_search)이
키를 고르고, 이 도구는 받아쓰기 글·검색 결과 JSON 만 받는다.

    PYTHONUTF8=1 py tools/calcopy/hybrid/server_ai.py asr <wav|mp4> [a-b a-b …] [--models m1,m2] [--prompt …]   # 클립 단독 받아쓰기(모델별 교차)
    PYTHONUTF8=1 py tools/calcopy/hybrid/server_ai.py yt "<검색어>" [--n 10] [--lang ko] [--duration short|medium|long]
    PYTHONUTF8=1 py tools/calcopy/hybrid/server_ai.py ping

받아쓰기는 **모델 2개 이상 교차 확인이 기본**(ASR_MODELS). 서버 쪽은 클립×모델을 스레드로 동시에 돌린다(키 여러 개 → 병렬).
서버에 없는 모델(404)은 그 모델만 건너뛰고 결과에 적는다 — 한 모델로 조용히 줄이지 않는다(결과 runs 에 모델별로 남는다).
한 모델이 끝까지 실패하면 그 자리에 {"why": …} 가 남고, 부르는 쪽(checks·name_check)이 '교차 확인 모자람'으로 적는다.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

KEY = "C:/Users/CH/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.35.251.172"
REPO = "/home/ubuntu/lotto-stock-wiki"
from tools.calcopy.engine.gemini_server import MODELS as ASR_MODELS, FALLBACK_MODELS as ASR_FALLBACK  # noqa: E402  — 모델 목록 주인은 엔진 한 곳(10-18 실측 표는 거기)
from tools.calcopy.engine.gemini_server import ASR_PROMPT  # noqa: E402  — 받아쓰기 프롬프트 주인도 엔진 한 곳({"text","speakers"} 모양). 10-18 여기 옛 {"clips"} 모양 두 벌째가 CLI 빈 글의 뿌리였다

# 서버에서 도는 코드 — 서비스 모듈만 부른다. 키는 key_vault 안에서만 돈다(여기서 print 하지 않는다).
REMOTE_ASR = r'''
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
clips = [base64.b64decode(c) for c in a["clips_b64"]]
def one(model):
    parts = []
    for k, data in enumerate(clips):
        parts += [f"클립 {k}:", types.Part.from_bytes(data=data, mime_type="audio/mp3")]
    parts.append(a["prompt"])
    t0 = time.time(); tries = 0; last = None
    for key in kv.rotated(live):
        tries += 1
        if tries > a.get("max_tries", 8):
            break
        try:
            r = kv.get_client_for_key(key).models.generate_content(model=model, contents=parts,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0, seed=7))
            kv.note_success(key)
            d = json.loads(r.text)
            return {"model": model, "tries": tries, "sec": round(time.time() - t0, 1), **({"clips": d.get("clips")} if "clips" in d else {"raw": d})}
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
            kv.note_failure(key, e)
            if "404" in str(e) or "NOT_FOUND" in str(e):
                return {"model": model, "why": "model_404 " + last, "tries": tries}
    return {"model": model, "why": last or "no_key", "tries": tries}
with ThreadPoolExecutor(max_workers=len(a["models"])) as ex:
    runs = list(ex.map(one, a["models"]))
print("@@JSON@@" + json.dumps({"runs": runs}, ensure_ascii=False))
'''

REMOTE_YT = r'''
import json, sys
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts import keypool, youtube_search
a = json.loads(sys.stdin.read())
store = Store(DB_PATH); keypool.resync_pools(store)
out = []
for q in a["queries"]:
    try:
        out.append({"q": q, "items": youtube_search.search(q, max_results=a["n"], duration=a.get("duration"), language=a.get("lang"))})
    except Exception as e:
        out.append({"q": q, "error": f"{type(e).__name__}: {str(e)[:160]}"})
print("@@JSON@@" + json.dumps(out, ensure_ascii=False))
'''


def _ssh_py(code: str, payload: dict, timeout: int = 300) -> dict | list:
    cmd = (f"cd {REPO} && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && "
           f"timeout {timeout} python3 -c {shlex.quote(code)}")
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-i", KEY, HOST, cmd], input=json.dumps(payload, ensure_ascii=False),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout + 60)
    m = [ln for ln in r.stdout.splitlines() if ln.startswith("@@JSON@@")]
    if not m:
        raise RuntimeError(f"서버 실행 실패 rc={r.returncode}: {r.stdout[-400:]} {r.stderr[-600:]}")
    return json.loads(m[-1][len("@@JSON@@"):])


def _clip_mp3(src, a: float | None, b: float | None, dst: Path):
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if a is not None:
        cmd += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}"]
    cmd += ["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(dst)]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True)


def _clip_json(m: dict) -> dict:
    """응답 한 건 → {"text","speakers"}. 엔진 프롬프트 모양({"text"})과 옛 묶음 모양({"clips":[{…}]}) 둘 다 읽는다 —
    호출자가 넘긴 프롬프트가 어느 모양이든 글이 빈칸으로 둔갑하지 않게(10-18 CLI·shark 영어 받아쓰기 빈 글 사고)."""
    j = m.get("json")
    if isinstance(j, dict) and "text" not in j and isinstance(j.get("clips"), list):
        j = j["clips"][0] if j["clips"] and isinstance(j["clips"][0], dict) else {"text": ""}
    if isinstance(j, list):
        j = j[0] if j and isinstance(j[0], dict) else {"text": ""}
    return j if isinstance(j, dict) else {"text": m.get("text", "")}


def asr_clips(src, spans: list[tuple[float, float]] | None, models=ASR_MODELS, prompt: str | None = None, max_tries: int = 8) -> dict:
    """소리 파일(또는 영상)의 구간들을 서버 제미나이로 받아쓴다 — 클립마다 **단독** 작업(병렬), 모델마다 1회(교차 확인).
    실제 호출은 gemini_server.ask_files 한 벌(0순위-B). 반환 {"spans", "runs":[{model, clips:[{i,text,speakers}]}|{model, why}], "ok_models", "sec"}."""
    from tools.calcopy.hybrid import gemini_server as G
    spans = spans or [(None, None)]
    files = [(str(src), a, b) if a is not None else str(src) for a, b in spans]
    r = G.ask_files(files, prompt or G.ASR_PROMPT, "audio", models, max_tries=max_tries)
    seen = list(models) + [x["model"] for job in r["jobs"] for x in job["runs"] if x["model"] not in models]
    runs = []
    for model in dict.fromkeys(seen):                   # 기본 모델 + 대체(fallback) 모델 — 성공한 클립만 싣는다
        clips, why = [], None
        for i, job in enumerate(r["jobs"]):
            m = next((x for x in job["runs"] if x["model"] == model and "why" not in x), None) or next((x for x in job["runs"] if x["model"] == model), None)
            if m is None or "why" in m:
                why = (m or {}).get("why", "no_run"); continue
            j = _clip_json(m)
            clips.append({"i": i, "text": j.get("text", ""), "speakers": j.get("speakers")})
        runs.append({"model": model, "clips": clips} if clips and why is None else {"model": model, "why": why or "partial", "clips": clips or None})
    cross = [len(job.get("ok_models") or []) for job in r["jobs"]]
    return {"spans": [list(s) if s[0] is not None else None for s in spans], "runs": runs, "sec": r["sec"],
            "ok_models": [x["model"] for x in runs if x.get("clips") and "why" not in x],
            "cross_per_clip": cross, "min_cross": min(cross) if cross else 0,      # ★교차 확인 = 클립마다 성공 모델 수(대체 모델 포함) ≥ 2
            "failed": [f for job in r["jobs"] for f in job.get("failed") or []]}


def asr_many(jobs: list[tuple], models=ASR_MODELS, workers: int = 3) -> list[dict]:
    """여러 (src, spans) 를 동시에(ssh 세션 여러 개) — 각 요청 안에서도 모델별 스레드가 돈다."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda j: asr_clips(j[0], j[1], models=models), jobs))


def texts_of(res: dict, i: int) -> list[str]:
    """클립 i 의 모델별 받아쓰기 글(성공한 모델만)."""
    out = []
    for r in res.get("runs", []):
        for c in r.get("clips") or []:
            if c.get("i") == i:
                out.append(c.get("text") or "")
    return out


def yt_search(queries: list[str], n: int = 10, lang: str | None = "ko", duration: str | None = None) -> list[dict]:
    """유튜브 Data API 검색(서버 키 풀) → [{"q", "items":[{url,title,thumbnail}]}]."""
    return _ssh_py(REMOTE_YT, {"queries": list(queries), "n": n, "lang": lang, "duration": duration}, timeout=120)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("asr"); a1.add_argument("src"); a1.add_argument("spans", nargs="*"); a1.add_argument("--models", default=",".join(ASR_MODELS)); a1.add_argument("--prompt")
    a2 = sub.add_parser("yt"); a2.add_argument("q", nargs="+"); a2.add_argument("--n", type=int, default=10); a2.add_argument("--lang", default="ko"); a2.add_argument("--duration")
    sub.add_parser("ping")
    a = ap.parse_args()
    if a.cmd == "ping":
        print(json.dumps(yt_search(["tekla towel"], n=1), ensure_ascii=False)[:200]); return
    if a.cmd == "asr":
        spans = [tuple(map(float, s.split("-"))) for s in a.spans] or None
        print(json.dumps(asr_clips(a.src, spans, models=tuple(a.models.split(",")), prompt=a.prompt or ASR_PROMPT), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(yt_search(a.q, a.n, a.lang, a.duration), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
