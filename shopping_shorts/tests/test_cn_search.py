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


def test_num_survives_infinity_and_nan():
    """★inf는 ValueError가 아니라 OverflowError다. 여기서 예외가 새면
    백엔드 결과가 통째로 죽는다(2026-08-17 코드리뷰 발견)."""
    for bad in ("inf", "-inf", "nan", float("inf"), 1e400):
        row = cn_backends.normalize({"likes": bad, "duration": bad}, "douyin")
        assert row["likes"] is None, f"{bad!r} → likes가 None이어야 한다"
        assert row["duration"] is None
        assert row["is_short"] is True      # duration 불명 → 숏폼 취급


def test_apify_backend_normalizes_and_swallows_errors(monkeypatch):
    """Apify가 터져도 예외가 밖으로 안 나간다(폴백은 cn_search가 판단)."""
    class Boom:
        @staticmethod
        def search(keyword, max_results=10):
            raise RuntimeError("APIFY_TOKEN이 설정되지 않았습니다")

    monkeypatch.setattr(cn_backends, "douyin_search", Boom)
    assert cn_backends.apify_douyin("蒜泥保存", 8) == []


def test_apify_backend_maps_rows(monkeypatch):
    class Ok:
        @staticmethod
        def search(keyword, max_results=10):
            return [{"url": "https://www.douyin.com/video/1", "title": "t",
                     "likes": "12", "duration": 30}]

    monkeypatch.setattr(cn_backends, "douyin_search", Ok)
    rows = cn_backends.apify_douyin("蒜泥保存", 8)
    assert len(rows) == 1
    assert rows[0]["platform"] == "douyin"
    assert rows[0]["likes"] == 12
    assert rows[0]["is_short"] is True
