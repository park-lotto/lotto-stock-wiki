"""싱크 콘폼루프(2026-07-20) — 대사가 영상 예산을 넘으면 문장을 압축해 그 비트만 재TTS.

설계: docs/superpowers/specs/2026-07-20-대본영상싱크-콘폼루프-design.md
원리: 서사=대본 / 시간=영상 / 표면=콘폼. 영상 레버는 이미 소진돼 있으므로
(_plan_beat_clips가 primary+alternates 전부 사용 후에만 얼림) 남은 레버는 대본 길이뿐.

여기서 지키는 불변식:
- narration 교체는 재TTS **성공 후에만**(문장/음성 불일치 금지).
- 리라이트 실패·게이트 불통과·TTS 예외 → 원문 유지 + sync_gap 플래그 잔존(freeze 폴백).
- 마지막 비트 여운: 실프레임 여유는 1배속, 부족분은 out_dur만(기존 slowmo/freeze 기계가 흡수).
"""
import pathlib

import pytest

from shopping_shorts import edit_plan as ep
from shopping_shorts import mix_pipeline as mp
from shopping_shorts.video_assemble import _LAST_RUNOUT, _extend_last_clip_for_runout

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


# ── T2: conform_narration 게이트 ───────────────────────────────
def test_conform_accepts_within_gate(monkeypatch):
    # 목표 2.3초 → 약 13자. 12자(공백제외) = 추정 2.1초 → 0.8~1.2배 안 → 수락.
    monkeypatch.setattr(ep, "_vault_call", lambda *a, **k: {"narration": "국물 없이도 밥이 잘 넘어가요"})
    out = ep.conform_narration("원래 아주 길고 긴 문장이 여기 있었다고 치자 정말 길다", 2.3)
    assert out == "국물 없이도 밥이 잘 넘어가요"


def test_conform_rejects_too_long_result(monkeypatch):
    # 30자 = 추정 5.3초 > 2.3×1.2 → 게이트가 거부(None) — 뜻 훼손 없는 폴백.
    monkeypatch.setattr(ep, "_vault_call",
                        lambda *a, **k: {"narration": "가" * 30})
    assert ep.conform_narration("원문", 2.3) is None


def test_conform_no_keys_returns_none(monkeypatch):
    monkeypatch.setattr(ep, "_vault_call", lambda *a, **k: None)
    assert ep.conform_narration("원문 문장", 2.3) is None


def test_conform_empty_input_short_circuits(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("빈 입력인데 Gemini를 불렀다")
    monkeypatch.setattr(ep, "_vault_call", boom)
    assert ep.conform_narration("", 2.3) is None
    assert ep.conform_narration("문장", 0) is None


# ── T3: _conform_beats — 초과 비트만, 성공 후에만 교체 ──────────
def _beat(idx, narration, seg_len, tts_path="/fake/beat.mp3"):
    return {"beat_idx": idx, "narration": narration, "role": "훅",
            "target_seconds": 3.0,
            "primary": {"video_id": "v1", "seg_id": f"s{idx}", "start": 0.0, "end": seg_len},
            "alternates": [], "tts_path": tts_path}


def test_conform_pass_rewrites_only_over_budget_beat(monkeypatch, tmp_path):
    """비트0: 예산 2.3s(2.0×1.15), 대사 5.0s → 콘폼. 비트1: 예산 4.6s, 대사 3.0s → 무변경."""
    beats = [_beat(0, "아주 긴 원래 문장", 2.0, tts_path="/fake/long.mp3"),
             _beat(1, "적당한 문장", 4.0, tts_path="/fake/short.mp3")]
    synth_calls = []
    durs = {"/fake/long.mp3": 5.0, "/fake/short.mp3": 3.0}   # 재TTS 결과(tmp 경로)는 2.2s
    monkeypatch.setattr(mp, "_probe_duration",
                        lambda p: durs.get(str(p).replace("\\", "/"), 2.2))
    monkeypatch.setattr(mp, "conform_narration",
                        lambda n, t: "짧게 줄인 문장")
    monkeypatch.setattr(mp, "synthesize_line",
                        lambda n, out, **k: synth_calls.append((n, str(out))))
    monkeypatch.setattr(mp.asr_check, "transcribe_words", lambda p: [{"w": "짧게"}])
    monkeypatch.setattr(mp.caption_sync, "phrase_durs_from_words",
                        lambda n, w, d: [d])
    mp._conform_beats(beats, tmp_path, voice=None)

    b0, b1 = beats
    assert b0["narration"] == "짧게 줄인 문장", "초과 비트가 리라이트되지 않았다"
    assert b0["conformed"] is True
    assert b0["tts_path"] == str(tmp_path / "beat_0.mp3"), "재TTS 경로가 비트에 반영 안 됨"
    assert b0["sync_gap"] == 0.0, "재TTS(2.2s) 후 예산(2.3s) 안인데 gap이 남았다"
    assert b0["cap_durs"] == [2.2], "콘폼 후 자막 타이밍 재동기 안 됨"
    assert b0["target_seconds"] == 1.5, "UI 표시 초 재계산 안 됨(화면 초≠실길이)"
    assert len(synth_calls) == 1, "초과 비트 1개만 재TTS해야 한다"
    assert b1["narration"] == "적당한 문장" and "conformed" not in b1
    assert b1["sync_gap"] == 0.0


def test_conform_pass_rewrite_failure_keeps_original_and_flag(monkeypatch, tmp_path):
    """리라이트 실패(None) → 원문 유지 + sync_gap 잔존(freeze 폴백의 근거 표시)."""
    beats = [_beat(0, "아주 긴 원래 문장", 2.0)]
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 5.0)
    monkeypatch.setattr(mp, "conform_narration", lambda n, t: None)
    def boom(*a, **k):
        raise AssertionError("리라이트 실패인데 재TTS를 불렀다")
    monkeypatch.setattr(mp, "synthesize_line", boom)
    mp._conform_beats(beats, tmp_path, voice=None)
    assert beats[0]["narration"] == "아주 긴 원래 문장"
    assert "conformed" not in beats[0]
    assert beats[0]["sync_gap"] == pytest.approx(2.7, abs=0.01)


def test_conform_pass_tts_exception_does_not_swap_narration(monkeypatch, tmp_path):
    """★재TTS 예외 → narration 미교체. 교체부터 하면 화면 문장≠음성(불일치 몰래 발생)."""
    beats = [_beat(0, "아주 긴 원래 문장", 2.0)]
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 5.0)
    monkeypatch.setattr(mp, "conform_narration", lambda n, t: "짧게 줄인 문장")
    def boom(*a, **k):
        raise RuntimeError("elevenlabs down")
    monkeypatch.setattr(mp, "synthesize_line", boom)
    mp._conform_beats(beats, tmp_path, voice=None)
    assert beats[0]["narration"] == "아주 긴 원래 문장", "TTS 실패인데 문장이 바뀌었다(문장/음성 불일치)"
    assert "conformed" not in beats[0]


def test_conform_pass_skips_small_gap(monkeypatch, tmp_path):
    """gap ≤ 0.8s(켄번즈 홀드로 자연 흡수 수준)는 제미니를 부르지 않는다 — 비용 가드."""
    beats = [_beat(0, "문장", 4.0)]   # 예산 4.6s
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 5.0)   # gap 0.4
    def boom(*a, **k):
        raise AssertionError("작은 gap인데 리라이트를 불렀다")
    monkeypatch.setattr(mp, "conform_narration", boom)
    mp._conform_beats(beats, tmp_path, voice=None)
    assert beats[0]["sync_gap"] == pytest.approx(0.4, abs=0.01)


# ── T4: 마지막 비트 여운 ───────────────────────────────────────
def test_runout_uses_real_frames_when_segment_has_slack():
    plan = [{"video_id": "v1", "start": 2.0, "src_dur": 3.0, "out_dur": 3.0}]
    segs = [{"video_id": "v1", "start": 0.0, "end": 10.0}]
    _extend_last_clip_for_runout(plan, segs, 1.0)
    c = plan[-1]
    assert c["src_dur"] == 4.0, "여유가 충분한데 실프레임으로 안 늘렸다"
    assert c["out_dur"] == 4.0, "1배속 여운이어야 한다(슬로모 금지)"


def test_runout_partial_slack_rest_absorbed_by_freeze_machinery():
    plan = [{"video_id": "v1", "start": 2.0, "src_dur": 3.0, "out_dur": 3.0}]
    segs = [{"video_id": "v1", "start": 0.0, "end": 5.4}]   # slack 0.4
    _extend_last_clip_for_runout(plan, segs, 1.0)
    c = plan[-1]
    assert c["src_dur"] == pytest.approx(3.4), "여유 0.4s만큼은 실프레임"
    assert c["out_dur"] == pytest.approx(4.0), "부족분 0.6s는 out_dur로(slowmo/freeze 기계가 흡수)"


def test_runout_no_slack_extends_out_only_and_empty_plan_safe():
    plan = [{"video_id": "v1", "start": 2.0, "src_dur": 3.0, "out_dur": 3.0}]
    segs = [{"video_id": "v1", "start": 0.0, "end": 5.0}]   # slack 0
    _extend_last_clip_for_runout(plan, segs, 1.0)
    assert plan[-1]["src_dur"] == 3.0 and plan[-1]["out_dur"] == 4.0
    assert _extend_last_clip_for_runout([], segs, 1.0) == []   # 빈 plan 무해
    assert _LAST_RUNOUT == 1.0


# ── T1: 편집안 화면 배지(소스 앵커) ─────────────────────────────
def test_review_body_shows_conform_badge_and_gap_warning():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index("function _renderMixReviewBody(")
    body = src[i:src.index("async function _restoreMixContext", i)]
    assert "길이 맞춤" in body, "콘폼 배지가 없다 — 대본이 몰래 바뀐 것처럼 보인다(스펙 리스크)"
    assert "sync_gap" in body, "sync_gap 경고가 없다 — 홀드가 생겨도 사장님이 이유를 모른다"
