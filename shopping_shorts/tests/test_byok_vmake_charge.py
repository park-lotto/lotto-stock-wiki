"""자막제거 관문 — **내 키가 없으면 거절**한다(2026-09-01 사장님 확정).

## 이 파일이 바뀐 이유

전에는 "소스 개수만큼 포인트를 깎는다"를 검증했다. 그런데 그 모델 자체가 사고였다 —
키를 안 낸 회원은 **사장님 VMake·일레븐랩스 계정으로 돌면서** 포인트만 깎였고,
회원들은 포인트를 쓰는 줄도 몰랐다(설명받은 적 없음). 포인트가 남은 회원만 조용히
통과해 "어떤 사람은 되고 어떤 사람은 안 되는" 상태가 됐다.
실측(2026-09-01): 최근 30일 제작 46명 중 16명이 음성 키 없이 86건을 만들었다.

사장님 지시: "v메이크랑 tts는 없으면 못하게 막아" / "포인트제도를 다 없애".

## 그래서 무엇을 지키나

숫자(몇 P)가 아니라 **불변식**을 박는다 — 정책 문구를 박으면 정책이 바뀔 때마다
테스트가 거짓말이 된다(이 파일이 실제로 그렇게 됐다).

1. 키가 없으면 **막힌다**(사장님 키가 안 나간다)
2. 키가 있으면 **통과하고 아무것도 안 깎는다**
3. 사장님(cid 0)은 **절대 안 막힌다**
4. 웹 진입과 워커가 **같은 판단**을 본다 — 한쪽만 막으면 큐에 남은 작업이 통과한다
"""
import importlib

import pytest

from shopping_shorts import keycrypt, keyroute, mix_pipeline as mp, points
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("vmake_api_key", "사장님키")     # 사장님 키가 있어도 회원에겐 안 나간다
    return s


# ── ① 키가 없으면 막힌다 ───────────────────────────────────────────────

def test_blocked_without_own_key(store):
    """★핵심. 전엔 여기서 사장님 키로 돌며 포인트만 깎였다."""
    with pytest.raises(mp.NotEnoughPoints) as e:
        mp._charge_clean(store, 5, 3)
    assert "키를 등록해야" in str(e.value)          # 회원이 할 행동이 문구에 있다


def test_points_do_not_unblock(store):
    """★포인트가 아무리 많아도 키가 없으면 못 쓴다 — 포인트로 때우는 길을 막는 것이
    이 변경의 목적이다(그 길이 열려 있어 회원이 키를 등록하지 않았다)."""
    points.add(store, 5, 999999)
    with pytest.raises(mp.NotEnoughPoints):
        mp._charge_clean(store, 5, 3)


# ── ② 키가 있으면 통과, 아무것도 안 깎는다 ─────────────────────────────

def test_own_key_passes_and_costs_nothing(store):
    store.add_customer_key(5, keyroute.SVC_VMAKE, "내키")
    points.add(store, 5, 10000)
    assert mp._charge_clean(store, 5, 3) == 0
    assert points.balance(store, 5) == 10000        # 한 푼도 안 깎인다


def test_zero_sources_is_free_even_without_key(store):
    """청소할 게 없으면 키를 안 봐도 된다 — 아무 호출도 안 나가기 때문이다."""
    assert mp._charge_clean(store, 5, 0) == 0


# ── ③ 사장님은 안 막힌다 ───────────────────────────────────────────────

def test_owner_cid0_never_blocked(store):
    """cid 0 = 사장님. 회사 자산 작업이 여기서 막히면 서비스가 통째로 선다."""
    assert mp._charge_clean(store, 0, 3) == 0


# ── ④ 웹과 워커가 같은 판단을 본다 ─────────────────────────────────────

def test_worker_and_web_share_one_judgement(store):
    """★한쪽만 막으면 큐에 남은 작업이 그대로 통과한다.
    둘 다 keyroute.block_reason을 봐야 하고, 그래서 결과가 늘 같아야 한다."""
    web_blocked = keyroute.block_reason(store, 5, keyroute.SVC_VMAKE) is not None
    try:
        mp._charge_clean(store, 5, 1)
        worker_blocked = False
    except mp.NotEnoughPoints:
        worker_blocked = True
    assert web_blocked == worker_blocked is True

    store.add_customer_key(5, keyroute.SVC_VMAKE, "내키")
    web_blocked2 = keyroute.block_reason(store, 5, keyroute.SVC_VMAKE) is not None
    mp._charge_clean(store, 5, 1)                   # 안 막혀야 한다(예외 없음)
    assert web_blocked2 is False


# ── ⑤ 환불은 유령 지급을 만들지 않는다 ─────────────────────────────────

def test_refund_of_zero_does_nothing(store):
    """★과금이 사라졌으니 환불도 0이어야 한다. 환불 코드를 남겨둔 채 액수만
    잘못 넣으면 **없던 포인트가 생긴다**(2026-08-23 점검에서 실제로 났던 모양)."""
    before = points.balance(store, 5)
    mp._refund_clean(store, 5, 0)
    assert points.balance(store, 5) == before


def test_mix_refund_skipped_without_charge_mark(store):
    """render_charge_day가 없으면 과금 안 한 job이다 — 환불하면 잔액이 부푼다."""
    points.add(store, 7, 1000)
    mp._refund_mix_points(store, 7, None)
    assert points.balance(store, 7) == 1000


def test_mix_refund_skips_owner(store):
    before = points.balance(store, 0)
    mp._refund_mix_points(store, 0, "2026-09-01")
    assert points.balance(store, 0) == before
