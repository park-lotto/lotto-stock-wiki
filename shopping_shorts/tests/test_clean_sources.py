from pathlib import Path

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


# ── 2026-07-20 사장님 제보: 2단계 자막제거 후 5단계 썸네일에 지우기 전 문구가 그대로 나옴.
# 원인: clean_sources(소스별 청소본)만 캐시되고 조립본(clean_video_path)은 아무도 안 만들어
# thumb/frames(app.py)가 clean_video_path→preview_path→video_path 순으로 보는데, preview_path는
# run_preview가 clean_fn=None으로 늘 원본 자막째 렌더한다 — 항상 자막 있는 화면으로 떨어졌다.


def _plan_with_beats():
    return {"beats": [{"beat_idx": 0, "tts_path": "/tts/0.mp3"},
                       {"beat_idx": 1, "tts_path": "/tts/1.mp3"}]}


def test_run_clean_sources_builds_clean_video_when_edit_plan_present(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"], "customer_id": 0, "edit_plan": _plan_with_beats()}
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    _patch_clean(monkeypatch, [])
    seen = {}
    def fake_assemble(plan, tts_paths, source_video_paths, out_path, **kw):
        seen["source_video_paths"] = source_video_paths
        seen["clean_fn"] = kw.get("clean_fn")
        open(out_path, "w").write("clean-preview")
        return out_path
    monkeypatch.setattr(mp, "assemble", fake_assemble)
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job["clean_status"] == "ready"
    assert job["clean_video_path"] == str(Path(tmp_path) / "j" / "clean_preview.mp4")
    assert Path(job["clean_video_path"]).exists()
    # 재조립은 이미 청소된 소스로만 — VMake(clean_fn)를 또 태우면 안 된다(과금 중복).
    assert seen["clean_fn"] is None
    assert seen["source_video_paths"] == job["clean_sources"]


def test_run_clean_sources_no_edit_plan_skips_assembly(monkeypatch, tmp_path):
    """edit_plan이 아직 없으면(믹스 전 단계 등) 조립을 시도하지 않는다 — clean_status는 그대로 ready."""
    job = {"job_id": "j", "urls": ["u"]}
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    _patch_clean(monkeypatch, [])
    monkeypatch.setattr(mp, "assemble", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("edit_plan 없이 assemble이 불렸다")))
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job["clean_status"] == "ready"
    assert "clean_video_path" not in job


def test_run_clean_sources_assembly_failure_keeps_clean_status_ready(monkeypatch, tmp_path):
    """조립(무료 재렌더)이 실패해도 소스청소(유료 VMake)는 이미 끝났다 — clean_status를
    failed로 뒤집으면 사용자가 '실패했다'고 오인해 재시도하게 만들 뿐(재과금은 없지만 혼란)."""
    job = {"job_id": "j", "urls": ["u"], "customer_id": 0, "edit_plan": _plan_with_beats()}
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    _patch_clean(monkeypatch, [])
    def boom(*a, **k):
        raise RuntimeError("ffmpeg 오류")
    monkeypatch.setattr(mp, "assemble", boom)
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job["clean_status"] == "ready"
    assert job["clean_error"] is None
    assert "clean_video_path" not in job
