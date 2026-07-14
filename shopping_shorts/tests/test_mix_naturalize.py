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
    profile = {"n_best": 1, "seed": 5}
    mix_pipeline._synthesize_beats(beats, tmp_path, voice_id="v", voice_settings=None,
                                   speed=1.0, extra_tempo=1.0, trim="off", profile=profile)
    assert seen[0]["text"] == "N:첫째"           # naturalize 적용됨
    assert seen[0]["next"] == "둘째"             # 다음 비트 원문이 next_text
    assert seen[1]["prev"] == "첫째"             # 이전 비트 원문이 previous_text
    assert beats[0]["tts_path"].endswith("beat_0.mp3")
