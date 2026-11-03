# -*- coding: utf-8 -*-
"""원음↔나레 경계 소리 점검(50ms RMS) — 벤치와 우리 완성본을 같은 자로. 사장님 10-17 '17초 끊김' 지적 뒤 만든 점검.
    PYTHONUTF8=1 py check_bounds.py <mp4> <경계초,…> [--label 이름]
경계마다 앞 0.5초·뒤 0.5초 50ms RMS(dB) 중앙 + 경계 ±0.1초 안 최대 점프(인접 50ms 차)."""
import subprocess
import sys

import numpy as np


def rms_track(mp4, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = sr // 20
    k = len(x) // n
    r = np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(r)


def main():
    mp4, bs = sys.argv[1], [float(b) for b in sys.argv[2].split(",")]
    db = rms_track(mp4)
    print(f"{'경계':>6} | 앞0.5s 중앙 | 뒤0.5s 중앙 | 차 | 경계±0.15s 최대 인접 점프 | 앞 0.3s→뒤 0.3s 50ms 값")
    for b in bs:
        i = int(round(b * 20))
        pre, post = db[max(0, i - 10):i], db[i:i + 10]
        win = db[max(0, i - 3):i + 4]
        jump = float(np.max(np.abs(np.diff(win)))) if len(win) > 1 else 0.0
        seq = " ".join(f"{v:.0f}" for v in db[max(0, i - 6):i + 6])
        print(f"{b:6.2f} | {np.median(pre):8.1f} | {np.median(post):8.1f} | {np.median(post) - np.median(pre):+5.1f} | {jump:5.1f} | {seq}")


if __name__ == "__main__":
    main()
