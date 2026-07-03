from datetime import datetime
from scripts.goal_loop import morning_brief as mb


def test_runs_weekday_0800_once():
    now = datetime(2026, 7, 2, 8, 3)   # 목요일 08:03
    assert mb.should_run_now(now, None) is True
    assert mb.should_run_now(now, "2026-07-02") is False   # 이미 오늘 실행


def test_skip_weekend_and_offwindow():
    assert mb.should_run_now(datetime(2026, 7, 4, 8, 3), None) is False   # 토요일
    assert mb.should_run_now(datetime(2026, 7, 2, 9, 30), None) is False  # 창밖(09:30)
    assert mb.should_run_now(datetime(2026, 7, 2, 7, 59), None) is False  # 창 직전
