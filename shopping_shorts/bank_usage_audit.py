"""생성 순응 검열 — 빼쓰기(생성) 시 은행이 대본을 실제로 형성했나를 결정적으로 측정.

순수함수만(계산·판정). 저장·조회·Gemini는 호출부(mix_pipeline)가 한다.
기존 gemini_audit.py(넣기 쪽 검열)의 빼기 쪽 대응."""

_PARTS_MIN = 5
_BEAT_MIN = 5
# 신호등 임계 — 하나라도 걸리면 그 색(적신호가 주의를 이긴다).
_BANK_USED_MIN = 0.5
_CONFORMANCE_MIN = 0.7
_PLAGIARISM_MAX = 0.1
_ARC_MIN = 2.5   # 5점 만점


def _opener_ok(narration):
    """beats[0]이 강한 오프너인가 — edit_plan의 토큰 재사용."""
    from shopping_shorts.edit_plan import _STRONG_OPENER_TOKENS
    head = (narration or "").lstrip()[:14]
    return any(t.strip() and t.strip() in head for t in _STRONG_OPENER_TOKENS)


def structural_conformance(chosen_plan, snapshot, story):
    """선택 후보가 아크가 규정하는 '모양'을 가졌나 — LLM 없이."""
    beats = (chosen_plan or {}).get("beats") or []
    need = max((snapshot or {}).get("spine_beats") or 0, _BEAT_MIN)
    beat_ok = len(beats) >= need
    opener_ok = bool(beats) and _opener_ok(beats[0].get("narration"))
    cta_ok = bool(((story or {}).get("cta_line") or "").strip())
    plagiarism_hits = len((chosen_plan or {}).get("plagiarism_flags") or [])
    conformant = beat_ok and opener_ok and cta_ok and plagiarism_hits == 0
    return {"beat_ok": beat_ok, "opener_ok": opener_ok, "cta_ok": cta_ok,
            "plagiarism_hits": plagiarism_hits, "conformant": conformant}
