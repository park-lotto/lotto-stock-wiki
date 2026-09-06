# -*- coding: utf-8 -*-
"""핀터레스트 기본 검색어 — 원본 적중률 실측으로 갈아끼운다 (2026-09-06).

사장님: "너무 테무 제품영상광고처럼 그런건 별로고 우리 쇼핑쇼츠에 들어갈만한걸 찾는게 핵심"

라이브 2,259건에서 **검색어별 원본 적중률**을 실측했다(6건 이상 수집된 126종).
원본 = pin_dest가 'Uploaded by user' = 쇼핑몰 링크도, 남의 릴스 재업로드도 아닌 것.

    ── 잘 되는 축 ──────────────────      ── 죽은 축 ──────────────────
    temu toilet gadget          100%      temu haul kitchen        0%
    viral shopping finds gadget 100%      temu haul home           0%
    temu shower gadget           88%      temu food container      0%
    weird gadgets that work      87%      temu wrap dispenser      0%
    farm tool invention          87%      temu spice rack          0%
    temu rice gadget             83%      temu rug hack            0%
    construction tool amazing    81%      bread baking asmr        0%(재업 88%)
    temu garden gadget           80%      amazon finds garage      0%

★읽어낸 규칙 (다음에 검색어를 늘릴 때 이 규칙을 따르라):
  ① `<물건> gadget` 꼴 = 원본이 잘 나온다. 실사용 장면 위주.
  ② `haul`(하울) = 언박싱 광고물. 원본 0%.
  ③ `container`·`rack`·`dispenser` 같은 **제품 카테고리명** = 쇼핑몰 광고로 빠진다.
  ④ `asmr` = 인스타 재업로드 88%.

종전 DEFAULT_KEYWORDS엔 **0%짜리 `temu haul kitchen`이 들어 있었고**, 100%짜리
`temu toilet gadget`·`viral shopping finds gadget`은 없었다. 버튼만 눌러도 좋은 게
걸리게 하려면 목록 자체가 실측을 반영해야 한다.
"""
import re
from pathlib import Path

import pytest

from shopping_shorts.pinterest_crawl import DEFAULT_KEYWORDS


# 실측 원본 적중률 0%인 축 — 목록에 있으면 안 된다.
DEAD_PATTERNS = ["haul", "food container", "wrap dispenser", "spice rack",
                 "rug hack", "asmr", "finds garage"]

# 실측 원본 적중률 80%+ — 적어도 몇 개는 목록에 있어야 한다.
PROVEN = ["temu toilet gadget", "viral shopping finds gadget", "temu shower gadget",
          "weird gadgets that actually work", "farm tool invention",
          "temu rice gadget", "construction tool amazing", "temu garden gadget"]


def test_죽은_축이_기본검색어에_없다():
    """★원본 0%짜리를 기본값에 두면 버튼만 누르는 사장님이 광고만 받는다."""
    low = [k.lower() for k in DEFAULT_KEYWORDS]
    bad = [k for k in low for p in DEAD_PATTERNS if p in k]
    assert not bad, f"실측 원본 0%인 검색어가 아직 있다: {sorted(set(bad))}"


def test_실측_상위축이_들어있다():
    """실측 80%+ 축이 최소 5개는 기본값에 있어야 한다."""
    low = {k.lower() for k in DEFAULT_KEYWORDS}
    hit = [p for p in PROVEN if p in low]
    assert len(hit) >= 5, f"실측 상위 축이 {len(hit)}개뿐이다: {hit}"


def test_알리축은_뺐다():
    """실측 465개 쇼핑몰 핀 중 알리는 1개. 핸드오프에도 '통째로 죽었다'고 적혀 있다."""
    low = [k.lower() for k in DEFAULT_KEYWORDS]
    assert not [k for k in low if "aliexpress" in k], \
        f"알리 검색어가 아직 있다(실측 1건): {[k for k in low if 'aliexpress' in k]}"


def test_검색어가_충분하다():
    """수집 버튼 한 번에 도는 개수 — 너무 적으면 한 번에 모이는 양이 적다."""
    assert len(DEFAULT_KEYWORDS) >= 12, f"검색어가 {len(DEFAULT_KEYWORDS)}개뿐"


def test_중복이_없다():
    assert len(DEFAULT_KEYWORDS) == len(set(DEFAULT_KEYWORDS)), "중복 검색어가 있다"


def test_전부_영어_소문자():
    """핸드오프 사장님 결정 3번: '키워드는 영어 먼저'. 핀터레스트 검색이 영어에 강하다."""
    for k in DEFAULT_KEYWORDS:
        assert re.fullmatch(r"[a-z0-9 '\-]+", k), f"영어 소문자가 아닌 검색어: {k!r}"
