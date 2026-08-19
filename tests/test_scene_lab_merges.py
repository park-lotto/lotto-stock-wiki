# -*- coding: utf-8 -*-
"""🔗 조각 합치기 — 2026-08-17 사장님 "0.5초 같은 건 못 쓰니까 3개 합쳐서 훅에 넣으려고".

화면(scene_play.js mergeSpan)과 서버(apply_scene_lab)가 **같은 규칙**이어야 한다:
대표 조각의 end를 마지막 멤버의 end까지 늘려 **긴 구간 하나**로 만든다.
"""
import shopping_shorts.edit_plan as ep


def _beat(idx=0):
    return {"beat_idx": idx, "narration": "가",
            "primary": {"video_id": "s1", "seg_id": "s1-1", "start": 0.0, "end": 2.0}}


SEG_MAP = {
    "a1": {"video_id": "s1", "seg_id": "a1", "start": 3.0, "end": 3.5,
           "scene_desc": "뚜껑 여는 손", "is_key": True, "shot_role": "before"},
    "a2": {"video_id": "s1", "seg_id": "a2", "start": 3.5, "end": 4.0, "scene_desc": "놀람"},
    "a3": {"video_id": "s1", "seg_id": "a3", "start": 4.0, "end": 4.6, "scene_desc": "클로즈업"},
    "b1": {"video_id": "s2", "seg_id": "b1", "start": 0.0, "end": 2.0, "scene_desc": "완성"},
}


def test_합친_조각은_긴_구간_하나로_간다():
    plan = {"beats": [_beat()]}
    ep.apply_scene_lab(plan, SEG_MAP, {
        "beats": [{"beat_idx": 0, "list": ["a1", "b1"]}],
        "merges": {"a1": ["a2", "a3"]}})
    over = plan["beats"][0]["scene_override"]
    assert [(s["seg_id"], s["start"], s["end"]) for s in over] == \
        [("a1", 3.0, 4.6), ("b1", 0.0, 2.0)]
    # 0.5초 → 1.6초. 이제 라운드로빈 min_clip(0.8)을 넘어 실제로 화면에 나온다.
    assert over[0]["end"] - over[0]["start"] >= 0.8
    assert plan["scene_lab"]["merges"] == {"a1": ["a2", "a3"]}


def test_멤버가_목록에_남아_있어도_중복되지_않는다():
    """화면 doMerge가 갈아 끼우지만, 옛 저장본·다른 경로로 멤버가 남아 올 수 있다."""
    plan = {"beats": [_beat()]}
    ep.apply_scene_lab(plan, SEG_MAP, {
        "beats": [{"beat_idx": 0, "list": ["a2", "a1", "a3"]}],
        "merges": {"a1": ["a2", "a3"]}})
    over = plan["beats"][0]["scene_override"]
    assert [(s["seg_id"], s["start"], s["end"]) for s in over] == [("a1", 3.0, 4.6)]


def test_트림과_같이_써도_토막_규칙은_그대로():
    plan = {"beats": [_beat()]}
    ep.apply_scene_lab(plan, SEG_MAP, {
        "beats": [{"beat_idx": 0, "list": ["a1"]}],
        "merges": {"a1": ["a2", "a3"]}, "trims": {"a1": [0.5, 1.0]}})
    # 합쳐 늘린 3.0~4.6 안에서 [0.5,1.0] 구멍 → 3.0~3.5 + 4.0~4.6
    assert [(s["start"], s["end"]) for s in plan["beats"][0]["scene_override"]] == \
        [(3.0, 3.5), (4.0, 4.6)]


def test_merges가_없으면_한_글자도_안_바뀐다():
    """회귀 방지 — 기존 잡·기존 저장본(merges 없음)은 종전과 100% 동일해야 한다."""
    edits = {"beats": [{"beat_idx": 0, "list": ["a1", "b1"], "stretch": True}]}
    p1, p2 = {"beats": [_beat()]}, {"beats": [_beat()]}
    ep.apply_scene_lab(p1, SEG_MAP, edits)
    ep.apply_scene_lab(p2, SEG_MAP, {**edits, "merges": {}})
    assert p1["beats"][0]["scene_override"] == p2["beats"][0]["scene_override"]
    assert [(s["seg_id"], s["end"]) for s in p1["beats"][0]["scene_override"]] == \
        [("a1", 3.5), ("b1", 2.0)]
