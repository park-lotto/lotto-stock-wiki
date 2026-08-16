"""CN 검색 통합 파서 — 폴백·스키마·meta 검증.

★실브라우저·실Apify를 부르지 않는다. 백엔드를 주입해 대체한다
(test_xiaohongshu_playwright.py와 동일 원칙)."""
from shopping_shorts import cn_backends


def test_normalize_fills_all_schema_keys():
    """백엔드가 뭘 빠뜨려도 스키마 키는 전부 채워진다(프론트가 조용히 깨지지 않게)."""
    row = cn_backends.normalize({"url": "https://x.com/1", "title": "t"}, "douyin")
    for key in ("platform", "url", "title", "thumbnail", "play_url",
                "channel", "likes", "views", "duration", "is_short"):
        assert key in row, f"{key} 누락"
    assert row["platform"] == "douyin"
    assert row["likes"] is None          # 없으면 None(0으로 위조하지 않는다)
    assert row["is_short"] is True       # duration 불명 → 숏폼으로 본다
