"""collect(platform='xiaohongshu') 배선 검증 — 크롤러는 monkeypatch로 대체."""
from datetime import datetime, timedelta, timezone
from shopping_shorts import service


def test_collect_xiaohongshu_uses_48h_window_and_saves(monkeypatch):
    store_calls = {}

    class _FakeStore:
        def __init__(self, *a, **kw): pass
        def list_seeds(self, platform):
            assert platform == "xiaohongshu"
            return [{"kind": "account", "value": "https://www.rednote.com/user/profile/u1", "added_at": ""}]
        def prev_base_platform(self, platform, sc): return None
        def prev_delta_platform(self, platform, sc): return None
        def save_run_platform(self, platform, run_date, rows):
            store_calls["save_run_platform"] = (platform, rows)
        def save_last_run_platform(self, platform, items, collected_at):
            store_calls["save_last_run_platform"] = (platform, len(items))

    # 절대 하드코딩 날짜(예: "2026-07-29T00:00:00Z")는 쓰지 않는다 — 실행 시각이 그 시각
    # 이전이면 build_overseas_items가 "미래 타임스탬프"로 판정해 age<0으로 걸러버려
    # 테스트가 시간대에 따라 flaky해진다(실측: 실행 시각 UTC 2026-07-28 17시경에 재현됨).
    # 항상 "1시간 전"으로 계산해 48h 윈도우 안에 안전하게 들어가게 한다.
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _fake_fetch_notes(urls, on_progress=None, _scrape_one=None):
        assert urls == ["https://www.rednote.com/user/profile/u1"]
        return [{"video_id": "n1", "title": "t", "published_at": recent_ts,
                 "views": 0, "likes": 10, "comments": 1, "collects": 0, "shares": 0,
                 "channel_title": "u1", "thumbnail": "", "url": "u",
                 "media_platform": "xiaohongshu", "duration": None}]

    monkeypatch.setattr(service, "Store", _FakeStore)
    monkeypatch.setattr(service, "_xhs_fetch_notes", _fake_fetch_notes)

    items = service.collect(platform="xiaohongshu")
    assert len(items) == 1
    assert items[0]["platform"] == "xiaohongshu"
    assert "save_run_platform" in store_calls
    assert "save_last_run_platform" in store_calls


def test_collect_xiaohongshu_no_seeds_returns_empty(monkeypatch):
    class _FakeStore:
        def __init__(self, *a, **kw): pass
        def list_seeds(self, platform): return []

    monkeypatch.setattr(service, "Store", _FakeStore)
    assert service.collect(platform="xiaohongshu") == []
