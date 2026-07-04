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
