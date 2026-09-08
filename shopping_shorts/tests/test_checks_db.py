import sqlite3
from shopping_shorts.checks import db
from shopping_shorts.checks.verdict import Result, Sample, RED, GREEN


def test_start_run_and_add_result_roundtrip(tmp_path):
    conn = db.open_db(tmp_path / "checks.db")
    run_id = db.start_run(conn, "shopping-shorts", "health", "abc1234")
    db.add_result(conn, run_id, Result(layer="L1", name="버튼", verdict=RED,
                                       reason="pageerror", signature="button#x", page="/produce"))
    rows = db.latest_results(conn, run_id)
    assert rows[0]["signature"] == "button#x" and rows[0]["verdict"] == RED
    db.finish_run(conn, run_id, RED)
    got = conn.execute("SELECT verdict FROM check_runs WHERE run_id=?", (run_id,)).fetchone()[0]
    assert got == RED


def test_previous_verdict_looks_at_earlier_run_only(tmp_path):
    conn = db.open_db(tmp_path / "checks.db")
    r1 = db.start_run(conn, "shopping-shorts", "health", "a")
    db.add_result(conn, r1, Result("L1", "x", GREEN, signature="sig"))
    r2 = db.start_run(conn, "shopping-shorts", "health", "b")
    db.add_result(conn, r2, Result("L1", "x", RED, signature="sig"))
    assert db.previous_verdict(conn, "sig", before_run_id=r2) == GREEN
    assert db.previous_verdict(conn, "sig", before_run_id=r1) is None


def test_sample_and_last_ts(tmp_path):
    conn = db.open_db(tmp_path / "checks.db")
    assert db.last_sample_ts(conn, "h_x") is None
    db.add_sample(conn, Sample(item="h_x", name="엑스", value=3.0, ok=True), ts="2026-09-07T00:00:00")
    assert db.last_sample_ts(conn, "h_x") == "2026-09-07T00:00:00"
