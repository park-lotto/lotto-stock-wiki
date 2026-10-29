# -*- coding: utf-8 -*-
"""줄 등장 시트(entersheet) — 줄 시작 시각마다 1프레임 간격 11장(0.34초) 자막 띠를 rangesheet 로 만들어 세로로 쌓는다(등장 애니메이션 눈 판독용).

어디서 왔나: 06 워커들의 세션 임시 폴더 entersheet.sh(반복 사용)를 파이썬으로 옮김(rangesheet 를 그대로 부름, ffmpeg vstack 대신 numpy).

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/entersheet.py <mp4> <out.jpg> <y0> <y1> <t1> [t2 ...]
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def entersheet(mp4: str, out: str, y0: int, y1: int, ts: list[float]) -> int:
    from tools.calcopy.engine.readline_tools.rangesheet import rangesheet
    rows = []
    with tempfile.TemporaryDirectory() as d:
        for i, t in enumerate(ts):
            p = str(Path(d) / f"r{i:02d}.jpg")
            rangesheet(mp4, p, t, round(t + 0.34, 3), 0.0333, 11, 0.18, y0, y1)
            rows.append(cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR))
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0))) for r in rows]
    cv2.imencode(".jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(out)
    return len(rows)


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 5:
        print(__doc__)
        return 2
    n = entersheet(a[0], a[1], int(a[2]), int(a[3]), [float(x) for x in a[4:]])
    print(a[1], n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
