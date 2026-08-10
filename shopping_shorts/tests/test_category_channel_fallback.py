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


# ── AI 재분류가 폴백을 덮지 않는지(2026-07-30 실사고) ────────────────────────
from unittest.mock import patch                                    # noqa: E402
from shopping_shorts import ai_categorize                          # noqa: E402


def test_reclassify_skips_items_without_caption():
    """캡션 없는 항목은 AI에 보내지 않는다 — 근거 없는 '기타'가 폴백을 덮었다."""
    items = [{"category": "홈템", "caption": ""},          # 폴백으로 채워진 항목
             {"category": "기타", "caption": "요리 레시피"}]
    sent = {}

    def fake_batch(batch, **kw):
        sent["idxs"] = [i for i, _ in batch]
        return {i: "레시피" for i, _ in batch}

    with patch.object(ai_categorize.comment_gen, "SHORTS_GEMINI_KEYS", ["k"]), \
         patch.object(ai_categorize, "_classify_batch", fake_batch):
        ai_categorize.reclassify(items)
    assert sent["idxs"] == [1], "캡션 없는 0번이 AI로 갔다"
    assert items[0]["category"] == "홈템", "폴백이 덮였다"


def test_reclassify_ai_기타는_기존값을_지우지_않는다():
    items = [{"category": "홈템", "caption": "무언가"}]
    with patch.object(ai_categorize.comment_gen, "SHORTS_GEMINI_KEYS", ["k"]), \
         patch.object(ai_categorize, "_classify_batch", lambda b, **kw: {0: "기타"}):
        ai_categorize.reclassify(items)
    assert items[0]["category"] == "홈템"
