# -*- coding: utf-8 -*-
"""AI 장면 클립의 **움직임이 언제 일어나는가**를 잰다 (2026-09-24).

왜 있나: 훅은 칸 길이만큼만 화면에 나온다(실측 2.42초). 그런데 Veo는 4초를 만든다.
"큰 동작을 앞에 두라"고 프롬프트를 고쳐도, 눈으로 보는 것만으로는 정말 앞으로 왔는지
말할 수 없다. 이 도구는 프레임 간 차이를 0.5초 구간별로 합쳐, 움직임이 몰린 자리를
숫자로 보여준다. 고칠 때마다 다시 돌린다(CLAUDE.md 0순위-A1b).

    py tools/ai_scene_motion_audit.py <클립.mp4> [--visible 2.42]

출력: 구간별 움직임 비중(%), 보이는 구간이 차지하는 비중, 최대 움직임 시각.
"""
import argparse
import subprocess
import sys

W, H, FPS = 64, 114, 10          # 작게 흑백으로 — 밝기 변화가 아니라 '얼마나 바뀌나'만 본다


def frames(path):
    """그레이스케일 저해상 프레임을 bytes 리스트로."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={FPS},scale={W}:{H},format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    n = W * H
    return [out[i:i + n] for i in range(0, len(out) - n + 1, n)]


def motion_series(path):
    """[(초, 직전 프레임과의 평균 밝기차)] — 값이 클수록 화면이 많이 바뀌었다."""
    fs = frames(path)
    series = []
    for i in range(1, len(fs)):
        a, b = fs[i - 1], fs[i]
        diff = sum(abs(a[j] - b[j]) for j in range(0, len(a), 7))   # 7픽셀마다 표본 — 충분하고 빠르다
        series.append((i / FPS, diff / (len(a) / 7)))
    return series


def report(path, visible=None):
    s = motion_series(path)
    if not s:
        print("프레임을 못 읽었습니다:", path)
        return 1
    total = sum(v for _, v in s) or 1e-9
    dur = s[-1][0]
    print(f"[{path}] 길이 {dur:.1f}초 · 표본 {len(s)}프레임")
    print("  구간      움직임 비중")
    bucket = {}
    for t, v in s:
        k = int(t * 2) / 2.0                      # 0.5초 구간
        bucket[k] = bucket.get(k, 0.0) + v
    for k in sorted(bucket):
        pct = bucket[k] / total * 100
        print("  %4.1f~%4.1f초  %5.1f%%  %s" % (k, k + 0.5, pct, "#" * int(pct / 2)))
    peak = max(s, key=lambda x: x[1])
    print("  가장 크게 움직인 때: %.1f초" % peak[0])
    if visible:
        seen = sum(v for t, v in s if t <= visible) / total * 100
        print("  ★보이는 %.2f초 안에 들어간 움직임: %.1f%%" % (visible, seen))
        print("   (화면에 나오는 길이 비중은 %.1f%% — 이보다 높아야 앞으로 쏠린 것)"
              % (min(visible, dur) / dur * 100))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", nargs="+")
    ap.add_argument("--visible", type=float, default=None, help="화면에 실제로 나오는 초(칸 길이)")
    a = ap.parse_args()
    rc = 0
    for c in a.clip:
        rc |= report(c, a.visible)
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
