"""덩어리 믹스 — 훅/스토리/CTA를 연속 구간으로 먼저 확정하고 화면을 코드가 배정한다.

사장님 지시(2026-07-31): "믹스할 때 완전 뒤죽박죽으로 하지 마라. 1~3개 영상에서 훅이 좋은
부분을 쭉 이어서 가져오고 그 장면에 맞게 대본을 넣고 / 스토리 / CTA. 단순하게.
30초면 6컷 정도. 액션 있는 장면은 잘게 쪼개지 말고 원대본과 다른 대사로."
"""
from shopping_shorts import edit_plan as ep


def _sm(spec):
    """spec: [(seg_id, role, dur, change)] → seg_map"""
    m, t = {}, 0.0
    for sid, role, dur, chg in spec:
        m[sid] = {"video_id": sid.rsplit("-", 1)[0], "seg_id": sid, "start": t, "end": t + dur,
                  "scene_desc": f"{sid} 화면", "change": chg, "is_key": bool(chg),
                  "shot_role": role}
        t += dur
    return m


def _demo():
    return _sm([("v-0", "문제", 2.0, "기름이 튄다"), ("v-1", "문제", 2.0, ""),
                ("v-2", "사용중", 3.0, "가림막을 세운다"), ("v-3", "사용중", 3.0, "물로 헹군다"),
                ("v-4", "사용중", 3.0, ""), ("v-5", "after", 3.0, "깨끗해졌다"),
                ("v-6", "완성", 2.0, ""), ("v-7", "완성", 2.0, "")])


def test_blocks_are_hook_story_cta_in_order():
    b = ep._build_scene_blocks(_demo(), 30)
    assert [x["name"] for x in b] == ["훅", "스토리", "CTA"]


def test_each_block_is_contiguous():
    for blk in ep._build_scene_blocks(_demo(), 30):
        nums = [ep._seg_seq(s["seg_id"])[1] for s in blk["segs"]]
        assert nums == list(range(nums[0], nums[0] + len(nums))), blk["name"]


def test_no_segment_used_twice():
    ids = [s["seg_id"] for blk in ep._build_scene_blocks(_demo(), 30) for s in blk["segs"]]
    assert len(ids) == len(set(ids))


def test_cut_count_stays_small_for_30s():
    """30초면 6컷 정도 — 액션 장면을 잘게 쪼개지 않으려면 컷이 적어야 한다."""
    n = sum(len(b["segs"]) for b in ep._build_scene_blocks(_demo(), 30))
    assert 3 <= n <= 8, n


def test_prompt_block_gives_char_budget():
    txt = ep._blocks_order_block(ep._build_scene_blocks(_demo(), 30))
    assert "자 이내로 써라" in txt and "화면은 이미 정해졌다" in txt
    assert "원본이 하던 말을 그대로 옮기지 말고" in txt


def test_assign_blocks_overrides_model_choice():
    """말은 모델 것, 화면은 코드 것 — 모델이 뭘 골랐든 덩어리 순서대로 다시 배정."""
    sm = _demo()
    blocks = ep._build_scene_blocks(sm, 30)
    beats = [{"role": "훅", "narration": "가나다", "primary": {"seg_id": "v-7"}, "alternates": []},
             {"role": "해결", "narration": "라마바사", "primary": {"seg_id": "v-7"}, "alternates": []},
             {"role": "CTA", "narration": "아자차", "primary": {"seg_id": "v-0"}, "alternates": []}]
    ep._assign_blocks(beats, blocks)
    hook_ids = {s["seg_id"] for s in blocks[0]["segs"]}
    cta_ids = {s["seg_id"] for s in blocks[-1]["segs"]}
    assert beats[0]["primary"]["seg_id"] in hook_ids
    assert beats[-1]["primary"]["seg_id"] in cta_ids


def test_empty_inventory_is_safe():
    assert ep._build_scene_blocks({}, 30) == []
    assert ep._blocks_order_block([]) == ""
    assert ep._assign_blocks([], []) == []
