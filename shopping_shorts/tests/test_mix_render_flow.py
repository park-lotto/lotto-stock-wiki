from shopping_shorts import mix_pipeline as mp


class FakeStore:
    def __init__(self, job):
        self._job = job
        self.updates = []

    def get_mix_job(self, job_id):
        return self._job

    def update_mix_job(self, job_id, **fields):
        self.updates.append(fields)
        self._job.update(fields)


def _statuses(store):
    return [u["status"] for u in store.updates if "status" in u]


def test_render_off_skips_vmake(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"], "edit_plan": {"beats": [{"beat_idx": 0, "tts_path": "t"}]},
           "subtitle_removal": False}
    store = FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "x.mp4"})
    called = {"clean": 0}
    def fake_assemble(plan, tts, sources, out, clean_fn=None):
        if clean_fn:
            called["clean"] += 1
        open(out, "w").write("v")
        return out
    monkeypatch.setattr(mp, "assemble", fake_assemble)

    mp.run_render("j", str(tmp_path / "db"), str(tmp_path))
    assert called["clean"] == 0
    assert "removing_subtitles" not in _statuses(store)
    assert _statuses(store)[-1] == "done"


def test_render_on_calls_vmake(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"], "edit_plan": {"beats": [{"beat_idx": 0, "tts_path": "t"}]},
           "subtitle_removal": True}
    store = FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "x.mp4"})
    monkeypatch.setattr(mp, "_vmake_key", lambda store: "appkey:secret")
    seen = {}
    def fake_remove(video, key, out_path, **kw):
        seen["video"] = video; open(out_path, "w").write("clean"); return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)
    def fake_assemble(plan, tts, sources, out, clean_fn=None):
        if clean_fn:
            clean_fn("mix_raw.mp4")
        open(out, "w").write("v"); return out
    monkeypatch.setattr(mp, "assemble", fake_assemble)

    mp.run_render("j", str(tmp_path / "db"), str(tmp_path))
    assert seen["video"] == "mix_raw.mp4"
    assert "removing_subtitles" in _statuses(store)
    assert _statuses(store)[-1] == "done"


def test_render_on_no_key_fails(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"], "edit_plan": {"beats": [{"beat_idx": 0, "tts_path": "t"}]},
           "subtitle_removal": True}
    store = FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "x.mp4"})
    monkeypatch.setattr(mp, "_vmake_key", lambda store: "")
    monkeypatch.setattr(mp, "assemble", lambda *a, **k: open(k.get("out") or a[3], "w").write("v"))

    mp.run_render("j", str(tmp_path / "db"), str(tmp_path))
    assert _statuses(store)[-1] == "failed"
    assert any("키" in (u.get("error") or "") for u in store.updates)
