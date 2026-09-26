# -*- coding: utf-8 -*-
"""4단계 청소가 끝나면 정본(clean_base.json)이 남고, 파생 사본에선 훅 시작점을 안 옮긴다."""
from pathlib import Path

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import video_assemble as va
from shopping_shorts import clean_base as cb


class _Store:
    def __init__(self): self.updates = []
    def update_mix_job(self, job_id, **kw): self.updates.append(kw)


def _job():
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "tts_path": None,
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []}]}
    return {"edit_plan": plan, "subtitle_removal": 1, "customer_id": 0}


def _patch(monkeypatch, fake_cuts):
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: 0)
    monkeypatch.setattr(mp, "_vmake_clean",
                        lambda src, keys, out, tier=None, **k: (Path(out).write_bytes(b"x" * 4096), out)[1])
    monkeypatch.setattr(mp, "final_clip_pairs", lambda plan, tts, durs: fake_cuts)
    monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: {"s0": 30.0})


def test_final_clean_fn_saves_base(tmp_path, monkeypatch):
    job = _job()
    fake_cuts = [{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}]
    _patch(monkeypatch, fake_cuts)
    fn = mp._final_clean_fn(_Store(), job, "job1", tmp_path, ["k"], 0)
    mix_raw = tmp_path / "mix_raw.mp4"; mix_raw.write_bytes(b"y" * 4096)
    out = fn(str(mix_raw))
    base = cb.load_base(tmp_path)
    # 전체 지우기면 모든 컷이 cleaned=True(장면 골라 지우기 2026-09-26의 표식) — 고른 장면 정보는 없다
    assert base is not None and base["path"] == out and base["cuts"] == [dict(c, cleaned=True) for c in fake_cuts]
    assert "partial" not in base and "skip_beats" not in base
    assert base["beat_keys"] == {"0": [["s0", 1.0, 3.0]]}


def test_reuse_branch_rewrites_base_when_sig_differs(tmp_path, monkeypatch):
    """등급 변경(basic→pro)은 새 정본이다 — 재사용 분기에서 서명이 다르면 정본을 다시 쓴다."""
    job = _job()
    fake_cuts = [{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}]
    _patch(monkeypatch, fake_cuts)
    sig = mp._clean_sig(job)
    (tmp_path / f"final_clean_{sig}.mp4").write_bytes(b"x" * 4096)        # 이미 청소된 파일
    (tmp_path / "final_clean_OLD.mp4").write_bytes(b"x" * 4096)
    cb.save_base(tmp_path, sig="OLD", path=str(tmp_path / "final_clean_OLD.mp4"), plan=job["edit_plan"], cuts=[])
    fn = mp._final_clean_fn(_Store(), job, "job1", tmp_path, ["k"], 0)
    out = fn(str(tmp_path / "mix_raw.mp4"))
    assert out.endswith(f"final_clean_{sig}.mp4")
    assert cb.load_base(tmp_path)["sig"] == sig


def test_hook_inpoint_skipped_for_clean_base_plan(tmp_path, monkeypatch):
    import shopping_shorts.scene_cut as sc
    called = []
    monkeypatch.setattr(sc, "peak_time_in_window", lambda *a, **k: called.append(1) or 5.0)
    plan = {"clean_base": True, "beats": [{"beat_idx": 0, "primary": {"video_id": "clean", "start": 0.0, "end": 2.0}}]}
    va._apply_hook_inpoint(plan, {"clean": str(tmp_path / "c.mp4")}, tmp_path)
    assert called == []
    assert plan["beats"][0]["primary"]["start"] == 0.0
