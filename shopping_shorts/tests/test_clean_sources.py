import pytest
from pathlib import Path

from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline as mp


@pytest.fixture(autouse=True)
def _vmake_gate_off(monkeypatch):
    """이 파일은 VMake 전송 관문(10-26 관제 270)이 아닌 다른 판단을 시험한다 — 관문은 test_vmake_send_rule.py 가 잰다."""
    import shopping_shorts.mix_pipeline as _mpg
    monkeypatch.setattr(_mpg, "_vmake_gate", lambda *a, **k: None)



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


# (10-26 관제 270: test_run_clean_sources_cleans_and_caches 삭제 — 원본 소스를 VMake 로 보내던 길 폐지. 대체 검사 test_vmake_send_rule.py)

def test_run_clean_sources_no_key_fails(monkeypatch, tmp_path):
    job = {"job_id": "j", "urls": ["u"]}
    store = _FakeStore(job)
    store.get_setting = lambda *a, **k: ""
    monkeypatch.setattr(mp, "Store", lambda p: store)
    _patch_clean(monkeypatch, [])
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job["clean_status"] == "failed"
    # 사용자 노출 문구엔 벤더명(VMake)이 없어야 한다 — 키 미등록을 알리되 브랜드는 "AI 자막 제거"
    assert "VMake" not in job["clean_error"]
    assert job["clean_error"]  # 비어있지 않음(사유는 전달)


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


# (10-26 관제 270: test_run_clean_sources_builds_clean_video_when_edit_plan_present 삭제 — 원본 소스를 VMake 로 보내던 길 폐지. 대체 검사 test_vmake_send_rule.py)

# (10-26 관제 270: test_run_clean_sources_no_edit_plan_skips_assembly 삭제 — 원본 소스를 VMake 로 보내던 길 폐지. 대체 검사 test_vmake_send_rule.py)

# (10-26 관제 270: test_run_clean_sources_assembly_failure_keeps_clean_status_ready 삭제 — 원본 소스를 VMake 로 보내던 길 폐지. 대체 검사 test_vmake_send_rule.py)

def _final_job():
    return {"job_id": "j", "urls": ["u"], "customer_id": 0,
            "edit_plan": {"beats": [{"beat_idx": 0, "src": "s0"}]}}


def _patch_final(monkeypatch, tmp_path, assemble_result):
    """라이브와 같은 final 전략으로 고정하고, 조립만 흉내낸다."""
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True, raising=False)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "/orig/s0.mp4"})
    monkeypatch.setattr(mp, "assemble_clean_video", assemble_result)


def test_final_path_marks_ready_when_assembled(monkeypatch, tmp_path):
    job = _final_job()
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    _patch_final(monkeypatch, tmp_path, lambda *a, **k: str(tmp_path / "out.mp4"))
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job.get("clean_status") == "ready"


def test_final_path_never_leaves_job_stuck_in_cleaning(monkeypatch, tmp_path):
    """★조립이 조용히 None을 줘도 'cleaning'으로 남기면 안 된다 — 그게 21시간 잠금이었다."""
    job = _final_job()
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    _patch_final(monkeypatch, tmp_path, lambda *a, **k: None)
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job.get("clean_status") == "failed"
    assert job.get("clean_error")           # 사유 없이 실패로만 두면 화면이 안내를 못 만든다


def test_final_path_records_error_when_assemble_raises(monkeypatch, tmp_path):
    """유료 청소가 조립 안에서 돈다 — 거기서 터진 사유(30029 등)가 DB에 남아야
    화면이 '업체 장애'인지 '영상 탓'인지 가를 수 있다."""
    job = _final_job()
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    def _boom(*a, **k):
        raise RuntimeError("AI 자막 제거 결과가 비었습니다: {'code': 30029}")
    _patch_final(monkeypatch, tmp_path, _boom)
    mp.run_clean_sources("j", "db", str(tmp_path))
    assert job.get("clean_status") == "failed"
    assert "30029" in (job.get("clean_error") or "")
