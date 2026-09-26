# -*- coding: utf-8 -*-
"""바뀐 장면·큰 늘림만 원본에서 잘라 **1콜**로 지우고 정본 extras에 붙인다."""
from pathlib import Path
import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import clean_base as cb


class _Store:
    def update_mix_job(self, *a, **k): pass


def _job_and_base(tmp_path):
    plan = {"beats": [
        {"beat_idx": 0, "target_seconds": 2.0, "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 2.0, "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 5.0, "end": 7.0}, "alternates": []}]}
    job = {"edit_plan": plan, "urls": ["u0", "u1"], "customer_id": 0, "clean_tier": "basic"}
    for i in ("s0", "s1"):
        (tmp_path / i).mkdir(); (tmp_path / i / "v.mp4").write_bytes(b"v" * 4096)
    (tmp_path / "final_clean_abc.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="abc", path=str(tmp_path / "final_clean_abc.mp4"), plan=plan,
                        cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0},
                              {"video_id": "s1", "beat_idx": 1, "src": 5.0, "fin": 2.0, "dur": 2.0}])
    return job, base


def _fake_cut(src, ss, dur, dst):
    Path(dst).write_bytes(b"p" * 2048); return str(dst)


def test_changed_beat_cleaned_in_one_call_and_added_to_extras(tmp_path, monkeypatch):
    job, base = _job_and_base(tmp_path)
    plan = job["edit_plan"]
    plan["beats"][0]["scene_override"] = [{"video_id": "s1", "seg_id": "s1-9", "start": 10.0, "end": 12.5}]
    calls, charged = [], []
    monkeypatch.setattr(mp, "_cut_piece", _fake_cut)
    tiers = []
    def _joined(items, keys, work, tag="", tier=None):
        calls.append([v for v, _ in items]); tiers.append(tier)
        out = {}
        for v, _ in items:
            p = Path(work) / f"{v}_clean.mp4"; p.write_bytes(b"q" * 2048); out[v] = str(p)
        return out, {}
    monkeypatch.setattr(mp, "_clean_joined", _joined)
    monkeypatch.setattr(mp, "_charge_clean", lambda s, c, n: charged.append(n) or 0)
    base2 = mp.incremental_clean(_Store(), job, "j", tmp_path, ["k"], 0, base, plan, uncovered=[0], extend=[])
    assert calls == [["cb0_0"]] and charged == [1]
    assert tiers == ["basic"]      # ★등급을 넘긴다 — 빠지면 고급 job의 바뀐 장면만 기본으로 지워진다(2026-09-26)
    assert base2["extras"]["cb0_0"]["seconds"] == pytest.approx(2.5)
    assert cb.coverage(plan, cb.load_base(tmp_path)) == {0: "covered", 1: "covered"}


def test_extend_request_cleans_tail_piece(tmp_path, monkeypatch):
    job, base = _job_and_base(tmp_path)
    plan = job["edit_plan"]
    monkeypatch.setattr(mp, "_cut_piece", _fake_cut)
    def _joined(items, keys, work, tag="", tier=None):
        out = {}
        for v, _ in items:
            p = Path(work) / f"{v}_clean.mp4"; p.write_bytes(b"q" * 2048); out[v] = str(p)
        return out, {}
    monkeypatch.setattr(mp, "_clean_joined", _joined)
    monkeypatch.setattr(mp, "_charge_clean", lambda s, c, n: 0)
    ext = [{"beat_idx": 1, "video_id": "s1", "start": 7.0, "end": 8.2, "need": 1.0}]
    base2 = mp.incremental_clean(_Store(), job, "j", tmp_path, ["k"], 0, base, plan, uncovered=[], extend=ext)
    assert base2["extras"]["cbx1"]["seconds"] == pytest.approx(1.2)
    assert base2["extras"]["cbx1"]["beat_idx"] == 1 and base2["extras"]["cbx1"]["key"] == [["s1", 5.0, 7.0]]


def test_failure_refunds_and_raises(tmp_path, monkeypatch):
    job, base = _job_and_base(tmp_path)
    plan = job["edit_plan"]
    plan["beats"][0]["scene_override"] = [{"video_id": "s1", "seg_id": "s1-9", "start": 10.0, "end": 12.5}]
    monkeypatch.setattr(mp, "_cut_piece", _fake_cut)
    def _boom(*a, **k): raise RuntimeError("vendor down")
    monkeypatch.setattr(mp, "_clean_joined", _boom)
    refunded = []
    monkeypatch.setattr(mp, "_charge_clean", lambda s, c, n: 7)
    monkeypatch.setattr(mp, "_refund_clean", lambda s, c, amt: refunded.append(amt))
    with pytest.raises(RuntimeError):
        mp.incremental_clean(_Store(), job, "j", tmp_path, ["k"], 0, base, plan, uncovered=[0], extend=[])
    assert refunded == [7]


def test_nothing_to_do_returns_base_without_charge(tmp_path, monkeypatch):
    job, base = _job_and_base(tmp_path)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a: pytest.fail("과금이 났다"))
    assert mp.incremental_clean(_Store(), job, "j", tmp_path, ["k"], 0, base, job["edit_plan"], uncovered=[], extend=[]) is base
