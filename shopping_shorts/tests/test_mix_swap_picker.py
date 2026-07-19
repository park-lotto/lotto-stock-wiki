from pathlib import Path
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


_EXTRACT = {"s0": {"video_id": "s0", "full_text": "x", "segments": [
    {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "감자 써는 손"},
    {"seg_id": "s0-1", "start": 2.0, "end": 4.0, "text": "b", "scene_desc": "접시"},
]}}
_PLAN = {"structure": "free", "plagiarism_flags": [], "beats": [
    {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2, "fit": 2,
     "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
     "alternates": [], "effect": "cut"}]}


def test_segments_lists_inventory_with_used_flag(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("js", ["u0"], 20, "free")
    store.update_mix_job("js", extract=_EXTRACT, edit_plan=_PLAN, status="ready_for_review")
    body = client.get("/api/mix/segments/js").json()
    assert body["ok"] is True
    by_id = {s["seg_id"]: s for s in body["segments"]}
    assert by_id["s0-0"]["used"] is True         # 비트0 primary
    assert by_id["s0-1"]["used"] is False
    assert by_id["s0-1"]["scene_desc"] == "접시"
    assert by_id["s0-1"]["dur"] == 2.0
    assert by_id["s0-1"]["thumb_url"] == "/api/mix/seg_thumb/js/s0-1"


def test_segments_404_when_no_extract(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("js2", ["u0"], 20, "free")
    assert client.get("/api/mix/segments/js2").status_code == 404


def test_seg_thumb_extracts_midpoint_and_caches(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jt", ["u0"], 20, "free")
    store.update_mix_job("jt", extract=_EXTRACT)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", tmp_path / "mix")
    monkeypatch.setattr(app_module, "_resolve_sources",
                        lambda job, work: {"s0": str(tmp_path / "s0.mp4")})
    (tmp_path / "s0.mp4").write_bytes(b"fake")
    calls = []

    def _fake_extract(video_path, dest_dir, ts, filename="f.jpg"):
        calls.append(ts)
        out = Path(dest_dir) / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\xff\xd8jpeg")
        return out

    monkeypatch.setattr(app_module, "extract_frame_at", _fake_extract)
    r = client.get("/api/mix/seg_thumb/jt/s0-1")
    assert r.status_code == 200 and r.content == b"\xff\xd8jpeg"
    assert calls == [3.0]                       # (2.0+4.0)/2 중간지점
    r2 = client.get("/api/mix/seg_thumb/jt/s0-1")
    assert r2.status_code == 200
    assert len(calls) == 1                       # 캐시 히트 — 재추출 없음


def test_seg_thumb_404_on_unknown_seg(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jt2", ["u0"], 20, "free")
    store.update_mix_job("jt2", extract=_EXTRACT)
    assert client.get("/api/mix/seg_thumb/jt2/NOPE").status_code == 404
