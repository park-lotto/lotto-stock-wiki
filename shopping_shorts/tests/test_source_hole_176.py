# -*- coding: utf-8 -*-
"""관제 176: 소스 영상의 화면 구멍(패킷 없는 구간) — 그 안의 컷이 0프레임으로 빠지지 않는다.

사고(2aa06a122f21 김성현님, 2026-10-09): s1 영상 4.13→9.20초에 화면 패킷이 없었다. 칸 1 둘째 컷(4.6초부터 1.98초)이
0프레임 → 칸이 59프레임 짧아져 컷 지도가 안 남음 → 자막제거가 예비 계산 컷으로 고른 장면을 자르고 정본을 적음 →
완성본 6/9칸이 편집 화면과 다른 장면(감정짤 2개 빠짐).
여기서는: ① 받는 문(normalize_playable)이 구멍을 메운다 ② 조립은 빈 컷을 직전 화면으로 채워 같은 프레임 수를 낸다
③ 컷 지도가 없으면 자막제거는 관문·업체를 부르기 전에 멈춘다(예비 계산으로 강행하지 않는다).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts import media_download as md, mix_pipeline as mp, video_assemble as va

_FF = shutil.which("ffmpeg") and shutil.which("ffprobe")
needs_ff = pytest.mark.skipif(not _FF, reason="ffmpeg 없음")


def _hole_video(path):
    """6초 영상에서 2~4초 화면 프레임을 뺀다(패킷 구멍 1.97→4.03초)."""
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=d=6:r=30:s=180x320",
         "-vf", "select='not(between(t,2,4))'", "-fps_mode", "passthrough",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True, stdin=subprocess.DEVNULL)
    return path


def _frame_md5s(args):
    o = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *args, "-an", "-f", "framemd5", "-"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True).stdout
    return [ln.split(",")[-1].strip() for ln in o.splitlines() if ln and not ln.startswith("#")]


@needs_ff
def test_video_holes_finds_the_hole_and_nothing_in_a_whole_video(tmp_path):
    gap = _hole_video(tmp_path / "gap.mp4")
    holes = md.video_holes(gap)
    assert len(holes) == 1 and 1.9 < holes[0][0] < 2.05 and 3.95 < holes[0][1] < 4.1, holes
    whole = tmp_path / "whole.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=d=2:r=30:s=180x320",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(whole)], check=True, stdin=subprocess.DEVNULL)
    assert md.video_holes(whole) == []


@needs_ff
def test_normalize_playable_fills_holes_and_keeps_timing(tmp_path):
    """받는 문에서 한 번 — 구멍이 직전 화면으로 메워지고(패킷이 30fps로 촘촘), 구멍 뒤 장면의 시각은 그대로다."""
    gap = _hole_video(tmp_path / "gap.mp4")
    after_hole = _frame_md5s(["-i", str(gap), "-vf", "select='gte(t,4.5)'", "-frames:v", "1"])[0]
    out = Path(md.normalize_playable(str(gap)))
    assert out.name.endswith("_h264.mp4") and out.exists()
    assert md.video_holes(out) == []
    n = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                            "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip().strip(","))
    assert 176 <= n <= 182, n                         # 6초 × 30fps — 구멍 2초(60프레임)가 채워졌다(구멍 난 원본은 119)
    # 구멍 안(3.0초) 화면 = 구멍 직전 화면이 서 있다(두 프레임이 같다)
    a = _frame_md5s(["-i", str(out), "-vf", "select='between(t,2.5,2.52)+between(t,3.5,3.52)'", "-fps_mode", "passthrough"])
    assert len(a) == 2 and a[0] == a[1]
    # 시각 보존 — 메운 파일의 4.5초 화면은 원본 4.5초와 같은 장면(재인코딩이라 md5 대신 구멍 직전 화면과 **다름**으로 본다)
    b = _frame_md5s(["-i", str(out), "-vf", "select='between(t,4.5,4.52)'", "-fps_mode", "passthrough"])
    assert b and b[0] != a[0] and after_hole


@needs_ff
def test_cut_read_hold_gives_full_frames_inside_the_hole(tmp_path):
    """조립 안전망 — 구멍 안의 창(2.5초부터 1초)을 직전 화면으로 채워 계획한 프레임 수(30)를 그대로 낸다."""
    gap = _hole_video(tmp_path / "gap.mp4")
    vf = va.cut_read_hold(2.5, 1.0) + ",fps=30"
    got = _frame_md5s(["-i", str(gap), "-vf", vf, "-frames:v", "30"])
    assert len(got) == 30 and len(set(got)) == 1, (len(got), len(set(got)))       # 30프레임 전부 같은 화면(서 있다)
    # 구멍이 파일 끝까지 이어져도(창이 영상 끝을 넘음) 마지막 화면으로 채운다
    tail = _frame_md5s(["-i", str(gap), "-vf", va.cut_read_hold(5.9, 0.6) + ",fps=30", "-frames:v", "18"])
    assert len(tail) == 18


def test_clean_stops_before_gate_and_vendor_when_assembly_has_no_cut_map(tmp_path, monkeypatch):
    """컷 지도 없는 조립본(= 조립이 계획과 달랐다) → 관문(_charge_clean)·업체·예비 계산 어느 것도 부르지 않고 멈춘다."""
    work = tmp_path / "w"
    work.mkdir()
    mix_raw = work / "mix_raw.mp4"
    mix_raw.write_bytes(b"raw")                        # 옆에 .cuts.json 없음
    job = {"job_id": "j", "subtitle_removal": 1, "customer_id": 0, "urls": ["a"],
           "edit_plan": {"beats": [{"beat_idx": 0, "narration": "a",
                                    "primary": {"video_id": "s0", "seg_id": "s0-a", "start": 1.0, "end": 3.0}}]}}
    called = []
    monkeypatch.setattr(mp, "_clean_final_found", lambda *a, **k: None)
    monkeypatch.setattr(mp, "clean_topup_plan", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: called.append("gate") or 0)
    monkeypatch.setattr(mp, "_vmake_clean", lambda *a, **k: called.append("vendor"))
    monkeypatch.setattr(mp, "_clean_partial", lambda *a, **k: called.append("vendor_partial"))
    monkeypatch.setattr(mp, "final_clip_pairs", lambda *a, **k: called.append("fallback_map") or [])
    monkeypatch.setattr(mp, "snapshot_cut_map", lambda *a, **k: (called.append("snapshot_map"), None)[1:] + (None,))
    fn = mp._final_clean_fn(None, job, "j", work, ["k"], 0)
    with pytest.raises(RuntimeError) as ei:
        fn(str(mix_raw))
    assert "[assembly_mismatch]" in str(ei.value)
    assert called == [], called
    assert not (work / "clean_base.json").exists()
    from shopping_shorts.app import clean_failure_kind
    assert clean_failure_kind(str(ei.value)) == "assembly_mismatch"
