"""T5 — 검수판 효과음 빼기 엔드포인트 + UI 요소 존재 검증(스펙 §5·§6)."""
import pathlib
import pytest
from fastapi.testclient import TestClient
from shopping_shorts import app as app_mod
from shopping_shorts.store import Store

STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    return TestClient(app_mod.app)


def _job_with_sfx(db):
    s = Store(db)
    s.create_mix_job("j1", ["u"], 20, "free")
    plan = {"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n",
         "sfx": {"asset_id": 5, "match_type": "role", "position": "first"}}]}
    s.update_mix_job("j1", status="ready_for_review", edit_plan=plan)
    return s


# ── 엔드포인트 ─────────────────────────────────────────────────

def test_remove_sfx_drops_beat_sfx(client):
    s = _job_with_sfx(app_mod.DB_PATH)
    r = client.post("/api/produce/mix/j1/sfx", json={"beat_idx": 0})
    assert r.status_code == 200 and r.json()["ok"] is True
    plan = s.get_mix_job("j1")["edit_plan"]
    assert "sfx" not in plan["beats"][0]     # 효과음 제거됨


def test_remove_sfx_404_unknown_job(client):
    r = client.post("/api/produce/mix/nope/sfx", json={"beat_idx": 0})
    assert r.status_code == 404


def test_remove_sfx_422_bad_beat_idx(client):
    _job_with_sfx(app_mod.DB_PATH)
    r = client.post("/api/produce/mix/j1/sfx", json={"beat_idx": 99})
    assert r.status_code == 422


def test_remove_sfx_422_missing_beat_idx(client):
    _job_with_sfx(app_mod.DB_PATH)
    r = client.post("/api/produce/mix/j1/sfx", json={})
    assert r.status_code == 422


# ── UI 요소 존재 ───────────────────────────────────────────────

def test_scene_library_has_role_dropdown():
    html = (STATIC / "scene_library.html").read_text(encoding="utf-8")
    assert 'id="uRole"' in html
    assert "fd.append('role'" in html
    # 통제어휘 7개가 옵션에 있다
    for role in ("훅", "반전", "CTA", "비법공개", "반응", "전환", "본문"):
        assert f'value="{role}"' in html or f'>{role}<' in html


def test_produce_has_sfx_badge_and_toggle():
    html = (STATIC / "produce.html").read_text(encoding="utf-8")
    assert "renderSceneSfx" in html
    assert "removeSfx" in html
    assert "이 효과음 빼기" in html
    assert "/sfx" in html                    # 제거 엔드포인트 호출
    assert 'id="sceneSfx${i}"' in html       # 비트 행에 컨테이너
