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
