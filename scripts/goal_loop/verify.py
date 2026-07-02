"""아침 브리핑 검증·이상징후 감지 (순수 파이썬, LLM 불필요)."""
ANOM_INDEX_PCT = 3.0

def detect_anomalies(data: dict, date: str, index_moves: dict) -> list:
    flags = []
    for name, key in [("코스피", "kospi"), ("코스닥", "kosdaq")]:
        v = index_moves.get(key)
        if v is not None and abs(v) >= ANOM_INDEX_PCT:
            flags.append(f"{name} {v:+.1f}% 급변(±{ANOM_INDEX_PCT}%↑)")
    ddate = str(data.get("date") or "").strip()
    if ddate and ddate != date:
        flags.append(f"데이터 최신일({ddate})≠대상일({date}) 공백 의심")
    if data.get("date_check") is False:
        flags.append("날짜검증 실패")
    return flags
