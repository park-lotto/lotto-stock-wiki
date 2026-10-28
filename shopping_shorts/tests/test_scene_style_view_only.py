# -*- coding: utf-8 -*-
"""장면꾸미기 저장값의 화면 전용 값(sceneIndex·frameKind)은 '설정이 바뀌었나' 판정에 안 들어간다 (2026-09-28 사장님 job 8c63b0691924).
렌더 끝난 작업에서 편집기를 열어 다른 장면을 구경하고 [닫기]만 눌러도 완성본이 무효화되던 것 — 판단 주인 scene_style.render_view."""
from shopping_shorts.store import Store
from shopping_shorts import app as module
from shopping_shorts.mix_pipeline import _render_stamp
from shopping_shorts.scene_style import render_view, deco_render_view

SNAP = {"version": 1, "mode": "story", "presetId": "t11", "sceneIndex": 3, "frameKind": "body",
        "captionDrags": {"t11:story:2:caption": {"x": 0.5, "y": 15.9}}, "text": {"channel": "숏템"}}


def _job(tmp_path):
    store = Store(str(tmp_path / "qa.db")); store.create_mix_job("j1", [], 3, "free")
    store.update_mix_job("j1", deco={"scene_style": dict(SNAP), "watermark": {"on": False}}, status="done", video_path="final.mp4")
    return store


def test_render_view_strips_only_view_keys():
    assert "sceneIndex" not in render_view(SNAP) and "frameKind" not in render_view(SNAP)
    assert render_view({**SNAP, "text": {"channel": "숏템", "caption": "a"}}) == render_view({**SNAP, "text": {"channel": "숏템", "caption": "b"}})
    assert render_view({**SNAP, "text": {"channel": "A"}}) != render_view({**SNAP, "text": {"channel": "B"}})
    assert render_view(SNAP)["captionDrags"] == SNAP["captionDrags"]
    assert render_view(None) is None and deco_render_view(None) is None


def test_browsing_scene_does_not_invalidate(tmp_path):
    store = _job(tmp_path)
    changed = module._save_render_inputs(store, "j1", deco={"scene_style": {**SNAP, "sceneIndex": 16, "frameKind": "hook", "text": {"channel": "숏템", "caption": "다른 장면 자막"}}, "watermark": {"on": False}})
    j = store.get_mix_job("j1")
    assert changed is False and j["status"] == "done" and j["video_path"] == "final.mp4"


def test_real_change_still_invalidates(tmp_path):
    store = _job(tmp_path)
    moved = {**SNAP, "captionDrags": {"t11:story:2:caption": {"x": 0.5, "y": -20}}}
    changed = module._save_render_inputs(store, "j1", deco={"scene_style": moved, "watermark": {"on": False}})
    j = store.get_mix_job("j1")
    assert changed is True and j["status"] == "ready_for_review" and not j["video_path"]


def test_render_stamp_ignores_view_keys():
    a = {"deco": {"scene_style": dict(SNAP)}, "headcopy": {"text": "x"}}
    b = {"deco": {"scene_style": {**SNAP, "sceneIndex": 9, "frameKind": "hook"}}, "headcopy": {"text": "x"}}
    c = {"deco": {"scene_style": {**SNAP, "text": {"channel": "다른"}}}, "headcopy": {"text": "x"}}
    assert _render_stamp(a) == _render_stamp(b) and _render_stamp(a) != _render_stamp(c)
