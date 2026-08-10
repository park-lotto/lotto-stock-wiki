"""소스별 첫·마지막 세그먼트를 인벤토리에서 제외(3개↑일 때만). 전사(full_text)는 무관."""
from shopping_shorts import edit_plan


def _seg(sid, txt, key=False):
    return {"seg_id": sid, "start": 0.0, "end": 2.0, "text": txt,
            "scene_desc": txt, "action": None, "is_key": key, "shot_role": "기타"}


def test_first_and_last_excluded_when_3plus():
    script = {"video_id": "v", "segments": [
        _seg("v-0", "썸네일"), _seg("v-1", "본문A"), _seg("v-2", "본문B"), _seg("v-3", "CTA")]}
    seg_map, _ = edit_plan._build_inventory([script])
    assert "v-0" not in seg_map      # 첫 제외
    assert "v-3" not in seg_map      # 마지막 제외
    assert "v-1" in seg_map and "v-2" in seg_map


def test_kept_when_2_or_fewer():
    script = {"video_id": "v", "segments": [_seg("v-0", "a"), _seg("v-1", "b")]}
    seg_map, _ = edit_plan._build_inventory([script])
    assert "v-0" in seg_map and "v-1" in seg_map   # 2개면 삭제 안 함


def test_iskey_preserved_in_seg_map():
    script = {"video_id": "v", "segments": [
        _seg("v-0", "썸네일"), _seg("v-1", "본문", key=True), _seg("v-2", "CTA")]}
    seg_map, _ = edit_plan._build_inventory([script])
    assert seg_map["v-1"]["is_key"] is True
