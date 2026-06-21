"""텔레그램 quote 원문 대조 (정답지 없음 → 유일한 1차 검증)."""


def _all_quotes(q: dict) -> list[str]:
    """질문지 내 모든 "quote" 키 값을 재귀적으로 수집."""
    out = []

    def walk(v):
        if isinstance(v, dict):
            for k, val in v.items():
                if k == "quote" and isinstance(val, str) and val.strip():
                    out.append(val.strip())
                else:
                    walk(val)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(q)
    return out


def verify_telegram_quotes(q: dict, md_text: str) -> list[dict]:
    """질문지 내 모든 quote가 md_text에 실제 존재하는지 검증.

    Args:
        q: 질문지 dict
        md_text: 원문 markdown 텍스트

    Returns:
        list[dict]: 플래그 목록. quote가 없으면 {"code":"TG_QUOTE_NOT_FOUND","msg":...}
    """
    flags = []
    for quote in _all_quotes(q):
        snippet = quote[:15].strip()
        if snippet and snippet not in md_text:
            flags.append({
                "code": "TG_QUOTE_NOT_FOUND",
                "msg": f"인용 미발견: '{snippet}...'"
            })
    return flags
