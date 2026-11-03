# -*- coding: utf-8 -*-
"""꾸밈 표시(화살표·원·밑줄) 색 덩어리 추적(marktrack) — 색마다 덩어리를 프레임 상자로, 같은 색·2프레임 안으로 이어 트랙.

어디서 왔나: 06 샤크탱크(해외쇼츠) 워커가 저장소 밖 C:/숏템_칼카피/foreignshowshow/work/tools/fxdet.py 에 만든 것을 옮김(알고리즘 그대로).
red.py 와 무엇이 다른가: red.py = 한 구간 프레임별 빨강 칸 수·상자 표(사람이 시각을 보고 고른 구간). marktrack = 영상 전체에서 여러 색 표시의
            등장(t_in)·퇴장(t_out)·자리(상자 중앙값)·움직인 거리를 트랙으로 뽑는다.
무엇을 재나: 창[y0,y1) 반 크기 RGB 에서 색 조건(기본 초록 R<45·B<45·G>215 / 분홍 R>190·B>165·G<120 / 빨강 R>215·G<60·B<65) 연결요소 면적≥120 →
            그 프레임 덩어리들의 바깥 상자 · 같은 색이 2프레임 안에 다시 나오면 같은 트랙 · 3프레임 미만 트랙은 버림.
출력: [{color, t_in, t_out, frames, x, y, w, h(원본 좌표 상자 중앙값), area_med, move_px}]

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/marktrack.py <mp4> <out.json> [--band 434,1486] [--sheet out.jpg]
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np

COLORS = {
    "초록": lambda r, g, b: (r < 45) & (b < 45) & (g > 215),
    "분홍": lambda r, g, b: (r > 190) & (b > 165) & (g < 120),
    "빨강": lambda r, g, b: (r > 215) & (g < 60) & (b < 65),
}


def _frames(mp4, y0, y1):
    from tools.calcopy.engine.readline_tools.capseg import fps_filter
    w, h = 540, (y1 - y0) // 2
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", mp4, "-vf", fps_filter(mp4) + f"crop=1080:{y1 - y0}:0:{y0}:exact=1,scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(w * h * 3)
        if len(b) < w * h * 3:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3).astype(int)
    p.wait()


def marktrack(mp4: str, y0: int = 434, y1: int = 1486, colors: dict | None = None, fps: float = 30.0) -> list[dict]:
    colors = colors or COLORS
    tracks = []
    open_ = {}
    for i, a in enumerate(_frames(mp4, y0, y1)):
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        for col, fn in colors.items():
            m = fn(r, g, b)
            n, lab, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
            boxes = [st[k] for k in range(1, n) if st[k][4] >= 120]
            if not boxes:
                continue
            x0 = min(bb[0] for bb in boxes)
            yy0 = min(bb[1] for bb in boxes)
            x1 = max(bb[0] + bb[2] for bb in boxes)
            yy1 = max(bb[1] + bb[3] for bb in boxes)
            area = int(sum(bb[4] for bb in boxes))
            box = (x0 * 2, y0 + yy0 * 2, (x1 - x0) * 2, (yy1 - yy0) * 2)
            tr = open_.get(col)
            if tr and i - tr["last"] <= 2:
                tr["boxes"].append(box)
                tr["areas"].append(area)
                tr["last"] = i
            else:
                tr = {"color": col, "first": i, "last": i, "boxes": [box], "areas": [area]}
                tracks.append(tr)
                open_[col] = tr
    out = []
    for t in tracks:
        if t["last"] - t["first"] < 2:
            continue
        B = np.array(t["boxes"])
        md = np.median(B, 0)
        out.append({"color": t["color"], "t_in": round(t["first"] / fps, 3), "t_out": round((t["last"] + 1) / fps, 3), "frames": len(t["boxes"]),
                    "x": int(md[0] + md[2] / 2), "y": int(md[1] + md[3] / 2), "w": int(md[2]), "h": int(md[3]), "area_med": int(np.median(t["areas"])),
                    "move_px": round(float(np.hypot(*(B[-1, :2] + B[-1, 2:] / 2 - B[0, :2] - B[0, 2:] / 2))), 1)})
    return out


def sheet(mp4: str, out: list[dict], path: str) -> None:
    cap = cv2.VideoCapture(mp4)
    tiles = []
    for k, t in enumerate(out):
        cap.set(cv2.CAP_PROP_POS_MSEC, (t["t_in"] + t["t_out"]) / 2 * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        x0, y0 = t["x"] - t["w"] // 2, t["y"] - t["h"] // 2
        cv2.rectangle(f, (x0, y0), (x0 + t["w"], y0 + t["h"]), (255, 255, 0), 6)
        cv2.putText(f, f"#{k} {t['t_in']}-{t['t_out']}", (20, 420), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (0, 255, 255), 5)
        tiles.append(cv2.resize(f[300:1600], (270, 325)))
    while len(tiles) % 6:
        tiles.append(np.zeros_like(tiles[0]) if tiles else np.zeros((325, 270, 3), np.uint8))
    if tiles:
        rows = [np.hstack(tiles[k:k + 6]) for k in range(0, len(tiles), 6)]
        cv2.imencode(".jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(path)


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    band, sh = (434, 1486), None
    if "--band" in a:
        i = a.index("--band")
        band = tuple(int(x) for x in a[i + 1].split(","))
        del a[i:i + 2]
    if "--sheet" in a:
        i = a.index("--sheet")
        sh = a[i + 1]
        del a[i:i + 2]
    if len(a) < 2:
        print(__doc__)
        return 2
    out = marktrack(a[0], *band)
    json.dump(out, open(a[1], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    if sh:
        sheet(a[0], out, sh)
    for k, t in enumerate(out):
        print(k, t)
    return 0


if __name__ == "__main__":
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    sys.exit(main())
