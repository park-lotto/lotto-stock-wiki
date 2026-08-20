# -*- coding: utf-8 -*-
"""가격 칸은 **숫자**여야 한다 — 형용사가 가격 행세를 못 하게 (2026-08-21).

사장님 지적(라이브 작업 b6db20544505 육안):
    "심지어 저렴한 가격밖에 안 하는거있죠? 이건 어떤가"

실제로 두 안 모두 같은 값이 박혀 있었다.
    A안(spine 54) escalation  "심지어 저렴한 가격밖에 안 하는 거 있죠"
    B안(spine 57) price       "심지어 저렴한 가격밖에 안 해서 더 놀랐어요"

{가격} 자리에 들어간 값이 "저렴한 가격" — 숫자가 아니라 **형용사**다.
시청자에게 아무 정보도 안 주면서 "가격을 말했다"는 티만 낸다.

왜 안 걸렸나 — 보호막 두 개를 **둘 다** 비껴간다:
  · 장면 근거 게이트(_SCENE_GATED)   → price는 면제(카메라로 못 찍으니 당연)
  · script_gate 문장틀 검사          → 틀만 보지 값이 말이 되는지는 안 본다
                                       (라이브 로그에 "price 문장틀 준수 ok:true"로 찍혔다)

★프롬프트가 말해도 아무도 검사 안 하면 안 지켜진다 — effects가 명사형으로 새던 것
  (2026-08-19 함정 #3)과 **같은 뿌리**다. 그때는 프롬프트만 고쳤고 price엔 안 했다.
  여기서는 프롬프트가 아니라 **판정**으로 막는다.
"""
from shopping_shorts import insta_facts


# ── 숫자 판정 그 자체 ────────────────────────────────────────────────────
def test_라이브에서_실제로_샌_값을_가격으로_안_본다():
    """이 한 줄이 이 파일의 존재 이유다 — 실제 라이브 값."""
    assert not insta_facts.is_price("저렴한 가격")


def test_숫자_없는_값은_전부_가격이_아니다():
    for s in ("저렴한 가격", "가성비 좋은 가격", "부담 없는 가격",
              "싼 가격", "얼마 안 하는 가격", "저렴해요"):
        assert not insta_facts.is_price(s), s


def test_진짜_가격은_통과시킨다():
    """한글 수사·아라비아 숫자·구어 표현 전부 실제 전사에 나오는 모양이다."""
    for s in ("천 원", "오천 원", "단돈 몇 천 원", "3000원",
              "1,000원", "이천원밖에", "만 원도 안 하는"):
        assert insta_facts.is_price(s), s


def test_숫자만_있고_돈이_아니면_가격이_아니다():
    """'5분'은 numbers 재료지 가격이 아니다 — 숫자만 보면 시간을 가격으로 읽는다."""
    for s in ("5분", "3개", "2주"):
        assert not insta_facts.is_price(s), s


# ── 추출 단계에서 버려지는가 ─────────────────────────────────────────────
def test_가격이_아닌_값은_재료에서_버린다():
    out = insta_facts.drop_fake_price(
        {"price": ["저렴한 가격"], "targets": ["욕실 수전 물때"]},
        log=lambda *a: None)
    assert "price" not in out            # ★빈 리스트로 남기면 "채워졌다"고 본다(spine_fill 규약)
    assert out["targets"] == ["욕실 수전 물때"]


def test_진짜_가격이_섞여_있으면_그것만_남긴다():
    """한 칸에 후보가 여럿이라 하나 버려도 대체가 남는다(외국어 필터와 같은 원칙)."""
    out = insta_facts.drop_fake_price(
        {"price": ["저렴한 가격", "천 원"]}, log=lambda *a: None)
    assert out["price"] == ["천 원"]


def test_버릴_때_이유를_남긴다():
    """재료 없음(정상)과 고장(비정상)은 화면에서 구분돼야 한다(함정 #1)."""
    msgs = []
    insta_facts.drop_fake_price({"price": ["저렴한 가격"]}, log=msgs.append)
    assert any("가격" in m for m in msgs), msgs


def test_다른_칸은_건드리지_않는다():
    """numbers·effects는 숫자 검사 대상이 아니다 — 여기서 거르면 멀쩡한 재료가 죽는다."""
    facts = {"numbers": ["체취의 53퍼센트"], "effects": ["새 것처럼 닦이는"],
             "pain": ["아무리 문질러도 안 지워지던"]}
    assert insta_facts.drop_fake_price(dict(facts), log=lambda *a: None) == facts


def test_가격_칸이_없어도_안전하다():
    assert insta_facts.drop_fake_price({}, log=lambda *a: None) == {}
