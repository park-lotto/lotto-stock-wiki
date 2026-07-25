"""전역 발음사전이 실제 합성 텍스트에 반영되는지(2026-07-22).
synthesize_line이 global_pron을 받으면 그 구절이 재표기돼 TTS로 넘어간다."""
from shopping_shorts import mix_pipeline as mp


def test_global_pron_respells_text_into_tts(monkeypatch, tmp_path):
    seen = {}
    def fake_synth_best(text, out_path, **kw):
        seen["text"] = text
        open(out_path, "wb").write(b"x")
        return out_path
    monkeypatch.setattr(mp.tts, "synthesize_best", fake_synth_best)
    monkeypatch.setattr(mp.audio_post, "post_process", lambda *a, **k: a[1])

    out = tmp_path / "b.mp3"
    mp.synthesize_line("이건 좋은데요", out,
                       voice={"voice_id": "v", "speed": 1.0},
                       global_pron={"좋은데요": "조은데요"})
    assert "조은데요" in seen["text"]
    assert "좋은데요" not in seen["text"]


def test_no_global_pron_keeps_text(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(mp.tts, "synthesize_best",
                        lambda text, out_path, **kw: (seen.__setitem__("text", text),
                                                      open(out_path, "wb").write(b"x"), out_path)[-1])
    monkeypatch.setattr(mp.audio_post, "post_process", lambda *a, **k: a[1])
    out = tmp_path / "b.mp3"
    mp.synthesize_line("이건 좋은데요", out, voice={"voice_id": "v", "speed": 1.0})
    assert "좋은데요" in seen["text"]      # 전역 미지정 → 원문 유지
