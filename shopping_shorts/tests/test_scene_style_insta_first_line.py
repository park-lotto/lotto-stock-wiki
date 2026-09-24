# -*- coding: utf-8 -*-
"""인스타 대본은 첫 장면부터 본문(자막) — 썰 대본은 첫 비트=훅 제목 그대로 (2026-09-25 사장님)."""
from shopping_shorts import scene_style, script_families, video_assemble


def _tl(title_line=None):
    plan = {"beats": [{"beat_idx": i, "narration": n, "caption_lines": [n], "role": r, "target_seconds": 1}
                      for i, (n, r) in enumerate([("아니, 요즘 거실에서 싸움이 멈추질 않아요", "훅"), ("이거 하나로 끝났어요", "장면")])]}
    if title_line is not None:
        plan["title_line"] = title_line
    tts = {0: "a.wav", 1: "b.wav"}
    orig = video_assemble._beat_effective_dur
    video_assemble._beat_effective_dur = lambda beat, tts: 1.0
    try:
        return video_assemble._beat_timeline(plan, tts)
    finally:
        video_assemble._beat_effective_dur = orig


def test_sul_first_beat_is_hook():
    scenes = scene_style.context_for(_tl())["scenes"]
    assert scenes[0]["kind"] == "hook"


def test_insta_first_beat_is_body():
    scenes = scene_style.context_for(_tl(False))["scenes"]
    assert all(s["kind"] == "body" for s in scenes)
    assert scenes[0]["caption"].startswith("아니")


def test_mark_plan_by_family(monkeypatch):
    import shopping_shorts.sfx_pack as sp
    monkeypatch.setattr(sp, "script_family", lambda store, job: ["지인증언형", "홈템"])
    assert script_families.mark_plan(None, {}, {"beats": []})["title_line"] is False
    monkeypatch.setattr(sp, "script_family", lambda store, job: ["오용형"])
    assert script_families.mark_plan(None, {}, {"beats": []})["title_line"] is True
    monkeypatch.setattr(sp, "script_family", lambda store, job: [])
    assert script_families.mark_plan(None, {}, {"beats": []})["title_line"] is True   # 모르면 종전
