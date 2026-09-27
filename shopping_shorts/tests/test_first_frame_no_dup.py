"""완성본 컷 조각의 **첫 프레임이 두 번 찍히지 않는지** — 편집 화면 합본과 같은 프레임 순서인지 영상으로 잰다.

왜 (2026-09-27, 서버 재현): 완성본 1차 조각(_render_mix)은 `setpts={factor}*PTS`(배율 1이면 setpts 없음)였다.
  `-ss`가 원본 프레임 사이에 떨어지면 첫 프레임 시각이 0이 아니라(예: +0.023초) `-r 30` 변환이 그 프레임을
  0초 자리에 한 번 더 찍어 조각 전체가 1프레임 늦게 움직였다. 편집 화면 합본(app._pvproxy_build enc)은
  `setpts=(PTS-STARTPTS)*slow`라 중복이 없었다 → 두 경로 순서가 1프레임 갈렸다.

검사: 프레임마다 밝기가 다른 합성 원본(프레임 번호 = 밝기)을 프레임 사이 시각부터 읽어
  ① 첫 두 프레임 밝기가 다른가(중복 없음) ② 완성본과 편집 화면의 프레임 밝기 순서가 같은가.
  배율 1(setpts 없던 자리)과 느리게(1.111배) 둘 다(CASES).
"""
import shutil
import subprocess

import numpy as np
import pytest

from shopping_shorts import video_assemble as va

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                reason="ffmpeg 없음")

STEP = 3            # 프레임마다 밝기 +3 (재인코딩 잡음 ±1보다 넉넉히)

# (원본 fps, -ss 시각, 원본 읽는 길이) — 서버(ffmpeg 6.1)·로컬(8.1) 실측으로 옛 식이 틀리는 자리:
#   25fps·0.51초·배율1  → 옛 식(setpts 없음) 첫 프레임 13,13,14… (중복)
#   30fps·0.52초·1.11배 → 옛 식(factor*PTS) 16,17,17,18… (시작 어긋남이 배율로 커져 1프레임 늦음)
CASES = [("25", 0.51, 1.0), ("30", 0.52, 0.9)]


def _make_src(tmp_path, fps):
    p = tmp_path / "ramp.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s=180x320:r={fps}:d=2",
                    "-vf", f"format=yuv420p,geq=lum='16+{STEP}*N':cb=128:cr=128",
                    "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(p)],
                   check=True, stdin=subprocess.DEVNULL)
    return str(p)


def _tts(tmp_path, sec):
    p = tmp_path / "tts.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", f"{sec}", str(p)], check=True, stdin=subprocess.DEVNULL)
    return str(p)


def _levels(path):
    """프레임마다 가운데 밝기 → 원본 프레임 번호(밝기에서 거꾸로)."""
    # ★Y 평면을 그대로 읽는다 — format=gray 변환은 밝기 범위를 늘려 프레임 번호가 비선형으로 뭉개진다(실측)
    #   가운데 8x8만 잘라(crop — 크기 바꾸기는 값을 섞는다) Y 평면 평균
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-an", "-vsync", "0",
                        "-vf", "crop=8:8", "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"],
                       capture_output=True, check=True, stdin=subprocess.DEVNULL)
    a = np.frombuffer(r.stdout, np.uint8).reshape(-1, 96)[:, :64].astype(float).mean(axis=1)
    return [round((x - 16) / STEP, 1) for x in a]


def _render_final(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start, fit=False):
    plan = [{"video_id": "V", "seg_id": "V-0", "start": start, "src_dur": src_dur, "out_dur": out_dur,
             # [속도 맞추기] = 계획의 playback_speed(읽는 길이/출력 길이, plan_beat_clips_for 와 같은 값)
             **({"playback_speed": src_dur / out_dur} if fit else {})}]
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda *a, **k: [dict(x) for x in plan])
    monkeypatch.setattr(va, "_trans_sec", lambda: 0.0)
    beat = {"beat_idx": 0, "narration": "테스트",
            "primary": {"video_id": "V", "seg_id": "V-0", "start": 0.0, "end": 3.0}}
    work = tmp_path / "final"
    work.mkdir()
    return va._render_mix({"beats": [beat]}, {0: tts}, {"V": src}, work)


def _render_editor(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start, fit=False):
    from shopping_shorts import app

    class _NoStore:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, *_a, **_k):
            return None

    pv = tmp_path / "pv"
    monkeypatch.setattr(app, "Store", _NoStore)
    monkeypatch.setattr(app, "_pvproxy_dir", lambda _j: pv)
    app._pvproxy_build("testjob", "sigdup", [{"video_id": "V", "start": start, "dur": out_dur,
                                              "src_dur": src_dur, **({"fit": 1} if fit else {})}],
                       {"V": src}, [1], {0: tts})
    out = pv / "sigdup.mp4"
    assert out.exists(), "편집 화면 합본 굽기 실패"
    return out


@pytest.mark.parametrize("fps,start,src_dur", CASES, ids=["25fps-speed1", "30fps-slow1.11"])
def test_first_frame_not_duplicated_and_same_as_editor(tmp_path, monkeypatch, fps, start, src_dur):
    src = _make_src(tmp_path, fps)
    tts = _tts(tmp_path, 1.0)
    fl = _levels(_render_final(tmp_path, monkeypatch, src, tts, 1.0, src_dur, start))
    el = _levels(_render_editor(tmp_path, monkeypatch, src, tts, 1.0, src_dur, start))
    assert len(fl) == 30 and len(el) == 30, (len(fl), len(el))
    assert abs(fl[0] - fl[1]) >= 0.5, f"완성본 첫 프레임 중복: {fl[:4]}"
    # 두 경로가 같은 원본 프레임을 같은 자리에 — 느리게(1.11배)면 원본 프레임이 가끔 두 번 나오는 자리까지 같아야 한다
    diff = [i for i, (a, b) in enumerate(zip(fl, el)) if abs(a - b) >= 0.5]
    assert not diff, f"완성본 {fl[:8]} vs 화면 {el[:8]} — 다른 프레임 {diff[:6]}"


# ── B: 배율·정지 몫을 두 경로가 **같은 함수**(_speed_and_freeze·motion_frames)로 정하나 ─────────────
#   정지(원본 0.5초 → 1초: 상한까지만 움직이고 나머지 정지) · [속도 맞추기](0.6초를 1초로 끝까지 움직임)
#   freeze-round: 움직이는 몫을 motion_frames로 자르지 않으면 화면만 1프레임 더 움직였다(42사례 중 24사례, 합성 실측)
@pytest.mark.parametrize("src_dur,fit,start", [(0.5, False, 0.52), (0.62, False, 0.535), (0.6, True, 0.52),
                                               (0.95, False, 0.52)],
                         ids=["freeze", "freeze-round", "fit", "slow-in-cap"])
def test_speed_and_hold_same_frames_as_editor(tmp_path, monkeypatch, src_dur, fit, start):
    src = _make_src(tmp_path, "30")
    tts = _tts(tmp_path, 1.0)
    fl = _levels(_render_final(tmp_path, monkeypatch, src, tts, 1.0, src_dur, start, fit))
    el = _levels(_render_editor(tmp_path, monkeypatch, src, tts, 1.0, src_dur, start, fit))
    assert len(fl) == 30 and len(el) == 30, (len(fl), len(el))
    diff = [i for i, (a, b) in enumerate(zip(fl, el)) if abs(a - b) >= 0.5]
    assert not diff, f"완성본 {fl} vs 화면 {el} — 다른 프레임 {diff[:6]}"
    if not fit and src_dur < 1.0 / va._MAX_SLOWMO:
        # 정지 컷: 움직이는 프레임 수 = motion_frames(나머지는 같은 그림)
        play, freeze = va._speed_and_freeze(src_dur, 1.0)
        mv = va.motion_frames(30, play, freeze)
        assert len(set(el[mv - 1:])) == 1 and el[mv - 2] != el[mv - 1], (mv, el)


def test_app_has_no_own_slowmo_cap():
    """편집 화면 합본이 늘리기 상한을 따로 적지 않는다 — 상한은 video_assemble._MAX_SLOWMO 한 곳(0순위-B)."""
    import re
    from pathlib import Path as _P
    src = (_P(va.__file__).parent / "app.py").read_text(encoding="utf-8")
    i = src.index("def _pvproxy_build(")
    body = src[i:src.index(chr(10) + "@app.", i)]
    assert not re.search(r"1\.15", src), "app.py 에 1.15 리터럴이 남아 있다"
    assert "_speed_and_freeze(" in body and "motion_frames(" in body and "cut_setpts(" in body


# ── 원본 영상이 계획보다 먼저 끝나는 컷(서버 job a90253dd235b 0번 칸 실측: 파일 길이는 7.87초인데 영상 프레임은
#   7.70초에서 끝나 -t 1.003 중 0.83초만 읽혔다) ──
#   종전엔 첫 프레임 중복이 우연히 1프레임을 메워 줬다. 중복을 없애자 모자란 몫이 드러나 칸이 1프레임 짧아지고
#   뒤 칸이 전부 1프레임 당겨졌다(완성본 23.29→23.25초). 늘 컷 프레임 수(_nf)를 채워야 한다 — 화면 합본처럼.
def _make_src_audio_longer(tmp_path):
    """영상 2초 + 소리 2.6초 — 파일 길이(_probe_duration)가 영상보다 길다."""
    p = tmp_path / "ramp_av.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=black:s=180x320:r=30:d=2",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-filter_complex", f"[0:v]format=yuv420p,geq=lum='16+{STEP}*N':cb=128:cr=128[v]",
                    "-map", "[v]", "-map", "1:a", "-t", "2.6",
                    "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)],
                   check=True, stdin=subprocess.DEVNULL)
    return str(p)


@pytest.mark.parametrize("src_dur", [0.8, 0.95], ids=["freeze", "no-freeze"])
def test_video_ends_before_plan_keeps_cut_frames(tmp_path, monkeypatch, src_dur):
    src = _make_src_audio_longer(tmp_path)
    assert va._probe_duration(src) > 2.4
    tts = _tts(tmp_path, 1.0)
    # 1.7초부터 읽는다 → 영상은 0.3초(9프레임)뿐
    fl = _levels(_render_final(tmp_path, monkeypatch, src, tts, 1.0, src_dur, 1.7))
    el = _levels(_render_editor(tmp_path, monkeypatch, src, tts, 1.0, src_dur, 1.7))
    assert len(el) == 30
    assert len(fl) == 30, f"완성본 컷 프레임 {len(fl)} != 30 — 영상이 모자라면 칸이 짧아진다"
