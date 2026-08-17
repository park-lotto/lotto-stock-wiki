"""역대 히트작 탭 — 이미 받아둔 아카이브 20만 건에서 크게 터진 것만 꺼낸다.

추가 크롤 0(channel_archive는 수집이 끝나 크론도 꺼져 있다). 실측 2026-08-17:
총 206,672건 중 댓글 1,000+ 14,880 / 3,000+ 5,829 / 5,000+ 3,324 / 10,000+ 1,235.

기간 탭(hits_since)과 소스가 다르다 — 저쪽은 reel_history(30일 롤링), 여기는
channel_archive(누적). 그래서 카테고리·표시명이 없다(아래 걸러내기 미작동).
"""
import pytest

from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    with s._conn() as c:
        for sc, user, views, comments in [
            ("mega", "a", 3_000_000, 50_000),   # 역대급
            ("big", "b", 500_000, 12_000),      # 1만 넘음
            ("mid", "c", 100_000, 2_000),       # 1만 미만
            ("small", "d", 900, 12),            # 잡음
        ]:
            c.execute(
                "INSERT INTO channel_archive(username, shortcode, url, thumbnail,"
                " views, likes, comments, posted_at, first_seen, last_seen)"
                " VALUES(?,?,'','',?,0,?,'2026-07-01',datetime('now'),datetime('now'))",
                (user, sc, views, comments))
    return s


class TestArchiveHits:
    def test_문턱넘은것만(self, store):
        got = {i["shortcode"] for i in store.archive_hits(min_comments=10_000)}
        assert got == {"mega", "big"}

    def test_댓글순_정렬(self, store):
        got = [i["shortcode"] for i in store.archive_hits(min_comments=1_000)]
        assert got == ["mega", "big", "mid"]      # 50000 > 12000 > 2000

    def test_문턱을_낮추면_늘어난다(self, store):
        assert len(store.archive_hits(min_comments=1_000)) == 3

    def test_카드필드가_기간탭과_같은_모양(self, store):
        # 프론트 렌더를 그대로 재사용하려면 키 이름이 같아야 한다
        item = store.archive_hits(min_comments=10_000)[0]
        for k in ("shortcode", "username", "url", "thumb", "views", "comments"):
            assert k in item, f"카드가 쓰는 {k}가 없다"

    def test_thumbnail을_thumb으로_넘긴다(self, store):
        # channel_archive는 컬럼명이 thumbnail — 그대로 주면 카드가 못 읽는다
        assert "thumbnail" not in store.archive_hits(min_comments=10_000)[0]

    def test_limit(self, store):
        assert len(store.archive_hits(min_comments=1, limit=2)) == 2

    def test_결과없어도_안죽는다(self, store):
        assert store.archive_hits(min_comments=999_999) == []


class TestApiWiring:
    def test_archive_파라미터가_store로_간다(self, monkeypatch):
        from shopping_shorts import app as app_mod
        seen = {}

        class _S:
            def archive_hits(self, min_comments=10000):
                seen["min"] = min_comments
                return []

            def removed_usernames(self):
                return set()

        monkeypatch.setattr(app_mod, "Store", lambda *a, **k: _S())
        monkeypatch.setattr(app_mod, "_attach_vision_tags", lambda *a, **k: None)
        monkeypatch.setattr(app_mod, "_attach_durations", lambda *a, **k: None)
        monkeypatch.setattr(app_mod, "_attach_posted_at", lambda *a, **k: None)
        app_mod.api_reference(platform="instagram", archive=1, min_comments=10000)
        assert seen == {"min": 10000}

    def test_archive_기본은_꺼짐(self):
        # 켜져 있으면 첫 화면이 통째로 아카이브가 된다
        import inspect
        from shopping_shorts.app import api_reference
        assert inspect.signature(api_reference).parameters["archive"].default == 0
