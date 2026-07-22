import time
from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_unapproved_signup_sets_24h_trial_window(tmp_path):
    s = _store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)
    cust = s.get_customer(cid)
    now = int(time.time())
    # 대기중이지만 체험창은 열렸다: now+24h 근처(오차 5분)
    assert cust["approved_at"] is None
    assert cust["trial_ends_at"] is not None
    assert abs(cust["trial_ends_at"] - (now + 24 * 3600)) < 300


def test_approved_signup_has_no_trial_window(tmp_path):
    s = _store(tmp_path)
    cid = s.create_customer("appr", "pw12")  # 기본 approved=True
    assert s.get_customer(cid)["trial_ends_at"] is None


def test_access_level_full_during_trial_then_pending(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("evt", "pw12", approved=False)
    tea = s.get_customer(cid)["trial_ends_at"]
    # 창 안: full
    assert app.access_level(cid, now=tea - 10) == "full"
    # 창 밖: pending
    assert app.access_level(cid, now=tea + 10) == "pending"


def test_access_level_legacy_pending_customer_stays_pending(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("evt", "pw12", approved=False)
    # trial_ends_at를 NULL로 강제(기존 고객 흉내)
    with s._conn() as c:
        c.execute("UPDATE customers SET trial_ends_at=NULL WHERE id=?", (cid,))
    assert app.access_level(cid, now=int(time.time())) == "pending"


def test_trial_render_capped_at_one(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("evt", "pw12", approved=False)  # 체험중
    assert app._is_trial(cid) is True
    assert app.check_and_count(cid, "render") is True    # 1회차 허용
    assert app.check_and_count(cid, "render") is False   # 2회차 차단
    # 렌즈는 체험 상한 안 걸림(일일 한도만) — 여러 번 True
    assert app.check_and_count(cid, "lens") is True
    assert app.check_and_count(cid, "lens") is True


def test_nontrial_render_uses_daily_limit(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("appr", "pw12")   # 승인+체험중(full, 미이벤트)
    assert app._is_trial(cid) is False
    # 일일 render 기본 상한 2 → 2회 True, 3회째 False
    assert app.check_and_count(cid, "render") is True
    assert app.check_and_count(cid, "render") is True
    assert app.check_and_count(cid, "render") is False


def test_trial_render_refund_restores_one_shot(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    from shopping_shorts import mix_pipeline
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    dbp = str(tmp_path / "t.db")
    s = Store(dbp)
    cid = s.create_customer("evt", "pw12", approved=False)
    # 체험 렌더 1회 소진
    assert app.check_and_count(cid, "render") is True
    assert s.usage_get(cid, "render", "trial") == 1
    # 실패 환불 시뮬: render_charge_day="trial" job의 환불 규칙 적용
    mix_pipeline._refund_render_charge(s, cid, "trial")
    assert s.usage_get(cid, "render", "trial") == 0        # 재도전 가능
    # 이제 다시 1회 허용
    assert app.check_and_count(cid, "render") is True


def test_list_customers_exposes_trial_ends_at(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("evt", "pw12", approved=False)   # 이벤트 체험
    rows = {c["id"]: c for c in s.list_customers()}
    assert "trial_ends_at" in rows[cid]
    assert rows[cid]["trial_ends_at"] is not None            # 미승인 체험자는 창 열림
