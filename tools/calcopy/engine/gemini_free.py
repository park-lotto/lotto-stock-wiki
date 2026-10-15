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
# 그래서 3.5-flash(실측 4키 OK) → 별칭 flash-latest(503 잦음) → 2.5 순. 키마다 404 난 모델·429 난 (키,모델)은 이번 실행 동안 다시 안 부른다.
MODELS = ("gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest")
TIMEOUT_MS = 180_000
_DEAD: set = set()      # (키번호, 모델) — 404/429
_CURSOR = {"i": 0}      # 키 라운드로빈 시작점
CALLS: list[dict] = []   # 이번 실행의 호출 장부(모델·키번호·결과) — 뜯기.json 에 남긴다


def _keys() -> list[str]:
    from tools.calcopy.engine.gemini_keys import keys   # 키 고르기는 gemini_keys 한 곳
    return keys()


def ask(parts: list, prompt: str, tag: str = "") -> tuple[dict | None, str | None]:
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
    for step in range(n):
        ki = (start + step) % n
        for model in MODELS:
            if (ki, model) in _DEAD:
                continue
            t0 = time.time()
            try:
                c = genai.Client(api_key=keys[ki], http_options=types.HttpOptions(timeout=TIMEOUT_MS))
                r = c.models.generate_content(model=model, contents=contents,
                                              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                                                 temperature=0))
                d = json.loads(r.text)
                if isinstance(d, list):      # 3.x 모델은 최상위 목록으로 답할 때가 있다(2026-10-16 실측) → {"items": 목록}
                    d = {"items": d}
                if not isinstance(d, dict):
                    raise ValueError(f"JSON 모양 이상: {type(d).__name__}")
                CALLS.append({"tag": tag, "model": model, "key": ki, "ok": True, "sec": round(time.time() - t0, 1)})
                return d, None
            except Exception as e:  # noqa: BLE001 — 한도·없는 모델·일시 장애면 다음 모델/키, 끝까지 막히면 이유를 돌려준다
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    last = "429"
                    _DEAD.add((ki, model))
                elif "404" in msg or "NOT_FOUND" in msg:
                    last = "404 모델 없음"
                    _DEAD.add((ki, model))
                else:
                    last = msg[:120]
                CALLS.append({"tag": tag, "model": model, "key": ki, "failed": last, "sec": round(time.time() - t0, 1)})
                if last == "429":
                    break           # 이 키는 쉬게 하고 다음 키
    return None, last
