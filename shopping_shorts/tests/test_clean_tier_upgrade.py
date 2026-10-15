# -*- coding: utf-8 -*-
"""자막제거 등급 상향 뒤 최종 렌더 (2026-09-27, 사장님 승인).

규칙(한 곳 = mix_pipeline.clean_tier_upgrade):
  · 기본 정본 + 고급 요청 → 렌더는 정본을 쓰지 않고 **고급으로 전체** 재청소(고객이 비싼 등급을 고른 정당한 과금).
    확인창(clean_base_preview)이 전체 초·고급 크레딧을 미리 띄운다.
  · 고급 정본 + 기본 요청 → 정본 재사용(과금 0) — 버튼·렌더 모두.
  · 과금은 고객이 확인창을 보고 누른 렌더(allow_clean=True)·버튼에서만. 미리보기·내보내기·썸네일 배경
    (allow_clean=False)은 절대 청소를 부르지 않는다.
"""
from pathlib import Path

import pytest

from shopping_shorts import clean_base as cb
from shopping_shorts import mix_pipeline as mp

BASIC_SIG = "0123456789abcdef"            # 16자 편성 서명 = 기본
PRO_SIG = "0123456789abcdefp"             # 뒤에 'p' = 고급


class _Store:
    def __init__(self, job): self.job = job; self.updates = []
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.updates.append(kw); self.job.update(kw)
    def get_setting(self, k, d=None): return "1" if k == "clean_base_enabled" else d


def _job(work, base_sig, tier):
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "narration": "a", "tts_path": None,
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []}]}
    job = {"job_id": "j", "edit_plan": plan, "urls": ["u"], "subtitle_removal": 1, "customer_id": 0}
    if tier:
        job["clean_tier"] = tier
    work.mkdir(parents=True, exist_ok=True)
    (work / "s0").mkdir(exist_ok=True); (work / "s0" / "v.mp4").write_bytes(b"v" * 4096)
    f = work / ("final_clean_%s.mp4" % base_sig)
    f.write_bytes(b"c" * 4096)
    cb.save_base(work, sig=base_sig, path=str(f), plan=plan,
                 cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    return job


@pytest.fixture
def env(monkeypatch, tmp_path):
    charges, incr = [], []
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: charges.append(1) or 1)
    monkeypatch.setattr(mp, "_refund_clean", lambda *a, **k: None)
    monkeypatch.setattr(mp, "incremental_clean", lambda *a, **k: incr.append(1) or a[6])
    monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: {"s0": 60.0})
    mp._JUDGE_CACHE.clear()
    return charges, incr, tmp_path


def test_rule_one_place():
    b = {"sig": BASIC_SIG}; p = {"sig": PRO_SIG}
    assert mp.clean_tier_upgrade(b, {"clean_tier": "pro"}) is True
    assert mp.clean_tier_upgrade(p, {"clean_tier": "basic"}) is False
    assert mp.clean_tier_upgrade(p, {"clean_tier": "pro"}) is False
    assert mp.clean_tier_upgrade(b, {}) is False
    assert mp.clean_base_fits(b, {"clean_tier": "pro"}) is False
    assert mp.clean_base_fits(p, {}) is True                 # 고급 정본 + 기본 요청 = 재사용


def test_render_basic_base_pro_request_full_clean(env):
    """렌더(allow_clean=True): 정본을 버리고(base None) 정본 없는 job 과 같은 전체 청소 경로 — 증분 아님."""
    charges, incr, tmp = env
    work = tmp / "j"; job = _job(work, BASIC_SIG, "pro")
    j = mp.clean_base_judge(_Store(job), job, work)
    assert j["tier_upgrade"] is True
    plan, paths, base = mp.render_inputs_for(_Store(job), job, "j", work, ["k"], 0, allow_clean=True)
    assert base is None and "s0" in paths and incr == []
    assert mp.clean_route(job, base) in ("final", "sources")       # run_render 가 요청 등급 전체 청소로 간다


def test_full_clean_uses_requested_tier_and_charges_once(env, monkeypatch):
    charges, _i, tmp = env
    work = tmp / "j"; job = _job(work, BASIC_SIG, "pro")
    tiers = []

    def _vc(src, keys, out, tier=None, resume_key=None):
        tiers.append(tier); Path(out).write_bytes(b"x" * 2048); return out
    monkeypatch.setattr(mp, "_vmake_clean", _vc)
    monkeypatch.setattr(mp, "_va_read_cut_map", lambda p: [{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    mp._final_clean_fn(None, job, "j", work, ["k"], 0)(str(work / "mix_raw.mp4"))
    assert tiers == ["pro"] and charges == [1]
    assert mp._sig_tier(cb.load_base(work)["sig"]) == "pro"         # 다음 렌더는 고급 정본 재사용(과금 0)
    mp._JUDGE_CACHE.clear()
    assert mp.clean_base_judge(_Store(job), job, work)["tier_upgrade"] is False


@pytest.mark.parametrize("who", ["preview/export/thumb"])
def test_no_charge_without_confirmed_render(env, who):
    """allow_clean=False(미리보기·캡컷·ZIP·썸네일 배경) — 등급 상향이어도 기존 정본을 쓰고 청소·과금 0."""
    charges, incr, tmp = env
    work = tmp / "j"; job = _job(work, BASIC_SIG, "pro")
    plan, paths, base = mp.render_inputs_for(_Store(job), job, "j", work, [], 0, allow_clean=False)
    assert base is not None and charges == [] and incr == []
    assert set(paths) >= {"clean"}


def test_pro_base_basic_request_reuses(env):
    charges, incr, tmp = env
    work = tmp / "j"; job = _job(work, PRO_SIG, "basic")
    plan, paths, base = mp.render_inputs_for(_Store(job), job, "j", work, ["k"], 0, allow_clean=True)
    assert base is not None and charges == [] and incr == []
    assert mp.clean_base_ready_for(_Store(job), job, work) is True


def test_confirm_dialog_full_seconds_pro_price(env, monkeypatch):
    from shopping_shorts import app as A
    charges, _i, tmp = env
    work = tmp / "j"; job = _job(work, BASIC_SIG, "pro")
    prev = work / "preview.mp4"; prev.write_bytes(b"p" * 2048); job["preview_path"] = str(prev)
    monkeypatch.setattr(mp, "_probe_seconds", lambda p: 30.4)
    store = _Store(job)
    monkeypatch.setattr(A, "Store", lambda db: store)
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp)
    out = A.api_produce_mix_clean_base_preview("j")
    assert out["tier_upgrade"] is True and out["tier"] == "pro" and out["base_tier"] == "basic"
    assert out["seconds"] == 30.4 and out["est_credits"] == mp.clean_credit_estimate(30.4, "pro") == 124
    assert charges == []                                   # 확인창은 묻기만 한다
    # 같은 편성·고급 청소본이 이미 있으면 0초(재사용) — 확인창도 과금 없음으로 안내
    (work / ("final_clean_%s.mp4" % mp._clean_sig(job))).write_bytes(b"c" * 4096)
    out2 = A.api_produce_mix_clean_base_preview("j")
    assert out2["seconds"] == 0 and out2["est_credits"] == 0


def test_confirm_dialog_pro_base_basic_request_no_upgrade(env, monkeypatch):
    from shopping_shorts import app as A
    _c, _i, tmp = env
    work = tmp / "j"; job = _job(work, PRO_SIG, "basic")
    store = _Store(job)
    monkeypatch.setattr(A, "Store", lambda db: store)
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp)
    out = A.api_produce_mix_clean_base_preview("j")
    assert not out.get("tier_upgrade") and out["est_credits"] == 0


@pytest.mark.parametrize("base_sig,tier,want", [(PRO_SIG, "basic", ["reassemble"]),      # 재사용 — 과금 0
                                                (BASIC_SIG, "pro", ["assemble"])])       # 고급 전체 청소(버튼 확인창 뒤)
def test_button_same_rule(env, monkeypatch, base_sig, tier, want):
    _c, _i, tmp = env
    work = tmp / "j"; job = _job(work, base_sig, tier)
    store = _Store(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_vmake_keys", lambda *a, **k: ["k"])
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    calls = []
    monkeypatch.setattr(mp, "assemble_clean_video",
                        lambda *a, **k: calls.append("assemble" if k.get("clean_fn") else "reassemble") or None)
    from shopping_shorts.tests._clean_consent import consent
    mp.run_clean_sources("j", "db", str(tmp), **consent(store, job, work, "button"))
    assert calls == want
