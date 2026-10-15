# -*- coding: utf-8 -*-
"""칼카피 엔진의 무료 제미나이 키 목록 — **여기 한 곳**에서만 고른다(analyze·compare·다른 도구 공용).

이름 패턴으로 읽는다(값 하드코딩·출력 금지): GEMINI_API_KEY, GEMINI_API_KEY_<n>, GEMINI_BRIEFING_KEY*,
SHORTS_GEMINI_KEY, SHORTS_GEMINI_KEY_<n>(숏템 공용 14개, 2026-10-16 사장님). 환경변수가 .env 보다 먼저.
순서: GEMINI_API_KEY* → SHORTS_GEMINI_KEY* (번호순). 같은 값은 한 번만. 429면 부르는 쪽이 다음 키로 돈다.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATTERNS = (r"GEMINI_API_KEY(?:_\d+)?", r"GEMINI_BRIEFING_KEY(?:_\d+)?", r"SHORTS_GEMINI_KEY(?:_\d+)?")


def _num(name: str) -> int:
    m = re.search(r"_(\d+)$", name)
    return int(m.group(1)) if m else 1


def key_names(env_file: str | None = None) -> list[str]:
    """찾은 키 이름(값 말고) — 진단·보고용."""
    return [n for n, _ in _pairs(env_file)]


def _pairs(env_file: str | None = None) -> list[tuple[str, str]]:
    env_file = env_file or str(ROOT / ".env")
    found: dict[str, str] = {}
    if os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            m = re.match(r"^([A-Z0-9_]+)=(\S+)", line.strip())
            if m:
                found[m.group(1)] = m.group(2).strip()
    for k, v in os.environ.items():
        if v.strip():
            found[k] = v.strip()
    out, seen = [], set()
    for pat in PATTERNS:
        names = sorted((n for n in found if re.fullmatch(pat, n)), key=_num)
        for n in names:
            if found[n] not in seen:
                seen.add(found[n])
                out.append((n, found[n]))
    return out


def keys(env_file: str | None = None) -> list[str]:
    return [v for _, v in _pairs(env_file)]
