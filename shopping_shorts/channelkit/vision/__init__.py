# -*- coding: utf-8 -*-
"""소재 화면 자 — 얼굴·주인공 동일성·박힌 자막. 채널과 무관한 엔진 층(슬롯 크기·좌표는 부르는 쪽이 준다).

tools/hotpeople/measure/faces_text.py(2026-09-28, 원본 9편·v3 실측 자)를 그대로 옮긴 것이다 — 같은 모델·같은 문턱.
  얼굴  : YuNet(facelib_cv, 점수 0.7, 두 배율)                          ← 동봉 facelib_cv.py (MIT, LICENSE-YUNET)
  동일성: SFace 임베딩(cv2.FaceRecognizerSF) · alignCrop 은 YuNet 원시 행 ← 랜드마크 0 채우면 cos=1.0(자가 아무것도 안 잼)
  글자  : PP-OCRv5 server det(글자 상자만, 인식 없음)                  ← 동봉 ocrdet.py (Apache-2.0, LICENSE-PADDLEOCR)
★동봉 두 파일은 볼케이노 framevision 팩과 **바이트 동일**(sha256 manifest 대조). 고치지 마라.
★모델(onnx)은 저장소에 없다: SHORTEM_MODELS 또는 ~/.shortem/models. 없으면 죽는다 — 조용한 폴백 금지.

그림 입력은 전부 **BGR uint8**(cv2 관례). 반환 좌표는 그림 크기 대비 0~1.
"""
import os

import numpy as np

MODELS_DIR = os.environ.get("SHORTEM_MODELS") or os.path.join(os.path.expanduser("~"), ".shortem", "models")
YUNET = "face_detection_yunet_2023mar.onnx"
SFACE = "face_recognition_sface_2021dec.onnx"
OCRDET = "ppocrv5_server_det.onnx"

# ── 자의 문턱 (faces_text.py 와 같다 — 바꾸면 원본 9편 기준표 §19 숫자와 더는 같은 자가 아니다) ─────────
FACE_SCORE = 0.7            # YuNet 점수(두 배율). framevision 기본 — 키아누15 357장 Vision 대조로 정한 값
EMBED_SCORE = 0.5           # 임베딩용 원시 행 검출 문턱(faces_text.embed 와 같다)
COS_SAME = 0.363            # SFace 코사인 동일 문턱(OpenCV 기본값)
COS_OTHER = 0.20            # 이 아래면 "다른 사람". 0.20~0.363 은 "애매"(v3 실측: 컷6 0.30·컷24 0.235)
JUDGE_H = 0.20              # 판정 가능 얼굴 = 높이 ≥ 크롭 20%. v3 실측: 0.2 미만은 주인공도 cos −0.1~0.1
# 자막꼴 박힌 글자(같은 줄 낱말 상자를 합친 뒤) — 점수판·스폰서 보드(원본 80% 컷에 글자)와 가르는 자
SUB_ROW_GAP = 0.06          # 낱말 상자 사이 가로 간격 < 폭 6% 면 같은 줄
SUB_CY_MIN = 0.60           # 줄 중심 y ≥ 60% (아래 40%)
SUB_CX_TOL = 0.20           # 줄 중심 x 가 가운데 ±20%
SUB_W_MIN = 0.35            # 합친 폭 ≥ 35%
SUB_H_RANGE = (0.03, 0.13)  # 줄 높이 3~13%
SUB_MIN_WORDS = 2           # 낱말 상자 2개 이상(코트 바닥 'TOTAL' 한 덩어리는 제외, v3 컷10)

WHO_MAIN, WHO_OTHER, WHO_UNSURE, WHO_SMALL, WHO_NONE = "주인공", "다른사람", "애매", "판정불가(작음)", "얼굴없음"

_state = {}


def model(name):
    p = os.path.join(MODELS_DIR, name)
    if not os.path.isfile(p):
        raise RuntimeError(f"vision: 모델 없음 {p} — SHORTEM_MODELS 또는 ~/.shortem/models 에 {name} 을 둬라")
    return p


def models_missing():
    """setup 단계 점검용 — 없는 모델 경로 목록."""
    return [os.path.join(MODELS_DIR, n) for n in (YUNET, SFACE, OCRDET) if not os.path.isfile(os.path.join(MODELS_DIR, n))]


def _facelib():
    if "facelib" not in _state:
        os.environ.setdefault("MOON_YUNET", model(YUNET))
        from . import facelib_cv
        _state["facelib"] = facelib_cv
    return _state["facelib"]


def _rec():
    if "rec" not in _state:
        import cv2
        _state["rec"] = cv2.FaceRecognizerSF.create(model(SFACE), "")
    return _state["rec"]


def _ocr():
    if "ocr" not in _state:
        from . import ocrdet
        _state["ocr"] = ocrdet.Detector(model(OCRDET))
    return _state["ocr"]


def faces(bgr, score=FACE_SCORE):
    """→ [{x,y,w,h,conf}] 정규화(0~1). facelib_cv.faces(path) 와 같은 계산을 배열에 한다(두 배율 합집합 + IoU 0.4 NMS).
    ★facelib_cv.faces 는 파일 경로만 받는다 — 같은 내부 함수(_detect_norm·_iou)를 같은 순서로 부른다.
      같은 답인지는 test_vision_faces_same_as_facelib_path 가 잰다."""
    import cv2
    fl = _facelib()
    H, W = bgr.shape[:2]
    if H < 2 or W < 2:
        return []
    found = fl._detect_norm(bgr, score)
    if max(W, H) > fl.SMALL_SIDE * 1.25:
        s = fl.SMALL_SIDE / max(W, H)
        small = cv2.resize(bgr, (max(2, int(round(W * s))), max(2, int(round(H * s)))), interpolation=cv2.INTER_AREA)
        found += fl._detect_norm(small, score)
    found.sort(key=lambda f: -f["conf"])
    keep = []
    for f in found:
        if all(fl._iou(f, k) < 0.4 for k in keep):
            keep.append(f)
    return [dict(x=round(f["x"], 4), y=round(f["y"], 4), w=round(f["w"], 4), h=round(f["h"], 4), conf=round(f["conf"], 3))
            for f in keep]


def biggest(fs):
    return max(fs, key=lambda q: q["w"] * q["h"]) if fs else None


def _raw_rows(bgr):
    import cv2
    H, W = bgr.shape[:2]
    key = ("yn", W, H)
    if key not in _state:
        _state[key] = cv2.FaceDetectorYN.create(model(YUNET), "", (W, H), EMBED_SCORE, 0.3, 5000)
    _, res = _state[key].detect(bgr)
    return res


def embedding(bgr, face, raw=None):
    """SFace 임베딩(128). face = faces()의 한 원소. alignCrop 은 YuNet 원시 행(랜드마크 5점)이 필요해
    그림을 한 번 더 검출하고 face 와 중심이 가장 가까운 행을 쓴다(faces_text.embed 와 같다). 행이 없으면 None."""
    H, W = bgr.shape[:2]
    res = _raw_rows(bgr) if raw is None else raw
    if res is None or len(res) == 0:
        return None
    fx, fy = face["x"] * W + face["w"] * W / 2, face["y"] * H + face["h"] * H / 2
    row = min(res, key=lambda r: (r[0] + r[2] / 2 - fx) ** 2 + (r[1] + r[3] / 2 - fy) ** 2)
    rec = _rec()
    return rec.feature(rec.alignCrop(bgr, row)).flatten().astype(np.float32)


def cos(a, b):
    """SFace 코사인(cv2.FaceRecognizerSF_FR_COSINE 과 같다 = 내적/노름곱)."""
    a, b = np.asarray(a, np.float32).ravel(), np.asarray(b, np.float32).ravel()
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def protagonist_embedding(embs, groups=None):
    """주인공 = 다른 얼굴과 가장 많이 "같다"(cos ≥ COS_SAME)고 판정되는 얼굴(짝별 코사인, 중심 평균 없음).
    → (index, embedding, 짝 수) 또는 (None, None, 0). 짝 0 이어도 첫 얼굴을 돌려준다(faces_text 와 같다) —
      지지가 없는 주인공을 쓸지는 부르는 쪽이 짝 수로 정한다(소스 자는 0이면 멈춘다).

    groups: 얼굴마다 출처(영상 id 등). 주면 **서로 다른 출처 몇 개에서 짝이 나오나**를 먼저 세고 짝 수로 동점을 가른다.
    ★왜: 토크쇼 한 편에 진행자 얼굴이 12분 내내 나오면 짝 수로는 진행자가 이긴다(우상혁 v001 소스 b_EPLebN4xU).
      이름으로 검색한 여러 영상에 **공통으로** 나오는 얼굴이 주인공이다. 한 영상 안(faces_text)에서는 groups=None.
    ★첫 판(중심 평균 탐욕 군집)은 v3 컷23(다른 사람 메달)을 주인공으로 묶었다 — 그래서 짝별이다."""
    if not len(embs):
        return None, None, 0
    E = np.asarray(embs, np.float32)
    E = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-12)
    S = (E @ E.T) >= COS_SAME
    np.fill_diagonal(S, False)
    n_same = S.sum(axis=1)
    if groups is None:
        score = [(int(n_same[k]),) for k in range(len(E))]
    else:
        g = np.asarray(groups)
        score = [(len(set(g[S[k]].tolist()) - {g[k]}), int(n_same[k])) for k in range(len(E))]
    i = max(range(len(E)), key=lambda k: score[k])        # 동점이면 앞 번호(faces_text 의 max(dict) 와 같다)
    return i, np.asarray(embs[i], np.float32), int(n_same[i])


def who(face, emb, anchor):
    """한 크롭의 가장 큰 얼굴 → 주인공/다른사람/애매/판정불가(작음)/얼굴없음. ★이 판정은 여기 하나(faces_text 와 같은 순서)."""
    if not face:
        return WHO_NONE
    if face["h"] < JUDGE_H:
        return WHO_SMALL
    if emb is None or anchor is None:
        return WHO_UNSURE
    c = cos(anchor, emb)
    if c >= COS_SAME:
        return WHO_MAIN
    if c < COS_OTHER:
        return WHO_OTHER
    return WHO_UNSURE


def _merge_rows(boxes, W):
    """PP-OCR 은 "완전히 / 망가져 / 버렸죠"를 세 상자로 준다(v3 컷1) — 같은 줄의 낱말 상자를 합친다."""
    rows = []
    for b in sorted(boxes, key=lambda b: (b[1], b[0])):
        for r in rows:
            gap = max(b[0] - r["x1"], r["x0"] - b[2]) / W        # 양쪽 방향 간격(정렬이 y 우선이라 왼쪽 상자가 나중에 올 수 있다)
            if min(r["y1"], b[3]) - max(r["y0"], b[1]) > 0.5 * min(r["y1"] - r["y0"], b[3] - b[1]) and gap < SUB_ROW_GAP:
                r["x0"] = min(r["x0"], b[0]); r["x1"] = max(r["x1"], b[2])     # ★x0도 갱신 — 빠뜨리면 폭이 0.17로 나왔다
                r["y0"] = min(r["y0"], b[1]); r["y1"] = max(r["y1"], b[3]); r["n"] += 1
                break
        else:
            rows.append({"x0": b[0], "x1": b[2], "y0": b[1], "y1": b[3], "n": 1})
    return rows


def _sub_like(r, W, H):
    bw, bh = (r["x1"] - r["x0"]) / W, (r["y1"] - r["y0"]) / H
    cx, cy = ((r["x0"] + r["x1"]) / 2) / W, ((r["y0"] + r["y1"]) / 2) / H
    return (cy >= SUB_CY_MIN and abs(cx - 0.5) <= SUB_CX_TOL and bw >= SUB_W_MIN
            and SUB_H_RANGE[0] <= bh <= SUB_H_RANGE[1] and r["n"] >= SUB_MIN_WORDS)


def text_boxes(bgr):
    """PP-OCR det 글자 상자 [(x0,y0,x1,y1)] 픽셀."""
    return _ocr().boxes(np.ascontiguousarray(bgr[:, :, ::-1]))


def subtitle_like_text(bgr, boxes=None):
    """자막처럼 생긴 박힌 글자 줄 목록(합친 줄 dict). 빈 목록 = 없음."""
    H, W = bgr.shape[:2]
    tb = text_boxes(bgr) if boxes is None else boxes
    return [r for r in _merge_rows(tb, W) if _sub_like(r, W, H)]


def look(bgr, text=True):
    """크롭 한 장 → {face, face_h, cx_off, face_cx, emb, sub_like, text_boxes}. who 는 anchor 가 정해진 뒤 who()로.
    face_cx = 가장 큰 얼굴 중심 x(0~1), cx_off = face_cx − 0.5."""
    fs = faces(bgr)
    big = biggest(fs)
    emb = embedding(bgr, big) if big else None
    out = {"face": bool(big), "face_h": round(big["h"], 3) if big else None,
           "face_cx": round(big["x"] + big["w"] / 2, 4) if big else None,
           "cx_off": round(big["x"] + big["w"] / 2 - 0.5, 3) if big else None, "emb": emb, "box": big}
    if text:
        tb = text_boxes(bgr)
        out["text_boxes"] = len(tb)
        out["sub_like"] = len(subtitle_like_text(bgr, tb))
    return out


def faces_all(bgr, min_h=JUDGE_H):
    """판정 가능한(높이 ≥ min_h) 얼굴 전부의 (face, emb) — 소스 자(한 프레임에 여럿)."""
    fs = [f for f in faces(bgr) if f["h"] >= min_h]
    if not fs:
        return []
    raw = _raw_rows(bgr)
    return [(f, embedding(bgr, f, raw)) for f in fs]
