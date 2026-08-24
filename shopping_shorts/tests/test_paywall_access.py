"""유료게이트 Task1 — 접근권한 판정기 + /api/me (2026-07-19)."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _now():
    return int(datetime.now(timezone.utc).timestamp())


def test_access_level_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    cid = s.create_customer("u1", "pw12")
    s.set_plan(cid, "free", full_access_until=0)                      # 체험 만료
    assert appmod.access_level(cid, now=1000) == "ranking_only"
    s.set_plan(cid, "free", full_access_until=_now() + 86400)         # 체험 중
    assert appmod.access_level(cid) == "full"
    s.set_plan(cid, "pro")                                            # 결제
    assert appmod.access_level(cid, now=1000) == "full"
    assert appmod.access_level(0, now=1000) == "full"                 # 사장님
    assert appmod.access_level(99999, now=1000) == "ranking_only"     # 없는 고객


def test_create_customer_starts_trial(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("trial_days", 3)
    cid = s.create_customer("u2", "pw12")
    cust = s.get_customer(cid)
    assert cust["plan"] == "free"
    # 체험 만료가 대략 now+3일 (오차 여유 120초)
    assert abs(cust["full_access_until"] - (_now() + 3 * 86400)) < 120


def test_settings_roundtrip(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("trial_days", 7)
    s.set_setting("trial_days", 10)         # 덮어쓰기
    assert int(s.get_setting("trial_days")) == 10   # 저장타입 무관 int로 비교
    assert s.get_setting("nope", "d") == "d"


def test_grandfather_existing_customers(tmp_path):
    """페이월 이전 DB(full_access_until 컬럼 없음)의 기존 고객은 마이그레이션 시 유예 체험을 받아
    즉시 ranking_only로 강등되지 않는다. cid≠0만."""
    import sqlite3
    db = str(tmp_path / "old.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "username TEXT NOT NULL UNIQUE, password_hash TEXT, salt TEXT, created_at TEXT)")
    con.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO customers(username,password_hash,salt) VALUES('old','h','s')")
    con.commit(); con.close()
    s = Store(db)                       # __init__ 마이그레이션 → full_access_until 추가 + 유예
    cust = s.get_customer(1)
    assert cust["plan"] == "free"
    assert cust["full_access_until"] > _now()      # 유예 체험 부여됨(미래 시각)


def test_api_me_auth_off_is_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", False)   # 미들웨어가 cid=0 세팅
    Store(str(tmp_path / "t.db")).ensure_paywall_schema()
    c = TestClient(appmod.app)
    d = c.get("/api/me").json()
    assert d["customer_id"] == 0 and d["level"] == "full" and d["plan"] == "pro"
    assert d["days_left"] is None
    # ★관리자(cid 0)는 하루 한도가 없다 → None(무제한).
    #   2026-08-23까지는 여기가 무료 등급 값(5/2)이었다 — /api/me가 한도를 두 벌 실었고
    #   화면이 하드코딩 쪽을 읽어 "Pro인데 영상 제작 2회"가 떴다. 두 필드를 합치면서
    #   이 계약도 사실에 맞췄다. usage_limits와 limits는 언제나 같은 값이어야 한다.
    assert d["limits"]["lens"] is None and d["limits"]["render"] is None
    assert d["limits"] == d["usage_limits"]


def test_access_level_pending(tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    from shopping_shorts.store import Store
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("pend", "pw12", approved=False)
    with s._conn() as conn:                      # 체험창 만료 강제 → 진짜 pending 상태로 검증
        conn.execute("UPDATE customers SET trial_ends_at=NULL WHERE id=?", (cid,))
    assert appmod.access_level(cid) == "pending"
    # 승인된 계정은 pending 아님
    cid2 = s.create_customer("ok", "pw12")
    assert appmod.access_level(cid2) == "full"
    # 사장님은 DB와 무관하게 full
    assert appmod.access_level(0) == "full"
