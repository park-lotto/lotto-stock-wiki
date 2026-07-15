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
    # TTS·ASR·후처리 스텁(실 API·ffmpeg 안 부름)
    monkeypatch.setattr(appmod.tts, "synthesize_best",
                        lambda text, out_path, **kw: (open(out_path, "wb").write(b"x"), out_path)[1])
    monkeypatch.setattr(appmod.asr_check, "transcribe", lambda p: "이건 좋아요")
    monkeypatch.setattr(appmod.audio_post, "post_process", lambda *a, **k: a[1])
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


def test_frozen_profile_lands_in_job_voice_snapshot(monkeypatch):
    """작업대에서 동결한 프로파일이 /api/mix/voice가 만드는 job 스냅샷에 실린다.

    회귀: 스냅샷에 naturalize_profile이 빠져 렌더가 기본값으로 조용히 합성하던 버그(리뷰 S1).
    이 테스트가 '저장 위치 ≠ 읽기 위치' seam을 잠근다."""
    from shopping_shorts import app as appmod
    client.post("/api/voice-tune/profile/kr-snap",
                json={"profile": {"n_best": 3, "seed": 9}, "frozen": True,
                      "voice_id": "kelee"})
    snap = appmod._voice_snapshot(appmod.Store(appmod.DB_PATH), {"preset_id": "kr-snap"})
    assert snap["naturalize_profile"]["seed"] == 9
    assert snap["naturalize_profile"]["n_best"] == 3
    assert snap["voice_id"] == "kelee"        # 프리셋 성우가 스냅샷에 실림


def test_seed_presets_does_not_wipe_frozen_profile():
    """startup seed_presets(JSON 재적용)가 동결 프로파일을 NULL로 덮지 않는다(리뷰 S2)."""
    from shopping_shorts import app as appmod
    store = appmod.Store(appmod.DB_PATH)
    client.post("/api/voice-tune/profile/kr-keep",
                json={"profile": {"seed": 123}, "frozen": True})
    # JSON 시드처럼 naturalize_profile 없는 dict로 같은 preset_id upsert
    store.upsert_voice_preset({"preset_id": "kr-keep", "name": "kr-keep",
                               "base_voice_id": "v", "voice_settings": {}})
    assert store.get_voice_preset("kr-keep")["naturalize_profile"]["seed"] == 123
