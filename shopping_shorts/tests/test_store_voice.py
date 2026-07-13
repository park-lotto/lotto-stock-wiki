import tempfile
from pathlib import Path
from shopping_shorts.store import Store


def _store():
    return Store(Path(tempfile.mkdtemp()) / "t.db")


def test_upsert_and_list_and_get_preset():
    s = _store()
    p = {
        "preset_id": "kr-calm-seulgi", "name": "슬기", "one_liner": "차분한 여성",
        "lang": "KR", "archetype": "차분정보", "base_voice_id": "v1",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
        "default_speed": 1.1, "default_silence_trim": "mid",
        "sample_file": "seulgi.mp3", "source_ref": "채널X 참고", "origin": "curated",
    }
    s.upsert_voice_preset(p)
    got = s.get_voice_preset("kr-calm-seulgi")
    assert got["name"] == "슬기"
    assert got["voice_settings"]["stability"] == 0.65
    assert got["default_speed"] == 1.1

    p2 = dict(p, name="슬기2")
    s.upsert_voice_preset(p2)
    assert s.get_voice_preset("kr-calm-seulgi")["name"] == "슬기2"

    rows = s.list_voice_presets(lang="KR")
    assert len(rows) == 1 and rows[0]["preset_id"] == "kr-calm-seulgi"
    assert s.list_voice_presets(lang="JP") == []


def test_mix_job_voice_json_roundtrip():
    s = _store()
    s.create_mix_job("j1", ["u"], 30, "구조")
    s.update_mix_job("j1", voice={"preset_id": "kr-calm-seulgi", "speed": 1.3, "silence_trim": "mid"})
    job = s.get_mix_job("j1")
    assert job["voice"]["preset_id"] == "kr-calm-seulgi"
    assert job["voice"]["speed"] == 1.3
