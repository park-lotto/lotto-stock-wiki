import os
import time
from types import SimpleNamespace

import pytest

from shopping_shorts.checks import db, run_checks
from shopping_shorts.checks.verdict import Result, RED, GREEN, GRAY


def test_alert_only_on_two_consecutive_reds_or_any_gray(tmp_path):
    conn = db.open_db(tmp_path / "c.db")
    sent = []
    r1 = db.start_run(conn, "s", "deploy", "a")
    db.add_result(conn, r1, Result("L1", "x", RED, signature="sig"))
    run_checks.alert_if_needed(conn, r1, [Result("L1", "x", RED, signature="sig")], send=lambda **kw: sent.append(kw))
    assert sent == []                                   # 첫 빨강은 조용
    r2 = db.start_run(conn, "s", "deploy", "b")
    db.add_result(conn, r2, Result("L1", "x", RED, signature="sig"))
    run_checks.alert_if_needed(conn, r2, [Result("L1", "x", RED, signature="sig")], send=lambda **kw: sent.append(kw))
    assert len(sent) == 1 and "x" in sent[0]["title"]
    r3 = db.start_run(conn, "s", "deploy", "c")
    run_checks.alert_if_needed(conn, r3, [Result("L0", "기동", GRAY, signature="L0:boot")], send=lambda **kw: sent.append(kw))
    assert len(sent) == 2 and "판정 불가" in sent[1]["title"]


def test_needs_ui_run_when_sha_changed(tmp_path):
    conn = db.open_db(tmp_path / "c.db")
    assert run_checks.needs_ui_run(conn, "abc") is True
    rid = db.start_run(conn, "s", "deploy", "abc"); db.finish_run(conn, rid, GREEN)
    assert run_checks.needs_ui_run(conn, "abc") is False
    assert run_checks.needs_ui_run(conn, "def") is True


def test_run_with_timeout_returns_within_budget_for_slow_fn():
    """timeout_s를 실제로 강제하는지: 3초 걸리는 가짜 함수를 0.3초 예산으로 돌리면
    0.3초 근방에서 TimeoutError로 돌아와야 한다(3초를 다 기다리면 안 된다)."""
    def _slow():
        time.sleep(3)
        return "done"

    t0 = time.time()
    with pytest.raises(TimeoutError):
        run_checks._run_with_timeout(_slow, 0.3)
    elapsed = time.time() - t0
    assert elapsed < 2.5, f"타임아웃이 실제로 발동하지 않음(경과 {elapsed:.2f}s)"


def test_run_with_timeout_returns_value_for_fast_fn():
    assert run_checks._run_with_timeout(lambda: 42, 5) == 42


def test_run_flow_with_budget_marks_gray_on_timeout():
    """가짜 flow 모듈(느림)을 run_flow_with_budget에 태우면 GRAY로 끝나야 한다."""
    def _slow_run(session):
        time.sleep(3)
        return [Result("L2", "가짜 느린 흐름", GREEN, signature="L2:fake_slow")]

    fake_module = SimpleNamespace(
        __name__="shopping_shorts.checks.flows.flow_fake_slow",
        META={"name": "가짜 느린 흐름", "needs_worker": False, "timeout_s": 0.3},
        run=_slow_run,
    )
    results = run_checks.run_flow_with_budget(session=None, module=fake_module)
    assert len(results) == 1
    assert results[0].verdict == GRAY
    assert "시간초과" in results[0].reason


@pytest.mark.skipif(not os.environ.get("CHECKS_BASE_URL"), reason="실서버/브라우저 필요")
def test_run_ui_smoke():
    pass


def test_no_preview_flag_leaves_preview_untouched(tmp_path, monkeypatch):
    """--no-preview는 "이미 떠 있는 걸 그대로 쓴다"는 뜻이어야 한다(2026-09-07 서버 실측 발견:
    예전엔 s.restart_web에 무조건 restart_preview가 심어져 flow_share_link_restart가 그 훅을
    부르는 순간 --no-preview를 줬어도 미리보기가 내려갔다 재기동됐다). preview_start/preview_stop이
    안 불리고, restart_web 훅도 안 심기는지(getattr 폴백으로 회색 처리되게) 확인한다."""
    calls = []
    monkeypatch.setattr(run_checks, "preview_start", lambda sha: calls.append(("start", sha)))
    monkeypatch.setattr(run_checks, "preview_stop", lambda: calls.append(("stop",)))
    monkeypatch.setattr(run_checks, "restart_preview", lambda: calls.append(("restart",)))
    monkeypatch.setattr(run_checks, "live_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(run_checks, "run_ui", lambda conn, run_id, s, quick=False:
                         [Result("L1", "가짜", GREEN, signature="L1:fake")])
    monkeypatch.setattr(run_checks, "run_health", lambda conn, ctx, force=False, run_id=None: [])

    fake_session = SimpleNamespace(context=SimpleNamespace(cookies=lambda: []))
    seen_session = {}

    def _fake_open_session(base_url, user, password):
        return fake_session

    def _fake_login(s):
        seen_session["restart_web_set"] = hasattr(s, "restart_web")
        return 0

    import shopping_shorts.checks.browser as browser_mod
    monkeypatch.setattr(browser_mod, "open_session", _fake_open_session)
    monkeypatch.setattr(browser_mod, "login", _fake_login)
    monkeypatch.setattr(browser_mod, "close_session", lambda s: None)
    monkeypatch.setenv("DASH_USER", "u")
    monkeypatch.setenv("DASH_PASS", "p")

    rc = run_checks.main(["--trigger", "daily", "--force", "--no-preview",
                          "--db", str(tmp_path / "c.db"), "--base-url", "http://x"])

    assert rc == 0
    assert ("start", "deadbeef") not in calls
    assert ("stop",) not in calls
    assert ("restart",) not in calls        # --no-preview면 restart_web 훅 자체가 안 불림
    assert seen_session["restart_web_set"] is False   # 훅이 아예 안 심겼다(getattr 폴백으로 회색 처리됨)
