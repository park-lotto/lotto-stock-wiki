"""과금 면제는 **배선을 따라간다** — 안 쓰이는 키로 면제하면 구멍이 된다(2026-08-17 실사고).

옛 사고: 대본·영상제작은 SVC_GEMINI 기준으로 면제하는데 제미나이 키는 실제 호출에
안 쓰여서, 고객이 키만 등록하면 **회사 키로 돌면서 포인트는 0원**이었다.

2026-08-24 정책(사장님): 서비스는 두 갈래다.
  · 개인 전용(vmake·serpapi·elevenlabs) — 회원이 자기 돈으로 결제. 자기 키만 쓴다.
  · 공용 풀(gemini·youtube)   — 회원에게 1개만 받아 **우리 풀에 합류**시키고
                                회원은 풀 전체를 무료로 쓴다(모자란 건 사장님이 채운다).
공용 풀은 회원 키가 회사 풀 안에 들어가 있으므로 "회사 키로만 돌면서 돈은 안 받는"
상태가 아니다 — 의도된 거래다. 단 **합류 배선이 살아 있어야** 성립한다(아래 테스트).
"""
import pytest

from shopping_shorts import keyroute
from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    return Store(str(tmp_path / "t.db"))


def test_wired_is_a_subset_of_registerable_services():
    assert set(keyroute.WIRED) <= set(keyroute.SERVICES)


def test_pooled_is_a_subset_of_wired():
    """공용 풀 서비스는 반드시 WIRED다 — 풀에 넣었으면 무료로 쓰게 해준다는 뜻이므로."""
    assert set(keyroute.POOLED) <= set(keyroute.WIRED)


def test_registered_key_buys_free_usage(store):
    """배선이 끝난 서비스는 키를 등록하면 과금이 면제된다."""
    for svc in keyroute.WIRED:
        store.add_customer_key(7, svc, f"mine-{svc}")
        assert keyroute.should_charge(store, 7, svc) is False, svc


def test_unregistered_customer_is_still_charged(store):
    """키를 안 낸 회원은 그대로 과금 — 면제는 '키를 낸 사람'만."""
    for svc in keyroute.WIRED:
        assert keyroute.should_charge(store, 99, svc) is True, svc


@pytest.mark.parametrize("svc", list(keyroute.POOLED))
def test_pooled_service_hands_back_the_whole_pool(store, monkeypatch, svc):
    """★공용 풀: 회원이 키 1개를 내면 **풀 전체**를 쓴다.

    1개만 받는데 그 1개로만 돌리면 분당·하루 한도에 곧바로 걸려, 부담을 줄이려
    1개만 받은 취지가 뒤집힌다. 그래서 개인 전용과 달리 풀을 통째로 돌려준다."""
    monkeypatch.setattr(keyroute, "_owner_keys",
                        lambda s: ["POOL-1", "POOL-2", "mine-1"])
    store.add_customer_key(7, svc, "mine-1")
    keys, is_user = keyroute.keys_for(store, 7, svc)
    assert is_user is True                      # 면제로 이어진다
    assert "POOL-1" in keys and "POOL-2" in keys


@pytest.mark.parametrize("svc", [s for s in keyroute.WIRED
                                 if s not in keyroute.POOLED])
def test_personal_service_never_mixes_other_keys(store, monkeypatch, svc):
    """★개인 전용은 종전 그대로 — 남의 키·사장님 키를 절대 안 섞는다.
    회원이 자기 돈으로 결제하는 서비스라 남의 키로 돌면 안 된다."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda s: ["OWNER-1"])
    store.add_customer_key(7, svc, "mine-1")
    keys, is_user = keyroute.keys_for(store, 7, svc)
    assert keys == ["mine-1"] and is_user is True


def test_pool_join_wiring_is_alive():
    """★면제의 전제 — 회원 키를 풀에 넣는 함수가 실제로 있어야 한다.

    이게 사라지면 '회사 키로만 돌면서 돈은 안 받는' 08-17 사고가 그대로 재현된다.
    지우려면 keyroute.WIRED에서 POOLED 서비스도 같이 빼라."""
    from shopping_shorts import config
    assert callable(config.refresh_member_gemini_keys)
    assert callable(config.refresh_member_youtube_keys)
