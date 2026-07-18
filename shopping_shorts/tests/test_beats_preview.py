from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def _beats():
    return [
        {"beat_idx": 0, "narration": "이거 만들어줬더니", "primary": {"video_id": "s0", "start": 0.0, "end": 2.0}},
        {"beat_idx": 1, "narration": "딱 한 뼘이면 OK", "primary": {"video_id": "s0", "start": 2.0, "end": 4.0}},
    ]


def test_beats_preview_lists_captions(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status="ready_for_review", edit_plan={"beats": _beats()})
    r = client.get("/api/produce/mix/beats_preview/j1")
    assert r.status_code == 200
    beats = r.json()["beats"]
    assert [b["caption"] for b in beats] == ["이거 만들어줬더니", "딱 한 뼘이면 OK"]
    assert beats[0]["total"] == 2 and beats[0]["i"] == 0


def test_beats_preview_empty_when_no_edit_plan(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j2", ["u0"], 20, "free")
    r = client.get("/api/produce/mix/beats_preview/j2")
    assert r.status_code == 200
    assert r.json() == {"beats": []}


import subprocess as _sp
from pathlib import Path


def test_extract_beat_frame_real_ffmpeg(tmp_path):
    from shopping_shorts import app as app_module
    work = tmp_path / "job"
    (work / "s0").mkdir(parents=True)
    src = work / "s0" / "clip.mp4"
    # 2초짜리 teal 세로 클립 생성(테스트 픽스처)
    _sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=teal:s=1080x1920:d=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
            capture_output=True, stdin=_sp.DEVNULL)
    out = work / "beatframes" / "0.jpg"
    ok = app_module._extract_beat_frame(work, {"primary": {"video_id": "s0", "start": 0.5}}, out)
    assert ok and out.exists() and out.stat().st_size > 0
