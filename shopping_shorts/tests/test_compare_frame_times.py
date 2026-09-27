# -*- coding: utf-8 -*-
"""전/후 비교 좌표는 프레임 번호로(2026-09-27) — 청소본 시각은 n/30 격자, 원본은 같은 프레임 수만큼."""
import pytest
from shopping_shorts import mix_pipeline as mp


def test_times_are_frame_aligned_and_same_offset():
    c = {"src": 7.7, "fin": 2.66, "dur": 1.05}
    s, f = mp.compare_frame_times(c, 0.5)
    ff = (f - 0.0005) * 30
    assert abs(ff - round(ff)) < 1e-6                       # 청소본 쪽은 정확히 프레임 격자
    k = round(ff) - round(2.66 * 30)
    assert 0 <= k < 31 and abs((s - 0.0005) - (7.7 + k / 30)) < 1e-6   # 원본도 같은 프레임 수 k만큼
    s0, f0 = mp.compare_frame_times(c, 0.0); s1, f1 = mp.compare_frame_times(c, 0.999)
    assert round((f0 - 0.0005) * 30) == round(2.66 * 30) and f1 < 2.66 + 1.05 + 0.02   # 컷 안에 머문다


def test_clean_thumb_uses_frame_times(monkeypatch):
    from shopping_shorts import app as A

    class _Boom(Exception):
        pass

    class _S:
        def __init__(self, *a): pass
        def get_mix_job(self, j): return {"job_id": j, "clean_status": "ready", "clean_sources": None, "edit_plan": {"beats": []}}
    monkeypatch.setattr(A, "Store", _S)
    monkeypatch.setattr(A.mix_pipeline, "clean_compare_clips", lambda job, work: {
        "clips": [{"ci": 0, "si": 0, "video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 1.0, "cleaned": True}],
        "clean_path": None, "stale": False, "plan_used": "current"})
    monkeypatch.setattr(A.mix_pipeline, "compare_frame_times", lambda c, pos: (_ for _ in ()).throw(_Boom()))
    with pytest.raises(_Boom):
        A.api_produce_mix_clean_thumb("j1", kind="original", si=0, pos=0.5, ci=0)
