"""레시피면 movable 재배치 시 shot_role=완성 세그먼트를 조리 뒤로 정렬(완성이 조리 앞에 안 낌).
제품(is_recipe=False)이면 기존 (video_id,start) 시간순 유지."""
from shopping_shorts import edit_plan


def _beat(sid, vid, start, role):
    seg = {"seg_id": sid, "video_id": vid, "start": start, "end": start + 2,
           "scene_desc": role, "text": "t", "shot_role": role}
    return {"primary": seg, "alternates": [], "text": "t", "fit": 4}


def test_recipe_finish_after_cook():
    # 머리·꼬리 앵커 제외를 피하려 비트 5개, 가운데 3개가 movable.
    beats = [_beat("h", "a", 0, "기타"),
             _beat("a-5", "a", 5, "완성"), _beat("a-1", "a", 1, "조리"),
             _beat("a-3", "a", 3, "조리"),
             _beat("t", "a", 9, "기타")]
    out = edit_plan._chronological_respine(beats, is_recipe=True)
    mid_roles = [b["primary"]["shot_role"] for b in out[1:-1]]
    # 완성이 가장 뒤
    assert mid_roles.index("완성") == max(range(len(mid_roles)))


def test_product_keeps_time_order():
    beats = [_beat("h", "a", 0, "기타"),
             _beat("a-5", "a", 5, "완성"), _beat("a-1", "a", 1, "완성"),
             _beat("a-3", "a", 3, "완성"),
             _beat("t", "a", 9, "기타")]
    out = edit_plan._chronological_respine(beats, is_recipe=False)
    mids = [b["primary"]["start"] for b in out[1:-1]]
    assert mids == sorted(mids)   # 제품은 (start) 시간순 그대로
