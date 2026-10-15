# -*- coding: utf-8 -*-
"""뜯기용 무료 제미나이 창구 — 키는 gemini_keys.keys() 한 곳(GEMINI_API_KEY*·SHORTS_GEMINI_KEY*), transcribe_free.py 와 같은 방식(버텍스·유료 API 금지, BRAINBULB_VERTEX=0).

ask(parts, prompt) → (dict|None, 실패이유|None). 429·한도면 다음 키 → 다음 모델로 넘기고, 다 막히면 "429" 를
돌려준다(멈추지 않는다 — 부르는 쪽이 그 항목을 failed:429 로 적는다).
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
TIMEOUT_MS = 180_000
SEED = 7               # 같은 입력 → 같은 답에 가깝게(temperature 0 + 고정 seed)
_DEAD: set = set()      # (키번호, 모델) — 404/429
_CURSOR = {"i": 0}      # 키 라운드로빈 시작점
CALLS: list[dict] = []   # 이번 실행의 호출 장부(모델·키번호·결과) — 뜯기.json 에 남긴다


def _keys() -> list[str]:
    from tools.calcopy.engine.gemini_keys import keys   # 키 고르기는 gemini_keys 한 곳
    return keys()


def ask(parts: list, prompt: str, tag: str = "", models: tuple | None = None) -> tuple[dict | None, str | None]:
    """parts = [bytes(jpeg)|str, ...] 순서대로 붙인다. JSON 응답을 dict 로."""
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
    last = None
    n = len(keys)
    start = _CURSOR["i"] % n
    _CURSOR["i"] += 1
    # models = 부르는 쪽이 고른 모델 순서(글쓰기처럼 판독 일관성보다 글 품질이 중요한 곳). 없으면 뜯기 기본(PRIMARY 고정)
    plan = [PRIMARY] * PRIMARY_ROUNDS + [FALLBACK] if not models else list(models)
    for rnd, model in enumerate(plan):
        if rnd and model == plan[0]:
            time.sleep(5 * rnd)          # 503(과부하)면 잠깐 쉬고 같은 모델로 다시
        for step in range(n):
            ki = (start + step) % n
            if (ki, model) in _DEAD:
                continue
            t0 = time.time()
            try:
                c = genai.Client(api_key=keys[ki], http_options=types.HttpOptions(timeout=TIMEOUT_MS))
                r = c.models.generate_content(model=model, contents=contents,
                                              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                                                 temperature=0, seed=SEED))
                d = json.loads(r.text)
                if isinstance(d, list):      # 3.x 모델은 최상위 목록으로 답할 때가 있다(2026-10-16 실측) → {"items": 목록}
                    d = {"items": d}
                if not isinstance(d, dict):
                    raise ValueError(f"JSON 모양 이상: {type(d).__name__}")
                d["_model"] = model
                CALLS.append({"tag": tag, "model": model, "key": ki, "ok": True, "sec": round(time.time() - t0, 1)})
                return d, None
            except Exception as e:  # noqa: BLE001 — 한도·없는 모델·일시 장애면 다음 키, 끝까지 막히면 이유를 돌려준다
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    last = "429"
                    _DEAD.add((ki, model))
                elif "404" in msg or "NOT_FOUND" in msg:
                    last = "404 모델 없음"
                    _DEAD.add((ki, model))
                elif "503" in msg or "UNAVAILABLE" in msg:
                    last = "503"
                    CALLS.append({"tag": tag, "model": model, "key": ki, "failed": last, "sec": round(time.time() - t0, 1)})
                    break                # 과부하는 모델 탓 — 다음 바퀴(잠깐 쉰 뒤 같은 모델)
                else:
                    last = msg[:120]
                CALLS.append({"tag": tag, "model": model, "key": ki, "failed": last, "sec": round(time.time() - t0, 1)})
    return None, last
