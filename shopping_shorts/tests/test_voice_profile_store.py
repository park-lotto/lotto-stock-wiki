import tempfile, os
from shopping_shorts.store import Store


def _store():
    p = os.path.join(tempfile.mkdtemp(), "t.db")
    return Store(p)


def test_upsert_and_get_naturalize_profile():
    s = _store()
    s.upsert_voice_preset({
        "preset_id": "kr-x", "name": "X", "lang": "KR", "base_voice_id": "v",
        "voice_settings": {"stability": 0.5}, "model_id": "eleven_v3",
        "naturalize_profile": {"spoken_style": {"intensity": 0.7}},
    })
    p = s.get_voice_preset("kr-x")
    assert p["naturalize_profile"]["spoken_style"]["intensity"] == 0.7


def test_missing_profile_is_none():
    s = _store()
    s.upsert_voice_preset({"preset_id": "kr-y", "name": "Y", "lang": "KR",
                           "base_voice_id": "v", "voice_settings": {}})
    assert s.get_voice_preset("kr-y").get("naturalize_profile") in (None, {})
