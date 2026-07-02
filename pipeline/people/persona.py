"""persona.py — 질의 엔진: "이 종목 태린이라면 어떻게 볼까?"

그의 규칙(퍼널 로직)을 특정 종목에 적용해 판정. 접지된 결정론적 답변:
[발언]=그가 실제 한 말(원자), [데이터]=오늘 지표, [추론]=그의 프레임 적용.
할루시네이션 없음(LLM 미사용, 근거만 조립).
"""
import sys
import io


def _norm(s):
    return (s or "").replace(" ", "").lower()


def decide_verdict(leading: bool, vac: bool, up_ok: bool) -> str:
    """그의 규칙(퍼널 his모드)으로 판정 라벨 결정 — 순수 함수."""
    if leading and (vac or up_ok):
        return "탑픽 후보"
    if leading:
        return "관심 (주도지만 빈집·재료 약함)"
    if vac and up_ok:
        return "관망 (빈집+컨센이나 주도 미확인)"
    return "그의 기준 밖 (미해당)"


def stock_verdict(person: str, stock: str) -> dict:
    """종목 하나에 대한 '그라면' 판정."""
    from pipeline.people import funnel as _f
    from pipeline.people.rs_data import load_rs
    from pipeline.people.sortino_data import load_sortino_top
    from pipeline.people.people_query import atoms_for

    data = _f._load()
    stocks = data.get("stocks", {})
    smap = _f._sector_map()
    th = _f.THRESHOLDS

    # 종목 매칭 (정확 → 부분)
    q = _norm(stock)
    match = None
    for code, s in stocks.items():
        nm = s.get("name") or ""
        if _norm(nm) == q:
            match = (code, s); break
    if not match:
        for code, s in stocks.items():
            nm = s.get("name") or ""
            if q and q in _norm(nm):
                match = (code, s); break

    rs = load_rs()
    sortino = load_sortino_top()
    s_names = set(sortino.get("names") or [])
    s_sectors = [k for k in (sortino.get("sectors") or []) if k]

    # 그의 실제 발언 (해당 종목)
    quotes = [{"date": a["date"], "content": a["content"],
               "signal": a.get("signal"), "stance": a.get("stance_key") is not None}
              for a in atoms_for(person, asset=stock, days=45, limit=8)]

    if not match:
        # taerini에 없어도 발언은 있을 수 있음
        return {
            "stock": stock, "found_in_data": False,
            "quotes": quotes,
            "data": None,
            "verdict": "판단 보류" if quotes else "데이터·발언 없음",
            "reason": ["[데이터] taerini 지표에 이 종목 없음"] +
                      (["[발언] 그가 언급한 기록은 있음(위 인용)"] if quotes else
                       ["위키/원자에 이 종목 자료 없음 — 모름"]),
        }

    code, s = match
    name = s.get("name", stock)
    osc = s.get("osc") or {}
    tp = s.get("tp") or {}
    pct = osc.get("pct")
    up, down = tp.get("up_count", 0) or 0, tp.get("down_count", 0) or 0
    sector = smap.get(name) or (rs.get(name) or {}).get("sector")

    vac = pct is not None and pct <= th["vacuum_pct_max"]
    up_ok = up > down and up >= th["min_up_count"]
    leader = name in rs
    sortino_match = name in s_names or any(k in (sector or "") for k in s_sectors)
    leading = leader or sortino_match

    # 그의 규칙(퍼널 his모드) 적용 → 판정
    verdict = decide_verdict(leading, vac, up_ok)

    reason = []
    # [데이터]
    dparts = []
    dparts.append(f"수급빈집 {'O' if vac else 'X'}(pct {pct})")
    dparts.append(f"컨센 {'상향' if up_ok else '약함'}(↑{up}/↓{down})")
    dparts.append(f"주도주(RS) {'O' if leader else 'X'}" + (f"(3M {rs[name].get('m3')}%)" if leader else ""))
    dparts.append(f"소라티노 주도섹터 {'O' if sortino_match else 'X'}" + (f"({sector})" if sortino_match else ""))
    reason.append("[데이터] " + " · ".join(dparts))
    # [추론] 규칙
    if leading and (vac or up_ok):
        reason.append(f"[추론] 그의 규칙상 주도({'RS' if leader else '소라티노'}) 안에서 "
                      f"{'빈집' if vac else '컨센상향'}이라 → 탑픽 후보로 볼 것")
    elif leading:
        reason.append("[추론] 주도주이나 빈집·컨센이 약해 → 지금 진입보다 관심·대기")
    elif vac and up_ok:
        reason.append("[추론] 빈집+컨센은 좋으나 주도(RS/소라티노) 미확인 → 주도 확인 전 관망")
    else:
        reason.append("[추론] 빈집·주도·컨센 어느 것도 강하지 않아 → 그의 우선순위 밖")
    # [발언]
    if quotes:
        q0 = quotes[0]
        reason.append(f"[발언] 최근({q0['date']}): {q0['content'][:80]}")

    return {
        "stock": name, "code": code, "found_in_data": True,
        "verdict": verdict,
        "data": {"vacuum_pct": pct, "vacuum": vac, "consensus_up": up, "consensus_down": down,
                 "leader": leader, "sortino_match": sortino_match, "sector": sector,
                 "rs_m3": (rs.get(name) or {}).get("m3")},
        "quotes": quotes,
        "reason": reason,
    }


def decide_posture(bull: int, bear: int, has_cash: bool, has_defensive: bool) -> str:
    """비중/현금 자세 판정 — 순수 함수."""
    if bear > bull and (has_cash or has_defensive):
        return "방어 (비중 축소·현금 확대 성향)"
    if bull > bear and not has_defensive:
        return "공격 (비중 유지·확대 성향)"
    return "중립·선별 (섹터 갈아타기)"


def market_verdict(person: str) -> dict:
    """지금 시장 자세 — 비중 높일까 낮출까?"""
    from collections import Counter
    from pipeline.people.brain_view import market_insight
    from pipeline.people.people_query import atoms_for

    mkt = market_insight(person, days=10, limit=20)
    recent = atoms_for(person, days=7, limit=300)
    sig = Counter((a.get("signal") or "neutral") for a in recent)
    bull = sig.get("bullish", 0)
    bear = sig.get("bearish", 0) + sig.get("risk", 0)
    cash = [a for a in recent if "현금" in (a.get("content") or "")]
    defensive = [a for a in recent if "이탈" in (a.get("content") or "")
                 and ("축소" in a["content"] or "줄" in a["content"])]

    posture = decide_posture(bull, bear, bool(cash), bool(defensive))
    reason = [
        f"[데이터] 최근7일 신호 — 긍정 {bull} · 부정/리스크 {bear} · "
        f"현금언급 {len(cash)} · 이평선이탈축소 {len(defensive)}",
    ]
    reason.append(f"[추론] 그의 규칙(이평선 이탈→현금, 가속구간→비중확대)상 현재 → {posture}")
    if cash:
        reason.append(f"[발언] 현금 관련({cash[0]['date']}): {cash[0]['content'][:80]}")
    elif mkt:
        reason.append(f"[발언] 시장({mkt[0]['date']}): {mkt[0]['content'][:80]}")
    return {
        "query": "지금 시장 (비중 높일까/낮출까)",
        "verdict": posture,
        "data": {"bullish": bull, "bearish_risk": bear,
                 "cash_mentions": len(cash), "defensive": len(defensive)},
        "quotes": [{"date": a["date"], "content": a["content"]} for a in mkt[:5]],
        "reason": reason,
    }


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    person = sys.argv[1] if len(sys.argv) > 1 else "태린이아빠"
    stock = sys.argv[2] if len(sys.argv) > 2 else "삼성전자"
    v = stock_verdict(person, stock)
    print(f"[{person}] '{v['stock']}' → {v['verdict']}")
    for r in v["reason"]:
        print("  " + r)
