"""collect()가 config 플래그로 스크레이퍼를 고르는지 — 롤백 스위치의 실동작 검증.

★이 스위치가 없으면 새 경로에 문제가 생겼을 때 라이브 인스타 수집을 되돌릴 방법이
코드 revert밖에 없다. 서버 환경변수 하나로 돌아갈 수 있어야 한다.
"""
from shopping_shorts import service


def _stub_channels(monkeypatch, usernames):
    chans = [{"username": u, "name": u, "inpock": "", "followers": 0} for u in usernames]
    monkeypatch.setattr(service, "load_channels", lambda: chans)
    monkeypatch.setattr(service, "select_tracked", lambda c, *a, **k: c)


def test_apify_path_used_by_default(monkeypatch):
    _stub_channels(monkeypatch, ["a"])
    called = {}

    def _apify(u):
        called["apify"] = u
        return []

    def _pw(u, on_progress=None):
        called["pw"] = u
        return []

    monkeypatch.setattr(service.config, "INSTAGRAM_SCRAPER", "apify")
    monkeypatch.setattr(service, "fetch_reels", _apify)
    monkeypatch.setattr(service, "_pw_fetch_reels", _pw)
    service.collect(platform="instagram")
    assert "apify" in called and "pw" not in called


def test_playwright_path_used_when_flag_set(monkeypatch):
    _stub_channels(monkeypatch, ["a"])
    called = {}

    def _apify(u):
        called["apify"] = u
        return []

    def _pw(u, on_progress=None):
        called["pw"] = u
        return []

    monkeypatch.setattr(service.config, "INSTAGRAM_SCRAPER", "playwright")
    monkeypatch.setattr(service, "fetch_reels", _apify)
    monkeypatch.setattr(service, "_pw_fetch_reels", _pw)
    service.collect(platform="instagram")
    assert "pw" in called and "apify" not in called


def test_progress_callback_forwarded_to_playwright(monkeypatch):
    _stub_channels(monkeypatch, ["a"])
    got = {}
    monkeypatch.setattr(service.config, "INSTAGRAM_SCRAPER", "playwright")

    def _pw(usernames, on_progress=None):
        got["cb"] = on_progress
        return []
    monkeypatch.setattr(service, "_pw_fetch_reels", _pw)
    marker = lambda *a: None
    service.collect(platform="instagram", on_progress=marker)
    assert got["cb"] is marker
