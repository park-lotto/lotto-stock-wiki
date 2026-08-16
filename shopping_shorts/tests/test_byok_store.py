"""customer_keys 저장·조회 — 사용자별로 갈리는지, 중복이 막히는지."""
import importlib
import pytest
from shopping_shorts.store import Store
from shopping_shorts import keycrypt

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    return Store(str(tmp_path / "t.db"))


def test_add_and_list(store):
    store.add_customer_key(1, "vmake", "appkey:secret")
    rows = store.list_customer_keys(1, "vmake")
    assert len(rows) == 1
    assert rows[0]["label"] == keycrypt.mask("appkey:secret")
    assert "secret" not in rows[0]["label"]      # 평문이 라벨로 새면 안 된다


def test_list_does_not_return_plaintext(store):
    """★목록 조회에 평문 키가 섞여 나오면 화면으로 샌다."""
    store.add_customer_key(1, "vmake", "appkey:secret")
    row = store.list_customer_keys(1, "vmake")[0]
    assert "key_enc" not in row
    assert "appkey:secret" not in str(row)


def test_users_are_isolated(store):
    """A가 넣은 키가 B에게 보이면 안 된다."""
    store.add_customer_key(1, "vmake", "user-one-key")
    store.add_customer_key(2, "vmake", "user-two-key")
    assert store.get_customer_keys_plain(1, "vmake") == ["user-one-key"]
    assert store.get_customer_keys_plain(2, "vmake") == ["user-two-key"]


def test_services_are_isolated(store):
    store.add_customer_key(1, "vmake", "vmake-key")
    store.add_customer_key(1, "gemini", "gemini-key")
    assert store.get_customer_keys_plain(1, "vmake") == ["vmake-key"]
    assert store.get_customer_keys_plain(1, "gemini") == ["gemini-key"]


def test_duplicate_key_is_rejected(store):
    assert store.add_customer_key(1, "gemini", "same-key") is True
    assert store.add_customer_key(1, "gemini", "same-key") is False   # 두 번째는 거절
    assert len(store.list_customer_keys(1, "gemini")) == 1


def test_gemini_holds_multiple_keys(store):
    """구글만 여러 개 — 하나가 한도에 걸리면 다음으로 넘어가야 한다."""
    for k in ("k1", "k2", "k3"):
        store.add_customer_key(1, "gemini", k)
    assert store.get_customer_keys_plain(1, "gemini") == ["k1", "k2", "k3"]


def test_delete(store):
    store.add_customer_key(1, "vmake", "bye-key")
    kid = store.list_customer_keys(1, "vmake")[0]["id"]
    store.delete_customer_key(1, kid)
    assert store.list_customer_keys(1, "vmake") == []


def test_delete_only_own_key(store):
    """★남의 키를 id만 알면 지울 수 있으면 안 된다."""
    store.add_customer_key(1, "vmake", "mine")
    kid = store.list_customer_keys(1, "vmake")[0]["id"]
    store.delete_customer_key(999, kid)                  # 다른 사용자가 시도
    assert len(store.list_customer_keys(1, "vmake")) == 1  # 그대로 남아야


def test_set_status(store):
    store.add_customer_key(1, "gemini", "probe-me")
    kid = store.list_customer_keys(1, "gemini")[0]["id"]
    store.set_customer_key_status(kid, "ok")
    assert store.list_customer_keys(1, "gemini")[0]["status"] == "ok"


def test_status_defaults_to_unknown(store):
    store.add_customer_key(1, "gemini", "fresh")
    assert store.list_customer_keys(1, "gemini")[0]["status"] == "unknown"


def test_broken_key_does_not_shift_others(store):
    """★복호 실패한 행이 있어도 나머지 키의 id가 밀리면 안 된다.

    실증(2026-08-17): 화면목록과 평문목록을 zip으로 짝지으면 깨진 행이
    평문 쪽에서만 빠져 한 칸씩 밀린다 — id 2(깨진 키)에 key-C의 검증
    결과가 박혔다. 그러면 멀쩡한 키가 'bad'로 보인다. id를 함께 받아야 한다."""
    import sqlite3
    for k in ("key-A", "key-B", "key-C"):
        store.add_customer_key(1, "gemini", k)
    ids = [r["id"] for r in store.list_customer_keys(1, "gemini")]

    with sqlite3.connect(store.db_path) as c:      # 가운데 키를 깨뜨린다
        c.execute("UPDATE customer_keys SET key_enc='broken' WHERE id=?", (ids[1],))

    pairs = store.get_customer_keys_with_id(1, "gemini")
    assert pairs == [(ids[0], "key-A"), (ids[2], "key-C")]
    assert ids[1] not in [kid for kid, _ in pairs]   # 깨진 건 아예 빠진다
