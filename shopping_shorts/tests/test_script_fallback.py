# -*- coding: utf-8 -*-
"""생성·검사 실패에도 실패 초안을 재사용하지 않는 장면 근거 출구."""
from shopping_shorts.script_fallback import build_grounded_fallback, canonical_observations


def test_fallback_uses_only_product_and_canonical_evidence():
    evidence = {"items": [
        {"evidence_id": "scene:ice:s1:visual", "kind": "visual",
         "text": "정수기에서 얼음이 컵으로 떨어진다."},
        {"evidence_id": "source:ice:transcript", "kind": "transcript",
         "text": "물을 받고 얼음을 꺼냅니다."},
        {"evidence_id": "style:bad", "kind": "style",
         "text": "현지에서 품절이라 없어서 못 구합니다."},
    ]}
    result = build_grounded_fallback(
        "올인원 얼음정수기", evidence,
        {"id": 7, "name": "발견형", "beat_roles": ["hook", "show", "cta"]},
        "사실 검사 실패")

    assert result["beats"]
    assert "올인원 얼음정수기" in result["script"]
    assert "얼음이 컵으로 떨어진다" in result["script"]
    assert "품절" not in result["script"]
    assert result["fallback_reason"] == "사실 검사 실패"
    assert result["needs_review"] is True
    assert result["made_by"] == "장면근거"
    assert any(beat.get("src_seg") == "s1" for beat in result["beats"])


def test_fallback_still_returns_one_draft_shape_when_evidence_items_are_empty():
    result = build_grounded_fallback("접이식 선반", {"items": []}, {}, "AI 응답 없음")
    assert result["script"]
    assert len(result["beats"]) >= 2
    assert result["hook"] == result["beats"][0]["text"]
    assert "접이식 선반" in result["script"]
    assert "가격" not in result["script"] and "품절" not in result["script"]


def test_canonical_observations_deduplicates_and_ignores_generated_kinds():
    rows = canonical_observations({"items": [
        {"evidence_id": "scene:a:s1:visual", "kind": "visual", "text": "선반을 펼친다."},
        {"evidence_id": "scene:a:s2:visual", "kind": "visual", "text": "선반을 펼친다."},
        {"evidence_id": "product:0", "kind": "product_fact", "text": "폭은 40cm다."},
        {"evidence_id": "generated:0", "kind": "generated", "text": "무조건 튼튼하다."},
    ]})
    assert [row["text"] for row in rows] == ["선반을 펼친다.", "폭은 40cm다."]
    assert rows[0]["src_seg"] == "s1"
