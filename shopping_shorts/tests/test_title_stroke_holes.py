"""11-06 박은숙 #9849·#9859(썰템쇼판 full 틀, 제목 BlackHanSans): frame.png 제목 '갈아도'의 '아' ㅏ 자리에 검은 외곽선이 없어
밝은 장면에서 글자가 사라졌다. 원인 = Pillow ImageDraw.text(stroke_width) 의 FreeType 외곽선이 일부 글자 모양(아·안·하·히…, 글꼴 20개)에서
외곽선을 빠뜨림. 주인 = render_bench._spaced(외곽선 글 한 곳) — 채움 마스크 팽창 외곽선을 먼저 깐다. 결과물(frame.png 픽셀)로 잰다."""
import json

import numpy as np
from PIL import Image, ImageDraw

from tools.calcopy.hybrid import render_bench as RB, styles as STY

S = {"lines": [{"id": "L1", "kind": "tts", "tts": "a", "caps": [{"text": "a"}]}], "title_lines": [["와이퍼 새로 갈아도"], ["끼익 소리 나면"]]}
TEXT = {"layout": "full", "title_font": "BlackHanSans", "title_colors": ["#FFFFFF", "#FFE600"], "caption_font": "BlackHanSans"}


def _bare(sw, text, font="BlackHanSans.ttf", px=104):
    """빈 판에 외곽선 글 한 줄 → (외곽선이 덮어야 할 자리 중 비어 있는 픽셀 수). 덮어야 할 자리 = 채움 잉크에서 sw-2 안쪽."""
    f = RB._font(font, px)
    lay = Image.new("RGBA", (900, 300), (0, 0, 0, 0))
    RB._spaced(ImageDraw.Draw(lay), (60, 60), text, f, 0, fill=(255, 255, 255, 255), stroke_width=sw, stroke_fill=(0, 0, 0, 255))
    m = Image.new("L", lay.size, 0)
    ImageDraw.Draw(m).text((60, 60), text, font=f, fill=255)
    ink = np.array(m) >= 128
    near = np.zeros_like(ink)
    r = sw - 2
    ys, xs = np.nonzero(ink)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                near[np.clip(ys + dy, 0, ink.shape[0] - 1), np.clip(xs + dx, 0, ink.shape[1] - 1)] = True
    return int((near & (np.array(lay)[..., 3] < 250)).sum())


def test_외곽선이_빠지는_글자도_테두리가_찬다():
    for t in ("갈아도", "안", "하히", "뒤뉘"):
        assert _bare(10, t) == 0, t


def test_박은숙_full틀_제목_구멍_0(tmp_path, monkeypatch):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"member": {"brand": {"channel_name": "테스트채널"}, "text": TEXT}}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(p))
    st = STY.load("썰템쇼판")
    assert st["frame"]["kind"] == "full"
    out = RB.frame_png(S, st, tmp_path / "frame.png")
    a = np.array(Image.open(out).convert("RGBA"))
    # 제목 두 줄 자리(가운데 250·385) — 흰·노랑 채움 픽셀 둘레(외곽선 폭 안)가 전부 불투명해야 한다
    reg = a[150:480]
    fillpx = (reg[..., 0] > 200) & (reg[..., 1] > 200) & (reg[..., 3] > 0)
    ys, xs = np.nonzero(fillpx)
    hole = 0
    for dy, dx in ((0, 6), (0, -6), (6, 0), (-6, 0)):
        yy, xx = np.clip(ys + dy, 0, reg.shape[0] - 1), np.clip(xs + dx, 0, reg.shape[1] - 1)
        hole += int((reg[yy, xx, 3] == 0).sum())
    assert hole == 0, hole
