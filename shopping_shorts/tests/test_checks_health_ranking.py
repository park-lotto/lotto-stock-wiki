import json
import sqlite3
import types
from datetime import datetime, timedelta, timezone
from shopping_shorts.checks import discover, db, run_checks
from shopping_shorts.checks.health import h_ranking_fresh
from shopping_shorts.checks.verdict import GRAY, RED, Sample


def _live(tmp_path, collected_at):
    p = tmp_path / "reference.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE last_run(id INTEGER PRIMARY KEY, items_json TEXT, collected_at TEXT)")
    c.execute("INSERT INTO settings VALUES(?,?)", ("last_run::youtube",
              json.dumps({"items": [{"a": 1}], "collected_at": collected_at})))
    c.execute("INSERT INTO last_run VALUES(1, ?, ?)", (json.dumps([{"a": 1}]), collected_at))
    c.commit()
    return p


def test_fresh_within_26h_is_ok(tmp_path):
    now = datetime.now(timezone.utc)
    p = _live(tmp_path, (now - timedelta(hours=2)).isoformat())
    out = h_ranking_fresh.measure({"live_db": p, "base_url": None, "now": now})
    by = {s.item: s for s in out}
    assert by["h_ranking_fresh::youtube"].ok is True
    assert by["h_ranking_fresh::instagram"].ok is True


def test_stale_over_26h_is_red_and_missing_platform_is_red(tmp_path):
    now = datetime.now(timezone.utc)
    p = _live(tmp_path, (now - timedelta(hours=30)).isoformat())
    by = {s.item: s for s in h_ranking_fresh.measure({"live_db": p, "base_url": None, "now": now})}
    assert by["h_ranking_fresh::youtube"].ok is False
    assert by["h_ranking_fresh::tiktok"].ok is False and "없음" in by["h_ranking_fresh::tiktok"].detail


def test_unreadable_db_is_gray(tmp_path):
    out = h_ranking_fresh.measure({"live_db": tmp_path / "nope.db", "base_url": None,
                                   "now": datetime.now(timezone.utc)})
    assert all(s.ok is None for s in out)


def test_run_checks_records_gray_for_broken_module(tmp_path, monkeypatch):
    """discover()의 LAST_ERRORS를 러너가 GRAY Result로 기록하는지 — discover.py의
    docstring 계약("러너(Task 4)는 discover() 호출 뒤 LAST_ERRORS를 읽어 GRAY 결과로
    기록해야 한다")을 검증한다. 정상 항목은 그대로 기록되고, 깨진 모듈은 checks.db에
    GRAY Result가 남아야 한다."""
    import types

    good_calls = []

    def good_measure(ctx):
        good_calls.append(ctx)
        return []

    good_mod = types.SimpleNamespace(
        __name__="shopping_shorts.checks.health.h_good_dummy",
        META={"name": "정상 더미", "every": "1h"},
        measure=good_measure,
    )

    def fake_discover(kind):
        discover.LAST_ERRORS.clear()
        discover.LAST_ERRORS.append(
            ("shopping_shorts.checks.health.h_broken_dummy", "ValueError('일부러 깨진 모듈')")
        )
        return [good_mod]

    monkeypatch.setattr(run_checks.discover, "discover", fake_discover)

    conn = db.open_db(tmp_path / "checks.db")
    run_id = db.start_run(conn, run_checks.SERVICE, "health", "deadbeef")
    ctx = {"live_db": tmp_path / "nope.db", "base_url": None, "now": datetime.now(timezone.utc)}
    run_checks.run_health(conn, ctx, run_id=run_id, force=True)

    rows = db.latest_results(conn, run_id)
    assert len(good_calls) == 1, "정상 항목은 그대로 measure가 호출돼야 한다"
    gray_rows = [r for r in rows if r["verdict"] == GRAY]
    assert len(gray_rows) == 1
    assert "h_broken_dummy" in gray_rows[0]["signature"]
    assert "ValueError" in gray_rows[0]["reason"]


def _clean_discover(mods):
    """LAST_ERRORS는 discover() 호출마다 비워지는 모듈 전역이라(discover.py 계약),
    이전 테스트가 남긴 값이 새 monkeypatch 람다에는 안 지워진 채 새 실행에 섞여든다.
    실제 discover()처럼 매 호출 시작에 비워준다."""
    def fake(kind):
        discover.LAST_ERRORS.clear()
        return mods
    return fake


def _fake_module(name, every, ok_values):
    """measure가 호출될 때마다 ok_values의 값들로 Sample을 만들어 item='<name>::x'로 낸다."""
    calls = []

    def measure(ctx):
        calls.append(ctx)
        return [Sample(f"{name}::x", name, None, ok, detail=f"ok={ok}") for ok in ok_values]

    mod = types.SimpleNamespace(
        __name__=f"shopping_shorts.checks.health.{name}",
        META={"name": name, "every": every},
        measure=measure,
    )
    return mod, calls


def test_overall_verdict_is_red_when_a_sample_is_red(tmp_path, monkeypatch):
    """리뷰 1번 — check_runs.verdict는 health_samples를 반드시 봐야 한다.
    랭킹이 전부 RED인데 discover import 에러가 없으면(=check_results 0건),
    이전 코드는 'green'을 찍었다. summarize()로 샘플까지 합쳐야 red가 나온다."""
    mod, _ = _fake_module("h_all_red_dummy", "1h", [False, False])
    monkeypatch.setattr(run_checks.discover, "discover", _clean_discover([mod]))

    db_path = tmp_path / "checks.db"
    argv = ["--trigger", "health", "--force", "--db", str(db_path)]
    rc = run_checks.main(argv)
    assert rc == 0

    conn = db.open_db(db_path)
    row = conn.execute("SELECT verdict, finished FROM check_runs ORDER BY run_id DESC LIMIT 1").fetchone()
    assert row["verdict"] == RED, f"실제 기록된 verdict: {row['verdict']!r} (green이면 거짓 초록 회귀)"
    assert row["finished"] is not None
    conn.close()


def test_finish_run_is_guaranteed_even_when_run_health_raises(tmp_path, monkeypatch):
    """리뷰 2번 — run_health 내부에서 못 잡는 예외가 나도 check_runs.finished가
    NULL로 고착되면 안 된다. 예외로 끝난 run의 verdict는 GRAY(판정 불가)여야 한다
    (서비스가 아픈 게 아니라 점검 자체가 실패한 것이므로)."""
    def boom(kind):
        raise RuntimeError("일부러 터뜨림")

    monkeypatch.setattr(run_checks.discover, "discover", boom)

    db_path = tmp_path / "checks.db"
    argv = ["--trigger", "health", "--force", "--db", str(db_path)]
    rc = run_checks.main(argv)
    assert rc == 1

    conn = db.open_db(db_path)
    row = conn.execute("SELECT verdict, finished FROM check_runs ORDER BY run_id DESC LIMIT 1").fetchone()
    assert row["finished"] is not None, "예외로 끝나도 finish_run이 반드시 불려야 한다"
    assert row["verdict"] == GRAY
    conn.close()


def test_is_due_actually_skips_and_reruns_after_period(tmp_path, monkeypatch):
    """리뷰 3번 — Sample.item에 항상 서브키가 붙어 last_sample_ts(정확일치)로는
    모듈의 마지막 실행 시각을 절대 못 찾던 문제. last_sample_ts_prefix로 고친 뒤
    (a) 방금 돈 항목은 다시 안 돌고 (b) 주기가 지난 항목은 다시 도는지 검증한다."""
    mod, calls = _fake_module("h_due_dummy", "1h", [True])
    monkeypatch.setattr(run_checks.discover, "discover", _clean_discover([mod]))

    conn = db.open_db(tmp_path / "checks.db")
    ctx = {"live_db": tmp_path / "nope.db", "base_url": None, "now": datetime.now(timezone.utc)}

    run_checks.run_health(conn, ctx, force=False)
    assert len(calls) == 1, "최초 1회는 last_ts가 없으니 돌아야 한다"

    run_checks.run_health(conn, ctx, force=False)
    assert len(calls) == 1, "1시간이 안 지났으면 다시 돌면 안 된다(주기 무의미화 회귀)"

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    conn.execute("UPDATE health_samples SET ts=? WHERE item=?", (old_ts, "h_due_dummy::x"))
    conn.commit()

    run_checks.run_health(conn, ctx, force=False)
    assert len(calls) == 2, "주기(1h)가 지났으면 다시 돌아야 한다"
