import sqlite3
from shopping_shorts.store import Store


def test_prev_comments_empty(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.prev_comments("abc") is None  # 이력 없으면 None

def test_save_and_prev(tmp_path):
    s = Store(tmp_path / "t.db")
    # 1차 수집
    s.save_run("2026-07-08", [
        {"shortcode": "abc", "username": "u1", "comments": 600, "delta": 0},
    ])
    # 다음 수집 시 직전값 조회
    assert s.prev_comments("abc") == 600
    # 2차 수집
    s.save_run("2026-07-09", [
        {"shortcode": "abc", "username": "u1", "comments": 1400, "delta": 800},
    ])
    assert s.prev_comments("abc") == 1400  # 가장 최근값

def test_prev_deltas_for_acceleration(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_run("2026-07-08", [{"shortcode": "x", "username": "u", "comments": 200, "delta": 200}])
    s.save_run("2026-07-09", [{"shortcode": "x", "username": "u", "comments": 500, "delta": 300}])
    assert s.prev_delta("x") == 300  # 직전 Δ (가속 계산용)
