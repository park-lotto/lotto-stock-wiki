"""Whisper(GROQ)로 TTS mp3를 재전사해 원문과 diff → 오독/탈락 자동경보(튜닝 작업대용).

키 없으면 transcribe가 None(작업대는 diff 없이 재생만). 순수 diff는 키와 무관하게 동작."""
import re
import difflib

import requests

from shopping_shorts import config

_GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_MODEL = "whisper-large-v3"


def _tokens(text):
    """비교용 토큰화: 감정태그([..])·문장부호 제거, 공백분리, 소문자."""
    text = re.sub(r"\[[^\]]+\]", " ", text)
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


def transcribe_words(mp3_path):
    """GROQ Whisper verbose_json으로 워드 타임스탬프 재전사.
    성공 → [{"word","start","end"}, …](발화 순서). 키 없음·실패·워드 없음 → None.
    (transcribe와 같은 graceful 계약: 예외를 삼켜 None. 호출부가 폴백한다.)"""
    if not config.GROQ_API_KEY:
        return None
    try:
        with open(mp3_path, "rb") as f:
            r = requests.post(
                _GROQ_URL,
                headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                files={"file": (mp3_path, f, "audio/mpeg")},
                data={"model": _MODEL, "language": "ko",
                      "response_format": "verbose_json",
                      "timestamp_granularities[]": "word"},
                timeout=60)
        r.raise_for_status()
        raw = r.json().get("words")
        if not raw:
            return None
        out = []
        for w in raw:
            if "word" in w and "start" in w and "end" in w:
                out.append({"word": w["word"], "start": float(w["start"]),
                            "end": float(w["end"])})
        return out or None
    except Exception:
        return None
