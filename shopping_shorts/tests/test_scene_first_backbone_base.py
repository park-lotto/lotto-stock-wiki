"""백본 통합(2026-07-22 페이블 점검 결론): 생성기는 rich(_scene_first_candidates) 하나만.
backbone_base=True는 백본의 '화면 순서 제약' 블록만 프롬프트에 얹는다 — 스토리 선언·짤드라마
헌장·은행·다중컷은 rich가 담당. (예전 뼈다귀 생성기는 스키마에 스토리 필드가 없어 단조·무스토리·
은행묻힘이 구조적으로 났고 폐기됨 — 그 회귀 방지가 이 테스트들.)"""
from shopping_shorts import edit_plan


# BB는 세그먼트 2개(최다)+인스타 → 백본. S1은 서브.
_SOURCES = [
    {"video_id": "BB", "full_text": "백본대본", "segments": [
        {"seg_id": "BB-1", "start": 0, "end": 3, "text": "", "scene_desc": "재료 손질", "action": "자르다"},
        {"seg_id": "BB-2", "start": 3, "end": 6, "text": "", "scene_desc": "완성 접시", "action": "올리다"}]},
    {"video_id": "S1", "full_text": "서브대본", "segments": [
        {"seg_id": "S1-9", "start": 0, "end": 3, "text": "", "scene_desc": "붓는 장면", "action": "붓다"}]},
]

_RICH = {"candidates": [{
    "hook": "이거 실화냐?", "story_person": "남편",
    "beats": [
        {"role": "훅", "narration": "이거 실화냐? 남편이 아침을 거르더라고요", "seg_ids": ["BB-1"], "fit": 5},
        {"role": "결말", "narration": "이젠 이것만 찾아요", "seg_ids": ["BB-2"], "fit": 5}]}]}


def test_backbone_base_uses_rich_generator_with_order_block():
    # 백본은 '순서 블록'으로만 개입 — 프롬프트에 스토리 헌장+은행+순서 뼈대가 전부 실려야 한다.
    seen = {}

    def _cap(prompt, schema):
        seen["prompt"], seen["schema"] = prompt, schema
        return _RICH
    res = edit_plan.build_scene_first_plan(_SOURCES, "ref", 20, n_candidates=1, call=_cap,
                                           backbone_base=True, bank_context="[은행 훅] 이거 실화냐")
    p = seen["prompt"]
    assert "백본 흐름" in p and "BB-1" in p and "BB-2" in p        # 백본 순서 제약(2026-07-27 헤더 개명)
    assert p.index("BB-1 [자르다]") < p.index("BB-2 [올리다]")      # 시간순 나열
    assert "스파인" in p                                           # rich 스토리 생성(5단계 스파인) 그대로
    assert "[은행 훅] 이거 실화냐" in p                             # 은행 parts 재주입(2026-07-27 우수라인 양념)
    # rich 스키마(스토리 필드·다중컷)로 생성 — 뼈다귀 스키마(beats+seg_id 단일) 회귀 방지.
    cand_props = seen["schema"]["properties"]["candidates"]["items"]["properties"]
    assert "story_person" in cand_props and "hook" in cand_props
    # 후보가 rich 형태로 grounding됨 + 스토리 필드 보존.
    rec = res["candidates"][0]
    assert rec["story"]["story_person"] == "남편"
    assert "남편" in rec["plan"]["beats"][0]["narration"]


def test_backbone_base_off_has_no_order_block():
    seen = {}

    def _cap(prompt, schema):
        seen["prompt"] = prompt
        return _RICH
    edit_plan.build_scene_first_plan(_SOURCES, "ref", 20, n_candidates=1, call=_cap,
                                     backbone_base=False)
    assert "화면 순서 뼈대" not in seen["prompt"]


def test_backbone_order_block_empty_when_backbone_missing():
    assert edit_plan._backbone_order_block("없는영상", _SOURCES) == ""
    assert edit_plan._backbone_order_block("BB", []) == ""


def test_backbone_order_block_has_replace_insert_guard():
    """교체/삽입 지시가 예시 없는 추상 문장뿐이면 실사용에서 잘 안 지켜졌다(2026-07-30 실사고:
    3영상 중 백본만 거의 다 들어가고 서브는 버려짐). 구체적 BAD/GOOD 예시 + 서브 소스 식별
    규칙 + 서브 목록 명시 + '전부 최소 한 번씩' 강제 지시가 있는지 고정."""
    block = edit_plan._backbone_order_block("BB", _SOURCES)
    assert "(BAD)" in block and "(GOOD)" in block          # 패러프레이즈 구체 예시
    assert "서브 소스 식별" in block                          # seg_id 접두사로 서브 구분 규칙
    assert "서브 소스: S1" in block                          # 서브 소스를 이름으로 콕 집어줌
    assert "각각을 최소 한 번씩" in block                      # 서브소스 전부 커버 강제(1개만 X)
    assert "리액션/감상 문장" in block                        # 행위 안 맞아도 쓸 수 있는 대안 제시


def test_backbone_order_block_no_sub_sources_note():
    """서브 소스가 없는 단일 소스 영상이면 서브 강제 문구 대신 안내만."""
    solo = [_SOURCES[0]]   # 백본(BB)만
    block = edit_plan._backbone_order_block("BB", solo)
    assert "서브 소스가 없다" in block
    assert "각각을 최소 한 번씩" not in block


def test_judge_picks_best_candidate():
    # rich 생성이 후보 2개를 주면 심사위원(대본품질·장면싱크·스토리라인)이 최고를 추천한다.
    def _call(prompt, schema):
        props = schema.get("properties", {})
        if "script_quality" in props:                    # 심사 콜
            good = "남편" in prompt                      # 스토리 있는 후보에 고득점
            return {"script_quality": 5 if good else 1, "scene_sync": 3, "storyline": 5 if good else 1}
        return {"candidates": [
            {"hook": "", "beats": [{"role": "", "narration": "달걀을 부어요",
                                    "seg_ids": ["BB-1"], "fit": 5}]},
            {"hook": "h", "story_person": "남편", "beats": [
                {"role": "훅", "narration": "남편이 아침을 거르더라고요", "seg_ids": ["BB-2"], "fit": 5}]}]}
    res = edit_plan.build_scene_first_plan(_SOURCES, "ref", 20, call=_call,
                                           backbone_base=True, judge=True)
    rec = next(c for c in res["candidates"] if c["recommended"])
    assert "남편" in rec["plan"]["beats"][0]["narration"]   # 스토리 후보가 이김
    assert rec["judge"]["storyline"] == 5
