"""캡션 없는 수집에서도 카테고리가 '기타'로 몰리지 않는지(2026-07-30).

배경: 429 회피로 릴스 상세 REST를 끄면서 캡션이 사라졌고, 캡션 기반 categorize가
289건 중 277건을 '기타'로 판정했다. 채널 대표 카테고리를 폴백으로 쓴다.
"""
from datetime import datetime, timezone

from shopping_shorts.ranking import build_items, _category_of


def _now():
    return datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def _reel(caption=""):
    return {"shortcode": "DbZPKc2TKHC", "timestamp": "2026-07-30T09:00:00Z",
            "commentsCount": 10, "caption": caption}


def test_caption_없으면_채널_카테고리를_쓴다():
    meta = {"name": "someone", "username": "someone", "followers": 100, "category": "홈템"}
    out = build_items([_reel()], meta, prev_comments=lambda s: None,
                      prev_delta=lambda s: None, now=_now())
    assert out[0]["category"] == "홈템"


def test_caption_판정이_되면_캡션이_우선():
    # 캡션에 뚜렷한 신호가 있으면 채널 카테고리보다 개별 릴스 판정을 믿는다
    meta = {"name": "someone", "username": "someone", "followers": 100, "category": "홈템"}
    guess = _category_of(meta, {"caption": "오늘 저녁 레시피 만드는 법 요리"})
    assert guess != "홈템"


def test_채널_카테고리도_없으면_기타():
    meta = {"name": "someone", "username": "someone", "followers": 100}
    assert _category_of(meta, {"caption": ""}) == "기타"
    meta2 = dict(meta, category="   ")      # 공백만 있는 값도 없는 것으로 친다
    assert _category_of(meta2, {"caption": ""}) == "기타"
