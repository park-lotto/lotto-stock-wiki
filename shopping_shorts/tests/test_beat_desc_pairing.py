# -*- coding: utf-8 -*-
"""칸 설명이 빠지면 그 칸은 지시 없이 나간다 — 조용한 구멍 (2026-08-22).

## 왜 필요한가 (실측 근거)

`style_block`은 칸 설명을 `dict(zip(roles, beat_chain))`으로 짝짓는다.
`zip`은 **짧은 쪽에서 조용히 끊긴다** — 오류도 경고도 없다.

라이브 실측(2026-08-22, 서버 DB 43개 스파인):
  · 어긋난 스파인 **10개**
  · id=52 가족갈등 반전형: 칸 10 · 설명 5 → method·result·escalation·regret·**cta**가 설명 없음
  · id=57 다이소 내부인형 등 **6개는 설명이 0개** → 8칸 전부가 이름만 나간다

결과로 모델은 `role="escalation"` 같은 **칸 이름만 보고 추측**한다. 실제 피해(08-21):
  · 단정 명령형 스콘 대본 — witness 칸이 "다들 이 방법으로 편하게 만드시길 바라요"로
    끝나 CTA가 통째로 사라졌다(cta 칸에 설명이 없어 모델이 그 칸을 안 썼다).
  · 사장님 제보 "문장과 문장의 연계가 없다 / 문장 내에서도 말이 안 된다"의 한 축.

★그리고 CTA 지시가 5번 칸(reveal·usage·scale)에 박힌다 — beat_chain 5번째 원소가
  CTA 문구인데 roles 5번째는 중간 칸이라, 짝이 밀려 **중간 칸이 댓글을 유도**한다.
  실측(08-21 13:11 가족갈등 반전형): reveal 칸에 "댓글에 '불꽃' 남겨주시면 좌표
  드릴게요"가 들어가고 cta 칸에서 또 한 번 나왔다.

## 무엇을 못 박는가
1. 설명이 칸보다 적어도 **모든 칸이 프롬프트에 설명을 갖는다**(빈 설명 금지).
2. CTA 문구는 **마지막 칸(cta)에만** 붙는다 — 중간 칸으로 밀리지 않는다.
"""
from shopping_shorts import bank_assemble


# 실측 그대로: 칸 10개인데 설명 5개, 5번째 설명이 CTA 문구(라이브 id=52)
SHORT_CHAIN = {
    "name": "가족갈등 반전형",
    "beat_roles": ["hook", "situation", "notice", "ask", "reveal",
                   "method", "result", "escalation", "regret", "cta"],
    "beat_chain": [
        "가족에게 혼나거나 충격받은 상황을 첫 3초에 던진다",
        "무엇이 문제였는지 — 더러움·불편함을 구체적으로",
        "반전: 알고 보니 제3자 전문가가 알려준 물건이었다",
        "쓰고 나서 어떻게 달라졌는지 — 비포애프터 대비",
        "[댓글 달 수밖에 없는 명분 한 줄] + 댓글에 '(단어)' 남겨주시면 [받는 것] 드릴게요.",
    ],
    "templates": {},
    "chars_per_30s": 300,
}

# 설명이 아예 0개인 스파인(라이브 6개가 이 상태 — 다이소 내부인형 등)
NO_CHAIN = {
    "name": "다이소 내부인형",
    "beat_roles": ["hook", "problem", "reveal", "proof", "demo", "result", "price", "cta"],
    "beat_chain": [],
    "templates": {},
    "chars_per_30s": 300,
}


def _lines(block):
    """프롬프트에서 '  N) role="X" — 설명' 줄만 뽑는다."""
    return [ln for ln in block.split("\n") if ln.strip().startswith(tuple("123456789"))
            and 'role="' in ln]


def _desc_of(block, role):
    for ln in _lines(block):
        if 'role="%s"' % role in ln:
            # '  1) role="hook" — 설명…' 에서 설명만
            return ln.split("—", 1)[1].strip() if "—" in ln else ""
    return None


def test_every_role_has_a_description():
    """칸이 설명보다 많아도 모든 칸에 설명이 붙는다(빈 설명 금지)."""
    block = bank_assemble.style_block(SHORT_CHAIN, seconds=30)
    for role in SHORT_CHAIN["beat_roles"]:
        desc = _desc_of(block, role)
        assert desc is not None, "칸 %s이 프롬프트에 없다" % role
        assert desc, "칸 %s에 설명이 비었다 — 모델이 이름만 보고 추측한다" % role


def test_no_chain_still_describes_every_role():
    """설명이 0개인 스파인도 모든 칸이 설명을 갖는다(라이브 6개가 이 상태)."""
    block = bank_assemble.style_block(NO_CHAIN, seconds=30)
    for role in NO_CHAIN["beat_roles"]:
        desc = _desc_of(block, role)
        assert desc, "칸 %s에 설명이 비었다" % role


def test_cta_instruction_only_on_last_slot():
    """CTA(댓글 유도) 지시는 마지막 칸에만 — 중간 칸으로 밀리지 않는다."""
    block = bank_assemble.style_block(SHORT_CHAIN, seconds=30)
    for role in SHORT_CHAIN["beat_roles"][:-1]:
        desc = _desc_of(block, role) or ""
        assert "남겨주" not in desc, (
            "중간 칸 %s에 CTA 지시가 들어갔다 — 대본 한가운데서 댓글을 유도한다: %s"
            % (role, desc[:60]))
    assert "남겨주" in (_desc_of(block, "cta") or ""), "정작 cta 칸에 CTA 지시가 없다"
