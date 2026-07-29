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


def _ready_beat(tmp_path, job_id="j"):
    """추천 후보 상태의 비트 하나 — 내용해시 tts_path + 실재 파일이라 run_render의
    skip_existing이 재합성 없이 넘어간다(2026-07-27 TTS 파일명 내용해시 키잉)."""
    import pathlib
    beat = {"beat_idx": 0, "narration": "렌더 비트"}
    d = pathlib.Path(str(tmp_path)) / job_id / "tts"; d.mkdir(parents=True, exist_ok=True)
    beat["tts_path"] = mp._beat_tts_path(d, beat)
    open(beat["tts_path"], "w").write("m")
    return beat


def test_render_off_uses_original_sources(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"], "edit_plan": {"beats": [_ready_beat(tmp_path)]},
           "subtitle_removal": False}
    store = FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "orig.mp4"})
    monkeypatch.setattr(mp, "remove_subtitles", lambda *a, **k: (_ for _ in ()).throw(AssertionError("불려선 안 됨")))
    seen = {}
    def fake_assemble(plan, tts, sources, out, clean_fn=None, **kw):
        seen["sources"] = sources; seen["clean_fn"] = clean_fn
        open(out, "w").write("v"); return out
    monkeypatch.setattr(mp, "assemble", fake_assemble)

    mp.run_render("j", str(tmp_path / "db"), str(tmp_path))
    assert seen["sources"] == {"s0": "orig.mp4"}
    assert seen["clean_fn"] is None
    assert _statuses(store)[-1] == "done"


def test_render_on_uses_clean_sources(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"], "edit_plan": {"beats": [_ready_beat(tmp_path)]},
           "subtitle_removal": True}
    store = FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "orig.mp4"})
    monkeypatch.setattr(mp, "_vmake_key", lambda store: "appkey:secret")
    removed = []
    def fake_remove(video, key, out_path, **kw):
        removed.append(video); open(out_path, "w").write("clean"); return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)
    seen = {}
    def fake_assemble(plan, tts, sources, out, clean_fn=None, **kw):
        seen["sources"] = sources; seen["clean_fn"] = clean_fn
        open(out, "w").write("v"); return out
    monkeypatch.setattr(mp, "assemble", fake_assemble)

    mp.run_render("j", str(tmp_path / "db"), str(tmp_path))
    assert removed == ["orig.mp4"]
    assert seen["clean_fn"] is None
    assert list(seen["sources"].values())[0].endswith("clean_src_s0.mp4")
    assert job["clean_status"] == "ready"


def test_render_on_no_key_fails(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"], "edit_plan": {"beats": [_ready_beat(tmp_path)]},
           "subtitle_removal": True}
    store = FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "x.mp4"})
    monkeypatch.setattr(mp, "_vmake_key", lambda store: "")
    monkeypatch.setattr(mp, "assemble", lambda *a, **k: open(k.get("out") or a[3], "w").write("v"))

    mp.run_render("j", str(tmp_path / "db"), str(tmp_path))
    assert _statuses(store)[-1] == "failed"
    # 새 문구: 벤더명(VMake) 없이 "설정이 완료되지 않았습니다"로 사유 전달
    assert any("설정" in (u.get("error") or "") for u in store.updates)
    assert not any("VMake" in (u.get("error") or "") for u in store.updates)
