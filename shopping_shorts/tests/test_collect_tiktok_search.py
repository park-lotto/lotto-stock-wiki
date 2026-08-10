"""틱톡 키워드검색 수집(Apify) — **옵트인 경로**의 언어별 시드 검색.

⚠️ 2026-07-24 계약 변경: 키워드 검색은 Apify 건당과금이라 **자동 수집에서 빠졌다**
(사장님 "과금 없는 구조"). `collect(platform='tiktok')`는 이제 무료 계정시드만 돈다
(그 계약은 test_collect_tiktok_free_only.py가 지킨다). 아래 검색 로직 테스트들은
유료 경로를 명시로 켜서(`_collect_tiktok(include_paid_keywords=True)`) 검증한다 —
검색 로직 자체는 그대로 살아 있어야 하므로 테스트를 지우지 않는다.


계정시드(yt-dlp) 경로와 공존한다. 키워드 시드는 kind=언어코드(ko/en/ja/zh/ru)로 저장되며
(비한국어는 등록 시 이미 그 언어로 번역돼 들어옴), service는 저장된 값 그대로 각 언어로
Apify 검색(clockworks/tiktok-scraper). 5개국어 자동확장이 아니라 사용자가 켠 언어만.
결과는 build_tiktok_items→apply_grades로 계정시드 결과와 동일 파이프라인을 탄다."""
from datetime import datetime, timedelta, timezone

from shopping_shorts import service
from shopping_shorts.store import Store

# ★고정 날짜 금지(2026-08-10) — 틱톡 랭킹 창은 WINDOW_HOURS=48시간이다.
#   원래 "2026-07-13"을 박아둬서, 그 날이 이틀 지나자마자 수집 결과가 []가 되고
#   2건이 계속 실패했다(코드가 아니라 날짜 때문에 깨진 시한폭탄).
#   build_*_items가 age > window_hours면 버린다(ranking.py:128).
RECENT = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

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
            "title": kw, "thumbnail": "c", "published_at": RECENT,
            "views": 90000, "likes": 3000, "comments": 100,
        }]

    monkeypatch.setattr(service, "tt_search_full", fake_search_full)

    items = service._collect_tiktok(include_paid_keywords=True)   # 유료 경로 명시로 켬

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

    service._collect_tiktok(include_paid_keywords=True)   # 유료 경로 명시로 켬
    assert captured["max_results"] == 30


def test_collect_tiktok_search_count_defaults_to_50(monkeypatch, tmp_path):
    """설정 없으면 언어당 기본 50개(요청 변경: 60→50)."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(service, "DB_PATH", db)
    Store(db).add_seed("tiktok", "ko", "청소")

    captured = {}
    monkeypatch.setattr(service, "tt_search_full",
                        lambda kw, max_results=50, **_: captured.update(n=max_results) or [])
    service._collect_tiktok(include_paid_keywords=True)   # 유료 경로 명시로 켬
    assert captured["n"] == 50


def test_collect_tiktok_account_seed_still_works(monkeypatch, tmp_path):
    """계정시드(yt-dlp) 경로는 그대로 — keyword 시드가 없으면 기존 동작 유지."""
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(service, "DB_PATH", db)
    Store(db).add_seed("tiktok", "account", "@cleanguru")

    def fake_tt_fetch(acc):
        assert acc == "@cleanguru"
        return [{"video_id": "a1", "url": "u", "channel_title": "cleanguru",
                 "title": "t", "thumbnail": "", "published_at": RECENT,
                 "views": 5000, "likes": 50, "comments": 5}]

    monkeypatch.setattr(service, "tt_fetch", fake_tt_fetch)

    items = service.collect(platform="tiktok")
    assert len(items) == 1
    assert items[0]["shortcode"] == "a1"
