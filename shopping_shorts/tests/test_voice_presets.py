import json, tempfile
from pathlib import Path
from shopping_shorts import voice_presets
from shopping_shorts.store import Store


def test_load_presets_file_has_kr_presets():
    rows = voice_presets.load_presets_file()
    assert len(rows) >= 6
    assert all(r.get("lang") for r in rows)
    assert all(r.get("base_voice_id") for r in rows)
    assert all("stability" in r.get("voice_settings", {}) for r in rows)


def test_seed_upserts_into_db(monkeypatch):
    fake = [{
        "preset_id": "kr-x", "name": "X", "lang": "KR", "base_voice_id": "v",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
        "default_speed": 1.0, "default_silence_trim": "off", "origin": "curated",
    }]
    monkeypatch.setattr(voice_presets, "load_presets_file", lambda: fake)
    s = Store(Path(tempfile.mkdtemp()) / "t.db")
    n = voice_presets.seed_presets(s)
    assert n == 1
    assert s.get_voice_preset("kr-x")["name"] == "X"
    assert voice_presets.seed_presets(s) == 1
    assert len(s.list_voice_presets()) == 1
