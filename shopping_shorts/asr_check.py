"""Whisper(GROQ)로 TTS mp3를 재전사해 원문과 diff → 오독/탈락 자동경보(튜닝 작업대용).

키 없으면 transcribe가 None(작업대는 diff 없이 재생만). 순수 diff는 키와 무관하게 동작."""
import os
import re
import difflib

import requests

from shopping_shorts import config
from shopping_shorts.narration_naturalize import normalize_reading

_GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_MODEL = "whisper-large-v3"


def _tokens(text):
    """비교용 토큰화: 감정태그([..]) 제거 → 숫자·단위·기호를 읽기말로 정규화
    (ref·hyp 양쪽 동일 적용) → 문장부호 제거 → 공백분리.

    normalize_reading을 여기서 재사용한다 — Whisper가 성우가 읽은 '삼 점 오
    킬로그램'을 '3.5kg'로 되표기(또는 그 반대)해도 양쪽을 같은 읽기말로 맞춰야
    성우가 제대로 읽은 게 오독으로 안 뜬다(설계 의도, narration_naturalize.py
    normalize_reading docstring). 태그는 정규화 전에 걷어낸다 — `[` 등 대괄호가
    숫자 옆에 붙어 있으면 단위/기호 매칭을 흐트러뜨릴 수 있어서다."""
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = normalize_reading(text)[0]
    text = re.sub(r"[^\w가-힣\s]", " ", text)
    return [t for t in text.split() if t]


def diff_words(ref_text, hyp_text):
    """원문 ref vs 재전사 hyp → {ok, words:[{kind, ref, hyp}]}. kind: equal|sub|del|ins."""
    ref, hyp = _tokens(ref_text), _tokens(hyp_text)
    sm = difflib.SequenceMatcher(a=ref, b=hyp)
    words = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                words.append({"kind": "equal", "ref": ref[k], "hyp": ref[k]})
        elif tag == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                words.append({"kind": "sub",
                              "ref": ref[i1 + k] if i1 + k < i2 else "",
                              "hyp": hyp[j1 + k] if j1 + k < j2 else ""})
        elif tag == "delete":
            for k in range(i1, i2):
                words.append({"kind": "del", "ref": ref[k], "hyp": ""})
        elif tag == "insert":
            for k in range(j1, j2):
                words.append({"kind": "ins", "ref": "", "hyp": hyp[k]})
    ok = all(w["kind"] == "equal" for w in words)
    return {"ok": ok, "words": words}


def mismatch_score(diff):
    """오독 점수(낮을수록 좋음) = 불일치 토큰 수. N-best ranker로 사용."""
    return sum(1 for w in diff["words"] if w["kind"] != "equal")


def transcribe(mp3_path):
    """GROQ Whisper로 재전사. 키 없으면 None. 실패 시 None(작업대는 graceful)."""
    if not config.GROQ_API_KEY:
        return None
    try:
        with open(mp3_path, "rb") as f:
            r = requests.post(_GROQ_URL,
                              headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                              files={"file": (mp3_path, f, "audio/mpeg")},
                              data={"model": _MODEL, "language": "ko"}, timeout=60)
        r.raise_for_status()
        return r.json().get("text", "")
    except Exception:
        return None


_LAST = __import__("threading").local()   # 직전 실패 사유(스레드별) — last_error()


def transcribe_words(mp3_path, language="ko"):
    """GROQ Whisper verbose_json으로 워드 타임스탬프 재전사.
    성공 → [{"word","start","end"}, …](발화 순서). 키 없음·실패·워드 없음 → None.
    (transcribe와 같은 graceful 계약: 예외를 삼켜 None. 호출부가 폴백한다.)

    language: 기본 "ko"(우리 TTS 검수용 — 종전 동작 그대로). **None이면 언어 자동 감지** —
    소스 영상 전사(frame_script)는 외국 영상이 많아 "ko" 고정이면 중국어·영어를 한국어로
    엉터리 받아쓴다(2026-09-04). 호출부가 원문 언어를 알아서 번역까지 한다."""
    _LAST.error = ""
    if not config.GROQ_API_KEY:
        _LAST.error = "no_groq_key"
        return None
    try:
        data = {"model": _MODEL, "response_format": "verbose_json",
                "timestamp_granularities[]": "word"}
        if language:
            data["language"] = language
        # ★파일명은 반드시 str — Path를 그대로 주면 requests가 .translate()를 불러
        #   AttributeError로 죽는다(2026-09-05 서버 실측: 전사 0/30의 뿌리).
        #   경로 전체가 아니라 basename만 보낸다(한글 절대경로·서버 경로 노출 방지).
        fname = os.path.basename(str(mp3_path)) or "audio.mp3"
        with open(mp3_path, "rb") as f:
            r = requests.post(
                _GROQ_URL,
                headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                files={"file": (fname, f, "audio/mpeg")},
                data=data,
                timeout=60)
        if getattr(r, "status_code", 200) >= 400:      # 테스트 가짜 응답엔 status_code가 없다
            # ★사유를 남긴다(2026-09-05): 종전엔 raise_for_status→except가 삼켜 429·401을 구분할 길이 없었다
            #   (서버 30편 전사 0/30인데 원인 모름). 계약(None 반환)은 그대로다.
            _LAST.error = f"HTTP {r.status_code} {(r.text or '')[:120]}"
            return None
        raw = r.json().get("words")
        if not raw:
            _LAST.error = "no_words"
            return None
        out = []
        for w in raw:
            if "word" in w and "start" in w and "end" in w:
                out.append({"word": w["word"], "start": float(w["start"]),
                            "end": float(w["end"])})
        if not out:
            _LAST.error = "no_words"
        return out or None
    except Exception as e:  # noqa: BLE001 — graceful 계약 유지, 사유만 남긴다
        _LAST.error = f"exception: {e!r}"[:160]
        return None


def last_error():
    """직전 transcribe_words 실패 사유(스레드별). 성공이면 ""."""
    return getattr(_LAST, "error", "") or ""
