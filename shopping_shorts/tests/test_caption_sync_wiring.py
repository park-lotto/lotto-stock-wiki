"""배선 — 합성 지점에서 cap_durs를 계산·저장하고, 키 없으면 미설정(회귀0).
저장위치(_synthesize_beats)=읽기위치(_burn_captions→_beat_timeline 경유)를 죽는 테스트로 잠근다."""
import shopping_shorts.mix_pipeline as mp


def test_synth_sets_cap_durs_when_asr_available(monkeypatch, tmp_path):
    beats = [{"beat_idx": 0, "narration": "귤은 손으로 까요"}]
    # synthesize_line·probe·transcribe_words를 스텁으로: 실렌더/네트워크 없이 배선만 검증.
    monkeypatch.setattr(mp, "synthesize_line", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 1.5, raising=False)
    monkeypatch.setattr(mp.asr_check, "transcribe_words",
                        lambda p: [{"word": "귤은", "start": 0.0, "end": 0.5},
                                   {"word": "손으로", "start": 0.5, "end": 1.0},
                                   {"word": "까요", "start": 1.0, "end": 1.5}])
    mp._synthesize_beats(beats, tmp_path, voice={})
    assert isinstance(beats[0]["cap_durs"], list) and len(beats[0]["cap_durs"]) >= 1


def test_synth_leaves_cap_durs_absent_without_asr(monkeypatch, tmp_path):
    beats = [{"beat_idx": 0, "narration": "귤은 손으로 까요"}]
    monkeypatch.setattr(mp, "synthesize_line", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 1.5, raising=False)
    monkeypatch.setattr(mp.asr_check, "transcribe_words", lambda p: None)  # 키 없음 흉내
    mp._synthesize_beats(beats, tmp_path, voice={})
    assert beats[0].get("cap_durs") is None


def test_render_reads_stored_cap_durs(tmp_path, monkeypatch):
    """저장된 cap_durs가 _beat_timeline을 거쳐 _caption_drawtexts에 real_durs로
    전달되는가(저장위치=읽기위치). _beat_timeline이 beat 원본이 아니라 새 dict를
    만들기 때문에, cap_durs를 안 실어보내면 여기서 죽는다(2026-07-18 실측)."""
    import shopping_shorts.video_assemble as va

    font = tmp_path / "f.ttf"
    font.write_bytes(b"\x00")
    base = tmp_path / "base.mp4"
    base.write_bytes(b"\x00")

    monkeypatch.setattr(va, "_run_ffmpeg", lambda cmd, **k: None)
    monkeypatch.setattr(va, "_resolve_font", lambda: str(font))
    monkeypatch.setattr(va.shutil, "copy", lambda *a, **k: None)
    monkeypatch.setattr(va, "_probe_duration", lambda p: 1.5)

    captured = {}

    def fake_drawtexts(narration, dur, work, idx, t0=0.0, style=None, real_durs=None, cap_offset=0.0, tail=0.5):
        captured["real_durs"] = real_durs
        return []

    monkeypatch.setattr(va, "_caption_drawtexts", fake_drawtexts)

    plan = {"beats": [{"beat_idx": 0, "role": "hook", "narration": "귤은 까요",
                       "cap_durs": [0.9, 0.6]}]}
    tts = {0: "a.mp3"}
    va._burn_captions(str(base), plan, tts, str(tmp_path / "out.mp4"), tmp_path, None, None, None)

    assert captured["real_durs"] == [0.9, 0.6]


def test_render_without_asr_passes_none_real_durs(tmp_path, monkeypatch):
    """cap_durs가 없는(비ASR) 비트는 real_durs=None → _caption_drawtexts의 기존
    char-weight 폴백 경로 그대로(회귀0 확인)."""
    import shopping_shorts.video_assemble as va

    font = tmp_path / "f.ttf"
    font.write_bytes(b"\x00")
    base = tmp_path / "base.mp4"
    base.write_bytes(b"\x00")

    monkeypatch.setattr(va, "_run_ffmpeg", lambda cmd, **k: None)
    monkeypatch.setattr(va, "_resolve_font", lambda: str(font))
    monkeypatch.setattr(va.shutil, "copy", lambda *a, **k: None)
    monkeypatch.setattr(va, "_probe_duration", lambda p: 1.5)

    captured = {}

    def fake_drawtexts(narration, dur, work, idx, t0=0.0, style=None, real_durs=None, cap_offset=0.0, tail=0.5):
        captured["real_durs"] = real_durs
        return []

    monkeypatch.setattr(va, "_caption_drawtexts", fake_drawtexts)

    plan = {"beats": [{"beat_idx": 0, "role": "hook", "narration": "귤은 까요"}]}  # cap_durs 없음
    tts = {0: "a.mp3"}
    va._burn_captions(str(base), plan, tts, str(tmp_path / "out.mp4"), tmp_path, None, None, None)

    assert captured["real_durs"] is None
