import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts.store import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    return TestClient(app_mod.app)


def test_inline_sources_used_without_wiki_lookup(client, monkeypatch):
    """sources가 body에 오면 위키 조회 없이 그 대본으로 조합한다(레퍼런스랭킹 임시 대본)."""
    captured = {}

    def fake_generate_mix(sources, target_seconds=20, n=3):
        captured["sources"] = sources
        captured["target_seconds"] = target_seconds
        captured["n"] = n
        return [{"text": "믹스 결과"}]

    monkeypatch.setattr(app_mod.script_generate, "generate_mix", fake_generate_mix)

    inline_sources = [
        {"name": "영상A", "full_text": "대본A 본문입니다"},
        {"name": "영상B", "full_text": "대본B 본문입니다"},
    ]
    r = client.post("/api/produce/script/mix", json={
        "sources": inline_sources, "target_seconds": 30, "n": 2,
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # 조합 초안도 이제 save_draft로 draft_id를 부여받는다(요소 업그레이드 전제, 2026-07-19).
    # 그래서 응답 초안은 원본 필드 + draft_id — 정확일치 대신 text 유지 + draft_id 부여를 본다.
    drafts = r.json()["drafts"]
    assert len(drafts) == 1
    assert drafts[0]["text"] == "믹스 결과"
    assert drafts[0].get("draft_id")
    assert captured["sources"] == inline_sources
    assert captured["target_seconds"] == 30
    assert captured["n"] == 2


def test_inline_sources_with_empty_full_text_excluded_and_422(client, monkeypatch):
    """full_text 없는 원소는 제외되고, 남은 게 2개 미만이면 422."""
    monkeypatch.setattr(app_mod.script_generate, "generate_mix",
                        lambda *a, **k: pytest.fail("generate_mix should not be called"))

    inline_sources = [
        {"name": "영상A", "full_text": "대본A 본문입니다"},
        {"name": "영상B", "full_text": ""},
    ]
    r = client.post("/api/produce/script/mix", json={"sources": inline_sources})
    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_no_sources_falls_back_to_wiki_shortcodes(client):
    """sources 없이 shortcodes만 있으면 기존 위키 경로(위키에 없으면 422)."""
    r = client.post("/api/produce/script/mix", json={"shortcodes": ["sc1", "sc2"]})
    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_no_sources_and_less_than_two_shortcodes_422(client):
    r = client.post("/api/produce/script/mix", json={"shortcodes": ["sc1"]})
    assert r.status_code == 422
