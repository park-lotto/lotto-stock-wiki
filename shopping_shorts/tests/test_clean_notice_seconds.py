# -*- coding: utf-8 -*-
"""자막제거 안내 초·크레딧 == 렌더/버튼이 **업체에 실제로 보낼 초** (2026-09-27).

왜: 최종렌더 전 안내(api_produce_mix_clean_base_preview)는 remap_plan을 따로 부르고 늘림 여유(EXTEND_PAD)를 빼
  실제보다 짧게 안내했다(서버 실측 안내 152.6초 vs 실제 204.6초). 버튼 안내(_clean_credit_est)는 증분을 몰라
  전체 길이로 안내했다. 대조 기준 = incremental_clean 이 업체 호출 직전에 잘라 보내는 조각 길이(_cut_piece dur).
"""
import pytest

from shopping_shorts import app as A
from shopping_shorts import clean_base as cb
from shopping_shorts import mix_pipeline as mp


class _Stop(Exception):
    pass


def _setup(tmp_path, monkeypatch, tier="basic", sel=None):
    plan = {"beats": [
        {"beat_idx": 0, "target_seconds": 2.0, "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 2.0, "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 0.0, "end": 2.5}, "alternates": []},
        {"beat_idx": 2, "target_seconds": 2.0, "primary": {"video_id": "s2", "seg_id": "s2-0", "start": 4.0, "end": 5.2}, "alternates": []}]}
    work = tmp_path / "jobx"; work.mkdir()
    (work / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    cb.save_base(work, sig="x", path=str(work / "final_clean_x.mp4"), plan={"beats": plan["beats"][:1]},
                 cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    job = {"job_id": "jobx", "edit_plan": plan, "subtitle_removal": 1, "customer_id": 0, "clean_tier": tier,
           "clean_cuts": sel}
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)

    class _S:
        def get_mix_job(self, j): return job
        def get_setting(self, k, d=None): return "1"
        def update_mix_job(self, *a, **k): pass
    monkeypatch.setattr(A, "Store", lambda db: _S())
    monkeypatch.setattr(mp, "Store", lambda db: _S())
    # 원본 파일: s0·s1 은 있다, s2 는 못 찾는다(incremental_clean 이 건너뛴다 → 안내에서도 빠져야 한다)
    srcs = {"s0": str(work / "s0.mp4"), "s1": str(work / "s1.mp4")}
    monkeypatch.setattr(mp, "_resolve_sources", lambda j, w: dict(srcs))
    mp._JUDGE_CACHE.clear()
    return job, work, _S()


def _sent_seconds(monkeypatch, job, work, store):
    """렌더(render_inputs_for → incremental_clean)가 업체 호출 직전에 잘라 보내는 조각 길이 합."""
    durs = []
    monkeypatch.setattr(mp, "_cut_piece", lambda src, ss, dur, dst: (durs.append(dur), str(dst))[1])
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: 0)

    def _joined(items, *a, **k):
        raise _Stop()
    monkeypatch.setattr(mp, "_clean_joined", _joined)
    with pytest.raises(_Stop):
        mp.render_inputs_for(store, job, "jobx", work, ["k"], 0, allow_clean=True)
    return sum(durs)


def _fake_need(monkeypatch):
    """렌더 컷 재생이 못 덮은 구간(_clean_need)이 있는 경우 — 조각마다 EXTEND_PAD 가 붙는 길."""
    real = cb.remap_plan

    def _remap(plan, base, **kw):
        p2, unc, ext = real(plan, base, **kw)
        p2["_clean_need"] = {"1": [{"video_id": "s1", "start": 0.3, "end": 1.1},
                                   {"video_id": "s1", "start": 1.5, "end": 2.4}],
                             "2": [{"video_id": "s2", "start": 4.0, "end": 5.0}]}
        return p2, sorted(set(unc) | {1, 2}), [{"beat_idx": 0, "video_id": "s0", "start": 3.0, "end": 3.9, "need": 0.7}]
    monkeypatch.setattr(cb, "remap_plan", _remap)


@pytest.mark.parametrize("need", [False, True], ids=["재료전체", "못덮은구간+여유"])
def test_notice_seconds_equal_sent_seconds(tmp_path, monkeypatch, need):
    job, work, store = _setup(tmp_path, monkeypatch)
    if need:
        _fake_need(monkeypatch)
    out = A.api_produce_mix_clean_base_preview("jobx")
    assert out["enabled"] and out["base"], out
    sent = _sent_seconds(monkeypatch, job, work, store)
    assert sent > 0
    assert out["seconds"] == pytest.approx(sent, abs=0.011), (out, sent)
    assert out["est_credits"] == mp.clean_credit_estimate(sent, "basic")
    if need:
        # 여유가 실제로 들어간 사례인지(못 덮은 조각 2개 × EXTEND_PAD, s2 는 원본 없음·늘림 0.9초) — 빼면 빨강
        assert sent == pytest.approx(0.8 + 0.9 + 0.9 + 2 * cb.EXTEND_PAD, abs=1e-6)


def test_button_credit_incremental_when_base_fits(tmp_path, monkeypatch):
    job, work, store = _setup(tmp_path, monkeypatch)
    _fake_need(monkeypatch)
    monkeypatch.setattr(mp, "_clean_strategy", lambda j: "final")
    sent = _sent_seconds(monkeypatch, job, work, store)
    mp._JUDGE_CACHE.clear()
    assert A._clean_credit_est(job, "jobx") == mp.clean_credit_estimate(sent, "basic")


def test_button_credit_full_when_base_tier_differs(tmp_path, monkeypatch):
    """정본이 기본 등급인데 고급을 골랐으면 버튼은 전체를 다시 지운다 → 증분 초가 아니라 전체 길이로 안내."""
    job, work, store = _setup(tmp_path, monkeypatch, tier="pro")
    _fake_need(monkeypatch)
    monkeypatch.setattr(mp, "_clean_strategy", lambda j: "final")
    prev = work / "preview.mp4"; prev.write_bytes(b"p" * 2048)
    job["preview_path"] = str(prev)
    monkeypatch.setattr(mp, "_probe_seconds", lambda p: 30.4)
    assert A._clean_credit_est(job, "jobx") == mp.clean_credit_estimate(30.4, "pro") == 124
