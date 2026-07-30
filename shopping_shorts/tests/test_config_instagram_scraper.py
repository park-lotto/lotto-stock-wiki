"""인스타 스크레이퍼 선택 플래그 — 기본값이 apify여야 한다(라이브 안전).

★기본값이 playwright면, 이 브랜치가 병합되는 순간 검증도 안 된 새 경로로
라이브 수집이 통째로 넘어간다. 전환은 서버 환경변수로 명시적으로만 한다.
"""
import importlib


def test_default_scraper_is_apify(monkeypatch):
    monkeypatch.delenv("INSTAGRAM_SCRAPER", raising=False)
    from shopping_shorts import config
    importlib.reload(config)
    assert config.INSTAGRAM_SCRAPER == "apify"


def test_scraper_switchable_by_env(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_SCRAPER", "playwright")
    from shopping_shorts import config
    importlib.reload(config)
    assert config.INSTAGRAM_SCRAPER == "playwright"
    monkeypatch.delenv("INSTAGRAM_SCRAPER", raising=False)
    importlib.reload(config)


def test_proxy_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("INSTAGRAM_PROXY", raising=False)
    from shopping_shorts import config
    importlib.reload(config)
    assert config.INSTAGRAM_PROXY == ""


def test_context_and_timeout_defaults():
    from shopping_shorts import config
    assert config.INSTAGRAM_PW_CONTEXTS == 5
    assert config.INSTAGRAM_PW_TIMEOUT_MS == 20000
