import tempfile
from pathlib import Path
from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


def _dbpath():
    return Path(tempfile.mkdtemp()) / "t.db"


def test_run_mix_job_happy_path(monkeypatch):
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("j1", ["url0", "url1"], 20, "free")

    monkeypatch.setattr(mix_pipeline, "download_video", lambda url, d: Path(d) / "v.mp4")
    monkeypatch.setattr(mix_pipeline, "extract_script",
                        lambda path, video_id, caption="": {
                            "segments": [{"seg_id": f"{video_id}-0", "start": 0.0, "end": 2.0,
                                          "text": "t", "scene_desc": "s"}],
                            "full_text": "ft"})
    monkeypatch.setattr(mix_pipeline, "build_edit_plan",
                        lambda scripts, target_seconds, structure, **k: {
                            "structure": structure,
                            "beats": [{"beat_idx": 0, "role": "훅", "narration": "n",
                                       "target_seconds": 2,
                                       "primary": {"video_id": "s0", "seg_id": "s0-0",
                                                   "start": 0.0, "end": 2.0},
                                       "alternates": [], "effect": "cut"}],
                            "plagiarism_flags": []})
    monkeypatch.setattr(mix_pipeline, "synthesize_tts", lambda text, out, **k: out)

    mix_pipeline.run_mix_job("j1", db, work)
    job = s.get_mix_job("j1")
    assert job["status"] == "ready_for_review"
    assert job["extract"]["s0"]["segments"][0]["seg_id"] == "s0-0"
    assert job["edit_plan"]["beats"][0]["narration"] == "n"


def test_run_mix_job_failure_sets_status(monkeypatch):
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("j2", ["url0"], 20, "free")

    def boom(url, d): raise RuntimeError("다운로드 실패")
    monkeypatch.setattr(mix_pipeline, "download_video", boom)

    mix_pipeline.run_mix_job("j2", db, work)
    job = s.get_mix_job("j2")
    assert job["status"] == "failed"
    assert "다운로드 실패" in job["error"]


def test_source_video_id():
    assert mix_pipeline._source_video_id(0) == "s0"
    assert mix_pipeline._source_video_id(2) == "s2"
