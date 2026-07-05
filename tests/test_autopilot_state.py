import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from autopilot_state import (
    load_state, save_state, touch_anomaly, should_diagnose, mark_diagnosed,
    resolve_if_healed, days_open, open_escalations, get_daily_stats,
)


def test_load_state_missing_file_returns_empty(tmp_path):
    assert load_state(str(tmp_path / "nope.json")) == {}


def test_save_and_load_state_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    state = {"ch1": {"first_detected": "2026-07-05"}}
    save_state(path, state)
    assert load_state(path) == state


def test_touch_anomaly_creates_new_entry_and_bumps_detected():
    state = {}
    touch_anomaly(state, "ch1", "2026-07-05")
    assert state["ch1"]["first_detected"] == "2026-07-05"
    assert state["ch1"]["last_seen"] == "2026-07-05"
    assert get_daily_stats(state, "2026-07-05")["detected"] == 1


def test_touch_anomaly_repeat_same_day_does_not_double_count_detected():
    state = {}
    touch_anomaly(state, "ch1", "2026-07-05")
    touch_anomaly(state, "ch1", "2026-07-05")
    assert get_daily_stats(state, "2026-07-05")["detected"] == 1


def test_touch_anomaly_preserves_first_detected_across_days():
    state = {}
    touch_anomaly(state, "ch1", "2026-07-05")
    touch_anomaly(state, "ch1", "2026-07-06")
    assert state["ch1"]["first_detected"] == "2026-07-05"
    assert state["ch1"]["last_seen"] == "2026-07-06"


def test_should_diagnose_true_for_new_channel():
    assert should_diagnose({}, "ch1", "2026-07-05") is True


def test_should_diagnose_false_if_already_diagnosed_today():
    state = {"ch1": {"diagnosed_dates": ["2026-07-05"]}}
    assert should_diagnose(state, "ch1", "2026-07-05") is False


def test_should_diagnose_true_next_day():
    state = {"ch1": {"diagnosed_dates": ["2026-07-05"]}}
    assert should_diagnose(state, "ch1", "2026-07-06") is True


def test_mark_diagnosed_escalated_keeps_entry_and_bumps_stat():
    state = {"ch1": {"first_detected": "2026-07-05", "diagnosed_dates": [], "latest_outcome": None}}
    mark_diagnosed(state, "ch1", "2026-07-05", "escalated")
    assert state["ch1"]["latest_outcome"] == "escalated"
    assert "2026-07-05" in state["ch1"]["diagnosed_dates"]
    assert get_daily_stats(state, "2026-07-05")["escalated"] == 1


def test_mark_diagnosed_auto_fixed_removes_entry_and_bumps_stat():
    state = {"ch1": {"first_detected": "2026-07-05", "diagnosed_dates": [], "latest_outcome": None}}
    mark_diagnosed(state, "ch1", "2026-07-05", "auto_fixed")
    assert "ch1" not in state
    assert get_daily_stats(state, "2026-07-05")["auto_fixed"] == 1


def test_resolve_if_healed_returns_none_if_not_tracked():
    assert resolve_if_healed({}, "ch1", "2026-07-05") is None


def test_resolve_if_healed_pops_and_returns_days_open():
    state = {"ch1": {"first_detected": "2026-07-03"}}
    result = resolve_if_healed(state, "ch1", "2026-07-05")
    assert result == {"channel": "ch1", "first_detected": "2026-07-03", "days_open": 3}
    assert "ch1" not in state


def test_days_open_counts_inclusive():
    entry = {"first_detected": "2026-07-05"}
    assert days_open(entry, "2026-07-05") == 1
    assert days_open(entry, "2026-07-07") == 3


def test_open_escalations_filters_only_escalated_and_skips_meta():
    state = {
        "ch1": {"latest_outcome": "escalated"},
        "ch2": {"latest_outcome": "auto_fixed"},
        "_daily_stats": {"date": "2026-07-05", "detected": 1},
    }
    assert list(open_escalations(state).keys()) == ["ch1"]


def test_get_daily_stats_returns_zeros_for_different_date():
    state = {"_daily_stats": {"date": "2026-07-04", "detected": 5}}
    assert get_daily_stats(state, "2026-07-05") == {"detected": 0, "auto_fixed": 0, "escalated": 0}
