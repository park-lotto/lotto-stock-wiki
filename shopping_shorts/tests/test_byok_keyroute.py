"""키 선택 + 과금 판단 — 이 둘이 절대 어긋나면 안 된다."""
import importlib
import pytest
from shopping_shorts import keyroute, keycrypt
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    return Store(str(tmp_path / "t.db"))


def test_user_key_wins(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    store.add_customer_key(7, "vmake", "내키")
    keys, is_user = keyroute.keys_for(store, 7, "vmake")
    assert keys == ["내키"]
    assert is_user is True


def test_no_user_key_uses_owner(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    keys, is_user = keyroute.keys_for(store, 7, "vmake")
    assert keys == ["사장님키"]
    assert is_user is False


def test_never_falls_back(store, monkeypatch):
    """★사장님 지시: 폴백 없음. 사용자 키가 있으면 그것만 쓴다.
    사용자 키가 소진돼도 사장님 키로 넘어가면 안 된다 — 그러면 비용이 샌다."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키1", "사장님키2"])
    store.add_customer_key(7, "gemini", "내키")
    keys, is_user = keyroute.keys_for(store, 7, "gemini")
    assert keys == ["내키"]
    assert "사장님키1" not in keys
    assert "사장님키2" not in keys


def test_string_customer_id(store, monkeypatch):
    """★cid가 문자열 "7"로 오는 경로가 있다(app.py:6813 실사고).
    int와 같게 다뤄야 사용자 키를 못 찾고 사장님 키로 새는 일이 없다."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    store.add_customer_key(7, "vmake", "내키")
    keys, is_user = keyroute.keys_for(store, "7", "vmake")
    assert keys == ["내키"]
    assert is_user is True


def test_users_do_not_share(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    store.add_customer_key(1, "vmake", "A키")
    keys, is_user = keyroute.keys_for(store, 2, "vmake")     # B는 등록 안 함
    assert keys == ["사장님키"]
    assert is_user is False


def test_gemini_returns_all_user_keys(store, monkeypatch):
    """구글은 여러 개 — 하나가 한도에 걸리면 다음으로 넘어가야 하니 전부 준다."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    for k in ("k1", "k2", "k3"):
        store.add_customer_key(7, "gemini", k)
    keys, is_user = keyroute.keys_for(store, 7, "gemini")
    assert keys == ["k1", "k2", "k3"]
    assert is_user is True


def test_empty_when_nobody_has_keys(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: [])
    keys, is_user = keyroute.keys_for(store, 7, "vmake")
    assert keys == []
    assert is_user is False


def test_should_charge_is_inverse_of_user_key(store, monkeypatch):
    """★과금 여부는 키 출처에서만 나온다 — 따로 판단하는 곳을 만들지 마라."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    assert keyroute.should_charge(store, 7, "vmake") is True     # 사장님 키 → 과금
    store.add_customer_key(7, "vmake", "내키")
    assert keyroute.should_charge(store, 7, "vmake") is False    # 내 키 → 무료
