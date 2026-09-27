# -*- coding: utf-8 -*-
"""final_audio_audit 합성 소리 시험 — 렌더처럼 섞은 가짜 완성본으로 도구가 **실제로 잡는지** 본다.

  나레이션 칸 2개(사인 스윕 — 주기가 없어 상관 봉우리가 하나) → mp3 로 굽는다(렌더 입력과 같은 형식)
  완성본 = 나레이션×0.5 + BGM×0.15×0.5(amix normalize 기본 2입력) + 효과음×0.6(normalize=0) → AAC(m4a)
  ① 어긋남 없음 → 오차·누락·이상 0
  ② 둘째 칸을 0.3초 늦게 붙임 → 둘째 칸 오차 +0.3 이 잡힌다
  ③ 효과음을 빼고 섞음 → 누락 1
  ④ BGM 기대인데 빼고 섞음 → BGM 이상
  ⑤ 인트로 1.2초(무음) 앞에 붙임 → 인트로를 알면 오차 0
사보타주: ncc_search 가 예상 시각을 그대로(오프셋 0·NCC 1) 돌려주게 바꾸면 ②·③·④가 빨강이어야 한다.
돌리기: py -m pytest tools/test_final_audio_audit.py -q
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import final_audio_audit as fa      # noqa: E402

R = 44100


def _sweep(f0, f1, dur, am=4.0):
    t = np.arange(int(dur * R)) / R
    ph = 2 * np.pi * (f0 * t + (f1 - f0) * t * t / (2 * dur))
    env = 0.6 + 0.4 * np.sin(2 * np.pi * am * t)
    fade = np.minimum(1.0, np.minimum(t, dur - t) / 0.01)
    return 0.8 * np.sin(ph) * env * fade


def _wav(p, x):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(R)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def _enc(src, dst, extra=()):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *extra, str(dst)], check=True, stdin=subprocess.DEVNULL)


@pytest.fixture(scope="module")
def mats(tmp_path_factory):
    d = tmp_path_factory.mktemp("aa")
    b1, b2 = _sweep(300, 900, 1.5), _sweep(1200, 500, 1.8, am=3.0)
    rng = np.random.default_rng(7)
    bgm = np.convolve(rng.standard_normal(int(2.0 * R)), np.ones(30) / 30, "same")   # 2초 — 렌더처럼 반복(aloop)돼야 채운다
    bgm = 0.7 * bgm / np.max(np.abs(bgm))
    sfx = _sweep(2500, 5000, 0.3, am=0.0) * np.exp(-np.arange(int(0.3 * R)) / R / 0.08)
    out = {}
    for name, x in (("b1", b1), ("b2", b2), ("bgm", bgm), ("sfx", sfx)):
        _wav(d / (name + ".wav"), x)
        _enc(d / (name + ".wav"), d / (name + ".mp3"), ("-b:a", "128k"))
        out[name] = d / (name + ".mp3")
    out["arr"] = {"b1": b1, "b2": b2, "bgm": bgm, "sfx": sfx}
    out["dir"] = d
    return out


def _final(mats, name, shift2=0.0, sfx_on=True, bgm_on=True, intro=0.0):
    a = mats["arr"]
    n1, n2 = len(a["b1"]), len(a["b2"])
    gap = int(round(shift2 * R))
    total = int(round(intro * R)) + n1 + n2 + gap
    narr = np.zeros(total)
    i0 = int(round(intro * R))
    narr[i0:i0 + n1] += a["b1"]
    s2 = i0 + n1 + gap
    narr[s2:min(total, s2 + n2)] += a["b2"][:max(0, total - s2)]
    mix = 0.5 * narr
    if bgm_on:
        body = total - i0
        bg = np.tile(a["bgm"], body // len(a["bgm"]) + 1)[:body]
        mix[i0:] += 0.5 * 0.15 * bg
    if sfx_on:            # 효과음: 둘째 칸 시작(=first)에
        t = i0 + n1
        mix[t:t + len(a["sfx"])] += 0.6 * a["sfx"][:max(0, total - t)]
    wv = mats["dir"] / (name + ".wav")
    _wav(wv, mix)
    m4a = mats["dir"] / (name + ".m4a")
    _enc(wv, m4a, ("-c:a", "aac", "-b:a", "128k"))
    return m4a


def _ctx(mats, final, intro=0.0, bgm=True):
    d1, d2 = 1.5, 1.8
    return {"final": str(final), "intro": intro,
            "beats": [{"idx": 0, "tts": str(mats["b1"]), "head_trim": 0.0, "dur": d1, "t0": 0.0},
                      {"idx": 1, "tts": str(mats["b2"]), "head_trim": 0.0, "dur": d2, "t0": d1}],
            "sfx": [{"path": str(mats["sfx"]), "t": d1, "vol": 0.6, "beat": 1}],
            "bgm": {"path": str(mats["bgm"]), "vol": 0.15} if bgm else None}


def test_aligned_clean(mats):
    r = fa.audit(_ctx(mats, _final(mats, "ok")))
    j = fa.judge(r)
    assert [x["err"] for x in r["rows"]] and all(x["err"] is not None and abs(x["err"]) < 0.01 for x in r["rows"]), r["rows"]
    assert not j["narr_bad"] and not j["narr_lost"] and not j["sfx_miss"] and not j["sfx_off"], j
    assert j["bgm_bad"] == 0 and abs(r["bgm"]["rel_db"] - r["bgm"]["exp_db"]) < 1.5, r["bgm"]
    assert j["len_bad"] == 0, r["len"]


def test_shifted_beat_caught(mats):
    r = fa.audit(_ctx(mats, _final(mats, "shift", shift2=0.3)))
    j = fa.judge(r)
    assert [x["beat"] for x in j["narr_bad"]] == [1], r["rows"]
    assert abs(j["narr_bad"][0]["err"] - 0.3) < 0.01, j["narr_bad"]
    assert j["len_bad"] == 1        # 늦게 붙인 만큼 길다


def test_missing_sfx_caught(mats):
    r = fa.audit(_ctx(mats, _final(mats, "nosfx", sfx_on=False)))
    j = fa.judge(r)
    assert len(j["sfx_miss"]) == 1, r["sfx"]
    assert not j["narr_bad"]


def test_missing_bgm_caught(mats):
    r = fa.audit(_ctx(mats, _final(mats, "nobgm", bgm_on=False)))
    assert fa.judge(r)["bgm_bad"] == 1, r["bgm"]


def test_intro_offset(mats):
    r = fa.audit(_ctx(mats, _final(mats, "intro", intro=1.2), intro=1.2))
    j = fa.judge(r)
    assert not j["narr_bad"] and not j["narr_lost"] and not j["sfx_miss"] and j["bgm_bad"] == 0, (r["rows"], r["sfx"], r["bgm"])
    # 인트로를 모르면(0으로 알면) 칸 전부가 창 밖 오차로 잡혀야 한다
    r0 = fa.audit(_ctx(mats, _final(mats, "intro", intro=1.2), intro=0.0))
    assert all(x["err"] is not None and abs(x["err"] - 1.2) < 0.01 for x in r0["rows"]), r0["rows"]


def test_render_concat_drift_caught(mats, tmp_path):
    """렌더 _render_mix 의 칸 소리 붙이기(video_assemble.py: 칸마다 `-af apad -t 칸길이 -c:a aac` 클립 → concat -c copy)를
    그대로 따라 하면 뒤 칸일수록 나레이션이 밀린다(서버 10편 중 5편 실측 +0.21~0.37초). 나레이션 한 줄을 한 번에
    인코딩하면 안 밀린다. 도구가 앞은 잡고 뒤는 통과시켜야 한다."""
    durs = [2.37, 3.11, 1.93, 2.71, 3.05, 2.2]
    beats, clips, lens, cum, t0 = [], [], [], 0.0, 0.0
    for i, d in enumerate(durs):
        x = _sweep(300 + 97 * i, 1500 - 60 * i, d)
        _wav(tmp_path / ("b%d.wav" % i), x)
        _enc(tmp_path / ("b%d.wav" % i), tmp_path / ("b%d.mp3" % i), ("-b:a", "128k"))
        dd = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                            str(tmp_path / ("b%d.mp3" % i))]))
        f0 = int(round(cum * 30)); cum += dd; nfr = max(1, int(round(cum * 30)) - f0); bl = nfr / 30.0; lens.append(bl)
        v = tmp_path / ("v%d.mp4" % i); c = tmp_path / ("c%d.mp4" % i)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x%02x%02x%02x:s=64x112:r=30:d=%.3f" % ((i * 97) % 256, (40 + i * 53) % 256, (200 - i * 31) % 256, bl + 0.2),
                        "-frames:v", str(nfr), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(v), "-ss", "0.000", "-i", str(tmp_path / ("b%d.mp3" % i)),
                        "-map", "0:v:0", "-map", "1:a:0", "-frames:v", str(nfr), "-af", "apad", "-t", "%.4f" % bl,
                        "-c:v", "copy", "-c:a", "aac", str(c)], check=True, stdin=subprocess.DEVNULL)
        clips.append(c)
        beats.append({"idx": i, "tts": str(tmp_path / ("b%d.mp3" % i)), "head_trim": 0.0, "dur": dd, "t0": t0}); t0 += dd
    lst = tmp_path / "cc.txt"
    lst.write_text("".join("file '%s'\n" % c.as_posix() for c in clips), encoding="utf-8")
    raw = tmp_path / "mix_raw.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)],
                   check=True, stdin=subprocess.DEVNULL)
    r = fa.audit({"final": str(raw), "intro": 0.0, "beats": beats, "sfx": [], "bgm": None})
    # 칸마다 색이 달라 영상 컷이 잡혀야 한다 → 기준이 '영상 칸 첫 그림'
    assert all(x["vid"] is not None for x in r["rows"][1:]), r["rows"]
    worst = max(abs(x["err_v"] or 0) for x in r["rows"])
    assert worst >= 0.08, r["rows"]
    # 표본이 남아돈다: 디코드 길이 - 칸 길이 합(프레임 경계) 이 마지막 칸 밀림과 같은 크기
    surplus = r["len"]["got"] - sum(lens)
    print("[concat] 디코드 %.3fs · 칸길이합 %.3fs · 남는 표본 %+.3fs · 마지막칸 음성-영상 %+.3f · 칸별 %s" % (
        r["len"]["got"], sum(lens), surplus, r["rows"][-1]["err_v"], [x["err_v"] for x in r["rows"]]))
    assert abs(surplus - r["rows"][-1]["err_v"]) < 0.05
    # 관문 조건: 패킷 잉여(ffprobe 만으로) — 칸별 AAC concat 은 기준(0.05초)을 넘고 판정도 '이상'
    assert r["surplus"] is not None and r["surplus"] >= fa.SURPLUS_T, r["surplus"]
    assert fa.judge(r)["surplus_bad"] == 1
    # 수정안: 나레이션 한 줄(칸마다 apad+atrim 표본 정확히) → 한 번만 AAC
    ins, fc = [], []
    for i, L in enumerate(lens):
        ins += ["-i", beats[i]["tts"]]
        fc.append("[%d:a]aresample=48000,apad,atrim=end_sample=%d,asetpts=N/SR/TB[a%d]" % (i, int(round(L * 48000)), i))
    fc.append("".join("[a%d]" % i for i in range(len(lens))) + "concat=n=%d:v=0:a=1[a]" % len(lens))
    narr = tmp_path / "narr.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[a]", str(narr)],
                   check=True, stdin=subprocess.DEVNULL)
    fixed = tmp_path / "fixed.m4a"
    _enc(narr, fixed, ("-c:a", "aac"))
    r2 = fa.audit({"final": str(fixed), "intro": 0.0, "beats": beats, "sfx": [], "bgm": None})
    worst2 = max(abs(x["err"] or 0) for x in r2["rows"])
    assert worst2 < 0.03, r2["rows"]
    assert r2["surplus"] is not None and r2["surplus"] < fa.SURPLUS_T, r2["surplus"]
    assert fa.judge(r2)["surplus_bad"] == 0


# ── 일정 지연(2026-09-27) — 칸마다 같은 크기로 밀리는 결함은 '가장 큰 칸'(0.15)·패킷 잉여(0.05)로 안 잡힌다 ──

def test_constant_delay_after_intro_caught(mats):
    """종전 인트로 경로처럼 인트로 뒤 목소리 전체가 +0.06초 늦으면 일정 지연 1편(중앙값·인트로 뒤 첫 칸 둘 다)."""
    late = _final(mats, "late", intro=1.26)                   # 실제 목소리는 1.26초부터
    r = fa.audit(_ctx(mats, late, intro=1.2))                 # 편성은 인트로 1.2초
    j = fa.judge(r)
    assert j["delay_bad"] == 1, (j["delay_med"], j["delay_first"])
    assert abs(j["delay_med"] - 0.06) < 0.01 and abs(j["delay_first"] - 0.06) < 0.01, (j["delay_med"], j["delay_first"])
    assert not j["narr_bad"], "0.15 기준으로는 안 잡힌다 — 그래서 일정 지연 항목이 필요하다"


def test_constant_delay_zero_when_aligned(mats):
    r = fa.audit(_ctx(mats, _final(mats, "intro_ok", intro=1.2), intro=1.2))
    j = fa.judge(r)
    assert j["delay_bad"] == 0 and abs(j["delay_med"]) < 0.01 and abs(j["delay_first"]) < 0.01, (j["delay_med"], j["delay_first"])


def test_parse_summary_reads_gate_items_and_rejects_old_format():
    line = ("== 칸 82 · 나레이션 0.15초+ 오차 3 · 효과음 누락 1 · BGM 이상 0 · 음성-자막 0.15초+ 2 · 나레이션 못찾음 0"
            " · 효과음 타점0.10+ 0 · 길이 이상 0 · 렌더뒤음성바뀜 0 · 건너뜀 1 · 패킷 잉여 0.05초+ 2편 · 일정 지연 4편 · 검출불일치 0칸   (…)")
    assert fa.parse_summary("x\n" + line + "\n") == {"cells": 82, "narr": 3, "sfx_miss": 1, "bgm": 0, "lost": 0,
                                                      "skip": 1, "surplus": 2, "delay": 4, "vcut_mis": 0}
    old = line.split(" · 일정 지연")[0]                        # 일정 지연 항목이 없는 옛 판본 → 판정 불가
    assert fa.parse_summary(old) is None
    assert fa.parse_summary("요약 없음") is None



# ── 판정 기준 = 계획 프레임(2026-09-27 finish 12차 오탐: 6c1a 칸2 검출 컷 +0.200, 계획 프레임 0.000) ──

def _video_with_cut(mats, name, cut_at, voice_shift=0.0):
    """칸 2개(1.5초·1.8초) 영상+소리. 그림은 cut_at 초에서 한 번 바뀐다(빨강→파랑). 둘째 칸 목소리는 voice_shift 초 늦다.
    소리는 BGM·효과음 없이 나레이션만(렌더처럼 AAC 한 번)."""
    a = mats["arr"]
    n1, n2 = len(a["b1"]), len(a["b2"])
    gap = int(round(voice_shift * R))
    total = n1 + n2 + gap
    narr = np.zeros(total)
    narr[:n1] += a["b1"]
    narr[n1 + gap:n1 + gap + n2] += a["b2"]
    wv = mats["dir"] / (name + ".wav")
    _wav(wv, 0.5 * narr)
    dur = total / R
    out = mats["dir"] / (name + ".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=red:s=64x112:r=30:d=%.4f" % cut_at,
                    "-f", "lavfi", "-i", "color=c=blue:s=64x112:r=30:d=%.4f" % (dur - cut_at),
                    "-i", str(wv), "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                    "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
                   check=True, stdin=subprocess.DEVNULL)
    return out


def _ctx2(mats, final):
    return {"final": str(final), "intro": 0.0,
            "beats": [{"idx": 0, "tts": str(mats["b1"]), "head_trim": 0.0, "dur": 1.5, "t0": 0.0},
                      {"idx": 1, "tts": str(mats["b2"]), "head_trim": 0.0, "dur": 1.8, "t0": 1.5}],
            "sfx": [], "bgm": None}


def test_scene_change_inside_beat_is_not_a_narration_error(mats):
    """칸 경계엔 그림이 안 바뀌고 칸 안 +0.2초에서 바뀌면 검출 컷은 +0.2로 잡힌다 — 그건 목소리 결함이 아니다(판정 0, 검출불일치 1)."""
    r = fa.audit(_ctx2(mats, _video_with_cut(mats, "incut", 1.5 + 0.2)))
    j = fa.judge(r)
    row = r["rows"][1]
    assert abs(row["err_vcut"] + 0.2) < 0.04, row          # 검출 기준이면 −0.2(목소리가 '앞선' 것처럼 보인다)
    assert abs(row["err_v"]) < 0.02, row                   # 계획 프레임 기준 0
    assert not j["narr_bad"], [(x["beat"], x["err_v"]) for x in j["narr_bad"]]
    assert [x["beat"] for x in j["vcut_mis"]] == [1], [(x["beat"], x.get("vcut_off")) for x in r["rows"]]


def test_voice_really_late_is_caught_against_plan_frame(mats):
    """그림은 칸 경계에서 바뀌고 목소리가 실제로 +0.2초 늦으면 판정 1(계획 프레임 기준), 검출불일치 0."""
    r = fa.audit(_ctx2(mats, _video_with_cut(mats, "late2", 1.5, voice_shift=0.2)))
    j = fa.judge(r)
    assert [x["beat"] for x in j["narr_bad"]] == [1], [(x["beat"], x["err_v"]) for x in r["rows"]]
    assert abs(j["narr_bad"][0]["err_v"] - 0.2) < 0.02
    assert not j["vcut_mis"], [(x["beat"], x.get("vcut_off")) for x in r["rows"]]


def test_parse_summary_reads_vcut_mismatch():
    line = ("== 칸 8 · 나레이션 0.15초+ 오차 0 · 효과음 누락 0 · BGM 이상 0 · 음성-자막 0.15초+ 0 · 나레이션 못찾음 0"
            " · 효과음 타점0.10+ 0 · 길이 이상 0 · 렌더뒤음성바뀜 0 · 건너뜀 0 · 패킷 잉여 0.05초+ 0편 · 일정 지연 0편 · 검출불일치 2칸   (…)")
    assert fa.parse_summary(line)["vcut_mis"] == 2
    assert fa.parse_summary(line.split(" · 검출불일치")[0]) is None      # 새 항목이 없는 옛 판본 → 판정 불가
