# -*- coding: utf-8 -*-
"""'문장틀 준수'는 조립 대본에만 묻는다 (2026-08-22).

## 왜 (실측 근거)

이 검사는 대본을 **템플릿 원문과 글자 단위로 대조**한다(`template_matches`).
조립(`spine_fill`)은 틀을 글자 그대로 쓰므로 옳은 검사다.

그런데 생성기(`script_generate`)는 틀을 **참고만** 하고 문장을 새로 쓴다.
`assemble_off=1`(2026-08-21 사장님 지시)로 지금은 **전부 생성기**를 탄다.
→ 잘 쓸수록 떨어진다. 라이브 실측(08-22, 실제 대본 6편·스콘 소재):

    cta 문장틀 준수         5편 (83%) 실패
    escalation 문장틀 준수  4편 (67%) 실패
    hook 문장틀 준수        4편 (67%) 실패
    → 6편 **전부** 게이트 실패. 비문은 0건인데도.

피해는 두 겹이다:
  ① 화면에 ⚠️ 경고가 잔뜩 떠 **진짜 문제를 덮는다**(무의미한 경고는 안 보게 된다)
  ② 재작성 루프가 "틀에 맞춰라"로 돌아 **생성기의 장점을 도로 깎는다**

★그래서 없애는 게 아니라 **묻는 대상을 가른다**. 조립은 종전대로 검사하고(회귀 0),
  생성기 경로에서는 그 항목을 만들지 않는다. `assembled=True`를 준 호출만 검사한다.
"""
from shopping_shorts import script_gate


STYLE = {
    "beat_roles": ["hook", "cta"],
    "templates": {"hook": ["여러분 (대상)은 무조건 이렇게 하세요"],
                  "cta": ["궁금하면 댓글에 나도 남겨주세요"]},
    "chars_per_30s": 300,
}
# 생성기가 쓴 문장 — 틀의 뼈대는 안 쓰고 소재로 새로 썼다(정상 동작)
FRESH = [{"role": "hook", "text": "스콘은 절대 카페에서 사 먹지 마세요"},
         {"role": "cta", "text": "레시피 궁금하면 댓글에 '스콘' 남겨주시면 보내드릴게요"}]


def _names(checks):
    return [c["name"] for c in checks]


def test_generator_path_has_no_template_check():
    """생성기 경로(기본): '문장틀 준수' 항목 자체를 만들지 않는다."""
    checks, _ = script_gate.check(STYLE, FRESH, seconds=30)
    assert not [n for n in _names(checks) if "문장틀 준수" in n], \
        "생성기 대본에 문장틀 대조가 걸렸다 — 잘 쓸수록 떨어진다: %s" % _names(checks)


def test_assembled_path_still_checks_templates():
    """조립 경로: 종전대로 검사한다(회귀 0). 틀을 안 쓴 문장은 실패해야 한다."""
    checks, _ = script_gate.check(STYLE, FRESH, seconds=30, assembled=True)
    tmpl = [c for c in checks if "문장틀 준수" in c["name"]]
    assert tmpl, "조립인데 문장틀 검사가 사라졌다"
    assert any(not c["ok"] for c in tmpl), "틀을 안 쓴 문장인데 통과했다"


def test_other_checks_unaffected():
    """문장틀 말고 다른 검사는 두 경로 모두 그대로 돈다."""
    gen, _ = script_gate.check(STYLE, FRESH, seconds=30)
    asm, _ = script_gate.check(STYLE, FRESH, seconds=30, assembled=True)
    for nm in ("구간 순서", "CTA 단어유도"):
        assert nm in _names(gen), "%s가 생성기 경로에서 사라졌다" % nm
        assert nm in _names(asm), "%s가 조립 경로에서 사라졌다" % nm
