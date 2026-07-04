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
