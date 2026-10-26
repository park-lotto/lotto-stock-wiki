# -*- coding: utf-8 -*-
"""카드뉴스 레이아웃 산식 — 정본 `renderer.ts` 의 순수 함수 이식본.

■ 왜 이 파일이 따로 있나
    정본은 브라우저 canvas 에 묶여 있다(`document.createElement`·`document.fonts`).
    파이썬으로 옮길 때 **그림 그리는 부분과 자릿수 계산하는 부분을 갈라서**,
    자릿수 쪽만 먼저 1:1 로 옮기고 **차동 검증으로 동일성을 증명**한다.
    (`CLAUDE.md` §1: 옮길 때는 차동 테스트로 동일성을 증명한다)

■ JS 와 파이썬이 다른 지점 — 여기서 틀리면 1px 씩 어긋난다
    · `Math.round` 는 **항상 위로** 반올림한다(-0.5 → -0). 파이썬 `round` 는 짝수로 붙는다
      (`round(0.5)==0`, `round(2.5)==2`). 그래서 `js_round` 를 따로 쓴다.
    · `Math.floor` 는 파이썬 `math.floor` 와 같다 — 그대로 쓴다.
"""

import math

# 좌우 패딩 — 폭 대비 비율 (데모 검증값)
SIDE_PAD_FRAC = 0.065
# 하단/상단 앵커 패딩 — 높이 대비
BOTTOM_PAD_FRAC = 0.055
TOP_PAD_FRAC = 0.06
# 제목 줄간(폰트 px 대비 배수)
TITLE_LINE_GAP_FRAC = 0.22
# 본문 폰트 크기 = 제목 대비 배수
BODY_SIZE_FRAC = 0.42
BODY_LINE_HEIGHT = 1.45
# 제목-본문 사이 간격(제목 px 대비)
BODY_TOP_GAP_FRAC = 0.55
# 폴라로이드 프레임 여백(폭 대비) + 하단 흰 영역(높이 대비)
POLAROID_MARGIN_FRAC = 0.05
POLAROID_ZONE_FRAC = 0.24


def js_round(v):
    """JS `Math.round` — 0.5 는 **항상 큰 쪽**으로. 파이썬 round 와 다르다."""
    return math.floor(v + 0.5)


def compute_cover_fit(src_w, src_h, dst_w, dst_h):
    """cover-fit — 큰 쪽 배율로 키우고 가운데를 잘라 쓴다."""
    if src_w <= 0 or src_h <= 0:
        return {"dx": 0, "dy": 0, "dw": dst_w, "dh": dst_h}
    scale = max(dst_w / src_w, dst_h / src_h)
    dw = src_w * scale
    dh = src_h * scale
    return {"dx": (dst_w - dw) / 2, "dy": (dst_h - dh) / 2, "dw": dw, "dh": dh}


def compute_highlight_rect(style, text_width, x, baseline_y, font_size):
    """형광펜/밴드 박스. under·none 은 박스가 없다 → None."""
    if style not in ("pen", "band"):
        return None
    pad_x = font_size * 0.28
    ascent = font_size * 0.82
    top_pad = font_size * 0.12
    bottom_pad = font_size * 0.18
    return {
        "x": x - pad_x,
        "y": baseline_y - ascent - top_pad,
        "w": text_width + pad_x * 2,
        "h": ascent + top_pad + bottom_pad + font_size * 0.08,
        "radius": font_size * 0.16,
    }


def compute_underline_rect(text_width, x, baseline_y, font_size):
    """밑줄 — baseline 바로 아래 두께 fontSize*0.22 띠."""
    return {
        "x": x - font_size * 0.05,
        "y": baseline_y - font_size * 0.08,
        "w": text_width + font_size * 0.1,
        "h": font_size * 0.22,
        "radius": 0,
    }


def compute_fitted_font_size(measured_width, base_size, max_width, min_size=18):
    """잰 폭이 자리보다 넓으면 폰트를 그 비율만큼 줄인다(텍스트 폭은 크기에 비례)."""
    if measured_width <= 0 or max_width <= 0:
        return base_size
    if measured_width <= max_width:
        return base_size
    return max(min_size, math.floor(base_size * (max_width / measured_width)))


def compute_photo_rect(width, height, frame):
    """사진이 그려질 영역 — polaroid 는 액자 안쪽, 그 외는 전면."""
    if frame != "polaroid":
        return {"x": 0, "y": 0, "w": width, "h": height}
    m = js_round(width * POLAROID_MARGIN_FRAC)
    zone_h = js_round(height * POLAROID_ZONE_FRAC)
    return {"x": m, "y": m, "w": width - m * 2, "h": height - m - zone_h}


def compute_text_zone(width, height, frame):
    """글자가 들어갈 수 있는 세로 구간 — polaroid 는 아래 흰 여백만."""
    if frame == "polaroid":
        photo = compute_photo_rect(width, height, frame)
        return {
            "top": photo["y"] + photo["h"] + js_round(height * 0.02),
            "bottom": height
            - js_round(width * POLAROID_MARGIN_FRAC)
            - js_round(height * 0.005),
        }
    return {
        "top": js_round(height * TOP_PAD_FRAC),
        "bottom": height - js_round(height * BOTTOM_PAD_FRAC),
    }


def compute_template_layout(
    width, height, title_size_px, has_line1, has_line2, body_line_count, anchor, frame
):
    """제목1/제목2/본문N 을 위에서부터 쌓고, anchor 에 따라 통째로 옮긴다.

    line2 가 비면 그 줄의 높이를 차지하지 않는다(빈 형광펜 박스 방지)."""
    text_x = js_round(width * SIDE_PAD_FRAC)
    body_font_size = js_round(title_size_px * BODY_SIZE_FRAC)
    body_line_h = js_round(body_font_size * BODY_LINE_HEIGHT)
    title_gap = js_round(title_size_px * TITLE_LINE_GAP_FRAC)
    title_ascent = js_round(title_size_px * 0.85)

    # ① 블록 안에서의 상대 위치 (블록 맨 위 = 0)
    cursor = 0
    line1_off = 0
    line2_off = 0
    if has_line1:
        line1_off = cursor + title_ascent
        cursor = line1_off + js_round(title_size_px * 0.2)
    if has_line2:
        line2_off = (line1_off + title_size_px + title_gap) if has_line1 else title_ascent
        cursor = line2_off + js_round(title_size_px * 0.25)
    body_offsets = []
    if body_line_count > 0:
        body_cursor = (
            (cursor + js_round(title_size_px * BODY_TOP_GAP_FRAC))
            if (has_line1 or has_line2)
            else 0
        ) + js_round(body_font_size * 0.85)
        for _ in range(body_line_count):
            body_offsets.append(body_cursor)
            body_cursor += body_line_h
        cursor = body_offsets[-1] + js_round(body_font_size * 0.35)
    block_height = cursor

    # ② 배치 구간
    zone = compute_text_zone(width, height, frame)
    zone_top = zone["top"]
    zone_bottom = zone["bottom"]

    # ③ anchor 적용
    if anchor == "top":
        block_top = zone_top
    elif anchor == "center":
        block_top = zone_top + max(
            0, js_round((zone_bottom - zone_top - block_height) / 2)
        )
    else:
        block_top = zone_bottom - block_height

    return {
        "line1BaselineY": (block_top + line1_off) if has_line1 else 0,
        "line2BaselineY": (block_top + line2_off) if has_line2 else 0,
        "bodyBaselineYs": [block_top + off for off in body_offsets],
        "textX": text_x,
        "bodyFontSize": body_font_size,
        "blockTop": block_top,
        "blockBottom": block_top + block_height,
    }


def compute_zone_fitted_layout(
    width, height, title_size_px, has_line1, has_line2, body_line_count, anchor, frame
):
    """블록이 구간을 넘치면 제목 크기를 그 비율만큼 줄여 한 번 더 배치한다."""
    first = compute_template_layout(
        width, height, title_size_px, has_line1, has_line2, body_line_count, anchor, frame
    )
    zone = compute_text_zone(width, height, frame)
    zone_h = zone["bottom"] - zone["top"]
    block_h = first["blockBottom"] - first["blockTop"]
    if block_h <= zone_h or zone_h <= 0:
        return {"layout": first, "titleSizePx": title_size_px}
    scaled = max(18, math.floor(title_size_px * (zone_h / block_h)))
    return {
        "layout": compute_template_layout(
            width, height, scaled, has_line1, has_line2, body_line_count, anchor, frame
        ),
        "titleSizePx": scaled,
    }


# ── 색 계산 ────────────────────────────────────────────────


def parse_hex_color(hex_str):
    s = (hex_str or "").strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        return None
    try:
        v = int(s, 16)
    except ValueError:
        return None
    return {"r": (v >> 16) & 0xFF, "g": (v >> 8) & 0xFF, "b": v & 0xFF}


def to_hex_channel(v):
    return "%02x" % max(0, min(255, js_round(v)))


def mix_hex_colors(from_hex, to_hex, t):
    """두 색 섞기 — t=0 이면 from, t=1 이면 to."""
    a = parse_hex_color(from_hex)
    b = parse_hex_color(to_hex)
    if a is None or b is None:
        if b is None:
            return "#000000"
        return "#" + to_hex_channel(b["r"]) + to_hex_channel(b["g"]) + to_hex_channel(b["b"])
    k = max(0.0, min(1.0, t))
    return (
        "#"
        + to_hex_channel(a["r"] + (b["r"] - a["r"]) * k)
        + to_hex_channel(a["g"] + (b["g"] - a["g"]) * k)
        + to_hex_channel(a["b"] + (b["b"] - a["b"]) * k)
    )


def approx_luma(hex_str):
    c = parse_hex_color(hex_str)
    if c is None:
        return 0
    return 0.2126 * c["r"] + 0.7152 * c["g"] + 0.0722 * c["b"]


def compute_no_image_backdrop(accent_hex, ink):
    """사진이 없는 카드의 배경 — 새까만 판 대신 강조색을 머금은 딥톤."""
    accent = accent_hex if parse_hex_color(accent_hex) else "#FFE14D"
    if ink == "dark":
        return {
            "from": mix_hex_colors(accent, "#f2efe9", 0.86),
            "to": mix_hex_colors(accent, "#e0dcd4", 0.93),
            "glow": accent,
        }
    return {
        "from": mix_hex_colors(accent, "#16161d", 0.84),
        "to": mix_hex_colors(accent, "#07070b", 0.95),
        "glow": accent,
    }


def pick_ink_on_accent(accent_hex):
    """강조색 위에 올릴 글자색 — 밝으면 검정, 어두우면 흰색."""
    if parse_hex_color(accent_hex) is None:
        return "#111111"
    return "#111111" if approx_luma(accent_hex) > 140 else "#FFFFFF"
