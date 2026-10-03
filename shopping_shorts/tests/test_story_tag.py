# -*- coding: utf-8 -*-
"""스토리 태깅(2026-10-01 사장님 "태깅부터 대본화"): 1단계가 만들고 2단계가 특징 묶음 자리에 그대로 쓴다."""
from shopping_shorts import story_tag as st, backbone_assemble as ba


def _segs():
    return [{"seg_id": "s1-0", "start": 0, "end": 2, "scene_desc": "계량 구멍에 면", "label": "계량", "use_point": "구멍에 쏙, 1인분 끝", "appeal_kind": "기능", "hook_type": "클로즈업"},
            {"seg_id": "s1-1", "start": 2, "end": 4, "scene_desc": "전자레인지에 넣음", "label": "조리", "use_point": "돌리면 끝", "appeal_kind": "기능"},
            {"seg_id": "s1-2", "start": 4, "end": 7, "scene_desc": "물만 빠짐", "label": "배수", "use_point": "물만 쏙", "appeal_kind": "장점"},
            {"seg_id": "s1-3", "start": 7, "end": 9, "scene_desc": "인사", "label": "마무리", "is_outro": True, "product_benefits": []}]


def test_make_story_validates_and_puts_problem_first():
    out = st.make_story("파스타 쿠커", _segs(), call=lambda p: {"lines": [
        {"text": "돌리면 끝!", "cuts": ["s1-1", "없는컷"], "kind": "기능", "point": "전자레인지"},
        {"text": "냄비 삶기 불편하셨죠?", "cuts": ["s1-0"], "kind": "문제", "point": "불편"},
        {"text": "", "cuts": ["s1-2"]}, {"text": "중복", "cuts": ["s1-1"]}]})
    assert [L["kind"] for L in out] == ["문제", "기능"] and out[1]["cuts"] == ["s1-1"]


def test_rows_hide_outro_and_prompt_has_flavor_rule():
    rows = st._rows(_segs())
    assert all("s1-3" not in r for r in rows) and len(rows) == 3
    assert "말맛" in st.PROMPT and "묘사·보고 문장은 금지" in st.PROMPT


def test_groups_from_stories_merges_same_point_and_skips_problem():
    srcs = [{"video_id": "s1", "source_brief": {"product": "쿠커"}, "story": [
                {"text": "냄비 불편", "cuts": ["s1-0"], "kind": "문제", "point": "불편"},
                {"text": "물만 쏙", "cuts": ["s1-2"], "kind": "장점", "point": "거름망 배수"}]},
            {"video_id": "s2", "story": [{"text": "체 없이 물만 쏙", "cuts": ["s2-5"], "kind": "장점", "point": "거름망 배수"}]}]
    idx = {"s1-0": {"vid": "s1", "secs": 2}, "s1-2": {"vid": "s1", "secs": 3}, "s2-5": {"vid": "s2", "secs": 2}}
    g = st.groups_from_stories(srcs, idx)
    assert g["groups_from"] == "story" and g["product"] == "쿠커"
    assert len(g["groups"]) == 1 and sorted(g["groups"][0]["cuts"]) == ["s1-2", "s2-5"] and g["groups"][0]["kind"] == "장점"


def test_assemble_uses_story_groups_without_ai_grouping(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("스토리가 있는데 build_groups(AI)를 불렀다")
    monkeypatch.setattr(ba, "build_groups", boom)
    srcs = [{"video_id": "s0", "full_text": "씨앗 원문 " * 20, "source_brief": {"product": "쿠커"}, "segments": [{"seg_id": "s0-0", "start": 0, "end": 3, "scene_desc": "씨앗"}]},
            {"video_id": "s1", "story": [{"text": "물만 쏙", "cuts": ["s1-2"], "kind": "장점", "point": "배수"},
                                         {"text": "렌지에 쏙", "cuts": ["s1-1"], "kind": "기능", "point": "조리"},
                                         {"text": "구멍에 딱", "cuts": ["s1-0"], "kind": "기능", "point": "계량"}],
             "segments": [{"seg_id": "s1-0", "start": 0, "end": 2, "scene_desc": "계량"}, {"seg_id": "s1-1", "start": 2, "end": 4, "scene_desc": "렌지"},
                          {"seg_id": "s1-2", "start": 4, "end": 7, "scene_desc": "물만 빠짐"}]}]
    seen = {}

    def fake_write(groups_out, spine, seg_index, *a, **k):
        seen["g"] = groups_out
        return [{"role": "훅", "text": "정체", "group": -1}, {"role": "고조1", "text": "물만 쏙 빠진다", "group": 0}, {"role": "마무리", "text": "끝", "group": -1}]
    monkeypatch.setattr(ba, "write_lines", fake_write)
    monkeypatch.setattr(ba, "pick_hook_spine", lambda *a, **k: {"id": 1, "name": "틀", "fit_categories": []})
    from shopping_shorts import ai_match as _am
    seen_m = {}
    monkeypatch.setattr(_am, "match", lambda *a, **k: seen_m.setdefault("called", True) and [])   # 매칭 전문가가 불리는지만 본다(실패 → 코드 매칭)
    note = {}
    given, bs, meta = ba.assemble(srcs, "s0", store=None, note=note, seed_src=srcs[0])
    assert note["groups_from"] == "story" and seen["g"]["groups"][0]["cuts"] == ["s1-2"]
    assert bs[1]["segs"] == ["s1-2"]
    assert seen_m.get("called") and note["matcher"].startswith("code")     # 고객 기본 경로(백본)도 3단계 매칭 전문가를 부른다


def test_has_stories_majority_and_min_lines():
    L = {"text": "a", "cuts": ["x"]}
    assert st.has_stories([{"story": [L, L, L]}])
    assert st.has_stories([{"story": [L, L, L]}, {"story": []}])            # 절반 이상이면 된다(한 편 빈 응답)
    assert not st.has_stories([{"story": [L, L, L]}, {"story": []}, {"story": []}])
    assert not st.has_stories([{"story": [L]}]) and not st.has_stories([])


def test_feats_from_stories_merges_same_point_across_videos():
    srcs = [{"video_id": "s1", "story": [{"text": "물만 쏙", "cuts": ["s1-2"], "kind": "장점", "point": "거름망 배수"}]},
            {"video_id": "s2", "story": [{"text": "체 없이 물만", "cuts": ["s2-5", "s2-6"], "kind": "장점", "point": "거름망 배수"}]}]
    idx = {"s1-2": {"vid": "s1"}, "s2-5": {"vid": "s2"}, "s2-6": {"vid": "s2"}}
    f = st.feats_from_stories(srcs, idx)
    assert len(f) == 1 and sorted(f[0]["from_cuts"]) == ["s1-2", "s2-5", "s2-6"]


def test_story_survives_storable():
    """스토리는 DB 저장 화이트리스트(script_extract.storable)를 통과해야 한다 — 10-02 실측: 빠져서 배포 뒤 전부 버려졌다."""
    from shopping_shorts import script_extract as se
    story = [{"text": "물만 쏙", "cuts": ["s1-2"], "kind": "장점", "point": "배수"}]
    assert se.storable({"segments": [], "story": story})["story"] == story
    assert se.storable({"segments": []})["story"] == []
