"""후보 선택(/api/mix/candidate) → 미리보기가 TTS 없음으로 죽던 회귀(2026-07-21 실사고).

증상: 사장님이 장면우선 믹스에서 후보 카드를 누르면 미리보기가
`video_assemble: 렌더할 비트가 없습니다`로 실패. 편집안엔 비트가 4개(🟢4) 있는데도.

근본원인: _plan_and_tts가 set_mix_candidates(TTS 합성 **전** 스냅샷)로 후보를 저장하고,
/api/mix/candidate가 그 저장본 plan을 edit_plan에 그대로 꽂는다 → 비트에 tts_path가 없어
run_preview의 tts_paths가 비고 → video_assemble이 모든 비트를 스킵 → 렌더할 비트 0.

수정(방어심층): 렌더 경로(run_preview/run_render)가 조립 직전 자기 plan의 비트에 TTS가
있는지 보장한다(_synthesize_beats skip_existing=True). 추천 후보(이미 TTS 있음)는 재합성 0,
갈아끼운 후보만 그 자리에서 합성한다. edit_plan을 어떻게 세팅했든 렌더는 스스로 낫는다.

assemble/synthesize는 실행하지 않는다(이 저장소 pytest는 실 ffmpeg/ElevenLabs를 못 부른다) —
이름 import된 심볼을 가짜화한다.
"""
import pytest

from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


def _tts_less_candidate_plan():
    """set_mix_candidates가 저장하는 형태 — 비트에 tts_path가 **없다**(합성 전 스냅샷)."""
    return {"beats": [
        {"beat_idx": 0, "narration": "여러분 다이소 가시면 이건 무조건 담으세요",
         "primary": {"video_id": "v1", "start": 0.0, "end": 2.0}},
        {"beat_idx": 1, "narration": "가격도 착한데 활용도가 미쳤어요",
         "primary": {"video_id": "v1", "start": 2.0, "end": 4.0}},
    ]}


@pytest.fixture
def job(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    store = Store(db)
    store.create_mix_job("J1", ["https://x/1"], 20, "template")
    # 후보 선택 직후 상태: edit_plan = TTS 없는 후보 plan (api_mix_candidate가 만드는 그대로)
    store.update_mix_job("J1", edit_plan=_tts_less_candidate_plan(),
                         status="ready_for_review")
    monkeypatch.setattr(mix_pipeline, "_resolve_sources",
                        lambda job, work: {"v1": str(tmp_path / "v1.mp4")})

    # synthesize_line: 실 ElevenLabs 대신 mp3 파일만 만든다. 부른 비트를 기록.
    synth_calls = []

    def fake_synth(narration, out_path, **kw):
        synth_calls.append(str(narration))
        open(out_path, "w").write("mp3")
        return str(out_path)

    monkeypatch.setattr(mix_pipeline, "synthesize_line", fake_synth)
    monkeypatch.setattr(mix_pipeline.asr_check, "transcribe_words", lambda p: None)
    return db, str(tmp_path / "work"), store, synth_calls


def test_preview_of_tts_less_candidate_gets_all_beats(job, monkeypatch):
    """★회귀: TTS 없는 후보 plan으로도 미리보기가 모든 비트의 tts_path를 조립에 넘겨야 한다.

    수정 전: tts_paths={} → assemble이 빈 tts로 불려 video_assemble이 렌더할 비트 0.
    수정 후: run_preview가 조립 직전 TTS를 보장 → assemble이 비트 2개 모두의 tts를 받는다.
    """
    db, work, store, _ = job
    seen = {}

    def fake_assemble(plan, tts_paths, srcs, out, clean_fn=None, headcopy=None,
                      caption_style=None, deco=None, cutaway_paths=None, sfx_paths=None):
        seen["tts_paths"] = dict(tts_paths)
        open(out, "w").write("x")
        return out

    monkeypatch.setattr(mix_pipeline, "assemble", fake_assemble)
    mix_pipeline.run_preview("J1", db, work)

    j = store.get_mix_job("J1")
    assert j["preview_status"] == "ready", \
        f"미리보기가 실패했다(TTS 없는 후보를 못 낫게 함): {j.get('preview_error')!r}"
    assert set(seen["tts_paths"].keys()) == {0, 1}, \
        f"조립에 넘어간 tts가 모든 비트를 못 덮었다: {seen['tts_paths']!r} — 렌더할 비트가 없어진다"


def test_recommended_plan_does_not_resynthesize(job, monkeypatch):
    """추천 후보(이미 TTS 있음)는 미리보기가 재합성하지 않는다(재과금 0)."""
    db, work, store, synth_calls = job
    # 이미 TTS가 붙은 plan(=추천 edit_plan 상태)을 넣고, 그 mp3 파일이 실재하게 만든다.
    import pathlib
    p0 = pathlib.Path(work); p0.mkdir(parents=True, exist_ok=True)
    a0, a1 = str(p0 / "b0.mp3"), str(p0 / "b1.mp3")
    open(a0, "w").write("mp3"); open(a1, "w").write("mp3")
    plan = _tts_less_candidate_plan()
    plan["beats"][0]["tts_path"] = a0
    plan["beats"][1]["tts_path"] = a1
    store.update_mix_job("J1", edit_plan=plan)

    monkeypatch.setattr(mix_pipeline, "assemble",
                        lambda *a, **k: (open(a[3], "w").write("x"), a[3])[1])
    mix_pipeline.run_preview("J1", db, work)

    assert synth_calls == [], \
        f"이미 TTS 있는 비트를 재합성했다(재과금): {synth_calls!r}"


def test_synthesize_beats_skip_existing(tmp_path, monkeypatch):
    """_synthesize_beats(skip_existing=True): 유효한 tts 파일이 있는 비트는 건너뛴다."""
    synth = []
    monkeypatch.setattr(mix_pipeline, "synthesize_line",
                        lambda n, out, **k: (synth.append(str(n)), open(out, "w").write("m"))[0])
    monkeypatch.setattr(mix_pipeline.asr_check, "transcribe_words", lambda p: None)

    have = tmp_path / "have.mp3"; have.write_text("m")
    beats = [
        {"beat_idx": 0, "narration": "이미 있음", "tts_path": str(have)},
        {"beat_idx": 1, "narration": "합성 필요"},  # tts_path 없음
    ]
    mix_pipeline._synthesize_beats(beats, tmp_path / "tts", voice=None, skip_existing=True)

    assert synth == ["합성 필요"], f"skip_existing이 이미 있는 비트를 재합성했거나 놓쳤다: {synth!r}"
    assert beats[0]["tts_path"] == str(have), "기존 tts_path가 바뀌었다"
    assert beats[1].get("tts_path"), "빠진 비트가 합성되지 않았다"
