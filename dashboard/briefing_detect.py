"""market_flow 임계치 감지 — AI 호출 없이 숫자 비교만으로 속보 이벤트 생성.
서버 재시작 직후(prev=None)는 기준선이 없어 오탐이 나므로 값만 저장하고 알림은 안 낸다."""
from datetime import datetime

_INDEX_THRESHOLD_PP = 1.0        # 지수 등락률 %p
_PROG_THRESHOLD = 50000          # 프로그램 순매수 변동(백만원 단위, 500억)

_LABELS = {
    "J_change_rate": "코스피 등락률",
    "Q_change_rate": "코스닥 등락률",
    "J_investor_외인": "코스피 외국인 수급",
    "J_investor_기관": "코스피 기관 수급",
    "Q_investor_외인": "코스닥 외국인 수급",
    "Q_investor_기관": "코스닥 기관 수급",
    "J_prog_합계": "코스피 프로그램 순매수",
    "Q_prog_합계": "코스닥 프로그램 순매수",
}


def detect_alerts(prev: dict | None, curr: dict) -> list[dict]:
    if prev is None:
        return []
    ts = datetime.now().strftime("%H:%M")
    out = []

    for mkt in ("J", "Q"):
        p_rate = (prev.get(f"{mkt}_price") or {}).get("change_rate")
        c_rate = (curr.get(f"{mkt}_price") or {}).get("change_rate")
        if p_rate is not None and c_rate is not None and abs(c_rate - p_rate) >= _INDEX_THRESHOLD_PP:
            metric = f"{mkt}_change_rate"
            out.append({"ts": ts, "metric": metric, "from": p_rate, "to": c_rate,
                        "label": _LABELS[metric]})

        for who in ("외인", "기관"):
            p_v = (prev.get(f"{mkt}_investor") or {}).get(who)
            c_v = (curr.get(f"{mkt}_investor") or {}).get(who)
            if p_v is not None and c_v is not None and p_v != 0 and c_v != 0:
                if (p_v > 0) != (c_v > 0):
                    metric = f"{mkt}_investor_{who}"
                    out.append({"ts": ts, "metric": metric, "from": p_v, "to": c_v,
                                "label": _LABELS[metric]})

        p_prog = (prev.get(f"{mkt}_prog") or {}).get("합계")
        c_prog = (curr.get(f"{mkt}_prog") or {}).get("합계")
        if p_prog is not None and c_prog is not None and abs(c_prog - p_prog) >= _PROG_THRESHOLD:
            metric = f"{mkt}_prog_합계"
            out.append({"ts": ts, "metric": metric, "from": p_prog, "to": c_prog,
                        "label": _LABELS[metric]})

    return out


def compute_index_shape(bars: list[dict]) -> dict | None:
    """지수 15분봉에서 시가/저점/고점/현재가를 계산 — Gemini에게 넘길 실측 재료.
    AI가 차트를 직접 해석하게 두지 않고, 계산된 사실만 근거로 쓰게 해서 환각을 막는다."""
    if not bars or len(bars) < 2:
        return None

    def _fmt(t: str) -> str:
        t = str(t or "").zfill(6)
        return f"{t[:2]}:{t[2:4]}"

    open_bar = bars[0]
    current_bar = bars[-1]
    low_bar = min(bars, key=lambda b: b["price"])
    high_bar = max(bars, key=lambda b: b["price"])
    return {
        "open": open_bar["price"],
        "low": low_bar["price"], "low_t": _fmt(low_bar["t"]),
        "high": high_bar["price"], "high_t": _fmt(high_bar["t"]),
        "current": current_bar["price"],
    }
