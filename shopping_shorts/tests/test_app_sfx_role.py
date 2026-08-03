"""T4 — sfx/overlay role 통제어휘 검증(스펙 §5). 통제어휘 밖 role은 upload·commit에서 422.
빈 role은 허용(매칭 후보에서만 빠짐). clip은 기존 자동태깅 경로라 여기 대상 아님.
"""
import pytest
from fastapi.testclient import TestClient
from shopping_shorts import app as app_mod
from shopping_shorts.store import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(app_mod, "_SCENE_ASSETS_DIR", tmp_path / "scene_assets")
    return TestClient(app_mod.app)


# ── /api/scene/upload ──────────────────────────────────────────

def test_upload_sfx_rejects_role_outside_vocab(client):
    r = client.post("/api/scene/upload",
                    data={"asset_type": "sfx", "title": "띠용", "role": "바나나"},
                    files={"file": ("a.mp3", b"mp3bytes", "audio/mpeg")})
    assert r.status_code == 422 and r.json()["ok"] is False


def test_upload_sfx_valid_role_ok(client):
    r = client.post("/api/scene/upload",
                    data={"asset_type": "sfx", "title": "띠용", "role": "훅"},
                    files={"file": ("a.mp3", b"mp3bytes", "audio/mpeg")})
    assert r.status_code == 200 and r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["role"] == "훅"


def test_upload_sfx_empty_role_ok(client):
    # 빈 role은 허용 — 매칭 후보에서 빠질 뿐 저장은 막지 않는다(스펙 §5).
    r = client.post("/api/scene/upload",
                    data={"asset_type": "sfx", "title": "띠용", "role": ""},
                    files={"file": ("a.mp3", b"mp3bytes", "audio/mpeg")})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_upload_overlay_rejects_bad_role(client):
    # overlay도 통제어휘 강제(파일 처리 전에 422 — 이미지 유효성 무관)
    r = client.post("/api/scene/upload",
                    data={"asset_type": "overlay", "title": "로고", "role": "엉뚱"},
                    files={"file": ("a.png", b"png", "image/png")})
    assert r.status_code == 422 and r.json()["ok"] is False


# ── /api/scene/save/commit ─────────────────────────────────────

def test_commit_sfx_rejects_bad_role(client, tmp_path):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "a" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")
    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "sfx", "title": "띠용",
        "role": "바나나", "source_origin": "짜집기"})
    assert r.status_code == 422 and r.json()["ok"] is False


def test_commit_sfx_valid_role_ok(client, tmp_path, monkeypatch):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "b" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")
    monkeypatch.setattr(app_mod.scene_assets, "extract_audio",
                        lambda clip, out: (out.write_bytes(b"mp3"), out)[1])
    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "sfx", "title": "띠용",
        "role": "반전", "source_origin": "짜집기"})
    assert r.status_code == 200 and r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["role"] == "반전"
