# -*- coding: utf-8 -*-
"""고객 키 켜기/끄기(A) + 포인트 면제(B) — 2026-08-25 사장님 지시.

★왜 필요한가 (실사고, cid 57 comeback2359)
    이 고객이 자막제거 1회에 4배 차감되는 문제가 있어 사장님이 **DB에서 직접**
    service를 'vmake' → 'vmake_paused'로 바꿔 키를 껐다. 그러자:
      - 시스템은 "이 사람은 키가 없다"로 보고 사장님 키로 처리했고(의도대로),
      - **포인트는 계속 깎았다**(의도와 다름) → 6건 성공 후 잔액 부족으로 막힘.
    사장님이 원한 "내 키를 쓰게 해주되 포인트는 안 깎기"라는 상태가 코드에 없었다.

    그래서 둘을 만든다:
      A. 키를 끄고 켜는 정식 스위치 — status='off'. ★조회가 이걸 실제로 봐야 한다
         (지금은 status를 안 봐서, 껐다고 생각해도 그 키가 계속 쓰인다).
      B. 포인트 면제 — 사장님 키로 돌면서 과금만 면제. A와 짝이 되어야 의도가 성립한다.
"""
import pytest
from cryptography.fernet import Fernet

from shopping_shorts import keyroute
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    return Store(str(tmp_path / "t.db"))


class TestKeyToggle:
    """A — 끈 키는 **실제 호출에서 빠져야** 한다."""

    def test_켜진_키는_쓰인다(self, store):
        store.add_customer_key(57, "vmake", "AK123:SK456")
        assert store.get_customer_keys_plain(57, "vmake") == ["AK123:SK456"]

    def test_끈_키는_안_쓰인다(self, store):
        """★이게 핵심이다 — 지금은 status를 안 봐서 꺼도 계속 쓰였다."""
        kid = store.add_customer_key(57, "vmake", "AK123:SK456")
        store.set_customer_key_status(kid, "off")
        assert store.get_customer_keys_plain(57, "vmake") == []

    def test_다시_켜면_돌아온다(self, store):
        kid = store.add_customer_key(57, "vmake", "AK123:SK456")
        store.set_customer_key_status(kid, "off")
        store.set_customer_key_status(kid, "ok")
        assert store.get_customer_keys_plain(57, "vmake") == ["AK123:SK456"]

    def test_끄면_사장님_키로_넘어간다(self, store, monkeypatch):
        """키를 끄면 keys_for가 사장님 키를 준다 — 작업 자체는 계속 된다."""
        kid = store.add_customer_key(57, "vmake", "AK123:SK456")
        store.set_customer_key_status(kid, "off")
        monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["OWNER_KEY"])
        keys, is_user = keyroute.keys_for(store, 57, keyroute.SVC_VMAKE)
        assert keys == ["OWNER_KEY"] and is_user is False


class TestPointExempt:
    """B — 사장님 키를 쓰면서도 포인트는 안 깎는 상태."""

    def test_기본은_면제가_아니다(self, store):
        assert store.is_point_exempt(57, "vmake") is False

    def test_면제를_켜면_과금하지_않는다(self, store, monkeypatch):
        """키가 없어(=사장님 키로 돌아) 원래는 과금 대상인데, 면제면 안 깎는다."""
        monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["OWNER_KEY"])
        assert keyroute.should_charge(store, 57, keyroute.SVC_VMAKE) is True
        store.set_point_exempt(57, "vmake", True)
        assert keyroute.should_charge(store, 57, keyroute.SVC_VMAKE) is False

    def test_면제는_고객마다_따로다(self, store):
        store.set_point_exempt(57, "vmake", True)
        assert store.is_point_exempt(57, "vmake") is True
        assert store.is_point_exempt(58, "vmake") is False

    def test_서비스마다_따로다(self, store):
        """vmake만 면제했는데 elevenlabs까지 공짜가 되면 안 된다."""
        store.set_point_exempt(57, "vmake", True)
        assert store.is_point_exempt(57, "elevenlabs") is False

    def test_해제하면_다시_과금한다(self, store, monkeypatch):
        monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["OWNER_KEY"])
        store.set_point_exempt(57, "vmake", True)
        store.set_point_exempt(57, "vmake", False)
        assert keyroute.should_charge(store, 57, keyroute.SVC_VMAKE) is True

    def test_사장님_본인_면제는_과금부가_담당한다(self, store):
        """cid 0(사장님)은 종전부터 과금 대상이 아니다 — 단 그 판정은 should_charge가
        아니라 **과금하는 쪽**(_charge_clean)에 있다. 여기 있다고 착각하고 옮기면
        같은 판단이 두 곳으로 흩어진다(0순위-B)."""
        from shopping_shorts.mix_pipeline import _charge_clean
        assert _charge_clean(store, 0, 3) == 0


class TestTogetherIsTheIntent:
    """A+B를 함께 걸어야 사장님이 원한 상태가 된다 — 이 조합이 이번 사고의 처방이다."""

    def test_키를_끄고_면제하면_사장님키로_공짜로_돈다(self, store, monkeypatch):
        monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["OWNER_KEY"])
        kid = store.add_customer_key(57, "vmake", "AK123:SK456")
        store.set_customer_key_status(kid, "off")     # A: 내 키 잠시 끄기
        store.set_point_exempt(57, "vmake", True)     # B: 그동안 포인트도 안 깎기

        keys, is_user = keyroute.keys_for(store, 57, keyroute.SVC_VMAKE)
        assert keys == ["OWNER_KEY"], "사장님 키로 돌아야 한다"
        assert is_user is False
        assert keyroute.should_charge(store, 57, keyroute.SVC_VMAKE) is False, "포인트가 깎이면 안 된다"
