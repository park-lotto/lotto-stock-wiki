"""관측판 — 판정이 실제로 위험을 잡아내는지 고정한다(2026-08-22).

관측판의 값어치는 표가 아니라 **판정 한 줄**에 있다. 판정이 틀리면
"괜찮다"를 보고 안심하다가 오픈 날 서버가 죽는다. 그래서 여기를 테스트한다.
"""
import sqlite3

import pytest

from shopping_shorts import capacity_watch as cw


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "t.db"
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE job_queue (id INTEGER PRIMARY KEY, state TEXT, owner TEXT)")
    cw.ensure_schema(conn)
    conn.commit()
    conn.close()
    return p


def _put(db, at, **kw):
    row = {"at": at, "running": 0, "queued": 0, "workers": 0, "load1": 0.1,
           "cores": 4, "disk_used_gb": 70.0, "disk_free_gb": 230.0,
           "net_tx_gb": 0.0, "net_rx_gb": 0.0}
    row.update(kw)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO capacity_samples (at,running,queued,workers,load1,cores,"
        "disk_used_gb,disk_free_gb,net_tx_gb,net_rx_gb) VALUES "
        "(:at,:running,:queued,:workers,:load1,:cores,:disk_used_gb,:disk_free_gb,"
        ":net_tx_gb,:net_rx_gb)", row)
    conn.commit()
    conn.close()


def test_sample_records_a_row_and_returns_it(db):
    """표본 한 줄이 실제로 쌓이고, 그 내용을 그대로 돌려준다."""
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO job_queue (state, owner) VALUES ('running','w1')")
    conn.execute("INSERT INTO job_queue (state, owner) VALUES ('running','w2')")
    conn.execute("INSERT INTO job_queue (state, owner) VALUES ('queued', NULL)")
    conn.commit()
    conn.close()

    d = cw.sample(db)
    assert d["running"] == 2 and d["queued"] == 1
    assert d["workers"] == 2          # 서로 다른 owner 2명이 물고 있었다
    assert d["disk_free_gb"] > 0 and d["cores"] >= 1

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM capacity_samples").fetchone()[0] == 1
    conn.close()


def test_daily_folds_by_max_not_average(db):
    """하루 요약은 최대치로 접는다 — 평균은 위험한 순간을 숨긴다."""
    _put(db, "2026-08-22 01:00", running=1)
    _put(db, "2026-08-22 02:00", running=6)      # 이 순간이 문제다
    _put(db, "2026-08-22 03:00", running=1)
    rows = cw.daily(db, days=3650)
    assert rows and rows[0]["max_running"] == 6


def test_daily_transfer_is_delta_not_cumulative(db):
    """송신은 누적값이라 그대로 쓰면 안 된다 — 그날 늘어난 양으로 본다."""
    _put(db, "2026-08-22 01:00", net_tx_gb=100.0)
    _put(db, "2026-08-22 23:00", net_tx_gb=140.0)
    rows = cw.daily(db, days=3650)
    assert rows[0]["tx_gb"] == 40.0


def test_daily_transfer_survives_a_reboot(db):
    """재부팅으로 카운터가 0으로 돌아가도 없는 숫자를 지어내지 않는다.

    실사고(2026-08-24): 서버 증설로 누적값이 58GB→0.2GB가 됐는데
    (최댓값−최솟값) 방식이라 하루 67GB라는 없는 송신이 표에 찍혔다.
    이 숫자로 요금을 판단하면 그대로 오판이다.
    """
    _put(db, "2026-08-24 01:00", net_tx_gb=50.0)
    _put(db, "2026-08-24 02:00", net_tx_gb=58.0)    # 여기까지 +8
    _put(db, "2026-08-24 03:00", net_tx_gb=0.2)     # ★재부팅 — 카운터가 되감겼다
    _put(db, "2026-08-24 04:00", net_tx_gb=1.2)     # 그 뒤로 +1
    rows = cw.daily(db, days=3650)
    assert rows[0]["tx_gb"] == 9.0, "증가분만 더해야 한다(8 + 1). 되감긴 구간은 0으로."


def test_daily_transfer_counts_each_day_separately(db):
    """날이 바뀌면 그날 증가분만 그날에 잡힌다."""
    _put(db, "2026-08-22 23:00", net_tx_gb=100.0)
    _put(db, "2026-08-23 01:00", net_tx_gb=105.0)
    _put(db, "2026-08-23 23:00", net_tx_gb=112.0)
    rows = {r["date"]: r["tx_gb"] for r in cw.daily(db, days=3650)}
    assert rows["2026-08-23"] == 12.0    # 100→105→112 = 그날 12


def test_verdict_flags_disk_first(db):
    """디스크가 차는 건 서비스가 통째로 죽는 일이라 가장 먼저 알린다."""
    _put(db, "2026-08-22 01:00", disk_free_gb=20.0, running=1)
    v = cw.verdict(db, cores=8)
    assert v["level"] == "danger" and "디스크" in v["msg"]


def test_verdict_flags_core_contention(db):
    """동시 렌더가 코어 수에 닿으면 서로 뺏는 구간 — 실측 9.8배 지연의 근거."""
    _put(db, "2026-08-22 01:00", running=8, disk_free_gb=200.0)
    v = cw.verdict(db, cores=8)
    assert v["level"] == "danger" and "코어" in v["msg"]


def test_verdict_warns_on_queue_backlog(db):
    """줄이 계속 서 있으면 상한이 모자란 것 — 다만 디스크·코어보다는 급하지 않다."""
    _put(db, "2026-08-22 01:00", running=2, queued=5, disk_free_gb=200.0)
    v = cw.verdict(db, cores=8)
    assert v["level"] == "warn" and "대기" in v["msg"]


def test_verdict_ok_when_everything_is_roomy(db):
    _put(db, "2026-08-22 01:00", running=1, queued=0, disk_free_gb=230.0)
    v = cw.verdict(db, cores=8)
    assert v["level"] == "ok"


def test_verdict_without_samples_says_so(db):
    """표본이 없으면 '괜찮다'가 아니라 '아직 모른다'라고 해야 한다."""
    v = cw.verdict(db, cores=8)
    assert v["level"] == "unknown"
