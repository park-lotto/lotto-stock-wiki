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


# ── 하루 예산·429 장부(2026-10-16 3판) ──────────────────────────────────────
# 무료 등급 한도는 태평양 자정(KST 16:00~17:00)에 풀린다. 오늘 429 난 (키, 모델)과 오늘 쓴 횟수를 파일 하나에 적어
# 모든 프로세스(분석기·워커·대조)가 같이 본다 — 바닥난 키로 재시도하며 시간을 버리지 않게(1판 편당 429 재시도 14회).
# 키 값은 적지 않는다(이름만).
import json as _json
import time as _time
from datetime import datetime as _dt, timezone as _tz, timedelta as _td

QUOTA_FILE = Path(os.environ.get("CALCOPY_QUOTA_FILE") or (Path.home() / ".calcopy_gemini_quota.json"))
DAILY_BUDGET = int(os.environ.get("CALCOPY_GEMINI_DAILY_BUDGET") or 250)   # 키·모델당 하루 성공 호출 상한(넘으면 그 키는 오늘 안 씀)


def quota_day() -> str:
    """무료 한도 날짜(태평양 시간 날짜)."""
    try:
        from zoneinfo import ZoneInfo
        return _dt.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001 — 시간대 자료가 없으면 UTC-7 로
        return (_dt.now(_tz.utc) - _td(hours=7)).strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        d = _json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 없거나 깨졌으면 새로
        d = {}
    if d.get("day") != quota_day():
        d = {"day": quota_day(), "dead": {}, "used": {}}
    return d


def _save(d: dict) -> None:
    try:
        tmp = QUOTA_FILE.with_suffix(".tmp")
        tmp.write_text(_json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, QUOTA_FILE)
    except Exception:  # noqa: BLE001 — 장부를 못 써도 호출은 계속(다음 프로세스가 다시 429를 겪을 뿐)
        pass


def is_dead(name: str, model: str, d: dict | None = None) -> bool:
    d = d or _load()
    k = f"{name}|{model}"
    return k in d["dead"] or d["used"].get(k, 0) >= DAILY_BUDGET


def mark(name: str, model: str, status: str) -> None:
    """status: '429'(오늘 그 키·모델 끝) / 'ok'(쓴 횟수 +1)."""
    d = _load()
    k = f"{name}|{model}"
    if status == "429":
        d["dead"][k] = _time.strftime("%H:%M:%S")
    elif status == "ok":
        d["used"][k] = d["used"].get(k, 0) + 1
    _save(d)


def quota_report() -> dict:
    """오늘 장부 요약(이름만): 모델별 살아 있는 키 수·429 키·쓴 횟수."""
    d = _load()
    names = key_names()
    models = sorted({k.split("|", 1)[1] for k in list(d["dead"]) + list(d["used"])})
    return {"day": d["day"], "budget": DAILY_BUDGET,
            "models": {m: {"alive": sum(1 for n in names if not is_dead(n, m, d)), "keys": len(names),
                           "dead": sorted(k.split("|")[0] for k in d["dead"] if k.endswith("|" + m)),
                           "used": sum(v for k, v in d["used"].items() if k.endswith("|" + m))} for m in models}}
