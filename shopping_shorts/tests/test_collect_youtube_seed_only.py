"""seed_only=True면 키워드 검색을 아예 호출하지 않아야 한다.

왜 이 테스트가 중요한가: 자동 수집(매일 08:10)에 연예 클립이 섞여 들어오던 유일한 경로가
키워드 검색이다. '호출되지 않음'을 직접 확인하지 않으면 조용히 되살아난다.
"""
import shopping_shorts.service as service


def test_seed_only_skips_keyword_search(monkeypatch):
    calls = {"search": 0, "channel": 0}

    def fake_search(*a, **kw):
        calls["search"] += 1
        return []

    def fake_channel(*a, **kw):
        calls["channel"] += 1
        return []

    monkeypatch.setattr(service, "yt_search", fake_search)
    monkeypatch.setattr(service, "yt_fetch_channel", fake_channel)
    monkeypatch.setattr(service, "preset_keywords", lambda cats: ["살림꿀팁"])

    class FakeStore:
        def list_seeds(self, platform):
            return [{"kind": "account", "value": "https://www.youtube.com/channel/UC_test"}]

        def yt_cache_get(self, seed):
            return None

        def yt_cache_put(self, *a):
            pass

        def prev_base_platform(self, *a):
            return None

        def prev_delta_platform(self, *a):
            return None

        def save_run_platform(self, *a):
            pass

        def save_last_run_platform(self, *a):
            pass

    monkeypatch.setattr(service, "Store", lambda *a, **kw: FakeStore())

    service._collect_youtube(categories=None, seed_only=True)

    assert calls["search"] == 0, "seed_only인데 키워드 검색이 호출됐다"
    assert calls["channel"] == 1, "계정 시드 수집이 안 돌았다"


def test_default_still_runs_keyword_search(monkeypatch):
    """기본값(False)은 기존 동작 유지 — 수동 '지금 수집'은 새 채널 발굴에 키워드가 필요하다."""
    calls = {"search": 0}

    monkeypatch.setattr(service, "yt_search", lambda *a, **kw: calls.__setitem__("search", calls["search"] + 1) or [])
    monkeypatch.setattr(service, "yt_fetch_channel", lambda *a, **kw: [])
    monkeypatch.setattr(service, "preset_keywords", lambda cats: ["살림꿀팁"])

    class FakeStore:
        def list_seeds(self, platform):
            return []

        def yt_cache_get(self, seed):
            return None

        def yt_cache_put(self, *a):
            pass

        def prev_base_platform(self, *a):
            return None

        def prev_delta_platform(self, *a):
            return None

        def save_run_platform(self, *a):
            pass

        def save_last_run_platform(self, *a):
            pass

    monkeypatch.setattr(service, "Store", lambda *a, **kw: FakeStore())

    service._collect_youtube(categories=None)

    assert calls["search"] == 1
