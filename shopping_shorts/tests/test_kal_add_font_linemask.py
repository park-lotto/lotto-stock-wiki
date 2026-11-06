"""글꼴 대조 줄 마스크 오염 자르기(표 #222 자리 · Jev 해결 0.51·0.53·위험 0.31·0.30 · 11-06).

자막이 영상 위에 있으면 영상 속 밝은 픽셀이 같은 줄로 붙는다(스냅봤니 fFhPI 줄 상자 225~340px·'모든 후보 점수 0').
줄 높이·OCR 줄 수를 받으면 그 높이 창 n 개 + 섬 자르기. 안 받으면 옛 동작 그대로.
"""
import numpy as np
from PIL import Image, ImageDraw

from tools.calcopy.engine import fontmatch as FM


def _scene(with_blob=True):
    img = np.zeros((300, 1000, 3), np.uint8) + 60
    im = Image.fromarray(img)
    if with_blob:                                        # 영상 속 흰 옷(검은 테두리 — 외곽선 자막처럼 보이는 밝은 덩어리), 글자 줄 바로 위에 붙음
        ImageDraw.Draw(im).rectangle((300, 60, 420, 215), fill=(250, 250, 250), outline=(0, 0, 0), width=6)
    f = FM._font(FM.font_paths()[2], 60)                 # BMJUA
    d = ImageDraw.Draw(im)
    d.text((100, 200), "한 친구의 의자만", font=f, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    d.text((800, 90), "가", font=f, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))   # 멀리 떨어진 섬
    return np.array(im)


def test_old_behaviour_is_polluted_and_unchanged_without_args():
    a = _scene()
    old = FM.line_masks(a, "bright")
    assert max(m.shape[0] for m in old) > 100                 # 고치기 전: 줄 상자가 영상 덩어리까지 커진다


def test_line_h_window_cuts_pollution():
    a = _scene()
    ms = FM.line_masks(a, "bright", line_h=62, n_lines=1)
    assert len(ms) == 1 and ms[0].shape[0] <= 62 + 6 and ms[0].shape[1] < 700   # 높이 = 줄 창, 폭 = 글자 덩어리(섬 '가' 버림)
