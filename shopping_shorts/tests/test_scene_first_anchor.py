"""scene_first 주경로용 앵커 dedup + 레시피 grain (순수 헬퍼) — Task8.

primary 경로(build_scene_first_plan→_ground_candidate)는 _chronological_respine을
안 쓴다. 그래서 앵커 dedup·레시피 grain을 이 경로용 순수 헬퍼 _apply_anchor_grain으로
따로 태워 _ground_score의 _verify_fits 직후 발동시킨다. 이 파일은 그 헬퍼를 직접 검증한다.
"""
from shopping_shorts import edit_plan


def _beat(sid, desc, role="기타", key=False, alt=None):
    p = {"seg_id": sid, "video_id": sid[0], "start": 0.0, "end": 2.0,
         "scene_desc": desc, "is_key": key, "shot_role": role}
    return {"primary": p, "alternates": ([alt] if alt else []),
            "narration": "n", "fit": 4, "role": ""}


def test_recipe_grain_finish_last():
    """레시피면 movable 비트 중 완성 primary가 조리 뒤로 밀린다(finish_last)."""
    beats = [_beat("h", "훅"),
             _beat("a-5", "완성샷", "완성"), _beat("a-1", "조리1", "조리"),
             _beat("a-3", "조리2", "조리"),
             _beat("t", "끝")]
    out = edit_plan._apply_anchor_grain(beats, is_recipe=True)
    mids = [b["primary"]["shot_role"] for b in out[1:-1]]
    assert mids.index("완성") == max(range(len(mids)))  # 완성이 movable 중 가장 뒤


def test_anchor_dedup_promotes_alternate():
    """같은 장점(넓다) is_key 앵커가 둘이면 뒤엣것은 대체로 교체돼 장점 primary는 하나만."""
    alt = {"seg_id": "b-9", "video_id": "b", "start": 9.0, "end": 11.0,
           "scene_desc": "다른 장점", "is_key": True, "shot_role": "완성"}
    beats = [_beat("h", "훅"),
             _beat("a-1", "내부 넓어 가득", "완성", key=True),
             _beat("b-1", "안쪽 넓어 가득", "완성", key=True, alt=alt),  # 같은 장점 → 대체로 승격
             _beat("t", "끝")]
    out = edit_plan._apply_anchor_grain(beats, is_recipe=False)
    primaries = [b["primary"]["seg_id"] for b in out]
    assert primaries.count("b-1") == 0 or "b-9" in primaries  # 중복 앵커는 대체로 교체
    # 넓다 장점 primary는 하나만
    wide = [b for b in out if "넓" in b["primary"]["scene_desc"]]
    assert len(wide) == 1


def test_non_recipe_keeps_order():
    """비레시피는 순서 불변(제품 순서 보존) — grain 리오더 안 함."""
    beats = [_beat("h", "훅"), _beat("a-1", "완성", "완성"),
             _beat("a-2", "조리", "조리"), _beat("t", "끝")]
    out = edit_plan._apply_anchor_grain(beats, is_recipe=False)
    assert [b["primary"]["seg_id"] for b in out] == ["h", "a-1", "a-2", "t"]  # 순서 불변


def test_no_mutation_of_input():
    """입력 비트를 제자리 변형하지 않는다(스냅샷 안전)."""
    beats = [_beat("h", "훅"), _beat("a-5", "완성", "완성"),
             _beat("a-1", "조리", "조리"), _beat("t", "끝")]
    before = [b["primary"]["seg_id"] for b in beats]
    edit_plan._apply_anchor_grain(beats, is_recipe=True)
    after = [b["primary"]["seg_id"] for b in beats]
    assert before == after  # 원본 순서 불변(새 리스트 반환)


def test_empty_and_short():
    """빈/짧은 비트 방어 — 크래시 없이 그대로 반환."""
    assert edit_plan._apply_anchor_grain([], is_recipe=True) == []
    one = [_beat("h", "훅")]
    assert len(edit_plan._apply_anchor_grain(one, is_recipe=True)) == 1
