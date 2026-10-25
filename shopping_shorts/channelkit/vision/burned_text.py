# -*- coding: utf-8 -*-
"""컷 안 '남의 박힌 글자(자막·워터마크·제목 띠)' 판정 — **판정 주인 한 곳**(관제 271, 2026-10-26).

칼카피 렌더 전 관문 ④(tools/calcopy/hybrid/render_bench.py 의 text_feats·foreign_text·TEXT_*)를 그대로 옮긴 것이다 — 같은 자·같은 문턱.
  쓰는 곳: 웹 라인 VMake 보낼 컷(mix_pipeline.vmake_send_cuts ← vmake_cut_text) · 칼카피 관문 ④(옮긴 뒤 import 로 바꾼다 — handoff/VMake자막판정.md).
  표본 = 칼카피 shopping_shorts/tests/fixtures/cut_content_labels.json (오푸스 눈 라벨 762컷, 홀수 반 P 0.917·R 0.887).
★문턱을 바꾸면 그 표본 시험(test_cut_content_labels)이 먼저 깨진다 — 표본을 다시 보고(눈 판정 = 오푸스) 고친다.
★글자 상자 자 = channelkit.vision.text_boxes_scored(PP-OCRv5 det). 모델이 없으면 죽는다 — 조용한 폴백 금지(부르는 쪽이 경보).
"""
import subprocess

import numpy as np

# ── 글자 문턱 (render_bench 10-25 표본 — 설명은 그쪽 주석 그대로) ─────────────────────────────
TEXT_SCORE_MIN = 0.9              # 상자 점수(윤곽 안 확률 평균)
TEXT_FILL_MIN = 0.8               # 윤곽 넓이/사각형 넓이(얼굴·유리 질감을 따라 번진 가짜 윤곽 거르기 — 박힌 글은 0.85~0.95)
TEXT_ASPECT_MIN = 1.6             # 가로/세로 — 글줄 모양
TEXT_H_RANGE = (0.035, 0.25)      # 상자 높이 / 창 높이 — 진열대 가격표(0.01~0.03)는 밖
TEXT_BLUR_MAX = 0.3               # 흐림 칸이 이만큼 넘게 덮으면 이미 가린 글
TEXT_STILL_RATIO = 0.5            # 상자 안 변화 / 둘레 변화 < 이 값이면 붙박이(박힌 글) — 움직이는 화면 위 자막
TEXT_RING_MIN = 1.0               # 둘레 변화가 이보다 작으면(멈춘 화면) 붙박이를 잴 수 없다 → 크기로만(TEXT_STATIC_H)
TEXT_STATIC_H = 0.05              # 멈춘 화면에서는 높이 ≥ 창 5% 글줄만(제목 띠·큰 자막)
TEXT_FAR_RING = 5.0               # 긴 간격(같은 컷 다른 잴 프레임) 둘레 변화가 이 이상이어야 그 짝을 쓴다
TEXT_SCENE_RATIO = (0.6, 1.3)     # 멈춘 화면 글: 긴 간격 짝에서 안/둘레 가 이 범위 = 주변과 같이 변함 = 장면 속 글
TEXT_SMALL_H = 0.03               # 창 3~3.5% 작은 글줄은 긴 간격 짝 전부에서 안/둘레 < TEXT_SMALL_STILL 일 때만
TEXT_SMALL_STILL = 0.6
TEXT_GLYPH_STILL = 0.3            # 획 픽셀 변화(d_gl) / 둘레 변화 < 이 값 = 획이 그대로인 박힌 글
TEXT_GLYPH_FILL = 0.65            # 획 판정 상자 채움 하한
TEXT_GLYPH_ASPECT = 3.0           # 획 판정은 글줄(가로/세로 ≥ 3)만
TEXT_GLYPH_RING = 2.0             # 둘레 변화가 이 이상일 때만 획 판정
TEXT_MIN_HITS = 1                 # 컷 3장 중 글자 걸린 장 수 — 1(2로 올리면 짧게 지나가는 자막을 놓친다)
PAIR_FRAMES = 2                   # 붙박이 재기 짝 = 2프레임 뒤(render_bench CONTENT_PAIR = 2/FPS 와 같은 뜻)


def look_times(d: float) -> list:
    """컷 안 재는 시각(컷 시작부터 초) — 처음·가운데·끝 근처 3장(render_bench.look_times 와 같다)."""
    return [round(x, 3) for x in (min(0.2, d / 4), d / 2, max(d - 0.2, 3 * d / 4))]


def _in_ring(diff, box) -> list:
    """상자 안 평균 변화 · 둘레(상자 높이만큼 넓힌 테) 평균 변화."""
    H, W = diff.shape
    x0, y0, x1, y1 = box
    bh = max(1, y1 - y0)
    ring = diff[max(0, y0 - bh):min(H, y1 + bh), max(0, x0 - bh):min(W, x1 + bh)]
    inner = diff[y0:y1, x0:x1]
    return [round(float(inner.mean()), 2) if inner.size else 0.0, round(float((ring.sum() - inner.sum()) / max(1, ring.size - inner.size)), 2)]


def _glyph_diff(g, diffs, box) -> list:
    """상자 안 '획 픽셀'(오츠 두 무리 중 적은 쪽 = 글자 획) 위 평균 변화 — diffs 마다 하나."""
    import cv2
    x0, y0, x1, y1 = box
    p = g[y0:y1, x0:x1]
    if p.size < 16:
        return [0.0 for _ in diffs]
    u = p.astype(np.uint8)
    _, m = cv2.threshold(u, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m = m.astype(bool)
    if m.mean() > 0.5:
        m = ~m
    if not m.any():
        return [0.0 for _ in diffs]
    return [round(float(d[y0:y1, x0:x1][m].mean()), 2) for d in diffs]


def text_feats(a, b, far=(), blur=None) -> list:
    """한 프레임(a, BGR)의 글자 상자마다 잰 값 — 판정은 foreign_text. b = 짝 프레임(붙박이 재기). far = 같은 컷의 다른 잴 프레임들.
    blur = 상자(창 좌표) → 흐림 칸이 덮는 비율(0~1) 함수(칼카피 재료 blur). 없으면 0."""
    import cv2
    from shopping_shorts.channelkit import vision as V
    gray = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    ga = gray(a)
    gb = gray(b) if b is not None else ga
    diff = np.abs(ga - gb)
    dfar = [np.abs(ga - gray(x)) for x in far if x is not None and x.shape == a.shape]
    H, W = ga.shape
    out = []
    for q in V.text_boxes_scored(a):
        x0, y0, x1, y1 = q["box"]
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        d_in, d_ring = _in_ring(diff, (x0, y0, x1, y1))
        gl = _glyph_diff(ga, [diff] + dfar, (x0, y0, x1, y1))
        out.append({"box": [x0, y0, x1, y1], "score": q["score"], "fill": q["fill"], "aspect": round(bw / bh, 2), "h": round(bh / H, 4),
                    "cx": round((x0 + x1) / 2 / W, 3), "cy": round((y0 + y1) / 2 / H, 3),
                    "d_in": d_in, "d_ring": d_ring, "d_gl": gl[0], "fg": gl[1:],
                    "fi": [_in_ring(d, (x0, y0, x1, y1)) for d in dfar],
                    "blur": float(blur((x0, y0, x1, y1))) if blur else 0.0})
    return out


def foreign_text(f: dict) -> bool:
    """글자 상자 하나가 '남의 박힌 글자(자막·워터마크·로고 글)'인가 — **판정 주인**.
    fi(긴 간격 짝)·d_gl(획 변화) 가 없는 옛 값은 그 판정을 건너뛴다(옛 판정 그대로)."""
    if f["blur"] > TEXT_BLUR_MAX:
        return False
    if (f.get("d_gl") is not None and f["score"] >= TEXT_SCORE_MIN and f["fill"] >= TEXT_GLYPH_FILL and f["aspect"] >= TEXT_GLYPH_ASPECT
            and TEXT_SMALL_H <= f["h"] <= TEXT_H_RANGE[1] and f["d_ring"] >= TEXT_GLYPH_RING and f["d_gl"] < TEXT_GLYPH_STILL * f["d_ring"]):
        return True
    if f["score"] < TEXT_SCORE_MIN or f["fill"] < TEXT_FILL_MIN or f["aspect"] < TEXT_ASPECT_MIN:
        return False
    if not (TEXT_SMALL_H <= f["h"] <= TEXT_H_RANGE[1]):
        return False
    far = [i / r for i, r in (f.get("fi") or []) if r >= TEXT_FAR_RING]
    small = f["h"] < TEXT_H_RANGE[0]
    if small and not (far and max(far) < TEXT_SMALL_STILL):
        return False
    if f["d_ring"] < TEXT_RING_MIN:
        if any(TEXT_SCENE_RATIO[0] <= q <= TEXT_SCENE_RATIO[1] for q in far):
            return False
        return f["h"] >= TEXT_STATIC_H or small
    return f["d_in"] < TEXT_STILL_RATIO * f["d_ring"]


def cut_hit(frames_feats) -> bool:
    """컷 하나(잴 프레임마다 글자 상자 값 목록)에 남의 박힌 글자가 있나 — TEXT_MIN_HITS 장 이상."""
    return sum(1 for fr in frames_feats if any(foreign_text(b) for b in fr)) >= TEXT_MIN_HITS


# ── 영상 파일에서 바로 재기(웹 라인 조립본) ─────────────────────────────────────────────
def _probe_wh(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0:s=x", str(path)], capture_output=True, timeout=60)
    w, h = (out.stdout or b"").decode("ascii", "ignore").strip().split("x")[:2]
    return int(w), int(h)


def _frames_at(path, t, n, wh):
    """시각 t 부터 연속 n 프레임(BGR) — ffmpeg 입력 앞 -ss(정확 탐색). 모자라면 있는 만큼."""
    w, h = wh
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % max(0.0, t), "-i", str(path), "-frames:v", str(n),
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, timeout=120)
    buf = out.stdout or b""
    k = len(buf) // (w * h * 3)
    return [np.frombuffer(buf[i * w * h * 3:(i + 1) * w * h * 3], np.uint8).reshape(h, w, 3) for i in range(k)]


def video_cut_feats(path, t0: float, dur: float, wh=None) -> list:
    """영상 파일의 [t0, t0+dur) 컷 하나 → 잴 프레임 3장마다 글자 상자 값(text_feats). 칼카피 cut_content_feats 와 같은 재기(흐림 없음)."""
    wh = wh or _probe_wh(path)
    A, B = [], []
    for dt in look_times(float(dur)):
        fr = _frames_at(path, float(t0) + dt, PAIR_FRAMES + 1, wh)
        A.append(fr[0] if fr else None)
        B.append(fr[PAIR_FRAMES] if len(fr) > PAIR_FRAMES else (fr[-1] if fr else None))
    out = []
    for i, a in enumerate(A):
        if a is None:
            continue
        out.append(text_feats(a, B[i], far=[x for j, x in enumerate(A) if j != i]))
    return out
