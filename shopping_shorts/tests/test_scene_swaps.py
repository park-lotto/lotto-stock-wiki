# -*- coding: utf-8 -*-
"""장면 교체 기록(2026-09-04) — 3단계에서 사람이 첫 조각을 바꾼 비트를 자동으로 남긴다.
매칭의 시험지(설계 §8-D). 픽 로직에는 쓰지 않는다."""
import os
import tempfile

from shopping_shorts import edit_plan as EP


def _beat(i, primary, over=None, **extra):
    b = {"beat_idx": i, "narration": f"줄{i}", "primary": {"seg_id": primary, "video_id": "s0"}, **extra}
    if over:
        b["scene_override"] = [{"seg_id": s, "video_id": "s0"} for s in over]
    return b


def test_first_material_seg_은_편성이_있으면_편성_없으면_primary():
    assert EP.first_material_seg(_beat(0, "s0-1")) == "s0-1"
    assert EP.first_material_seg(_beat(0, "s0-1", over=["s0-7", "s0-8"])) == "s0-7"
    assert EP.first_material_seg({"beat_idx": 0}) is None


def test_scene_swap_rows_는_첫_조각이_바뀐_비트만():
    before = {"beats": [_beat(0, "s0-1"), _beat(1, "s0-2"), _beat(2, "s0-3", inherited=True)],
              "generator": "inherit"}
    after = {"beats": [_beat(0, "s0-1"), _beat(1, "s0-2", over=["s0-9"]), _beat(2, "s0-3", over=["s0-5"], inherited=True, fit=5)],
             "generator": "inherit"}
    rows = EP.scene_swap_rows(before, after)
    assert [r["beat_idx"] for r in rows] == [1, 2]
    assert rows[0]["old_seg"] == "s0-2" and rows[0]["new_seg"] == "s0-9" and rows[0]["inherited"] == 0
    assert rows[1]["old_seg"] == "s0-3" and rows[1]["new_seg"] == "s0-5" and rows[1]["inherited"] == 1
    assert rows[1]["generator"] == "inherit" and rows[1]["fit"] == 5
    # 편성을 원래 첫 조각과 같게 두면 교체가 아니다
    same = {"beats": [_beat(0, "s0-1", over=["s0-1", "s0-4"])], "generator": "legacy"}
    assert EP.scene_swap_rows({"beats": [_beat(0, "s0-1")]}, same) == []


def test_store_에_쌓이고_요약이_나온다():
    from shopping_shorts.store import Store
    d = tempfile.mkdtemp()
    st = Store(os.path.join(d, "t.db"))
    rows = [{"beat_idx": 1, "narration": "줄1", "old_seg": "a", "new_seg": "b", "generator": "inherit", "inherited": 1, "fit": 5},
            {"beat_idx": 2, "narration": "줄2", "old_seg": "c", "new_seg": "d", "generator": "inherit", "inherited": 0, "fit": 3}]
    assert st.add_scene_swaps("job1", 7, rows) == 2
    assert st.add_scene_swaps("job2", 7, rows[:1]) == 1
    assert st.add_scene_swaps("job2", 7, []) == 0
    got = st.list_scene_swaps(job_id="job1")
    assert len(got) == 2 and {r["new_seg"] for r in got} == {"b", "d"} and got[0]["customer_id"] == 7
    s = st.scene_swap_summary()
    assert s["inherit"]["jobs"] == 2 and s["inherit"]["swaps"] == 3 and s["inherit"]["inherited_swaps"] == 2
    assert s["inherit"]["per_job"] == 1.5
