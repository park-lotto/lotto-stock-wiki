# -*- coding: utf-8 -*-
"""스타일 목록의 '재료 몇 칸' 표시 — 사장님 아이디어(2026-08-20).

★왜 중요한가: 지금까지는 대본을 **다 돌려본 뒤에야** "재료가 모자랍니다"를 알았다.
  그만큼 기다린 뒤에 안다는 뜻이라, 일단 많이 담고 보게 됐다(무분별 수집).
  고르기 **전에** 몇 칸 차는지 보이면 더 담을지 말지를 그 자리에서 정할 수 있다.

★여기서 모델을 부르면 안 된다 — 드롭다운 한 번 여는 데 담긴 영상 수만큼 Gemini를
  때리게 된다. `cache_only`로 이미 뽑아둔 재료만 쓴다.
"""
import hashlib
import json

import pytest

import shopping_shorts.app as A


INV = {
    "id": 60, "name": "유튜브 발명품형", "fit_categories": ["발명품형"],
    "beat_roles": ["title", "story", "authority", "benefit", "escalate", "twist"],
    "templates": {
        "title": ["{나라} 천재가 만들어 떼돈 번 {제품}의 정체"],
        "story": ["{계기}에서 탄생한 이 제품이 퍼지기 시작했는데",
                  "누가 봐도 평범해 보이는 이 {제품군} 하나가 퍼지기 시작했는데"],
        "authority": ["{나라}에서 바이럴이 터지며 매출이 폭발했다는데"],
        "benefit": ["이게 진짜 말도 안 되는 게 {효능}"],
        "escalate": ["심지어 {효능2}"],
        "twist": ["근데 진짜 충격적인 포인트는 따로 있는데 {효능3}"],
    },
}
SRC = [{"full_text": "나이키 플라이이즈 소개 자막", "structure": {}, "segments": []}]
FULL = {"product_name": "나이키 플라이이즈", "category_word": "신발", "origin_country": "미국",
        "origin_story": "뇌성마비 소년의 편지 한 통",
        "benefits": ["발만 넣으면 1초 착용", "뒤꿈치만 밟으면 벗겨짐", "만성통증 환자도 애용"]}


class _Store:
    """설정 저장소만 흉내 낸다 — 커버리지는 캐시만 읽으므로 이것으로 충분하다."""

    def __init__(self, cache=None):
        self._d = dict(cache or {})

    def get_setting(self, k, default=""):
        return self._d.get(k, default)

    def set_setting(self, k, v):
        self._d[k] = v


def _cached(facts):
    key = "sul_facts1_" + hashlib.md5(
        SRC[0]["full_text"].encode("utf-8")).hexdigest()[:16]
    return _Store({key: json.dumps(facts, ensure_ascii=False)})


def test_분석_전이면_모델을_안_부르고_이유를_말한다():
    """★캐시가 비어도 Gemini를 부르면 안 된다. 부르면 이 테스트가 예외로 죽는다."""
    def _boom(*a, **k):                       # noqa: ANN001
        raise AssertionError("cache_only인데 추출기를 불렀다")

    import shopping_shorts.sul_facts as SF
    orig, SF.analyze_sul = SF.analyze_sul, _boom
    try:
        c = A._spine_cover(INV, SRC, _Store())
    finally:
        SF.analyze_sul = orig
    assert c and c["ready"] is False
    assert "분석 전" in c["why"]


def test_재료가_충분하면_전칸_참():
    c = A._spine_cover(INV, SRC, _cached(FULL))
    assert c == {"done": 6, "total": 6, "missing": [], "ready": True, "why": ""}


def test_장점이_모자라면_이유를_말한다():
    c = A._spine_cover(INV, SRC, _cached({"product_name": "X", "benefits": ["a", "b"]}))
    assert c["ready"] is False and "장점이 2개" in c["why"]


def test_계기가_없어도_전칸_찬다():
    """계기는 필수가 아니다 — 계기를 안 쓰는 story 변형이 대신 걸린다."""
    no_story = {k: v for k, v in FULL.items() if k != "origin_story"}
    c = A._spine_cover(INV, SRC, _cached(no_story))
    assert c["ready"] is True and c["done"] == 6


def test_조립을_안_쓰는_스타일엔_아무것도_안_붙인다():
    """빈 경고를 띄우면 멀쩡한 스타일이 고장 난 것처럼 보인다."""
    other = {"id": 1, "fit_categories": ["레시피"], "beat_roles": ["a", "b"], "templates": {}}
    assert A._spine_cover(other, SRC, _cached(FULL)) is None


def test_같은_갈래는_한_번만_계산한다():
    """★목록 API는 스파인 수만큼 이 함수를 부른다. 캐시가 없으면 같은 슬롯 계산을
    7~10번 반복한다(라이브 실측으로 잡음 — 인스타 재료 조립 로그가 스파인마다 찍혔다).
    드롭다운을 여는 동작이라 그만큼 그대로 기다림이 된다."""
    calls = []
    orig = A._slots_for_spine

    def _counted(*a, **k):
        calls.append(1)
        return orig(*a, **k)

    A._slots_for_spine = _counted
    try:
        cache = {}
        st = _cached(FULL)
        # 같은 갈래(발명품형) 스파인 3개를 잇달아 물어본다
        for i in range(3):
            A._spine_cover(dict(INV, id=60 + i), SRC, st, _cache=cache)
    finally:
        A._slots_for_spine = orig
    assert len(calls) == 1, "갈래가 같은데 %d번 계산했다" % len(calls)
