from pipeline import backtest_signal as bt


def test_forward_return():
    assert bt.forward_return(100, 110) == 10.0
    assert bt.forward_return(100, 95) == -5.0
    assert bt.forward_return(None, 100) is None
    assert bt.forward_return(100, None) is None


def test_agg_win_rate_and_avg():
    subset = [{"return_pct": 10.0}, {"return_pct": -4.0}, {"return_pct": 6.0}]
    a = bt._agg(subset)
    assert a["n"] == 3
    assert a["win_rate"] == 66.7   # 2/3
    assert a["avg_return"] == 4.0  # (10-4+6)/3


def test_agg_empty():
    a = bt._agg([])
    assert a == {"n": 0, "win_rate": None, "avg_return": None}


def test_log_today_filters_and_dedups(tmp_path, monkeypatch):
    # 로그 파일을 임시경로로
    monkeypatch.setattr(bt, "PICKS_LOG", tmp_path / "picks.jsonl")
    monkeypatch.setattr(bt, "SIG_DIR", tmp_path)
    snapshot = {"stage3": {"stocks": [
        {"name": "A", "code": "1", "score": 4, "vacancy": "A", "sector": "반도체"},
        {"name": "B", "code": "2", "score": 2, "vacancy": "C", "sector": "조선"},   # score<4 제외
        {"name": "C", "code": "3", "score": 5, "vacancy": "A", "sector": "로봇"},
    ]}}
    prices = {"A": 1000.0, "C": 2000.0}  # B는 가격 없음
    new = bt.log_today(snapshot, prices, "2026-06-22")
    names = {r["name"] for r in new}
    assert names == {"A", "C"}              # score>=4 & 가격있음만
    # 같은 날 재실행 → 중복 없음
    again = bt.log_today(snapshot, prices, "2026-06-22")
    assert again == []


def test_evaluate_computes_returns(tmp_path, monkeypatch):
    monkeypatch.setattr(bt, "PICKS_LOG", tmp_path / "picks.jsonl")
    monkeypatch.setattr(bt, "SIG_DIR", tmp_path)
    bt._append_log([
        {"pick_date": "2026-06-20", "name": "A", "code": "1", "score": 4,
         "vacancy": "A", "sector": "반도체", "entry_close": 1000.0},
    ])
    prices = {"A": 1100.0}
    summary = bt.evaluate(prices, "2026-06-22")
    assert summary["overall"]["n"] == 1
    assert summary["overall"]["avg_return"] == 10.0
    assert summary["overall"]["win_rate"] == 100.0
    assert summary["picks"][0]["return_pct"] == 10.0
    assert summary["picks"][0]["days_held"] == 2
