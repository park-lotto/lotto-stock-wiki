from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    # 백그라운드 작업은 즉시 no-op(상태만 미리 세팅해 검증)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def test_mix_start_creates_job(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/mix/start", json={"urls": ["u0", "u1"], "target_seconds": 20, "structure": "free"})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert store.get_mix_job(jid)["status"] == "downloading"


def test_mix_status_and_result(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status="ready_for_review", edit_plan={
        "structure": "free",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                   "alternates": [], "effect": "cut"}],
        "plagiarism_flags": []})
    assert client.get("/api/mix/status/j1").json()["status"] == "ready_for_review"
    body = client.get("/api/mix/result/j1").json()
    assert body["beats"][0]["narration"] == "n"


def test_mix_adjust_regrounds_from_inventory(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j2", ["u0"], 20, "free")
    store.update_mix_job("j2", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": [
        {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "c"},
        {"seg_id": "s0-1", "start": 2.0, "end": 4.0, "text": "b", "scene_desc": "d"},
    ]}}, edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
         "alternates": [], "effect": "cut"}], "plagiarism_flags": []}, status="ready_for_review")
    # beat0의 primary를 s0-1로 교체 — start/end는 서버가 인벤토리에서 되붙여야 함
    r = client.post("/api/mix/adjust", json={"job_id": "j2", "beat_idx": 0, "video_id": "s0", "seg_id": "s0-1"})
    assert r.status_code == 200
    plan = store.get_mix_job("j2")["edit_plan"]
    assert plan["beats"][0]["primary"] == {"video_id": "s0", "seg_id": "s0-1", "start": 2.0, "end": 4.0}


def test_mix_render_sets_background(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j3", ["u0"], 20, "free")
    store.update_mix_job("j3", status="ready_for_review", edit_plan={"structure": "free", "beats": [], "plagiarism_flags": []})
    assert client.post("/api/mix/render", json={"job_id": "j3"}).status_code == 200
