# -*- coding: utf-8 -*-
"""칼카피 제미나이 창구 **한 곳** — 모든 도구(analyze·material_auto·topic_find·script_frame·yanshot·style_writer·narr_video…)가 ask() 를 부른다.
키는 gemini_keys.keys() 한 곳(GEMINI_API_KEY*·SHORTS_GEMINI_KEY* = pull_pool_keys 로 받은 공용 풀), 버텍스·유료 API 금지(BRAINBULB_VERTEX=0).

ask(parts, prompt) → (dict|None, 실패이유|None). 429·한도면 다음 키 → 다음 모델로 넘기고, 다 막히면 "quota" 를
돌려준다(멈추지 않는다 — 부르는 쪽이 그 항목을 failed 로 적는다).

★2026-10-18 뿌리 수리(사장님 "제미나이는 최대한 다 활용해" · "시간부터 줄여라") — 부르는 쪽은 아무것도 안 바꿔도 된다:
  · 서버 대체: 로컬 풀이 오늘 다 막혔거나(quota/no_key) 키가 0개면 **서버 풀**(engine/gemini_server — 회원 풀·key_vault, 키 값은 PC 로 안 옴)로
    같은 모델·같은 프롬프트를 보낸다. 답에 _via="server" 표식. CALCOPY_GEMINI_BACKEND=auto(기본)|local|server.
    실측 10-18: 서버는 요청 1건당 SSH+기동 12~17초 고정비 → 글 1회짜리는 로컬이 빠르다(4~9초). 그래서 기본은 로컬 먼저.
  · ask_many(jobs, workers≤8): 묶음 동시 호출의 주인(analyze._batched 가 쓴다). 8개 동시 13.8초 vs 순차 4개 25.3초(10-18 실측).
  · ask_cross(parts, prompt, models): 모델 교차 — 모델별 답을 그대로 돌려준다(조용히 한 모델로 줄이지 않는다).
  · video_part(path): 영상을 인라인 상한(19MB) 아래로 줄여 (bytes, "video/mp4") 파트로.
시험에서는 analyze(..., llm=가짜함수) 로 이 창구 자체를 바꿔 끼운다.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ["BRAINBULB_VERTEX"] = "0"
# 2026-10-16 실측: SHORTS_GEMINI_KEY* 새 키 대부분은 gemini-2.5-flash 가 404("no longer available to new users").
# 모델은 **하나로 고정**(PRIMARY) — 받아쓰기·소리 구성이 실행마다 흔들린 원인이 503 때 lite·별칭으로 넘어간 것이었다(1판).
# PRIMARY 가 503 이면 키를 바꿔 PRIMARY 로 PRIMARY_ROUNDS 바퀴 재시도한 뒤에만 FALLBACK. 답에는 _model 표식을 붙인다.
PRIMARY = "gemini-3.5-flash"
PRIMARY_ROUNDS = 3
FALLBACK = "gemini-flash-lite-latest"
MODELS = (PRIMARY, FALLBACK)
TIMEOUT_MS = 180_000            # 그림·영상이 붙은 호출
TEXT_TIMEOUT_MS = 60_000        # 글만 보내는 호출(대본 등) — 10-18 옆 세션 순찰: 503·지연 때 키마다 180초씩 기다려 대본 1회 7분+ 멈춤
BACKEND = os.environ.get("CALCOPY_GEMINI_BACKEND", "auto").strip().lower() or "auto"   # auto|local|server
MANY_WORKERS = int(os.environ.get("CALCOPY_GEMINI_WORKERS") or 8)                      # 묶음 동시 상한(로컬 풀)
SERVER_FALLBACK_REASONS = ("quota", "no_key", "429")
SEED = 7               # 같은 입력 → 같은 답에 가깝게(temperature 0 + 고정 seed)
_DEAD: set = set()      # (키번호, 모델) — 404/429
# 키 라운드로빈 시작점 — ★프로세스마다 다른 자리에서 시작(10-18). 예전엔 모든 세션·워커가 0번 키부터 돌아
# 같은 키에 동시에 몰려 분당 429 → 그 429 를 '오늘 끝'으로 적어 공용 장부(~/.calcopy_gemini_quota.json, 모든 세션이 같이 씀)에서
# 161키가 전부 '죽음'이 됐다(실제로는 151키 정상, 10-18 161키 동시 1회 실측).
_CURSOR = {"i": int.from_bytes(os.urandom(2), "big")}
CALLS: list[dict] = []   # 이번 실행의 호출 장부(모델·키번호·결과) — 뜯기.json 에 남긴다


def _keys() -> list[str]:
    from tools.calcopy.engine.gemini_keys import keys   # 키 고르기는 gemini_keys 한 곳
    return keys()


def _names() -> list[str]:
    from tools.calcopy.engine.gemini_keys import key_names
    return key_names()


def _ask_local(parts: list, prompt: str, tag: str = "", models: tuple | None = None) -> tuple[dict | None, str | None]:
    """로컬 무료 풀(.env 키)로 1회. parts = [bytes(jpeg)|str|(bytes, mime), ...] 순서대로 붙인다. JSON 응답을 dict 로."""
    from google import genai
    from google.genai import types
    keys = _keys()
    if not keys:
        CALLS.append({"tag": tag, "failed": "no_key"})
        return None, "no_key"
    contents = []
    for p in parts:
        if isinstance(p, (bytes, bytearray)):
            contents.append(types.Part.from_bytes(data=bytes(p), mime_type="image/jpeg"))
        elif isinstance(p, tuple):   # (bytes, mime)
            contents.append(types.Part.from_bytes(data=p[0], mime_type=p[1]))
        else:
            contents.append(p)
    contents.append(prompt)
    from tools.calcopy.engine import gemini_keys as gk
    names = _names()
    last = None
    n = len(keys)
    start = _CURSOR["i"] % n
    _CURSOR["i"] += 1
    # models = 부르는 쪽이 고른 모델 순서(글쓰기처럼 판독 일관성보다 글 품질이 중요한 곳). 없으면 뜯기 기본(PRIMARY 고정)
    plan = [PRIMARY] * PRIMARY_ROUNDS + [FALLBACK] if not models else list(models)
    led = gk._load()
    # 오늘 장부에서 모든 키가 끝난 모델은 계획에서 뺀다 — 다 끝났으면 즉시 failed:quota(재시도로 시간 버리지 않기)
    plan = [m for m in plan if any(not gk.is_dead(nm, m, led) for nm in names)]
    if not plan:
        CALLS.append({"tag": tag, "failed": "quota", "day": led["day"]})
        return None, "quota"
    # 죽은 키 바로 넘기기(10-18): 모델마다 프로세스당 한 번 키를 동시에 미리 확인(models.get, 생성 한도 안 씀) →
    # 무효·권한·정지 키와 그 모델이 없는 키는 고장 장부(날 넘어 남음)에 적히고, 아래 루프는 부르지 않고 건너뛴다.
    #   ★본 호출을 기다리게 하지 않는다 — 뒤에서(데몬 스레드) 돈다. 10-18 실측: 161키 앞에서 막고 확인 = 54초 → 첫 호출 80초(더 느림).
    for m_ in dict.fromkeys(plan):
        gk.probe_bg(m_, keys)
    bled = gk._bload()
    for rnd, model in enumerate(plan):
        if rnd and model == plan[0]:
            time.sleep(5 * rnd)          # 503(과부하)면 잠깐 쉬고 같은 모델로 다시
        for step in range(n):
            ki = (start + step) % n
            if (ki, model) in _DEAD or gk.is_dead(names[ki], model) or gk.is_broken(keys[ki], model, bled):
                continue
            t0 = time.time()
            try:
                tmo = TIMEOUT_MS if any(not isinstance(p, str) for p in parts) else TEXT_TIMEOUT_MS
                c = genai.Client(api_key=keys[ki], http_options=types.HttpOptions(timeout=tmo))
                r = c.models.generate_content(model=model, contents=contents,
                                              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                                                 temperature=0, seed=SEED))
                d = json.loads(r.text)
                if isinstance(d, list):      # 3.x 모델은 최상위 목록으로 답할 때가 있다(2026-10-16 실측) → {"items": 목록}
                    d = {"items": d}
                if not isinstance(d, dict):
                    raise ValueError(f"JSON 모양 이상: {type(d).__name__}")
                d["_model"] = model
                gk.mark(names[ki], model, "ok")
                CALLS.append({"tag": tag, "model": model, "key": ki, "ok": True, "sec": round(time.time() - t0, 1)})
                return d, None
            except Exception as e:  # noqa: BLE001 — 한도·없는 모델·일시 장애면 다음 키, 끝까지 막히면 이유를 돌려준다
                msg = str(e)
                kind = gk.broken_reason(msg)
                if kind:                     # 키 자체가 죽음(무효·권한·정지) / 그 모델 없음 → 고장 장부(날 넘어 남음), 다시 안 부른다
                    gk.mark_broken(keys[ki], model, kind, msg)
                    bled = gk._bload()
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    last = "429"
                    if gk.rate_scope(msg) == "day":      # 분당 한도는 장부가 65초 뒤 풀어 준다 — 프로세스 메모리에 영구로 막지 않는다
                        _DEAD.add((ki, model))
                    gk.mark(names[ki], model, "429", msg)
                elif "API key not valid" in msg or "API_KEY_INVALID" in msg:
                    last = "400 키 무효"
                    for m_ in MODELS + tuple(plan):     # 키 자체가 무효 — 오늘 장부에 모든 모델로 끝 표시(42키 중 무효 키를 매번 다시 부르지 않게)
                        _DEAD.add((ki, m_))
                        gk.mark(names[ki], m_, "429")
                elif "404" in msg or "NOT_FOUND" in msg:
                    last = "404 모델 없음"
                    _DEAD.add((ki, model))
                elif "503" in msg or "UNAVAILABLE" in msg or "timed out" in msg.lower() or "Timeout" in msg:
                    last = "503"
                    CALLS.append({"tag": tag, "model": model, "key": ki, "failed": last, "sec": round(time.time() - t0, 1)})
                    break                # 과부하는 모델 탓 — 다음 바퀴(잠깐 쉰 뒤 같은 모델)
                else:
                    last = msg[:120]
                CALLS.append({"tag": tag, "model": model, "key": ki, "failed": last, "sec": round(time.time() - t0, 1)})
    if last == "429" and all(gk.is_dead(nm, m) for nm in names for m in plan):
        last = "quota"
    return None, last


# ── 서버 대체·묶음·교차 (10-18) ───────────────────────────────────────────
def _server_parts(parts: list) -> list[dict]:
    import base64
    out = []
    for p in parts:
        if isinstance(p, (bytes, bytearray)):
            out.append({"mime": "image/jpeg", "b64": base64.b64encode(bytes(p)).decode()})
        elif isinstance(p, tuple):
            out.append({"mime": p[1], "b64": base64.b64encode(bytes(p[0])).decode()})
        else:
            out.append({"text": str(p)})
    return out


def _ask_server(parts: list, prompt: str, tag: str = "", models: tuple | None = None) -> tuple[dict | None, str | None]:
    """서버 풀로 1회(모델은 요청한 순서대로 시도 — 첫 성공 모델의 답). 실패 이유는 모델별로 모아 돌려준다."""
    from tools.calcopy.engine import gemini_server as GS
    plan = list(models) if models else [PRIMARY, FALLBACK]
    t0 = time.time()
    try:
        r = GS.ask_raw([{"parts": _server_parts(parts), "prompt": prompt, "json": True}], models=plan)
    except Exception as e:  # noqa: BLE001 — SSH·서버 실패는 이유를 돌려준다(조용히 삼키지 않는다)
        why = f"server {type(e).__name__}: {str(e)[:120]}"
        CALLS.append({"tag": tag, "via": "server", "failed": why, "sec": round(time.time() - t0, 1)})
        return None, why
    runs = r["runs"][0]
    for model in plan:
        m = next((x for x in runs if x.get("model") == model and "why" not in x), None)
        if m is None:
            continue
        d = m.get("json")
        if d is None:
            try:
                d = json.loads(m.get("text") or "")
            except Exception:  # noqa: BLE001
                d = {"text": m.get("text")}
        if isinstance(d, list):
            d = {"items": d}
        if not isinstance(d, dict):
            d = {"value": d}
        d["_model"] = model
        d["_via"] = "server"
        CALLS.append({"tag": tag, "via": "server", "model": model, "ok": True, "sec": round(time.time() - t0, 1), "tries": m.get("tries")})
        return d, None
    why = "server " + "; ".join(f"{x.get('model')}: {x.get('why', '?')[:60]}" for x in runs)
    CALLS.append({"tag": tag, "via": "server", "failed": why, "sec": round(time.time() - t0, 1)})
    return None, why


def ask(parts: list, prompt: str, tag: str = "", models: tuple | None = None) -> tuple[dict | None, str | None]:
    """창구 하나. BACKEND=local → 로컬만 / server → 서버만 / auto(기본) → 로컬 먼저, 오늘 로컬 풀이 다 막히면(quota·no_key·429) 서버 풀로.
    client → 고객 PC 모드(관제 234): 고객 Claude 가 답한다(engine/client_llm — 제미나이·서버 풀 0, 소리는 위스퍼 글로)."""
    if BACKEND == "client":
        from tools.calcopy.engine import client_llm
        t0 = time.time()
        d, err = client_llm.ask(parts, prompt, tag, models)
        CALLS.append({"tag": tag, "via": "client", **({"ok": True} if d is not None else {"failed": err}), "sec": round(time.time() - t0, 1)})
        return d, err
    if BACKEND == "server":
        return _ask_server(parts, prompt, tag, models)
    d, err = _ask_local(parts, prompt, tag, models)
    if d is not None or BACKEND == "local" or err not in SERVER_FALLBACK_REASONS:
        return d, err
    d2, err2 = _ask_server(parts, prompt, tag, models)
    if d2 is not None:
        d2["_local_err"] = err
        return d2, None
    return None, f"{err} → {err2}"


def ask_many(jobs: list[tuple], workers: int | None = None) -> list[tuple[dict | None, str | None]]:
    """여러 (parts, prompt[, tag[, models]]) 를 **동시에**. 순서대로 (dict|None, err) 목록. 주인: 묶음 동시 호출은 여기 한 곳.
    상한 MANY_WORKERS(기본 8) — 로컬 풀 키 수(161)와 무관하게 유튜브·서버 과부하를 막는 값(10-18 실측 8개 13.8초)."""
    from concurrent.futures import ThreadPoolExecutor
    if not jobs:
        return []
    n = max(1, min(int(workers or MANY_WORKERS), MANY_WORKERS, len(jobs)))

    def one(j):
        parts, prompt = j[0], j[1]
        tag = j[2] if len(j) > 2 else ""
        models = j[3] if len(j) > 3 else None
        return ask(parts, prompt, tag=tag, models=models)
    if n == 1:
        return [one(j) for j in jobs]
    with ThreadPoolExecutor(max_workers=n) as ex:
        return list(ex.map(one, jobs))


def ask_cross(parts: list, prompt: str, models: tuple, tag: str = "") -> list[dict]:
    """모델 교차 확인 — 모델마다 1회(동시), [{"model", "json"|"why"}]. 받아쓰기 검증처럼 '두 모델이 같은가'를 볼 때.
    모델 하나가 끝까지 실패해도 그 자리에 why 를 남긴다(조용히 한 모델로 줄이지 않는다)."""
    res = ask_many([(parts, prompt, f"{tag}@{m}", (m,)) for m in models])
    return [{"model": m, **({"json": d} if d is not None else {"why": err})} for m, (d, err) in zip(models, res)]


def video_part(path: str, max_bytes: int = 19_000_000, height: int = 480) -> tuple[bytes, str]:
    """영상 파일 → (bytes, "video/mp4") 파트. 인라인 상한을 넘으면 480p·10fps 로 줄인 임시본을 쓴다(gemini_server._video_b64 와 같은 규칙)."""
    import subprocess
    import tempfile
    p = Path(path)
    data = p.read_bytes()
    if len(data) <= max_bytes:
        return data, "video/mp4"
    with tempfile.TemporaryDirectory() as td:
        small = Path(td) / "v.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p), "-vf", f"scale=-2:{height},fps=10", "-c:v", "libx264", "-crf", "30",
                        "-preset", "veryfast", "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart", str(small)],
                       check=True, stdin=subprocess.DEVNULL, capture_output=True)
        data = small.read_bytes()
    if len(data) > max_bytes:
        raise RuntimeError(f"영상이 줄여도 너무 크다({len(data) // 1_000_000}MB): {path} — 구간을 나눠라")
    return data, "video/mp4"
