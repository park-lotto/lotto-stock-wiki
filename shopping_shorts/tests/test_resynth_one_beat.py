from pathlib import Path
from shopping_shorts import mix_pipeline as mp


def test_resynth_one_beat_overwrites_only_target(monkeypatch, tmp_path):
    calls = {"synth": [], "asr": 0}

    def fake_synth_line(narr, out, **kw):
        Path(out).write_bytes(b"MP3"); calls["synth"].append((narr, kw.get("voice")))
    monkeypatch.setattr(mp, "synthesize_line", fake_synth_line)
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 3.0)
    monkeypatch.setattr(mp.asr_check, "transcribe_words", lambda p: [{"word": "가", "start": 0.0, "end": 3.0}])
    monkeypatch.setattr(mp.caption_sync, "phrase_durs_from_words", lambda n, w, d: [3.0])

    plan = {"beats": [
        {"beat_idx": 0, "narration": "가나", "cap_durs": None},
        {"beat_idx": 1, "narration": "다라", "cap_durs": None}]}

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, j): return {"edit_plan": plan, "status": "ready_for_review"}
        def update_mix_job(self, j, **f): pass
    monkeypatch.setattr(mp, "Store", FakeStore)

    ov = {"voice_id": "V2", "settings": {"stability": 0.2}, "speed": 1.0}
    mp.resynth_one_beat("job1", 1, ov, "db", str(tmp_path))

    # 비트 1만 재합성
    assert len(calls["synth"]) == 1 and calls["synth"][0][0] == "다라"
    assert calls["synth"][0][1] == ov              # voice_override로 합성
    b1 = plan["beats"][1]
    assert b1["cap_durs"] == [3.0]                  # 재동기됨
    assert b1["voice_override"] == ov               # 저장됨
    assert b1["tts_path"].endswith("beat_1.mp3")
    assert "voice_override" not in plan["beats"][0]  # 비트0 무접촉
