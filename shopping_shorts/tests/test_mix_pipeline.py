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
    assert job["edit_plan"]["beats"][0]["tts_path"]  # 렌더가 의존하는 불변식


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


def test_run_render_happy_path(monkeypatch):
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("j3", ["url0"], 20, "free")

    edit_plan = {
        "structure": "free",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n",
                   "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0",
                               "start": 0.0, "end": 2.0},
                   "alternates": [], "effect": "cut",
                   "tts_path": str(work / "j3" / "tts" / "beat_0.mp3")}],
        "plagiarism_flags": [],
    }
    s.update_mix_job("j3", status="ready_for_review", edit_plan=edit_plan)

    # 소스 mp4 배치 (run_render가 glob으로 찾아야 함)
    src_dir = work / "j3" / "s0"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "vid.mp4").write_bytes(b"")

    captured = {}
    def fake_assemble(plan, tts_paths, source_video_paths, out_path):
        captured["plan"] = plan
        captured["tts_paths"] = tts_paths
        captured["source_video_paths"] = source_video_paths
        captured["out_path"] = out_path
        Path(out_path).write_bytes(b"")
        return out_path
    monkeypatch.setattr(mix_pipeline, "assemble", fake_assemble)

    mix_pipeline.run_render("j3", db, work)

    job = s.get_mix_job("j3")
    assert job["status"] == "done"
    assert job["video_path"]

    assert captured["tts_paths"] == {0: str(work / "j3" / "tts" / "beat_0.mp3")}
    assert captured["source_video_paths"] == {"s0": str(src_dir / "vid.mp4")}
