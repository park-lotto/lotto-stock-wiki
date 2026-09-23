# -*- coding: utf-8 -*-
"""AI 장면 생성(Veo) — 순수 부분(길이·베이스 컷·프롬프트)과 워커 흐름(Vertex는 가짜)."""
import json
from pathlib import Path

import pytest

from shopping_shorts import ai_scene as ai


# ── 순수 부분 ──────────────────────────────────────────────────────────

def test_pick_seconds_boundaries():
    assert [ai.pick_seconds(x) for x in (0, 2.9, 4.0, 4.1, 6.0, 6.01, 12)] == [4, 4, 4, 6, 6, 8, 8]


EXTRACT = {
    "s0": {"segments": [
        {"seg_id": "a-0", "start": 0.0, "end": 2.5, "scene_desc": "아기가 문어 인형에 감싸여 있는 모습"},
        {"seg_id": "a-1", "start": 2.5, "end": 5.4, "scene_desc": "손으로 인형 다리를 눌러보는 모습"}]},
    "s2": {"segments": [
        {"seg_id": "b-2", "start": 6.77, "end": 8.07, "scene_desc": "문어 인형의 앞면 모습이 정면으로 클로즈업됨."},
        {"seg_id": "b-3", "start": 8.07, "end": 8.5, "scene_desc": "인형 정면"}]},
}
BEAT = {"beat_idx": 1, "target_seconds": 3.0, "narration": "세탁기 돌려도 변형 없는 소재",
        "primary": {"video_id": "s0", "seg_id": "a-0", "start": 0.0, "end": 2.5}, "alternates": []}


def test_pick_base_material_prefers_product_only_longest_cut():
    vid, t = ai.pick_base_material(BEAT, EXTRACT)
    assert (vid, t) == ("s2", 7.42)          # 아기·손 있는 컷 제외, 제품만 컷 중 가장 긴 것의 가운데


def test_pick_base_material_falls_back_to_primary():
    vid, t = ai.pick_base_material(BEAT, {"s0": {"segments": [EXTRACT["s0"]["segments"][0]]}})
    assert (vid, t) == ("s0", 0.2)
    vid, t = ai.pick_base_material(BEAT, EXTRACT, product_only=False)
    assert (vid, t) == ("s0", 0.2)


def test_build_prompt_has_frame0_steps_and_negative():
    motion = {"subject_desc_en": "A pale-yellow plush octopus facing the camera.",
              "motion_steps_en": ["A hand sets it on a towel.", "The hand pats the head twice.", "Slow push-in; it stays unchanged."],
              "forbid_extra": ["no washing machine"]}
    p = ai.build_prompt(motion, 6, "natural")
    assert p.startswith("INPUT IMAGE = FRAME 0: A pale-yellow plush octopus")
    assert "CONTINUOUS SINGLE SHOT" in p and "6.0 seconds" in p
    assert "0.0-2.0s  A hand sets it on a towel." in p and "4.0-6.0s  Slow push-in" in p
    assert "NEGATIVE: no text" in p and "no washing machine" in p
    assert "quick dolly-in" not in p and "REALISM: photorealistic" in p and "no speed lines" in p
    assert "quick dolly-in" in ai.build_prompt(motion, 4, "impact")


def test_motion_request_uses_model_json_or_defaults():
    got = ai.motion_request("아기 재우기 힘들면", "문어 인형", "natural",
                            call=lambda prompt, schema: {"subject_desc_en": "Yellow plush octopus.",
                                                         "motion_steps_en": ["a", "b", "c"], "forbid_extra": ["no baby"]})
    assert got == {"subject_desc_en": "Yellow plush octopus.", "motion_steps_en": ["a", "b", "c"], "forbid_extra": ["no baby"]}
    dflt = ai.motion_request("x", "문어 인형", "impact", call=lambda p, s: None)
    assert len(dflt["motion_steps_en"]) == 3 and "push-in" in dflt["motion_steps_en"][0] and dflt["subject_desc_en"] == "문어 인형"


# ── 워커 흐름(가짜 Vertex) ────────────────────────────────────────────

class _Store:
    def __init__(self, job):
        self.job = job; self.assets = []
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.job.update(kw)
    def add_scene_asset(self, asset, customer_id=0):
        self.assets.append((asset, customer_id)); return 77


def _job(work):
    plan = {"beats": [dict(BEAT, beat_idx=0), dict(BEAT, beat_idx=1)]}
    (work / "s0").mkdir(parents=True); (work / "s0" / "v.mp4").write_bytes(b"v" * 4096)
    (work / "s2").mkdir(); (work / "s2" / "v.mp4").write_bytes(b"v" * 4096)
    return {"job_id": "j", "edit_plan": plan, "urls": ["u0", "u1", "u2"], "extract": EXTRACT,
            "customer_id": 0, "status": "ready_for_review", "product": {"name": "문어 인형"}}


def _patch_common(monkeypatch, tmp_path, store):
    monkeypatch.setattr("shopping_shorts.store.Store", lambda db: store)
    monkeypatch.setattr(ai, "extract_frame", lambda src, t, out: (Path(out).write_bytes(b"p" * 100), str(out))[1])
    from shopping_shorts import app as A
    monkeypatch.setattr(A, "_SCENE_ASSETS_DIR", tmp_path / "assets")
    from shopping_shorts import scene_assets
    monkeypatch.setattr(scene_assets, "make_poster", lambda m, o: (Path(o).write_bytes(b"j"), o)[1])
    monkeypatch.setattr(scene_assets, "probe_duration", lambda p: 4.0)
    from shopping_shorts import mix_pipeline as mp
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": str(Path(work) / "s0" / "v.mp4"), "s2": str(Path(work) / "s2" / "v.mp4")})


def test_run_ai_scene_success_saves_asset_and_cutaway(tmp_path, monkeypatch):
    work = tmp_path / "j"; job = _job(work); store = _Store(job)
    _patch_common(monkeypatch, tmp_path, store)
    seen = {}
    def fake_gen(png, prompt, sec, out):
        seen.update(png=png, prompt=prompt, sec=sec); Path(out).write_bytes(b"m" * 20000); return str(out)
    aid = ai.run_ai_scene("j", 1, "impact", "db", tmp_path, gen=fake_gen,
                          call=lambda p, s: {"subject_desc_en": "Yellow octopus.", "motion_steps_en": ["a", "b", "c"]})
    assert aid == 77
    b = job["edit_plan"]["beats"][1]
    assert b["cutaway"] == {"asset_id": 77, "match_type": "ai"}
    assert b["ai_scene"]["state"] == "done" and b["ai_scene"]["sec"] == 4 and b["ai_scene"]["style"] == "impact"
    asset, cid = store.assets[0]
    assert asset["asset_type"] == "clip" and asset["render_mode"] == "cutaway" and asset["source_kind"] == "veo"
    assert asset["source_ref"] == "j:1:impact" and Path(asset["media_path"]).exists()
    assert seen["png"].endswith("ai_scene_base_1.png") and "quick dolly-in" in seen["prompt"]
    assert (work / "ai_scene_prompt_1.txt").exists()


def test_run_ai_scene_failure_sets_state_no_asset(tmp_path, monkeypatch):
    work = tmp_path / "j"; job = _job(work); store = _Store(job)
    _patch_common(monkeypatch, tmp_path, store)
    def boom(png, prompt, sec, out): raise RuntimeError("Veo 실패: quota")
    assert ai.run_ai_scene("j", 0, "natural", "db", tmp_path, gen=boom, call=lambda p, s: None) is None
    b = job["edit_plan"]["beats"][0]
    assert b["ai_scene"]["state"] == "failed" and "quota" in b["ai_scene"]["error"]
    assert "cutaway" not in b and store.assets == []


def test_run_ai_scene_refuses_while_rendering(tmp_path, monkeypatch):
    work = tmp_path / "j"; job = _job(work); job["status"] = "rendering"; store = _Store(job)
    _patch_common(monkeypatch, tmp_path, store)
    assert ai.run_ai_scene("j", 0, "natural", "db", tmp_path, gen=lambda *a: pytest.fail("생성이 돌았다")) is None
    assert job["edit_plan"]["beats"][0]["ai_scene"]["state"] == "failed"


def test_base_frame_prefers_clean_base_when_product_cut_is_in_it(tmp_path, monkeypatch):
    """제품만 컷(s2 6.77~8.07)이 청소본 컷 지도에 있으면 청소본 파일에서 그 자리를 뜬다(자막·워터마크 없음)."""
    from shopping_shorts import clean_base as cb
    work = tmp_path / "j"; work.mkdir()
    (work / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    cb.save_base(work, sig="x", path=str(work / "final_clean_x.mp4"), plan={"beats": []},
                 cuts=[{"video_id": "s2", "beat_idx": 3, "src": 6.8, "fin": 10.0, "dur": 1.2}])
    seen = {}
    monkeypatch.setattr(ai, "extract_frame", lambda src, t, out: (seen.update(src=str(src), t=t), str(out))[1])
    ai.base_frame_path({"urls": []}, work, dict(BEAT, beat_idx=3), EXTRACT, product_only=True,
                       resolve_sources=lambda job, w: {"s2": "raw_s2.mp4"})
    assert seen["src"].endswith("final_clean_x.mp4") and abs(seen["t"] - 10.6) < 0.01   # 겹침 6.8~8.0 → 청소본 10.0~11.2 가운데


def test_motion_request_passes_frame_to_image_call(monkeypatch):
    got = {}
    monkeypatch.setattr("shopping_shorts.edit_plan._vault_call_image",
                        lambda p, s, f: (got.update(frame=f, prompt=p), {"subject_desc_en": "x", "motion_steps_en": ["1", "2", "3"]})[1])
    ai.motion_request("a", "b", "natural", frame_path="base.png")
    assert got["frame"] == "base.png" and "Describe ONLY what is visible" in got["prompt"] and "flip inside out" in got["prompt"]
