# -*- coding: utf-8 -*-
"""훅에서 제품 정체를 숨기라고 **프롬프트에도** 말한다 (2026-08-23 사장님).

사장님: "이거라고 특정 제품을 숨겨야 해."

## 왜 (실측)

훅 틀은 "여러분 다이소 가면 **이거** 꼭 사오세요"인데, 실제 생성은 8회 중 6회가
제품명을 넣었다 — "여러분 다이소 가면 **이 앞머리 고데기** 무조건 담아오세요".
'이거'로 가려야 궁금해서 계속 보는데 제품이 나오면 훅이 죽는다.

`script_gate`에 `훅 3초 정체은폐` 검사는 있지만(hook_conceal) **판정만 하고
프롬프트는 침묵한다** — 08-22 반말체 건과 똑같은 구조다(memory:
reference_판정만있고지시없음). 모델은 게이트 결과를 못 보므로 계속 제품명을 쓴다.

★선언한 스타일에만 붙인다(기본 False = 회귀 0).
"""
from shopping_shorts import bank_assemble

CONCEAL = {"name": "다이소", "beat_roles": ["hook", "reveal"], "templates": {},
           "chars_per_30s": 297, "hook_conceal": True}
PLAIN = {"name": "보통", "beat_roles": ["hook", "cta"], "templates": {},
         "chars_per_30s": 300}


def test_conceal_prompt_tells_model():
    """은폐 선언 시 '제품 이름을 쓰지 마라'가 프롬프트에 있다."""
    blk = bank_assemble.style_block(CONCEAL, seconds=25)
    assert "이거" in blk, "가리는 말('이거') 예시가 없다"
    assert ("제품 이름" in blk or "제품명" in blk), "제품명 금지 지시가 없다"


def test_plain_style_unaffected():
    """선언 안 한 스타일엔 안 붙는다(회귀 0)."""
    blk = bank_assemble.style_block(PLAIN, seconds=25)
    assert "제품 이름" not in blk and "제품명" not in blk
