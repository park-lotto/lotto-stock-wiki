"""API가 best를 그룹에 실어 내리는가 + 정렬을 보존하는가.

Store가 정렬해 줘도 app.py가 dict로 묶는 과정에서 순서가 깨지면 화면이 안 바뀐다.
그 이음새를 잠근다(파이썬 dict는 삽입 순서를 보존하므로 통과해야 정상).
"""
from fastapi.testclient import TestClient
from shopping_shorts.app import app


def test_groups_carry_best_and_order(monkeypatch):
    rows = [
        {"preset_id": "kr-mina-stable", "group_id": "kr-mina", "variant": "stable",
         "name": "미나", "one_liner": "차분", "lang": "KR", "archetype": "차분",
         "base_voice_id": "v1", "voice_settings": {}, "default_speed": 1.0,
         "default_silence_trim": "mid", "sample_file": "kr-mina-stable.mp3", "best": True},
        {"preset_id": "kr-han-stable", "group_id": "kr-han", "variant": "stable",
         "name": "한", "one_liner": "캐주얼", "lang": "KR", "archetype": "캐주얼",
         "base_voice_id": "v2", "voice_settings": {}, "default_speed": 1.0,
         "default_silence_trim": "mid", "sample_file": None, "best": False},
    ]
    monkeypatch.setattr("shopping_shorts.app.Store",
                        lambda *_a, **_k: type("S", (), {"list_voice_presets": lambda s, lang=None: rows})())
    d = TestClient(app).get("/api/voice-presets?lang=KR").json()
    assert [g["group_id"] for g in d["groups"]] == ["kr-mina", "kr-han"]
    assert [g["best"] for g in d["groups"]] == [True, False]


def test_best_defaults_false_when_absent(monkeypatch):
    rows = [{"preset_id": "x-stable", "group_id": "x", "variant": "stable", "name": "x",
             "one_liner": "", "lang": "KR", "archetype": "", "base_voice_id": "v",
             "voice_settings": {}, "default_speed": 1.0, "default_silence_trim": "off",
             "sample_file": None}]
    monkeypatch.setattr("shopping_shorts.app.Store",
                        lambda *_a, **_k: type("S", (), {"list_voice_presets": lambda s, lang=None: rows})())
    assert TestClient(app).get("/api/voice-presets?lang=KR").json()["groups"][0]["best"] is False
