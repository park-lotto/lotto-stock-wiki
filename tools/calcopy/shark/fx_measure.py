# -*- coding: utf-8 -*-
"""샥탬스토리 꾸밈 실측 — 얼굴 검출(YuNet, 무료·로컬)·빨간 원 맞추기(링 피팅)·원↔얼굴 관계 (관제 097, 2026-10-18).

사장님 10-18 "빨간원 그리는게 너무 안맞는다 … 정확하게". 원 자리를 사람이 눈대중(how=hand)으로 적던 것이 뿌리 →
원 자리는 얼굴 검출로 계산한다(fx_place.circle_for_face 가 주인, 비율은 rules.json effects.red_circle.face).
이 파일은 재는 도구만(판단 없음): faces() · ring() · scan() · relation().

    PYTHONUTF8=1 py tools/calcopy/shark/fx_measure.py bench <id…> <out.json>          # 벤치 mp4 전체 30fps 원 구간 + 같은 프레임 얼굴
    PYTHONUTF8=1 py tools/calcopy/shark/fx_measure.py video <mp4> [--to 3]            # 완성본 원-얼굴 관계(검사용)
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCH_DIR = Path("C:/숏템_칼카피/foreignshowshow/mp4")
WIN = (0, 434, 1080, 1052)          # 창 [x, y, w, h] (벤치 8/8)
CAP_BAND = (880, 1050)              # 자막 띠 — 원 픽셀에서 뺀다(빨강 자막 글자가 섞이므로)
RED = np.array([247, 42, 48])
MODEL_CANDS = [os.environ.get("MOON_YUNET", ""), str(Path.home() / ".shortem/models/face_detection_yunet_2023mar.onnx"),
               str(Path.home() / ".brainbulb/models/face_detection_yunet_2023mar.onnx"),
               str(ROOT / "shopping_shorts/channelkit/vision/models/face_detection_yunet_2023mar.onnx")]
_det = {}


# ── 얼굴 ─────────────────────────────────────────────────────────────
def _detector(w, h):
    import cv2
    if "d" not in _det:
        p = next((c for c in MODEL_CANDS if c and os.path.exists(c)), None)
        if not p:
            raise RuntimeError(f"YuNet onnx 없음: {MODEL_CANDS}")
        buf = np.frombuffer(Path(p).read_bytes(), dtype=np.uint8)
        _det["d"] = cv2.FaceDetectorYN.create("onnx", buf, np.empty(0, dtype=np.uint8), (w, h), 0.6, 0.3, 50)
        _det["wh"] = (w, h)
    if _det["wh"] != (w, h):
        _det["d"].setInputSize((w, h)); _det["wh"] = (w, h)
    return _det["d"]


def faces(rgb: np.ndarray, score: float = 0.6) -> list[dict]:
    """얼굴 상자(픽셀) — YuNet 상자는 이마 위~턱(머리카락·정수리 빠짐). eye = 두 눈 가운데, nose = 코끝."""
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    H, W = bgr.shape[:2]
    out = []
    for sc in (1.0, 0.5):
        im = bgr if sc == 1.0 else bgr[::2, ::2].copy()
        d = _detector(im.shape[1], im.shape[0])
        _, res = d.detect(im)
        for r in (res if res is not None else []):
            if float(r[14]) < score:
                continue
            v = [float(x) / sc for x in r[:14]]
            x, y, w, h = v[:4]
            f = {"x": x, "y": y, "w": w, "h": h, "cx": x + w / 2, "cy": y + h / 2, "conf": round(float(r[14]), 3),
                 "eye": [(v[4] + v[6]) / 2, (v[5] + v[7]) / 2], "nose": [v[8], v[9]], "mouth": [(v[10] + v[12]) / 2, (v[11] + v[13]) / 2]}
            if not any(abs(f["cx"] - g["cx"]) < 0.3 * g["w"] and abs(f["cy"] - g["cy"]) < 0.3 * g["h"] for g in out):
                out.append(f)
        if out:
            break
    return sorted(out, key=lambda f: -f["w"] * f["h"])


# ── 사람 상자 (NanoDet-Plus, opencv_zoo object_detection_nanodet_2022nov.onnx · COCO 'person' — 무료·로컬, onnxruntime) ──
NANODET_CANDS = [os.environ.get("NANODET_ONNX", ""), str(Path.home() / ".shortem/models/dl/nanodet.onnx"),
                 str(Path.home() / ".shortem/models/object_detection_nanodet_2022nov.onnx")]


def _nanodet():
    if "n" not in _det:
        import onnxruntime as ort
        p = next((c for c in NANODET_CANDS if c and os.path.exists(c)), None)
        if not p:
            raise RuntimeError("NanoDet onnx 없음 — https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_nanodet/"
                               "object_detection_nanodet_2022nov.onnx 를 ~/.shortem/models/dl/nanodet.onnx 로")
        o = ort.SessionOptions(); o.log_severity_level = 3
        _det["n"] = ort.InferenceSession(p, o)
    return _det["n"]


def persons(rgb: np.ndarray, score: float = 0.35) -> list[dict]:
    """사람 상자(픽셀) [{x0,y0,x1,y1,conf}] 큰 것부터. 얼굴이 안 보이는(허리 숙인·뒤돈) 사람도 잡는다."""
    import cv2
    H, W = rgb.shape[:2]
    S = 416
    r = min(S / W, S / H)
    nw, nh = int(round(W * r)), int(round(H * r))
    img = np.zeros((S, S, 3), np.float32)
    img[:nh, :nw] = cv2.resize(rgb[:, :, ::-1], (nw, nh)).astype(np.float32)
    img = (img - np.array([103.53, 116.28, 123.675], np.float32)) / np.array([57.375, 57.12, 58.395], np.float32)
    sess = _nanodet()
    outs = sess.run(None, {sess.get_inputs()[0].name: img.transpose(2, 0, 1)[None]})
    boxes, confs = [], []
    for cls, reg, st in ((outs[0], outs[3], 8), (outs[1], outs[4], 16), (outs[2], outs[5], 32)):
        n = S // st
        c = cls[0][:, 0]
        keep = np.nonzero(c > score)[0]
        if not len(keep):
            continue
        d = reg[0][keep].reshape(-1, 4, 8)
        d = np.exp(d - d.max(axis=2, keepdims=True)); d /= d.sum(axis=2, keepdims=True)
        dist = (d * np.arange(8)).sum(axis=2) * st
        cy, cx = (keep // n) * st, (keep % n) * st
        b = np.stack([cx - dist[:, 0], cy - dist[:, 1], cx + dist[:, 2], cy + dist[:, 3]], axis=1) / r
        boxes += b.tolist(); confs += c[keep].tolist()
    if not boxes:
        return []
    idx = cv2.dnn.NMSBoxes([[b[0], b[1], b[2] - b[0], b[3] - b[1]] for b in boxes], confs, score, 0.5)
    out = [{"x0": max(0.0, boxes[i][0]), "y0": max(0.0, boxes[i][1]), "x1": min(float(W), boxes[i][2]), "y1": min(float(H), boxes[i][3]),
            "conf": round(confs[i], 3)} for i in np.array(idx).ravel()]
    return sorted(out, key=lambda b: -(b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))


# ── 빨간 원 ───────────────────────────────────────────────────────────
def red_mask(rgb: np.ndarray, tol: int = 75) -> np.ndarray:
    a = rgb.astype(np.int16)
    # 그래픽 빨강은 채도가 꽉 찬 색(실선 [247,42,48]·점선 [251,25,27]) — 주황빨강 옷(QMJ 228,64,81)·빨강 자막(235,78,79)은 빠지게
    m = (np.abs(a - RED).sum(axis=2) < tol) & (a[..., 0] > 225) & (a[..., 1] < 58) & (a[..., 2] < 64) & (a[..., 0] - a[..., 1] > 180)
    return m


def _fit(xs, ys):
    A = np.c_[2 * xs, 2 * ys, np.ones(len(xs))]
    b = xs ** 2 + ys ** 2
    c, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = c[0], c[1]
    return cx, cy, math.sqrt(max(1.0, c[2] + cx * cx + cy * cy))


def ring(rgb: np.ndarray, win=WIN, tol: int = 75) -> dict | None:
    """창 안 빨간 고리 하나를 맞춘다 → {cx, cy(완성본 좌표), r(선 가운데), r_out, r_in, stroke, cover(각도 덮음), n, color}. 고리 아니면 None."""
    x0, y0, w, h = win
    sub = rgb[y0:y0 + h, x0:x0 + w]
    m = red_mask(sub, tol)
    m[CAP_BAND[0] - y0:CAP_BAND[1] - y0] = False
    ys, xs = np.nonzero(m)
    if len(xs) < 400:
        return None
    xs, ys = xs.astype(float), ys.astype(float)
    keep = np.ones(len(xs), bool)
    for _ in range(6):
        cx, cy, r = _fit(xs[keep], ys[keep])
        d = np.hypot(xs - cx, ys - cy)
        res = np.abs(d - r)
        band = max(10.0, np.percentile(res[keep], 80) * 2.0)
        nk = res < band
        if nk.sum() < 300 or (nk == keep).all():
            keep = nk; break
        keep = nk
    if keep.sum() < 300:
        return None
    cx, cy, r = _fit(xs[keep], ys[keep])
    d = np.hypot(xs[keep] - cx, ys[keep] - cy)
    ang = (np.degrees(np.arctan2(ys[keep] - cy, xs[keep] - cx)) + 360) % 360
    bins = np.bincount((ang // 5).astype(int), minlength=72)[:72]
    # 자막 띠로 가려진 각도는 덮음 계산에서 뺀다
    th = np.radians(np.arange(72) * 5 + 2.5)
    yy = cy + r * np.sin(th) + y0
    vis = ~((yy >= CAP_BAND[0]) & (yy < CAP_BAND[1]))
    vis &= (cx + r * np.cos(th) >= 0) & (cx + r * np.cos(th) < w) & (cy + r * np.sin(th) >= 0) & (cy + r * np.sin(th) < h)
    cover = float((bins[vis] > 2).mean()) if vis.any() else 0.0
    r_out, r_in = float(np.percentile(d, 97)), float(np.percentile(d, 3))
    thick = r_out - r_in
    if r < 60 or thick > 0.45 * r or thick > 45 or cover < 0.25 or keep.sum() < 2 * math.pi * r * 3 * 0.25:
        return None
    col = sub[ys[keep].astype(int), xs[keep].astype(int)]
    return {"cx": round(cx + x0, 1), "cy": round(cy + y0, 1), "r": round(r, 1), "r_out": round(r_out, 1), "r_in": round(r_in, 1),
            "stroke": round(thick, 1), "cover": round(cover, 2), "n": int(keep.sum()), "color": [int(v) for v in np.median(col, axis=0)],
            "runs": _runs(bins, vis)}


def _runs(bins, vis):
    """보이는 각도에서 점(덮인 칸) 덩어리 수 — 점선 원 점 개수 추정."""
    on = (bins > 2) & vis
    n, prev = 0, on[-1]
    for v in on:
        if v and not prev:
            n += 1
        prev = v
    return int(n)


def edge_profile(rgb: np.ndarray, R: dict, n_ang: int = 48) -> dict:
    """고리 바깥쪽 지름 방향 단면 — 경계 부드러움(빨강 50%→10% 사이 px)·바깥 그림자(바깥 3~8px 밝기 − 바깥 15~25px 밝기)."""
    a = rgb.astype(float)
    red = lambda p: np.clip(((p[..., 0] - (p[..., 1] + p[..., 2]) / 2) / 200.0), 0, 1)
    soft, shadow_out, shadow_in = [], [], []
    for k in range(n_ang):
        t = 2 * math.pi * k / n_ang
        pts = []
        for s in np.arange(-12, 26, 1.0):
            x = R["cx"] + (R["r_out"] + s) * math.cos(t); y = R["cy"] + (R["r_out"] + s) * math.sin(t)
            if not (0 <= x < rgb.shape[1] - 1 and WIN[1] <= y < WIN[1] + WIN[3] - 1) or CAP_BAND[0] - 30 <= y <= CAP_BAND[1] + 30:
                pts = None; break
            pts.append(a[int(y), int(x)])
        if pts is None:
            continue
        p = np.array(pts)
        rr = red(p)
        inside = rr[:12].max()
        if inside < 0.5:
            continue
        lum = p.mean(axis=1)
        i50 = next((i for i in range(10, len(rr)) if rr[i] < 0.5 * inside), None)
        i10 = next((i for i in range(10, len(rr)) if rr[i] < 0.1 * inside), None)
        if i50 is not None and i10 is not None:
            soft.append(i10 - i50)
            shadow_out.append(lum[i10 + 1:i10 + 6].mean() - lum[i10 + 14:i10 + 24].mean() if i10 + 24 < len(lum) else np.nan)
    so = [x for x in shadow_out if x == x]
    return {"soft_px": round(float(np.median(soft)), 1) if soft else None,
            "shadow_out_dl": round(float(np.median(so)), 1) if so else None, "n": len(soft)}


# ── 원 ↔ 얼굴 ─────────────────────────────────────────────────────────
def relation(R: dict, F: dict) -> dict:
    """원(R)과 얼굴 상자(F) 관계 — 전부 얼굴 높이(fh) 단위. inside = 얼굴 상자 내접 타원 16점 중 원(선 안쪽) 안 비율(가로 ±, 위 −0.35fh 정수리까지 따로)."""
    fh, fw = F["h"], F["w"]
    dx, dy = (R["cx"] - F["cx"]) / fh, (R["cy"] - F["cy"]) / fh
    ri = R.get("r_in") or R["r"]
    ell = [(F["cx"] + fw / 2 * math.cos(a), F["cy"] + fh / 2 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
    inside = sum(math.hypot(x - R["cx"], y - R["cy"]) <= ri for x, y in ell) / len(ell)   # 얼굴 = 상자에 내접한 타원 16점
    crown = (F["cx"], F["y"] - 0.35 * fh)      # 정수리 추정(YuNet 상자 위 끝은 이마 — 머리 전체 높이 ≈ 1.35~1.5 fh)
    chin = (F["cx"], F["y"] + fh)
    dx, dy = float(dx), float(dy)
    return {"dx_fh": round(dx, 3), "dy_fh": round(dy, 3), "off_fh": round(math.hypot(dx, dy), 3), "r_fh": round(R["r"] / fh, 3),
            "face_w_win": round(fw / WIN[2], 3), "face_h_win": round(fh / WIN[2], 3), "face_inside": inside,
            "crown_in": bool(math.hypot(crown[0] - R["cx"], crown[1] - R["cy"]) <= ri), "chin_in": bool(math.hypot(chin[0] - R["cx"], chin[1] - R["cy"]) <= ri),
            "eye_dy_fh": round(float(R["cy"] - F["eye"][1]) / fh, 3), "nose_dy_fh": round(float(R["cy"] - F["nose"][1]) / fh, 3),
            "crown_gap_fh": round(float(R["cy"] - ri - (F["y"] - 0.35 * fh)) / fh, 3), "chin_gap_fh": round(float(R["cy"] + ri - (F["y"] + fh)) / fh, 3)}


def face_near(R: dict, fs: list[dict]) -> dict | None:
    """원 중심에 가장 가까운 얼굴(원 안쪽에 상자 중심이 있는 것 우선)."""
    if not fs:
        return None
    return min(fs, key=lambda f: math.hypot(f["cx"] - R["cx"], f["cy"] - R["cy"]) / max(1.0, R["r"]))


# ── 영상 훑기 ──────────────────────────────────────────────────────────
def frames(src, fps=30, scale=1.0, ss=0.0, to=None):
    W, H = int(1080 * scale), int(1920 * scale)
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{ss:.3f}", "-i", str(src)] + (["-t", f"{to - ss:.3f}"] if to else []) + \
          ["-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    k = 0
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        yield ss + k / fps, np.frombuffer(b, np.uint8).reshape(H, W, 3)
        k += 1
    p.wait()


def scan(src, to=None, ss=0.0) -> list[dict]:
    """30fps 프레임마다 빨간 고리(실선·점선) + 같은 프레임 얼굴. 원 없는 프레임은 건너뜀."""
    rows = []
    for t, a in frames(src, 30, 1.0, ss, to):
        m = red_mask(a[WIN[1]:WIN[1] + WIN[3]:4, ::4])
        if m.sum() < 30:
            continue
        R = ring(a)
        if not R:
            continue
        fs = faces(a)
        F = face_near(R, fs)
        R = {k: (float(v) if isinstance(v, np.floating) else v) for k, v in R.items()}
        row = {"t": round(t, 3), "ring": R, "face": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in F.items()} if F else None}
        if F:
            row["rel"] = relation(R, F)
        rows.append(row)
    return rows


def segments(rows: list[dict], gap=0.05) -> list[dict]:
    """프레임 줄 → 구간(실선 cover≥0.8 / 점선)."""
    segs = []
    for r in rows:
        kind = "solid" if r["ring"]["cover"] >= 0.8 else "dashed"
        if segs and segs[-1]["kind"] == kind and r["t"] - segs[-1]["t1"] <= 1 / 30 + gap:
            segs[-1]["t1"] = r["t"]; segs[-1]["rows"].append(r)
        else:
            segs.append({"kind": kind, "t0": r["t"], "t1": r["t"], "rows": [r]})
    return [s for s in segs if len(s["rows"]) >= 3]


def summarize(seg: dict) -> dict:
    rs = seg["rows"]
    med = lambda key, sub="ring": round(float(np.median([r[sub][key] for r in rs if r.get(sub) and r[sub].get(key) is not None])), 2)
    out = {"kind": seg["kind"], "t0": seg["t0"], "t1": seg["t1"], "frames": len(rs), "cx": med("cx"), "cy": med("cy"), "r": med("r"),
           "stroke": med("stroke"), "cover": med("cover"), "runs": int(np.median([r["ring"]["runs"] for r in rs])),
           "color": [int(np.median([r["ring"]["color"][i] for r in rs])) for i in range(3)],
           "move_px": round(float(max(math.hypot(r["ring"]["cx"] - rs[0]["ring"]["cx"], r["ring"]["cy"] - rs[0]["ring"]["cy"]) for r in rs)), 1),
           "r_first_last": [rs[0]["ring"]["r"], rs[-1]["ring"]["r"]]}
    rel = [r["rel"] for r in rs if r.get("rel")]
    if rel:
        out["rel"] = {k: round(float(np.median([x[k] for x in rel])), 3) for k in rel[0] if isinstance(rel[0][k], (int, float)) and not isinstance(rel[0][k], bool)}
        out["rel"]["crown_in"] = round(sum(x["crown_in"] for x in rel) / len(rel), 2)
        out["rel"]["chin_in"] = round(sum(x["chin_in"] for x in rel) / len(rel), 2)
        out["face_frames"] = len(rel)
    return out


def main():
    cmd = sys.argv[1]
    if cmd == "bench":
        ids, dst = sys.argv[2:-1], Path(sys.argv[-1])
        res = {}
        for i in ids:
            src = BENCH_DIR / f"{i}.mp4"
            rows = scan(src)
            segs = segments(rows)
            res[i] = {"segments": [summarize(s) for s in segs], "rows": rows}
            for s in res[i]["segments"]:
                print(i, json.dumps({k: v for k, v in s.items()}, ensure_ascii=False))
        dst.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(dst)
    elif cmd == "video":
        src = sys.argv[2]
        to = float(sys.argv[sys.argv.index("--to") + 1]) if "--to" in sys.argv else None
        for s in segments(scan(src, to)):
            print(json.dumps(summarize(s), ensure_ascii=False))


if __name__ == "__main__":
    main()
