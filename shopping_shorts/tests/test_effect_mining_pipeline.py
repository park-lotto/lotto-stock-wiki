from pathlib import Path

from shopping_shorts.effect_mining.connectors import ConnectorRegistry, external_id_from_url
from shopping_shorts.effect_mining.db import MiningDB
from shopping_shorts.effect_mining.analyzers import derive_candidates
from shopping_shorts.effect_mining.pipeline import MiningPipeline


class FakeConnector:
    def __init__(self, items):
        self.items = items
        self.calls = 0

    def discover(self, source):
        self.calls += 1
        return list(self.items)


class FakeDownloader:
    def __init__(self):
        self.calls = 0

    def __call__(self, item, target_dir):
        self.calls += 1
        path = Path(target_dir) / f"{item['external_id']}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-video")
        return path


class FakeAnalyzer:
    def __init__(self):
        self.calls = 0

    def __call__(self, media_path):
        self.calls += 1
        return {
            "duration_sec": 8.0,
            "fps": 30.0,
            "cuts": [
                {"start_sec": 0.0, "end_sec": 2.0, "peak_sec": 0.8,
                 "motion_energy": 4.0, "motion_level": "LOW"},
                {"start_sec": 2.0, "end_sec": 5.0, "peak_sec": 2.1,
                 "motion_energy": 22.0, "motion_level": "PEAK"},
                {"start_sec": 5.0, "end_sec": 8.0, "peak_sec": 6.2,
                 "motion_energy": 10.0, "motion_level": "MED"},
            ],
        }


def _run_next(db, pipeline, worker="test-worker"):
    job = db.claim(worker, lease_sec=60, now=2_000)
    assert job is not None
    result = pipeline.execute(job["task"], job["payload"], now=2_000)
    db.complete(job["id"], worker, result, now=2_000)
    return job, result


def test_external_id_normalization_for_supported_short_form_urls():
    assert external_id_from_url("youtube", "https://youtube.com/shorts/abc_DEF-1") == "abc_DEF-1"
    assert external_id_from_url("youtube", "https://youtu.be/abc_DEF-1?t=3") == "abc_DEF-1"
    assert external_id_from_url("instagram", "https://instagram.com/reel/C9abc_1/") == "C9abc_1"
    assert external_id_from_url("tiktok", "https://tiktok.com/@x/video/741234567") == "741234567"


def test_full_pipeline_persists_lineage_and_candidates(tmp_path):
    db = MiningDB(tmp_path / "mining.db")
    source_id = db.add_source("youtube", "keyword", "쇼핑 꿀템", 300, now=1_000)
    connector = FakeConnector([{
        "external_id": "abc123",
        "url": "https://youtube.com/shorts/abc123",
        "title": "수납 꿀템",
        "channel": "demo",
        "views": 1000,
    }])
    downloader = FakeDownloader()
    analyzer = FakeAnalyzer()
    pipeline = MiningPipeline(
        db, tmp_path / "media", ConnectorRegistry({"youtube": connector}),
        downloader=downloader, analyzer=analyzer, analyzer_version="signals-v1",
    )

    db.schedule_due_sources(now=1_000)
    assert _run_next(db, pipeline)[0]["task"] == "discover"
    assert _run_next(db, pipeline)[0]["task"] == "acquire"
    assert _run_next(db, pipeline)[0]["task"] == "measure"
    assert _run_next(db, pipeline)[0]["task"] == "promote"

    items = db.list_items()
    signals = db.list_signals(items[0]["id"])
    candidates = db.list_candidates(items[0]["id"])
    assert len(items) == 1
    assert items[0]["media_sha256"]
    assert len(signals) == 1
    assert signals[0]["analyzer_version"] == "signals-v1"
    assert {c["candidate_kind"] for c in candidates} == {"scene_transition", "motion_peak"}
    assert all(c["signal_id"] == signals[0]["id"] for c in candidates)
    assert connector.calls == downloader.calls == analyzer.calls == 1
    assert db.get_run(source_id)["new_count"] == 1


def test_repeated_discovery_updates_item_without_duplicate_acquire(tmp_path):
    db = MiningDB(tmp_path / "mining.db")
    source_id = db.add_source("youtube", "keyword", "주방템", 10, now=1_000)
    connector = FakeConnector([{
        "external_id": "same1", "url": "https://youtube.com/shorts/same1",
        "title": "첫 제목", "views": 10,
    }])
    pipeline = MiningPipeline(db, tmp_path / "media", ConnectorRegistry({"youtube": connector}),
                              downloader=FakeDownloader(), analyzer=FakeAnalyzer())

    first = pipeline.execute("discover", {"source_id": source_id}, now=1_000)
    connector.items[0]["views"] = 25
    second = pipeline.execute("discover", {"source_id": source_id}, now=2_000)

    assert len(db.list_items()) == 1
    assert db.list_items()[0]["metadata"]["views"] == 25
    assert db.queue_counts()["queued"] == 1
    assert first["new"] == 1
    assert second["new"] == 0


def test_rediscovery_after_completed_pipeline_only_refreshes_metadata(tmp_path):
    db = MiningDB(tmp_path / "mining.db")
    source_id = db.add_source("youtube", "keyword", "생활템", 10, now=1_000)
    connector = FakeConnector([{
        "external_id": "done1", "url": "https://youtube.com/shorts/done1",
        "title": "완료 영상", "views": 10,
    }])
    downloader = FakeDownloader()
    analyzer = FakeAnalyzer()
    pipeline = MiningPipeline(db, tmp_path / "media", ConnectorRegistry({"youtube": connector}),
                              downloader=downloader, analyzer=analyzer)

    pipeline.execute("discover", {"source_id": source_id}, now=1_000)
    _run_next(db, pipeline)
    _run_next(db, pipeline)
    _run_next(db, pipeline)
    connector.items[0]["views"] = 99

    result = pipeline.execute("discover", {"source_id": source_id}, now=3_000)

    assert result["new"] == 0
    assert db.list_items()[0]["metadata"]["views"] == 99
    assert db.queue_counts() == {"done": 3}
    assert downloader.calls == analyzer.calls == 1


def test_measure_is_versioned_and_does_not_duplicate_signal(tmp_path):
    db = MiningDB(tmp_path / "mining.db")
    item_id, _ = db.upsert_item("youtube", "v1", "https://youtube.com/shorts/v1", {}, now=1_000)
    media = tmp_path / "v1.mp4"
    media.write_bytes(b"video")
    db.set_item_media(item_id, media, now=1_000)
    analyzer = FakeAnalyzer()
    pipeline = MiningPipeline(db, tmp_path / "media", ConnectorRegistry({}),
                              downloader=FakeDownloader(), analyzer=analyzer,
                              analyzer_version="signals-v1")

    first = pipeline.execute("measure", {"item_id": item_id}, now=1_000)
    second = pipeline.execute("measure", {"item_id": item_id}, now=1_001)

    assert first["signal_id"] == second["signal_id"]
    assert len(db.list_signals(item_id)) == 1
    assert analyzer.calls == 1


def test_zero_energy_relative_peak_is_not_promoted_as_motion_effect():
    signal = {
        "duration_sec": 2.0,
        "cuts": [{
            "start_sec": 0.0, "end_sec": 2.0, "peak_sec": 0.0,
            "motion_energy": 0.0, "motion_level": "PEAK",
        }],
    }

    assert derive_candidates(signal) == []
