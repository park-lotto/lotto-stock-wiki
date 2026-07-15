from shopping_shorts import mix_pipeline


def test_beat_tts_applies_naturalize_and_continuity(monkeypatch, tmp_path):
    """_synthesize_beats가 각 비트에 naturalize 적용 + previous/next_text 전달."""
    seen = []
    def fake_synth_best(text, out_path, **kw):
        seen.append({"text": text, "prev": kw.get("previous_text"), "next": kw.get("next_text")})
        open(out_path, "wb").write(b"x")
        return out_path
    monkeypatch.setattr(mix_pipeline.tts, "synthesize_best", fake_synth_best)
    monkeypatch.setattr(mix_pipeline.audio_post, "post_process", lambda *a, **k: a[1])
    # naturalize를 관측 가능한 스텁으로(원문에 접두어)
    monkeypatch.setattr(mix_pipeline, "naturalize",
                        lambda text, profile, **kw: "N:" + text)

    beats = [{"beat_idx": 0, "narration": "첫째", "role": "hook"},
             {"beat_idx": 1, "narration": "둘째", "role": "body"}]
    voice = {"voice_id": "v", "settings": None, "speed": 1.0, "silence_trim": "off",
             "naturalize_profile": {"n_best": 1, "seed": 5}}
    mix_pipeline._synthesize_beats(beats, tmp_path, voice=voice)
    assert seen[0]["text"] == "N:첫째"           # naturalize 적용됨
    assert seen[0]["next"] == "둘째"             # 다음 비트 원문이 next_text
    assert seen[1]["prev"] == "첫째"             # 이전 비트 원문이 previous_text
    assert beats[0]["tts_path"].endswith("beat_0.mp3")


def test_voice_snapshot_profile_reaches_render(monkeypatch, tmp_path):
    """job voice 스냅샷의 naturalize_profile·model_id가 실제 TTS 호출까지 도달한다.

    회귀: 이 구간(preset→스냅샷→렌더)을 통과하는 테스트가 없어서, 동결한 프로파일이
    렌더에 전혀 안 실리는 버그가 유닛 리뷰를 그대로 통과했다(2026-07-15 리뷰 S1)."""
    seen = {}
    def fake_synth_best(text, out_path, **kw):
        seen.update(kw)
        open(out_path, "wb").write(b"x")
        return out_path
    monkeypatch.setattr(mix_pipeline.tts, "synthesize_best", fake_synth_best)
    monkeypatch.setattr(mix_pipeline.audio_post, "post_process", lambda *a, **k: a[1])

    beats = [{"beat_idx": 0, "narration": "안녕하세요", "role": "hook"}]
    voice = {"voice_id": "kelee", "settings": {"stability": 0.6}, "speed": 1.15,
             "silence_trim": "mid", "model_id": "eleven_v3",
             "naturalize_profile": {"n_best": 3, "seed": 77}}
    mix_pipeline._synthesize_beats(beats, tmp_path, voice=voice)

    assert seen["voice_id"] == "kelee"            # 프리셋 성우(기본 성우 아님)
    assert seen["voice_settings"] == {"stability": 0.6}
    assert seen["n"] == 3 and seen["base_seed"] == 77   # 동결 프로파일의 N-best·seed
    assert seen["ranker"] is not None             # 렌더도 ASR 랭커를 태운다(리뷰 S4)
    assert seen["model_id"] == "eleven_v3"
