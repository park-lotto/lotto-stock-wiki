"""썰쇼핑 대본 재료 추출 — 템플릿 빈칸과 짝을 맞춘다 (2026-08-19).

사장님 지시: "대본 템플릿은 많이 만들어 놓았으니 **영상들에서 뭘 추출해야 대본을
완성할 수 있는지**만 알면 되는 거니까 그걸 뽑아"

## 왜 이 테스트가 필요한가

템플릿 빈칸과 추출 항목이 **따로 관리되면 반드시 어긋난다**(0순위-B).
실측: 유튜브 스파인 2종이 요구하는 빈칸은 8종인데, 지금 product_facts가 뽑는 것으로는
4종만 채워진다 — 나머지 4종(`본래용도`·`속성`·`용도`·`제품군`)은 **아무도 안 뽑는다.**
빈칸이 안 채워지면 모델이 지어낸다(그게 "AI 티 나는 대본"의 정체다).

    {나라}    ✅ origin        {본래용도}  ❌ 없음
    {제품}    ✅ title         {속성}      ❌ 없음
    {효능}    ✅ why           {용도}      ❌ 없음
    {효능2}   ✅ why           {제품군}    ❌ 없음

이 테스트가 **빈칸 → 추출항목 매핑을 코드로 못박아**, 템플릿에 새 빈칸이 생기면
추출도 같이 늘게 강제한다.
"""
import re
from pathlib import Path

from shopping_shorts import sul_facts

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "tools" / "seed_style_youtube.py"


def _template_slots():
    """유튜브 스파인 시드에서 {빈칸}을 전부 뽑는다."""
    return set(re.findall(r"\{([가-힣0-9]+)\}", SEED.read_text(encoding="utf-8")))


def test_모든_템플릿_빈칸이_추출항목에_매핑돼있다():
    """★이게 깨지면 그 빈칸은 모델이 지어낸다 — 대본이 거짓말을 한다."""
    missing = sorted(_template_slots() - set(sul_facts.SLOT_SOURCE))
    assert not missing, "추출 계획이 없는 빈칸: %s" % missing


def test_오용형_4종이_새로_추가됐다():
    """오용형 스파인의 뼈대 — 이게 없으면 '용도 뒤집기' 서사가 성립 안 한다."""
    for k in ("본래용도", "속성", "용도", "제품군"):
        assert k in sul_facts.SLOT_SOURCE, "%s 매핑 없음" % k


def test_프롬프트가_4종을_실제로_묻는다():
    """매핑만 있고 프롬프트가 안 물으면 영영 빈값이다(조용한 실패)."""
    p = sul_facts.SUL_PROMPT
    for k in ("본래용도", "속성", "용도", "제품군"):
        assert k in p, "프롬프트에 %s 질문 없음" % k


def test_스키마가_프롬프트와_짝이_맞는다():
    """모델이 돌려줄 필드와 우리가 읽을 필드가 어긋나면 통째로 빈다."""
    props = set(sul_facts.SUL_SCHEMA["properties"])
    for k in ("original_use", "hidden_property", "misuses", "category_word"):
        assert k in props, "스키마에 %s 없음" % k


def test_지어내기_금지_문구가_있다():
    """★재료 없이 채우면 '천재가 만든 발명품'류 거짓말이 나온다.

    기존 product_facts도 같은 안전장치를 쓴다(0순위-B: 같은 원칙, 같은 방식)."""
    assert "지어내" in sul_facts.SUL_PROMPT


def test_빈_입력이면_빈dict(monkeypatch):
    """재료가 없으면 조용히 {} — 예외로 대본 생성을 죽이면 안 된다."""
    assert sul_facts.analyze_sul(None) == {}
    assert sul_facts.analyze_sul({}) == {}


def test_prompt_block이_빈값이면_빈문자열():
    """★기존 호출부 규약과 같다 — 빈 문자열이면 회귀 0."""
    assert sul_facts.sul_prompt_block({}) == ""
    assert sul_facts.sul_prompt_block(None) == ""


def test_prompt_block이_뽑은_값을_싣는다():
    facts = {"original_use": ["의류 태그 부착"],
             "hidden_property": ["옷감 손상이 없다"],
             "misuses": ["바지 밑단 줄임", "커튼 길이 조절"],
             "category_word": "택총"}
    out = sul_facts.sul_prompt_block(facts)
    assert "의류 태그 부착" in out
    assert "커튼 길이 조절" in out
    assert "택총" in out


def test_프롬프트_조립이_KeyError로_죽지_않는다():
    """★실사고(2026-08-19): SUL_PROMPT에 설명용 중괄호({본래용도} 등)가 있는데
    `.format(body=...)`을 썼더니 그걸 치환 필드로 보고 KeyError로 죽었다.

    예외를 삼키는 구조라 오류도 안 보이고 **실제 자막 2건이 통째로 빈 dict**였다
    (조용한 실패). 프롬프트+본문 조립이 항상 안전한지 못박는다."""
    body = "이게 원래는 의류 태그 부착용으로 개발된 제품이었음"
    joined = sul_facts.SUL_PROMPT + body          # 실제 코드가 쓰는 방식
    assert body in joined
    assert "{본래용도}" in joined                  # 설명용 중괄호는 그대로 남아야 한다
    # .format을 쓰면 죽는다는 것 자체를 기록해 둔다(다시 도입하지 못하게)
    import pytest
    with pytest.raises(KeyError):
        sul_facts.SUL_PROMPT.format(body=body)


def test_프롬프트가_스펙과_이득을_가른다():
    """★실측 2026-08-19: 스펙만 뽑혀 "충격적인 포인트는 전압 호환이 가능하다"는
    대본이 나왔다. 이 지시가 빠지면 그 사고가 재발한다."""
    from shopping_shorts.sul_facts import SUL_PROMPT
    assert "스펙이 아니라" in SUL_PROMPT
    assert "전압 호환" in SUL_PROMPT          # 나쁜 예를 실측 그대로 박아둔다
    assert "놀라운 순서로 정렬" in SUL_PROMPT


def test_프롬프트가_모델명을_금지한다():
    """"이건 바로 YQQ KRCB 요거트 메이커 및 그릭요거트 스트레이너"가 나왔던 자리다."""
    from shopping_shorts.sul_facts import SUL_PROMPT
    assert "브랜드·모델명을 쓰지 마라" in SUL_PROMPT


# ── 무자막 영상(해외 원본) ────────────────────────────────────────────────
# 사장님 지적(2026-08-19): "결국 외국 무자막에서 장면을 보면서 태깅을 하고
# 그걸로 가능한지를 봐야 하잖아"
# → 그전까지 이 모듈은 자막·캡션만 읽어서 무자막 영상은 재료가 0개였다.
def test_무자막이면_장면태깅이_재료가_된다():
    from shopping_shorts.sul_facts import _body_of
    body = _body_of({"segments": [
        {"scene_desc": "투명 통에 마시는 요거트를 붓는다", "action": "붓기"},
        {"scene_desc": "뚜껑을 눌러 스프링을 압축한다", "change": "유청이 아래로 분리됨"},
    ]})
    assert body, "무자막 영상에서 재료 본문이 안 만들어진다"
    assert "투명 통에" in body and "유청이 아래로 분리됨" in body
    assert "장면1)" in body and "장면2)" in body


def test_자막이_있으면_장면과_함께_쓴다():
    from shopping_shorts.sul_facts import _body_of
    body = _body_of({"captions": ["이건 유청 분리기입니다"],
                     "segments": [{"scene_desc": "요거트를 붓는다"}]})
    assert "이건 유청 분리기입니다" in body and "요거트를 붓는다" in body


def test_장면이_없으면_종전과_같다():
    """회귀 0 — segments를 안 주면 예전과 똑같은 본문."""
    from shopping_shorts.sul_facts import _body_of
    assert _body_of({"captions": ["가나다"]}) == "가나다"


def test_프롬프트가_무자막_판단법을_말한다():
    from shopping_shorts.sul_facts import SUL_PROMPT
    assert "말이 없는 영상" in SUL_PROMPT
    assert "장면에 없는 것은 지어내지 마라" in SUL_PROMPT
