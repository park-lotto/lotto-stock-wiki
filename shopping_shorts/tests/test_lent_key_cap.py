"""빌려준 회사 VMake 키 한도(관제 277) — 한도에 닿으면 회원 쪽 그 키만 꺼지고 본인 키로 돌아간다."""
import importlib
import pytest
from shopping_shorts import keyroute, keycrypt
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 테스트 전용 Fernet 키


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    s = Store(str(tmp_path / "t.db"))
    s.add_customer_key(0, "vmake", "회사키")        # 사장님 본인 행 — 꺼지면 안 된다
    s.add_customer_key(412, "vmake", "본인키")
    s.add_customer_key(412, "vmake", "회사키")      # 빌려준 키(최신이라 먼저 쓰인다)
    s.set_setting("lent_cap::" + keycrypt.fingerprint("회사키"), "200")
    return s


def test_lent_key_used_first_until_cap(store):
    assert keyroute.keys_for(store, 412, "vmake")[0][0] == "회사키"
    assert keyroute.lent_key_charge(store, "회사키", 120) == (120, 200)
    assert keyroute.keys_for(store, 412, "vmake")[0][0] == "회사키"
    assert keyroute.lent_key_charge(store, "회사키", 80) == (200, 200)
    # 한도 도달 → 회원 쪽 회사키 꺼짐, 본인 키로 돌아감, 사장님 행은 그대로
    assert keyroute.keys_for(store, 412, "vmake")[0] == ["본인키"]
    assert store.get_customer_keys_plain(0, "vmake") == ["회사키"]
    labels = [r["label"] for r in store.list_customer_keys(412, "vmake")]
    assert "지원 200크레딧 · 남은 0" in labels


def test_unlent_key_not_counted(store):
    assert keyroute.lent_key_charge(store, "본인키", 50) is None
    assert store.get_setting("lent_used::" + keycrypt.fingerprint("본인키")) is None
