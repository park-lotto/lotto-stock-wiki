"""완성본 나레이션 한 줄(video_assemble.narration_track) — 칸 소리가 영상 칸과 **표본 단위로** 맞는지 실제 렌더로 잰다.

왜 (2026-09-27, 서버 실측): 종전 _render_mix 는 칸마다 소리를 AAC 로 따로 굽고 concat -c copy 로 이었다. AAC 가 칸마다
  채움 표본을 달고 나와 **소리 패킷 표본 수가 타임스탬프보다 칸당 20~40ms 많은** 파일이 나왔다(수리 뒤 렌더 4편 +0.14~0.21초
  — ffprobe nb_frames×1024/표본율 − 스트림 길이). 이어 재생하면 마지막 칸 목소리가 그림보다 +0.13~0.20초 늦고, 장면꾸미기
  합성의 -shortest 가 끝 말소리를 잘랐다(수리 전 5편 0.17~0.37초).

검사: 칸마다 색이 다른 소스 + 칸마다 다른 사인 스윕 나레이션 10칸을 실제 _render_mix 로 굽고
  (a) 패킷 잉여 < 0.03초 · 칸마다 목소리 시작 = 영상 칸 첫 프레임 ±0.02초  (c) 끝 말소리 안 잘림
  (d) 효과음 타점 = sfx_events_for 시각 ±0.02초(효과음 단계 _burn_captions 까지 통과)
  (e) 소리 길이 = 영상 길이(프레임 × 1600표본) — 함수 단위.
사보타주: _render_mix 를 종전(칸 클립마다 -c:a aac → concat)으로 되돌리면 (a)가 빨강(패킷 잉여 +0.2초대, 마지막 칸 +0.1초대).
"""
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from shopping_shorts import video_assemble as va

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg 없음")

R = 48000
DURS = [2.37, 3.11, 1.93, 2.71, 3.05, 2.2, 2.9, 3.3, 2.45, 2.8]
COLORS = ["red", "lime", "blue", "yellow", "magenta", "cyan", "white", "orange", "purple", "gray"]


def _sweep(f0, f1, d):
    t = np.arange(int(d * R)) / R
    x = 0.7 * np.sin(2 * np.pi * (f0 * t + (f1 - f0) * t * t / (2 * d))) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))
    fade = np.minimum(1.0, np.minimum(t, d - t) / 0.01)
    return x * fade


def _wav(p, x):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(R)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def _mp3(tmp, name, x):
    wv = tmp / (name + ".wav"); _wav(wv, x)
    mp = tmp / (name + ".mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wv), "-b:a", "128k", str(mp)], check=True, stdin=subprocess.DEVNULL)
    return str(mp)


def _decode(path, sr=16000, hp=None):
    af = ["-af", "highpass=f=%d,highpass=f=%d" % (hp, hp)] if hp else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", *af, "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True, check=True, stdin=subprocess.DEVNULL)
    return np.frombuffer(r.stdout, np.float32).astype(np.float64)


def _ncc_at(sig, tmpl, center, win):
    """tmpl 이 center(표본) 근처 ±win 에서 시작하는 자리 → (오프셋표본, ncc)."""
    L = len(tmpl); a = center - win
    seg = np.zeros(2 * win + L)
    s0, s1 = max(0, a), min(len(sig), a + len(seg))
    seg[s0 - a:s1 - a] = sig[s0:s1]
    n = 1 << int(math.ceil(math.log2(len(seg))))
    c = np.fft.irfft(np.fft.rfft(seg, n) * np.conj(np.fft.rfft(tmpl, n)), n)[:2 * win + 1]
    cs = np.concatenate([[0.0], np.cumsum(seg * seg)])
    e = cs[L:L + 2 * win + 1] - cs[:2 * win + 1]
    ncc = c / (np.sqrt(np.maximum(e, 0)) * np.linalg.norm(tmpl) + 1e-12)
    k = int(np.argmax(ncc))
    return k - win, float(ncc[k])


def _packet_surplus(path):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=sample_rate,duration,nb_frames", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL).stdout.strip().split(",")
    sr, dur, nf = int(o[0]), float(o[1]), int(o[2])
    return nf * 1024 / sr - dur


@pytest.fixture(scope="module")
def mats(tmp_path_factory):
    d = tmp_path_factory.mktemp("narr")
    srcs, tts, arr = {}, {}, {}
    for i, (du, col) in enumerate(zip(DURS, COLORS)):
        p = d / ("src%d.mp4" % i)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=%s:s=180x320:r=30:d=5" % col,
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)], check=True, stdin=subprocess.DEVNULL)
        srcs["V%d" % i] = str(p)
        x = _sweep(300 + 97 * i, 1500 - 60 * i, du)
        arr[i] = x
        tts[i] = _mp3(d, "b%d" % i, x)
    return {"dir": d, "srcs": srcs, "tts": tts, "arr": arr}


def _plan():
    beats = []
    for i in range(len(DURS)):
        beats.append({"beat_idx": i, "narration": "칸 %d" % i, "role": "body",
                      "primary": {"video_id": "V%d" % i, "seg_id": "V%d-0" % i, "start": 0.0, "end": 5.0},
                      "alternates": [], "effect": "cut", "fit": 0})
    return {"structure": "t", "beats": beats}


def _patch(monkeypatch, mod=va):
    def _one(beat, tts_dur, srcd, runout=0.0):
        vid = beat["primary"]["video_id"]
        return [{"video_id": vid, "seg_id": vid + "-0", "start": 0.2, "src_dur": tts_dur, "out_dur": tts_dur}]
    monkeypatch.setattr(mod, "plan_beat_clips_for", _one)
    monkeypatch.setattr(mod, "_trans_sec", lambda: 0.0)
    monkeypatch.setattr(mod, "_important_beat_indices", lambda beats: set())


def _render(mats, monkeypatch, work, mod=va):
    _patch(monkeypatch, mod)
    work.mkdir(parents=True, exist_ok=True)
    with va.preview_preset():
        return mod._render_mix(_plan(), dict(mats["tts"]), dict(mats["srcs"]), work)


def _frame_starts(mats):
    """렌더가 쓰는 칸 첫 프레임(누적 시각 반올림) — render_cut_plan 과 같은 자."""
    cum, out = 0.0, []
    for i in range(len(DURS)):
        du = va._beat_effective_dur({}, mats["tts"][i])
        out.append(int(round(cum * 30)))
        cum += du
    return out, int(round(cum * 30))


def _starts_err(mix, mats):
    sig = _decode(mix)
    f0s, _tot = _frame_starts(mats)
    errs = []
    for i, f0 in enumerate(f0s):
        t = _decode(mats["tts"][i])
        off, v = _ncc_at(sig, t, int(round(f0 / 30 * 16000)), int(0.5 * 16000))
        assert v > 0.5, (i, v)
        errs.append(off / 16000)
    return errs, sig


def test_render_mix_narration_sample_exact(mats, monkeypatch, tmp_path):
    mix = _render(mats, monkeypatch, tmp_path / "w")
    sur = _packet_surplus(mix)
    errs, sig = _starts_err(mix, mats)
    print("\n[수리 후] 패킷 잉여 %+.3fs · 칸별 목소리-영상칸 %s" % (sur, [round(e, 3) for e in errs]))
    assert sur < 0.03, sur                                     # (a) 표본 = 타임스탬프
    assert max(abs(e) for e in errs) <= 0.02, errs             # (a) 칸마다 목소리 = 영상 칸 첫 프레임
    # (e) 소리 길이 = 영상 길이
    _f, tot = _frame_starts(mats)
    assert abs(len(sig) / 16000 - tot / 30) < 0.03, (len(sig) / 16000, tot / 30)
    # (c) 끝 말소리 안 잘림 — 마지막 칸 뒤 0.3초가 제자리에 온전히 있다
    last = _decode(mats["tts"][len(DURS) - 1])
    tail = last[-int(0.3 * 16000):]
    f0s, _ = _frame_starts(mats)
    exp = int(round(f0s[-1] / 30 * 16000)) + len(last) - len(tail)
    off, v = _ncc_at(sig, tail, exp, int(0.05 * 16000))
    assert v > 0.8 and abs(off) <= int(0.02 * 16000), (off, v)


def test_narration_track_length_is_frames_times_1600(mats, tmp_path):
    frames = [(0, 71), (1, 93), (2, 58)]
    out = va.narration_track(_plan(), dict(mats["tts"]), frames, tmp_path / "n.wav")
    with wave.open(out) as w:
        assert w.getframerate() == 48000
        assert w.getnframes() == sum(n for _, n in frames) * 1600
    # head_trim 은 칸 시작에서 빠진다(종전 `-ss head_trim -i tts` 와 같은 자리)
    plan = _plan(); plan["beats"][0]["head_trim"] = 0.25
    out2 = va.narration_track(plan, dict(mats["tts"]), [(0, 71)], tmp_path / "n2.wav")
    a = _decode(out2); t = _decode(mats["tts"][0])
    off, v = _ncc_at(a, t[int(0.25 * 16000):], 0, int(0.1 * 16000))
    assert v > 0.8 and abs(off) <= 16, (off, v)


def test_sfx_timing_unchanged_after_burn(mats, monkeypatch, tmp_path):
    """(d) 효과음 단계(_burn_captions, amix)를 지나도 효과음은 sfx_events_for 시각에, 목소리는 영상 칸에 있다."""
    mix = _render(mats, monkeypatch, tmp_path / "w")
    sfx_x = _sweep(2500, 5000, 0.3) * np.exp(-np.arange(int(0.3 * R)) / R / 0.08)
    sfx = _mp3(tmp_path, "sfx", sfx_x)
    plan = _plan()
    for i in (2, 6, 9):
        plan["beats"][i]["sfx"] = {"asset_id": 1, "match_type": "role", "position": "first"}
    sp = {i: sfx for i in (2, 6, 9)}
    tl = va._beat_timeline(plan, dict(mats["tts"]))
    evs = va.sfx_events_for(tl, sp)
    out = tmp_path / "out.mp4"
    with va.preview_preset():
        va._burn_captions(mix, plan, dict(mats["tts"]), str(out), tmp_path / "w", deco={}, sfx_paths=sp, skip_text=True)
    # 효과음(2.5~5kHz)만 보이게 2kHz 위만 남긴다 — 나레이션(0.3~1.5kHz)이 섞여 상관이 묻히지 않게
    sig = _decode(out, hp=2000)
    st = _decode(sfx, hp=2000)
    for path, t, *_ in evs:
        off, v = _ncc_at(sig, st, int(round(t * 16000)), int(0.3 * 16000))
        assert v > 0.3 and abs(off / 16000) <= 0.02, (t, off / 16000, v)
    errs, _ = _starts_err(out, mats)
    assert max(abs(e) for e in errs) <= 0.02, errs
