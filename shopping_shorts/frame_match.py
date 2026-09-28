# -*- coding: utf-8 -*-
"""영상 프레임 닮음 판정 — 한 곳(0순위-B, 2026-09-27).

쓰는 곳: clean_base.calibrate(옛 청소본 컷별 밀림 측정) · tools/editor_vs_final_video.py(편집 화면 vs 완성본 비교).
두 곳이 같은 '닮음'을 써야 도구가 "밀림 0"이라고 할 때 보정도 같은 자로 잰 것이다.

특징 = 90x160·30fps로 푼 프레임의 가운데 띠(위 10%·아래 30% 제외 — 채널명·자막 띠)만 회색조 →
  5x5 칸 평균(흐림+축소) → 밝기·대비 정규화(z). 거리 = 칸별 |차| 평균.
  같은 장면이면 작고(측정 최대 0.45), 무관한 장면이면 이론값 ~1.13. SCENE_T 이상 = 다른 장면.
★청소본은 원본 자막을 지운 영상이라 전체 화면을 비교하면 자막 띠 차이가 걸린다 — 가운데 띠만 본다.
"""
import subprocess

import numpy as np

FPS, W, H = 30, 90, 160
Y0, Y1 = int(H * 0.10), int(H * 0.70)     # 가운데 띠만 — 위 채널명·아래 자막 띠 제외
BLK = 5                                    # 5x5 칸 평균 = 흐림 + 축소(18x19)
SCENE_T = 0.55                             # 이 거리 이상 = 다른 장면(측정 2026-09-27, 30작업 706컷: 같은 장면 최대 0.452)
SHIFT_TOL = 0.02                           # 최소 거리에서 이만큼 안이면 같은 후보로 본다(정지 화면 가짜 밀림 방지)


def duration(path):
    """영상 길이(초). 못 재면 0."""
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                              "-of", "csv=p=0", str(path)], timeout=60).strip())
    except Exception:      # noqa: BLE001
        return 0.0


def frames(path, t0=None, dur=None, timeout=600, pre_vf=None):
    """영상 → (N,H,W,3) uint8, 프레임 i = t0 + i/FPS 초. t0·dur 없으면 통째로.
    pre_vf: 줄이기 전에 걸 ffmpeg 필터(예: 완성본 구도 자르기 — 원본을 청소본과 같은 화면으로 맞출 때)."""
    cmd = ["ffmpeg", "-v", "error"]
    if t0 is not None:
        cmd += ["-ss", "%.3f" % max(0.0, float(t0))]
    if dur is not None:
        cmd += ["-t", "%.3f" % max(1.0 / FPS, float(dur))]
    vf = "fps=%d,%sscale=%d:%d" % (FPS, (pre_vf + ",") if pre_vf else "", W, H)
    cmd += ["-i", str(path), "-an", "-vf", vf,
            "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    a = np.frombuffer(r.stdout, np.uint8)
    n = a.size // (H * W * 3)
    return a[: n * H * W * 3].reshape(n, H, W, 3)


# ★아래 띠(2026-09-27 fab5e5d4662a): 원본 **위쪽**에 글자 띠(검정 바탕 문구, 화면 10~21%)가 박힌 영상은 청소본에서 그 띠가
#   지워지고 채워진다(자막제거가 한 일) → 가운데 띠(10~70%) 비교만으로는 같은 장면·같은 프레임인데 0.65~0.77로 '다른 장면'.
#   같은 프레임을 25~95%로 재면 0.00~0.03이었다. 그래서 **두 띠 중 가까운 쪽**을 거리로 쓴다(dist_any) — 위 글자 띠는 아래 띠가,
#   아래 자막 띠는 가운데 띠가 비켜 간다. 진짜 다른 장면은 두 띠가 45% 겹쳐 둘 다 멀다.
Y2A, Y2B = int(H * 0.25), int(H * 0.95)


def _band_feats(fr, y0, y1):
    g = fr[:, y0:y1].astype(np.float32).mean(axis=3)
    h, w = (g.shape[1] // BLK) * BLK, (g.shape[2] // BLK) * BLK
    g = g[:, :h, :w].reshape(len(g), h // BLK, BLK, w // BLK, BLK).mean(axis=(2, 4))
    m = g.mean(axis=(1, 2), keepdims=True)
    s = g.std(axis=(1, 2), keepdims=True)
    return (g - m) / (s + 8.0)


def feats_low(fr):
    """아래 띠(25~95%) 특징 — dist_any 의 두 번째 자."""
    return _band_feats(fr, Y2A, Y2B)


def dist_any(ff, ff2, js, ref, ref2):
    """두 띠(가운데·아래) 거리 중 작은 쪽 — 글자 띠가 지워진 청소본도 같은 장면으로 본다(위 주석)."""
    return np.minimum(dist(ff, js, ref), dist(ff2, js, ref2))


def feats(fr):
    """가운데 띠 회색조 → 5x5 평균 → z 정규화. (N, h, w) float32."""
    g = fr[:, Y0:Y1].astype(np.float32).mean(axis=3)
    h, w = (g.shape[1] // BLK) * BLK, (g.shape[2] // BLK) * BLK
    g = g[:, :h, :w].reshape(len(g), h // BLK, BLK, w // BLK, BLK).mean(axis=(2, 4))
    m = g.mean(axis=(1, 2), keepdims=True)
    s = g.std(axis=(1, 2), keepdims=True)
    return (g - m) / (s + 8.0)             # +8: 거의 단색(검정) 화면에서 잡음이 부풀지 않게


def dist(ff, js, ref):
    """ff[js] 각각과 ref(특징 한 장)의 거리. 범위 밖 인덱스는 inf."""
    js = np.asarray(js)
    out = np.full(len(js), np.inf, np.float32)
    ok = (js >= 0) & (js < len(ff))
    if ok.any():
        out[ok] = np.abs(ff[js[ok]] - ref).mean(axis=tuple(range(1, ff.ndim)))
    return out


def pick(js, d, prefer, tol=SHIFT_TOL):
    """거리 d 가 최소 + tol 안인 후보 중 prefer 에 가장 가까운 js. → (고른 js, 최소 거리, 후보 js 배열)."""
    js = np.asarray(js)
    dmin = float(np.min(d))
    ok = js[d <= dmin + tol]
    return int(ok[np.argmin(np.abs(ok - prefer))]), dmin, ok
