"""러너 트리거 라우트 — 생성·상태조회(트랙4 Task5). 러너 자체는 monkeypatch."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    # 실 엔진이 안 돌게 러너를 가짜로
    monkeypatch.setattr(app_mod, "run_auto_job",
                        lambda job_id, store, **k: store.update_auto_job(job_id, status="done"),
                        raising=False)
    return TestClient(app_mod.app)


def test_start_creates_job(client):
    r = client.post("/api/auto/start", json={})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["job_id"]


def test_status_returns_job(client):
    jid = client.post("/api/auto/start", json={}).json()["job_id"]
    r = client.get(f"/api/auto/{jid}")
    assert r.status_code == 200
    assert r.json()["id"] == jid


def test_status_missing_404(client):
    assert client.get("/api/auto/없는id").status_code == 404
