"""뜯기.json → frame.json 자동 변환(tools/calcopy/engine/to_frame.build) — 답을 아는 합성 프레임·합성 뜯기로 필드를 단언한다.

합성 프레임: 바탕 (250,240,245) · 제목 2줄 NotoSansKRBold 80px(검정) · 오른쪽 위 [광고] 회색 채움+짙은 외곽선 3px.
합성 뜯기: 분석기 1판 모양(analyze.py) — bg_rgb 는 일부러 실제 칠과 다르게(잰 값 흉내), 틀이 다른 구간은 조각 단위(15초)로.
"""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from shopping_shorts.calcopy_frame import schema
from tools.calcopy.engine import to_frame

W, H = 1080, 1920
PAINT = (250, 240, 245)
TITLE = ["닿으면 스피커", "소름 돋는 음질 수준"]
CAP = "아니 이거 해외 릴스에서 맨날 보이길래"


def ink_rows(im, y0, y1, x0=0, x1=W):
    a = np.asarray(im)[y0:y1, x0:x1].astype(int)
    rows = np.where((np.abs(a - np.array(PAINT)).max(axis=2) > 40).any(axis=1))[0]
    return int(rows.min()) + y0, int(rows.max()) + y0


@pytest.fixture(scope="module")
def synth():
    f80 = to_frame._pil_font("NotoSansKRBold", 80)
    im = Image.new("RGB", (W, H), PAINT); d = ImageDraw.Draw(im)
    d.text((540, 260), TITLE[0], font=f80, fill=(0, 0, 0), anchor="ms")
    d.text((540, 360), TITLE[1], font=f80, fill=(0, 0, 0), anchor="ms")
    d.text((1060, 70), "[광고]", font=to_frame._pil_font("NotoSansKRBold", 50), fill=(190, 189, 192), anchor="rs",
           stroke_width=3, stroke_fill=(80, 80, 80))
    d.rectangle((0, 500, W - 1, 1499), fill=(30, 90, 120))     # 영상 창
    f60 = to_frame._pil_font("NotoSansKRBold", 60)
    d.text((540, 1600), CAP, font=f60, fill=(0, 0, 0), anchor="ms")
    bands = [list(ink_rows(im, 0, 120)), list(ink_rows(im, 180, 290)), list(ink_rows(im, 290, 420))]
    cy0, cy1 = ink_rows(im, 1500, 1700)
    cb = f60.getbbox(CAP, anchor="ms")
    J = {"engine": "합성", "source": "synthetic.mp4",
         "probe": {"w": W, "h": H, "duration": 20.0},
         "layout": {"window": [0, 500, W, 1000], "bg_rgb": [240, 231, 234], "ink_polarity": "dark",
                    "above_bands": bands, "other_frame_segments": [[15.0, 20.0]]},
         "captions": {"spans": [[0, 10], [10, 17.3]],
                      "items": [{"i": 0, "t0": 0, "t1": 10, "lines": 1, "widths": [cb[2] - cb[0]], "top_y": cy0, "text": [CAP]}],
                      "glyph": [{"line_h": cy1 - cy0 + 1}]},
         "text_fx": {"summary": {"fill_rgb": [0, 0, 0], "outline_px": 0, "outline_rgb": None, "box": None, "shadow": None,
                                 "line_h_px": cy1 - cy0 + 1}},
         "fonts": {"ok": True, "top3": [{"font": "SpoqaHanSansNeo-Bold.otf", "score": 0.42}, {"font": "NotoSansKR-Bold.otf", "score": 0.41}],
                   "per_crop": []}}
    ocr = {"title": TITLE, "brand": "[광고]"}
    F = to_frame.build(J, np.asarray(im), ocr, tail_probe=lambda t: t < 17.3)
    return F, bands, (cy0, cy1)


def layer(F, kind, role=None):
    return next(l for l in F["layers"] if l["kind"] == kind and (role is None or l.get("role") == role))


def test_valid_and_frame_fields(synth):
    F, bands, _ = synth
    schema.validate(F)
    assert layer(F, "bg")["rgb"] == list(PAINT)                       # 잰 값(240,231,234)이 아니라 실제 칠
    assert layer(F, "video") == {"kind": "video", "x": 0, "y": 500, "w": W, "h": 1000, "radius": 0}
    assert F["template_off"] == {"tail_sec": 2.7}                     # 조각 값 15초가 아니라 다시 찾은 17.3초부터


def test_title_from_bands(synth):
    F, bands, _ = synth
    t = layer(F, "text", "title")
    assert t["text"] == "\n".join(TITLE) and t["lines"] == 2 and t["align"] == "center"
    assert t["font"] == "NotoSansKRBold" and abs(t["size"] - 80) <= 2
    assert t["line_h"] == bands[2][0] - bands[1][0]
    assert t["rgb"] == [0, 0, 0] and t["outline"] is None and t["shadow"] is None and t["box"] is None
    assert abs(t["letter_spacing"]) <= 2                               # 같은 글꼴로 그렸으니 폭 보정이 거의 0


def test_brand_and_caption(synth):
    F, bands, (cy0, cy1) = synth
    b = layer(F, "text", "brand")
    assert b["text"] == "[광고]" and b["align"] == "right"
    assert max(abs(x - y) for x, y in zip(b["rgb"], (190, 189, 192))) <= 20
    assert b["outline"] and abs(b["outline"]["px"] - 3) <= 1 and max(b["outline"]["rgb"]) <= 110
    c = layer(F, "text", "caption")
    assert c["font"] == "NotoSansKRBold" and abs(c["size"] - 60) <= 2 and c["lines"] == 1
    assert c["outline"] is None and c["rgb"] == [0, 0, 0]
    assert abs(c["letter_spacing"]) <= 2


def test_font_confidence_and_notes(synth):
    F, *_ = synth
    m = F["made_from"]
    assert m["font_confidence"] == "low"                              # 1위 0.42 < 0.5
    assert m["font"]["top1"] == "SpoqaHanSansNeo-Bold.otf" and "SpoqaHanSansNeo-Bold.otf(장면꾸미기 미등록)" in m["font"]["skipped"]


def test_missing_values_are_null_not_guessed():
    J = {"probe": {"w": W, "h": H, "duration": 10}, "layout": {}, "captions": {}, "fonts": {"failed": "OCR 글자가 없음"}}
    F = to_frame.build(J, None, None)
    assert F["layers"] == [] and F["template_off"] is None
    assert any("배경색 없음" in n for n in F["made_from"]["notes"]) and any("글꼴 못 정함" in n for n in F["made_from"]["notes"])
