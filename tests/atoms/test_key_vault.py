from concurrent.futures import ThreadPoolExecutor

import pytest
import pipeline.atoms.key_vault as kv


def test_get_keys_reads_numbered_env_vars(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_EMBED_KEY_2=e2\nGEMINI_EMBED_KEY_3=e3\n"
        "GEMINI_API_KEY=g1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    assert kv.get_keys("embed") == ["e1", "e2", "e3"]
    assert kv.get_keys("general") == ["g1"]


def test_get_keys_skips_missing_numbers_without_stopping(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_INGEST_KEY=i1\nGEMINI_INGEST_KEY_3=i3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    assert kv.get_keys("ingest") == ["i1", "i3"]


def test_get_keys_prefers_os_environ_over_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from_file\n", encoding="utf-8")
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setenv("GEMINI_API_KEY", "from_environ")
    assert kv.get_keys("general") == ["from_environ"]


def test_get_keys_raises_keyerror_for_unknown_group(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=key1\n", encoding="utf-8")
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    with pytest.raises(KeyError):
        kv.get_keys("nonexistent_group")


def test_mark_exhausted_removes_key_from_live_keys(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_EMBED_KEY_2=e2\nGEMINI_EMBED_KEY_3=e3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    assert kv.get_live_keys("embed") == ["e1", "e2", "e3"]
    kv.mark_exhausted("embed", "e2")
    assert kv.get_live_keys("embed") == ["e1", "e3"]


def test_mark_exhausted_is_scoped_per_group(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_INGEST_KEY=i1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    kv.mark_exhausted("embed", "e1")
    assert kv.get_live_keys("embed") == []
    assert kv.get_live_keys("ingest") == ["i1"]  # 다른 그룹은 영향 없음


def test_state_resets_on_new_day(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"date": "2020-01-01", "exhausted": {"embed": [0]}}', encoding="utf-8"
    )
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_EMBED_KEY=e1\n", encoding="utf-8")
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", state_path)
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    assert kv.get_live_keys("embed") == ["e1"]  # 어제자 소진 기록은 무시됨


def test_mark_exhausted_survives_concurrent_writers(monkeypatch, tmp_path):
    keys = [f"e{i}" for i in range(1, 9)]  # 8 distinct embed keys
    env_lines = [f"GEMINI_EMBED_KEY={keys[0]}\n"]
    env_lines += [f"GEMINI_EMBED_KEY_{i}={keys[i - 1]}\n" for i in range(2, 9)]
    env_file = tmp_path / ".env"
    env_file.write_text("".join(env_lines), encoding="utf-8")

    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    assert kv.get_live_keys("embed") == keys

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(kv.mark_exhausted, "embed", key) for key in keys]
        for f in futures:
            f.result()

    # All 8 keys marked exhausted concurrently -- no update should be lost
    # to interleaved read-modify-write, and no reader should observe a
    # torn/partial state file mid-write.
    assert kv.get_live_keys("embed") == []


def test_get_client_for_key_caches_by_key():
    from unittest.mock import patch, MagicMock

    with patch("pipeline.atoms.key_vault.genai.Client") as MockClient:
        MockClient.return_value = MagicMock()
        c1 = kv.get_client_for_key("same-key")
        c2 = kv.get_client_for_key("same-key")
        assert c1 is c2
        MockClient.assert_called_once_with(api_key="same-key")


def test_rotate_marks_current_key_exhausted_and_advances(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_EMBED_KEY_2=e2\n", encoding="utf-8"
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")
    monkeypatch.setattr(kv, "_tg_alert", lambda text: None)
    kv.reset("embed")

    assert kv.rotate("embed") is True
    assert kv.get_live_keys("embed") == ["e2"]


def test_rotate_returns_false_and_alerts_when_all_exhausted(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_EMBED_KEY=e1\n", encoding="utf-8")
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")
    alerts = []
    monkeypatch.setattr(kv, "_tg_alert", lambda text: alerts.append(text))
    kv.reset("embed")

    assert kv.rotate("embed") is False
    assert any("전체 소진" in a for a in alerts)


def test_is_daily_exhausted_error_vs_rpm_error():
    daily = Exception("429 RESOURCE_EXHAUSTED PerDay limit: 500")
    rpm = Exception("429 RESOURCE_EXHAUSTED PerMinute limit: 15")
    assert kv.is_daily_exhausted_error(daily) is True
    assert kv.is_daily_exhausted_error(rpm) is False
    assert kv.is_quota_error(rpm) is True


def test_get_client_raises_when_group_has_zero_configured_keys(monkeypatch, tmp_path):
    """그룹이 전혀 설정되지 않은 경우(키 0개) RuntimeError 발생해야 함."""
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_EMBED_KEY=e1\n", encoding="utf-8")  # briefing 그룹은 설정하지 않음
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    with pytest.raises(RuntimeError, match="briefing"):
        kv.get_client("briefing")


def test_get_client_returns_client_when_all_keys_exhausted_but_configured(monkeypatch, tmp_path):
    """모든 키가 소진되었지만 구성된 경우(키 1개 이상), 마지막 키로 클라이언트 반환해야 함."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_EMBED_KEY_2=e2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")
    kv.reset("embed")

    # 모든 키를 소진 처리
    kv.mark_exhausted("embed", "e1")
    kv.mark_exhausted("embed", "e2")
    assert kv.get_live_keys("embed") == []  # 확인: 모든 키 소진됨

    # RuntimeError 발생하지 않고 클라이언트 반환해야 함
    client = kv.get_client("embed")
    assert client is not None
