from fastapi.testclient import TestClient
from shopping_shorts.app import app

client = TestClient(app)


def test_corpus_returns_lines():
    r = client.get("/api/voice-tune/corpus")
    assert r.status_code == 200
    lines = r.json()["lines"]
    assert any(l["role"] == "hook" for l in lines)


def test_preview_transforms_text_no_synth():
    r = client.post("/api/voice-tune/preview", json={
        "text": "이건 정말 좋습니다. 50% 할인",
        "profile": {"spoken_style": {"on": True, "intensity": 1.0},
                    "normalize": {"on": True}},
        "beat_role": "hook",
    })
    assert r.status_code == 200
    out = r.json()["text"]
    assert "좋아요" in out and "오십 퍼센트" in out


def test_synth_returns_audio_and_diff(monkeypatch, tmp_path):
    from shopping_shorts import app as appmod
    # TTS·ASR 스텁(실 API 안 부름)
    monkeypatch.setattr(appmod.tts, "synthesize_best",
                        lambda text, out_path, **kw: (open(out_path, "wb").write(b"x"), out_path)[1])
    monkeypatch.setattr(appmod.asr_check, "transcribe", lambda p: "이건 좋아요")
    # 모든 자연화 스테이지를 끔 — naturalize가 텍스트를 변형하지 않게 해서(예: 추임새 삽입)
    # ASR 목이 고정 반환하는 "이건 좋아요"와 정확히 일치시켜 diff.ok=True를 검증한다.
    off_profile = {k: {"on": False} for k in
                  ("normalize", "spoken_style", "pronunciation", "phrasing",
                   "endings", "fillers", "emotion_arc", "intonation")}
    off_profile.update({"n_best": 1, "seed": 3})
    r = client.post("/api/voice-tune/synth", json={
        "text": "이건 좋아요", "profile": off_profile,
        "line_id": "hook1", "preset_id": "kr-test",
    })
    assert r.status_code == 200
    j = r.json()
    assert "audio_url" in j and "diff" in j and j["diff"]["ok"] is True


def test_profile_freeze_and_load():
    save = client.post("/api/voice-tune/profile/kr-test",
                       json={"profile": {"spoken_style": {"intensity": 0.6}}, "frozen": True})
    assert save.status_code == 200
    got = client.get("/api/voice-tune/profile/kr-test")
    assert got.json()["profile"]["spoken_style"]["intensity"] == 0.6
