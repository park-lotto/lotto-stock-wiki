from pathlib import Path
from fastapi import BackgroundTasks
from shopping_shorts import mix_pipeline as mp
from shopping_shorts import app as appmod


def test_resynth_one_beat_overwrites_only_target(monkeypatch, tmp_path):
    calls = {"synth": [], "asr": 0}

    def fake_synth_line(narr, out, **kw):
        Path(out).write_bytes(b"MP3"); calls["synth"].append((narr, kw.get("voice")))
    monkeypatch.setattr(mp, "synthesize_line", fake_synth_line)
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 3.0)
    monkeypatch.setattr(mp.asr_check, "transcribe_words", lambda p: [{"word": "가", "start": 0.0, "end": 3.0}])
    monkeypatch.setattr(mp.caption_sync, "phrase_durs_from_words", lambda n, w, d, preset=None: [3.0])

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


def test_api_mix_tts_regen_merges_override_onto_job_voice_snapshot(monkeypatch):
    """리뷰 지적: override가 job.voice 스냅샷 위에 병합돼야 한다.
    UI가 안 보낸 키(model_id·silence_trim 등)는 job 값을 유지 —
    빠지면 _voice_params가 기본값(eleven_v3 등)으로 채워 재생성 비트만 소리가 달라진다."""
    captured = {}

    def fake_resynth_one_beat(job_id, beat_idx, voice_override, db_path, work_dir):
        captured["voice_override"] = voice_override
    monkeypatch.setattr(appmod, "resynth_one_beat", fake_resynth_one_beat)

    job_voice = {
        "voice_id": "JOB_V", "model_id": "eleven_multilingual_v2",
        "silence_trim": "strong", "settings": {"stability": 0.5},
    }
    job = {"edit_plan": {"beats": []}, "status": "ready_for_review", "voice": job_voice}

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, j): return job
    monkeypatch.setattr(appmod, "Store", FakeStore)

    body = {"voice_id": "TONE_V", "settings": {"stability": 0.2}}  # speed 미포함
    bg = BackgroundTasks()
    appmod.api_mix_tts_regen("job1", 0, body, bg)
    for task in bg.tasks:
        task.func(*task.args, **task.kwargs)

    ov = captured["voice_override"]
    # UI가 보낸 키는 덮어씀
    assert ov["voice_id"] == "TONE_V"
    assert ov["settings"] == {"stability": 0.2}
    # UI가 안 보낸 job 스냅샷 필드는 유지됨 — 이게 이번 수정의 핵심
    assert ov["model_id"] == "eleven_multilingual_v2"
    assert ov["silence_trim"] == "strong"
    # speed는 body·job 스냅샷 둘 다에 없었으니 None으로 강제되면 안 됨 — 키 자체가 없어야 함
    assert "speed" not in ov
