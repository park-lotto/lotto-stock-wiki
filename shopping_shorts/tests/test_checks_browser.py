import os
import pytest
from shopping_shorts.checks import allow_mutations


def test_allow_list_has_no_external_send():
    allow_mutations.assert_safe()          # 예외 없어야 함
    assert allow_mutations.is_allowed("POST", "/api/login")
    assert allow_mutations.is_allowed("POST", "/api/produce/works")
    assert not allow_mutations.is_allowed("POST", "/api/buffer/schedule")
    assert not allow_mutations.is_allowed("DELETE", "/api/seeds")
    assert allow_mutations.is_allowed("GET", "/api/anything")


def test_assert_safe_rejects_external_pattern(monkeypatch):
    monkeypatch.setattr(allow_mutations, "ALLOW", allow_mutations.ALLOW + (r"^/api/buffer/schedule$",))
    with pytest.raises(RuntimeError):
        allow_mutations.assert_safe()


@pytest.mark.skipif(not os.environ.get("CHECKS_BASE_URL"), reason="미리보기 서버 필요(CHECKS_BASE_URL)")
def test_login_and_canary_live():
    from shopping_shorts.checks import browser
    s = browser.open_session(os.environ["CHECKS_BASE_URL"], os.environ["DASH_USER"], os.environ["DASH_PASS"])
    try:
        assert browser.login(s) == 0
        assert browser.timer_probe(s.page) >= 25
        assert browser.canary(s.page).verdict == "green"   # 카나리는 '빨강을 냈다'가 초록
    finally:
        browser.close_session(s)
