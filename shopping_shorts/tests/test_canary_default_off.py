"""관리자 카나리 기본값 = 꺼짐. 고객 경로에서 제목형 스파인·보조제목 한도가 종전 그대로인지(2026-09-18)."""
from shopping_shorts import bank_assemble, canary, headcopy_gen


def test_default_off_leaves_title_style_untouched():
    canary.set_active(False)
    st = {"beat_roles": ["title", "story"], "beat_descs": {"title": "궁금증"}, "templates": {}}
    assert bank_assemble.with_spoken_hook(st) is st
    assert headcopy_gen._support_max() == headcopy_gen._LEGACY_SUBLINE_LEN == 32


def test_on_switches_contract():
    canary.set_active(True)
    try:
        st = {"beat_roles": ["title", "story"], "beat_descs": {}, "templates": {}}
        assert bank_assemble.with_spoken_hook(st)["beat_roles"] == ["title", "subline", "hook", "story"]
        assert headcopy_gen._support_max() == 22
    finally:
        canary.set_active(False)


class _Req:
    def __init__(self, cookies): self.cookies = cookies


def test_activate_requires_admin_and_cookie():
    calls = []
    def is_admin():
        calls.append(1); return True
    assert canary.activate_from_request(_Req({}), is_admin) is False and not calls   # 쿠키 없으면 DB 판정도 안 부른다
    assert canary.activate_from_request(_Req({"ss_canary": "1"}), lambda: False) is False
    assert canary.activate_from_request(_Req({"ss_canary": "1"}), is_admin) is True
    assert canary.on() is True
    canary.activate_from_request(_Req({}), is_admin)
    assert canary.on() is False
