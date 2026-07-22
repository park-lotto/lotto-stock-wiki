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


# ── A: 최종 렌더(run_render) 실패 시 체험 1회 환불 (2026-07-22 후속) ──
def test_run_render_failure_refunds_trial(tmp_path, monkeypatch):
    from shopping_shorts import mix_pipeline
    dbp = str(tmp_path / "t.db")
    s = Store(dbp)
    cid = s.create_customer("evt", "pw12", approved=False)   # 체험중
    s.usage_incr(cid, "render", "trial")                     # run_mix_job 성공으로 1회 소진된 상태 재현
    assert s.usage_get(cid, "render", "trial") == 1
    job_id = "jtrial01"
    s.create_mix_job(job_id, ["u"], 30, "free", customer_id=cid, render_charge_day="trial")
    s.update_mix_job(job_id, edit_plan={"beats": [{"beat_idx": 0, "narration": "x"}]})
    def boom(*a, **k):
        raise RuntimeError("render boom")
    monkeypatch.setattr(mix_pipeline, "_synthesize_beats", boom)  # 최종 렌더가 실패하도록
    mix_pipeline.run_render(job_id, dbp, str(tmp_path / "work"))
    assert s.get_mix_job(job_id)["status"] == "failed"
    assert s.usage_get(cid, "render", "trial") == 0          # 환불 → 재도전 가능


def test_run_render_failure_does_not_refund_paid(tmp_path, monkeypatch):
    """유료(render_charge_day=날짜)는 최종렌더 실패에도 미환불 — 기존 동작 유지(체험 한정)."""
    from shopping_shorts import mix_pipeline
    dbp = str(tmp_path / "t.db")
    s = Store(dbp)
    cid = s.create_customer("paid", "pw12")
    day = "2026-07-22"
    s.usage_incr(cid, "render", day)
    job_id = "jpaid01"
    s.create_mix_job(job_id, ["u"], 30, "free", customer_id=cid, render_charge_day=day)
    s.update_mix_job(job_id, edit_plan={"beats": [{"beat_idx": 0, "narration": "x"}]})
    def boom(*a, **k):
        raise RuntimeError("render boom")
    monkeypatch.setattr(mix_pipeline, "_synthesize_beats", boom)
    mix_pipeline.run_render(job_id, dbp, str(tmp_path / "work"))
    assert s.usage_get(cid, "render", day) == 1              # 미환불(유료 불변)


# ── B: pro 하루 렌더 상한 = 10 (돌려쓰기 상한, 2026-07-22) ──
def test_pro_daily_render_limit_is_10(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("pro", "pw12")
    s.set_plan(cid, "pro")
    for i in range(10):
        assert app.check_and_count(cid, "render") is True, f"{i}회차는 통과해야"
    assert app.check_and_count(cid, "render") is False       # 11회차 차단
