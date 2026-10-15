"""게시글형 틀 자동 설명서(tools/calcopy/engine/to_frame_multi.analyze_image) — 답을 아는 합성 프레임.

합성: 흰 바탕 · 헤더 띠(연두, 0~236, 가운데 검정 글자) · 프로필 상자(연두 136×127) · 큰 제목 2줄(검정·각 120px) ·
구분선(검정 2px, y515) · 영상 창(움직임: 두 장이 다름) + 창에 붙은 영상 줄(창 아래 50px, 움직임).
"""
import numpy as np
from PIL import Image, ImageDraw

from tools.calcopy.engine import to_frame as T
from tools.calcopy.engine import to_frame_multi as M

W, H = 1080, 1920


def synth(seed):
    rng = np.random.default_rng(seed)
    im = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, 235), fill=(227, 239, 211))
    d.text((80, 160), "맛있는 친구들", font=T._pil_font("BMDOHYEON", 100), fill=(0, 0, 0), anchor="ls")
    d.rectangle((88, 267, 223, 393), fill=(227, 239, 211))
    d.text((540, 380), "한국 코스트코가", font=T._pil_font("BMDOHYEON", 120), fill=(0, 0, 0), anchor="ms")   # 띠 밖 큰 글자 2줄
    d.text((540, 500), "억울했던 이유야", font=T._pil_font("BMDOHYEON", 120), fill=(0, 0, 0), anchor="ms")
    d.rectangle((0, 515, W - 1, 516), fill=(0, 0, 0))
    a = np.asarray(im).copy()
    a[750:1700] = rng.integers(0, 255, (950, W, 3), dtype=np.uint8)     # 영상 창 750~1650 + 붙은 영상 줄 1650~1700
    return a


def test_analyze_image_layers():
    a, b = synth(1), synth(2)
    an = M.analyze_image(a, [], [0, 750, W, 900], b)
    assert an["bg"] == [255, 255, 255]
    assert any(abs(x["y"] - 0) <= 1 and abs(x["h"] - 236) <= 2 and max(abs(p - q) for p, q in zip(x["rgb"], (227, 239, 211))) <= 4
               for x in an["bands"])                                    # 헤더 띠(가운데 글자가 얹혀도 한 띠)
    assert any(x["y"] == 515 and x["h"] == 2 for x in an["dividers"])  # 구분선
    assert any(abs(x["x"] - 88) <= 2 and abs(x["w"] - 136) <= 3 for x in an["boxes"])   # 프로필 상자
    assert an["video_ext"] == [(1650, 1699)]                            # 움직이는 줄 = 영상(창을 늘린다), 띠 아님
    big = [t for t in an["texts"] if t["y1"] - t["y0"] + 1 >= 80 and not t.get("in_band")]
    assert len(big) == 2                                                 # 큰 제목 2줄 — 낱말 사이 띄어쓰기로 안 쪼개진다
    assert any(t.get("in_band") for t in an["texts"])                   # 헤더 글자는 띠 안 글자
