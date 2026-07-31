"""장면 스파인 먼저 재설계 (2026-07-29).

카테고리별 spine 슬롯 순서로 태깅된 장면을 먼저 배치 → 그 순서에 대본을 얹는다.
설계: docs/superpowers/specs/2026-07-29-장면스파인-먼저-재설계-design.md
"""
from shopping_shorts import edit_plan as ep
from shopping_shorts import script_extract as se


# ── ① VIDEO_TYPES 5개 + spine ────────────────────────────────────────────────
def test_video_types_has_five_with_spine():
    for k in ("recipe", "kitchen_tool", "beauty", "cleaning", "generic"):
        assert k in ep.VIDEO_TYPES, f"{k} 누락"
        vt = ep.VIDEO_TYPES[k]
        assert vt.get("spine"), f"{k} spine 없음"
        # 각 슬롯은 이름(slot)과 허용 역할(roles) 리스트를 가진다
        for slot in vt["spine"]:
            assert slot.get("slot") and isinstance(slot.get("roles"), list)
    # 모든 스파인은 마지막 슬롯이 CTA(끝에 CTA 보장)
    for k, vt in ep.VIDEO_TYPES.items():
        if "spine" in vt:
            assert vt["spine"][-1]["slot"] == "CTA", f"{k} 마지막이 CTA 아님"


def test_default_type_is_generic():
    assert ep._DEFAULT_TYPE == "generic"


def test_old_type_keys_alias_fail_open():
    """옛 캐시 key(recipe_secret/product_reveal)는 새 key로 매핑돼 살아남아야."""
    assert ep._normalize_video_type("recipe_secret") == "recipe"
    assert ep._normalize_video_type("product_reveal") in ep.VIDEO_TYPES
    assert ep._normalize_video_type("없는키") == ep._DEFAULT_TYPE
    assert ep._normalize_video_type("beauty") == "beauty"


# ── ② shot_role 어휘 확장 + fail-open ────────────────────────────────────────
def test_shot_role_enum_expanded():
    enum = se._RESPONSE_SCHEMA["properties"]["segments"]["items"]["properties"]["shot_role"]["enum"]
    for v in ("before", "사용중", "after", "완성", "문제", "기타"):
        assert v in enum


def test_old_shot_role_maps_fail_open():
    """옛 추출본의 '조리'는 '사용중'으로 흡수(크래시·누락 금지)."""
    out = se._assign_seg_ids("v", [{"text": "x", "shot_role": "조리"}])
    assert out[0]["shot_role"] == "사용중"
    # 알 수 없는 값은 '기타'로
    out2 = se._assign_seg_ids("v", [{"text": "x", "shot_role": "괴상"}])
    assert out2[0]["shot_role"] == "기타"


# ── ③ _build_scene_spine — 태깅 장면을 슬롯 순서로 배치 ──────────────────────
def _seg(sid, start, end, role="기타", key=False, desc="화면"):
    return {"seg_id": sid, "start": start, "end": end, "text": "말",
            "scene_desc": desc, "shot_role": role, "is_key": key}


def test_build_scene_spine_orders_by_slots():
    """recipe 스파인(완성훅→재료→과정→완성샷→CTA) 순서로 seg가 배치돼야."""
    segs = [_seg("s1-0", 0, 2, role="사용중", desc="재료 붓기"),
            _seg("s1-1", 2, 4, role="사용중", desc="반죽 치대기"),
            _seg("s1-2", 4, 6, role="완성", key=True, desc="완성 모찌"),
            _seg("s1-3", 6, 8, role="기타", desc="인사")]
    spine = ep._build_scene_spine({s["seg_id"]: s for s in segs}, "recipe")
    # 첫 슬롯(완성훅)은 완성/is_key 장면을 당겨온다
    assert spine[0]["seg_id"] == "s1-2"
    # 순서는 스파인 슬롯 순서를 따른다(슬롯 이름 확인)
    names = [b["slot"] for b in spine]
    assert names[0] == "완성훅" and names[-1] == "CTA"


def test_build_scene_spine_empty_inventory_no_crash():
    assert ep._build_scene_spine({}, "recipe") == []


def test_build_scene_spine_unknown_category_falls_back():
    """알 수 없는 카테고리는 generic 스파인으로 폴백(렌더 안 깨짐)."""
    segs = [_seg("s1-0", 0, 2, role="완성", key=True)]
    spine = ep._build_scene_spine({s["seg_id"]: s for s in segs}, "없는카테고리")
    assert spine and spine[-1]["slot"] == "CTA"


# ── ④ 스파인 순서 고정 제약이 프롬프트에 실린다 ──────────────────────────────
def test_spine_block_renders_fixed_order():
    spine = [{"slot": "완성훅", "seg_id": "s1-2", "scene_desc": "완성 모찌"},
             {"slot": "CTA", "seg_id": "s1-3", "scene_desc": "인사"}]
    block = ep._spine_order_block(spine)
    assert "완성훅" in block and "s1-2" in block
    assert "순서" in block and "고정" in block   # 순서 고정 지시


def test_spine_block_empty_when_no_spine():
    assert ep._spine_order_block([]) == ""


# ── ⑤ 기본 경로(backbone_base off)가 스파인 블록을 실제로 주입한다 ──────────
def test_default_path_injects_block_mix_then_spine_fallback():
    """라이브 기본 경로(2026-07-31~): **덩어리 믹스**(훅/스토리/CTA 연속 구간 + 글자수 예산)가
    프롬프트에 실린다. 옛 스파인 블록은 덩어리를 못 만들 때의 폴백이다.

    바뀐 이유: 스파인은 "이 순서 고정"이라고 말만 하고 지켰는지 **검사하지 않아** 매번
    다르게 나왔다. 덩어리 믹스는 화면 배정을 코드가 강제한다(_assign_blocks).
    """
    sources = [{"video_id": "s1", "full_text": "본문", "segments": [
        {"seg_id": "s1-0", "start": 0, "end": 2, "text": "인트로", "scene_desc": "인트로", "shot_role": "기타"},
        {"seg_id": "s1-1", "start": 2, "end": 4, "text": "재료", "scene_desc": "재료 붓기", "shot_role": "사용중"},
        {"seg_id": "s1-2", "start": 4, "end": 6, "text": "완성", "scene_desc": "완성 접시",
         "shot_role": "완성", "is_key": True},
        {"seg_id": "s1-3", "start": 6, "end": 8, "text": "끝", "scene_desc": "인사", "shot_role": "기타"}]}]
    seen = {}

    def _cap(prompt, schema):
        seen["prompt"] = prompt
        return {"candidates": [{"hook": "h", "beats": [
            {"role": "훅", "narration": "완성부터 보여드릴게요", "seg_ids": ["s1-2"], "fit": 5}]}]}
    ep.build_scene_first_plan(sources, "ref", 20, n_candidates=1, call=_cap,
                              video_type="recipe", backbone_base=False)
    p = seen["prompt"]
    # 2026-07-31 최종: 기본 경로 = **리라이트 믹스**(원본 타임라인 뼈대 + 문장만 갈아끼우기).
    # 덩어리 믹스(BLOCK_MIX)와 옛 스파인은 그 뒤 폴백이다.
    assert "원본이 하던 말을 우리 말로 바꿔 쓴다" in p
    assert "원본이 한 말:" in p and "자 이내" in p       # 그 자리의 원본 대사 + 글자수 예산
    assert "화면 순서 뼈대" not in p             # 백본 블록은 안 쓴다(기본 경로)
