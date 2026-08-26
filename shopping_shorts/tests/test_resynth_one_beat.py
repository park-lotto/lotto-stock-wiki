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
    monkeypatch.setattr(mp.caption_sync, "phrase_durs_from_words",
                        lambda n, w, d, preset=None: mp.caption_sync.PhraseTiming([3.0], 0.0))

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
    # ★현재 대본의 해시 경로여야 한다(2026-08-19). 옛 beat_1.mp3는 어느 대본의 음성인지
    #   알 수 없어 "대본은 새 것 / 소리는 옛 것"을 영영 판정할 수 없었다.
    assert b1["tts_path"] == mp._beat_tts_path(tmp_path / "job1" / "tts", b1)
    assert mp.tts_matches_narration(b1), "재합성 후에도 대본과 음성이 어긋난 채다"
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


def test_resynth_updates_target_seconds_and_conforms(monkeypatch, tmp_path):
    """★2026-08-20 실사고(job 087e03b69dc2): 대본수정으로 mp3가 16.8초가 됐는데
    target_seconds는 옛 2.9초 그대로였다. 미리보기는 mp3 실길이를, 편성·예산은 옛 초를
    따라가 초가 두 벌이 됐고, 화면이 모자라 앞 장면을 되풀이했다("끝나고 계속 반복").
    → 재합성 뒤에는 렌더와 같은 싱크 마무리(target 갱신 + 초과분 콘폼)가 돌아야 한다."""
    monkeypatch.setattr(mp, "synthesize_line",
                        lambda narr, out, **kw: Path(out).write_bytes(b"MP3"))
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 16.8)   # 새 음성 실길이
    monkeypatch.setattr(mp, "_beat_words", lambda *a, **k: [])
    monkeypatch.setattr(mp, "conform_narration", lambda n, budget, **k: None)  # 축약 실패 = 원문 유지

    plan = {"beats": [{
        "beat_idx": 0,
        "narration": "여러분 다이소 가면 이거 무조건 사오세요" * 3,
        "target_seconds": 2.9,                                   # ← 옛 값
        "primary": {"start": 0.0, "end": 2.9},                   # 화면 재료 2.9초뿐
        "cap_durs": None,
    }]}

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, j): return {"edit_plan": plan, "status": "ready_for_review"}
        def update_mix_job(self, j, **f): pass
    monkeypatch.setattr(mp, "Store", FakeStore)

    mp.resynth_one_beat("job1", 0, {"voice_id": "V"}, "db", str(tmp_path))

    b = plan["beats"][0]
    assert b["target_seconds"] == 16.8, "실측 길이로 갱신 안 됨 — 초가 두 벌로 남는다"
    assert b.get("sync_gap", 0) > 0.8, "화면 부족을 sync_gap으로 안 남기면 UI가 경고를 못 띄운다"
