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
import re
from pathlib import Path

DICT = Path(__file__).with_name("name_dict.json")


def josa(word: str, pair: str = "이/가") -> str:
    """받침으로 조사 고르기 — '손태영'+'이' / '손태영 씨'+'가'. 10-18 손태영: 시험 문장이 '손태영가'로 비문이었다."""
    a, b = pair.split("/")
    w = (word or "").rstrip()
    if not w:
        return b
    ch = w[-1]
    if "가" <= ch <= "힣":
        return a if (ord(ch) - 0xAC00) % 28 else b
    if ch.isdigit():
        return a if ch in "013678" else b
    return b


def heard_ok(name: str, text: str, d: dict | None = None) -> bool:
    """받아쓰기 글에 이름이 들렸나 — 사전 heard_ok(연음·오인식 허용 표기, 예 '한혜진'→'한예진')도 이름으로 친다. 10-18 한혜진 편 A11' 거짓 ×."""
    t = re.sub(r"[^0-9A-Za-z가-힣]", "", text or "")
    if name in t:
        return True
    ent = (d or load())["names"].get(name) or {}
    return any(a and a in t for a in ent.get("heard_ok") or [])


def load() -> dict:
    if not DICT.exists():
        return {"names": {}}
    return json.loads(DICT.read_text(encoding="utf-8"))


def save(d: dict) -> None:
    tmp = DICT.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, DICT)


def update(name: str, fn) -> dict:
    """잠금 아래 읽기-수정-쓰기: fn(entry) 가 그 이름 항목을 고친다 — 두 세션이 동시에 돌려도 서로 덮어쓰지 않는다(10-18 한혜진 두 목소리 동시)."""
    from tools.calcopy.engine.filelock import locked
    with locked(DICT):
        d = load()
        ent = d["names"].setdefault(name, {"tts": name, "bad": [], "voices": {}})
        fn(ent)
        save(d)
        return ent


def spelling(name: str, voice_id: str | None = None, d: dict | None = None) -> str:
    """이름 → TTS 표기. 성우별 표기가 있으면 그것, 없으면 공통 tts, 둘 다 없으면 원문."""
    ent = (d or load())["names"].get(name)
    if not ent:
        return name
    return (ent.get("voices") or {}).get(voice_id or "", None) or ent.get("tts") or name


def apply(text: str, name: str, voice_id: str | None = None, d: dict | None = None) -> str:
    """읽는 글에서 이름 하나를 표기로. 이미 표기로 적힌 자리는 다시 바꾸지 않는다(10-18 한혜진: '한혜진 씨가' + 표기 '한혜진 씨' → '씨 씨가')."""
    sp = spelling(name, voice_id, d)
    if sp == name or not text:
        return text
    # 이미 표기로 적힌 자리는 잠가 둔다(접두 '방송인 ' 이 붙은 표기도 — 10-18 최화정·서인영·채정안 '방송인 OO 씨 씨').
    keep: list[str] = []

    def _lock(m):
        keep.append(m.group(0))
        return f"\x00{len(keep) - 1}\x00"

    out = re.sub(re.escape(sp), _lock, text)
    ssi = sp.rstrip().endswith("씨")
    pat = re.escape(name) + (r"(?:\s?씨)?" if ssi else "") + _JOSA_RE

    def _sub(m):
        j = m.group("j")
        if not j:
            return sp
        return sp + (josa(sp, _JOSA[j]) if j in _JOSA else j)

    out = re.sub(pat, _sub, out)
    return re.sub("\x00(\\d+)\x00", lambda m: keep[int(m.group(1))], out)


# 이름 뒤 조사 → 받침 짝. 표기가 '… 씨'(받침 없음)로 바뀌면 '최화정이'→'… 씨가'로 다시 고른다(10-18 다섯 편이 손으로 고침).
_PAIRS = ["이랑/랑", "이에요/예요", "이었/였", "이야/야", "으로/로", "과/와", "은/는", "을/를", "이/가"]
_JOSA = {w: p for p in _PAIRS for w in p.split("/")}
_JOSA_RE = "(?P<j>" + "|".join(sorted(map(re.escape, _JOSA), key=len, reverse=True)) + ")?"


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
