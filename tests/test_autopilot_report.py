import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from autopilot_report import render_slot_alert, render_healed_alert, render_daily_summary


def test_render_slot_alert_auto_fixed():
    text = render_slot_alert("12:10", "실시간주식뉴스", "auto_fixed",
                              root_cause="타임아웃 부족", summary="타임아웃 90초로 상향")
    assert "🟢" in text
    assert "실시간주식뉴스" in text
    assert "자동수정 완료" in text


def test_render_slot_alert_escalated():
    text = render_slot_alert("12:10", "그로쓰리서치특징주", "escalated",
                              root_cause="플랫폼 리드 제한 추정")
    assert "🔴" in text
    assert "사람 판단 필요" in text


def test_render_healed_alert():
    text = render_healed_alert("15:10", "그로쓰리서치특징주", 3)
    assert "✅" in text
    assert "3일만에" in text


def test_render_daily_summary_includes_open_escalations():
    text = render_daily_summary(
        "2026-07-05",
        {"checked": 5, "detected": 2, "auto_fixed": 1, "escalated": 1},
        {"ok": True, "failed_tests": []},
        {"stockbrain": {"active": True}, "crawlingbot": {"active": True}},
        {"그로쓰리서치특징주": {"first_detected": "2026-07-03", "days_open": 3}},
    )
    assert "3일째 미해결" in text
    assert "그로쓰리서치특징주" in text
    assert "1건 자동수정" in text


def test_render_daily_summary_no_open_escalations_says_so():
    text = render_daily_summary(
        "2026-07-05", {"checked": 5, "detected": 0, "auto_fixed": 0, "escalated": 0},
        {"ok": True, "failed_tests": []}, {"stockbrain": {"active": True}}, {})
    assert "미해결 에스컬레이션 없음" in text


def test_render_daily_summary_shows_pytest_failures():
    text = render_daily_summary(
        "2026-07-05", {"checked": 5, "detected": 0, "auto_fixed": 0, "escalated": 0},
        {"ok": False, "failed_tests": ["tests/test_a.py::test_x"]},
        {"stockbrain": {"active": True}}, {})
    assert "test_x" in text


def test_render_slot_alert_escalated_shows_summary_when_given():
    text = render_slot_alert("15:10", "실시간주식뉴스", "escalated",
                              root_cause="pytest 실패", summary="수정 후 pytest 실패 — 커밋 안 함")
    assert "수정 후 pytest 실패 — 커밋 안 함" in text
    assert "코드로 해결 불가 또는 실패" not in text  # summary가 있으면 제네릭 문구 대신 표시


def test_render_slot_alert_escalated_falls_back_to_generic_without_summary():
    text = render_slot_alert("15:10", "그로쓰리서치특징주", "escalated",
                              root_cause="플랫폼 리드 제한 추정")
    assert "코드로 해결 불가 또는 실패" in text
