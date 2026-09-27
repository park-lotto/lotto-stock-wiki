# -*- coding: utf-8 -*-
"""컷 지도(final_clip_pairs)는 렌더(_render_mix)와 같은 프레임 배치 — video_assemble.beat_frames 한 곳(2026-09-27)."""
import inspect
from shopping_shorts import mix_pipeline as mp
from shopping_shorts import video_assemble as va


def test_beat_frames_matches_render_rule():
    f0, nfr, cum = va.beat_frames(0.0, 1.013)
    assert (f0, nfr) == (0, 30) and abs(cum - 1.013) < 1e-9            # 1.013초 → 30프레임(반올림), 올림 31이 아니다
    f1, n1, cum = va.beat_frames(cum, 1.013)
    assert (f1, n1) == (30, 31) and f1 + n1 == round(cum * 30)          # 누적 경계 차 → 쌓이지 않는다


def test_final_clip_pairs_on_frame_grid_and_render_layout(monkeypatch):
    plan = {"beats": [
        {"beat_idx": 0, "target_seconds": 1.013, "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 1.1}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 1.013, "primary": {"video_id": "s0", "seg_id": "b", "start": 5.0, "end": 6.1}, "alternates": []}]}
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda b, tts_dur, src_durs, runout=0.0: [
        {"video_id": "s0", "start": b["primary"]["start"], "out_dur": 0.4}, {"video_id": "s0", "start": b["primary"]["start"] + 0.5, "out_dur": 0.613}])
    cuts = mp.final_clip_pairs(plan, {}, {"s0": 30.0})
    assert [round(c["fin"] * 30) for c in cuts] == [0, 12, 30, 42]                  # 칸0 30프레임(0,12), 칸1 30→(30,42)
    assert all(abs(c["fin"] * 30 - round(c["fin"] * 30)) < 1e-6 for c in cuts)     # 전부 프레임 격자 위
    assert [round(c["dur"] * 30) for c in cuts] == [12, 18, 12, 19]                 # 마지막 컷이 칸 나머지를 흡수
    assert abs(sum(c["dur"] for c in cuts) * 30 - 61) < 1e-6                        # 총 61프레임 = round(2.026*30)


def test_render_uses_beat_frames_not_its_own_formula():
    src = inspect.getsource(va._render_mix)
    assert "beat_frames(" in src and "int(round(_cum_t * 30)) - _f0" not in src
