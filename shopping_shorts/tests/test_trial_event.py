import time
from shopping_shorts.store import Store


def _store(tmp_path):
    """무료체험 이벤트 OFF — 가입 직후 바로 대기실.

    ★2026-08-25부터 기본값이 72시간(3일)이라 **명시적으로 0을 넣어야** OFF가 된다.
      예전엔 기본이 0이라 아무것도 안 해도 OFF였다(그래서 이 헬퍼가 빈 Store였다).
    """
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("trial_event_hours", "0")
    return s


def _evt_store(tmp_path):
    """무료체험 이벤트 ON — 가입 후 24h 자동 맛보기(옛 이벤트). 설정으로 켠 상태."""
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("trial_event_hours", "24")
    return s


# ── 기본: 가입 즉시 체험 3일(2026-08-25 정책 변경) ──
def test_default_signup_gets_3day_trial(tmp_path, monkeypatch):
    """★기본 정책 변경(2026-08-25 사장님 "가입되면 체험3일 자동, 확인 누르면 고객관리로").

    예전엔 가입 직후 바로 잠겼고(pending) 사장님이 일일이 체험을 줘야 했다.
    이제 trial_event_hours 기본값이 72시간이라 가입 즉시 3일 체험이 열린다.
    (설정을 0으로 두면 옛 동작으로 돌아간다 — 아래 _store가 그 경우다.)
    """
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))            # 설정을 건드리지 않은 기본 상태
    cid = s.create_customer("evt", "pw12", approved=False)
    cust = s.get_customer(cid)
    now = int(time.time())
    assert cust["approved_at"] is None                        # 아직 대기실 목록에 뜬다
    assert 71 * 3600 <= (cust["trial_ends_at"] - now) <= 72 * 3600   # 3일 창
    assert app.access_level(cid) == "full"                    # 바로 써볼 수 있다
    assert app._is_trial(cid) is True


def test_signup_stays_locked_when_event_off(tmp_path, monkeypatch):
    """설정으로 끄면(0) 옛 동작 그대로 — 가입 직후 잠김."""
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = _store(tmp_path)                                      # trial_event_hours=0
    cid = s.create_customer("evt", "pw12", approved=False)
    assert s.get_customer(cid)["trial_ends_at"] is None
    assert app.access_level(cid) == "pending"
    assert app._is_trial(cid) is False


# ── 이벤트 ON일 때만 자동 맛보기 창 ──
def test_unapproved_signup_sets_24h_trial_window_when_enabled(tmp_path):
    s = _evt_store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)
    cust = s.get_customer(cid)
    now = int(time.time())
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
    s = _evt_store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)
    tea = s.get_customer(cid)["trial_ends_at"]
    assert app.access_level(cid, now=tea - 10) == "full"     # 창 안
    assert app.access_level(cid, now=tea + 10) == "pending"  # 창 밖


def test_access_level_legacy_pending_customer_stays_pending(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = _store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)
    with s._conn() as c:
        c.execute("UPDATE customers SET trial_ends_at=NULL WHERE id=?", (cid,))
    assert app.access_level(cid, now=int(time.time())) == "pending"


def test_trial_render_capped_at_one(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = _evt_store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)  # 체험중(이벤트 ON)
    assert app._is_trial(cid) is True
    assert app.check_and_count(cid, "render") is True    # 1회차 허용
    assert app.check_and_count(cid, "render") is False   # 2회차 차단
    assert app.check_and_count(cid, "lens") is True      # 렌즈는 안 걸림
    assert app.check_and_count(cid, "lens") is True


def test_nontrial_render_uses_daily_limit(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = _store(tmp_path)
    cid = s.create_customer("appr", "pw12")   # 승인+체험중(full, 미이벤트)
    assert app._is_trial(cid) is False
    # ★체험(1회 고정)과 달리 일일 상한을 그대로 쓴다 — 그게 이 테스트의 요지다.
    #   횟수를 하드코딩하면 상한을 조정할 때마다 깨진다(2026-08-17 실제로 2→10에서 깨졌다).
    limit = app._CREDIT_DEFAULTS["render"]
    for _ in range(limit):
        assert app.check_and_count(cid, "render") is True
    assert app.check_and_count(cid, "render") is False


def test_trial_render_refund_restores_one_shot(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    from shopping_shorts import mix_pipeline
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = _evt_store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)
    assert app.check_and_count(cid, "render") is True
    assert s.usage_get(cid, "render", "trial") == 1
    mix_pipeline._refund_render_charge(s, cid, "trial")
    assert s.usage_get(cid, "render", "trial") == 0        # 재도전 가능
    assert app.check_and_count(cid, "render") is True


def test_list_customers_exposes_trial_ends_at(tmp_path):
    s = _evt_store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)   # 이벤트 체험
    rows = {c["id"]: c for c in s.list_customers()}
    assert "trial_ends_at" in rows[cid]
    assert rows[cid]["trial_ends_at"] is not None


# ── A: 최종 렌더(run_render) 실패 시 체험 1회 환불 (2026-07-22 후속) ──
def test_run_render_failure_refunds_trial(tmp_path, monkeypatch):
    from shopping_shorts import mix_pipeline
    dbp = str(tmp_path / "t.db")
    s = _evt_store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)   # 체험중
    s.usage_incr(cid, "render", "trial")                     # run_mix_job 성공으로 1회 소진 재현
    assert s.usage_get(cid, "render", "trial") == 1
    job_id = "jtrial01"
    s.create_mix_job(job_id, ["u"], 30, "free", customer_id=cid, render_charge_day="trial")
    s.update_mix_job(job_id, edit_plan={"beats": [{"beat_idx": 0, "narration": "x"}]})
    def boom(*a, **k):
        raise RuntimeError("render boom")
    monkeypatch.setattr(mix_pipeline, "_synthesize_beats", boom)
    mix_pipeline.run_render(job_id, dbp, str(tmp_path / "work"))
    assert s.get_mix_job(job_id)["status"] == "failed"
    assert s.usage_get(cid, "render", "trial") == 0          # 환불 → 재도전 가능


def test_run_render_failure_does_not_refund_paid(tmp_path, monkeypatch):
    """유료(render_charge_day=날짜)는 최종렌더 실패에도 미환불 — 기존 동작 유지(체험 한정)."""
    from shopping_shorts import mix_pipeline
    dbp = str(tmp_path / "t.db")
    s = _store(tmp_path)
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


# ── A2: 재타이핑(retype_mix_job) 실패 시 체험 1회 환불 (run_render와 대칭) ──
def test_retype_failure_refunds_trial(tmp_path, monkeypatch):
    from shopping_shorts import mix_pipeline
    dbp = str(tmp_path / "t.db")
    s = _evt_store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)   # 체험중
    s.usage_incr(cid, "render", "trial")                     # 1회 소진 재현
    assert s.usage_get(cid, "render", "trial") == 1
    job_id = "jretype01"
    s.create_mix_job(job_id, ["u"], 30, "free", customer_id=cid, render_charge_day="trial")
    s.update_mix_job(job_id, extract={"s1": "원본 대본"})      # retype은 extract 캐시 필요
    def boom(*a, **k):
        raise RuntimeError("retype boom")
    monkeypatch.setattr(mix_pipeline, "_plan_and_tts", boom)
    mix_pipeline.retype_mix_job(job_id, "unknown", dbp, str(tmp_path / "work"))
    assert s.get_mix_job(job_id)["status"] == "failed"
    assert s.usage_get(cid, "render", "trial") == 0          # 환불 → 재도전 가능


def test_retype_failure_does_not_refund_paid(tmp_path, monkeypatch):
    """유료는 재타이핑 실패에도 미환불 — 기존 동작 유지(체험 한정)."""
    from shopping_shorts import mix_pipeline
    dbp = str(tmp_path / "t.db")
    s = _store(tmp_path)
    cid = s.create_customer("paid", "pw12")
    day = "2026-07-22"
    s.usage_incr(cid, "render", day)
    job_id = "jretype02"
    s.create_mix_job(job_id, ["u"], 30, "free", customer_id=cid, render_charge_day=day)
    s.update_mix_job(job_id, extract={"s1": "원본 대본"})
    def boom(*a, **k):
        raise RuntimeError("retype boom")
    monkeypatch.setattr(mix_pipeline, "_plan_and_tts", boom)
    mix_pipeline.retype_mix_job(job_id, "unknown", dbp, str(tmp_path / "work"))
    assert s.usage_get(cid, "render", day) == 1              # 미환불(유료 불변)


# ── B: pro 하루 렌더 상한 = 10 (돌려쓰기 상한, 2026-07-22) ──
def test_pro_daily_render_limit_is_10(tmp_path, monkeypatch):
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = _store(tmp_path)
    cid = s.create_customer("pro", "pw12")
    s.set_plan(cid, "pro")
    for i in range(10):
        assert app.check_and_count(cid, "render") is True, f"{i}회차는 통과해야"
    assert app.check_and_count(cid, "render") is False       # 11회차 차단


# ── '확인함'(ack) — 대기실에서만 내리고 체험은 유지(2026-08-25) ──
def test_ack_keeps_trial_and_removes_from_pending(tmp_path, monkeypatch):
    """★사장님 지시의 핵심: 확인을 눌러도 체험 3일은 그대로 흘러가야 한다.

    access_level은 체험창(trial_ends_at)을 approved_at이 비어 있을 때만 본다.
    ack가 approved_at만 채우고 끝내면 **그 순간 체험이 끊긴다** — 그래서
    남은 시간을 full_access_until로 옮긴다. 이 테스트가 그걸 지킨다.
    """
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("acked", "pw12", approved=False)
    assert app.access_level(cid) == "full"                    # 가입 즉시 체험
    assert any(p["id"] == cid for p in s.pending_customers())  # 대기실에 있다

    assert s.ack_customer(cid) is True
    assert not any(p["id"] == cid for p in s.pending_customers())  # 대기실에서 내려감
    assert app.access_level(cid) == "full"                    # ★체험이 살아 있다
    now = int(time.time())
    assert 71 * 3600 <= (s.get_customer(cid)["full_access_until"] - now) <= 72 * 3600


def test_ack_is_idempotent(tmp_path):
    """두 번 눌러도 기간이 늘거나 줄지 않는다."""
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("twice", "pw12", approved=False)
    assert s.ack_customer(cid) is True
    fau = s.get_customer(cid)["full_access_until"]
    assert s.ack_customer(cid) is False        # 이미 내려간 고객
    assert s.get_customer(cid)["full_access_until"] == fau


def test_ack_expires_after_trial(tmp_path, monkeypatch):
    """3일이 지나면 알아서 잠긴다 — 공짜로 계속 쓰면 안 된다."""
    import sqlite3
    import shopping_shorts.app as app
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("gone", "pw12", approved=False)
    s.ack_customer(cid)
    c = sqlite3.connect(str(tmp_path / "t.db"))
    c.execute("UPDATE customers SET full_access_until=? WHERE id=?",
              (int(time.time()) - 10, cid))
    c.commit()
    assert app.access_level(cid) == "ranking_only"


def test_ack_does_not_touch_already_approved(tmp_path):
    """결제로 승인된 고객을 ack해도 기간이 안 바뀐다(연장·삭감 사고 방지)."""
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("paid", "pw12", approved=False)
    s.approve_customer(cid, 30, 10000, "계좌")
    before = s.get_customer(cid)["full_access_until"]
    assert s.ack_customer(cid) is False
    assert s.get_customer(cid)["full_access_until"] == before
