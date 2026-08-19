"""등록만 되고 안 쓰이는 키로 **과금을 면제하면 안 된다** (2026-08-17 실사고).

라이브에서 이런 상태였다:
  대본(OP_SCRIPT)·영상제작(OP_MIX)은 SVC_GEMINI 기준으로 면제하는데,
  제미나이 키는 실제 호출에 안 쓰인다(key_vault 경유, 호출부 ~80곳).
  → 고객이 제미나이 키만 등록하면 **회사 키로 돌면서 포인트는 0원**.

그래서 keyroute.WIRED(=진짜 쓰이는 서비스)를 한 곳에 두고 should_charge가 그걸 본다.
배선이 끝나 WIRED에 넣는 순간 이 예외는 저절로 사라진다 — 그때 이 테스트도 같이 바뀐다.
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


def test_only_actually_wired_services_are_listed():
    """★이 목록을 늘리기 전에 호출부에 cid가 진짜 닿는지 확인해라.
    앞서가면 '안 쓰이는 키로 과금 면제' 구멍이 그대로 다시 열린다."""
    assert set(keyroute.WIRED) == {keyroute.SVC_VMAKE, keyroute.SVC_SERPAPI}


@pytest.mark.parametrize("svc", [keyroute.SVC_GEMINI, keyroute.SVC_ELEVENLABS,
                                 keyroute.SVC_YOUTUBE])
def test_unwired_key_does_not_buy_free_usage(store, svc):
    """키를 등록해도 과금은 그대로 — 실제로는 회사 키로 돌기 때문이다."""
    store.add_customer_key(7, svc, "mine-1")
    assert keyroute.should_charge(store, 7, svc) is True


@pytest.mark.parametrize("svc", [keyroute.SVC_VMAKE, keyroute.SVC_SERPAPI])
def test_wired_key_is_free(store, svc):
    assert keyroute.should_charge(store, 7, svc) is True      # 등록 전
    store.add_customer_key(7, svc, "mine-1")
    assert keyroute.should_charge(store, 7, svc) is False     # 등록 후


def test_admin_session_is_told_the_truth():
    """cid 0은 keyroute가 등록 키를 조회조차 안 한다(keys_for의 `if cid:`).
    그런데 화면은 저장·목록이 되니 '등록됨'을 띄웠다 = 거짓말.
    서버가 personal 플래그로 사실을 알려주고, 화면은 그걸 보고 등록칸을 감춘다."""
    from pathlib import Path
    from shopping_shorts import app as appmod
    src = Path(appmod.__file__).read_text(encoding="utf-8")
    assert '"personal": bool(cid)' in src, "GET /api/settings/keys가 personal을 안 준다"
    assert '"wired": list(keyroute.WIRED)' in src, "화면이 배선 여부를 알 수 없다"

    html = (Path(appmod.__file__).parent / "static" / "settings.html").read_text(encoding="utf-8")
    assert "KEYS_ENABLED && PERSONAL" in html, "관리자 세션에도 등록칸을 준다"
    assert "adminNotice" in html, "관리자 세션 안내가 없다"
    assert "WIRED.indexOf(s.id) < 0" in html, "미배선 서비스에 준비중 표시가 없다"
