# -*- coding: utf-8 -*-
"""템플릿에서 제목 세 칸이 전부 빈칸으로 저장되면 자동 제목으로 — 원본(plain)은 빈칸 그대로 (2026-09-25)."""
from shopping_shorts import scene_style

TL = [{"beat_idx": 0, "t0": 0, "dur": 1, "narration": "프로게이머도 예상 못한 미친 활용법", "caption_lines": ["프로게이머도 예상 못한 미친 활용법"], "role": "훅"},
      {"beat_idx": 1, "t0": 1, "dur": 1, "narration": "과자 먹을 때", "caption_lines": ["과자 먹을 때"], "role": "미끼"}]
EMPTY = {"channel": "숏템메이커", "hook1": "", "hook2": "", "bodyTitle": "", "caption": "x"}


def _text(preset, text):
    return scene_style.context_for(TL, {"text": ""}, {"presetId": preset, "text": text})["text"]


def test_template_all_empty_titles_fall_back_to_script():
    t = _text("t11", EMPTY)
    assert t["hook1"] and "프로게이머" in t["hook1"] + t["hook2"]


def test_template_partial_empty_is_respected():
    t = _text("t11", {"hook1": "내 제목", "hook2": "", "bodyTitle": ""})
    assert t["hook1"] == "내 제목" and t["hook2"] == ""


def test_plain_empty_titles_stay_empty():
    t = _text("plain", EMPTY)
    assert t["hook1"] == "" and t["hook2"] == "" and t["bodyTitle"] == ""
