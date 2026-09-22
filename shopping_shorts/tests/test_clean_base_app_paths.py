# -*- coding: utf-8 -*-
"""정본이 있으면 화면·내보내기도 그 청소본을 본다 — 서명이 달라져도 stale 아님."""
import json
from pathlib import Path

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import clean_base as cb


def _job_with_base(tmp_path):
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "narration": "a",
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []}]}
    job = {"edit_plan": json.loads(json.dumps(plan)), "urls": ["u"], "subtitle_removal": 1, "customer_id": 0, "clean_status": "ready"}
    (tmp_path / "final_clean_old.mp4").write_bytes(b"c" * 4096)
    cb.save_base(tmp_path, sig="old", path=str(tmp_path / "final_clean_old.mp4"), plan=plan,
                 cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    (tmp_path / "final_clean_old.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    job["edit_plan"]["beats"][0]["caption_lines"] = ["a", "b"]     # 서명이 바뀐다
    return job


def test_clean_final_path_for_plan_returns_base_when_on(tmp_path, monkeypatch):
    job = _job_with_base(tmp_path)
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid: True)
    assert str(mp.clean_final_path_for_plan(job, tmp_path)).endswith("final_clean_old.mp4")
    assert mp.clean_final_matches_plan(job, tmp_path) is True


def test_clean_final_path_for_plan_unchanged_when_off(tmp_path, monkeypatch):
    job = _job_with_base(tmp_path)
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid: False)
    assert mp.clean_final_path_for_plan(job, tmp_path) is None       # 종전: 서명이 다르면 None


def test_compare_clips_not_stale_and_uses_snapshot_with_base(tmp_path, monkeypatch):
    job = _job_with_base(tmp_path)
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid: True)
    monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: {"s0": 30.0})
    out = mp.clean_compare_clips(job, tmp_path)
    assert out["stale"] is False and out["clean_path"].endswith("final_clean_old.mp4")
    assert out["plan_used"] == "snapshot"


def test_app_final_cuts_use_clean_coords(tmp_path, monkeypatch):
    from shopping_shorts import app as A
    job = _job_with_base(tmp_path)
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid: True)
    monkeypatch.setattr(A, "Store", lambda db: object())
    monkeypatch.setattr(A.frame_extract, "_probe_duration", lambda p: 2.0)
    cuts = A._final_cuts(job, tmp_path)
    assert cuts and cuts[0]["video_id"] == "clean" and cuts[0]["src"] == 0.0


def test_app_clean_frame_src_points_into_clean_file(tmp_path, monkeypatch):
    from shopping_shorts import app as A
    job = _job_with_base(tmp_path)
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid: True)
    monkeypatch.setattr(A, "Store", lambda db: object())
    monkeypatch.setattr(A.frame_extract, "_probe_duration", lambda p: 2.0)
    srcs, cvp, ratio, tag, fresh = A._clean_frame_src(job, tmp_path, 0)
    assert cvp.endswith("final_clean_old.mp4") and fresh is True and tag == "_cb_old"
    assert abs(ratio - 0.5) < 1e-6          # 컷 0.0~2.0의 가운데 = 1.0초 / 2.0초
