"""시그널 픽 일일 백테스팅.

매일 시그널 상위 픽(score>=4)을 entry_close와 함께 picks_log.jsonl에 누적 기록하고,
매일 최신 종가로 사후 수익률을 갱신해 backtest_summary.json을 만든다.
→ 9점 시스템이 실제로 먹히는지(승률·평균수익) 검증한다.

가격원: 한국상대강도 엑셀 '종가' 시트 (매일 다운로드됨, 컬럼=종목명, 행=날짜).
실행: python -m pipeline.backtest_signal
"""
import json
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).parent.parent
SIG_DIR = ROOT / "output" / "signal"
PICKS_LOG = SIG_DIR / "picks_log.jsonl"
SUMMARY = SIG_DIR / "backtest_summary.json"
SCORE_THRESHOLD = 4  # 픽 기준점수


def load_latest_prices():
    """한국상대강도 종가 시트 → ({종목명: 최신종가}, 최신날짜)."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import ingest_excel as ie
    path = ie.find_excel("한국상대강도")
    if not path:
        return {}, None
    wb = ie.load_wb(path)
    if not wb or "종가" not in wb.sheetnames:
        return {}, None
    ws = wb["종가"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return {}, None
    headers = [str(v).strip() if v else None for v in rows[0]]
    latest, last_date = {}, None
    for row in rows[1:]:
        if row[0] is None:
            continue
        last_date = row[0]
        for c, h in enumerate(headers[1:], 1):
            if not h:
                continue
            v = row[c] if c < len(row) else None
            if isinstance(v, (int, float)):
                latest[h] = float(v)  # 마지막 유효값으로 갱신 → 최신 종가
    return latest, (str(last_date)[:10] if last_date else None)


def forward_return(entry, current):
    if not entry or not current:
        return None
    return round((current - entry) / entry * 100, 2)


def _read_log():
    if not PICKS_LOG.exists():
        return []
    out = []
    for line in PICKS_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _append_log(rows):
    SIG_DIR.mkdir(parents=True, exist_ok=True)
    with PICKS_LOG.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def log_today(snapshot, prices, today):
    """오늘 score>=THRESHOLD 픽을 방식(A/B)별로 entry_close와 함께 기록.
    각 방식이 선택한 섹터의 종목만 그 방식 픽으로 본다. 같은 날·방식·종목 중복 방지."""
    methods = snapshot.get("stage2", {}).get("methods", {})
    already = {(r["pick_date"], r.get("method"), r["name"]) for r in _read_log()}
    top = [s for s in snapshot.get("stage3", {}).get("stocks", [])
           if s.get("score", 0) >= SCORE_THRESHOLD]
    new = []
    for method, sectors in methods.items():
        secset = set(sectors)
        for s in top:
            if s.get("sector") not in secset:
                continue
            if (today, method, s["name"]) in already:
                continue
            entry = prices.get(s["name"])
            if entry is None:
                continue  # 가격 없으면 추적 불가
            new.append({
                "pick_date": today, "method": method, "name": s["name"],
                "code": s.get("code"), "score": s["score"],
                "vacancy": s.get("vacancy"), "sector": s.get("sector"),
                "entry_close": entry,
            })
    _append_log(new)
    return new


def _agg(subset):
    if not subset:
        return {"n": 0, "win_rate": None, "avg_return": None}
    wins = sum(1 for p in subset if p["return_pct"] > 0)
    return {
        "n": len(subset),
        "win_rate": round(wins / len(subset) * 100, 1),
        "avg_return": round(sum(p["return_pct"] for p in subset) / len(subset), 2),
    }


def evaluate(prices, today):
    """누적 픽을 최신 종가로 평가하고 방식(A/B)별로 비교 집계한다."""
    picks = []
    for r in _read_log():
        cur = prices.get(r["name"])
        days = (date.fromisoformat(today) - date.fromisoformat(r["pick_date"])).days
        picks.append({**r, "current_close": cur,
                      "return_pct": forward_return(r["entry_close"], cur),
                      "days_held": days})
    rated = [p for p in picks if p["return_pct"] is not None and p["days_held"] > 0]
    methods = sorted({p.get("method") for p in picks if p.get("method")})
    by_method = {}
    for m in methods:
        sub = [p for p in rated if p.get("method") == m]
        by_method[m] = {
            **_agg(sub),
            "by_score": {str(sc): _agg([p for p in sub if p["score"] == sc])
                         for sc in sorted({p["score"] for p in sub})},
        }
    return {
        "as_of": today,
        "overall": _agg(rated),
        "by_method": by_method,
        "by_vacancy": {v: _agg([p for p in rated if p["vacancy"] == v])
                       for v in sorted({p["vacancy"] for p in rated if p["vacancy"]})},
        "picks": sorted(picks, key=lambda p: (p["return_pct"] is not None,
                                              p["return_pct"] or -999), reverse=True)[:60],
    }


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    snap_path = SIG_DIR / "signal_snapshot.json"
    snapshot = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
    prices, price_date = load_latest_prices()
    logged = log_today(snapshot, prices, today)
    summary = evaluate(prices, today)
    summary["price_date"] = price_date
    SIG_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    o = summary["overall"]
    print(f"백테스트: 오늘 신규픽 {len(logged)} | 누적평가 {o['n']} | "
          f"승률 {o['win_rate']} | 평균 {o['avg_return']}% | 가격일 {price_date}")
    return summary


if __name__ == "__main__":
    main()
