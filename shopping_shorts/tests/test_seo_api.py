import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts.store import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    s = Store(db)
    s.create_mix_job("job1", ["https://x/1"], 20, "free")
    s.update_mix_job("job1", given_script="대본입니다")
    return TestClient(app_mod.app)


_SEO = {"title": "제목", "title_candidates": [{"text": "A", "why": "w", "keywords": ["kw1"]}],
        "description": "d", "tags": ["t"], "hashtags": {"youtube": [], "tiktok": [], "threads": []},
        "hook_line": "h", "comment_bait": "c",
        "cta": {"youtube": "y", "tiktok": "t", "threads": "th"}}


def test_generate_404_on_missing_job(client):
    r = client.post("/api/produce/seo/generate", json={"job_id": "nope"})
    assert r.status_code == 404


def test_generate_returns_seo_with_stats(client, monkeypatch):
    monkeypatch.setattr(app_mod.seo_generate, "generate", lambda *a, **k: dict(_SEO))
    monkeypatch.setattr(app_mod.seo_probe, "probe_keywords",
                        lambda kws, store, lang="ko": [{"keyword": "kw1", "verdict": "blue",
                                                        "views_median": 300000, "small_ratio": 0.4,
                                                        "top_titles": [], "sample_n": 20}])
    r = client.post("/api/produce/seo/generate", json={"job_id": "job1"})
    assert r.status_code == 200
    seo = r.json()["seo"]
    assert seo["title"] == "제목"
    assert seo["keyword_stats"][0]["verdict"] == "blue"
    assert "generated_at" in seo


def test_generate_502_when_ai_fails(client, monkeypatch):
    monkeypatch.setattr(app_mod.seo_generate, "generate", lambda *a, **k: None)
    r = client.post("/api/produce/seo/generate", json={"job_id": "job1"})
    assert r.status_code == 502


def test_generate_does_not_save(client, monkeypatch):
    """무과금 미리보기 — 저장은 사장님이 확정할 때만(fx/suggest와 같은 규약)."""
    monkeypatch.setattr(app_mod.seo_generate, "generate", lambda *a, **k: dict(_SEO))
    monkeypatch.setattr(app_mod.seo_probe, "probe_keywords", lambda kws, store, lang="ko": [])
    client.post("/api/produce/seo/generate", json={"job_id": "job1"})
    assert Store(app_mod.DB_PATH).get_mix_job("job1")["seo"] is None


def test_generate_only_skips_probe(client, monkeypatch):
    """부분 재생성은 측정을 다시 하지 않는다 — 100유닛짜리를 공짜로 태우면 안 된다."""
    called = []
    monkeypatch.setattr(app_mod.seo_generate, "generate", lambda *a, **k: dict(_SEO))
    monkeypatch.setattr(app_mod.seo_probe, "probe_keywords",
                        lambda kws, store, lang="ko": called.append(kws) or [])
    client.post("/api/produce/seo/generate",
                json={"job_id": "job1", "only": "title",
                      "keyword_stats": [{"keyword": "kw1", "verdict": "red"}]})
    assert called == []


def test_settings_saves_seo(client):
    r = client.post("/api/produce/mix/settings", json={"job_id": "job1", "seo": _SEO})
    assert r.status_code == 200
    assert Store(app_mod.DB_PATH).get_mix_job("job1")["seo"]["title"] == "제목"


def test_settings_404_on_missing_job(client):
    r = client.post("/api/produce/mix/settings", json={"job_id": "nope", "seo": _SEO})
    assert r.status_code == 404
