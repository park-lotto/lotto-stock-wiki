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
MASKS_OF_MODE = {"color": ("color",), "bright": ("color",), "shadow": ("color",), "dark": ("dark", "wstroke"), "box": ("dark", "wstroke"),
                 "both": ("color", "dark", "wstroke"), "measure": ("wring",)}
# 모드별 띠 모양: (목표 높이, 최소 여유) — color 계열은 두 줄 자막까지 넓히고, 검정 글·흰 획(measure)은 핵에 바짝(넓히면 장면 글자가 섞여 경계가 는다,
# 10-25 대조: 홈디자인노트 measure 넓힘 F1 0.76~0.87 → 바짝 0.93~1.0, 썰풀다 iZ dark 0.77 → 1.0)
SHAPE_OF_MODE = {"color": (230, 24), "bright": (230, 24), "shadow": (230, 24), "dark": (0, 24), "box": (0, 24), "both": (0, 24), "measure": (0, 12)}
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
        elif mask == "wstroke":                                 # 흰 획(큰 흰 면은 뺌) — 흰 상자 테두리·흰 글
            wh = ((V > 215) & (S < 60)).astype(np.uint8)
            m = (wh > 0) & ~(cv2.morphologyEx(wh, cv2.MORPH_OPEN, np.ones((11, 11), np.uint8)) > 0)
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


def core_candidates(R: np.ndarray, k: int = 3) -> list[tuple[float, int, int]]:
    """겹치지 않는 상위 k 개 핵 창(점수, a, b) — 절반 크기 행."""
    out = []
    X = R.copy()
    for _ in range(k):
        sc, a, b = core_window(X)
        if sc <= 0 or b <= a:
            break
        out.append((sc, a, b))
        X[:, max(0, a - 30):b + 30] = 0                        # 그 자리를 지우고 다음
    return out


def _shape(c0: int, c1: int, mode: str, H: int, target_h: int | None, pad_min: int | None) -> tuple[list[int], int]:
    tg, pm = SHAPE_OF_MODE.get(mode, (TARGET_H, 24))
    tg = tg if target_h is None else target_h
    pm = pm if pad_min is None else pad_min
    pad = max(pm, (tg - (c1 - c0)) // 2)
    y0 = max(0, c0 - pad)
    y1 = min(H, c1 + pad)
    y0 -= y0 % 2
    if (y1 - y0) % 2:
        y1 = y1 - 1 if y1 >= H else y1 + 1
    return [y0, y1], pad


def candidates(mp4: str, mode: str = "color", H: int = 1920) -> list[dict]:
    k = H / SH
    out = []
    for m in MASKS_OF_MODE.get(mode, ("color",)):
        for sc, a, b in core_candidates(row_profile(mp4, m)):
            out.append({"score": round(float(sc), 2), "core": [int(a * k), int(b * k)], "mask": m})
    return sorted(out, key=lambda c: -c["score"])


def find_band(mp4: str, mode: str = "color", pad_min: int | None = None, target_h: int | None = None, H: int = 1920,
              prior: list[int] | None = None, cands: list[dict] | None = None) -> dict:
    """한 편 띠. prior(채널 다른 편들의 핵 가운데)가 있으면, 최고 점수의 절반 이상인 후보 중 prior 에 가장 가까운 것."""
    cands = cands if cands is not None else candidates(mp4, mode, H)
    best = cands[0]
    why = "최고 점수"
    if prior is not None and cands:
        ok = [c for c in cands if c["score"] >= 0.5 * best["score"]]
        near = min(ok, key=lambda c: abs((c["core"][0] + c["core"][1]) / 2 - prior[0]))
        if near is not best and abs((near["core"][0] + near["core"][1]) / 2 - prior[0]) < abs((best["core"][0] + best["core"][1]) / 2 - prior[0]):
            best, why = near, f"채널 무리 가운데 y≈{prior[0]} 에 가까운 후보(점수 {near['score']} ≥ 최고의 절반)"
    band, pad = _shape(best["core"][0], best["core"][1], mode, H, target_h, pad_min)
    return {"band": band, "core": best["core"], "mask": best["mask"], "score": best["score"], "pad": pad, "why": why}


def channel_bands(mp4s: list[str], mode="color", H: int = 1920) -> dict:
    """채널 여러 편: 편마다 최고 핵 가운데의 무리(±80px 안에 3편 이상, 과반)가 있으면 그것을 prior 로 편마다 다시 고른다.
    mode 는 문자열(모두 같음) 또는 {편 id: 모드} — 편마다 글자 꼴이 달라도 자막 자리는 채널이 같다(썰풀다 fnZN)."""
    md = (lambda m: mode.get(Path(m).stem, "color")) if isinstance(mode, dict) else (lambda m: mode)
    C = {str(m): candidates(m, md(m), H) for m in mp4s}
    centers = [(c[0]["core"][0] + c[0]["core"][1]) / 2 for c in C.values() if c]
    prior = None
    if len(centers) >= 3:
        best_c = max(centers, key=lambda y: sum(1 for z in centers if abs(z - y) <= 80))
        grp = [z for z in centers if abs(z - best_c) <= 80]
        if len(grp) >= 3 and len(grp) >= len(centers) / 2:
            prior = [float(np.median(grp))]
    return {Path(m).stem: find_band(m, md(m), H=H, prior=prior, cands=C[m]) for m in C if C[m]} | ({"_prior": prior} if prior else {})


_CH = {}


def band_in_channel(mp4: str, mode: str = "color") -> dict:
    """kal 흐름용: 같은 폴더의 mp4 전부로 channel_bands 를 한 번 재고(폴더에 _autoband_<mode>.json 저장 — 파일 목록·크기가 같으면 다시 안 잼) 이 편 결과."""
    folder = Path(mp4).parent
    mp4s = sorted(str(p) for p in folder.glob("*.mp4"))
    sig = [[Path(m).name, Path(m).stat().st_size] for m in mp4s]
    key = (str(folder), mode)
    if key not in _CH:
        cp = folder / f"_autoband_{mode}.json"
        d = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
        if d.get("_sig") != sig:
            d = channel_bands(mp4s, mode) if len(mp4s) >= 3 else {Path(m).stem: find_band(m, mode) for m in mp4s}
            d["_sig"] = sig
            try:
                cp.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
            except OSError:
                pass
        _CH[key] = d
    return _CH[key].get(Path(mp4).stem) or find_band(mp4, mode)


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
    res = channel_bands(mp4s, A.mode) if len(mp4s) >= 3 else {Path(m).stem: find_band(m, A.mode) for m in mp4s}
    for vid, r in res.items():
        if vid.startswith("_"):
            print(vid, r)
            continue
        found[vid] = r["band"]
        print(vid, r)
    if A.write and A.slug:
        print("→", write_profile(A.slug, found, A.mode))
    return 0


if __name__ == "__main__":
    sys.exit(main())
