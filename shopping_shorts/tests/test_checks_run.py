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
