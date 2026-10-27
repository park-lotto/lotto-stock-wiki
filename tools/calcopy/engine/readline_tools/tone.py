# -*- coding: utf-8 -*-
"""말 위에 얹힌 지속 순음(띵·딩동) 검출(tone).

어디서 왔나: 06 이븐쇼핑 워커(관제 263, 10-25) `channel/evenshopping/_kal/측정도구/tone.py` 를 옮김(알고리즘 바꾸지 않음).
            박혀 있던 경로(C:/숏템_칼카피/evenshopping/src·work)는 인자로, 문턱은 인자·프로필(`profiles/<slug>.json` 의 "tone")로 뺐다.
왜 따로 있나: engine/sound/sfx_events --detect 의 tonal 검출은 유성(말) 마스크 탓에 말과 겹친 띵을 0발로 냈다(이븐쇼핑 실측).
무엇을 재나: 22.05kHz 모노 STFT(2048, hop 256) → lo~hi Hz 각 칸 dB 에서 주파수 방향 15칸 중앙값을 뺀 돌출(±1칸 최대) ≥ prom_db 가
            min_dur 초 이상 이어지면 후보 → merge 초 안 후보는 한 사건(주파수 50Hz 단위 모음).
입력: mp4 (여러 개) · [--lo 2500 --hi 6000 --prom 14 --min-dur 0.12 --merge 0.35] 또는 --profile
출력(json): {id: [{t, dur, hz(최대 4개), prom_db}]}

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/tone.py <mp4 ...> [--out tone.json] [--profile profiles/evenshopping.json]
    (옛 꼴: --src-dir C:/숏템_칼카피/evenshopping/src <id ...> → <src-dir>/<id>.mp4)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

DEFAULTS = {"lo": 2500, "hi": 6000, "prom": 14.0, "min_dur": 0.12, "merge": 0.35}


def tone_events(mp4: str, lo: float = 2500, hi: float = 6000, prom: float = 14.0, min_dur: float = 0.12, merge: float = 0.35) -> list[dict]:
    from scipy.ndimage import maximum_filter1d, median_filter
    from scipy.signal import stft
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-ac", "1", "-ar", "22050", "-f", "s16le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768
    f, t, Z = stft(x, 22050, nperseg=2048, noverlap=2048 - 256)
    L = 10 * np.log10(np.abs(Z) ** 2 + 1e-12)
    m = (f >= lo) & (f <= hi)
    S = L[m]
    ff = f[m]
    P = S - median_filter(S, size=(15, 1), mode="nearest")
    P = maximum_filter1d(P, 3, axis=0)
    ok = P >= prom
    hits = []
    dt = t[1] - t[0]
    need = int(min_dur / dt)
    for b in range(ok.shape[0]):
        row = ok[b]
        i = 0
        while i < len(row):
            if row[i]:
                j = i
                while j + 1 < len(row) and row[j + 1]:
                    j += 1
                if j - i + 1 >= need:
                    hits.append((float(t[i]), float(t[j]), int(ff[b]), float(np.median(P[b, i:j + 1]))))
                i = j + 1
            else:
                i += 1
    hits.sort()
    ev = []
    for a, b, hz, p in hits:
        if ev and a - ev[-1]["t1"] < merge:
            e = ev[-1]
            e["t1"] = max(e["t1"], b)
            e["hz"].add(round(hz / 50) * 50)
            e["prom"] = max(e["prom"], p)
        else:
            ev.append({"t": a, "t1": b, "hz": {round(hz / 50) * 50}, "prom": p})
    return [{"t": round(e["t"], 2), "dur": round(e["t1"] - e["t"], 2), "hz": sorted(e["hz"])[:4], "prom_db": round(e["prom"], 1)} for e in ev]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="mp4 경로 또는 (--src-dir 와 함께) 영상 id")
    ap.add_argument("--src-dir")
    ap.add_argument("--out")
    ap.add_argument("--profile")
    for k, v in DEFAULTS.items():
        ap.add_argument("--" + k.replace("_", "-"), type=float)
    A = ap.parse_args(argv)
    P = dict(DEFAULTS)
    if A.profile:
        P.update(json.loads(Path(A.profile).read_text(encoding="utf-8")).get("tone") or {})
    for k in DEFAULTS:
        if getattr(A, k) is not None:
            P[k] = getattr(A, k)
    res = {}
    for x in A.inputs:
        mp4 = str(Path(A.src_dir) / f"{x}.mp4") if A.src_dir else x
        vid = Path(mp4).stem
        out = tone_events(mp4, P["lo"], P["hi"], P["prom"], P["min_dur"], P["merge"])
        res[vid] = out
        print(vid, len(out), [(o["t"], o["dur"], o["hz"][:2]) for o in out])
    if A.out:
        json.dump(res, open(A.out, "w"), indent=0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
