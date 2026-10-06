"""Fish 기본 성우 속도(관제 123, 2026-10-05) — 결과 말 빠르기 맞춤값이 파일·주인 함수에서 같은가."""
from shopping_shorts import voice_presets


def test_fish_speed_owner_matches_presets_file():
    fish = [p for p in voice_presets.load_presets_file() if p["preset_id"].startswith("fs-")]
    assert len(fish) == 8
    for p in fish:
        assert voice_presets.default_speed(p["base_voice_id"]) == p["default_speed"], p["preset_id"]
        assert 0.8 <= p["default_speed"] <= 1.6
    # 기존 규칙은 그대로: 미나 1.35, 그 외 1.25
    assert voice_presets.default_speed(voice_presets.MINA_VOICE_ID) == 1.35
    assert voice_presets.default_speed("tc_68257f68bc6e3c161ab5078d") == 1.25
