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


def test_translate_new_subjects_caps_and_dedups(client):
    c, app_mod = client
    st = app_mod.Store(app_mod.DB_PATH)
    st.save_translation("빵", "面包")   # 이미 번역됨 → 재호출 안 함
    items = [{"vision_subject": "빵"}, {"vision_subject": "오이"}, {"vision_subject": "감자"}]
    calls = []
    def fake_tr(kw, **kw2):
        calls.append(kw)
        return {"ko": kw, "zh": kw + "_zh"}
    with patch("shopping_shorts.video_analysis.translate_keyword", side_effect=fake_tr):
        app_mod._translate_new_subjects(items)
    assert "빵" not in calls          # 캐시된 건 skip
    assert set(calls) == {"오이", "감자"}
    assert st.get_translation("오이") == "오이_zh"


def test_translate_new_subjects_respects_cap(client, monkeypatch):
    c, app_mod = client
    monkeypatch.setattr(app_mod, "_TRANSLATE_CAP", 1)
    items = [{"vision_subject": "a"}, {"vision_subject": "b"}, {"vision_subject": "c"}]
    with patch("shopping_shorts.video_analysis.translate_keyword",
               side_effect=lambda kw, **k: {"ko": kw, "zh": kw}) as m:
        app_mod._translate_new_subjects(items)
    assert m.call_count == 1          # CAP=1
