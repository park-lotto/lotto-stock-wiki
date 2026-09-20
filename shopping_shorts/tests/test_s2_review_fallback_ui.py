# -*- coding: utf-8 -*-
"""사실검사 폴백 초안이 정상 통과본처럼 보이지 않는지 고정한다."""
from pathlib import Path


HTML = (Path(__file__).parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_review_candidate_has_explicit_fact_warning_not_style_mismatch_copy():
    start = HTML.index("function s2DraftHtml(dr,i)")
    end = HTML.index("// ── ✍ 내가 직접 쓰기", start)
    block = HTML[start:end]
    assert "dr.needs_review" in block
    assert "사실 근거 확인이 필요한 초안" in block
    assert "확정 전 빨간 검사 항목" in block


def test_legacy_modal_also_labels_review_candidate_as_fact_warning():
    start = HTML.index("function _pmChecksHtml(dr)")
    end = HTML.index("function pmRenderDrafts", start)
    block = HTML[start:end]
    assert "if(dr.needs_review)" in block
    assert "사실 근거 확인이 필요한 초안" in block


def test_scene_fallback_explains_that_a_draft_was_recovered():
    start = HTML.index("function s2DraftHtml(dr,i)")
    end = HTML.index("// ── ✍ 내가 직접 쓰기", start)
    block = HTML[start:end]
    assert "dr.made_by==='장면근거'" in block
    assert "장면에서 확인된 내용만 사용해 자동 복구" in block
