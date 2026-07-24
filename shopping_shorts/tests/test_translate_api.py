"""트렌드카드 번역 API(2026-07-24) — 캐시 우선, 미스 시 translate_keyword 1회."""
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(app_mod.app), app_mod


def test_cache_hit_no_translate_call(client):
    c, app_mod = client
    app_mod.Store(app_mod.DB_PATH).save_translation("빵", "面包")
    with patch("shopping_shorts.video_analysis.translate_keyword") as m:
        r = c.get("/api/translate", params={"q": "빵"})
    assert r.json() == {"ok": True, "ko": "빵", "zh": "面包"}
    m.assert_not_called()


def test_cache_miss_calls_translate_and_saves(client):
    c, app_mod = client
    with patch("shopping_shorts.video_analysis.translate_keyword",
               return_value={"ko": "오이", "zh": "黄瓜"}) as m:
        r = c.get("/api/translate", params={"q": "오이"})
    assert r.json()["zh"] == "黄瓜"
    m.assert_called_once()
    with patch("shopping_shorts.video_analysis.translate_keyword") as m2:
        c.get("/api/translate", params={"q": "오이"})
    m2.assert_not_called()


def test_empty_q(client):
    c, _ = client
    r = c.get("/api/translate", params={"q": "  "})
    assert r.json()["zh"] == ""


def test_too_long_q_rejected(client):
    c, _ = client
    r = c.get("/api/translate", params={"q": "가" * 100})
    assert r.json()["ok"] is False
