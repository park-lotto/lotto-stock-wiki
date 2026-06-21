"""Test daily health check functions."""
from pipeline.atoms.daily_health import compare_to_baseline, render_card


def test_atom_drop_orange():
    today = {"date": "2026-06-21", "atoms": {"telegram": 3}, "queue_new": 0, "pytest_ok": True}
    yest = {"atoms": {"telegram": 22}}
    alerts = compare_to_baseline(today, yest)
    assert any(a["level"] == "orange" and "telegram" in a["msg"] for a in alerts)


def test_pytest_fail_red():
    today = {"date": "2026-06-21", "atoms": {"telegram": 20}, "queue_new": 0, "pytest_ok": False}
    yest = {"atoms": {"telegram": 22}}
    alerts = compare_to_baseline(today, yest)
    assert any(a["level"] == "red" for a in alerts)


def test_queue_increase_yellow():
    today = {"date": "2026-06-21", "atoms": {"telegram": 20}, "queue_new": 5, "pytest_ok": True}
    yest = {"atoms": {"telegram": 22}}
    alerts = compare_to_baseline(today, yest)
    assert any(a["level"] == "yellow" for a in alerts)


def test_no_baseline_no_drop_alert():
    today = {"date": "2026-06-21", "atoms": {"telegram": 20}, "queue_new": 0, "pytest_ok": True}
    alerts = compare_to_baseline(today, {})
    assert not any(a["level"] == "orange" for a in alerts)


def test_render_card_normal_one_line():
    metrics = {"date": "2026-06-21", "atoms": {"telegram": 22, "news": 9}, "queue_new": 0, "pytest_ok": True}
    card = render_card(metrics, [])
    assert card.count("\n") <= 1
    assert "✅" in card


def test_render_card_alert_detailed():
    metrics = {"date": "2026-06-21", "atoms": {"telegram": 3}, "queue_new": 2, "pytest_ok": True}
    alerts = [{"level": "orange", "code": "ATOM_DROP", "msg": "telegram 22→3"}]
    card = render_card(metrics, alerts)
    assert "⚠️" in card
    assert "telegram 22→3" in card
