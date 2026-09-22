# -*- coding: utf-8 -*-
"""정본이 있으면 렌더는 청소본을 소스로 조립하고 VMake를 안 부른다(재과금 0)."""
from pathlib import Path
import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import clean_base as cb


class _Store:
    def __init__(self, job): self.job = job; self.updates = []
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.updates.append(kw); self.job.update(kw)
    def get_setting(self, k, d=None): return "1" if k == "clean_base_enabled" else d


def _setup(work):
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "narration": "a", "tts_path": None,
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []}]}
    job = {"job_id": "j", "edit_plan": plan, "urls": ["u"], "subtitle_removal": 1, "customer_id": 0, "clean_status": "ready"}
    work.mkdir(parents=True, exist_ok=True)
    (work / "s0").mkdir(); (work / "s0" / "v.mp4").write_bytes(b"v" * 4096)
    (work / "final_clean_abc.mp4").write_bytes(b"c" * 4096)
    cb.save_base(work, sig="abc", path=str(work / "final_clean_abc.mp4"), plan=plan,
                 cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    return job


def test_render_inputs_use_clean_base(tmp_path, monkeypatch):
    job = _setup(tmp_path)
    job["edit_plan"]["beats"][0]["caption_lines"] = ["a", "b"]      # 꾸미기 편집
    monkeypatch.setattr(mp, "_vmake_clean", lambda *a, **k: pytest.fail("VMake가 불렸다"))
    plan_used, paths, base = mp.render_inputs_for(_Store(job), job, "j", tmp_path, ["k"], 0)
    assert base is not None and paths == {"clean": str(tmp_path / "final_clean_abc.mp4")}
    assert plan_used["beats"][0]["scene_override"][0]["video_id"] == "clean"
    assert plan_used["clean_base"] is True
    assert job["edit_plan"].get("clean_base") is None              # DB 원본은 그대로


def test_render_inputs_fall_back_when_switch_off(tmp_path):
    job = _setup(tmp_path)
    class _Off(_Store):
        def get_setting(self, k, d=None): return ""
    plan_used, paths, base = mp.render_inputs_for(_Off(job), job, "j", tmp_path, ["k"], 0)
    assert base is None and "s0" in paths and plan_used is job["edit_plan"]


def test_render_inputs_run_incremental_for_changed_beat(tmp_path, monkeypatch):
    job = _setup(tmp_path)
    job["edit_plan"]["beats"][0]["scene_override"] = [{"video_id": "s0", "seg_id": "s0-1", "start": 20.0, "end": 22.0}]
    seen = {}
    def _inc(store, job, job_id, work, keys, cid, base, plan, uncovered, extend):
        seen["uncovered"] = uncovered
        (Path(work) / "cb0_0.mp4").write_bytes(b"q" * 2048)
        return cb.add_extra(work, base, vid="cb0_0", path=str(Path(work) / "cb0_0.mp4"), beat_idx=0,
                            material_key=cb.beat_material_key(plan["beats"][0]), seconds=2.0)
    monkeypatch.setattr(mp, "incremental_clean", _inc)
    plan_used, paths, base = mp.render_inputs_for(_Store(job), job, "j", tmp_path, ["k"], 0)
    assert seen["uncovered"] == [0]
    assert plan_used["beats"][0]["scene_override"][0]["video_id"] == "cb0_0" and "cb0_0" in paths


def test_preview_does_not_clean_changed_beat(tmp_path, monkeypatch):
    job = _setup(tmp_path)
    job["edit_plan"]["beats"][0]["scene_override"] = [{"video_id": "s0", "seg_id": "s0-1", "start": 20.0, "end": 22.0}]
    monkeypatch.setattr(mp, "incremental_clean", lambda *a, **k: pytest.fail("미리보기가 돈을 썼다"))
    plan_used, paths, base = mp.render_inputs_for(_Store(job), job, "j", tmp_path, [], 0, allow_clean=False)
    assert base is not None and "s0" in paths and "clean" in paths
    assert plan_used["beats"][0]["scene_override"][0]["video_id"] == "s0"


def test_run_render_passes_clean_fn_none_with_base(tmp_path, monkeypatch):
    work = tmp_path / "j"
    job = _setup(work)
    store = _Store(job)
    monkeypatch.setattr(mp, "Store", lambda db: store)
    monkeypatch.setattr(mp, "_job_customer_id", lambda db, jid: 0)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp.pron_corrections, "load", lambda s: {})
    monkeypatch.setattr(mp, "_vmake_keys", lambda s, c: ["k"])
    monkeypatch.setattr(mp, "_vmake_clean", lambda *a, **k: pytest.fail("VMake가 불렸다"))
    monkeypatch.setattr(mp, "resolve_deco_media", lambda d, w: {})
    monkeypatch.setattr(mp, "_template_layer", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_scene_mask_layers", lambda *a, **k: [])
    monkeypatch.setattr(mp, "_resolve_cutaway_paths", lambda *a, **k: {})
    monkeypatch.setattr(mp, "_resolve_sfx_paths", lambda *a, **k: {})
    monkeypatch.setattr(mp, "ensure_faststart", lambda p: None)
    got = {}
    def _assemble(plan, tts, paths, out, clean_fn=None, **kw):
        got["clean_fn"] = clean_fn; got["paths"] = paths; got["plan"] = plan
        Path(out).write_bytes(b"f" * 4096); return out
    monkeypatch.setattr(mp, "assemble", _assemble)
    mp.run_render("j", "db", tmp_path)
    assert got["clean_fn"] is None and got["paths"] == {"clean": str(work / "final_clean_abc.mp4")}
    assert got["plan"]["clean_base"] is True
    assert store.job.get("status") == "done", store.job.get("error")
    # DB에 저장된 편성표는 파생 사본이 아니다
    assert all("clean_base" not in (u.get("edit_plan") or {}) for u in store.updates)
