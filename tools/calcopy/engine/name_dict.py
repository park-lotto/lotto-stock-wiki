# -*- coding: utf-8 -*-
"""사람 이름 TTS 발음 사전 — 주인은 이 파일 + name_dict.json 한 장(2026-10-18 hybrid 에서 엔진으로 옮김, 0순위-B).

왜: Typecast 가 '최은경'을 '최화정', '이영자'를 '미영자'로 읽어 TTS 전체를 21번 다시 불렀다(최은경 편). 표기('최, 은경')를
한 번 확인해 사전에 적어 두면 **모든 TTS 경로**(preset_make·하이브리드 렌더러·remake…)가 읽기 전에 바꿔 쓴다.
자막(text)은 원문 그대로 — 바꾸는 건 읽는 글(tts)뿐.

    from tools.calcopy.engine import name_dict as ND
    ND.spelling("최은경", voice_id)      # 사전 표기(없으면 원문)
    ND.apply_all("최은경 씨가 산", voice_id)   # 사전에 있는 모든 이름을 표기로(없는 이름은 손대지 않는다 → 결과 동일)
    ND.load() / ND.save(d)               # 갱신은 hybrid/name_check.check(이름 구절 합성·받아쓰기) 가 한다

사전 꼴: {"names": {"최은경": {"tts": "최, 은경", "voices": {"<voice_id>": "표기"}, "bad": [...], "verified": "..."}}}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DICT = Path(__file__).with_name("name_dict.json")


def load() -> dict:
    if not DICT.exists():
        return {"names": {}}
    return json.loads(DICT.read_text(encoding="utf-8"))


def save(d: dict) -> None:
    tmp = DICT.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, DICT)


def spelling(name: str, voice_id: str | None = None, d: dict | None = None) -> str:
    """이름 → TTS 표기. 성우별 표기가 있으면 그것, 없으면 공통 tts, 둘 다 없으면 원문."""
    ent = (d or load())["names"].get(name)
    if not ent:
        return name
    return (ent.get("voices") or {}).get(voice_id or "", None) or ent.get("tts") or name


def apply(text: str, name: str, voice_id: str | None = None, d: dict | None = None) -> str:
    """읽는 글에서 이름 하나를 표기로."""
    sp = spelling(name, voice_id, d)
    return text if sp == name or not text else text.replace(name, sp)


def apply_all(text: str, voice_id: str | None = None) -> str:
    """읽는 글에서 사전에 있는 모든 이름을 표기로. 긴 이름부터(겹침 방지). 사전에 없는 글은 그대로 돌아온다."""
    if not text:
        return text
    d = load()
    out = text
    for name in sorted(d["names"], key=len, reverse=True):
        if name in out:
            out = apply(out, name, voice_id, d)
    return out


def names_in(text: str) -> list[str]:
    """글에 들어 있는 사전 이름들(보고용)."""
    return [n for n in load()["names"] if n in (text or "")]
