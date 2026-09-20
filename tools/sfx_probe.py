# -*- coding: utf-8 -*-
"""효과음 온셋 검출기 — 영상에서 효과음이 '언제' 울리는지 잰다.

배경(2026-08-29 실측, channel/strategy/효과음_패턴분석.md):
  효과음은 대본의 역할이 아니라 화면의 **컷**에 붙는다(컷 55개중 52개=95%).
  이 스크립트는 그 측정을 재현·확장하기 위한 것이다.

★반드시 --selftest 를 먼저 통과시키고 써라.
  이 검출기는 08-29에 두 번 0건을 냈다(백분위 임계 / 대역 오선택). 0건을
  그대로 믿으면 "효과음이 없다"고 틀린 결론을 낸다. selftest는 합성 정답
  파일(정해진 시각에 소리를 심은 것)을 만들어 검출기가 그 시각을 찾는지 본다.

사용법:
  py tools/sfx_probe.py --selftest
  py tools/sfx_probe.py --video a.mp4 [--json out.json]
"""
import argparse, json, os, subprocess, sys, tempfile

# 윈도우 콘솔이 cp949라 em-dash 하나에 스크립트가 죽는다(실측). 출력만 UTF-8로 고정.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np

SR = 48000
WIN = int(0.040 * SR)      # 40ms 창
HOP = int(0.010 * SR)      # 10ms hop
HI = (8000, 16000)         # 반짝 / whoosh
LO = (20, 120)             # 붐 / 임팩트


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def load_audio(path):
    """모노 48kHz float32로 디코드."""
    p = _run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1",
              "-ar", str(SR), "-f", "f32le", "-"])
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 디코드 실패: " + p.stderr.decode("utf-8", "replace")[:300])
    return np.frombuffer(p.stdout, dtype=np.float32)


def band_energy(x):
    """두 대역의 프레임별 에너지 시계열 (hop=10ms)."""
    n = 1 + max(0, (len(x) - WIN) // HOP)
    if n <= 0:
        return np.zeros(0), np.zeros(0)
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    frames = x[idx] * np.hanning(WIN)[None, :]
    spec = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(WIN, 1.0 / SR)
    hi = spec[:, (freqs >= HI[0]) & (freqs < HI[1])].sum(axis=1)
    lo = spec[:, (freqs >= LO[0]) & (freqs < LO[1])].sum(axis=1)
    return hi, lo


def onsets(e, local_ratio=4.5, prev_ratio=2.5, local_sec=1.0, min_gap_sec=0.12):
    """온셋 = 로컬 배경(±local_sec 중앙값) 대비 급증 + 직전 60ms 대비 급증.

    ★백분위 임계를 쓰지 마라 — 효과음은 소수라 95분위가 효과음 '위'에 잡혀 0건이 된다.
    ★배경음악이 깔리면 절대 기준선이 통째로 올라간다 → 반드시 로컬 배경 대비로 잰다.
    """
    if len(e) < 20:
        return []
    half = int(local_sec / 0.010)
    prev_n = 6                       # 60ms
    min_gap = int(min_gap_sec / 0.010)
    out, last = [], -10**9
    for i in range(prev_n, len(e)):
        lo_i, hi_i = max(0, i - half), min(len(e), i + half)
        bg = float(np.median(e[lo_i:hi_i])) + 1e-9
        prev = float(np.mean(e[i - prev_n:i])) + 1e-9
        if e[i] > bg * local_ratio and e[i] > prev * prev_ratio:
            if i - last >= min_gap:
                out.append(i)
                last = i
    return out


def detect(path):
    x = load_audio(path)
    hi, lo = band_energy(x)
    ev = [{"t": round(i * 0.010, 3), "kind": "sparkle"} for i in onsets(hi)]
    ev += [{"t": round(i * 0.010, 3), "kind": "boom"} for i in onsets(lo)]
    ev.sort(key=lambda d: d["t"])
    # 같은 순간에 두 대역이 동시에 걸리면 하나로 본다
    merged = []
    for e in ev:
        if merged and e["t"] - merged[-1]["t"] < 0.06:
            merged[-1]["kind"] += "+" + e["kind"]
        else:
            merged.append(e)
    return merged, len(x) / SR


def cuts(path, thresh=0.30):
    """컷 경계 시각 — ffmpeg scene detect."""
    p = _run(["ffmpeg", "-v", "info", "-i", path, "-vf",
              f"select='gt(scene,{thresh})',showinfo", "-f", "null", "-"])
    out = []
    for line in p.stderr.decode("utf-8", "replace").splitlines():
        if "pts_time:" in line:
            try:
                out.append(round(float(line.split("pts_time:")[1].split()[0]), 3))
            except Exception:
                pass
    return sorted(out)


def selftest():
    """합성 정답파일로 검출기를 검증한다. 이걸 통과 못 하면 실제 영상에 쓰지 마라."""
    d = tempfile.mkdtemp(prefix="sfxtest_")
    voice = os.path.join(d, "voice.wav")
    mixed = os.path.join(d, "mixed.wav")
    truth = {"sparkle": [1.50, 6.30], "boom": [4.00]}

    # 목소리 대역 노이즈 = 배경
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          "anoisesrc=d=10:c=pink:a=0.06", "-af", "highpass=f=300,lowpass=f=3000",
          "-ar", str(SR), "-ac", "1", voice])
    # 소리 3개를 정해진 시각에 심는다
    filt = ("[1:a]highpass=f=8000,volume=0.5,adelay=1500|1500[s1];"
            "[2:a]volume=0.9,adelay=4000|4000[b1];"
            "[3:a]highpass=f=8000,volume=0.5,adelay=6300|6300[s2];"
            "[0:a][s1][b1][s2]amix=inputs=4:duration=first:normalize=0[out]")
    _run(["ffmpeg", "-v", "error", "-y", "-i", voice,
          "-f", "lavfi", "-i", "anoisesrc=d=0.15:c=white:a=0.5",
          "-f", "lavfi", "-i", "sine=f=60:d=0.25",
          "-f", "lavfi", "-i", "anoisesrc=d=0.15:c=white:a=0.5",
          "-filter_complex", filt, "-map", "[out]",
          "-ar", str(SR), "-ac", "1", mixed])

    ev, _ = detect(mixed)
    exp = sorted(truth["sparkle"] + truth["boom"])
    hits, misses = [], []
    for t in exp:
        near = [e for e in ev if abs(e["t"] - t) <= 0.05]
        (hits if near else misses).append((t, near[0]["t"] if near else None))
    ev_voice, _ = detect(voice)          # 음성만 → 오탐 0이어야 한다
    print(f"[selftest] 정답 {len(exp)}개 중 검출 {len(hits)}개")
    for t, got in hits:
        print(f"   OK  정답 {t:.2f}s → 검출 {got:.2f}s (Δ{abs(got-t)*1000:.0f}ms)")
    for t, _ in misses:
        print(f"   MISS 정답 {t:.2f}s → 검출 없음")
    print(f"[selftest] 음성만인 파일 오탐: {len(ev_voice)}건 (0이어야 정상)")
    ok = not misses and len(ev_voice) == 0
    print("[selftest]", "통과 - 실제 영상에 써도 된다" if ok else "★실패 - 이 검출기로 잰 0건은 믿지 마라")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--video")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.video:
        ap.error("--video 또는 --selftest")
    ev, dur = detect(a.video)
    cu = cuts(a.video)
    # 각 컷에 가장 가까운 효과음 (Δ = 효과음 - 컷)
    pairs = []
    for c in cu:
        if not ev:
            break
        best = min(ev, key=lambda e: abs(e["t"] - c))
        if abs(best["t"] - c) <= 0.25:
            pairs.append({"cut": c, "sfx": best["t"],
                          "delta_ms": round((best["t"] - c) * 1000, 1), "kind": best["kind"]})
    res = {"video": os.path.basename(a.video), "dur": round(dur, 2),
           "n_sfx": len(ev), "n_cuts": len(cu), "n_paired": len(pairs),
           "sfx_per_min": round(len(ev) / (dur / 60), 1) if dur else 0,
           "events": ev, "cuts": cu, "pairs": pairs}
    if pairs:
        d = sorted(p["delta_ms"] for p in pairs)
        res["delta_median_ms"] = d[len(d) // 2]
        res["delta_mean_ms"] = round(sum(d) / len(d), 1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:2000])
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
