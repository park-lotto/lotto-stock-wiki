# -*- coding: utf-8 -*-
"""썸네일 ↔ 영상 프레임 대조(thumbmatch) — 유튜브 썸네일이 영상 몇 초 프레임인지(가장 닮은 프레임 시각·상관)와 0초 프레임 상관.

어디서 왔나: 06 핫템리포트 워커(관제 263, 10-25)가 손으로 잰 방법(회색 90×160 상관, 0.167초 간격 — 스타일분석.md §9)을 도구로.
무엇을 재나: 썸네일·프레임을 회색 90×160 으로 줄여 피어슨 상관. 썸네일이 세로(9:16)가 아니면 가운데를 9:16 으로 잘라 본다.
입력: mp4 · 썸네일(jpg/png/webp 경로) 또는 info.json(thumbnail 주소를 받아 같은 폴더 <id>.thumb.jpg 로 저장 — 무료, 이미 있으면 다시 안 받음)
출력: {best_t, best_corr, t0_corr, top:[(t,corr)…5], step}

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/thumbmatch.py <mp4> <썸네일.jpg|info.json> [--step 0.1667]
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

SW, SH = 90, 160


def thumb_path(src: str) -> str:
    p = Path(src)
    if p.suffix.lower() != ".json":
        return str(p)
    d = json.loads(p.read_text(encoding="utf-8"))
    vid = d.get("id") or p.name.split(".")[0]
    out = p.parent / f"{vid}.thumb.jpg"
    if not out.exists():
        url = d.get("thumbnail") or (d.get("thumbnails") or [{}])[-1].get("url")
        if not url:
            raise ValueError("info.json 에 thumbnail 주소 없음")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=30).read()
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)   # webp 도 jpg 로 저장
        cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(out))
    return str(out)


def _norm(g: np.ndarray) -> np.ndarray:
    g = g.astype(np.float32).ravel()
    g -= g.mean()
    return g / (np.linalg.norm(g) + 1e-6)


def _thumb_vec(path: str) -> np.ndarray:
    im = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    h, w = im.shape
    if abs(w / h - 9 / 16) > 0.02:                       # 가로 썸네일이면 가운데 9:16
        cw = int(round(h * 9 / 16))
        if cw <= w:
            x0 = (w - cw) // 2
            im = im[:, x0:x0 + cw]
    return _norm(cv2.resize(im, (SW, SH), interpolation=cv2.INTER_AREA))


def thumbmatch(mp4: str, thumb: str, step: float = 1 / 6) -> dict:
    tv = _thumb_vec(thumb_path(thumb))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"fps={1 / step:.6f},scale={SW}:{SH}:flags=area", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = len(raw) // (SW * SH)
    F = np.frombuffer(raw, np.uint8)[:n * SW * SH].reshape(n, SH, SW)
    corr = np.array([float(_norm(f) @ tv) for f in F])
    if not len(corr):
        return {"best_t": None, "best_corr": None, "t0_corr": None, "top": [], "step": step}
    order = np.argsort(-corr)
    top = []
    for i in order:                                       # 서로 0.5초 넘게 떨어진 상위 5
        if all(abs(i - j) * step > 0.5 for j, _ in top):
            top.append((int(i), float(corr[i])))
        if len(top) == 5:
            break
    b = int(order[0])
    return {"best_t": round(b * step, 3), "best_corr": round(float(corr[b]), 3), "t0_corr": round(float(corr[0]), 3),
            "top": [(round(i * step, 3), round(c, 3)) for i, c in top], "step": round(step, 4)}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    step = 1 / 6
    if "--step" in a:
        i = a.index("--step")
        step = float(a[i + 1])
        del a[i:i + 2]
    if len(a) < 2:
        print(__doc__)
        return 2
    print(json.dumps(thumbmatch(a[0], a[1], step), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
