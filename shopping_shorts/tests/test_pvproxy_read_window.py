"""편집 화면 합본(app._pvproxy_build) 컷 조각이 **읽기로 한 창 [start, start+src_dur) 밖 원본 프레임**을 싣지 않는지 영상으로 잰다.

왜 (2026-09-27, 서버 job 62ed6bf66eb9 1번 칸 2번 컷): 편집 화면 미리보기에 컷 끝 2프레임짜리 딴 장면(꼬치 그릴)이 끼었다.
  창 [24.846, 25.633)은 원본 프레임 746..768(23장)이고 769번(25.6333)부터 다음 장면인데, ffmpeg 입력 `-t`는 -ss 시각이 아니라
  **처음 남은 프레임(24.8667)** 부터 세어 769번까지 24장을 읽었다(서버 showinfo 실측 pts_time 0.787333). 느리게(1.15배) 늘려 2프레임.
검사: 프레임 번호 = 밝기인 합성 원본에서 -ss 가 프레임 사이(0.312)이고 창 끝이 프레임 경계(1.000 = 30번)에 딱 붙은 컷을 굽고,
  합본에 나온 원본 프레임 번호의 최대값이 창 안(≤29)인지 본다. 배율 1·정지 컷(1.15배로 늘리고 남는 몫 정지 — 62ed와 같은 꼴) 둘 다.
"""
import shutil
import subprocess

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                reason="ffmpeg 없음")

STEP = 3


def _make_src(tmp_path):
    p = tmp_path / "ramp.mp4"
    # 기본 libx264(B프레임 있음) — 실제 소재처럼 dts < pts 인 원본
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=black:s=180x320:r=30:d=2",
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
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-an", "-vsync", "0",
                        "-vf", "crop=8:8", "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"],
                       capture_output=True, check=True, stdin=subprocess.DEVNULL)
    a = np.frombuffer(r.stdout, np.uint8).reshape(-1, 96)[:, :64].astype(float).mean(axis=1)
    return [round((x - 16) / STEP, 1) for x in a]


def _render_editor(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start):
    from shopping_shorts import app

    class _NoStore:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, *_a, **_k):
            return None

    pv = tmp_path / "pv"
    monkeypatch.setattr(app, "Store", _NoStore)
    monkeypatch.setattr(app, "_pvproxy_dir", lambda _j: pv)
    app._pvproxy_build("testjob", "sigwin", [{"video_id": "V", "start": start, "dur": out_dur, "src_dur": src_dur}],
                       {"V": src}, [1], {0: tts})
    out = pv / "sigwin.mp4"
    assert out.exists(), "편집 화면 합본 굽기 실패"
    return out


# (시작, 읽는 길이, 출력 길이): 창 끝 = 1.000초 = 원본 30번 프레임의 시작 → 30번은 창 밖이다
@pytest.mark.parametrize("start,src_dur,out_dur", [(0.312, 0.688, 0.688), (0.312, 0.688, 0.85)],
                         ids=["speed1", "hold-slow1.15"])
def test_editor_cut_never_shows_frame_after_window(tmp_path, monkeypatch, start, src_dur, out_dur):
    src = _make_src(tmp_path)
    tts = _tts(tmp_path, out_dur)
    el = _levels(_render_editor(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start))
    last_in_window = int(np.ceil((start + src_dur) * 30 - 1e-6)) - 1        # 29
    first_in_window = int(np.ceil(start * 30 - 1e-6))                        # 10
    assert max(el) <= last_in_window + 0.4, f"창 밖 원본 프레임이 실렸다(잔상): 최대 {max(el)} > {last_in_window} — {el}"
    assert min(el) >= first_in_window - 0.4, f"창 앞 원본 프레임이 실렸다: 최소 {min(el)} < {first_in_window} — {el}"
    # 창 안 마지막 프레임은 실려야 한다(너무 많이 잘라 1장 모자라게 만들지 않았나)
    assert abs(max(el) - last_in_window) < 0.5, (max(el), el)


def test_pvproxy_trim_marker_in_cut_key():
    """조각 곳간 키에 읽는 창 표식이 있어야 옛 조각(1프레임 더 읽은 것)을 재사용하지 않는다."""
    from pathlib import Path
    from shopping_shorts import app
    src = (Path(app.__file__)).read_text(encoding="utf-8")
    i = src.index("def _pvproxy_build(")
    body = src[i:src.index(chr(10) + "@app.", i)]
    assert '"rdx1"' in body and "video_assemble.cut_read_trim(take)" in body
    assert "trim=end=" not in body, "읽는 창 끊기를 app 에 따로 적지 마라 — video_assemble.cut_read_trim 한 곳(0순위-B)"
    va_src = (Path(app.__file__).parent / "video_assemble.py").read_text(encoding="utf-8")
    assert "{cut_read_trim(_c_src)}," in va_src


def _render_final(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start):
    from shopping_shorts import video_assemble as va
    plan = [{"video_id": "V", "seg_id": "V-0", "start": start, "src_dur": src_dur, "out_dur": out_dur}]
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda *a, **k: [dict(x) for x in plan])
    monkeypatch.setattr(va, "_trans_sec", lambda: 0.0)
    beat = {"beat_idx": 0, "narration": "테스트", "primary": {"video_id": "V", "seg_id": "V-0", "start": 0.0, "end": 3.0}}
    work = tmp_path / "final"
    work.mkdir()
    return va._render_mix({"beats": [beat]}, {0: tts}, {"V": src}, work)


# ★완성본(_render_mix 1차 조각)도 같은 `-ss … -t … -i` 읽기라 같은 1프레임을 더 읽었다(서버 실측: 같은 창·같은 필터로 마지막 프레임 차 55.5).
#   두 경로가 같은 함수(video_assemble.cut_read_trim)로 끊는다 — 한쪽만 빼면 이 파일의 테스트 하나가 빨강이 된다.
@pytest.mark.parametrize("start,src_dur,out_dur", [(0.312, 0.688, 0.688), (0.312, 0.688, 0.85)],
                         ids=["speed1", "hold-slow1.15"])
def test_final_cut_never_shows_frame_after_window(tmp_path, monkeypatch, start, src_dur, out_dur):
    src = _make_src(tmp_path)
    tts = _tts(tmp_path, out_dur)
    fl = _levels(_render_final(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start))
    el = _levels(_render_editor(tmp_path, monkeypatch, src, tts, out_dur, src_dur, start))
    assert max(fl) <= 29.4, f"완성본에 창 밖 원본 프레임: {fl}"
    assert abs(max(fl) - 29) < 0.5, fl
    diff = [i for i, (x, y) in enumerate(zip(fl, el)) if abs(x - y) >= 0.5]
    assert len(fl) == len(el) and not diff, f"완성본 {fl} vs 화면 {el} — 다른 프레임 {diff[:6]}"
