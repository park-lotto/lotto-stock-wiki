from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline as mp


def test_clean_fields_roundtrip(tmp_path):
    db = str(tmp_path / "t.db")
    s = Store(db)
    s.create_mix_job("j1", ["u"], 30, "template")
    job = s.get_mix_job("j1")
    assert job["clean_status"] is None
    assert job["clean_sources"] is None
    assert job["clean_error"] is None
    s.update_mix_job("j1", clean_status="ready", clean_error=None,
                     clean_sources={"s0": "/tmp/clean_src_s0.mp4"})
    job = s.get_mix_job("j1")
    assert job["clean_status"] == "ready"
    assert job["clean_sources"] == {"s0": "/tmp/clean_src_s0.mp4"}


def test_clean_status_failed_persists(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.create_mix_job("j2", ["u"], 30, "template")
    s.update_mix_job("j2", clean_status="failed", clean_error="키 없음")
    job = s.get_mix_job("j2")
    assert job["clean_status"] == "failed"
    assert job["clean_error"] == "키 없음"


class _FakeStore:
    def __init__(self, job):
        self._job = job
        self.updates = []
    def get_mix_job(self, _):
        return self._job
    def update_mix_job(self, _, **f):
        self.updates.append(f); self._job.update(f)
    def get_setting(self, *_a, **_k):
        return "appkey:secret"


def _patch_clean(monkeypatch, remove_calls):
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "/orig/s0.mp4"})
    def fake_remove(video, key, out_path, **kw):
        remove_calls.append(video); open(out_path, "w").write("clean"); return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)


def test_run_clean_sources_cleans_and_caches(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"]}
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    calls = []
    _patch_clean(monkeypatch, calls)
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert calls == ["/orig/s0.mp4"]
    assert job["clean_status"] == "ready"
    assert list(job["clean_sources"].keys()) == ["s0"]


def test_run_clean_sources_no_key_fails(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"]}
    store = _FakeStore(job)
    store.get_setting = lambda *a, **k: ""
    monkeypatch.setattr(mp, "Store", lambda p: store)
    _patch_clean(monkeypatch, [])
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job["clean_status"] == "failed"
    assert "VMake" in job["clean_error"]


def test_ensure_clean_sources_skips_cached(monkeypatch, tmp_path):
    existing = tmp_path / "clean_src_s0.mp4"; existing.write_text("x")
    job = {"job_id": "j", "urls": ["u"], "clean_sources": {"s0": str(existing)}}
    store = _FakeStore(job)
    calls = []
    _patch_clean(monkeypatch, calls)
    out = mp._ensure_clean_sources(store, job, "j", tmp_path, "appkey:secret")
    assert calls == []
    assert out == {"s0": str(existing)}
