# -*- coding: utf-8 -*-
"""칼카피 목소리 명단 — 주인 한 곳(kal·회원 PC 설정 화면 catalog 가 이것만 본다). 원래 kal.py 에 있던 표를 옮김(10-21, 회원 PC 가 kal 없이 읽게)."""

KNOWN_VOICES = [  # 칼카피 목소리 명단(사장님 10-20 확정 — 시작 문서 §12): 여 = 미나·문정·유라 / 남 = 박창수·지훈. 필재 금지(빠르면 발음 뭉개짐).
    # 주인 칸은 판 파일 voice 한 곳(여기는 후보 표만). 빠르게 돌리면 반드시 받아쓰기 되돌림으로 발음 확인(§12).
    {"name": "미나", "voice_id": "kr-mina-expressive", "engine": "일레븐랩스", "gender": "여", "note": "잇썸홈판·키치잇판·스타픽룸판, 배속 1.35 고정"},
    {"name": "문정", "voice_id": "tc_68f9c6a72f0f04a417bb136f", "engine": "타입캐스트", "gender": "여", "note": "차분·단정 — 아이템홈 1편·핫템 3호(6.52자/초)"},
    {"name": "유라", "voice_id": "tc_61130d6cf89dd58a4c13295d", "engine": "타입캐스트", "gender": "여", "note": "젊은 광고 나레 — 8.7~8.8자/초 실적"},
    {"name": "박창수", "voice_id": "tc_6059dad0b83880769a50502f", "engine": "타입캐스트", "gender": "남", "note": "재미썸홈판·꿀템노트판·썰템쇼"},
    {"name": "지훈", "voice_id": "tc_61f0859907085fc68561c9a1", "engine": "타입캐스트", "gender": "남", "note": "샥탬스토리(f0 129Hz)"},
]
BANNED_VOICES = {"tc_68257f68bc6e3c161ab5078d": "필재 — 빠르게 하면 발음이 계속 이상하게 된다(사장님 10-20)"}


# ── 회원 목소리 넓히기(관제 266, 사장님 10-26): 숏템 추천 성우(일레븐 14·피쉬) + 세 엔진 검색 성우 + 타입캐스트 감정 ──────────────
# 판단 주인 = 여기 한 곳. 회원 설정 저장 관문(preview_request.check)·제작기(preset_make.load_work/tts)가 이것만 부른다.
# KNOWN_VOICES 는 칼카피 '추천 명단'(설명 칸)일 뿐 허용 목록이 아니다 — 허용은 provider 별 형식 + 필재 금지.
import json as _json
import pathlib as _pathlib
import re as _re

PROVIDERS = ("typecast", "elevenlabs", "fish")
TC_EMOTIONS = ("angry", "happy", "normal", "sad", "tonedown", "toneup", "whisper")   # 팩 tts.emotion 한 곳 — 타입캐스트만
_ID_RE = {"typecast": _re.compile(r"tc_[0-9a-f]{24}"),
          "elevenlabs": _re.compile(r"kr-[a-z0-9]+-[a-z]+|[A-Za-z0-9]{20}"),     # 숏템 추천 프리셋 id | 일레븐 검색 성우 id
          "fish": _re.compile(r"fs-[a-z0-9]+-[a-z]+|[0-9a-f]{32}")}              # 숏템 추천 프리셋 id | 피쉬 검색 성우(reference_id)
_PRESETS = _pathlib.Path(__file__).resolve().parents[3] / "shopping_shorts" / "assets" / "voice_presets.json"


def preset_row(preset_id: str) -> dict | None:
    """숏템 추천 성우 프리셋(voice_presets.json) 한 줄 — 'kr-…'(일레븐)·'fs-…'(피쉬)·'tc-…'(타입캐스트)."""
    try:
        d = _json.loads(_PRESETS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = d if isinstance(d, list) else next(iter(d.values()), [])
    return next((r for r in rows if r.get("preset_id") == preset_id), None)


def provider_of(tts: dict) -> str | None:
    """명시한 provider 그대로. 없으면(옛 팩) voice_id 꼴로 — tc_ = 타입캐스트, kr- = 일레븐(미나), fs- = 피쉬. 모르면 None."""
    p = (tts or {}).get("provider")
    if p:
        return p
    v = str((tts or {}).get("voice_id") or "")
    return "typecast" if v.startswith("tc_") else "elevenlabs" if v.startswith("kr-") else "fish" if v.startswith("fs-") else None


def emotion_of(tts: dict) -> str | None:
    """합성에 넘길 감정 — 'normal'·빈 값은 감정 없음(None, 타입캐스트 build_payload 도 normal 은 안 보낸다 = 옛 캐시와 같은 소리)."""
    e = (tts or {}).get("emotion")
    return None if e in (None, "", "normal") else e


def is_banned(v: dict) -> str | None:
    """필재는 어느 provider 든 거절 — voice_id·preset_id(→base_voice_id)·이름 셋 다 본다."""
    vid, pid = str(v.get("voice_id") or ""), str(v.get("preset_id") or "")
    for x in (vid, pid, (preset_row(vid) or {}).get("base_voice_id"), (preset_row(pid) or {}).get("base_voice_id")):
        if x and x in BANNED_VOICES:
            return BANNED_VOICES[x]
    if str(v.get("name") or "").strip() == "필재":
        return BANNED_VOICES["tc_68257f68bc6e3c161ab5078d"]
    return None


def check_tts(tts: dict, allow_banned: bool = False) -> list[str]:
    """팩 tts 칸 검사 → 거절 사유 목록(빈 목록 = 통과). provider 값·voice_id 형식·추천 프리셋 존재·emotion(타입캐스트만, 허용 값)·필재.
    alternates 도 같은 provider 규칙으로 본다(provider 를 적으면 그 값, 없으면 위 칸 provider)."""
    err = []
    tts = tts or {}
    rows = [("", tts)] + [(f"대체 {i + 1} ", a) for i, a in enumerate(tts.get("alternates") or []) if isinstance(a, dict)]
    for tag, v in rows:
        if not v.get("voice_id"):
            if v.get("emotion") is not None or v.get("provider") is not None:
                err.append(f"{tag}목소리(voice_id)가 없습니다")
            continue
        prov = provider_of(v) if not tag else (provider_of(v) or provider_of(tts))
        vid = str(v.get("voice_id") or "")
        who = v.get("name") or vid
        if prov not in PROVIDERS:
            err.append(f"{tag}모르는 목소리 엔진: {v.get('provider') or vid}(typecast·elevenlabs·fish 만)")
            continue
        if not _ID_RE[prov].fullmatch(vid):
            err.append(f"{tag}목소리 id 형식이 {prov} 와 맞지 않습니다: {who}")
            continue
        if vid[:3] in ("kr-", "fs-") and not preset_row(vid):
            err.append(f"{tag}모르는 추천 성우: {who}")
        if not allow_banned and is_banned(v):
            err.append(f"{tag}쓸 수 없는 목소리: {who} — {is_banned(v)}")
        e = v.get("emotion")
        if e is not None:
            if prov != "typecast":
                err.append(f"{tag}감정(emotion)은 타입캐스트 목소리에만 씁니다({prov} 는 거절)")
            elif e not in TC_EMOTIONS:
                err.append(f"{tag}모르는 감정: {e}({'·'.join(TC_EMOTIONS)})")
    return err
