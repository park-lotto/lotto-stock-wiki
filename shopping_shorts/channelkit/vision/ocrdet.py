#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ocrdet.py — 사장님 앱의 **DBNet 글자 검출 모델**로 자막 글자 상자를 딴다.

■ 왜 필요했나 (실사고 2026-08-16)
    `deepfont.py` 를 앱 소스 그대로 이식해 돌렸더니 10장 중 6장에서 마스크가
    **뒤집혔다.** 원인은 `otsu_with_border_orientation` 의 반전 규칙이다 —
    "테두리 평균이 127 을 넘으면 뒤집는다". 앱은 **OCR 이 딴 꽉 낀 글자 상자**를
    넣으므로 테두리가 자막 자신의 어두운 테두리라 안 뒤집힌다. 그런데 내가 넣은
    것은 **자막 띠 크롭**이라 가장자리에 밝은 영상 배경이 물려 테두리 평균이
    139·226 까지 올라갔다(실측). 그래서 글자가 배경이 되고 배경이 글자가 됐다.
    → 문턱을 손보는 게 아니라 **앱과 같은 입력을 만들어 준다.**

■ 모델·상수는 전부 앱 것 (src/ocr/det.rs · 추측 0)
    모델        native-runtime/src-tauri/models/ppocrv5_server_det.onnx
    긴변 상한   960 (DET_LIMIT_SIDE_LEN) · 한 배율을 두 축에 같이 쓴다
    보간        Lanczos3
    패딩        오른쪽·아래를 32의 배수까지 0(정규화 공간의 0)으로
    채널        RGB→**BGR 로 바꿔 넣고**, mean/std 는 **RGB 순서 숫자 그대로**
                mean [0.485,0.456,0.406] · std [0.229,0.224,0.225]
                (det.rs:229 주석 — 채널0=B 에 0.485(R 통계)를 쓴다. 학습과 같다)
    문턱        0.3 (det.rs:128 threshold) · 최소면적 10

■ unclip 은 **한다** (처음엔 뺐다가 자체 시험에 걸려 넣었다)
    처음에 "우리는 사각형 하나만 있으면 되니 확률지도 문턱만 넘으면 된다"고
    적고 unclip 을 생략했다. 자체 시험에서 **높이 56 짜리 글자에 29 짜리 상자**가
    나왔다 — DBNet 은 글자 영역을 **줄여서** 예측하기 때문이다. 그 상자를 그대로
    쓰면 글자 위아래가 잘려 글꼴 판정이 망가진다. 그래서 앱 의존성
    (`pure-onnx-ocr` postprocessing.rs:462) 의 거리 공식 **(면적/둘레)×1.5** 를
    그대로 넣었다. 넣은 뒤 (55,68)~(383,133) 으로 글자를 감쌌다.
    다각형 오프셋 대신 사각형을 네 변으로 미는데, Round 조인의 민코프스키 합은
    바깥 사각형을 각 변마다 정확히 그 거리만큼 키우므로 결과가 같다.

실행:  python3 ocrdet.py --selftest
       python3 ocrdet.py <이미지…>
"""
from __future__ import annotations

import argparse
import os

import cv2
import numpy as np
from PIL import Image

# ★2026-08-26 (15-76 F) Samsung_T5 이전 — 원본 /Volumes/Samsung_T5/all-in-one-production/native-runtime/…
DET = ("/Volumes/SSD/#moon/자산/all-in-one-production/native-runtime/src-tauri/"
       "models/ppocrv5_server_det.onnx")
LIMIT_SIDE = 960
STRIDE = 32
MEAN = np.float32([0.485, 0.456, 0.406])
STD = np.float32([0.229, 0.224, 0.225])
THRESH = 0.3
MIN_AREA = 10
UNCLIP_RATIO = 1.5      # det.rs:139 — pure-onnx-ocr DetPostProcessorConfig


class Detector:
    def __init__(self, path: str = DET):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.iname = self.sess.get_inputs()[0].name

    def prob_map(self, rgb: np.ndarray) -> tuple[np.ndarray, float]:
        """확률지도(원본 배율 되돌리기 전)와 orig→resized 배율을 돌려준다."""
        h, w, _ = rgb.shape
        m = max(w, h)
        ratio = LIMIT_SIDE / m if m > LIMIT_SIDE else 1.0
        rw, rh = max(1, round(w * ratio)), max(1, round(h * ratio))
        im = Image.fromarray(rgb).resize((rw, rh), Image.LANCZOS)
        a = np.asarray(im, dtype=np.float32) / 255.0            # (h,w,3) RGB
        bgr = a[:, :, ::-1]                                     # → BGR
        norm = (bgr - MEAN) / STD                               # ★숫자는 RGB 순서 그대로
        pw = -(-rw // STRIDE) * STRIDE
        ph = -(-rh // STRIDE) * STRIDE
        ten = np.zeros((1, 3, ph, pw), dtype=np.float32)
        ten[0, :, :rh, :rw] = norm.transpose(2, 0, 1)
        out = self.sess.run(None, {self.iname: ten})[0]
        p = np.asarray(out).reshape(out.shape[-2], out.shape[-1])
        return p[:rh, :rw], ratio

    def boxes(self, rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
        """윤곽선마다 unclip 한 **원본 좌표** 사각형들.

        ★DBNet 은 글자 영역을 **줄여서** 예측한다 — 자체 시험에서 높이 56 짜리
          글자에 29 짜리 상자가 나왔다. 그래서 되부풀리는 unclip 이 필요하다.
          거리 공식은 pure-onnx-ocr `unclip_distance`(postprocessing.rs:462)
          그대로 **(면적/둘레)×1.5** 다. 다각형을 그 거리만큼 바깥으로 밀면
          바깥 사각형은 네 변이 각각 그 거리만큼 커진다(Round 조인이라 정확히).
        """
        p, ratio = self.prob_map(rgb)
        bina = (p >= THRESH).astype(np.uint8) * 255      # ★`>=` — 원본과 같다
        cont, _ = cv2.findContours(bina, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        h, w, _ = rgb.shape
        out = []
        for c in cont:
            area = abs(cv2.contourArea(c))
            if area < MIN_AREA:
                continue
            per = cv2.arcLength(c, True)
            d = (area / per) * UNCLIP_RATIO if per > 0 else 0.0
            x, y, bw, bh = cv2.boundingRect(c)
            x0, y0 = (x - d) / ratio, (y - d) / ratio
            x1, y1 = (x + bw + d) / ratio, (y + bh + d) / ratio
            out.append((max(0, int(np.floor(x0))), max(0, int(np.floor(y0))),
                        min(w, int(np.ceil(x1))), min(h, int(np.ceil(y1)))))
        return out

    def text_bbox(self, rgb: np.ndarray) -> tuple[int, int, int, int] | None:
        """검출된 상자 전체를 감싸는 하나의 사각형(자막 한 줄용)."""
        bb = self.boxes(rgb)
        if not bb:
            return None
        return (min(b[0] for b in bb), min(b[1] for b in bb),
                max(b[2] for b in bb), max(b[3] for b in bb))


def selftest() -> int:
    """흰 바탕에 검은 글자를 그려 넣고, 검출 상자가 그 글자를 감싸는지 본다."""
    from PIL import ImageDraw, ImageFont
    W, H = 640, 200
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    f = None
    import fontpath        # ★15-200 이식성 — 글꼴 자리는 fontpath.py 가 찾는다
    # ★15-228 — 애플 글꼴이 없는 PC(윈도우)에서도 자체시험 그림에 한글이 그려지게 팩 동봉 글꼴을 후보에 넣는다
    for cand in (fontpath.find("AppleSDGothicNeo.ttc"), fontpath.find("Helvetica.ttc"),
                 fontpath.find("SCDream9.otf"), fontpath.find("ROKAFSansMedium.ttf")):
        if cand:
            f = ImageFont.truetype(cand, 56)
            break
    d.text((60, 70), "자막 검출 시험", fill=(0, 0, 0), font=f)
    rgb = np.asarray(im)
    det = Detector()
    bb = det.text_bbox(rgb)
    assert bb is not None, "글자를 하나도 못 찾았다"
    x0, y0, x1, y1 = bb
    # 글자는 x≈60~ · y≈70~140 근처에 있다. 상자가 그 안쪽을 포함하고
    # 이미지 전체(=검출 실패의 다른 얼굴)가 아니어야 한다.
    assert x0 < 120 and x1 > 300, bb
    # unclip 뒤에는 글자 세로 범위(≈70~140)를 감싸야 한다 — 축소 상자면 여기서 걸린다
    assert 40 < y0 < 90 and 120 < y1 < 190, bb
    assert (x1 - x0) < W * 0.95, bb
    print(f"자체 시험 통과 · 검출 상자 {bb} (그림 {W}x{H})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    det = Detector()
    for p in a.images:
        rgb = np.asarray(Image.open(p).convert("RGB"))
        print(f"{os.path.basename(p):28s} {rgb.shape[1]}x{rgb.shape[0]} → {det.text_bbox(rgb)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
