# -*- coding: utf-8 -*-
"""유튜브 썰: 반말체·CTA금지를 **프롬프트에도** 말해준다 (2026-08-22 사장님).

## 왜 (실측)

사장님 제보: "유튜브는 그냥 말투가 ~했음 이런 거 있잖아. 초반 후킹 말투로 끝까지.
존댓말 없음."

화면이 이미 경고를 띄우고 있었다 — `말끝(반말체)` · `CTA 금지(유튜브 썰)` 둘 다
A안·B안 전부에서 떴다. 그런데 **경고만 하고 아무도 안 고친다**. 이유:

  · `script_gate`에 검사는 있다(`_POLITE_TAILS`, `hook_3s`일 때만)
  · 그런데 **프롬프트 어디에도 "반말로 써라"가 없다**(voice_block이 빈 문자열).
    유튜브 스파인 3개(55·56·60) 전부 `voice` 사전이 비어 있다.
  · 더 나쁜 건 CTA다 — `_STORY_RULES_CORE`가 "댓글에 'OO' 남겨주시면 …드릴게요"를
    **쓰라고 지시**하는데, 게이트는 그걸 쓰면 반려한다. 시켜놓고 벌주는 구조다.

→ 판정만 있고 지시가 없으면 모델은 계속 같은 걸 쓴다. 프롬프트에 못 박는다.

★인스타 스타일은 존댓말·CTA가 정답이므로 **hook_3s/no_cta를 선언한 스타일에만** 건다
  (기본값은 종전 그대로 = 회귀 0).
"""
from shopping_shorts import bank_assemble

YT = {"name": "유튜브 은폐형", "beat_roles": ["title", "bait", "twist"],
      "templates": {}, "chars_per_30s": 270, "hook_3s": True, "no_cta": True}
INSTA = {"name": "가족갈등 반전형", "beat_roles": ["hook", "cta"],
         "templates": {}, "chars_per_30s": 300}


def test_youtube_prompt_says_banmal():
    """유튜브 썰 프롬프트에 반말체 지시가 있다."""
    blk = bank_assemble.style_block(YT, seconds=30)
    assert "반말" in blk, "프롬프트에 반말 지시가 없다 — 게이트만 잡고 아무도 안 고친다"
    for bad in ("거든요", "드릴게요"):
        assert bad in blk, "금지 어미 예시(%s)가 프롬프트에 없다" % bad


def test_youtube_prompt_forbids_cta():
    """유튜브 썰 프롬프트가 CTA를 금지한다(헌장은 쓰라고 시킨다 — 여기서 뒤집는다)."""
    blk = bank_assemble.style_block(YT, seconds=30)
    assert "댓글" in blk and ("쓰지 마라" in blk or "금지" in blk), \
        "CTA 금지 지시가 없다 — 헌장이 시키는 CTA를 그대로 쓴다"


def test_insta_unaffected():
    """인스타는 존댓말·CTA가 정답 — 아무것도 안 붙는다(회귀 0)."""
    blk = bank_assemble.style_block(INSTA, seconds=30)
    assert "반말" not in blk, "인스타에 반말 지시가 붙었다"
