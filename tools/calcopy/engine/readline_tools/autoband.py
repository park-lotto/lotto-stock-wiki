# -*- coding: utf-8 -*-
"""자막 띠 자동 찾기(autoband) — 프로필에 손 띠가 없는 새 채널도 capseg·measure 를 돌릴 수 있게 편마다 자막 띠를 찾는다.

판단 주인: find_band(mp4, mode) 한 곳. build_lr.bands_for 가 프로필 bands{<편>} 다음 순서로 부른다.
무엇을 재나:
  1) 4fps·절반 크기(540x960)로 프레임마다 글자 잉크 마스크 행 합 R[t,y] — mode 에 맞는 꼴(color/bright/both = 검정 외곽 옆 밝은 채움,
     dark/box = 흰 옆 검정 글, both = 둘 중 점수 높은 쪽, measure = 흰 획+색 고리).
  2) 행 점수 v(y) = 바뀜 c(y)(이웃 표본 행 합 차의 평균) × 있음 p(y)(잉크 있는 표본 비율). 제목·로고(늘 있고 안 바뀜)는 c≈0,
     장면 가장자리(가끔 있고 늘 바뀜)는 p 가 낮다.
  3) 높이 48~320px 창 중 '안 평균 − 위아래 60px 평균' × 높이^0.3 이 가장 큰 창 = 자막 핵(한 줄).
  4) 띠 = 핵 ± max(24, (230 − 핵 높이)/2) — 한 줄 핵이면 두 줄 자막 자리까지, 두 줄 핵이면 조금만(10-25 대조로 고른 값).
     (핵과 바뀌는 순간이 같은 행으로 넓히기·상관으로 넓히기는 시험했지만 두 줄 자막 윗줄을 못 찾아 버렸다.)
  5) 짝수 y·짝수 높이(capseg crop exact 와 짝).
출력: {band:[y0,y1], core:[y0,y1], mask, score}
CLI: 한 채널 원본 폴더를 훑어 profiles/<slug>.json 에 bands{<편>:[y0,y1]}·default 를 적는다(--write, 손 값 capseg_band 는 안 건드림).

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/autoband.py <mp4 ...> [--mode color]
    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/autoband.py --slug <slug> --src-dir <원본 폴더> [--mode color] [--write]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

PROFILES = Path(__file__).resolve().parent / "profiles"
SW, SH = 540, 960          # 절반 크기(행 1개 = 원본 2px)
MASK_OF_MODE = {"color": "color", "bright": "color", "both": "both", "dark": "dark", "box": "dark", "shadow": "color", "measure": "wring"}
TARGET_H = 230   # 띠 목표 높이(px): 핵이 한 줄이면 위아래로 넓혀 두 줄 자막을, 두 줄이면 조금만 — 10-25 34편 대조에서 230 이 줄판독 경계 재현 21/27 로 가장 좋음(260: 19, 290: 16)


def row_profile(mp4: str, mask: str = "color", fps: float = 4) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"fps={fps},scale={SW}:{SH}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True).stdout
    n = len(raw) // (SW * SH * 3)
    F = np.frombuffer(raw, np.uint8)[:n * SW * SH * 3].reshape(n, SH, SW, 3)
    k = np.ones((5, 5), np.uint8)
    R = []
    for f in F:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        V = hsv[..., 2]
        S = hsv[..., 1]
        if mask == "color":
            m = (V > 185) & (cv2.dilate((V < 45).astype(np.uint8), k) > 0)
        elif mask == "dark":
            m = (V < 60) & (cv2.dilate(((V > 200) & (S < 70)).astype(np.uint8), k) > 0)
        elif mask == "wring":                                   # 흰 획 + 바로 옆 어두운 고리(색 외곽), 큰 흰 면은 뺌(홈디자인노트)
            wh = ((V > 215) & (S < 60)).astype(np.uint8)
            ring = ((V < 190) & (wh == 0)).astype(np.uint8)
            m = (wh > 0) & (cv2.dilate(ring, np.ones((5, 5), np.uint8)) > 0) & ~(cv2.morphologyEx(wh, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)) > 0)
        else:
            m = (V > 215) & (S < 60)
        R.append(m.sum(1))
    return np.array(R, np.float32)


def core_window(R: np.ndarray) -> tuple[float, int, int]:
    c = np.abs(np.diff(R, axis=0)).mean(0)
    p = (R > 4).mean(0)
    v = np.convolve(c * p, np.ones(5) / 5, mode="same")
    n = len(v)
    cs = np.r_[0, np.cumsum(v)]

    def m(a, b):
        return (cs[b] - cs[a]) / max(1, b - a)
    best = (-1e9, 0, 0)
    for h in range(24, 162, 2):
        for a in range(30, n - h - 30, 2):
            b = a + h
            sc = (m(a, b) - 0.5 * (m(a - 30, a) + m(b, b + 30))) * h ** 0.3
            if sc > best[0]:
                best = (sc, a, b)
    return best


def find_band(mp4: str, mode: str = "color", pad_min: int = 24, target_h: int = TARGET_H, H: int = 1920) -> dict:
    mask = MASK_OF_MODE.get(mode, "color")
    if mask == "both":                                           # 흰 글·검정 글 섞인 채널: 점수 높은 쪽
        cands = [(core_window(row_profile(mp4, m)), m) for m in ("color", "dark")]
        (sc, a, b), mask = max(cands, key=lambda x: x[0][0])
    else:
        sc, a, b = core_window(row_profile(mp4, mask))
    k = H / SH
    c0, c1 = int(a * k), int(b * k)
    pad = max(pad_min, (target_h - (c1 - c0)) // 2)
    y0 = max(0, c0 - pad)
    y1 = min(H, c1 + pad)
    y0 -= y0 % 2
    if (y1 - y0) % 2:
        y1 = y1 - 1 if y1 >= H else y1 + 1
    return {"band": [y0, y1], "core": [c0, c1], "mask": mask, "score": round(float(sc), 2), "pad": pad}


def write_profile(slug: str, found: dict[str, list[int]], mode: str) -> Path:
    p = PROFILES / f"{slug}.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"_what": f"{slug} 판독 도구 채널 값"}
    d["bands"] = dict(sorted(found.items()))
    ys0 = sorted(v[0] for v in found.values())
    ys1 = sorted(v[1] for v in found.values())
    d["bands_default"] = [ys0[len(ys0) // 2], ys1[len(ys1) // 2]] if found else None
    d["_bands_how"] = f"autoband.find_band(mode={mode}) 자동 — 손으로 고친 값은 capseg_band 또는 bands 에 직접(손 값이 이긴다)"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mp4s", nargs="*")
    ap.add_argument("--mode", default="color")
    ap.add_argument("--slug")
    ap.add_argument("--src-dir")
    ap.add_argument("--write", action="store_true")
    A = ap.parse_args(argv)
    mp4s = list(A.mp4s) + (sorted(str(p) for p in Path(A.src_dir).glob("*.mp4")) if A.src_dir else [])
    found = {}
    for mp4 in mp4s:
        r = find_band(mp4, A.mode)
        found[Path(mp4).stem] = r["band"]
        print(Path(mp4).stem, r)
    if A.write and A.slug:
        print("→", write_profile(A.slug, found, A.mode))
    return 0


if __name__ == "__main__":
    sys.exit(main())
