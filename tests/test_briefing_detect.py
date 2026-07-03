import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_detect import detect_alerts, compute_index_shape


def _mk(j_rate=0.0, q_rate=0.0, j_foreign=0, j_org=0, j_prog=0):
    return {
        "J_price": {"price": 7500, "change_rate": j_rate},
        "Q_price": {"price": 830, "change_rate": q_rate},
        "J_investor": {"외인": j_foreign, "기관": j_org, "개인": 0},
        "Q_investor": {"외인": 0, "기관": 0, "개인": 0},
        "J_prog": {"차익": 0, "비차익": 0, "합계": j_prog},
        "Q_prog": {"차익": 0, "비차익": 0, "합계": 0},
    }


def test_no_baseline_returns_empty():
    """서버 재시작 직후(prev=None)는 알림을 만들지 않는다 — 오탐 방지."""
    assert detect_alerts(None, _mk(j_rate=5.0)) == []


def test_index_change_over_1pp_triggers_alert():
    prev = _mk(j_rate=0.5)
    curr = _mk(j_rate=1.8)   # 1.3%p 변동 > 1%p 임계치
    alerts = detect_alerts(prev, curr)
    assert len(alerts) == 1
    assert alerts[0]["metric"] == "J_change_rate"
    assert alerts[0]["from"] == 0.5 and alerts[0]["to"] == 1.8


def test_index_change_under_1pp_no_alert():
    prev = _mk(j_rate=0.5)
    curr = _mk(j_rate=1.2)   # 0.7%p 변동 < 1%p
    assert detect_alerts(prev, curr) == []


def test_foreign_sign_flip_triggers_alert():
    prev = _mk(j_foreign=-500)
    curr = _mk(j_foreign=300)   # 매도(-)→매수(+) 전환
    alerts = detect_alerts(prev, curr)
    assert any(a["metric"] == "J_investor_외인" for a in alerts)


def test_foreign_same_sign_no_alert():
    prev = _mk(j_foreign=-500)
    curr = _mk(j_foreign=-900)   # 계속 매도, 부호 안 바뀜
    assert not any(a["metric"] == "J_investor_외인" for a in [
        x for x in detect_alerts(prev, curr) if x["metric"] == "J_investor_외인"])


def test_program_trade_over_500eok_triggers_alert():
    prev = _mk(j_prog=0)
    curr = _mk(j_prog=60000)   # 600억(백만원 단위 60000) 변동 > 500억
    alerts = detect_alerts(prev, curr)
    assert any(a["metric"] == "J_prog_합계" for a in alerts)


def test_program_trade_under_500eok_no_alert():
    prev = _mk(j_prog=0)
    curr = _mk(j_prog=30000)   # 300억 < 500억
    assert not any(a["metric"] == "J_prog_합계" for a in detect_alerts(prev, curr))


def test_compute_index_shape_returns_none_for_insufficient_bars():
    assert compute_index_shape([]) is None
    assert compute_index_shape([{"t": "090000", "price": 100.0}]) is None


def test_compute_index_shape_finds_open_low_high_current():
    bars = [
        {"t": "090000", "price": 100.0},
        {"t": "093000", "price": 90.0},
        {"t": "103000", "price": 85.0},
        {"t": "113000", "price": 105.0},
        {"t": "120000", "price": 98.0},
    ]
    shape = compute_index_shape(bars)
    assert shape["open"] == 100.0
    assert shape["low"] == 85.0 and shape["low_t"] == "10:30"
    assert shape["high"] == 105.0 and shape["high_t"] == "11:30"
    assert shape["current"] == 98.0


def test_compute_index_shape_handles_flat_series():
    bars = [{"t": "090000", "price": 100.0}, {"t": "093000", "price": 100.0}]
    shape = compute_index_shape(bars)
    assert shape["open"] == shape["low"] == shape["high"] == shape["current"] == 100.0
