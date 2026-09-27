# -*- coding: utf-8 -*-
"""청소본 정본 판정은 **항상 보정된 정본**으로 · 속도 불일치 컷은 덮지 않은 것으로 (2026-09-27).

1) clean_base_judge: 보정 v3부터 밀림(off)·다음 컷 시작 자르기가 덮음 범위를 바꾼다. 버튼·안내가 보정 없이
   판정하면 "덮임(과금 0)"인데 렌더는 "안 덮임(증분 과금)"이 갈렸다 → 판정은 늘 보정 뒤, 보정은 정본당 1회.
2) 옛 청소본 조각이 다른 배속으로 구워진 컷(cal_speed_mismatch) — 좌표를 못 믿으니 그 컷만 증분 청소 대상.
가짜 청소본은 정답을 아는 합성 영상(test_clean_base_calibrate 와 같은 무늬 — 프레임마다 다른 칸 무늬).
"""
import shutil
from pathlib import Path

import numpy as np
import pytest

from shopping_shorts import clean_base as cb
from shopping_shorts import frame_match as fm
from shopping_shorts import mix_pipeline as mp
from shopping_shorts.tests.test_clean_base_calibrate import FPS, _encode, _pattern

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


# ── 1) 판정 = 보정된 정본 ──────────────────────────────────────────────────────

class _Store:
    def __init__(self, job): self.job = job; self.updates = []
    def get_mix_job(self, jid): return self.job
    def update_mix_job(self, jid, **kw): self.updates.append(kw); self.job.update(kw)
    def get_setting(self, k, d=None): return "1" if k == "clean_base_enabled" else d


@pytest.fixture
def short_a(tmp_path, monkeypatch):
    """옛 청소본에서 A 조각이 지도보다 짧다: A(지도 fin 0·1.2초)는 파일 안 3프레임 늦게 27프레임만 있고
    바로 30프레임부터 B(지도 fin 1.2 = 36프레임)가 시작한다.
    보정 전(off 없음): A 컷이 원본 0~1.2초를 덮는다 → '덮임'.
    보정 후: A 는 B 시작(1.0초)에서 잘려 원본 0~0.9초만 덮는다 → 0.3초 모자람(끝 자투리 허용 0.18초 초과) → '안 덮임'."""
    work = tmp_path / "j"
    (work / "s0").mkdir(parents=True)
    rng = np.random.default_rng(5)
    src = np.stack([_pattern(rng) for _ in range(int(3.5 * FPS))])
    _encode(src, work / "s0" / "v.mp4")
    clean = np.stack([_pattern(rng) for _ in range(72)])
    clean[3:30] = src[0:27]
    clean[30:54] = src[60:84]
    f = work / "final_clean_0123456789abcdef.mp4"
    _encode(clean, f)
    import os
    os.utime(f, (cb.FRAME_EXACT_SINCE - 3600, cb.FRAME_EXACT_SINCE - 3600))   # 옛 조립 파일(보정 대상)
    plan = {"beats": [
        {"beat_idx": 0, "target_seconds": 1.2, "narration": "a", "tts_path": None,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 1.2}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 0.8, "narration": "b", "tts_path": None,
         "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 2.0, "end": 2.8}, "alternates": []}]}
    cb.save_base(work, sig="0123456789abcdef", path=str(f), plan=plan,
                 cuts=[{"video_id": "s0", "beat_idx": 0, "src": 0.0, "sdur": 1.2, "fin": 0.0, "dur": 1.2},
                       {"video_id": "s0", "beat_idx": 1, "src": 2.0, "sdur": 0.8, "fin": 1.2, "dur": 0.8}])
    assert "calibrated" not in cb.load_base(work)          # 옛 정본(보정 전)
    job = {"job_id": "j", "edit_plan": plan, "urls": ["u"], "subtitle_removal": 1, "customer_id": 0}
    monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: {"s0": 3.5})
    mp._JUDGE_CACHE.clear()
    return work, job


def _uncal_uncovered(work, job):
    """보정 **없이** 판정했다면(옛 버튼·안내) — 대조용."""
    base = cb.load_base(work)
    base.pop("calibrated", None)
    for c in base["cuts"]:
        for k in ("off", "off_end", "cal_unsure", "cal_by", "cal_speed_mismatch"):
            c.pop(k, None)
    plan = job["edit_plan"]
    return cb.remap_plan(plan, base, tts_durs=mp.clean_tts_durs(plan), src_durs={"s0": 3.5})[1]


def test_판정은_보정된_정본으로_calibrate_False도(short_a):
    work, job = short_a
    assert _uncal_uncovered(work, job) == []                  # 보정 없이면 '덮임'(= 옛 버튼·안내의 거짓 과금 0)
    j = mp.clean_base_judge(_Store(job), job, work, calibrate=False)     # 옛 호출부 인자 — 무시하고 보정한다
    assert j["base"]["calibrated"] == cb.CAL_VERSION
    assert j["uncovered"] == [0]                               # 렌더와 같은 판정(A 끝 0.3초 모자람)
    assert cb.load_base(work)["calibrated"] == cb.CAL_VERSION  # 정본에 남는다(다음부터 즉시)
    assert mp.clean_base_judge(_Store(job), job, work)["uncovered"] == [0]


def test_보정은_정본당_한번만(short_a, monkeypatch):
    work, job = short_a
    decoded = []
    _orig = fm.frames
    monkeypatch.setattr(fm, "frames", lambda path, *a, **k: (decoded.append(Path(path).name), _orig(path, *a, **k))[1])
    mp.clean_base_judge(_Store(job), job, work)
    n1 = decoded.count("final_clean_0123456789abcdef.mp4")
    mp.clean_base_judge(_Store(job), job, work, calibrate=False)
    mp.clean_base_judge(_Store(job), job, work)
    assert n1 == 1 and decoded.count("final_clean_0123456789abcdef.mp4") == 1   # 두 번째부터 청소본을 안 푼다


def test_버튼은_렌더와_같은_판정으로_증분(short_a, monkeypatch, tmp_path):
    """보정 전 정본에서 버튼: 보정 없이 판정하면 '정본 재사용(과금 0)'으로 끝나고 렌더에서 과금된다.
    보정된 판정이면 버튼이 A 의 모자란 끝만 증분 청소한다(렌더와 같은 함수)."""
    work, job = short_a
    store = _Store(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    from shopping_shorts import video_assemble as _va
    monkeypatch.setattr(_va, "_apply_hook_inpoint", lambda *a, **k: None)   # 훅 시작점 이동은 여기 주제가 아니다
    monkeypatch.setattr(mp, "_vmake_keys", lambda *a, **k: ["k"])
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    assert _uncal_uncovered(work, job) == []                  # 보정 없이 판정하면 버튼은 '과금 0'으로 끝났을 것
    calls, sent = [], []
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: calls.append("charge") or 1)
    monkeypatch.setattr(mp, "_refund_clean", lambda *a, **k: None)
    monkeypatch.setattr(mp, "assemble_clean_video",
                        lambda *a, **k: calls.append("assemble" if k.get("clean_fn") else "reassemble") or None)

    def _cut(src, ss, dur, dst):
        Path(dst).write_bytes(b"p" * 2048); sent.append((round(float(ss), 3), round(float(dur), 3))); return str(dst)

    def _joined(items, keys, w, tag="", tier=None, **kw):
        out = {}
        for v, _ in items:
            q = Path(w) / f"{v}_clean.mp4"; q.write_bytes(b"q" * 2048); out[v] = str(q)
        return out, {}
    monkeypatch.setattr(mp, "_cut_piece", _cut)
    monkeypatch.setattr(mp, "_clean_joined", _joined)
    from shopping_shorts.tests._clean_consent import consent
    mp.run_clean_sources("j", "db", str(work.parent), **consent(store, job, work, "button"))
    assert calls == ["charge", "reassemble"], calls            # 증분 1콜 + 과금 0 재조립
    # 보낸 구간 = 렌더 판정이 말하는 모자란 곳(A 원본 0.9초 이후)만 — 칸 전체(0~1.2초)가 아니다
    assert len(sent) == 1 and sent[0][0] >= 0.85 and sent[0][1] <= 0.3 + cb.SPAN_TOL + cb.EXTEND_PAD + 1e-6, sent
    need = mp.clean_base_judge(_Store(job), job, work)
    assert need is not None and need["uncovered"] == []          # 증분 조각이 붙어 이제 렌더도 과금 0


# ── 2) 속도 불일치 컷 ──────────────────────────────────────────────────────────

SPEED = 1.3
# (원본 시작, 원본 길이 sdur = 완성본 길이 dur, 늦춘 프레임, 배속)
SCUTS = [(0.0, 1.2, 3, 1.0), (1.5, 1.2, 3, SPEED), (3.2, 1.2, 3, 1.0)]


def _speed_fake(tmp_path, cleaned_mid=True):
    rng = np.random.default_rng(9)
    src = np.stack([_pattern(rng) for _ in range(int(5.0 * FPS))])
    _encode(src, tmp_path / "src.mp4")
    n = int(round((sum(c[1] for c in SCUTS) + 0.6) * FPS))
    clean = np.stack([_pattern(rng) for _ in range(n)])
    fin = 0.0
    fins = []
    for s0, sd, lag, sp in SCUTS:
        fins.append(fin)
        for m in range(int(round(sd * FPS))):
            # 옛 조립이 이 조각을 sp 배속으로 구웠다: 청소본 m 프레임 = 원본 floor(m*sp)
            clean[int(round(fin * FPS)) + lag + m] = src[int(round(s0 * FPS)) + int(m * sp)]
        fin += sd
    _encode(clean, tmp_path / "final_clean_x.mp4")
    cuts = [{"beat_idx": i, "video_id": "v", "src": s0, "sdur": sd, "dur": sd, "fin": round(f, 3),
             "cleaned": (cleaned_mid if i == 1 else True)}
            for i, ((s0, sd, _lag, _sp), f) in enumerate(zip(SCUTS, fins))]
    base = {"sig": "x", "path": str(tmp_path / "final_clean_x.mp4"), "cuts": cuts, "extras": {},
            "beat_keys": {str(i): [["v", c["src"], round(c["src"] + c["sdur"], 3)]] for i, c in enumerate(cuts)}}
    return base


def _plan_for(base):
    return {"beats": [{"beat_idx": i, "target_seconds": c["dur"],
                       "primary": {"video_id": "v", "seg_id": "v-%d" % i, "start": c["src"],
                                   "end": round(c["src"] + c["sdur"], 3)}, "alternates": []}
                      for i, c in enumerate(base["cuts"])]}


def test_속도불일치_컷만_안덮임(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "SPEED_RECLEAN", True)      # 사장님 승인 뒤 켜는 스위치(과금)
    base = _speed_fake(tmp_path)
    out = cb.calibrate(tmp_path, base, {"v": str(tmp_path / "src.mp4")})
    flags = [bool(c.get("cal_speed_mismatch")) for c in out["cuts"]]
    assert flags == [False, True, False], [(c.get("off"), c.get("off_end"), c.get("cal_by")) for c in out["cuts"]]
    assert out["cal_speed"] == 1
    # 덮음: 가운데 컷만 안 덮임(렌더 컷 재생·재료 단위 둘 다)
    miss = {}
    for i, c in enumerate(out["cuts"]):
        _cuts, m = cb.replay_clips(out, [{"video_id": "v", "start": c["src"], "out_dur": c["dur"], "src_dur": c["sdur"]}])
        miss[i] = m
    assert not miss[0] and not miss[2] and miss[1], miss
    # 증분 청소가 보낼 구간 = 그 컷 원본 구간만(이미 지운 앞뒤 컷엔 돈이 안 나간다)
    assert [(round(g["start"], 2), round(g["end"], 2)) for g in miss[1]] == [(1.5, 2.7)]
    cov = cb.coverage(_plan_for(out), out)
    assert cov == {0: "covered", 1: "changed", 2: "covered"}, cov


def test_부분청소_안지운컷은_표식만(tmp_path):
    """부분 청소 정본에서 원래 안 지우는 컷(cleaned:false)은 속도 불일치여도 과금 대상이 아니다 — 표식만."""
    base = _speed_fake(tmp_path, cleaned_mid=False)
    out = cb.calibrate(tmp_path, base, {"v": str(tmp_path / "src.mp4")})
    mid = out["cuts"][1]
    assert mid.get("cal_speed_mismatch") is True and not cb._speed_bad(mid)
    assert not any(cb._speed_bad(c) for c in out["cuts"])


def test_정상_컷은_속도불일치가_아니다(tmp_path):
    """같은 무늬로 전부 1배속이면 아무 컷도 표시되지 않는다(오탐 방지)."""
    global SCUTS
    keep = SCUTS
    try:
        SCUTS = [(s0, sd, lag, 1.0) for s0, sd, lag, _sp in keep]
        base = _speed_fake(tmp_path)
    finally:
        SCUTS = keep
    out = cb.calibrate(tmp_path, base, {"v": str(tmp_path / "src.mp4")})
    assert not any(c.get("cal_speed_mismatch") for c in out["cuts"]) and out["cal_speed"] == 0


def test_속도불일치_스위치_꺼짐이_기본_표식만_과금없음(tmp_path, monkeypatch):
    """기본(스위치 꺼짐): 속도 불일치 컷은 표식·개수만 남고 **덮은 것으로 쳐서 재청소(과금)가 안 나간다**."""
    monkeypatch.setattr(cb, "SPEED_RECLEAN", False)
    base = _speed_fake(tmp_path)
    out = cb.calibrate(tmp_path, base, {"v": str(tmp_path / "src.mp4")})
    assert out["cuts"][1].get("cal_speed_mismatch") is True and out["cal_speed"] == 1
    assert not any(cb._speed_bad(c) for c in out["cuts"])
    c = out["cuts"][1]
    _cuts, miss = cb.replay_clips(out, [{"video_id": "v", "start": c["src"], "out_dur": c["dur"], "src_dur": c["sdur"]}])
    assert not miss, miss
    assert cb.coverage(_plan_for(out), out) == {0: "covered", 1: "covered", 2: "covered"}


def test_속도불일치_스위치_환경변수로_켠다(monkeypatch):
    import importlib
    monkeypatch.setenv("CLEAN_SPEED_RECLEAN", "1")
    m = importlib.reload(cb)
    try:
        assert m.SPEED_RECLEAN is True
        assert m._speed_bad({"cal_speed_mismatch": True}) and not m._speed_bad({"cal_speed_mismatch": True, "cleaned": False})
    finally:
        monkeypatch.delenv("CLEAN_SPEED_RECLEAN")
        importlib.reload(cb)
