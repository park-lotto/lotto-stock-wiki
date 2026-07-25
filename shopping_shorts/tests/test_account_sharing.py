# 돌려쓰기 소프트감지(2026-07-22): 계정별 접속 IP·기기 기록 + 요약
from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_record_access_dedups_same_combo(tmp_path):
    s = _store(tmp_path)
    cid = s.create_customer("u", "pw12")
    for _ in range(3):                                   # 같은 IP·기기·날짜 재접속
        s.record_access(cid, "1.1.1.1", "Chrome/UA", "2026-07-22")
    summ = s.access_summary(cid, "2026-07-01")
    assert summ == {"ips": 1, "devices": 1}              # 하루 1행으로 dedup


def test_distinct_ips_and_devices_counted(tmp_path):
    s = _store(tmp_path)
    cid = s.create_customer("u", "pw12")
    s.record_access(cid, "1.1.1.1", "Chrome", "2026-07-22")
    s.record_access(cid, "2.2.2.2", "Chrome", "2026-07-22")   # 다른 IP
    s.record_access(cid, "1.1.1.1", "Safari", "2026-07-22")   # 다른 기기
    summ = s.access_summary(cid, "2026-07-01")
    assert summ["ips"] == 2
    assert summ["devices"] == 2


def test_summary_respects_since_day(tmp_path):
    s = _store(tmp_path)
    cid = s.create_customer("u", "pw12")
    s.record_access(cid, "9.9.9.9", "Old", "2026-07-01")      # 창 밖
    s.record_access(cid, "1.1.1.1", "New", "2026-07-20")      # 창 안
    summ = s.access_summary(cid, "2026-07-15")
    assert summ["ips"] == 1                                   # 오래된 접속은 제외


def test_access_isolated_per_customer(tmp_path):
    s = _store(tmp_path)
    a = s.create_customer("a", "pw12")
    b = s.create_customer("b", "pw12")
    s.record_access(a, "1.1.1.1", "Chrome", "2026-07-22")
    s.record_access(b, "2.2.2.2", "Chrome", "2026-07-22")
    assert s.access_summary(a, "2026-07-01")["ips"] == 1      # 서로 안 섞임


# ── 배선: 미들웨어가 접속을 기록하고, admin 엔드포인트가 요약을 노출 ──
def _admin_setup(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient  # noqa
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    appmod._ACCESS_SEEN.clear()
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return appmod, s


def _cookie(appmod, cid):
    from datetime import datetime, timezone
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


def test_middleware_records_authenticated_access(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    appmod, s = _admin_setup(tmp_path, monkeypatch)
    cid = s.create_customer("u", "pw12")                      # 승인+full
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(appmod, cid)})
    c.get("/api/me", headers={"X-Forwarded-For": "5.6.7.8", "User-Agent": "TestUA/1.0"})
    summ = s.access_summary(cid, appmod._today_utc())
    assert summ["ips"] == 1 and summ["devices"] == 1          # 미들웨어가 기록함


def test_boss_access_not_recorded(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    appmod, s = _admin_setup(tmp_path, monkeypatch)
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(appmod, 0)})   # 사장님(0)
    c.get("/api/me", headers={"X-Forwarded-For": "9.9.9.9", "User-Agent": "Boss/1.0"})
    assert s.access_summary(0, appmod._today_utc()) == {"ips": 0, "devices": 0}  # 사장님 제외


def test_admin_customers_exposes_access_7d(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    appmod, s = _admin_setup(tmp_path, monkeypatch)
    s.create_customer("u", "pw12")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(appmod, 0)})
    r = owner.get("/api/admin/customers")
    assert r.status_code == 200
    custs = r.json()["customers"]
    assert custs and all("access_7d" in cu and "ips" in cu["access_7d"] for cu in custs)


# ── 접속중·활동기록(2026-07-22) ──
def test_track_activity_last_seen_and_trail(tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    appmod._LASTSEEN_SEEN.clear(); appmod._ACTIVITY_SEEN.clear()
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u", "pw12")
    appmod._track_activity(cid, "/api/mix/start")
    row = {c["id"]: c for c in s.list_customers()}[cid]
    assert row["last_seen"] is not None                 # last_seen 갱신됨
    act = s.recent_activity(cid)
    assert act and act[0]["action"] == "영상 제작 시작"   # 트레일 기록됨


def test_track_activity_dedups_within_window(tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    appmod._LASTSEEN_SEEN.clear(); appmod._ACTIVITY_SEEN.clear()
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u", "pw12")
    appmod._track_activity(cid, "/api/grab")
    appmod._track_activity(cid, "/api/grab")            # 60s 내 같은 액션 → 1건만
    assert len(s.recent_activity(cid)) == 1


def test_track_activity_ignores_unmapped_and_boss(tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    appmod._LASTSEEN_SEEN.clear(); appmod._ACTIVITY_SEEN.clear()
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u", "pw12")
    appmod._track_activity(cid, "/api/reference/rankings")   # 매핑 안 된 경로 → 로그 안 남김
    assert s.recent_activity(cid) == []
    appmod._track_activity(0, "/api/mix/start")              # 사장님(0)은 기록 안 함
    assert s.recent_activity(0) == []


def test_activity_endpoint_admin_only(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    appmod, s = _admin_setup(tmp_path, monkeypatch)
    cid = s.create_customer("u", "pw12")
    s.record_activity(cid, "영상 렌더", 1784600000)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(appmod, 0)})
    r = owner.get("/api/admin/customer/activity?customer_id=" + str(cid))
    assert r.status_code == 200 and r.json()["activity"][0]["action"] == "영상 렌더"
    # 비관리자는 403
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(appmod, cid)})
    assert other.get("/api/admin/customer/activity?customer_id=" + str(cid)).status_code == 403
