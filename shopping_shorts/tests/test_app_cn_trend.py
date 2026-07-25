"""트렌드 검색카드 엔드포인트 /api/reference/cn_trend(2026-07-25).

랭킹 상위 영상의 소재 주제를 강도순 카드로, 캐시된 중국어 번역을 실어 반환.
캐시 미스(zh="")면 프론트가 중국 플랫폼 버튼을 흐리게 처리(폴백 B)."""
from fastapi.testclient import TestClient
import shopping_shorts.app as app_module


def _setup(monkeypatch, insta_items, subj_map, zh_map):
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    monkeypatch.setattr(app_module.Store, "load_last_run", lambda self: (insta_items, "2026-07-25"))
    monkeypatch.setattr(app_module.Store, "load_last_run_platform", lambda self, p: ([], None))
    monkeypatch.setattr(app_module.Store, "vision_tags_map",
                        lambda self, codes: {c: {"subject": subj_map[c], "keywords": []}
                                             for c in codes if c in subj_map})
    monkeypatch.setattr(app_module.Store, "translations_map", lambda self, kos: dict(zh_map))
    return TestClient(app_module.app)


def test_cn_trend_cards_sorted_by_strength_with_translation(monkeypatch):
    items = [
        {"shortcode": "a", "thumbnail": "ta", "url": "ua", "views": 100},
        {"shortcode": "b", "thumbnail": "tb", "url": "ub", "views": 900},
    ]
    client = _setup(monkeypatch, items,
                    {"a": "오이무침", "b": "텀블러건조대"},
                    {"오이무침": "拍黄瓜", "텀블러건조대": "杯架沥水架"})
    r = client.get("/api/reference/cn_trend")
    assert r.status_code == 200
    cards = r.json()["cards"]
    assert [c["subject"] for c in cards] == ["텀블러건조대", "오이무침"]   # 강도(views)순
    assert cards[0]["zh"] == "杯架沥水架" and cards[0]["url"] == "ub"


def test_cn_trend_cache_miss_returns_empty_zh_for_fallback_b(monkeypatch):
    items = [{"shortcode": "a", "thumbnail": "t", "url": "u", "views": 5}]
    client = _setup(monkeypatch, items, {"a": "텀블러건조대"}, {})   # 캐시 미스
    cards = client.get("/api/reference/cn_trend").json()["cards"]
    assert len(cards) == 1
    assert cards[0]["zh"] == ""   # 미스 → "" → 프론트가 중국 버튼 흐리게(B)


def test_cn_trend_dedupes_same_subject(monkeypatch):
    items = [
        {"shortcode": "a", "thumbnail": "t", "url": "ua", "views": 50},
        {"shortcode": "b", "thumbnail": "t", "url": "ub", "views": 80},
    ]
    client = _setup(monkeypatch, items, {"a": "소파", "b": "소파"}, {"소파": "沙发"})
    cards = client.get("/api/reference/cn_trend").json()["cards"]
    assert len(cards) == 1   # 같은 소재는 하나만


def test_cn_trend_skips_items_without_subject(monkeypatch):
    items = [{"shortcode": "a", "thumbnail": "t", "url": "u", "views": 5}]
    client = _setup(monkeypatch, items, {}, {})   # 소재 없음 → 카드 없음
    assert client.get("/api/reference/cn_trend").json()["cards"] == []
