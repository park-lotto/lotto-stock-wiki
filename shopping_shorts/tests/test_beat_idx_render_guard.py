# -*- coding: utf-8 -*-
"""칸 번호(beat_idx)가 겹친 편성은 렌더·미리보기·자막제거·내보내기를 **막는다** (2026-09-27).

왜: 렌더는 음성 표를 {beat_idx: tts_path} 로 모은다. 번호가 겹치면 마지막 칸 음성만 남아 "CTA 음성 반복 +
  한 칸 음성 누락"이 출력에 실제로 났다(옛 job 5개, 파형 확인). 조용히 진행하지 않고 failed + 관리자 경보.
★판정은 store.beat_idx_duplicates 한 곳, 음성 표는 mix_pipeline.tts_paths_of 한 곳.
"""
import pytest

from shopping_shorts import mix_pipeline as mp


def _plan(dup=True):
    beats = [{"beat_idx": 0, "tts_path": "/t/a.mp3", "narration": "a"},
             {"beat_idx": 1, "tts_path": "/t/b.mp3", "narration": "b"},
             {"beat_idx": 1 if dup else 2, "tts_path": "/t/c.mp3", "narration": "c"}]
    return {"beats": beats}


class _Store:
    def __init__(self, job): self.job = job; self.updates = []
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.updates.append(kw); self.job.update(kw)
    def get_setting(self, k, d=None): return d


class _Reached(Exception):
    pass


@pytest.fixture
def env(monkeypatch, tmp_path):
    alerts, synth, charges = [], [], []
    from shopping_shorts import ops_alert
    monkeypatch.setattr(ops_alert, "raise_alert", lambda kind, title, *a, **k: alerts.append((kind, title)) or True)
    monkeypatch.setattr(mp.pron_corrections, "load", lambda store: {})

    def _synth(*a, **k):
        synth.append(1)
        raise _Reached()                # 정상 편성은 여기(음성 합성)까지 온다 — 그 뒤는 이 테스트 밖
    monkeypatch.setattr(mp, "_synthesize_beats", _synth)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: charges.append(1) or 1)

    def make(dup):
        job = {"job_id": "j", "edit_plan": _plan(dup), "urls": ["u"], "subtitle_removal": 1, "customer_id": 0}
        store = _Store(job)
        monkeypatch.setattr(mp, "Store", lambda p: store)
        return job, store
    return make, alerts, synth, charges, tmp_path


def test_tts_paths_of_raises_on_duplicate_and_matches_old_dict_otherwise():
    with pytest.raises(mp.BeatIdxDuplicateError):
        mp.tts_paths_of(_plan(dup=True))
    ok = _plan(dup=False)
    assert mp.tts_paths_of(ok) == {b["beat_idx"]: b["tts_path"] for b in ok["beats"] if b.get("tts_path")}


def test_run_render_blocks_duplicate_with_alert(env):
    make, alerts, synth, charges, tmp = env
    job, store = make(dup=True)
    mp.run_render("j", "db", str(tmp))
    assert job["status"] == "failed" and job["error"] == mp.BEAT_DUP_MSG
    assert synth == [] and charges == []                 # 음성 합성·과금 전에 막았다
    assert alerts and alerts[0][0] == "beat_idx_dup:j"


def test_run_preview_blocks_duplicate_with_alert(env):
    make, alerts, synth, _c, tmp = env
    job, store = make(dup=True)
    mp.run_preview("j", "db", str(tmp))
    assert job["preview_status"] == "failed" and job["preview_error"] == mp.BEAT_DUP_MSG
    assert synth == [] and alerts and alerts[0][0] == "beat_idx_dup:j"


def test_run_clean_sources_blocks_duplicate_before_charge(env):
    make, alerts, synth, charges, tmp = env
    job, store = make(dup=True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert job["clean_status"] == "failed" and job["clean_error"] == mp.BEAT_DUP_MSG
    assert synth == [] and charges == [] and alerts


def test_normal_plan_passes_guard(env):
    """정상 편성은 종전대로 음성 합성 단계까지 간다(경보 없음)."""
    make, alerts, synth, _c, tmp = env
    job, store = make(dup=False)
    mp.run_render("j", "db", str(tmp))
    assert synth == [1] and alerts == []
    assert job.get("error") != mp.BEAT_DUP_MSG
    job2, _ = make(dup=False)
    synth.clear()
    mp.run_preview("j", "db", str(tmp))
    assert synth == [1] and alerts == [] and job2.get("preview_error") != mp.BEAT_DUP_MSG


def test_export_routes_refuse_duplicate(monkeypatch, tmp_path, env):
    from shopping_shorts import app as A
    make, alerts, _s, _c, tmp = env
    job, store = make(dup=True)
    monkeypatch.setattr(A, "Store", lambda db: store)
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    r1 = A.api_mix_export("j")
    r2 = A.api_mix_capcut("j", base="C:/x")
    assert r1.status_code == 409 and r2.status_code == 409
    assert len(alerts) == 2
