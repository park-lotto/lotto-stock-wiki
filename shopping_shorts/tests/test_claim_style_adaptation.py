# -*- coding: utf-8 -*-
"""주제 잠금 대본에서 스타일의 미입증 사실 문구를 생성 전에 중립화한다."""
from shopping_shorts import bank_assemble


def _style():
    return {
        "id": 54,
        "name": "물건 발견형",
        "beat_roles": ["hook", "origin", "spread", "scale", "price", "easy", "cta"],
        "beat_descs": {
            "hook": "해외에서 난리 난 물건으로 연다",
            "origin": "원래 현지에서만 알던 물건이 만들어진 사연",
            "spread": "어쩌다 소문이 퍼졌는지",
            "scale": "얼마나 화제인지",
            "price": "가격 — 얼마나 부담 없는지",
            "easy": "어떻게 쓰는지",
            "cta": "검색해도 안 나오고 다들 물어봐서 댓글로 알려준다",
        },
        "templates": {
            "hook": ["이걸 줄 서서 산다고요?", "해외에서 난리 난 물건이에요"],
            "origin": ["원래 현지에서만 알던 건데", "이 문제 때문에 만들어진 거예요"],
            "spread": ["입소문이 쫙 퍼지면서"],
            "scale": ["현지에선 품절대란까지 났대요"],
            "price": ["단돈 몇천 원에 해결", "이 값에 된다는 게 말이 됨?",
                      "가격이 싼데도 후기가 만점"],
            "easy": ["펼치기만 하면 끝"],
            "cta": ["댓글에 변기 남겨주시면 링크 드릴게요"],
        },
        "voice": {"tone_note": "신기한 물건을 발견한 말투"},
    }


def _evidence(*rows):
    return {"version": 2, "items": list(rows)}


def _row(kind, text):
    return {"evidence_id": "%s:1" % kind, "kind": kind, "text": text}


def test_unlocked는_기존_style을_그대로_쓴다():
    style = _style()
    assert bank_assemble.fact_aware_style(style, None) is style
    assert bank_assemble.style_block(style, seed="job") == bank_assemble.style_block(
        bank_assemble.fact_aware_style(style, None), seed="job")


def test_근거없는_locked는_role순서와말투를_살리고_사실틀만_뺀다():
    style = _style()
    got = bank_assemble.fact_aware_style(style, _evidence())
    assert got["id"] == style["id"] and got["name"] == style["name"]
    assert got["beat_roles"] == style["beat_roles"]
    assert got["voice"] == style["voice"]
    assert got["templates"]["spread"] == []
    assert got["templates"]["scale"] == []
    assert got["templates"]["price"] == []
    assert got["templates"]["origin"] == []
    assert got["templates"]["easy"] == ["펼치기만 하면 끝"]
    assert got["templates"]["cta"] == ["댓글에 변기 남겨주시면 링크 드릴게요"]
    assert "가격·인기·품절" in got["beat_descs"]["spread"]
    assert "가격·인기·품절" in got["beat_descs"]["cta"]
    assert style == _style(), "prompt용 view를 만들며 DB style 원본을 바꾸면 안 된다"


def test_visual에_가격과품절글자가_보여도_외부사실_style은_안_열린다():
    got = bank_assemble.fact_aware_style(_style(), _evidence(
        _row("visual", "화면에 3,900원, 해외 품절, 입소문이라는 글자가 보인다")))
    assert got["templates"]["price"] == []
    assert got["templates"]["spread"] == []
    assert got["templates"]["scale"] == []
    assert got["templates"]["origin"] == []


def test_입소문근거는_spread만_열고_품절난리까지_확대하지_않는다():
    got = bank_assemble.fact_aware_style(_style(), _evidence(
        _row("transcript", "써 본 사람들의 입소문이 퍼졌다")))
    assert got["templates"]["spread"] == ["입소문이 쫙 퍼지면서"]
    assert got["templates"]["scale"] == []
    assert got["templates"]["hook"] == []


def test_정확한가격은_이값틀만_열고_몇천원과싸다는단정은_열지않는다():
    got = bank_assemble.fact_aware_style(_style(), _evidence(
        _row("product_fact", "확인된 판매가는 12,900원이다")))
    assert got["templates"]["price"] == ["이 값에 된다는 게 말이 됨?"]


def test_강한표현도_그표현의근거가_있을때만_원틀을_살린다():
    got = bank_assemble.fact_aware_style(_style(), _evidence(
        _row("general_fact", "해외 현지에서만 팔리던 제품이 품절대란으로 난리가 났다")))
    assert got["templates"]["scale"] == ["현지에선 품절대란까지 났대요"]
    assert got["templates"]["origin"] == ["원래 현지에서만 알던 건데"]


def test_style68의_price를_비워도_다음칸_그값이_가격을_되살리지_않는다():
    style = {
        "id": 68, "name": "유튜브 「단돈 OO원이면」",
        "beat_roles": ["price", "power", "easy", "extra", "land"],
        "beat_descs": {
            "price": "가격을 첫 문장에 던진다",
            "power": "그 값에 이게 된다는 걸 한 방으로",
            "easy": "쓰기가 얼마나 쉬운지",
            "extra": "심지어로 하나 더",
            "land": "여운을 두고 닫는다",
        },
        "templates": {
            "price": ["단돈 몇천 원에 해결"],
            "power": ["그 값에 이게 된다는 게 말이 됨?"],
            "easy": ["펼치기만 하면 끝"],
            "extra": ["심지어 하나 더"],
            "land": ["이 값이면 안 챙길 이유가 없겠더라", "구경은 해봐야겠더라"],
        },
    }
    got = bank_assemble.fact_aware_style(style, _evidence())
    block = bank_assemble.style_block(got, seconds=25, seed="job")
    assert got["beat_roles"] == style["beat_roles"]
    assert "가격을 첫 문장에" not in block
    assert "그 값에" not in block
    assert "몇천 원" not in block
    assert "이 값이면" not in block
    assert "구경은 해봐야겠더라" in block
