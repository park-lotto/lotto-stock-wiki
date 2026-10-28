"""칸 안 컷 경계가 편집 화면 합본(_pvproxy_build)과 완성본(_render_mix)에서 **같은 프레임**에 서는지 — 영상으로 잰다.

왜 (2026-09-27, job a90253dd235b 1번 칸 4번째 컷이 완성본에서 4프레임 늦게 시작):
  컷 조각을 `-t 초`로 자르면 30fps는 프레임 경계로 올림된다(1.012초 → 31프레임). 칸 안에서 조각을
  이어 붙이면 그 올림이 컷마다 쌓여 뒤 컷일수록 늦게 시작했다. 이제 두 경로 모두
  video_assemble.cut_frame_list(칸 안 누적 시각의 프레임 경계 차이)로 조각 프레임 수를 정한다.

검사: 빨강·초록·파랑 합성 소스로 칸 1개·컷 4개(1.012초 ×3 + 나머지)를 두 경로로 굽고,
  프레임마다 색을 읽어 컷이 바뀌는 프레임 번호를 찾는다. 기대값 = round(편집 화면 컷 누적 시각 × 30).
  (옛 -t 방식이면 0,31,62,93 — 기대 0,30,61,91과 어긋나 빨강이 된다.)
"""
import shutil
import subprocess

import numpy as np
import pytest

from shopping_shorts import video_assemble as va

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                reason="ffmpeg 없음")

COLORS = {"R": "red", "G": "lime", "B": "blue"}
DURS = [1.012, 1.012, 1.012]            # 올림이 쌓이는 길이(30.36프레임)
TTS = 4.2                               # 칸 음성 길이 → 칸 126프레임
ORDER = ["R", "G", "B", "R"]            # 컷마다 색이 바뀐다 → 경계 = 색이 바뀌는 프레임
SRC = [None, 0.6, None, None]           # 2번째 컷은 원본이 짧다 → 느리게(1.15배) + 정지 조각도 같은 자로 잰다


def _expected():
    durs = DURS + [TTS - sum(DURS)]
    cum, out = 0.0, []
    for d in durs:
        out.append(int(round(cum * 30)))
        cum += d
    return out, int(round(TTS * 30))


def _make_inputs(tmp_path):
    srcs = {}
    for k, col in COLORS.items():
        p = tmp_path / f"src_{k}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color={col}:s=180x320:r=30:d=6",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                       check=True, stdin=subprocess.DEVNULL)
        srcs[k] = str(p)
    tts = tmp_path / "tts.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", f"{TTS}", str(tts)], check=True, stdin=subprocess.DEVNULL)
    return srcs, str(tts)


def _frame_colors(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-an", "-vsync", "0", "-vf", "scale=4:4",
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                       capture_output=True, check=True, stdin=subprocess.DEVNULL)
    a = np.frombuffer(r.stdout, np.uint8).reshape(-1, 4, 4, 3).astype(float).mean(axis=(1, 2))
    return ["RGB"[int(np.argmax(px))] for px in a]


def _boundaries(colors):
    """색이 바뀌는 프레임 번호(첫 프레임 0 포함)."""
    return [0] + [i for i in range(1, len(colors)) if colors[i] != colors[i - 1]]


def _cuts():
    durs = DURS + [round(TTS - sum(DURS), 3)]
    return [{"video_id": k, "start": 0.5, "dur": d, "src_dur": (sd if sd is not None else d)}
            for k, d, sd in zip(ORDER, durs, SRC)]


def _render_final(tmp_path, monkeypatch, srcs, tts, trans=0.0):
    cuts = _cuts()
    plan = [{"video_id": c["video_id"], "seg_id": c["video_id"] + "-0", "start": c["start"],
             "src_dur": c["src_dur"], "out_dur": c["dur"]} for c in cuts]
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda *a, **k: [dict(x) for x in plan])
    monkeypatch.setattr(va, "_trans_sec", lambda: trans)
    beat = {"beat_idx": 0, "narration": "테스트",
            "primary": {"video_id": "R", "seg_id": "R-0", "start": 0.0, "end": 6.0},
            "alternates": [{"video_id": "G", "seg_id": "G-0", "start": 0.0, "end": 6.0},
                           {"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 6.0}]}
    work = tmp_path / "final"
    work.mkdir()
    return va._render_mix({"beats": [beat]}, {0: tts}, srcs, work)


def _render_editor(tmp_path, monkeypatch, srcs, tts):
    from shopping_shorts import app

    class _NoStore:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, *_a, **_k):
            return None

    pv = tmp_path / "pv"
    monkeypatch.setattr(app, "Store", _NoStore)
    monkeypatch.setattr(app, "_pvproxy_dir", lambda _j: pv)
    app._pvproxy_build("testjob", "sigtest", _cuts(), srcs, [4], {0: tts})
    out = pv / "sigtest.mp4"
    assert out.exists(), "편집 화면 합본 굽기 실패"
    import json
    meta = json.loads((pv / "sigtest.json").read_text(encoding="utf-8"))
    return out, meta


def test_cut_frame_list_matches_cumulative_rounding():
    exp, total = _expected()
    got = va.cut_frame_list(DURS + [TTS - sum(DURS)], total)
    starts = [sum(got[:i]) for i in range(len(got))]
    assert starts == exp
    assert sum(got) == total


def test_final_and_editor_cut_boundaries_same_frame(tmp_path, monkeypatch):
    srcs, tts = _make_inputs(tmp_path)
    exp, total = _expected()

    final = _render_final(tmp_path, monkeypatch, srcs, tts)
    fcol = _frame_colors(final)
    editor, meta = _render_editor(tmp_path, monkeypatch, srcs, tts)
    ecol = _frame_colors(editor)

    assert len(fcol) == total, f"완성본 칸 프레임 수 {len(fcol)} != {total}"
    assert len(ecol) == total, f"편집 화면 칸 프레임 수 {len(ecol)} != {total}"
    fb, eb = _boundaries(fcol), _boundaries(ecol)
    assert eb == exp, f"편집 화면 컷 경계 {eb} != 화면 누적 시각 {exp}"
    assert fb == exp, f"완성본 컷 경계 {fb} != 화면 누적 시각 {exp}"
    assert fb == eb
    # 화면이 되감기에 쓰는 컷 위치 기록도 구운 프레임과 같아야 한다
    assert [int(round(x * 30)) for x in meta["cuts"][0]] == exp


def test_final_with_transition_keeps_beat_frames(tmp_path, monkeypatch):
    """전환(xfade)을 켜도 칸 프레임 수는 그대로, 다음 컷은 화면 컷 경계에서 들어오기 시작한다."""
    srcs, tts = _make_inputs(tmp_path)
    exp, total = _expected()
    final = _render_final(tmp_path, monkeypatch, srcs, tts, trans=0.2)
    fcol = _frame_colors(final)
    assert len(fcol) == total, f"전환 켠 완성본 칸 프레임 수 {len(fcol)} != {total}"
    fb = _boundaries(fcol)
    # 섞이는 동안 우세 색이 바뀌는 자리는 겹침(6프레임)의 가운데 근처 — 경계 + 0~6프레임 안
    assert len(fb) == len(exp)
    for got, want in zip(fb[1:], exp[1:]):
        assert want <= got <= want + 6, (fb, exp)


def test_last_cut_absorbs_beat_remainder(tmp_path, monkeypatch):
    """컷 길이 합이 칸 음성보다 짧아도(0.56초 모자람) 마지막 컷이 나머지를 흡수해 칸 프레임 수가 맞는다 — 두 경로 모두."""
    import shopping_shorts.tests.test_cut_frame_boundaries as T
    monkeypatch.setattr(T, "_cuts", lambda: [
        {"video_id": k, "start": 0.5, "dur": d, "src_dur": d}
        for k, d in zip(ORDER, DURS + [0.6])])
    srcs, tts = _make_inputs(tmp_path)
    exp, total = _expected()
    fcol = _frame_colors(_render_final(tmp_path, monkeypatch, srcs, tts))
    ecol = _frame_colors(_render_editor(tmp_path, monkeypatch, srcs, tts)[0])
    assert len(fcol) == total and len(ecol) == total, (len(fcol), len(ecol), total)
    assert _boundaries(fcol) == exp == _boundaries(ecol)
