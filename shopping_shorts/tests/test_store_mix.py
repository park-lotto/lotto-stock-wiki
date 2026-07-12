import json
import tempfile
from pathlib import Path
from shopping_shorts.store import Store


def _store():
    d = tempfile.mkdtemp()
    return Store(Path(d) / "t.db")


def test_create_and_get_mix_job():
    s = _store()
    s.create_mix_job("job1", ["u1", "u2"], 30, "template")
    job = s.get_mix_job("job1")
    assert job["job_id"] == "job1"
    assert job["urls"] == ["u1", "u2"]
    assert job["target_seconds"] == 30
    assert job["structure"] == "template"
    assert job["status"] == "downloading"
    assert job["extract"] is None
    assert job["edit_plan"] is None
    assert job["created_at"] and job["updated_at"]


def test_get_missing_returns_none():
    s = _store()
    assert s.get_mix_job("nope") is None


def test_update_mix_job_status_and_json():
    s = _store()
    s.create_mix_job("job2", ["u1"], 20, "free")
    s.update_mix_job("job2", status="planning", extract={"a": 1})
    job = s.get_mix_job("job2")
    assert job["status"] == "planning"
    assert job["extract"] == {"a": 1}
    s.update_mix_job("job2", status="done", edit_plan={"beats": []}, video_path="/x.mp4")
    job = s.get_mix_job("job2")
    assert job["status"] == "done"
    assert job["edit_plan"] == {"beats": []}
    assert job["video_path"] == "/x.mp4"
