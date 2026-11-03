# -*- coding: utf-8 -*-
"""facelib_cv.py — **OpenCV YuNet 얼굴 상자**. facelib.py(Apple Vision)와 같은 계약 · 맥/윈도우 공통.

■ 왜 (2026-09-02 · 15-201 수강생 윈도우 이식)
    facelib.py 는 pyobjc(Quartz/Vision)만으로 돈다 — 윈도우에서는 import 자체가 안 된다.
    YuNet(opencv_zoo face_detection_yunet_2023mar.onnx · 233KB)은 cv2 에 들어 있는 검출기라
    opencv-python 하나면 어디서나 같은 답을 낸다. 모델에게 좌표를 묻지 않는다(15-30)는 원칙은 그대로다.
    ★어느 쪽을 쓰는지는 pyvision.script("face") 가 정한다 — 맥+Vision 이면 facelib.py, 아니면(윈도우/리눅스 ·
      Vision 파이썬 없음 · MOON_FACE_ENGINE=cv) 이 파일. 부르는 쪽(harvest_hero/screencheck/fxplace)은 계약이 같아 고칠 것이 없다.

■ 계약 (facelib.py 와 동일)
    쓰기:  python facelib_cv.py <이미지…>
    출력:  이미지마다 JSON 한 줄  {"file": <basename>, "faces": [{x,y,w,h,conf}…]}
           · 좌표는 화면 정규화(0~1) · 좌상단 원점 · 소수 4자리 · conf 소수 3자리
           · 못 연 파일은 {"file":…, "faces": [], "error": "open_failed"}  (15-170c)
    ★차이 1: file 은 os.path.basename — 원본은 p.split("/")[-1] 이라 윈도우 역슬래시 경로에서
             부르는 쪽(os.path.basename 으로 대조)과 어긋난다. 여기서는 어긋나지 않는다.
    ★차이 2: 서브프로세스가 아니라 같은 파이썬에서 import 해 faces() 를 불러도 된다(pyobjc 가 아니라 fork 걱정 없음).
    ★차이 3(실측 · WINDOWS_PORT_PLAN.md §1): 상자 규약이 Vision 과 다르다 — 폭 0.93배 · 높이 1.25배 · 중심이 6.5% 위
             (이마 위까지 잡는다). 겹침 비율이 경계값 근처에서 흔들리며, 뒤집힘은 전부 「YuNet 이 더 엄격」한 쪽이었다.
             규약 보정은 **넣지 않는다**(결정 2026-09-02 — 놓침 최소가 우선).

■ 모델 자리 (순서대로 찾는다 · 없으면 죽는다 — 조용한 폴백 금지)
    ① 환경변수 MOON_YUNET=<onnx 경로>
    ② 이 파일 옆 models/face_detection_yunet_2023mar.onnx   ← 저장소에 동봉
    ③ 이 파일 옆 face_detection_yunet_2023mar.onnx

■ 문턱
    YuNet 점수 문턱 = 환경변수 MOON_YUNET_SCORE (기본 0.7 · 두 배율).
    ★기본값의 근거: Vision(facelib.py)과 키아누15 화면검사 357장으로 대조해 정했다(WINDOWS_PORT_PLAN.md §1 —
      두 배율 0.7 이 Vision 대비 큰 얼굴 놓침 1/357 · 뒤집힘은 전부 엄격한 쪽).

실행:  python facelib_cv.py <이미지…>      → JSON 줄들
       python facelib_cv.py --selftest     → 모델 적재 · 두 배율/단일 배율 · open_failed 계약 · CLI JSON 계약
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_NAME = "face_detection_yunet_2023mar.onnx"
SCORE_DEFAULT = 0.7
NMS = 0.3
TOP_K = 500
_det = [None, None]     # (detector, (w,h))


def model_path() -> str:
    env = (os.environ.get("MOON_YUNET") or "").strip()
    cands = ([env] if env else []) + [os.path.join(HERE, "models", MODEL_NAME),
                                       os.path.join(HERE, MODEL_NAME)]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise RuntimeError("YuNet 모델(onnx)을 못 찾았다. 시도: " + " → ".join(cands)
                       + "\n   처방: https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
                       + MODEL_NAME + " 을 받아 models/ 에 두거나 MOON_YUNET=<경로>")


def _load_bgr(path: str):
    """PIL 로 연다 — cv2.imread 는 윈도우에서 한글 경로를 못 읽고(ANSI), WebP 가 .png 행세를 해도 PIL 은 연다."""
    from PIL import Image                                        # noqa: PLC0415
    try:
        with Image.open(path) as im:
            rgb = np.asarray(im.convert("RGB"))
    except (OSError, ValueError):
        return None
    return rgb[:, :, ::-1].copy()


def _detector(w: int, h: int, score: float):
    import cv2                                                   # noqa: PLC0415
    if _det[0] is None:
        # Python opens Unicode filenames on every OS; OpenCV's native filename
        # loader uses an ANSI path on Windows. Pass the model bytes through the
        # documented buffer overload so the native API never receives a path.
        # https://docs.opencv.org/4.9.0/df/d20/classcv_1_1FaceDetectorYN.html
        with open(model_path(), "rb") as model_file:
            model = np.frombuffer(model_file.read(), dtype=np.uint8)
        _det[0] = cv2.FaceDetectorYN.create(
            "onnx", model, np.empty(0, dtype=np.uint8), (w, h), score, NMS, TOP_K)
        _det[1] = (w, h)
    if _det[1] != (w, h):
        _det[0].setInputSize((w, h))
        _det[1] = (w, h)
    return _det[0]


def _detect_norm(img, thr: float) -> list:
    """한 배율에서 검출 → 정규화 상자 목록."""
    H, W = img.shape[:2]
    det = _detector(W, H, thr)
    _, res = det.detect(img)
    out = []
    for r in (res if res is not None else []):
        x, y, w, h = float(r[0]), float(r[1]), float(r[2]), float(r[3])
        conf = float(r[14])
        # 화면 밖으로 삐져나온 상자는 화면 안으로 자른다(Vision 도 0~1 안의 값만 낸다)
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(float(W), x + w), min(float(H), y + h)
        if x1 <= x0 or y1 <= y0:
            continue
        out.append(dict(x=x0 / W, y=y0 / H, w=(x1 - x0) / W, h=(y1 - y0) / H, conf=conf))
    return out


def _iou(a, b) -> float:
    ix = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    iy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    i = ix * iy
    return i / max(1e-9, a["w"] * a["h"] + b["w"] * b["h"] - i)


SMALL_SIDE = 640          # 두 번째 배율 — 긴 변을 이만큼으로 줄인 그림


def faces(path: str, score: float | None = None, multiscale: bool | None = None):
    """facelib.faces 와 같은 반환: [{x,y,w,h,conf}] (정규화 · 좌상단 원점) · 못 열면 None.

    ★두 배율(원본 + 긴 변 640) 합집합 — 키아누15 실측: 원본 한 배율만 보면 **화면을 가득 채운 얼굴**
      (Vision h=0.72 · 0.35 · 0.32 …)을 YuNet 이 0.35~0.58 점수로 놓쳤다. 줄인 그림에서 다시 보면 잡힌다.
      MOON_YUNET_MULTISCALE=0 이면 원본 한 배율만 본다(실험용).
    """
    import cv2                                                   # noqa: PLC0415
    img = _load_bgr(path)
    if img is None:
        return None
    H, W = img.shape[:2]
    if H < 2 or W < 2:
        return None
    thr = float(score if score is not None else os.environ.get("MOON_YUNET_SCORE", SCORE_DEFAULT))
    ms = multiscale if multiscale is not None else (os.environ.get("MOON_YUNET_MULTISCALE", "1") != "0")
    found = _detect_norm(img, thr)
    if ms and max(W, H) > SMALL_SIDE * 1.25:
        s = SMALL_SIDE / max(W, H)
        small = cv2.resize(img, (max(2, int(round(W * s))), max(2, int(round(H * s)))), interpolation=cv2.INTER_AREA)
        found += _detect_norm(small, thr)
    # 두 배율이 같은 얼굴을 낸 것은 점수 높은 쪽만 남긴다(IoU 0.4 · 탐욕 NMS)
    found.sort(key=lambda f: -f["conf"])
    keep = []
    for f in found:
        if all(_iou(f, k) < 0.4 for k in keep):
            keep.append(f)
    return [dict(x=round(f["x"], 4), y=round(f["y"], 4), w=round(f["w"], 4), h=round(f["h"], 4),
                 conf=round(f["conf"], 3)) for f in keep]


def _record(p: str) -> dict:
    """CLI 한 줄의 내용. file 은 os.path.basename(★차이 1)."""
    fs = faces(p)
    d = {"file": os.path.basename(p), "faces": fs or []}
    if fs is None:
        d["error"] = "open_failed"
    return d


def selftest() -> int:
    """싸게 잰다 — 모델이 실재하고 적재되며, 두 배율(1920×1080)·단일 배율(320×180) 그림에서 예외 없이 목록을 내고,
    없는 파일은 None(open_failed), CLI 는 이미지마다 JSON 한 줄을 낸다. 합성 그림엔 얼굴이 없으므로 「검출 수」는 재지 않는다
    (실제 얼굴 정확도는 WINDOWS_PORT_PLAN.md §1 의 357장 대조가 정본이다). 한글 파일 이름으로 PIL 열기까지 본다."""
    import subprocess                                            # noqa: PLC0415
    import tempfile                                              # noqa: PLC0415
    from PIL import Image, ImageDraw                             # noqa: PLC0415
    mp = model_path()                                            # 없으면 여기서 RuntimeError — 조용히 넘기지 않는다
    with tempfile.TemporaryDirectory() as td:
        big = os.path.join(td, "합성_두배율_1080.png")
        im = Image.new("RGB", (1920, 1080), (30, 30, 30))
        dr = ImageDraw.Draw(im)
        dr.rectangle((700, 250, 1220, 830), fill=(210, 170, 140))
        dr.ellipse((850, 400, 930, 480), fill=(40, 30, 30)); dr.ellipse((990, 400, 1070, 480), fill=(40, 30, 30))
        dr.rectangle((870, 640, 1050, 680), fill=(120, 50, 50))
        im.save(big)
        small = os.path.join(td, "합성_단일_180.png")
        Image.new("RGB", (320, 180), (200, 200, 200)).save(small)
        missing = os.path.join(td, "없는파일.png")
        f_big = faces(big)
        f_small = faces(small)
        assert isinstance(f_big, list) and isinstance(f_small, list), (f_big, f_small)
        for f in f_big + f_small:
            assert set(f) == {"x", "y", "w", "h", "conf"} and 0 <= f["x"] <= 1 and 0 <= f["y"] <= 1, f
        assert faces(missing) is None, "없는 파일은 None(open_failed) 이어야 한다"
        r = subprocess.run([sys.executable, os.path.abspath(__file__), big, missing],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert r.returncode == 0, f"CLI rc={r.returncode} stderr={r.stderr[-400:]}"
        lines = [json.loads(ln) for ln in r.stdout.splitlines() if ln.strip()]
        assert len(lines) == 2, f"JSON 줄 수 {len(lines)} != 2"
        assert lines[0]["file"] == os.path.basename(big) and "error" not in lines[0], lines[0]
        assert lines[1]["file"] == os.path.basename(missing) and lines[1].get("error") == "open_failed", lines[1]
    print(f"✓ facelib_cv 자체시험 통과 — 모델 {os.path.relpath(mp, HERE)} · 두 배율 {len(f_big)}상자 · 단일 배율 "
          f"{len(f_small)}상자 · open_failed 계약 · CLI JSON 2줄 (문턱 {os.environ.get('MOON_YUNET_SCORE', SCORE_DEFAULT)})")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    for p in sys.argv[1:]:
        print(json.dumps(_record(p), ensure_ascii=False))
    sys.stdout.flush()
