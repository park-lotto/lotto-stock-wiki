# -*- coding: utf-8 -*-
"""덧지우기(2026-10-03, 황선희님 job 817308da1647) — 이미 지운 장면은 그대로 두고 고른 장면만 지워 붙인다.

실사고: 9장면 지움 → 덜 지워진 2장면만 골라 다시 → 나머지 7장면이 원본으로 돌아갔다.
잡는 것:
  ① 저장되는 선택 = 이미 지운 장면 ∪ 고른 장면(고른 것만 저장하면 원본 복귀)
  ② 업체로 보내는 컷 = 고른 것 중 이 등급으로 아직 안 지운 것(같은 등급 재선택은 과금 0)
  ③ 실제 ffmpeg — 덧지운 뒤 앞서 지운 구간이 지워진 채 그대로, 안 고른 구간은 원본 그대로, 프레임 수 불변
  ④ 완성본 청소 경로(_final_clean_fn) 전체 — 업체로 간 프레임 수, 정본(선택·컷별 등급), 청소본 옆 지도
  ⑤ 재사용 분기가 정본 지도를 스냅샷으로 다시 유도하지 않는다(그 파일을 만든 지도 = assembled)
  ⑥ 과금 안내 — 덧지우기 초만, 문구
"""
import shutil
import subprocess

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import clean_base as cb


def _plan():
    return {"beats": [
        {"beat_idx": 0, "target_seconds": 1.0, "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 1.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 1.0, "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 4.0, "end": 5.0}, "alternates": []},
        {"beat_idx": 2, "target_seconds": 1.0, "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 8.0, "end": 9.0}, "alternates": []}]}


CUTS = [{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 1.0},    # 프레임 0~29
        {"video_id": "s1", "beat_idx": 1, "src": 4.0, "fin": 1.0, "dur": 1.0},    # 30~59
        {"video_id": "s0", "beat_idx": 2, "src": 8.0, "fin": 2.0, "dur": 1.0}]    # 60~89
K0, K1, K2 = "0|s0|0.00", "1|s1|4.00", "2|s0|8.00"


def _wire(monkeypatch):
    """판정 함수들이 실제 TTS·소스 없이 돌게 — 컷 목록·경로 종류·스위치만 고정한다(판정 로직은 실물)."""
    monkeypatch.setattr(mp, "_clean_strategy", lambda j: "final")
    monkeypatch.setattr(mp, "clean_base_on", lambda store, cid=0: True)
    monkeypatch.setattr(mp, "Store", lambda *a, **k: None)
    monkeypatch.setattr(mp, "clean_pick_cuts", lambda j, w: [
        dict(c, ci=i, key=mp.cut_key(c), sel=mp.cut_selected(c, mp.clean_selection_of(j))) for i, c in enumerate(CUTS)])


def _job(sel=None, tier="pro", pick=None):
    j = {"edit_plan": _plan(), "customer_id": 0, "subtitle_removal": 1, "clean_tier": tier, "clean_cuts": sel}
    if pick:
        j["_clean_pick"] = pick
    return j


def _save_base(tmp_path, sel, tier="pro", cut_map="assembled", cut_tiers=None, extras=None):
    job = _job(sel, tier)
    sig = mp._clean_sig(job)
    f = tmp_path / ("final_clean_%s.mp4" % sig)
    f.write_bytes(b"c" * 4096)
    cuts = [dict(c, cleaned=mp.cut_selected(c, sel)) for c in CUTS]
    base = cb.save_base(tmp_path, sig=sig, path=str(f), plan=job["edit_plan"], cuts=cuts, sel=sel)
    base["cut_map"] = cut_map
    if cut_tiers:
        base["cut_tiers"] = cut_tiers
    if extras:
        base["extras"] = extras
    cb._write(tmp_path, base)
    return base


def test_merged_selection_keeps_already_cleaned(tmp_path, monkeypatch):
    _wire(monkeypatch)
    job = _job([K0, K1])
    _save_base(tmp_path, [K0, K1])
    # 2장면 지운 뒤 그중 1장면만 골라 다시 → 저장 값은 여전히 2장면(원본 복귀 없음)
    assert sorted(mp.clean_cuts_merged(job, tmp_path, [K1])) == sorted([K0, K1])
    # 안 지운 장면을 더 고르면 전부 → None(전체)
    assert mp.clean_cuts_merged(job, tmp_path, [K2]) is None


def test_merged_selection_without_base_is_just_picked(tmp_path, monkeypatch):
    _wire(monkeypatch)
    assert mp.clean_cuts_merged(_job(None), tmp_path, [K1]) == [K1]


def test_topup_sends_only_cuts_not_done_at_this_tier(tmp_path, monkeypatch):
    _wire(monkeypatch)
    _save_base(tmp_path, [K0])
    # 새 장면(K2)을 더 고름 → K2만 보낸다. 이미 고급으로 지운 K0을 같이 골라도 다시 안 보낸다.
    top = mp.clean_topup_plan(_job([K0, K2], pick=[K0, K2]), tmp_path)
    assert top is not None and top["send"] == [K2] and abs(top["seconds"] - 1.0) < 1e-6
    assert top["tiers"] == {K0: "pro", K2: "pro"}
    # 같은 등급으로 이미 지운 장면만 다시 고름 → 보낼 것 없음(과금 0)
    assert mp.clean_topup_plan(_job([K0], pick=[K0]), tmp_path) is None
    # 다른 등급으로 다시 고름 → 그 장면만 그 등급으로 보낸다
    top = mp.clean_topup_plan(_job([K0], tier="basic", pick=[K0]), tmp_path)
    assert top is not None and top["send"] == [K0] and top["tiers"] == {K0: "basic"}
    # 고른 것이 없으면(렌더·전체 버튼) 덧지우기가 아니다
    assert mp.clean_topup_plan(_job([K0, K2]), tmp_path) is None


def test_topup_refuses_when_base_cannot_be_trusted(tmp_path, monkeypatch):
    _wire(monkeypatch)
    job = _job([K0, K2], pick=[K2])
    _save_base(tmp_path, [K0], cut_map="snapshot")          # 그 파일을 만든 지도가 아니다
    assert mp.clean_topup_plan(job, tmp_path) is None
    _save_base(tmp_path, [K0], extras={"cb1_0": {"path": "x"}})      # 증분 조각이 붙은 정본(편성이 바뀌었다)
    assert mp.clean_topup_plan(job, tmp_path) is None
    base = _save_base(tmp_path, [K0])
    base["cuts"][2]["fin"] = 2.2                             # 정본 지도에서 그 컷 자리가 다르다(6프레임)
    cb._write(tmp_path, base)
    assert mp.clean_topup_plan(job, tmp_path) is None
    _save_base(tmp_path, [K0])
    other = dict(job, edit_plan=dict(_plan(), beats=_plan()["beats"][:2]))     # 지금 편성이 정본을 만든 편성과 다르다
    assert mp.clean_topup_plan(other, tmp_path) is None


def test_cut_states_report_kept_and_tier(tmp_path, monkeypatch):
    _wire(monkeypatch)
    _save_base(tmp_path, [K0, K2], cut_tiers={K2: "basic"})
    states, topup = mp.clean_cut_states(_job([K0, K2]), tmp_path)
    assert topup is True
    assert [s["kept"] for s in states] == [True, False, True]
    assert states[0]["done"] == {"basic": False, "pro": True}
    assert states[2]["done"] == {"basic": True, "pro": False}       # 덧지운 컷은 컷별 등급
    assert states[1]["done"] == {"basic": False, "pro": False}


def test_charge_plan_counts_only_topup_seconds(tmp_path, monkeypatch):
    _wire(monkeypatch)
    base = _save_base(tmp_path, [K0])
    monkeypatch.setattr(mp, "clean_base_judge", lambda store, job, work, **k: {
        "base": base, "plan2": {}, "uncovered": [], "extend": [], "tier_upgrade": False})
    job = _job([K0, K2], pick=[K2])
    plan = mp.clean_charge_plan(None, job, tmp_path, mode="button")
    assert plan["kind"] == "full" and plan["reason"] == "topup"
    assert plan["seconds"] == 1.0 and plan["credits"] == mp.clean_credit_estimate(1.0, "pro")
    assert "이미 지운 장면은 그대로" in mp.clean_charge_message(plan)
    assert mp.clean_consent_error(plan, None, None) is not None        # 돈이 나가니 동의를 받는다
    # 이미 지운 장면만 같은 등급으로 고르면 정본 재사용(과금 0)
    again = mp.clean_charge_plan(None, _job([K0], pick=[K0]), tmp_path, mode="button")
    assert again["kind"] == "reuse" and again["seconds"] == 0.0
    # 같은 장면을 **다른 등급**으로 다시 고르면 정본이 '다 덮는다'여도 그 장면만 다시 지운다(버튼이 덧지우기를 먼저 본다)
    redo = mp.clean_charge_plan(None, _job([K0], tier="basic", pick=[K0]), tmp_path, mode="button")
    assert redo["kind"] == "full" and redo["reason"] == "topup" and redo["seconds"] == 1.0


def test_untrusted_base_other_tier_repick_is_not_silently_ignored(tmp_path, monkeypatch):
    """덧붙일 수 없는 정본(지도를 못 믿음)에서 다른 등급으로 몇 장면만 고르면 — '정본이 다 덮는다'로 조용히 끝나면 안 된다.
    저장된 선택(이미 지운 것 ∪ 고른 것)을 그 등급으로 다시 지우고, 확인창은 그 초를 말한다."""
    _wire(monkeypatch)
    base = _save_base(tmp_path, [K0, K2], cut_map="snapshot")
    monkeypatch.setattr(mp, "clean_base_judge", lambda store, job, work, **k: {
        "base": base, "plan2": {}, "uncovered": [], "extend": [], "tier_upgrade": False})
    job = _job([K0, K2], tier="basic", pick=[K0])
    assert mp.clean_topup_plan(job, tmp_path) is None and mp.clean_repick_full(job, tmp_path) is True
    plan = mp.clean_charge_plan(None, job, tmp_path, mode="button")
    assert plan["kind"] == "full" and plan["reason"] == "reselect" and plan["seconds"] == 2.0
    assert "함께 다시 지웁니다" in mp.clean_charge_message(plan)
    # 같은 등급으로 이미 지운 장면만 고르면 그대로 재사용(과금 0)
    same = _job([K0, K2], tier="pro", pick=[K0])
    assert mp.clean_repick_full(same, tmp_path) is False
    assert mp.clean_charge_plan(None, same, tmp_path, mode="button")["kind"] == "reuse"
    # 고른 것이 없는 요청(렌더·전체 버튼)은 종전 그대로
    assert mp.clean_repick_full(_job([K0, K2], tier="basic"), tmp_path) is False


needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")


def _mk(path, n=90):
    """30fps n프레임 — 프레임 번호가 곧 밝기(20,22,24,…). 소리 포함."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x128:r=30:d=%.3f" % (n / 30.0 + 1),
                    "-f", "lavfi", "-i", "sine=f=440:r=48000:d=%.3f" % (n / 30.0 + 1),
                    "-vf", "geq=lum='mod(N*2,200)+20':cb=128:cr=128", "-frames:v", str(n),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)


def _lumas(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=1:1,format=gray",
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return list(raw)


def _fake_vendor(sent, lum):
    def _fn(src, keys, out, tier=None, **k):
        sent.append((mp._probe_fps_frames(src)[2], tier))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", "geq=lum=%d:cb=128:cr=128" % lum[0],
                        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", "-c:a", "copy", str(out)], check=True)
        return str(out)
    return _fn


@needs_ffmpeg
def test_topup_splice_keeps_earlier_cleaned_frames(tmp_path, monkeypatch):
    raw = tmp_path / "mix_raw.mp4"
    _mk(raw)
    sent, lum = [], [0]
    monkeypatch.setattr(mp, "_vmake_clean", _fake_vendor(sent, lum))
    a = tmp_path / "final_clean_a.mp4"
    mp._clean_partial(str(raw), CUTS, [K0], ["k"], str(a), "pro", tmp_path)            # 1차: 컷0만 지움(까맣게)
    lum[0] = 250                                                                       # 2차 업체 결과는 하얗게(구분)
    b = tmp_path / "final_clean_b.mp4"
    mp._clean_partial(str(raw), CUTS, [K2], ["k"], str(b), "pro", tmp_path, over=str(a), tag="t1")
    assert sent == [(30, "pro"), (30, "pro")]                                          # 2차도 고른 30프레임만
    o, r = _lumas(raw), _lumas(b)
    assert len(r) == len(o) == 90
    assert all(v < 12 for v in r[0:30])                              # ★앞서 지운 컷0이 지워진 채 그대로(원본 복귀 없음)
    assert all(abs(x - y) <= 2 for x, y in zip(o[30:60], r[30:60]))  # 안 고른 컷1은 원본 그대로, 제자리
    assert all(v > 240 for v in r[60:90])                            # 이번에 고른 컷2만 새로 지워짐


@needs_ffmpeg
def test_topup_stops_before_vendor_when_base_length_differs(tmp_path, monkeypatch):
    raw, short = tmp_path / "mix_raw.mp4", tmp_path / "old_clean.mp4"
    _mk(raw, 90)
    _mk(short, 60)
    sent = []
    monkeypatch.setattr(mp, "_vmake_clean", _fake_vendor(sent, [0]))
    with pytest.raises(RuntimeError, match="덧지울 수 없습니다"):
        mp._clean_partial(str(raw), CUTS, [K2], ["k"], str(tmp_path / "o.mp4"), "pro", tmp_path, over=str(short), tag="t")
    assert sent == []                                                # 업체를 부르기 전에 멈춘다(과금 0)


@needs_ffmpeg
def test_final_clean_fn_topup_end_to_end(tmp_path, monkeypatch):
    """완성본 청소 경로 전체: 1차(컷0) → 덧지우기(컷2) → 같은 등급 재선택(과금 0) → 옛 선택으로 되돌아가도 지도는 그 파일의 것."""
    _wire(monkeypatch)
    raw = tmp_path / "mix_raw.mp4"
    _mk(raw)
    sent, lum = [], [0]
    monkeypatch.setattr(mp, "_vmake_clean", _fake_vendor(sent, lum))
    monkeypatch.setattr(mp, "_charge_clean", lambda store, cid, n: 0)
    monkeypatch.setattr(mp, "_va_read_cut_map", lambda p: [dict(c) for c in CUTS])
    # 1차: 컷0만
    job1 = _job([K0])
    a = mp._final_clean_fn(None, job1, "j", tmp_path, ["k"], 0)(str(raw))
    base1 = cb.load_base(tmp_path)
    assert base1["cut_map"] == "assembled" and base1["sel"] == [K0]
    assert mp._read_clean_sidecar(a)["cuts"] is not None            # 청소본 옆에 그 파일을 만든 지도
    # 2차: 컷2만 골라 다시 — 저장 값은 합집합, 업체로는 컷2(30프레임)만
    merged = mp.clean_cuts_merged(job1, tmp_path, [K2])
    assert sorted(merged) == sorted([K0, K2])
    lum[0] = 250
    job2 = _job(merged, pick=[K2])
    b = mp._final_clean_fn(None, job2, "j", tmp_path, ["k"], 0)(str(raw))
    assert sent == [(30, "pro"), (30, "pro")]
    o, r = _lumas(raw), _lumas(b)
    assert len(r) == 90
    assert all(v < 12 for v in r[0:30]) and all(v > 240 for v in r[60:90])
    assert all(abs(x - y) <= 2 for x, y in zip(o[30:60], r[30:60]))
    base2 = cb.load_base(tmp_path)
    assert base2["path"] == b and sorted(base2["sel"]) == sorted([K0, K2]) and base2["cut_map"] == "assembled"
    assert [c["cleaned"] for c in base2["cuts"]] == [True, False, True]
    assert base2["cut_tiers"] == {K0: "pro", K2: "pro"}
    # 3차: 이미 지운 컷0만 같은 등급으로 다시 고름 → 덧지우기 아님, 저장 값 그대로, 업체 호출 없음
    job3 = _job(mp.clean_cuts_merged(job2, tmp_path, [K0]), pick=[K0])
    assert sorted(job3["clean_cuts"]) == sorted([K0, K2]) and mp.clean_topup_plan(job3, tmp_path) is None
    assert mp._final_clean_fn(None, job3, "j", tmp_path, ["k"], 0)(str(raw)) == b
    assert len(sent) == 2
    # 옛 선택 파일로 되돌아가는 재사용 분기 — 정본 지도는 스냅샷 유도가 아니라 그 파일을 만든 지도
    monkeypatch.setattr(mp, "snapshot_cut_map", lambda *a, **k: (_ for _ in ()).throw(AssertionError("지도를 다시 유도하면 안 된다")))
    assert mp._final_clean_fn(None, job1, "j", tmp_path, ["k"], 0)(str(raw)) == a
    base4 = cb.load_base(tmp_path)
    assert base4["path"] == a and base4["cut_map"] == "assembled" and len(sent) == 2
