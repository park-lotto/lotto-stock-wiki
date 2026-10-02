# -*- coding: utf-8 -*-
"""각 단계 전문가 지침서(2026-10-02 사장님 "영상추출분석 전문가 / 영상대본작가 / 장면매칭 전문가 — 지침서가 확실하게").
지침서 문구가 실제 프롬프트에 붙는지 본다(상수만 있고 안 붙으면 아무것도 안 바뀐다)."""
import inspect

from shopping_shorts import script_extract as se, backbone_assemble as ba, ai_match as am


def test_stage1_analyst_brief():
    g = se._SEG_FIELD_GUIDE
    assert "영상 추출·분석 전문가" in g and "밑작업" in g and "꼭 필요한가" in g


def test_stage2_writer_brief_on_all_three_prompts():
    assert "영상 대본 작가" in ba.WRITER_BRIEF and "장면 매칭 전문가" in ba.WRITER_BRIEF
    for fn in (ba._spine_prompt, ba.write_lines, ba.write_lines_from_origin):
        assert "WRITER_BRIEF" in inspect.getsource(fn), fn.__name__


def test_stage3_matcher_brief():
    assert "대본과 장면을 딱 맞게 배치하는 최고 전문가" in am.BRIEF


def test_stage2_writer_brief_on_customer_path_with_one_style():
    """고객 경로(이야기작가 write)도 같은 대본 작가 지침서 + 스타일 하나. 지위 문구('너는')는 지침서에만 — 두 번 말하지 않는다."""
    from shopping_shorts import story_writer as sw
    seen = {}
    def fake(prompt, schema, **k):
        seen.setdefault("p", []).append(prompt)
        return {}
    sw._sg._call_json, _orig = fake, sw._sg._call_json
    try:
        for plat in ("yt", "ig"):
            try:
                sw.write("거치대", "씨앗", [{"name": "a", "claim": "고리 쓱", "from_cuts": ["s1-0"]}], platform=plat)
            except Exception:
                pass
    finally:
        sw._sg._call_json = _orig
    ps = seen.get("p") or []
    assert len(ps) >= 2
    for p in ps:
        assert p.startswith(ba.WRITER_BRIEF) and p.count("너는") == 1
    assert "유튜브 썰쇼핑" in ps[0] and "인스타 릴스 체험담" not in ps[0]
    assert "인스타 릴스 체험담" in ps[-1] and "유튜브 썰쇼핑" not in ps[-1]
