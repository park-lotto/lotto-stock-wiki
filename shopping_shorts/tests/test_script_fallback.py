# -*- coding: utf-8 -*-
"""생성·검사 실패에도 실패 초안을 재사용하지 않는 장면 근거 출구.

2026-09-25(work 4bd606509402): 이 출구가 중국어 전사·글자 중간 잘림을 대본으로 올렸다 →
한국어 관측만, 어절 경계에서만, 쓸 게 없으면 None.
"""
from shopping_shorts.script_fallback import (build_grounded_fallback, canonical_observations,
                                             humanize_reason, is_korean)


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


def test_fallback_returns_none_when_no_korean_observation():
    """제품명+CTA 두 줄만 남는 안은 대본이 아니다 — None이어야 호출부가 이유를 말한다."""
    assert build_grounded_fallback("접이식 선반", {"items": []}, {}, "AI 응답 없음") is None
    foreign_only = {"items": [
        {"evidence_id": "source:s0:transcript", "kind": "transcript",
         "text": "我 买 了 一个 手 指 快 就是 当 你在 工作"},
        {"evidence_id": "source:s1:transcript", "kind": "transcript",
         "text": "Do you know what these are? These are finger chopsticks."},
        {"evidence_id": "source:s2:transcript", "kind": "transcript", "text": "."},
    ]}
    assert build_grounded_fallback("손가락 젓가락", foreign_only, {}, "503") is None


def test_canonical_observations_drops_untranslated_foreign_transcript():
    """실사고: 중국어 원문 '我 买 了 一个…'가 '반전' 칸에 그대로 올라갔다."""
    rows = canonical_observations({"items": [
        {"evidence_id": "source:s0:transcript", "kind": "transcript",
         "text": "我 买 了 一个 手 指 快 就是 当 你在 工作 刷 想 剧"},
        {"evidence_id": "source:s1:transcript", "kind": "transcript",
         "text": "I love Cheetos, but I hate how the dust sticks to my fingers."},
        {"evidence_id": "source:s2:transcript", "kind": "transcript", "text": "."},
        {"evidence_id": "scene:a:s3:visual", "kind": "visual",
         "text": "손가락 젓가락을 손에 끼워 가볍게 집게질하는 모습"},
    ]})
    assert [r["text"] for r in rows] == ["손가락 젓가락을 손에 끼워 가볍게 집게질하는 모습"]


def test_canonical_observations_drops_unpunctuated_run_on_instead_of_cutting():
    """실사고: 333자 무구두점 전사가 160자에서 '완벽하게 집'으로 잘려 '배경' 칸(16.9초)에 올라갔다.
    어절 경계에서 잘라도 '…개발된 이 제품이'처럼 말이 안 끝난다(라이브 재료 실측) → 버린다."""
    long = ("미국 천재가 만들어 떼돈번 제품의 정체 최근 원래는 젓가락질을 못하는 서양인들을 위해 "
            "개발된 이 제품이 오히려 아시아 포함 전세계 SNS에서 바이럴이 폭발하며 이걸 개발한 미국 "
            "천재가 돈방석에 앉았다는데 이게 말도 안 되는 게 두 손가락을 움직이는 간단한 메커니즘으로 "
            "음식을 완벽하게 집어내는 손가락 젓가락이라는 물건이라 사람들이 놀랐다고 합니다")
    rows = canonical_observations({"items": [
        {"evidence_id": "source:s0:transcript", "kind": "transcript", "text": long},
        {"evidence_id": "scene:a:s3:visual", "kind": "visual",
         "text": "손가락 젓가락을 손에 끼워 가볍게 집게질하는 모습\n손가락에 제품이 장착됨"}]})
    # 장면 관측은 '동작\\n변화' 두 줄 — 한 줄로 뭉치지 않고 각각 남는다
    assert [r["text"] for r in rows] == ["손가락 젓가락을 손에 끼워 가볍게 집게질하는 모습",
                                         "손가락에 제품이 장착됨"]


def test_is_korean():
    assert is_korean("손가락 젓가락 3D 프린터로 만듦")
    assert not is_korean("Do you know what these are?")
    assert not is_korean("我 买 了 一个")
    assert not is_korean(".")


def test_humanize_reason_translates_model_errors():
    assert "503" in humanize_reason("ServerError: 503 UNAVAILABLE. {'error': {'code': 503}}")
    assert "과부하" in humanize_reason("ServerError: 503 UNAVAILABLE")
    assert "월 지출 한도" in humanize_reason("429 RESOURCE_EXHAUSTED ... exceeded its monthly spending cap")
    assert humanize_reason("사실 검사 실패") == "사실 검사 실패"


def test_fallback_reason_is_humanized():
    evidence = {"items": [{"evidence_id": "scene:a:s1:visual", "kind": "visual",
                           "text": "선반을 펼친다."}]}
    result = build_grounded_fallback("접이식 선반", evidence, {}, "ServerError: 503 UNAVAILABLE")
    assert "과부하" in result["fallback_reason"]
    assert "ServerError" not in result["fallback_reason"]


def test_canonical_observations_deduplicates_and_ignores_generated_kinds():
    rows = canonical_observations({"items": [
        {"evidence_id": "scene:a:s1:visual", "kind": "visual", "text": "선반을 펼친다."},
        {"evidence_id": "scene:a:s2:visual", "kind": "visual", "text": "선반을 펼친다."},
        {"evidence_id": "product:0", "kind": "product_fact", "text": "폭은 40cm다."},
        {"evidence_id": "generated:0", "kind": "generated", "text": "무조건 튼튼하다."},
    ]})
    assert [row["text"] for row in rows] == ["선반을 펼친다.", "폭은 40cm다."]
    assert rows[0]["src_seg"] == "s1"
