"""소스별 첫·마지막 세그먼트를 인벤토리에서 제외. 전사(full_text)는 무관.

★기준 변경(2026-08-14): 옛 기준은 '3개 이상이면 제외'였는데, 그러면 세그 3개짜리
소스는 1개만 남아 **소스가 통째로 죽는다**(실측 job 1e924608af83: 샤오홍슈 s0).
이제 '잘라낸 뒤 3개 이상 남을 때만'(=5개 이상) 자른다.
"""
from shopping_shorts import edit_plan


def _seg(sid, txt, key=False):
    return {"seg_id": sid, "start": 0.0, "end": 2.0, "text": txt,
            "scene_desc": txt, "action": None, "is_key": key, "shot_role": "기타"}


def test_first_and_last_excluded_when_enough():
    """세그가 넉넉하면(5개↑) 종전대로 썸네일·CTA 자리를 버린다."""
    script = {"video_id": "v", "segments": [
        _seg("v-0", "썸네일"), _seg("v-1", "본문A"), _seg("v-2", "본문B"),
        _seg("v-3", "본문C"), _seg("v-4", "CTA")]}
    seg_map, _ = edit_plan._build_inventory([script])
    assert "v-0" not in seg_map      # 첫 제외
    assert "v-4" not in seg_map      # 마지막 제외
    assert {"v-1", "v-2", "v-3"} <= set(seg_map)


def test_short_source_not_trimmed():
    """3~4개짜리 짧은 소스는 자르지 않는다 — 자르면 소스가 사실상 사라진다."""
    for n in (3, 4):
        segs = [_seg(f"v-{i}", f"본문{i}") for i in range(n)]
        seg_map, _ = edit_plan._build_inventory([{"video_id": "v", "segments": segs}])
        assert len(seg_map) == n, f"세그 {n}개 소스가 잘렸다: {len(seg_map)}개 생존"


def test_kept_when_2_or_fewer():
    script = {"video_id": "v", "segments": [_seg("v-0", "a"), _seg("v-1", "b")]}
    seg_map, _ = edit_plan._build_inventory([script])
    assert "v-0" in seg_map and "v-1" in seg_map   # 2개면 삭제 안 함


def test_iskey_preserved_in_seg_map():
    script = {"video_id": "v", "segments": [
        _seg("v-0", "썸네일"), _seg("v-1", "본문", key=True), _seg("v-2", "CTA")]}
    seg_map, _ = edit_plan._build_inventory([script])
    assert seg_map["v-1"]["is_key"] is True
