from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    # 백그라운드 작업은 즉시 no-op(상태만 미리 세팅해 검증)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "retype_mix_job", lambda *a, **k: None)
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


def test_mix_result_includes_video_type(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jv", ["u0"], 20, "free")
    store.update_mix_job("jv", status="ready_for_review", edit_plan={
        "structure": "free", "detected_type": "recipe_secret", "affiliate_target": "소금",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                   "alternates": [], "effect": "cut"}],
        "plagiarism_flags": []})
    body = client.get("/api/mix/result/jv").json()
    assert body["detected_type"] == "recipe_secret"
    assert "비밀비법형" in body["detected_type_label"]
    assert body["affiliate_target"] == "소금"
    assert any(t["key"] == "product_reveal" for t in body["video_types"])


def test_mix_retype_valid_and_invalid(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jr", ["u0"], 20, "free")
    store.update_mix_job("jr", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": []}})
    # 유효 유형 → 200
    assert client.post("/api/mix/retype", json={"job_id": "jr", "video_type": "recipe_secret"}).status_code == 200
    # 무효 유형 → 422
    assert client.post("/api/mix/retype", json={"job_id": "jr", "video_type": "nope"}).status_code == 422
    # extract 없는 job → 404
    store.create_mix_job("jr2", ["u0"], 20, "free")
    assert client.post("/api/mix/retype", json={"job_id": "jr2", "video_type": "recipe_secret"}).status_code == 404


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


def test_mix_adjust_invalid_beat_idx_returns_404(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j2b", ["u0"], 20, "free")
    store.update_mix_job("j2b", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": [
        {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "c"},
        {"seg_id": "s0-1", "start": 2.0, "end": 4.0, "text": "b", "scene_desc": "d"},
    ]}}, edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
         "alternates": [], "effect": "cut"}], "plagiarism_flags": []}, status="ready_for_review")
    # 존재하지 않는 beat_idx — 매치되는 비트가 없으면 404여야 함(성공으로 위장 금지)
    r = client.post("/api/mix/adjust", json={"job_id": "j2b", "beat_idx": 999, "video_id": "s0", "seg_id": "s0-1"})
    assert r.status_code == 404
    plan = store.get_mix_job("j2b")["edit_plan"]
    assert plan["beats"][0]["primary"] == {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0}


def test_mix_render_sets_background(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j3", ["u0"], 20, "free")
    store.update_mix_job("j3", status="ready_for_review", edit_plan={"structure": "free", "beats": [], "plagiarism_flags": []})
    assert client.post("/api/mix/render", json={"job_id": "j3"}).status_code == 200


# ── 영상제작소 2단계: 1개 영상 순서편집도 허용(2026-07-14) ──────────

def test_produce_mix_start_accepts_single_url(monkeypatch, tmp_path):
    """소스 1개만 보내도(레퍼런스 모음집에서 하나만 골라 보낸 경우) 시작돼야 한다
    — 그 영상 안에서 구간 순서편집. 예전엔 '2개 이상' 검증에 막혔다."""
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/mix/start",
                    json={"script": "테스트 대본", "urls": ["u0"], "target_seconds": 20})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert store.get_mix_job(jid)["urls"] == ["u0"]


def test_produce_mix_start_rejects_empty_urls(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/mix/start",
                    json={"script": "테스트 대본", "urls": [], "target_seconds": 20})
    assert r.status_code == 422


def test_produce_mix_start_rejects_empty_script(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/mix/start",
                    json={"script": "", "urls": ["u0", "u1"], "target_seconds": 20})
    assert r.status_code == 422
