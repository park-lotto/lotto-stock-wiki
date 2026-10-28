# -*- coding: utf-8 -*-
"""구간 시트(segsheet) — capseg 덩어리마다 가운데 프레임을 [장면 썸네일 | 자막 띠 확대 | 시각·hex·잉크] 한 줄로, 10줄씩 jpg.

어디서 왔나: 06 잇템로그 워커(관제 263, 10-24)의 세션 임시 폴더 도구 segsheet.py 를 그대로 옮김(알고리즘 바꾸지 않음).
무엇에 쓰나: 사람 눈 판독용 — 자막 덩어리 경계(capseg)가 맞는지·글·화자를 한 장에서 본다. 측정값을 만들지 않는다.
입력: mp4 · capseg 결과 json · 출력 접두어 · (선택) 자막 띠 cy0 cy1 (기본 1150 1460)
출력: <접두어>_00.jpg, _01.jpg ... (10덩어리씩). 함수는 {rows, sheets(만든 파일 경로)} 를 돌려준다.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/segsheet.py <mp4> <seg.json> <out_prefix> [cy0 cy1]
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np


def segsheet(mp4: str, segs: list[dict], outp: str, cy0: int = 1150, cy1: int = 1460) -> dict:
    cap = cv2.VideoCapture(mp4)
    rows = []
    for i, s in enumerate(segs):
        t = (s["t0"] + s["t1"]) / 2
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        th = cv2.resize(f, (135, 240))
        band = cv2.resize(f[cy0:cy1], (810, int((cy1 - cy0) * 0.75)))
        hh = max(240, band.shape[0])
        row = np.zeros((hh, 135 + 810 + 220, 3), np.uint8)
        row[:240, :135] = th
        row[:band.shape[0], 135:945] = band
        cv2.putText(row, f"#{i} {s['t0']:.3f}-{s['t1']:.3f}", (950, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(row, f"{s.get('hex')} ink{s.get('ink')}", (950, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
        rows.append(row)
    cap.release()
    made = []
    for k in range(0, len(rows), 10):
        p = f"{outp}_{k // 10:02d}.jpg"
        cv2.imencode(".jpg", np.vstack(rows[k:k + 10]), [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(p)
        made.append(p)
    return {"rows": len(rows), "sheets": made}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 3:
        print(__doc__)
        return 2
    mp4, sj, outp = a[0], a[1], a[2]
    cy0, cy1 = (int(a[3]), int(a[4])) if len(a) > 4 else (1150, 1460)
    segs = json.load(open(sj))
    r = segsheet(mp4, segs, outp, cy0, cy1)
    print(r["rows"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
