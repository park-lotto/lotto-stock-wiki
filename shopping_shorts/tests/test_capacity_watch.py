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


# ── 대기 배너 문구 · 지금 줄 서 있는 사람 (2026-08-27) ────────────────────────

def test_verdict_queue_msg_names_the_day_and_now(db):
    """★배너는 7일 최대치인데 "밀렸습니다"라 현재형으로 읽힌다 — 실제로 이틀 전
    최대치를 오늘 사고로 오해했다. 날짜와 지금 값이 문장에 있어야 한다."""
    _put(db, "2026-08-25 01:00", running=2, queued=18, disk_free_gb=200.0)
    _put(db, "2026-08-26 01:00", running=1, queued=0, disk_free_gb=200.0)
    v = cw.verdict(db, cores=8, now_queued=0)
    assert v["level"] == "warn"
    assert "2026-08-25" in v["msg"]          # 언제의 숫자인지
    assert "지금은 대기 없습니다" in v["msg"]   # 지금은 어떤지


def _queue(db, rows):
    """job_queue를 만들어 행을 넣는다(운영 스키마와 같은 컬럼만 쓴다)."""
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE IF EXISTS job_queue")   # 픽스처의 축약본을 운영 스키마로 갈아끼운다
    conn.execute("""CREATE TABLE job_queue(
        id INTEGER PRIMARY KEY, task TEXT, args_json TEXT, state TEXT,
        error TEXT, created_at TEXT, claimed_at TEXT, heartbeat_at TEXT,
        finished_at TEXT, progress TEXT, owner TEXT, prio INTEGER)""")
    conn.executemany(
        "INSERT INTO job_queue(id,task,args_json,state,created_at,claimed_at,prio)"
        " VALUES(?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def _mix(db, rows, customers):
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS mix_jobs(job_id TEXT, customer_id INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS customers("
                 "id INTEGER, username TEXT, name TEXT, email TEXT)")
    conn.executemany("INSERT INTO mix_jobs(job_id,customer_id) VALUES(?,?)", rows)
    conn.executemany("INSERT INTO customers(id,username,name,email) VALUES(?,?,?,?)",
                     customers)
    conn.commit()
    conn.close()


def test_waiting_groups_by_person(db):
    """★"대기 8개"만으론 처방이 안 나온다 — 한 명이 몰아넣었는지 여러 명이
    한 개씩인지에 따라 1인 제한 vs 워커 증설로 갈린다."""
    _queue(db, [
        (1, "mix", '{"job_id": "a"}', "queued", "2026-08-27 00:00:00", None, 0),
        (2, "mix", '{"job_id": "a"}', "queued", "2026-08-27 00:00:00", None, 0),
        (3, "mix", '{"job_id": "b"}', "running", "2026-08-27 00:00:00",
         "2026-08-27 00:01:00", 0),
        (4, "mix", '{"job_id": "c"}', "done", "2026-08-27 00:00:00", None, 0),
    ])
    _mix(db, [("a", 12), ("b", 11), ("c", 12)],
         [(12, "g_1", "박2", None), (11, "g_2", None, "lee@example.com")])

    w = cw.waiting(db)
    assert len(w["rows"]) == 3               # done은 줄이 아니다
    by = {a["customer"]: a for a in w["by_customer"]}
    assert by["박2"]["queued"] == 2 and by["박2"]["running"] == 0
    assert by["lee@example.com"]["running"] == 1   # 이름이 없으면 이메일로
    # 이미 물린 작업은 claimed_at까지가 대기 시간이다(지금까지가 아니라).
    assert by["lee@example.com"]["max_wait_sec"] == 60


def test_waiting_names_the_admin_account(db):
    """cid 0은 customers에 행이 없다 — "(모름)"으로 두면 남의 고객이 밀린 줄 안다."""
    _queue(db, [(1, "mix", '{"job_id": "a"}', "queued",
                 "2026-08-27 00:00:00", None, 0)])
    _mix(db, [("a", 0)], [])
    assert cw.waiting(db)["by_customer"][0]["customer"] == "관리자(사장님)"


def test_waiting_without_job_queue_is_quiet(db):
    """관측이 서비스를 죽이면 안 된다 — 테이블이 없어도 빈 목록으로 답한다."""
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE job_queue")
    conn.commit()
    conn.close()
    assert cw.waiting(db) == {"rows": [], "by_customer": []}


def test_waiting_survives_a_slim_job_queue(db):
    """★컬럼이 몇 개 없는 job_queue에서도 '줄 서 있다'는 사실은 나와야 한다 —
    없는 컬럼 하나 때문에 목록이 통째로 비면 정작 밀렸을 때 못 본다."""
    conn = sqlite3.connect(db)     # 픽스처의 축약본(id, state, owner)을 그대로 쓴다
    conn.execute("INSERT INTO job_queue (state, owner) VALUES ('queued', NULL)")
    conn.execute("INSERT INTO job_queue (state, owner) VALUES ('running', 'w1')")
    conn.commit()
    conn.close()
    w = cw.waiting(db)
    assert len(w["rows"]) == 2
    assert w["by_customer"][0]["queued"] == 1
