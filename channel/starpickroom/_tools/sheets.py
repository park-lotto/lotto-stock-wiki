# -*- coding: utf-8 -*-
"""스타픽룸 판독용 시트 (관제 097) — 눈 판독 보조. 뜯기(analyze)와 별개로 사람이 볼 그림만 만든다.
    PYTHONUTF8=1 py channel/starpickroom/_tools/sheets.py <mp4> <out_dir> [--fps 2] [--y0 470 --y1 1570]
① sheet_<id>_NN.jpg : fps 칸 시트(초 라벨) — 창 영역만
② change_<id>.json  : 10fps 로 창 안 '글자 띠 후보'(밝은 흰/노랑 + 진한 외곽) 변화량 → 바뀌는 지점 목록
"""
import argparse, json, sys
from pathlib import Path
import cv2, numpy as np


def frames(mp4, fps):
    """순서대로 읽고 fps 간격에 가장 가까운 프레임만 낸다(되감기 탐색은 느리다)."""
    cap = cv2.VideoCapture(str(mp4)); src = cap.get(cv2.CAP_PROP_FPS) or 30
    i = 0; nxt = 0.0
    while True:
        ok, f = cap.read()
        if not ok: break
        if i + 0.5 >= nxt:
            yield round(i / src, 2), f
            nxt += src / fps
        i += 1
    cap.release()


def text_mask(img):
    """흰·노랑 채움(밝음) 바로 옆에 어두운 외곽이 있는 픽셀 = 자막 글자 후보."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    bright = (hsv[..., 2] > 215) & ((hsv[..., 1] < 60) | ((hsv[..., 0] > 20) & (hsv[..., 0] < 35)))
    dark = cv2.dilate(((hsv[..., 2] < 50)).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return (bright & dark).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mp4"); ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=2); ap.add_argument("--y0", type=int, default=470); ap.add_argument("--y1", type=int, default=1570)
    ap.add_argument("--cols", type=int, default=10); ap.add_argument("--rows", type=int, default=4)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True); vid = Path(a.mp4).stem
    tiles = []
    for t, f in frames(a.mp4, a.fps):
        c = cv2.resize(f[a.y0:a.y1], (216, int(216 * (a.y1 - a.y0) / 1080)))
        cv2.putText(c, f"{t:.1f}", (3, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4); cv2.putText(c, f"{t:.1f}", (3, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        tiles.append(c)
    per = a.cols * a.rows; h, w = tiles[0].shape[:2]
    for p in range(0, len(tiles), per):
        grid = np.zeros((h * a.rows, w * a.cols, 3), np.uint8)
        for i, c in enumerate(tiles[p:p + per]):
            grid[(i // a.cols) * h:(i // a.cols + 1) * h, (i % a.cols) * w:(i % a.cols + 1) * w] = c
        (out / f"sheet_{vid}_{p // per:02d}.jpg").write_bytes(cv2.imencode(".jpg", grid, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes())  # 한글 경로: imwrite 는 조용히 실패
    # 10fps 글자 변화
    prev = None; rows = []
    for t, f in frames(a.mp4, 10):
        m = text_mask(f[a.y0:a.y1]); ys = np.where(m.sum(1) > 6)[0]
        d = None if prev is None else int((m ^ prev).sum())
        rows.append({"t": t, "ink": int(m.sum()), "diff": d, "y": [int(ys.min()) + a.y0, int(ys.max()) + a.y0] if len(ys) else None})
        prev = m
    thr = "diff > max(600, 0.35 x max(앞 ink, 이 ink))"
    ch = [r for i, r in enumerate(rows) if r["diff"] and r["diff"] > max(600, 0.35 * max(rows[i - 1]["ink"], r["ink"]))]
    (out / f"change_{vid}.json").write_text(json.dumps({"thr": thr, "changes": ch, "all": rows}, ensure_ascii=False), encoding="utf-8")
    print(vid, "tiles", len(tiles), "changes", len(ch))


if __name__ == "__main__": main()
