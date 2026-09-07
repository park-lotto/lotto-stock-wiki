import json
import sqlite3
from datetime import datetime, timedelta, timezone
from shopping_shorts.checks.health import (
    h_collect_zero, h_stuck_jobs, h_dead_key_recall,
    h_thumb_missing, h_api_keys, h_member_keys_worker,
)


def _db(tmp_path):
    p = tmp_path / "reference.db"
    c = sqlite3.connect(p)
    c.executescript("""
    CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE job_queue(id INTEGER PRIMARY KEY, task TEXT, state TEXT, heartbeat_at TEXT, claimed_at TEXT);
    CREATE TABLE mix_jobs(job_id TEXT, status TEXT, preview_status TEXT, clean_status TEXT, fx_status TEXT, updated_at TEXT);
    CREATE TABLE api_events(id INTEGER PRIMARY KEY, ts TEXT, day TEXT, service TEXT, outcome TEXT, key_tail TEXT, customer_id TEXT);
    CREATE TABLE api_heartbeats(proc TEXT, pid INTEGER, ts TEXT, detail TEXT);
    CREATE TABLE last_run(id INTEGER PRIMARY KEY, items_json TEXT, collected_at TEXT);
    """)
    c.commit()
    return p, c


def test_collect_zero_flags_platform_with_items_zero(tmp_path):
    p, c = _db(tmp_path)
    c.execute("INSERT INTO settings VALUES(?,?)", ("last_run::threads",
              json.dumps({"items": [], "collected_at": datetime.now(timezone.utc).isoformat()})))
    c.commit()
    by = {s.item: s for s in h_collect_zero.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})}
    assert by["h_collect_zero::threads"].ok is False and by["h_collect_zero::threads"].value == 0


def test_stuck_running_over_5min_is_red_and_fx_included(tmp_path):
    p, c = _db(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(minutes=9)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO job_queue(task,state,heartbeat_at,claimed_at) VALUES('render','running',?,?)", (old, old))
    c.execute("INSERT INTO mix_jobs VALUES('j1','done',NULL,NULL,'queued',?)",
              ((datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat(),))
    c.commit()
    by = {s.item: s for s in h_stuck_jobs.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})}
    assert by["h_stuck_jobs::worker_silent"].ok is False and by["h_stuck_jobs::worker_silent"].value == 1
    assert by["h_stuck_jobs::fx"].ok is False


def test_dead_key_recalled_after_auth_dead_is_red(tmp_path):
    p, c = _db(tmp_path)
    t0 = datetime.now(timezone.utc)
    c.execute("INSERT INTO api_events(ts,day,service,outcome,key_tail) VALUES(?,?,?,?,?)",
              ((t0 - timedelta(hours=3)).isoformat(), "d", "gemini", "auth_dead", "abc123"))
    c.execute("INSERT INTO api_events(ts,day,service,outcome,key_tail) VALUES(?,?,?,?,?)",
              ((t0 - timedelta(hours=1)).isoformat(), "d", "gemini", "auth_dead", "abc123"))
    c.commit()
    s = h_dead_key_recall.measure({"live_db": p, "base_url": None, "now": t0})[0]
    assert s.ok is False and s.value == 1 and "abc123" in s.detail


def test_member_owned_dead_key_recall_does_not_turn_red(tmp_path):
    """★리뷰 지적 수정 — 회원 개인 키(customer_id 있음)가 반복 auth_dead여도
    운영 사고(빨강)로 켜지면 안 된다(api_health.verdict()와 같은 기준, 2026-09-04 사고 재발 방지)."""
    p, c = _db(tmp_path)
    t0 = datetime.now(timezone.utc)
    for hrs in (3, 1):
        c.execute("INSERT INTO api_events(ts,day,service,outcome,key_tail,customer_id) VALUES(?,?,?,?,?,?)",
                  ((t0 - timedelta(hours=hrs)).isoformat(), "d", "elevenlabs", "auth_dead", "zzz999", "340"))
    c.commit()
    by = {s.item: s for s in h_dead_key_recall.measure({"live_db": p, "base_url": None, "now": t0})}
    # 운영 키 서브키(기본 item)는 이 회원 키 재호출과 무관하게 초록/재호출없음이어야 한다.
    assert by["h_dead_key_recall"].ok is True and by["h_dead_key_recall"].value == 0
    # 회원 키는 참고용 서브키로 기록은 되지만 ok(=빨강 아님)여야 한다.
    assert "h_dead_key_recall::member" in by
    assert by["h_dead_key_recall::member"].ok is True
    assert "zzz999" in by["h_dead_key_recall::member"].detail


def test_thumb_missing_red_when_over_threshold(tmp_path, monkeypatch):
    p, c = _db(tmp_path)
    now = datetime.now(timezone.utc)
    c.execute("INSERT INTO settings VALUES(?,?)", ("last_run::tiktok",
              json.dumps({"items": [{"thumbnail": f"https://x.test/{i}.jpg"} for i in range(10)],
                         "collected_at": now.isoformat()})))
    c.commit()

    class _Resp:
        def __init__(self, code):
            self.status_code = code

    calls = {"n": 0}

    def fake_get(url, timeout=8, cookies=None):
        calls["n"] += 1
        # 절반은 실패(404) — 임계값 10%를 훌쩍 넘긴다.
        return _Resp(404 if calls["n"] % 2 == 0 else 200)

    monkeypatch.setattr(h_thumb_missing.requests, "get", fake_get)
    by = {s.item: s for s in h_thumb_missing.measure({"live_db": p, "base_url": "http://x", "now": now})}
    assert by["h_thumb_missing::tiktok"].ok is False
    assert by["h_thumb_missing::tiktok"].value >= 10.0


def test_thumb_missing_gray_without_base_url(tmp_path):
    p, c = _db(tmp_path)
    out = h_thumb_missing.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})
    assert len(out) == 1 and out[0].ok is None


def test_api_keys_red_when_verdict_danger(monkeypatch):
    def fake_snapshot():
        return {}

    def fake_verdict(snap=None, agg=None):
        return {"level": "danger", "msg": "gemini: 죽은 키 2개", "problems": ["gemini: 죽은 키 2개"], "warns": []}

    def fake_aggregates(hours=24):
        return {}

    monkeypatch.setattr(h_api_keys.api_health, "snapshot", fake_snapshot)
    monkeypatch.setattr(h_api_keys.api_health, "verdict", fake_verdict)
    monkeypatch.setattr(h_api_keys.api_health, "aggregates", fake_aggregates)
    s = h_api_keys.measure({"live_db": None, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is False and "죽은 키" in s.detail


def test_member_keys_worker_red_when_no_heartbeat(tmp_path):
    p, c = _db(tmp_path)
    # 회원 키는 있지만(다른 테이블 성격) 워커 하트비트가 24h 안에 없는 상황.
    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    c.execute("INSERT INTO api_heartbeats VALUES(?,?,?,?)", ("worker", 1, old, "keypool resync"))
    c.commit()
    s = h_member_keys_worker.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is False and s.value == 0
