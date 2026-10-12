# -*- coding: utf-8 -*-
"""스토리보드에서 사람이 고른 장면은 3단계 어느 단계도 더하거나 깎지 않는다(관제 120).

덮어쓰던 길 넷: ai_match.ensure_cover(장면 보장) · edit_plan._fill_beat_screen_time(화면 채우기)
· mix_pipeline._trim_for_cut_rhythm(컷 리듬) · store._ensure_screen_time(저장 관문).
판정은 ai_match.is_pinned 한 곳, 변환은 story_writer.storyboard_to_beat_sources 한 곳.
"""
from shopping_shorts import edit_plan, story_writer, ai_match
from shopping_shorts.mix_pipeline import _trim_for_cut_rhythm


def _seg(sid, start, end, desc):
    return {"seg_id": sid, "video_id": "s0", "start": start, "end": end,
            "shot_role": "사용중", "scene_desc": desc, "change": "", "text": "", "is_key": False}


SEGS = [_seg("s0-%d" % i, i * 1.0, i * 1.0 + 1.0, "장면 %d" % i) for i in range(12)]
LONG = "이 필터 하나 붙였더니 유리창 반사가 싹 사라져서 진짜 깜짝 놀랐다니까요 여러분 이거 꼭 써 보세요"


def _board():
    return [{"slot": "hook", "line": "반사 때문에 사진 망친 적 있죠?", "ids": ["s0-5"]},
            # 1초 장면 하나에 긴 대사 — 종전 길이면 장면 보장·화면 채우기가 컷을 덧붙였다
            {"slot": "feature", "line": LONG, "ids": ["s0-2"]},
            {"slot": "result", "line": "자석이라\n착 붙어요", "ids": ["s0-8", "s0-9", "s0-10"]}]


def _ids(b):
    return [r["seg_id"] for r in [b["primary"]] + list(b.get("alternates") or [])]


def test_변환은_줄마다_한칸_고른줄만_고정():
    conv = story_writer.storyboard_to_beat_sources(_board() + [{"slot": "x", "line": "  ", "ids": ["s0-1"]},
                                                              {"slot": "cta", "line": "댓글 남겨 주세요", "ids": []}])
    assert conv["script"].split("\n") == ["반사 때문에 사진 망친 적 있죠?", LONG, "자석이라 착 붙어요", "댓글 남겨 주세요"]
    assert [x["pinned"] for x in conv["beat_sources"]] == [True, True, True, False]
    assert conv["beat_sources"][2]["segs"] == ["s0-8", "s0-9", "s0-10"]


def test_상속_계획이_고른_장면을_그대로_잇는다():
    conv = story_writer.storyboard_to_beat_sources(_board())
    plan = edit_plan.build_inherit_plan([{"video_id": "s0", "segments": SEGS}], conv["script"], conv["beat_sources"])
    assert plan and len(plan["beats"]) == 3
    assert [_ids(b) for b in plan["beats"]] == [["s0-5"], ["s0-2"], ["s0-8", "s0-9", "s0-10"]]
    assert all(ai_match.is_pinned(b) for b in plan["beats"])
    # 컷 리듬도 깎지 않는다(1초 줄의 3컷 → 종전엔 1컷으로)
    _trim_for_cut_rhythm(plan)
    assert [_ids(b) for b in plan["beats"]] == [["s0-5"], ["s0-2"], ["s0-8", "s0-9", "s0-10"]]


def test_고정_안_한_줄은_종전대로_채운다():
    bs = [{"role": "feature", "seg": "s0-2", "segs": ["s0-2"]}]
    plan = edit_plan.build_inherit_plan([{"video_id": "s0", "segments": SEGS}], LONG + "\n끝", bs + [{"role": "cta", "seg": "", "segs": []}])
    assert plan and len(_ids(plan["beats"][0])) > 1, "고정이 아니면 장면 보장이 컷을 더한다(회귀 0)"


def test_장면보장은_고정줄을_모자람으로만_알린다():
    idx = {"a": {"secs": 1.0, "vid": "s0", "label": "x", "kind": ""}, "b": {"secs": 3.0, "vid": "s0", "label": "x", "kind": ""}}
    bs = [{"segs": ["a"], "pinned": True}]
    note = {}
    ai_match.ensure_cover(bs, [{"text": LONG}], idx, None, note=note)
    assert bs[0]["segs"] == ["a"] and note["cover_short"] == [0]


def test_저장관문은_고정계획을_다시_꽂지_않는다():
    from shopping_shorts import store as _store
    plan = {"generator": "inherit", "beats": [{"primary": {"seg_id": "s0-5"}, "alternates": [], "pinned": True,
                                                "narration": "x", "target_seconds": 9.0}]}

    class _St:
        def get_mix_job(self, _j):
            return {"customer_id": 0, "extract": {"s0": {"segments": SEGS}},
                    "script_structure": {"beat_sources": [{"role": "hook", "seg": "s0-1"}]}}

        def get_setting(self, *_a, **_k):
            return None

    out = _store._ensure_screen_time(plan, _St(), "j")
    assert _ids(out["beats"][0]) == ["s0-5"]


def test_번호가_바뀐_같은_장면은_경계로_잇는다():
    """10-05 라이브 job 4cd80576b70e: 2단계 캐시 번호(<영상코드>-n)가 3단계에서 s0-n 으로 바뀌고 설명도 새로 달렸다(경계는 같음)."""
    seg_map = {"s0-0": {"video_id": "s0", "start": 0.0, "end": 1.1}, "s0-1": {"video_id": "s0", "start": 1.1, "end": 2.0},
               "s1-0": {"video_id": "s1", "start": 0.0, "end": 5.5}, "s1-1": {"video_id": "s1", "start": 5.5, "end": 11.0}}
    key = {"id": "grab_b-1", "start": 5.5, "end": 11.0, "vsig": [0.0, 5.5]}
    assert edit_plan.match_seg_key(key, seg_map) == "s1-1"
    assert edit_plan.match_seg_key({"id": "x", "start": 0.0, "end": 1.1, "vsig": [0.0]}, seg_map) is None   # 영상 둘이 맞으면 안 붙인다
    assert edit_plan.match_seg_key({"id": "x", "start": 9.0, "end": 9.5, "vsig": [0.0, 5.5]}, seg_map) is None
