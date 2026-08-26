"""소재 일치 게이트 — 출구에서 잡는다(2026-08-18).

지금까지 소재 오염을 막는 방법은 전부 '프롬프트에 경고를 더 넣기'였다. 그건 통로를
하나씩 막는 두더지잡기라, 새 통로가 생기면 또 샌다. 출구는 하나뿐이므로 여기서 잡는다.

★라이브 실측(script_drafts 200건 중 제품명 있는 47건): 통과 34 / 실패 13 = 27.7%.
  실패 13건을 열어보니 오탐이 아니라 진짜 사고였다 —
    네일펜→주방 기름 가림막 / 어린이 카메라→주방 꿀템 / 뷰파인더→발뒤꿈치 각질.
  즉 이 증상은 어제 시작된 게 아니라 계속 나고 있었고, 게이트가 없어 아무도 몰랐다.
"""
from shopping_shorts import script_gate

_STYLE = {"beat_roles": ["hook"], "templates": {}, "chars_per_30s": 300}


def _topic_check(text, product):
    checks, _ = script_gate.check(_STYLE, [{"role": "hook", "text": text}], product=product)
    for c in checks:
        if c["name"] == "소재 일치":
            return c
    return None


def test_소재가_샌_대본을_잡는다():
    """라이브 실측 사고 그대로 — 재료는 네일펜인데 대본이 주방 가림막."""
    c = _topic_check("여러분 요리할 때 주방 벽에 튀는 기름을 가림막으로 막으세요",
                     "다이소 자석 네일펜")
    assert c and c["ok"] is False


def test_제품을_말하면_통과한다():
    c = _topic_check("다이소에서 파는 이 자석 네일펜 아세요", "다이소 자석 네일펜")
    assert c and c["ok"] is True


def test_줄여_부르는_것도_통과한다():
    """'네일펜'을 대본이 '네일'로만 부르는 건 정상 — 오탐이 미탐보다 나쁘다."""
    c = _topic_check("이 네일 하나면 손톱이 살아나요", "다이소 자석 네일펜")
    assert c and c["ok"] is True


def test_제품을_모르면_검사하지_않는다():
    """1단계 분석이 제품을 못 뽑은 소스도 있다 — 그때는 검사 자체를 건너뛴다(회귀 0)."""
    checks, _ = script_gate.check(_STYLE, [{"role": "hook", "text": "아무 말"}])
    assert all(c["name"] != "소재 일치" for c in checks)


def test_한글자_토큰은_버린다():
    """'펜' 같은 조각이 아무 대본에나 걸리면 검사가 무력해진다."""
    assert "펜" not in script_gate._product_tokens("펜 그립")
