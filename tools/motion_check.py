# -*- coding: utf-8 -*-
"""영상이 '자연스러운가'를 눈이 아니라 숫자로 본다(2026-08-15 신설).

★왜 만들었나. 롱폼→쇼츠 결과물을 정지 프레임으로만 확인하다 사장님께 "너무
  부자연스러운데 너는 그걸 측정 못하나"를 들었다. 맞는 지적이다 - 정지 프레임은
  "요소가 있다"만 증명하고 "움직임이 매끄러운가"는 전혀 증명하지 못한다.

무엇을 재는가: 영상 창 영역만 잘라 프레임마다 평균 밝기(YAVG)를 뽑고, **프레임 간
변화량**을 본다. 화면이 한 프레임에 확 튀면 사람 눈에는 '깜빡임·오류'로 읽힌다.

실측 기준선(2026-08-15, 38초 결과물 1140프레임):
    전체 평균 0.6 / 중앙값 0.0
    정상 이음매(컷 전환) 1~4
    깨진 것: 화이트 플래시 219.2  <-- 평균의 365배. 이게 '부자However natural' 아님의 정체였다

한계(정직하게): 이 도구는 **밝기 급변만** 본다. 동작의 리듬·이징이 어색한 것,
글자가 촌스러운 것은 못 잡는다. 그건 여전히 사람이 봐야 한다.

사용:
    py tools/motion_check.py <mp4> [--top 10] [--seams 1.2,8.2,10.0]
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys

# 세로 영상(1080x1920) 안의 '영상 창' 위치. 위아래 템플릿(글자·바)은 빼고 본다 -
# 자막이 바뀌는 것까지 급변으로 잡히면 신호가 묻힌다.
CROP = "crop=1080:608:0:656"


def frame_luma(path, crop=CROP):
    """[(시각초, 평균밝기)] - 작게 줄여서 재도 급변 판정에는 충분하다(속도 20배)."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", f"{crop},scale=192:108,signalstats,metadata=print:file=-",
         "-f", "null", "-"],
        capture_output=True, text=True).stdout
    rows, t = [], None
    for line in out.splitlines():
        m = re.match(r"frame:(\d+)\s+pts:\d+\s+pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(2))
            continue
        m2 = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", line)
        if m2 and t is not None:
            rows.append((t, float(m2.group(1))))
    return rows


def deltas(rows):
    return [(rows[i][0], abs(rows[i][1] - rows[i - 1][1])) for i in range(1, len(rows))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--seams", default="", help="확인할 이음매 시각들, 쉼표 구분(초)")
    a = ap.parse_args()

    rows = frame_luma(a.video)
    if len(rows) < 2:
        print("프레임을 못 읽었습니다", file=sys.stderr)
        return 1
    d = deltas(rows)
    vals = [v for _, v in d]
    print(f"프레임 {len(rows)}개 · 평균 {statistics.mean(vals):.1f} · "
          f"중앙값 {statistics.median(vals):.1f} · 최대 {max(vals):.1f}")

    print("\n밝기 급변 상위:")
    for t, v in sorted(d, key=lambda x: -x[1])[:a.top]:
        flag = "  <-- 튄다" if v > 60 else ""
        print(f"  {t:6.2f}초  {v:6.1f}{flag}")

    if a.seams:
        print("\n지정한 이음매:")
        dd = {round(t, 2): v for t, v in d}
        for s in a.seams.split(","):
            x = float(s)
            k = min(dd, key=lambda k: abs(k - x))
            print(f"  t={k:6.2f}초  변화량 {dd[k]:6.1f}")

    worst = max(vals)
    print("\n판정: " + ("OK - 튀는 프레임 없음" if worst <= 60 else
                       f"NG - 최대 {worst:.0f} (60 넘으면 깜빡임으로 보인다)"))
    return 0 if worst <= 60 else 2


if __name__ == "__main__":
    raise SystemExit(main())
