"""틱톡 키워드검색 수집(Apify) — service.collect(platform='tiktok')의 언어별 시드 경로.

계정시드(yt-dlp) 경로와 공존한다. 키워드 시드는 kind=언어코드(ko/en/ja/zh/ru)로 저장되며
(비한국어는 등록 시 이미 그 언어로 번역돼 들어옴), service는 저장된 값 그대로 각 언어로
Apify 검색(clockworks/tiktok-scraper). 5개국어 자동확장이 아니라 사용자가 켠 언어만.
결과는 build_tiktok_items→apply_grades로 계정시드 결과와 동일 파이프라인을 탄다."""
from shopping_shorts import service
from shopping_shorts.store import Store

_LANG_SEED = {"ko", "en", "ja", "zh", "ru"}


def test_collect_tiktok_searches_each_language_seed_directly(monkeypatch, tmp_path):
    """켠 언어(ko, en)만 각각 그 값 그대로 검색 — translate_keyword 자동확장 안 함."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(service, "DB_PATH", db)
    s = Store(db)
    s.add_seed("tiktok", "ko", "곰팡이 제거")     # 한국어 시드
    s.add_seed("tiktok", "en", "mold removal")   # 영어 시드(등록 시 이미 번역돼 들어옴)

    calls = []

    def fake_search_full(kw, max_results=50, **_):
        calls.append(kw)
        vid = "ko1" if kw == "곰팡이 제거" else "en1"
        return [{
            "video_id": vid, "url": f"https://tt/{vid}", "channel_title": "clean",
            "title": kw, "thumbnail": "c", "published_at": "2026-07-13T00:00:00.000Z",
            "views": 90000, "likes": 3000, "comments": 100,
        }]

    monkeypatch.setattr(service, "tt_search_full", fake_search_full)

    items = service.collect(platform="tiktok")

    assert sorted(calls) == ["mold removal", "곰팡이 제거"]
    assert len(items) == 2
    assert all(i["platform"] == "tiktok" for i in items)
    assert all("grade" in i and "score" in i for i in items)
    assert {i["base_count"] for i in items} == {90000}


def test_collect_tiktok_respects_search_count_setting(monkeypatch, tmp_path):
    """언어당 개수는 하드코딩 금지 — settings의 tiktok_search_count(기본 50)를 따른다."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(service, "DB_PATH", db)
    s = Store(db)
    s.add_seed("tiktok", "ko", "청소")
    s.set_setting("tiktok_search_count", "30")

    captured = {}

    def fake_search_full(kw, max_results=50, **_):
        captured["max_results"] = max_results
        return []

    monkeypatch.setattr(service, "tt_search_full", fake_search_full)

    service.collect(platform="tiktok")
    assert captured["max_results"] == 30


def test_collect_tiktok_search_count_defaults_to_50(monkeypatch, tmp_path):
    """설정 없으면 언어당 기본 50개(요청 변경: 60→50)."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(service, "DB_PATH", db)
    Store(db).add_seed("tiktok", "ko", "청소")

    captured = {}
    monkeypatch.setattr(service, "tt_search_full",
                        lambda kw, max_results=50, **_: captured.update(n=max_results) or [])
    service.collect(platform="tiktok")
    assert captured["n"] == 50


def test_collect_tiktok_account_seed_still_works(monkeypatch, tmp_path):
    """계정시드(yt-dlp) 경로는 그대로 — keyword 시드가 없으면 기존 동작 유지."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(service, "DB_PATH", db)
    Store(db).add_seed("tiktok", "account", "@cleanguru")

    def fake_tt_fetch(acc):
        assert acc == "@cleanguru"
        return [{"video_id": "a1", "url": "u", "channel_title": "cleanguru",
                 "title": "t", "thumbnail": "", "published_at": "2026-07-13T00:00:00Z",
                 "views": 5000, "likes": 50, "comments": 5}]

    monkeypatch.setattr(service, "tt_fetch", fake_tt_fetch)

    items = service.collect(platform="tiktok")
    assert len(items) == 1
    assert items[0]["shortcode"] == "a1"
