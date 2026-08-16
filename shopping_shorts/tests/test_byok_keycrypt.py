"""키 암복호 — 평문이 DB에 남지 않는지, 마스터키 없으면 꺼지는지."""
import importlib
import pytest
from shopping_shorts import keycrypt


def _reload(monkeypatch, master):
    """마스터키를 바꿔 모듈을 다시 읽는다(모듈 로드 시점에 키를 잡으므로)."""
    if master is None:
        monkeypatch.delenv("BYOK_MASTER_KEY", raising=False)
    else:
        monkeypatch.setenv("BYOK_MASTER_KEY", master)
    return importlib.reload(keycrypt)


_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="


def test_roundtrip(monkeypatch):
    kc = _reload(monkeypatch, _KEY)
    plain = "AQ.Ab8RNxxxxxxxxxxxxxxxxxxxxkz1MA"
    token = kc.encrypt(plain)
    assert token != plain              # 평문이 그대로 남으면 안 된다
    assert kc.decrypt(token) == plain


def test_same_plain_gives_different_ciphertext(monkeypatch):
    """같은 키를 두 번 넣어도 암호문이 달라야 한다(Fernet은 IV를 쓴다)."""
    kc = _reload(monkeypatch, _KEY)
    assert kc.encrypt("same") != kc.encrypt("same")


def test_mask_hides_middle(monkeypatch):
    kc = _reload(monkeypatch, _KEY)
    masked = kc.mask("AQ.Ab8RNxxxxxxxxxxxxxxxxxxxxkz1MA")
    assert masked.startswith("AQ.Ab8RN")
    assert masked.endswith("kz1MA")
    assert "•" in masked
    assert "xxxxxxxx" not in masked     # 가운데가 실제로 가려졌나


def test_mask_short_key_does_not_leak(monkeypatch):
    """짧은 키는 앞뒤를 보여주면 통째로 노출된다 — 전부 가린다."""
    kc = _reload(monkeypatch, _KEY)
    assert "abc" not in kc.mask("abc")


def test_fingerprint_is_stable_and_distinct(monkeypatch):
    kc = _reload(monkeypatch, _KEY)
    assert kc.fingerprint("key-a") == kc.fingerprint("key-a")
    assert kc.fingerprint("key-a") != kc.fingerprint("key-b")


def test_disabled_without_master_key(monkeypatch):
    """★마스터키가 없으면 평문 저장으로 폴백하지 않는다 — 기능을 끈다."""
    kc = _reload(monkeypatch, None)
    assert kc.enabled() is False
    with pytest.raises(RuntimeError):
        kc.encrypt("anything")


def test_enabled_with_master_key(monkeypatch):
    kc = _reload(monkeypatch, _KEY)
    assert kc.enabled() is True
