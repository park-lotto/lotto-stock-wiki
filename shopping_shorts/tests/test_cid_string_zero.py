"""customer_id가 문자열 "0"으로 와도 사장님으로 인식되는지(2026-07-30 실사고).

증상: 영상 3개를 담았는데 대본이 2개만 생겼다.
원인: 예열(prewarm)은 customer_id를 문자열 "0"으로 큐에 넣는데, check_and_count가
`customer_id == 0`으로 등급을 판정해 "0"을 **무료 등급**으로 떨궜다 → limit_script 10건.
하루 10건을 넘는 순간 담긴 영상의 예열이 전부 skipped_limit로 조용히 스킵됐다
(실측: 유튜브 2건은 처리, 인스타·샤오홍슈는 0.03초 만에 done).
"""
from shopping_shorts import app


def test_as_cid_normalizes_string_zero():
    assert app._as_cid("0") == 0
    assert app._as_cid(0) == 0
    assert app._as_cid("12") == 12
    assert app._as_cid(None) is None          # 숫자 아니면 원값 — 비교만 실패하게
    assert app._as_cid("abc") == "abc"


def test_owner_recognized_from_string_cid():
    # 넷 다 같은 계열 버그였다 — 하나만 고치면 다른 데서 또 샌다
    assert app._is_admin("0") is True
    assert app._code_admin("0") is True
    assert app.access_level("0") == "full"
    assert app._is_trial("0") is False


def test_paid_tier_uses_pro_limit_for_string_cid(monkeypatch):
    """문자열 "0"도 pro 상한(200)을 받아야 한다 — 무료(10)로 떨어지면 안 된다."""
    seen = {}

    class _FakeStore:
        def get_customer(self, cid):
            return None
        def get_setting(self, key, dflt=None):
            seen["key"] = key
            return dflt
        def usage_get(self, cid, op, day):
            return 50            # 무료 상한(10) 초과, pro 상한(200) 미만
        def usage_incr(self, cid, op, day):
            seen["incr"] = True

    monkeypatch.setattr(app, "Store", lambda *a, **kw: _FakeStore())
    assert app.check_and_count("0", "script") is True
    assert seen["key"] == "limit_script_pro", "무료 등급으로 판정됐다"
