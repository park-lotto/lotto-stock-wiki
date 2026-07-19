"""검수판 API — 비트 컷어웨이 토글(설정/제거).

⚠️ mix_jobs 테이블에는 customer_id 컬럼이 없다(store.py CREATE TABLE mix_jobs 확인,
2026-07-18). job_id는 uuid라 추측 불가능한 다리일 뿐 — 다른 /api/produce/mix/... 라우트
(start/settings/bgm/overlay/poster)도 전부 "존재하면 통과"만 검사하고 customer_id 대조는
안 한다. 그래서 실제 소유권 경계는 scene_assets(고객별 격리 테이블)에 있다: 컷어웨이를
"설정"할 때 남의 asset_id를 못 붙이게 get_scene_asset(customer_id=...)로 막는 것이
이 시스템에서 진짜 존재하는 격리다. job 자체에 대한 404는 "존재하는지"만 본다(기존 패턴과 동일).
"""
import pytest
from fastapi.testclient import TestClient
from shopping_shorts import app as app_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    from shopping_shorts.store import Store
    db = tmp_path / "t.db"
    Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    return TestClient(app_mod.app), Store(db)


def _job_with_beat(store):
    plan = {"structure": "t", "beats": [
        {"beat_idx": 0, "narration": "감자", "target_seconds": 2.0, "role": "본문",
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0, "end": 2},
         "alternates": [], "effect": "cut", "fit": 0}]}
    jid = "job" + "0" * 9  # 12자리 job_id 형식(uuid4().hex[:12])과 자릿수만 맞추면 됨
    store.create_mix_job(jid, urls=["https://example.com/v.mp4"], target_seconds=30,
                         structure="free")
    store.update_mix_job(jid, edit_plan=plan, status="ready_for_review")
    return jid


def _asset(store, customer_id=0):
    return store.add_scene_asset({
        "asset_type": "cutaway", "render_mode": "video", "media_path": "x.mp4",
    }, customer_id=customer_id)


def test_toggle_sets_and_clears_cutaway(client):
    c, store = client
    jid = _job_with_beat(store)
    asset_id = _asset(store, customer_id=0)
    # 설정
    r = c.post(f"/api/produce/mix/{jid}/cutaway", json={"beat_idx": 0, "asset_id": asset_id})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert store.get_mix_job(jid)["edit_plan"]["beats"][0]["cutaway"]["asset_id"] == asset_id
    # 제거
    r = c.post(f"/api/produce/mix/{jid}/cutaway", json={"beat_idx": 0, "asset_id": None})
    assert r.status_code == 200
    assert "cutaway" not in store.get_mix_job(jid)["edit_plan"]["beats"][0]


def test_toggle_bad_beat_idx_422(client):
    c, store = client
    jid = _job_with_beat(store)
    asset_id = _asset(store, customer_id=0)
    r = c.post(f"/api/produce/mix/{jid}/cutaway", json={"beat_idx": 99, "asset_id": asset_id})
    assert r.status_code == 422


def test_toggle_missing_asset_422(client):
    c, store = client
    jid = _job_with_beat(store)
    r = c.post(f"/api/produce/mix/{jid}/cutaway", json={"beat_idx": 0, "asset_id": 9999})
    assert r.status_code == 422


def test_toggle_bad_job_404(client):
    c, store = client
    r = c.post("/api/produce/mix/doesnotexist/cutaway", json={"beat_idx": 0, "asset_id": 1})
    assert r.status_code == 404


def test_manual_add_uses_match_type_not_fake_score(client):
    """검수판에서 사람이 직접 골라 붙인 컷어웨이는 적합도 점수가 없다 —
    기존 코드는 score를 1.0으로 꾸며내 마치 자동매칭인 것처럼 보였음(버그)."""
    c, store = client
    jid = _job_with_beat(store)
    asset_id = _asset(store, customer_id=0)
    r = c.post(f"/api/produce/mix/{jid}/cutaway", json={"beat_idx": 0, "asset_id": asset_id})
    assert r.status_code == 200
    cw = store.get_mix_job(jid)["edit_plan"]["beats"][0]["cutaway"]
    assert cw["asset_id"] == asset_id
    assert cw.get("match_type") == "manual"
    assert cw.get("score") in (None,)      # 가짜 1.00 안 씀


def test_toggle_cross_customer_asset_rejected(client):
    """다른 고객(customer_id=1) 소유의 asset은 못 붙인다 — get_scene_asset의 customer_id
    격리가 이 시스템에서 실제로 존재하는 소유권 경계(job 자체엔 customer_id 컬럼이 없다)."""
    c, store = client
    jid = _job_with_beat(store)
    other_asset_id = _asset(store, customer_id=1)  # 세션(cid=0)이 아닌 다른 고객 소유
    r = c.post(f"/api/produce/mix/{jid}/cutaway",
               json={"beat_idx": 0, "asset_id": other_asset_id})
    assert r.status_code == 422
    assert "cutaway" not in store.get_mix_job(jid)["edit_plan"]["beats"][0]
