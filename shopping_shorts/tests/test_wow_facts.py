# -*- coding: utf-8 -*-
"""영상 밖의 신기한 정보(wow_facts) — 대본에 "볼 이유"를 넣는 단계 (2026-09-09).

■ 왜 생겼나 — 사장님이 유튜브 21~26분 구간을 짚으며: "이렇게 간단하게 노가다로만
  해도 이런데 우리는 뭔가?"

  그 노가다의 가운데 단계가 우리에게 **없었다**. 대본 경로 전체에 웹검색 grounding이
  한 줄도 없었다(실측 grep 0건). 그래서 대본은 화면에 이미 보이는 것만 다시 말했고,
  사장님 말로 "사람들이 보게 해야 할 이유가 없어"가 됐다.

■ 여기서 못박는 계약
  · 근거 없는 훅은 **버린다** — 근거가 없으면 그건 지어낸 것이고, 대본에 박히면 거짓말이다
  · 못 찾으면 [] — 대본은 종전대로 나온다(fail-open · 회귀 0)
  · 프롬프트 블록이 비면 '' — 호출부는 그대로 두면 회귀 0
  · 429가 나면 키를 돌려 재시도한다(실측: 4개 연속 429 후 5번째 성공)
"""
from shopping_shorts import wow_facts


def test_근거_없는_훅은_버린다():
    """★대본에 박히면 거짓말이 된다 — 이게 이 파일의 존재 이유다."""
    out = wow_facts.find("오픈형 이어폰", _call=lambda p: """[
      {"hook": "귀를 막지 않는데 옆 사람한테는 안 들린다", "why": "지향성 음향이라 귓구멍으로만 쏜다"},
      {"hook": "근거가 없는 주장", "why": ""}
    ]""")
    assert len(out) == 1
    assert out[0]["hook"].startswith("귀를 막지")


def test_코드펜스와_앞뒤_설명이_붙어와도_건져낸다():
    """웹검색을 켜면 response_schema를 못 쓴다(제미니 제약) — 그래서 직접 판다."""
    out = wow_facts.find("미니 세탁기", _call=lambda p: (
        '알겠습니다! 정리해 드릴게요.\n```json\n'
        '[{"hook": "속옷만 따로 빠는 나라가 있다", "why": "위생 기준이 달라서"}]\n```\n도움이 되셨나요?'))
    assert len(out) == 1 and out[0]["hook"]


def test_못_찾으면_빈_목록이고_대본은_그대로():
    assert wow_facts.find("아무거나", _call=lambda p: "죄송합니다 찾지 못했습니다") == []
    assert wow_facts.find("", _call=lambda p: "[]") == []


def test_호출이_죽어도_대본을_막지_않는다():
    def _boom(p):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")
    assert wow_facts.find("이어폰", _call=_boom) == []


def test_블록이_비면_빈_문자열():
    """호출부가 그대로면 회귀 0이어야 한다(다른 재료 모듈과 같은 규약)."""
    assert wow_facts.wow_prompt_block([]) == ""
    assert wow_facts.wow_prompt_block(None) == ""


def test_블록은_하나만_고르라고_말한다():
    """★세 개를 다 넣으면 대본이 지식 나열이 된다 — 그건 또 다른 실패다."""
    b = wow_facts.wow_prompt_block([{"hook": "가", "why": "나"}, {"hook": "다", "why": "라"}])
    assert "하나만" in b and "나열하지 마라" in b
    assert "가" in b and "다" in b


def test_상한을_넘겨_받아도_잘라낸다():
    many = "[" + ",".join('{"hook":"h%d","why":"w"}' % i for i in range(9)) + "]"
    assert len(wow_facts.find("x", _call=lambda p: many)) == wow_facts.WOW_N


def test_프롬프트가_스펙나열을_금지한다():
    """이 문구가 빠지면 모델이 배터리 용량·색상 같은 화면에 보이는 걸 준다."""
    p = wow_facts.WOW_PROMPT.format(subject="이어폰", n=3)
    assert "스펙 나열은 쓸모없다" in p
    assert "영상에 안 나온 지식" in p


def test_키를_넉넉히_돌린다(monkeypatch):
    """사장님: "키배치를 여유있게 하는 걸로 해" (2026-09-09).

    실측에서 4개 연속 429였고 5번째에 성공했다. 6회로 묶으면 키가 붐비는 시간엔
    그대로 빈손이 된다 — 살아있는 키 수만큼 돈다(상한 _MAX_TRIES).
    """
    assert wow_facts._MAX_TRIES >= 20
    src = wow_facts.find.__doc__ or ""
    import inspect
    body = inspect.getsource(wow_facts.find)
    assert "_live_key_indices" in body, "키 수를 안 보고 고정 횟수만 돈다"
    assert "_MAX_TRIES" in body
