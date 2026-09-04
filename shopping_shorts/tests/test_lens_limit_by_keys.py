# -*- coding: utf-8 -*-
"""렌즈 하루 한도 = 등록한 SerpApi 키 개수만큼 늘린다 (2026-08-26 사장님 지시).

★왜
    SerpApi는 **키당 월 100회 무료**다. 키를 2개 내신 분은 실제로 쓸 수 있는 양이 2배인데,
    한도는 10회로 묶여 있어 낸 만큼 못 썼다(임영미님 cid 201 — 키 2개 등록 후 요청).
    사장님: "api 2개 등록시 20회로 상향하는걸로 모두 그렇게 설정".

★규칙
    한도 = 기본 한도 × max(1, 내가 등록한 SerpApi 키 개수)
      키 0개(운영자 키로 씀) → 기본 그대로. 남의 키를 쓰면서 더 달라고 할 수는 없다.
      키 1개 → 기본 그대로 / 2개 → 2배 / 3개 → 3배.

★렌즈에만 적용한다 — 다른 op(render·script)는 키 개수와 무관하다.
    render는 우리 렌더 서버 부하고, script는 공용 풀(gemini)이라 키를 더 내도
    그 사람 몫이 늘지 않는다. 여기서 같이 곱하면 근거 없는 우대가 된다.
"""
import pytest
from cryptography.fernet import Fernet

import shopping_shorts.app as appmod
from shopping_shorts.store import Store


@pytest.fixture
def s(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    return st


def _free_customer(s, keys=0):
    cid = s.create_customer("u%d" % keys, "pw12")
    s.set_plan(cid, "free", full_access_until=0)
    for i in range(keys):
        s.add_customer_key(cid, "serpapi", "KEY%d" % i)
    return cid


class TestLensLimitScalesWithKeys:
    def test_키_없으면_기본_한도(self, s):
        """운영자 키로 쓰는 분은 종전 그대로 — 남의 키로 더 달라고 할 수 없다."""
        s.set_setting("limit_lens", 2)
        cid = _free_customer(s, keys=0)
        assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is False      # 2회에서 막힌다

    def test_키_1개는_1개분(self, s):
        s.set_setting("limit_lens_per_key", 2)
        cid = _free_customer(s, keys=1)
        assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is False

    def test_키_2개면_두_배(self, s):
        """★이번 지시의 핵심 — 키 2개면 20회(기본 10 기준)."""
        s.set_setting("limit_lens_per_key", 2)
        cid = _free_customer(s, keys=2)
        for i in range(4):                                        # 2 × 2 = 4회
            assert appmod.check_and_count(cid, "lens") is True, f"{i+1}회째가 막혔다"
        assert appmod.check_and_count(cid, "lens") is False

    def test_키_3개면_세_배(self, s):
        s.set_setting("limit_lens_per_key", 2)
        cid = _free_customer(s, keys=3)
        for _ in range(6):
            assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is False

    def test_기본값_20이면_키2개는_40회(self, s):
        """설정을 안 건드린 상태(코드 기본값 20, 2026-09-04)에서 키 2개=40회가 나오는지."""
        cid = _free_customer(s, keys=2)
        for i in range(40):
            assert appmod.check_and_count(cid, "lens") is True, f"{i+1}회째가 막혔다"
        assert appmod.check_and_count(cid, "lens") is False

    def test_pro도_같은_규칙(self, s):
        s.set_setting("limit_lens_per_key", 3)
        cid = s.create_customer("p", "pw12")
        s.set_plan(cid, "pro")
        s.add_customer_key(cid, "serpapi", "K1")
        s.add_customer_key(cid, "serpapi", "K2")
        for _ in range(6):                                        # 3 × 2
            assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is False


class TestOnlyLens:
    """렌즈에만 적용한다 — 다른 op는 키를 더 내도 그 사람 몫이 안 늘어난다."""

    def test_render는_키_개수와_무관(self, s):
        s.set_setting("limit_render", 2)
        cid = _free_customer(s, keys=3)
        assert appmod.check_and_count(cid, "render") is True
        assert appmod.check_and_count(cid, "render") is True
        assert appmod.check_and_count(cid, "render") is False, "render가 키 개수로 늘어났다"

    def test_script도_키_개수와_무관(self, s):
        s.set_setting("limit_script", 2)
        cid = _free_customer(s, keys=3)
        assert appmod.check_and_count(cid, "script") is True
        assert appmod.check_and_count(cid, "script") is True
        assert appmod.check_and_count(cid, "script") is False


class TestOffKeysDoNotCount:
    """★꺼둔 키는 안 센다 — 안 쓰는 키로 한도만 늘리면 실제 호출에서 그냥 실패한다."""

    def test_꺼진_키는_한도에_안_들어간다(self, s):
        s.set_setting("limit_lens_per_key", 2)
        cid = s.create_customer("x", "pw12")
        s.set_plan(cid, "free", full_access_until=0)
        s.add_customer_key(cid, "serpapi", "K1")
        kid2 = s.add_customer_key(cid, "serpapi", "K2")
        s.set_customer_key_status(kid2, "off")                    # 2번째 키를 꺼둔다
        assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is True
        assert appmod.check_and_count(cid, "lens") is False, "꺼둔 키가 한도를 늘렸다"


def test_per_key_default_is_20():
    """2026-09-04 사장님: SerpApi 키를 낸 회원은 키 1개당 하루 20회(종전 10회)."""
    from shopping_shorts.app import _CREDIT_PER_KEY_DEFAULTS
    assert _CREDIT_PER_KEY_DEFAULTS["lens"] == 20
