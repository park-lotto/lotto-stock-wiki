"""자막 타임스탬프 드리프트 3종 회귀 (2026-08-06 실측 재현).

사장님 제보 "자막 타임스탬프가 약간씩 안 맞는다"의 원인 3개를 각각 잠근다.
전부 실측(실 ffmpeg 또는 수치 재현)으로 확인된 것이지 추정이 아니다.

① 리드인 버림    — 말 시작 전 무음을 버려 자막이 먼저 뜬다(실측 -0.50s).
② rescale 선형가정 — 속도감 모드가 내부 무음을 잘라 선형사상이 깨진다(실측 +0.28s 누적).
③ 트림 후 미갱신  — 수동 트림 뒤 cap_durs가 옛 모양 그대로 남는다.
"""
import shutil
import subprocess

import pytest

import shopping_shorts.caption_sync as cs
from shopping_shorts.video_assemble import _caption_segments


def _w(word, s, e):
    return {"word": word, "start": s, "end": e}


def _render_starts(durs, lead_in=0.0):
    """렌더러(_caption_drawtexts)가 실제로 찍는 자막 시작 시각 재현."""
    t, out = lead_in, []
    for d in durs:
        out.append(t)
        t += d
    return out


# ───────────────────────── ① 리드인 ─────────────────────────

def test_leadin_is_reported_not_discarded():
    """말이 0.5초 뒤에 시작하면 cap_lead가 0.5로 나와야 한다.
    예전엔 이 값을 버리고 durs 합만 total_dur로 정규화해 자막이 0.5초 먼저 떴다."""
    narr = "오늘 소개할 제품은 이겁니다 진짜 놀랍습니다 한번 보세요"
    starts = [0.5, 0.9, 1.4, 2.0, 2.6, 3.2, 3.8, 4.5, 5.2]
    words = [_w(t, s, s + 0.35) for t, s in zip(narr.split(), starts)]

    res = cs.phrase_durs_from_words(narr, words, 6.0)
    assert res is not None
    durs, lead = res.durs, res.lead_in
    assert lead == pytest.approx(0.5, abs=0.01), f"리드인 유실: {lead}"

    # 렌더 시작시각이 실제 발화 시각과 일치해야 한다.
    segs = _caption_segments(narr)
    w_at, truth = 0, []
    for s in segs:
        truth.append(starts[w_at])
        w_at += len(s.split())

    for i, (r, tr) in enumerate(zip(_render_starts(durs, lead), truth)):
        assert abs(r - tr) < 0.06, f"구절{i+1} 드리프트 {r - tr:+.2f}s"


def test_leadin_zero_when_speech_starts_immediately():
    """말이 0초에 시작하면 리드인 0 — 기존 동작과 동일(회귀0)."""
    narr = "귤은 손으로 까요 이제 시작합니다"
    words = [_w("귤은", 0.0, 0.4), _w("손으로", 0.4, 0.9), _w("까요", 0.9, 1.4),
             _w("이제", 2.0, 2.3), _w("시작합니다", 2.3, 3.0)]
    res = cs.phrase_durs_from_words(narr, words, 3.0)
    assert res.lead_in == pytest.approx(0.0, abs=1e-6)


def test_durs_no_longer_stretched_to_fill_total():
    """durs는 실제 발화 간격 그대로여야 한다(합이 total_dur보다 작을 수 있다).
    예전의 `d * total_dur / tot` 정규화는 오프셋 오차를 전 구절에 퍼뜨렸다."""
    narr = "이거 진짜 완전 대박이라서 다들 놀랐어요"
    words = [_w("이거", 1.0, 1.3), _w("진짜", 1.3, 1.6), _w("완전", 1.6, 2.0),
             _w("대박이라서", 2.0, 2.9), _w("다들", 3.0, 3.2), _w("놀랐어요", 3.2, 3.5)]
    res = cs.phrase_durs_from_words(narr, words, 5.0)
    assert res.lead_in == pytest.approx(1.0, abs=0.01)
    # 첫 구절은 실제 발화 간격(1.0→3.0 = 2.0초) 그대로여야 한다. 예전 정규화는 리드인
    # 1.0초까지 구절에 비례배분해 이 값을 늘려버렸다(2.0 → 2.5).
    assert res.durs[0] == pytest.approx(2.0, abs=0.05), \
        f"여전히 늘림: {res.durs[0]}"
    # 리드인 + durs 합 = total_dur (마지막 구절은 오디오 끝까지 유지 = 의도된 동작).
    assert res.lead_in + sum(res.durs) == pytest.approx(5.0, abs=0.05)


# ───────────────────────── ② rescale ─────────────────────────

def test_rescale_piecewise_beats_linear_on_internal_cuts():
    """내부 무음을 잘라낸 경우, 조각별 보정이 선형사상보다 정확해야 한다.

    원본: [무음.4] 말(.8) [무음.9] 말(.8) [무음.9] 말(.8)  = 4.6s
    잘림: 앞 .4 / 내부 .9 두 곳(0.3s 초과분) 제거 → 실제 발화 시작 [0, 1.17, 2.29]
    """
    from shopping_shorts import tts_timestamps as tt

    words = [_w("가", 0.4, 1.2), _w("나", 2.1, 2.9), _w("다", 3.8, 4.6)]
    # ★내부 무음은 stop_duration(0.3s)만 남기고 줄어든다 — 통째로 사라지지 않는다.
    # measure_removed_spans가 실제로 내주는 값(실 ffmpeg 실측 확인).
    removed = [(0.0, 0.4), (1.2, 1.8), (2.9, 3.5)]
    truth = [0.0, 1.169, 2.288]      # 후처리된 오디오에서 실측한 발화 시작

    out = tt.rescale(words, 3.167, removed=removed)
    for i, (w, tr) in enumerate(zip(out, truth)):
        assert abs(w["start"] - tr) < 0.06, \
            f"단어{i+1} 드리프트 {w['start'] - tr:+.3f}s"

    # 옛 선형사상보다 확실히 정확해야 한다(실측 0.276s → 0.037s).
    lin = tt.rescale(words, 3.167)
    err_new = max(abs(w["start"] - t) for w, t in zip(out, truth))
    err_old = max(abs(w["start"] - t) for w, t in zip(lin, truth))
    assert err_new < err_old / 3, f"개선 부족: {err_new:.3f} vs {err_old:.3f}"


def test_rescale_without_removed_keeps_legacy_linear():
    """removed 미제공이면 예전 선형 경로 그대로(회귀0)."""
    from shopping_shorts import tts_timestamps as tt

    words = [_w("가", 1.0, 1.5), _w("나", 2.0, 3.0)]
    out = tt.rescale(words, 2.0)
    assert out[0]["start"] == pytest.approx(0.0)
    assert out[-1]["end"] == pytest.approx(2.0)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")
def test_pace_mode_removed_spans_measured_real_ffmpeg(tmp_path):
    """실 ffmpeg: pace_mode가 잘라낸 구간을 measure_removed_spans가 잡아낸다."""
    from shopping_shorts import audio_post

    raw = tmp_path / "raw.wav"
    parts = [("s", 0.4), ("t", 0.8), ("s", 0.9), ("t", 0.8), ("s", 0.9), ("t", 0.8)]
    cmd = ["ffmpeg", "-y"]
    filt = ""
    for i, (kind, d) in enumerate(parts):
        src = (f"sine=frequency=300:duration={d}" if kind == "t"
               else f"anullsrc=r=44100:cl=mono:d={d}")
        cmd += ["-f", "lavfi", "-t", str(d), "-i", src]
        filt += f"[{i}:a]"
    filt += f"concat=n={len(parts)}:v=0:a=1[a]"
    cmd += ["-filter_complex", filt, "-map", "[a]", "-ar", "44100", str(raw)]
    subprocess.run(cmd, capture_output=True, check=True)

    spans = audio_post.measure_removed_spans(str(raw))
    # 앞 0.4초 + 내부 0.9초 두 곳이 잡혀야 한다(끝 무음은 없음).
    assert len(spans) >= 3, f"구간 감지 실패: {spans}"
    assert spans[0][0] == pytest.approx(0.0, abs=0.05)
    total_removed = sum(e - s for s, e in spans)
    assert 1.5 < total_removed < 2.5, f"제거량 이상: {total_removed}"


# ───────────────────────── ③ 트림 후 갱신 ─────────────────────────

def test_cap_durs_invalidated_on_head_trim():
    """head_trim이 걸리면 저장된 cap_durs를 그대로 쓰면 안 된다 —
    리드인/구절 시작이 트림량만큼 앞당겨져야 한다."""
    import shopping_shorts.video_assemble as va

    beat = {"beat_idx": 0, "narration": "귤은 까요",
            "cap_durs": [0.9, 0.6], "cap_lead": 0.5, "head_trim": 0.3}
    lead, durs = va._adjust_caps_for_trim(beat)
    assert lead == pytest.approx(0.2, abs=1e-6), "트림만큼 리드인이 줄어야"
    assert durs == [0.9, 0.6]


def test_cap_durs_trim_clamps_into_first_segment():
    """트림이 리드인보다 크면 첫 구절을 파고든다(음수 리드인 금지)."""
    import shopping_shorts.video_assemble as va

    beat = {"beat_idx": 0, "narration": "귤은 까요",
            "cap_durs": [0.9, 0.6], "cap_lead": 0.2, "head_trim": 0.5}
    lead, durs = va._adjust_caps_for_trim(beat)
    assert lead == 0.0
    assert durs[0] == pytest.approx(0.6, abs=1e-6), "남은 0.3을 첫 구절에서 깎아야"
    assert durs[1] == pytest.approx(0.6, abs=1e-6)


def test_no_trim_is_passthrough():
    """트림 0이면 그대로(회귀0)."""
    import shopping_shorts.video_assemble as va

    beat = {"cap_durs": [0.9, 0.6], "cap_lead": 0.4}
    lead, durs = va._adjust_caps_for_trim(beat)
    assert lead == pytest.approx(0.4)
    assert durs == [0.9, 0.6]
