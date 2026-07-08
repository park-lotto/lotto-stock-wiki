import json
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

def test_comment_drafts_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.get_drafts("sc1") == []
    s.save_drafts("sc1", ["댓글A", "댓글B", "댓글C"])
    assert s.get_drafts("sc1") == ["댓글A", "댓글B", "댓글C"]
    s.save_drafts("sc1", ["새댓글"])
    assert s.get_drafts("sc1") == ["새댓글"]

def test_drafts_bulk_map(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_drafts("a", ["x"])
    s.save_drafts("b", ["y", "z"])
    m = s.drafts_map(["a", "b", "c"])
    assert m["a"] == ["x"] and m["b"] == ["y", "z"]
    assert m.get("c", []) == []

def test_commented_mark_and_query(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.commented_set() == set()
    s.mark_commented("sc1")
    s.mark_commented("sc1")
    s.mark_commented("sc2")
    assert s.commented_set() == {"sc1", "sc2"}

def test_saved_mark_and_query(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.saved_set() == set()
    s.mark_saved("sc1")
    s.mark_saved("sc1")
    s.mark_saved("sc2")
    assert s.saved_set() == {"sc1", "sc2"}

def test_last_run_empty(tmp_path):
    s = Store(tmp_path / "t.db")
    items, collected_at = s.load_last_run()
    assert items == []
    assert collected_at is None

def test_last_run_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    data = [{"shortcode": "a", "name": "채널", "thumbnail": "t.jpg", "comments": 5}]
    s.save_last_run(data, "2026-07-09T10:00:00")
    items, collected_at = s.load_last_run()
    assert items == data
    assert collected_at == "2026-07-09T10:00:00"

def test_last_run_overwrites(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_last_run([{"shortcode": "a"}], "t1")
    s.save_last_run([{"shortcode": "b"}, {"shortcode": "c"}], "t2")
    items, collected_at = s.load_last_run()
    assert len(items) == 2
    assert collected_at == "t2"
