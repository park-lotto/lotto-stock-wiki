"""여러 소스가 같은 장점을 실증하면 하나만 남긴다(scene_desc 요지 기준). 강한 순 상위 N개."""
from shopping_shorts import edit_plan


def _seg(sid, desc, vid="v"):
    return {"seg_id": sid, "video_id": vid, "start": 0.0, "end": 2.0,
            "scene_desc": desc, "is_key": True, "shot_role": "완성"}


def test_dedup_same_claim_kept_once():
    anchors = [
        _seg("a-1", "내부가 넓어 그릇 가득", "a"),
        _seg("b-1", "안쪽이 넓어 접시 가득", "b"),   # 같은 장점(넓다)
        _seg("a-2", "과일 야채도 세척", "a"),
    ]
    out = edit_plan._dedup_anchors(anchors, top_n=4)
    descs = [s["scene_desc"] for s in out]
    # "넓다" 계열은 하나만
    wide = [d for d in descs if "넓" in d]
    assert len(wide) == 1
    assert any("세척" in d for d in descs)


def test_dedup_caps_top_n():
    anchors = [_seg(f"v-{i}", f"장점{i}") for i in range(8)]
    out = edit_plan._dedup_anchors(anchors, top_n=4)
    assert len(out) <= 4


def test_dedup_empty():
    assert edit_plan._dedup_anchors([], top_n=4) == []
