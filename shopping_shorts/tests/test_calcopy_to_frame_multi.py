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


def synth_hook():
    """훅 카드 꼴: 바탕 64 · 머리 띠(56,58,51 — 바탕과 차 8~13, 0~234) · 회색 띠(560~671: 위 20줄 번짐, 가로 양 끝 156 → 가운데 242)."""
    a = np.full((H, W, 3), 64, np.uint8)
    a[0:235] = (56, 58, 51)
    xs = np.abs(np.arange(W) - W / 2) / (W / 2)
    prof = np.clip(242 - np.maximum(0, xs - 0.8) / 0.2 * 86, 156, 242)          # 가운데 242, 양 끝 156
    for y in range(560, 672):
        r = min(1.0, (y - 560 + 0.5) / 20)
        a[y] = (64 + r * (prof - 64))[:, None].astype(np.uint8)
    im = Image.fromarray(a); d = ImageDraw.Draw(im)
    d.text((540, 650), "한국 코스트코가", font=T._pil_font("BMDOHYEON", 60), fill=(0, 0, 0), anchor="ms")
    d.line((80, 80, 160, 130), fill=(0, 0, 0), width=6)                         # 머리 띠 위 검정 선 그림(차 56)
    return np.asarray(im)


def test_low_contrast_band_fade_and_gradient():
    a = synth_hook()
    an = M.analyze_image(a, [], [0, 672, W, 1026], a)
    bands = sorted(an["bands"], key=lambda b: b["y"])
    head, grey = bands[0], bands[-1]
    assert head["y"] == 0 and abs(head["h"] - 235) <= 2 and head["rgb"] == [56, 58, 51]   # 바탕과 13 차이 띠도 띠
    assert grey["fade"][0] >= 10 and grey["y"] <= 566                                     # 위 번짐
    g = dict((p, c[0]) for p, c in grey["grad_x"])
    assert g[0] <= 170 and g[0.5] >= 235                                                  # 가로 그라데이션
    txt = [t for t in an["texts"] if 600 < t["y1"] < 672]
    assert txt and min(t["y0"] for t in txt) > 590                                        # 번진 줄·띠 끝은 글자가 아니다
    assert any(t["y0"] < 140 and t["x0"] < 100 for t in an["texts"])                      # 어두운 띠 위 검정 선 그림은 글자 덩어리


def test_band_grad_fade_schema():
    from shopping_shorts.calcopy_frame import schema
    base = {"canvas": [W, H], "layers": [{"kind": "bg", "rgb": [64, 64, 64]},
            {"kind": "band", "x": 0, "y": 560, "w": W, "h": 112, "rgb": [242, 242, 242],
             "grad_x": [[0, [156, 156, 156]], [0.5, [242, 242, 242]], [1, [156, 156, 156]]], "fade": [20, 0]}]}
    s = schema.validate(base)
    assert s["layers"][1]["fade"] == [20, 0] and len(s["layers"][1]["grad_x"]) == 3
    import copy, pytest
    bad = copy.deepcopy(base); bad["layers"][1]["fade"] = [80, 80]
    with pytest.raises(schema.FrameError):
        schema.validate(bad)
    bad = copy.deepcopy(base); bad["layers"][1]["grad_x"] = [[0.6, [1, 1, 1]], [0.2, [1, 1, 1]]]
    with pytest.raises(schema.FrameError):
        schema.validate(bad)
