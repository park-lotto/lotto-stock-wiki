import json, tempfile
from pathlib import Path
from shopping_shorts import voice_presets
from shopping_shorts.store import Store


def test_load_presets_file_has_kr_presets():
    rows = voice_presets.load_presets_file()
    assert len(rows) >= 6
    assert all(r.get("lang") for r in rows)
    assert all(r.get("base_voice_id") for r in rows)


def test_voice_settings_match_their_engine():
    """설정 축은 **엔진마다 다르다**(2026-08-19 타입캐스트 추가).

    종전엔 `all("stability" in settings)`였는데, 그건 "일레븐랩스뿐"이라는 전제였다.
    타입캐스트는 stability/style이 없고 emotion/emotion_intensity를 쓴다 — 축을 섞으면
    한 엔진에서 조용히 무시되는 값을 다른 엔진 기준으로 튜닝하게 된다(0순위-B).
    그래서 "전부 같은 키"가 아니라 "제 엔진의 키를 갖는가"로 잠근다."""
    from shopping_shorts import typecast_tts
    for r in voice_presets.load_presets_file():
        s = r.get("voice_settings", {})
        if typecast_tts.is_typecast(r.get("model_id")):
            assert "emotion" in s, r["preset_id"]
            assert "stability" not in s, r["preset_id"]      # 일레븐 축이 새어들면 안 된다
        else:
            assert "stability" in s, r["preset_id"]


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
