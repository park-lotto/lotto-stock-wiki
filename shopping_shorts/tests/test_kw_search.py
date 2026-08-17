"""인스타·틱톡·유튜브 키워드 검색 (2026-08-17).

샤오홍슈·도우인(cn_search)과 **같은 엔진**(search_chain)을 쓰는지, 카드 스키마가
같은지를 못박는다. 네트워크는 안 탄다.
"""
import pytest

from shopping_shorts import kw_backends, kw_search, cn_search, search_chain


# ── 엔진 공용화 (0순위-B) ────────────────────────────────────────

def test_cn_and_kw_share_one_engine():
    """규칙이 두 군데 적히면 언젠가 어긋난다 — 둘 다 search_chain을 쓴다."""
    assert cn_search.search_chain is search_chain
    assert kw_search.search_chain is search_chain


def test_zero_rows_falls_through_to_next_backend():
    """★0건도 폴백 사유다(예외뿐 아니라). CN이 쓰던 A안 규칙이 그대로 살아있나."""
    calls = []

    def empty(kw, n):
        calls.append("empty")
        return []

    def good(kw, n):
        calls.append("good")
        return [{"url": "u", "platform": "x"}]

    rows, meta = search_chain.run_chain([empty, good], "키워드", 5)
    assert calls == ["empty", "good"]
    assert meta["backend"] == "good" and len(rows) == 1


def test_raising_backend_does_not_kill_chain():
    def boom(kw, n):
        raise RuntimeError("죽음")

    def good(kw, n):
        return [{"url": "u"}]

    rows, meta = search_chain.run_chain([boom, good], "키워드", 5)
    assert meta["backend"] == "good" and len(rows) == 1


def test_one_platform_dying_does_not_kill_others():
    def boom(kw, n):
        raise RuntimeError("죽음")

    def good(kw, n):
        return [{"url": "u"}]

    res = search_chain.search_many({"a": [boom], "b": [good]}, "키워드")
    assert res["count"] == 1
    assert res["meta"]["a"]["backend"] is None
    assert res["meta"]["b"]["backend"] == "good"


def test_blank_keyword_costs_nothing():
    """빈 검색어로 유료 백엔드를 때리면 안 된다."""
    called = []
    res = search_chain.search_many(
        {"a": [lambda kw, n: called.append(1) or []]}, "   ")
    assert res == {"items": [], "count": 0, "keyword": "", "meta": {}}
    assert called == []


# ── 해시태그 변환 ────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expect", [
    ("에어프라이어 감자칩", "에어프라이어감자칩"),
    ("#키즈카메라", "키즈카메라"),
    ("air fryer chips!", "airfryerchips"),
    ("   ", ""),
    ("!!!", ""),
])
def test_to_hashtag(raw, expect):
    assert kw_backends.to_hashtag(raw) == expect


def test_instagram_skips_when_tag_is_empty(monkeypatch):
    """태그를 못 만들면 브라우저를 아예 띄우지 않는다(프록시 바이트 낭비 방지)."""
    called = []
    import shopping_shorts.instagram_playwright as ig
    monkeypatch.setattr(ig, "search_hashtag", lambda t: called.append(t) or [])
    assert kw_backends.instagram("!!!", 5) == []
    assert called == []


# ── 카드 스키마가 CN과 같은가 ────────────────────────────────────

_CARD_KEYS = {"platform", "url", "title", "thumbnail", "play_url",
              "channel", "likes", "views", "duration", "is_short"}


def test_instagram_rows_match_lens_card_schema(monkeypatch):
    import shopping_shorts.instagram_playwright as ig
    monkeypatch.setattr(ig, "search_hashtag", lambda t: [
        {"url": "https://www.instagram.com/p/AAA/", "username": "shop",
         "like_count": 12, "play_count": 340},
        {"url": "", "username": "no_url"},        # url 없으면 버린다
    ])
    rows = kw_backends.instagram("키즈 카메라", 5)
    assert len(rows) == 1
    r = rows[0]
    assert _CARD_KEYS.issubset(r.keys()), "렌즈 카드 스키마와 어긋나면 화면이 조용히 깨진다"
    assert r["platform"] == "instagram" and r["channel"] == "shop"
    assert r["likes"] == 12 and r["views"] == 340
    # 길이를 모르는 항목은 숏폼으로 본다 — 모른다고 자르면 멀쩡한 릴스가 사라진다
    assert r["duration"] is None and r["is_short"] is True


def test_youtube_rows_match_schema_and_use_lens_filters(monkeypatch):
    seen = {}
    import shopping_shorts.youtube_search as ys

    def fake(kw, n, duration=None, language=None):
        seen.update(kw=kw, n=n, duration=duration, language=language)
        return [{"url": "https://youtu.be/x", "title": "감자칩", "thumbnail": "t"}]

    monkeypatch.setattr(ys, "search", fake)
    rows = kw_backends.youtube("감자칩", 8)
    assert _CARD_KEYS.issubset(rows[0].keys())
    assert rows[0]["platform"] == "youtube"
    # 렌즈가 이미 쓰는 조건과 같아야 한다(같은 화면에 기준이 두 개면 안 된다)
    assert seen["duration"] == "short" and seen["language"] == "ko"


def test_youtube_quota_exhaustion_returns_empty_not_raise(monkeypatch):
    """★유튜브 쿼터가 말라도 인스타·틱톡 결과까지 같이 죽으면 안 된다."""
    import shopping_shorts.youtube_search as ys

    def boom(kw, n, duration=None, language=None):
        raise RuntimeError("YouTube 키 풀 소진")

    monkeypatch.setattr(ys, "search", boom)
    assert kw_backends.youtube("감자칩", 5) == []


def test_tiktok_missing_token_returns_empty(monkeypatch):
    import shopping_shorts.tiktok_search as ts

    def boom(kw, n):
        raise RuntimeError("tiktok_search: APIFY_TOKEN이 설정되지 않았습니다")

    monkeypatch.setattr(ts, "search", boom)
    assert kw_backends.tiktok("감자칩", 5) == []


def test_tiktok_rows_match_schema(monkeypatch):
    import shopping_shorts.tiktok_search as ts
    monkeypatch.setattr(ts, "search", lambda kw, n: [
        {"url": "https://www.tiktok.com/@a/video/1", "title": "칩", "thumbnail": "t"},
        {"title": "url 없음"},
    ])
    rows = kw_backends.tiktok("감자칩", 5)
    assert len(rows) == 1 and _CARD_KEYS.issubset(rows[0].keys())
    assert rows[0]["platform"] == "tiktok"


# ── 세 플랫폼 합류 ───────────────────────────────────────────────

def test_search_covers_three_platforms(monkeypatch):
    monkeypatch.setattr(kw_search, "_CHAIN", {
        "instagram": [lambda kw, n: [{"url": "i", "platform": "instagram"}]],
        "tiktok": [lambda kw, n: [{"url": "t", "platform": "tiktok"}]],
        "youtube": [lambda kw, n: [{"url": "y", "platform": "youtube"}]],
    })
    res = kw_search.search("감자칩", 8)
    assert res["count"] == 3
    assert set(res["meta"]) == {"instagram", "tiktok", "youtube"}
    assert res["keyword"] == "감자칩"


def test_cost_is_keyed_by_backend_function_name():
    """★비용표는 '플랫폼'이 아니라 **백엔드 함수 이름**으로 찾는다(run_chain이
    fn.__name__으로 조회). 이름을 바꾸면 비용이 조용히 0원으로 보고된다 —
    돈이 새는 걸 화면에서 못 보게 되므로 여기서 못박는다."""
    assert kw_backends.tiktok.__name__ in kw_search._COST
    assert kw_search._COST[kw_backends.tiktok.__name__] > 0


def test_tiktok_cost_surfaces_in_meta(monkeypatch):
    """실제로 meta에 비용이 실려 나오나(프론트가 이 값을 더해 화면에 띄운다)."""
    import shopping_shorts.tiktok_search as ts
    monkeypatch.setattr(ts, "search", lambda kw, n: [
        {"url": "https://www.tiktok.com/@a/video/1", "title": "t"}])
    monkeypatch.setattr(kw_search, "_CHAIN", {"tiktok": [kw_backends.tiktok]})
    res = kw_search.search("감자칩", 5)
    assert res["meta"]["tiktok"]["cost_usd"] == kw_search._COST["tiktok"]


def test_free_platforms_report_zero_cost(monkeypatch):
    """인스타·유튜브는 0원으로 보고돼야 한다(공짜인데 돈이 든 것처럼 보이면 안 된다)."""
    import shopping_shorts.youtube_search as ys
    monkeypatch.setattr(ys, "search", lambda kw, n, duration=None, language=None: [
        {"url": "https://youtu.be/x", "title": "t", "thumbnail": ""}])
    monkeypatch.setattr(kw_search, "_CHAIN", {"youtube": [kw_backends.youtube]})
    res = kw_search.search("감자칩", 5)
    assert res["meta"]["youtube"]["cost_usd"] == 0


def test_real_chain_has_the_three_platforms():
    """실제 배선이 세 플랫폼을 다 갖고 있나(모킹된 테스트만 통과하면 의미 없다)."""
    assert set(kw_search._CHAIN) == {"instagram", "tiktok", "youtube"}
    assert kw_search._CHAIN["instagram"] == [kw_backends.instagram]
    assert kw_search._CHAIN["tiktok"] == [kw_backends.tiktok]
    assert kw_search._CHAIN["youtube"] == [kw_backends.youtube]
