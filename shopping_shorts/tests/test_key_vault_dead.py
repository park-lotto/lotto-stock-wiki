"""401/403 사망 키는 영구 제외된다 — 2026-09-03 실사고(…nIWJaw가 사흘째 재호출).

이 테스트가 지키는 계약:
  ① 403/401은 mark_failure가 영구 제외로 보낸다(만료 없음)
  ② 429는 한시 잠금이라 만료되면 돌아온다
  ③ 최후 폴백(without_dead)에서도 사망 키는 안 돌아온다
"""
import time

import pytest

from pipeline.atoms import key_vault as kv


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")
    monkeypatch.setattr(kv, "get_keys", lambda g: ["K0", "K1", "K2"])
    return kv


def test_403_is_permanently_excluded(vault):
    exc = Exception("403 PERMISSION_DENIED. Your project has been denied access.")
    vault.mark_failure("K1", exc)
    assert vault.get_live_keys("general") == ["K0", "K2"]
    # 시간이 아무리 흘러도 안 돌아온다 — 잠금이 아니라 사망이다
    assert vault.get_live_keys("general") == ["K0", "K2"]
    assert vault.without_dead(["K0", "K1", "K2"]) == ["K0", "K2"]


def test_401_is_permanently_excluded(vault):
    vault.mark_failure("K0", Exception("401 UNAUTHENTICATED"))
    assert "K0" not in vault.get_live_keys("general")


def test_429_is_temporary_and_comes_back(vault, monkeypatch):
    vault.mark_failure("K2", Exception("429 RESOURCE_EXHAUSTED quota"))
    assert vault.get_live_keys("general") == ["K0", "K1"]      # 지금은 잠겨 있다
    later = time.time() + 26 * 3600          # 상한(25시간)보다 뒤로 감는다
    monkeypatch.setattr(time, "time", lambda: later)
    assert "K2" in vault.get_live_keys("general")              # 만료되면 돌아온다


def test_non_key_errors_leave_no_mark(vault):
    vault.mark_failure("K1", Exception("503 UNAVAILABLE high demand"))
    assert vault.get_live_keys("general") == ["K0", "K1", "K2"]


def test_invalid_api_key_is_permanently_excluded(vault):
    """★2026-09-04: 'API key not valid'(API_KEY_INVALID)도 영구 사망. 종전엔 쇼핑쇼츠 호출부가
    30분 잠금으로만 표시해 죽은 키 …sJbmaQ가 이틀째 다시 불렸다."""
    kv = vault
    kv.mark_failure("K1", Exception("400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key. API_KEY_INVALID"))
    assert "K1" not in kv.get_live_keys("general")
    assert "K1" not in kv.without_dead(["K0", "K1"])
