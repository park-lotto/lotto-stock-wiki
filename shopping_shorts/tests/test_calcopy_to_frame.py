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
    # [광고] 는 12도 기울여 붙인다(기울임 판정 답) — 위가 오른쪽으로
    br = Image.new("RGB", (300, 100), PAINT); bd = ImageDraw.Draw(br)
    bd.text((260, 75), "[광고]", font=to_frame._pil_font("NotoSansKRBold", 50), fill=(190, 189, 192), anchor="rs",
            stroke_width=3, stroke_fill=(80, 80, 80))
    k = np.tan(np.radians(12))
    br = br.transform(br.size, Image.AFFINE, (1, k, -k * 50, 0, 1, 0), resample=Image.BICUBIC, fillcolor=PAINT)
    im.paste(br, (W - 300, 0))
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
    J2 = {**J, "fonts": {**J["fonts"], "title": {"ok": True, "top3": [{"font": "BlackHanSans.ttf", "score": 0.81}], "per_crop": []}}}
    F2 = to_frame.build(J2, np.asarray(im), ocr, tail_probe=lambda t: t < 17.3)
    return F, bands, (cy0, cy1), F2


def layer(F, kind, role=None):
    return next(l for l in F["layers"] if l["kind"] == kind and (role is None or l.get("role") == role))


def test_valid_and_frame_fields(synth):
    F, bands, _, _ = synth
    schema.validate(F)
    assert layer(F, "bg")["rgb"] == list(PAINT)                       # 잰 값(240,231,234)이 아니라 실제 칠
    assert layer(F, "video") == {"kind": "video", "x": 0, "y": 500, "w": W, "h": 1000, "radius": 0}
    assert F["template_off"] == {"tail_sec": 2.7}                     # 조각 값 15초가 아니라 다시 찾은 17.3초부터


def test_title_from_bands(synth):
    F, bands, _, _ = synth
    t = layer(F, "text", "title")
    assert t["text"] == "\n".join(TITLE) and t["lines"] == 2 and t["align"] == "center"
    # 분석기 fonts.title 이 없으면 같은 판별 함수(fontmatch.rank)를 제목에 직접 — 출처가 notes 에 남는다
    assert any("제목 글꼴" in n and "fontmatch.rank" in n for n in F["made_from"]["notes"])
    assert t["font"] in schema.font_families() and abs(t["size"] - 80) <= 4
    assert t["line_h"] == bands[2][0] - bands[1][0]
    assert t["rgb"] == [0, 0, 0] and t["outline"] is None and t["shadow"] is None and t["box"] is None
    assert t["italic"] is False


def test_brand_and_caption(synth):
    F, bands, (cy0, cy1), _ = synth
    b = layer(F, "text", "brand")
    assert b["text"] == "[광고]" and b["align"] == "right"
    assert b["italic"] is True                                         # 12도 기울인 답 → 기울임
    assert any("고정 문구 기울기" in n for n in F["made_from"]["notes"])
    assert max(abs(x - y) for x, y in zip(b["rgb"], (190, 189, 192))) <= 20
    assert b["outline"] and abs(b["outline"]["px"] - 3) <= 1 and max(b["outline"]["rgb"]) <= 110
    c = layer(F, "text", "caption")
    # 자막 = 합산 1위(Spoqa) — 렌더러에 등록돼 그대로 쓴다(1위가 미등록이라 내려가던 일 없음). 그린 글꼴(Noto)과 달라 크기·자간은 느슨히
    assert c["font"] == "CcSpoqaHanSansNeo-Bold" and abs(c["size"] - 60) <= 6 and c["lines"] == 1
    assert c["outline"] is None and c["rgb"] == [0, 0, 0]


def test_font_confidence_and_notes(synth):
    F, *_ = synth
    m = F["made_from"]
    assert m["font_confidence"] == "low"                              # 1위 0.42 < 0.5
    assert m["font"]["top1"] == "SpoqaHanSansNeo-Bold.otf" and m["font"]["skipped"] == []   # 창고 전부 등록(register_fonts)


def test_title_font_from_analyzer_when_given(synth):
    *_, F2 = synth
    t = layer(F2, "text", "title")
    assert t["font"] == "BlackHanSans"                                 # 분석기 2판 fonts.title 이 있으면 그것
    assert any("분석기 fonts.title 1위 BlackHanSans.ttf" in n for n in F2["made_from"]["notes"])
    assert layer(F2, "text", "caption")["font"] == "CcSpoqaHanSansNeo-Bold"   # 자막은 그대로 자막 순위


def test_every_warehouse_font_is_drawable():
    """창고 ttf/otf 전부가 렌더러에 등록돼 있다(register_fonts.py --check 와 같은 뜻)."""
    from pathlib import Path
    root = Path(to_frame.ROOT) / "shopping_shorts/static/fonts"
    miss = [p.name for p in root.glob("*") if p.suffix.lower() in (".ttf", ".otf") and not to_frame.family_of(p.name)]
    assert miss == []


def test_missing_values_are_null_not_guessed():
    J = {"probe": {"w": W, "h": H, "duration": 10}, "layout": {}, "captions": {}, "fonts": {"failed": "OCR 글자가 없음"}}
    F = to_frame.build(J, None, None)
    assert F["layers"] == [] and F["template_off"] is None
    assert any("배경색 없음" in n for n in F["made_from"]["notes"]) and any("글꼴 못 정함" in n for n in F["made_from"]["notes"])


def test_band_body_removes_outline_and_lean():
    """잰 띠(채움+외곽선)에서 글자 몸을 구한다 — 외곽선은 위아래·좌우로 px 씩, 기울임은 윗끝을 tan(14도)×높이만큼 민다.
    (2026-10-16 대조: 이걸 안 빼서 [광고] 글자 높이 61 vs 원본 52, 오른쪽 끝이 화면 끝에 닿았다)"""
    body_h, body_w, lean = to_frame.band_body((10, 64), (930, 1067), 3, True)
    assert body_h == 55 - 6
    assert lean == round(np.tan(np.radians(to_frame.OBLIQUE_DEG)) * 49)
    assert body_w == 138 - 6 - lean
    assert to_frame.band_body((10, 64), (930, 1067), 0, False) == (55, 138, 0)


def test_brand_layer_inside_measured_box(synth):
    F, bands, _, _ = synth
    b = layer(F, "text", "brand")
    o = b["outline"]["px"]
    assert b["x"] <= 1060 - o                                          # 오른쪽 끝 = 잰 끝 − 외곽선 − 기울임(화면 끝에 닿지 않게)
    f = to_frame._pil_font(b["font"], b["size"])
    bb = f.getbbox("[광고]", anchor="ls")
    assert abs((bb[3] - bb[1]) + 2 * o - (bands[0][1] - bands[0][0] + 1)) <= 3   # 글자 몸 + 외곽선 = 잰 띠 높이


def test_line_outline_of_white_ring_over_video():
    """흰 바탕의 흰 외곽선은 창 영상 위에서만 보인다 — 창 행(over_from)부터의 고리로 잰다."""
    a = np.full((120, 400, 3), PAINT, np.uint8)
    a[70:] = (40, 90, 120)                                             # 70행부터 창(영상) — 글자 아래쪽과 외곽선이 창 위로 걸친다
    import cv2
    m = np.zeros((120, 400), np.uint8); cv2.rectangle(m, (50, 20), (350, 74), 1, -1)
    ring = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))).astype(bool) & ~m.astype(bool)
    a[ring] = (255, 255, 255); a[m.astype(bool)] = (186, 0, 120)
    lo = to_frame.line_outline_of(a, [186, 0, 120], 70, list(PAINT))
    assert lo and 5 <= lo[0] <= 7 and min(lo[1:]) >= 240
    assert to_frame.line_outline_of(a, [186, 0, 120], 200, None) is None   # 창에 안 닿으면 못 잼


def test_word_spacing_widens_only_word_gaps_and_keeps_letter_spacing():
    """10-16 반려(자막 낱말이 붙어 보임): 낱말 간격은 공백 틈만 넓히고, 자간은 spacing_for 그대로(다시 줄여 글자가 붙지 않게)."""
    fam, size, txt = "CcSpoqaHanSansNeo-Bold", 66.0, "아니 이거 해외 릴스에서"
    f = to_frame._pil_font(fam, size)
    w0, g0 = to_frame._css_line(f, txt, -7.4, 0.0)
    w1, g1 = to_frame._css_line(f, txt, -7.4, 10.0)
    assert all(abs((b - a) - 10.0) < 1e-6 for a, b in zip(g0, g1))     # 공백마다 정확히 ws 만큼
    assert abs((w1 - w0) - 10.0 * txt.count(" ")) < 1e-6
    target_w = 700
    ls0 = to_frame.spacing_for(fam, size, txt, target_w)
    gl = to_frame._css_line(f, txt, ls0, 0.0)[1]
    ls, ws = to_frame.spacing_and_word_gap(fam, size, txt, target_w, target_gap=max(gl) + 6, gap_texts=[txt])
    assert ls == ls0 and ws >= 6
    assert to_frame.spacing_and_word_gap(fam, size, txt, target_w, None) == (ls, 0)    # 틈을 못 쟀으면 낱말 간격 0


def test_schema_keeps_word_spacing():
    f = {"canvas": [1080, 1920], "layers": [{"kind": "video", "x": 0, "y": 0, "w": 1080, "h": 1080},
                                             {"kind": "text", "role": "caption", "x": 540, "y": 1500, "w": 1000, "lines": 1,
                                              "font": "CcSpoqaHanSansNeo-Bold", "size": 66, "line_h": 76, "rgb": [0, 0, 0],
                                              "letter_spacing": -7.4, "word_spacing": 6.8}]}
    cap = next(l for l in schema.validate(f)["layers"] if l.get("role") == "caption")
    assert cap["word_spacing"] == 6.8 and cap["letter_spacing"] == -7.4


def test_short_centered_captions_inside_window():
    """답 아는 합성: 짧은 자막 3개(가운데 정렬) — 창 안 자막이라 잰 상자·잰 폭이 영상 내용까지 잡혀 흐리다(mY 10-16).
    정렬 = 가운데(중심 중앙값 ±20), 자간·낱말 간격 = 0(잰 폭이 글 길이를 안 따른다)."""
    from tools.calcopy.engine import to_frame as T
    W = 1080
    boxes = [(7, 742), (192, 917), (238, 843)]                     # mY 실측 상자 — 각자 중심 374·554·540
    assert T.align_of(boxes, W)["align"] == "center"
    assert T.align_of([(100, 906), (288, 797), (296, 730)], W)["align"] == "center"   # 끝이 안 모이면 가운데
    assert T.align_of([(60, 700), (61, 400), (62, 900)], W)["align"] == "left"        # 왼쪽 끝이 모이면 왼쪽
    items = [{"text": ["하키 경기 중"], "widths": [738], "lines": 1},
             {"text": ["퍽을 기다리고 있었죠"], "widths": [673], "lines": 1},
             {"text": ["한 여성이"], "widths": [687], "lines": 1}]
    notes = []
    assert T.caption_width_ref("Pretendard", 64, items, notes) is None and "글 길이를 안 따른다" in notes[-1]
    f = T._pil_font("Pretendard", 64)
    good = [{"text": [t], "widths": [round(f.getlength(t) * 0.95)], "lines": 1}
            for t in ("유리문에 원판을 대자마자", "이게 진짜 되는 거였어", "생각보다 훨씬 단단하다")]
    assert T.caption_width_ref("Pretendard", 64, good, []) is good[0]   # 잰 폭이 글 길이를 따르면 첫 자막으로 역산


def _dark_band_frame():
    """답 아는 합성(핫템 OE11 꼴): 검정 바탕 · 초록 글로우 흰 채널명(132~258) · 노랑 1줄(297~396) · 더 큰 빨강 2줄(408~560, 창 560 위로 이어짐)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    from tools.calcopy.engine import to_frame as T
    W, H = 1080, 1920
    im = Image.new("RGB", (W, H), (0, 0, 0))
    glow = Image.new("RGB", (W, H), (0, 0, 0)); g = ImageDraw.Draw(glow)
    g.text((540, 222), "핫템리포트", font=T._pil_font("BMDOHYEON", 54), fill=(0, 255, 0), anchor="ms")
    im = Image.fromarray(np.maximum(np.asarray(im), np.asarray(glow.filter(ImageFilter.GaussianBlur(28))) * 3 // 2))
    d = ImageDraw.Draw(im)
    d.text((540, 222), "핫템리포트", font=T._pil_font("BMDOHYEON", 54), fill=(242, 255, 240), anchor="ms")
    d.text((540, 390), "AI 주작 논란", font=T._pil_font("BMDOHYEON", 100), fill=(250, 234, 2), anchor="ms")
    d.text((540, 570), "아이언맨 헬멧", font=T._pil_font("BMDOHYEON", 150), fill=(253, 32, 30), anchor="ms")
    a = np.asarray(im).copy()
    rng = np.random.default_rng(3)
    vid = rng.integers(60, 200, (H - 560, W, 3), dtype=np.uint8)
    keep = a[560:].max(axis=2) > 150          # 글자가 영상 위로 그려진 틀 — 글자 점은 그대로 둔다
    a[560:][~keep] = vid[~keep]
    return a


def test_dark_band_brand_glow_and_title_bottom():
    import numpy as np
    from tools.calcopy.engine import to_frame as T
    a = _dark_band_frame()
    bg = [0, 0, 0]
    cores = {b: T.band_core(a, b, bg) for b in ((132, 258), (297, 396), (408, 559))}
    brand, l1, l2 = cores[(132, 258)], cores[(297, 396)], cores[(408, 559)]
    assert brand["w"] < T.BRAND_MAX_W * 1080 and brand["h"] < T.BRAND_CORE_RATIO * max(l1["h"], l2["h"])   # 채널명 = 고정 문구 자격
    gl = T.glow_of(a, (132, 258), bg, brand)
    assert gl and gl["rgb"][1] > 2 * max(gl["rgb"][0], gl["rgb"][2]) and gl["px"] >= 10                    # 초록 글로우
    assert T.glow_of(a, (297, 396), bg, l1) is None                                                         # 제목 줄은 글로우 아님
    assert max(abs(x - y) for x, y in zip(l2["fill"], (253, 32, 30))) <= 10                                 # 빨강 줄 채움(분석기 bright 문턱 밖)
    bot = T.title_line_bottom(a, (408, 559), [0, 560, 1080, 1360])
    assert bot > 565                                                                                        # 창 위로 이어진 글자 아래까지


def test_line_outline_none_when_ring_never_ends():
    """어두운 바탕·어두운 영상 위 글자: 고리 색이 12px 까지 안 바뀌면 외곽선이 아니라 바탕(mY 12px 오판)."""
    import numpy as np
    from PIL import Image, ImageDraw
    from tools.calcopy.engine import to_frame as T
    im = Image.new("RGB", (600, 200), (45, 30, 38)); d = ImageDraw.Draw(im)
    d.text((300, 150), "눈물 줄줄", font=T._pil_font("BMDOHYEON", 120), fill=(240, 198, 18), anchor="ms")
    assert T.line_outline_of(np.asarray(im), [240, 198, 18], 0, None) is None
    im2 = Image.new("RGB", (600, 200), (0, 0, 0)); rng = np.random.default_rng(1)
    a2 = rng.integers(0, 255, (200, 600, 3)).astype(np.uint8)
    im2 = Image.fromarray(a2); d2 = ImageDraw.Draw(im2)
    d2.text((300, 150), "눈물 줄줄", font=T._pil_font("BMDOHYEON", 120), fill=(240, 198, 18), anchor="ms", stroke_width=5, stroke_fill=(255, 255, 255))
    m = T.line_outline_of(np.asarray(im2), [240, 198, 18], 0, None)
    assert m and 3 <= m[0] <= 7 and min(m[1:]) > 200                                                     # 영상 위 흰 외곽선 5px
