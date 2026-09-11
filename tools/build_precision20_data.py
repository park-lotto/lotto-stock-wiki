# -*- coding: utf-8 -*-
"""조회수 검증 20세트의 훅·본문 실측 JSON을 사용자 UI용 단일 데이터로 묶는다.

원본 프레임과 실측값이 정의처다. UI 안에 좌표를 두 번 적지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from caption_slot_detection import detect_bottom_caption_slot, extend_reserved_slot_over_source_text


ROOT = Path(__file__).resolve().parents[1]
COLLECT = ROOT / "out" / "장면꾸미기_작업대" / "스타일수집"
TOP = COLLECT / "top20_views"
DEST = ROOT / "out" / "precision20-data.js"

META = [
    ("01", "활용정점.", 12139793, "t01"), ("02", "살림킹왕짱", 10500577, "t02"),
    ("03", "썰카12", 4153755, "t03"), ("04", "방구석꿀템", 2632668, "t04"),
    ("05", "럭키박스", 2462198, "t05"), ("06", "쇼핑 치트키", 2191265, "t06"),
    ("07", "공가미", 1656963, "t07"), ("08", "코어장바구니", 1223987, "t08"),
    ("09", "살림장착", 1042893, "t09"), ("10", "쇼핑천재", 1037885, "t10"),
    ("11", "이븐쇼핑", 885414, "t11"), ("12", "이거였네", 852645, "t12"),
    ("13", "달래샵", 690236, "t13"), ("14", "꿀팁꿀템", 550893, "t14"),
    ("15", "다있슈", 475420, "t15"), ("16", "인생갓템", 469962, "t16"),
    ("17", "나만또모르고있었지", 455207, "t17"), ("18", "숏템", 0, "s0101"),
    ("19", "무슨템", 395739, "t19"), ("20", "헤븐쇼핑", 0, "s0056"),
]

SAMPLES = {
    "활용정점.": ["코스트코 본사도 몰랐던", "천재 아이디어"],
    "살림킹왕짱": ["개발자도 예상 못한", "미친 사용법"],
    "썰카12": ["다이소도 감탄한", "반전의 스티커"],
    "방구석꿀템": ["다이소 덕후들의", "천재적인 활용법"],
    "이븐쇼핑": ["건망증 환자를 살려낸", "일본 천재의 발명품"],
    "숏템": ["이케아도 놀랄", "한국 천재 발명품"],
    "쇼핑 치트키": ["부모를 오열하게 만든", "다이소 제품의 정체"],
    "이거였네": ["이게 왜 이제야 보였지", "몰랐던 생활 아이디어"],
    "나만또모르고있었지": ["나만 또 모르고 있었지", "이걸 왜 이제 알았지?"],
}

# 자동 실측기를 원본 프레임과 픽셀 대조해 수정한 값.
# 이 표에 들어온 프리셋만 "초정밀" 검수 대상이다.
MANUAL = {
    "s0101": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#2B271D", "top_band": None,
            "channel_boxes": [
                {"x": 132, "y": 20, "width": 96, "height": 48, "background": "#2B271D", "color": "#050505", "radius": 0, "border": None, "font_size": 27, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -1.4}
            ],
            "lines": [
                {"x0": 5, "x1": 355, "y0": 68, "y1": 132, "h": 65, "lpct": 1.4, "rpct": 1.4, "color": "#FFFFFF", "background": "#2D2D2A", "font_size": 63.4, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -3.3, "stroke": 3.8, "shadow_y": 4.2, "patch_top": 5, "patch_bottom": 3},
                {"x0": 5, "x1": 355, "y0": 133, "y1": 190, "h": 58, "lpct": 1.4, "rpct": 1.4, "color": "#FFE500", "background": "#2D2D2A", "font_size": 53, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -3.0, "stroke": 3.8, "shadow_y": 4.2, "patch_top": 2, "patch_bottom": 2},
            ],
            "white_box": {"y0": 191, "y1": 248, "text": {"x0": 16, "x1": 344, "y0": 205, "y1": 238, "h": 34, "font_size": 27, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -1.65, "stroke": 0, "shadow_y": 0}},
            "video_from": {"y": 249, "pct": 38.9}, "fingerprint": "manual-shortem-hook-v2",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None,
            "channel_boxes": [
                {"x": 145, "y": 27, "width": 70, "height": 36, "background": "#FFE9A8", "color": "#050505", "radius": 0, "border": None, "font_size": 28, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -1.2},
                {"x": 80, "y": 101, "width": 57, "height": 30, "background": "#FFFFFF", "color": "#050505", "radius": 0, "border": None, "font_size": 21, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -1.0}
            ],
            "lines": [
                {"x0": 38, "x1": 322, "y0": 158, "y1": 184, "h": 27, "lpct": 10.6, "rpct": 10.6, "color": "#050505", "background": "#FFFFFF", "font_size": 23, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -1.2, "stroke": 0, "shadow_y": 0, "patch_top": 4, "patch_bottom": 5},
                {"x0": 102, "x1": 258, "y0": 210, "y1": 236, "h": 27, "lpct": 28.3, "rpct": 28.3, "color": "#050505", "background": "#FFFFFF", "font_size": 23, "font_family": "TmonMonsori", "font_weight": 400, "letter_spacing": -1.2, "stroke": 0, "shadow_y": 0, "patch_top": 5, "patch_bottom": 6},
            ],
            "white_box": None, "video_from": {"y": 250, "pct": 39.1}, "fingerprint": "manual-shortem-body-v2",
        },
    },
    "t01": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "font_family": "TmonMonsori", "font_weight": 400,
            "channel_box": {"x": 91, "y": 55, "width": 151, "height": 25, "background": "#FFFFFF", "color": "#111111", "radius": 0, "border": None, "font_size": 22},
            "lines": [
                {"x0": 5, "x1": 355, "y0": 127, "y1": 164, "h": 38, "lpct": 1.4, "rpct": 1.1, "color": "#FFFFFF", "background": "#FFFFFF", "font_size": 31, "accent": "#00EFEA", "accent_words": 1, "stroke": 2.2, "shadow_y": 4, "patch_top": 4, "patch_bottom": 7},
                {"x0": 73, "x1": 287, "y0": 168, "y1": 207, "h": 40, "lpct": 20.3, "rpct": 20.0, "color": "#00EFEA", "background": "#FFFFFF", "font_size": 32, "stroke": 2.2, "shadow_y": 4, "patch_top": 5, "patch_bottom": 9},
            ],
            "white_box": None, "video_from": {"y": 214, "pct": 33.4}, "fingerprint": "manual-t01-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "font_family": "TmonMonsori", "font_weight": 400,
            "channel_box": {"x": 91, "y": 55, "width": 151, "height": 25, "background": "#FFFFFF", "color": "#111111", "radius": 0, "border": None, "font_size": 22},
            "lines": [
                {"x0": 18, "x1": 353, "y0": 101, "y1": 126, "h": 26, "lpct": 5.0, "rpct": 1.7, "color": "#111111", "background": "#FFFFFF", "font_size": 20, "stroke": 0, "shadow_y": 0},
                {"x0": 72, "x1": 289, "y0": 161, "y1": 205, "h": 45, "lpct": 20.0, "rpct": 19.4, "color": "#111111", "background": "#FFFFFF", "font_size": 20, "stroke": 0, "shadow_y": 0, "max_lines": 2},
            ],
            "white_box": None, "video_from": {"y": 215, "pct": 33.6}, "fingerprint": "manual-t01-body-v1",
        },
    },
    "t02": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None, "font_family": "GmarketSansBold", "font_weight": 700,
            "lines": [
                {"x0": 10, "x1": 350, "y0": 118, "y1": 162, "h": 45, "lpct": 2.8, "rpct": 2.5, "color": "#050505", "background": "#FFFFFF", "font_size": 37, "stroke": 0, "shadow_y": 0, "patch_top": 5, "patch_bottom": 4},
                {"x0": 78, "x1": 282, "y0": 169, "y1": 213, "h": 45, "lpct": 21.7, "rpct": 21.4, "color": "#FF5D5E", "background": "#FFFFFF", "font_size": 37, "stroke": 0.8, "shadow_y": 0, "patch_top": 4, "patch_bottom": 6},
            ],
            "white_box": None, "video_from": {"y": 239, "pct": 37.3}, "fingerprint": "manual-t02-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None, "font_family": "BlackHanSans", "font_weight": 400,
            "channel_box": {"x": 103, "y": 38, "width": 151, "height": 37, "background": "#F77C7F", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 25},
            "lines": [
                {"x0": 50, "x1": 310, "y0": 102, "y1": 129, "h": 28, "lpct": 13.9, "rpct": 13.6, "color": "#080808", "background": "#FFFFFF", "font_size": 23, "stroke": 0, "shadow_y": 0, "patch_top": 4, "patch_bottom": 4},
                {"x0": 88, "x1": 273, "y0": 175, "y1": 225, "h": 51, "lpct": 24.4, "rpct": 23.9, "color": "#080808", "background": "#FFFFFF", "font_size": 22, "stroke": 0, "shadow_y": 0, "max_lines": 2, "patch_top": 5, "patch_bottom": 7},
            ],
            "white_box": None, "video_from": {"y": 239, "pct": 37.3}, "fingerprint": "manual-t02-body-v1",
        },
    },
    "t03": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#514D3D", "top_band": None, "cleanup_y0": 50, "font_family": "TmonMonsori", "font_weight": 400,
            "lines": [
                {"x0": 12, "x1": 348, "y0": 52, "y1": 94, "h": 43, "lpct": 3.3, "rpct": 3.1, "color": "#FFFFFF", "background": "#514D3D", "font_size": 38, "stroke": 3.0, "shadow_y": 2, "patch_top": 5, "patch_bottom": 4},
                {"x0": 37, "x1": 323, "y0": 101, "y1": 143, "h": 43, "lpct": 10.3, "rpct": 10.0, "color": "#2CFF44", "background": "#514D3D", "font_size": 38, "stroke": 3.0, "shadow_y": 2, "patch_top": 4, "patch_bottom": 8},
            ],
            "white_box": {"y0": 169, "y1": 212, "text": {"x0": 22, "x1": 338, "y0": 176, "y1": 204, "h": 29, "font_size": 24, "stroke": 0, "shadow_y": 0}},
            "video_from": {"y": 231, "pct": 36.1}, "fingerprint": "manual-t03-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None, "font_family": "GmarketSansBold", "font_weight": 700,
            "channel_box": {"x": 112, "y": 51, "width": 123, "height": 24, "background": "#FFFFFF", "color": "#111111", "radius": 0, "border": None, "font_size": 18},
            "lines": [
                {"x0": 43, "x1": 318, "y0": 99, "y1": 125, "h": 27, "lpct": 11.9, "rpct": 11.7, "color": "#111111", "background": "#FFFFFF", "font_size": 22, "stroke": 0, "shadow_y": 0, "patch_top": 4, "patch_bottom": 4},
                {"x0": 66, "x1": 294, "y0": 165, "y1": 207, "h": 43, "lpct": 18.3, "rpct": 18.1, "color": "#111111", "background": "#FFFFFF", "font_size": 20, "stroke": 0, "shadow_y": 0, "max_lines": 2, "patch_top": 5, "patch_bottom": 8},
            ],
            "white_box": None, "video_from": {"y": 221, "pct": 34.5}, "fingerprint": "manual-t03-body-v1",
        },
    },
    "t04": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#F8F7FF", "top_band": None, "font_family": "TmonMonsori", "font_weight": 400,
            "channel_box": {"x": 91, "y": 29, "width": 183, "height": 44, "background": "#FF5D5E", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 28},
            "boxes": [{"x": 45, "y": 100, "width": 270, "height": 100, "background": "#F8F7FF", "border": "#FFFFFF", "border_width": 3, "shadow": "0 3px 9px #111111"}],
            "lines": [
                {"x0": 50, "x1": 310, "y0": 110, "y1": 150, "h": 41, "lpct": 13.9, "rpct": 13.6, "color": "#FFFFFF", "background": "#F8F7FF", "font_size": 34, "stroke": 2.3, "shadow_y": 2, "skip_patch": True},
                {"x0": 50, "x1": 310, "y0": 153, "y1": 195, "h": 43, "lpct": 13.9, "rpct": 13.6, "color": "#35EF58", "background": "#F8F7FF", "font_size": 36, "stroke": 2.3, "shadow_y": 2, "skip_patch": True},
            ],
            "white_box": None, "video_from": {"y": 222, "pct": 34.7}, "fingerprint": "manual-t04-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#F8F7FF", "top_band": None, "font_family": "TmonMonsori", "font_weight": 400,
            "channel_box": {"x": 91, "y": 29, "width": 183, "height": 44, "background": "#FF5D5E", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 28},
            "lines": [
                {"x0": 46, "x1": 316, "y0": 103, "y1": 129, "h": 27, "lpct": 12.8, "rpct": 12.2, "color": "#080808", "background": "#F8F7FF", "font_size": 22, "stroke": 0, "shadow_y": 0, "patch_top": 4, "patch_bottom": 4},
                {"x0": 120, "x1": 241, "y0": 164, "y1": 188, "h": 25, "lpct": 33.3, "rpct": 33.1, "color": "#111111", "background": "#F8F7FF", "font_size": 21, "stroke": 0, "shadow_y": 0, "patch_top": 5, "patch_bottom": 6},
            ],
            "white_box": None, "video_from": {"y": 222, "pct": 34.7}, "fingerprint": "manual-t04-body-v1",
        },
    },
    "t06": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#D8D8D8", "cleanup_y0": 39,
            "font_family": "GasoekOne", "font_weight": 400,
            "lines": [
                {"x0": 12, "x1": 348, "y0": 43, "y1": 98, "h": 56, "color": "#FFFFFF", "background": "#D8D8D8", "font_size": 46, "letter_spacing": -0.8, "stroke": 1.3, "shadow_y": 1.2},
                {"x0": 24, "x1": 336, "y0": 102, "y1": 157, "h": 56, "color": "#FF3037", "background": "#D8D8D8", "font_size": 47, "letter_spacing": -0.8, "stroke": 1.3, "shadow_y": 1.2},
            ],
            "white_box": {"y0": 160, "y1": 214, "background": "#FFFFFF", "text": {"x0": 18, "x1": 342, "y0": 174, "y1": 202, "h": 29, "font_size": 22, "font_family": "GmarketSansBold", "font_weight": 400, "letter_spacing": -0.7, "stroke": 0, "shadow_y": 0}},
            "video_from": {"y": 215, "pct": 33.6}, "fingerprint": "manual-t06-premium-v1",
        },
    },
    "t12": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "cleanup_y0": 116,
            "font_family": "BlackHanSans", "font_weight": 400,
            "channel_box": {"x": 86, "y": 40, "width": 188, "height": 42, "background": "#002D3A", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 25, "font_family": "GmarketSansBold", "font_weight": 400},
            "lines": [
                {"x0": 22, "x1": 338, "y0": 126, "y1": 169, "h": 44, "color": "#090909", "background": "#FFFFFF", "font_size": 37, "letter_spacing": -1.2, "stroke": 0, "shadow_y": 0},
                {"x0": 47, "x1": 313, "y0": 174, "y1": 217, "h": 44, "color": "#090909", "background": "#FFFFFF", "font_size": 37, "letter_spacing": -1.2, "stroke": 0, "shadow_y": 0},
            ],
            "white_box": None, "video_from": {"y": 241, "pct": 37.7}, "fingerprint": "manual-t12-premium-v1",
        },
    },
    "t17": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "cleanup_y0": 79,
            "font_family": "Pretendard", "font_weight": 800,
            "channel_box": {"x": 67, "y": 38, "width": 226, "height": 27, "background": "#010101", "color": "#D8D8D8", "radius": 0, "border": None, "font_size": 20, "font_family": "Pretendard", "font_weight": 800},
            "lines": [
                {"x0": 30, "x1": 330, "y0": 91, "y1": 126, "h": 36, "color": "#111111", "background": "#FFFFFF", "font_size": 30, "letter_spacing": -0.9, "stroke": 0, "shadow_y": 0},
                {"x0": 62, "x1": 298, "y0": 132, "y1": 158, "h": 27, "color": "#868686", "background": "#FFFFFF", "font_size": 20, "letter_spacing": -0.5, "stroke": 0, "shadow_y": 0},
            ],
            "white_box": None, "video_from": {"y": 177, "pct": 27.7}, "fingerprint": "manual-t17-premium-v1",
        },
    },
    "t16": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#665D44", "top_band": {"y0": 0, "y1": 28, "color": "#665D44"},
            "font_family": "GasoekOne", "font_weight": 400,
            "lines": [
                {"x0": 22, "x1": 338, "y0": 69, "y1": 113, "h": 45, "color": "#FFFFFF", "background": "#665D44", "font_size": 38, "letter_spacing": -0.7, "stroke": 0.9, "shadow_y": 1.0},
                {"x0": 34, "x1": 326, "y0": 120, "y1": 171, "h": 52, "color": "#FFE45B", "background": "#665D44", "font_size": 44, "letter_spacing": -0.8, "stroke": 0.9, "shadow_y": 1.0},
            ],
            "white_box": {"y0": 192, "y1": 222, "background": "#FFFFFF", "text": None},
            "video_from": {"y": 223, "pct": 34.8}, "fingerprint": "manual-t16-premium-v1",
        },
    },
}

STORY_FOOTER_OVERRIDES = {"t09": 545, "t14": 554}
HOOK_TYPE_PROFILES = {
    # 한 폰트로 도배하지 않는다. 각 레퍼런스의 성격은 유지하되 훅 가독성만 상향한다.
    "t01": {"family": "TmonMonsori", "weight": 400, "tracking": -1.2, "stroke": 1.35, "shadow": 1.4},
    "t02": {"family": "Jalnan2", "weight": 400, "tracking": -0.65, "stroke": 0.7, "shadow": 0.8},
    "t03": {"family": "JalnanGothic", "weight": 400, "tracking": -0.85, "stroke": 1.2, "shadow": 1.15},
    "t04": {"family": "TmonMonsori", "weight": 400, "tracking": -1.2, "stroke": 1.25, "shadow": 1.3},
    "t05": {"family": "Jalnan2", "weight": 400, "tracking": -0.7, "stroke": 1.0, "shadow": 1.0},
    "t06": {"family": "GasoekOne", "weight": 400, "tracking": -0.8, "stroke": 1.3, "shadow": 1.2},
    "t07": {"family": "GmarketSansBold", "weight": 400, "tracking": -1.0, "stroke": 1.1, "shadow": 1.15},
    "t08": {"family": "JalnanGothic", "weight": 400, "tracking": -0.9, "stroke": 1.05, "shadow": 1.0},
    "t09": {"family": "GothicA1Black", "weight": 900, "tracking": -0.85, "stroke": 1.05, "shadow": 1.0},
    "t10": {"family": "GasoekOne", "weight": 400, "tracking": -1.15, "stroke": 0.9, "shadow": 1.0},
    "t11": {"family": "Jalnan2", "weight": 400, "tracking": -0.65, "stroke": 1.0, "shadow": 1.0},
    "t12": {"family": "BlackHanSans", "weight": 400, "tracking": -1.2, "stroke": 0, "shadow": 0},
    "t13": {"family": "Jalnan2", "weight": 400, "tracking": -0.75, "stroke": 1.0, "shadow": 1.0},
    "t14": {"family": "JalnanGothic", "weight": 400, "tracking": -0.9, "stroke": 1.05, "shadow": 1.0},
    "t15": {"family": "GmarketSansBold", "weight": 400, "tracking": -0.9, "stroke": 1.05, "shadow": 1.0},
    "t16": {"family": "GasoekOne", "weight": 400, "tracking": -1.1, "stroke": 0.9, "shadow": 1.0},
    "t17": {"family": "Pretendard", "weight": 800, "tracking": -0.9, "stroke": 0, "shadow": 0},
    "t19": {"family": "JalnanGothic", "weight": 400, "tracking": -0.85, "stroke": 1.05, "shadow": 1.0},
    "s0056": {"family": "GmarketSansBold", "weight": 400, "tracking": -0.9, "stroke": 1.0, "shadow": 1.0},
}

# 320px 실사용 미리보기로 20장을 한 장씩 검수한 뒤 잡은 훅 전용 좌표다.
# 자동 실측값의 ink bbox를 그대로 글자 박스로 쓰면 제목이 작아지므로 화면 설계 좌표를 별도로 둔다.
HOOK_VISUAL_PATCHES = {
    "s0101": {"cleanup_y0": 0, "channel_boxes": [],
        "channel_box": {"x": 105, "y": 18, "width": 150, "height": 42, "background": "#2B271D", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 25, "font_family": "TmonMonsori", "font_weight": 400}},
    "t01": {"family": "TmonMonsori", "lines": [
        {"font_size": 34, "letter_spacing": -1.2, "stroke": 1.35, "shadow_y": 1.4},
        {"font_size": 38, "letter_spacing": -1.4, "stroke": 1.35, "shadow_y": 1.4},
    ]},
    "t02": {"cleanup_y0": 96,
        "cleanup_regions_extra": [{"role": "header-clean", "x": 0, "y": 0, "width": 360, "height": 96, "background": "#F77C7F"}],
        "channel_box": {"x": 90, "y": 24, "width": 180, "height": 38, "background": "#F77C7F", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 25, "font_family": "GmarketSansBold", "font_weight": 400}},
    "t03": {"cleanup_y0": 50,
        "cleanup_regions_extra": [{"role": "header-clean", "x": 0, "y": 0, "width": 360, "height": 50, "background": "#514D3D"}],
        "channel_box": {"x": 90, "y": 11, "width": 180, "height": 29, "background": "#514D3D", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 20, "font_family": "GmarketSansBold", "font_weight": 400}},
    "t04": {"family": "TmonMonsori", "lines": [
        {"font_size": 35, "letter_spacing": -1.2, "stroke": 1.25, "shadow_y": 1.3},
        {"font_size": 38, "letter_spacing": -1.3, "stroke": 1.25, "shadow_y": 1.3},
    ]},
    "t05": {"lines": [
        {"font_size": 35, "y0": 101, "y1": 141, "h": 41},
        {"font_size": 38, "y0": 146, "y1": 190, "h": 45},
    ]},
    "t07": {"lines": [
        {"x0": 12, "x1": 348, "y0": 70, "y1": 109, "h": 40, "font_size": 38},
        {"x0": 35, "x1": 325, "y0": 115, "y1": 160, "h": 46, "font_size": 43},
    ]},
    "t08": {"lines": [
        {"x0": 15, "x1": 345, "y0": 78, "y1": 116, "h": 39, "font_size": 36},
        {"x0": 30, "x1": 330, "y0": 121, "y1": 162, "h": 42, "font_size": 40},
    ]},
    "t09": {"cleanup_y0": 0,
        "channel_box": {"x": 90, "y": 15, "width": 180, "height": 31, "background": "#17181B", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 21, "font_family": "GmarketSansBold", "font_weight": 400},
        "lines": [
        {"x0": 16, "x1": 344, "y0": 82, "y1": 121, "h": 40, "font_size": 39},
        {"x0": 12, "x1": 348, "y0": 126, "y1": 170, "h": 45, "font_size": 42},
    ]},
    "t12": {"cleanup_regions_extra": [{"role": "header-clean", "x": 0, "y": 0, "width": 360, "height": 116, "background": "#002D3A"}]},
    "t10": {"cleanup_y0": 55, "lines": [
        {"x0": 22, "x1": 338, "y0": 63, "y1": 102, "h": 40, "font_size": 36},
        {"x0": 12, "x1": 348, "y0": 108, "y1": 153, "h": 46, "font_size": 42},
    ], "white_box": {"y0": 169, "y1": 204, "background": "#FFFFFF", "text": None}},
    "t11": {"lines": [
        {"x0": 16, "x1": 344, "y0": 79, "y1": 120, "h": 42, "font_size": 37},
        {"x0": 12, "x1": 348, "y0": 126, "y1": 171, "h": 46, "font_size": 41},
    ]},
    "t13": {"family": "Jalnan2", "cleanup_y0": 0, "video_from": {"y": 254, "pct": 39.7}, "lines": [
        {"x0": 18, "x1": 342, "y0": 52, "y1": 92, "h": 41, "font_size": 37},
        {"x0": 14, "x1": 346, "y0": 98, "y1": 143, "h": 46, "font_size": 42},
    ], "white_box": {"y0": 185, "y1": 253, "background": "#FFFFFF", "text": None}},
    "t14": {"family": "JalnanGothic", "cleanup_y0": 0, "lines": [
        {"x0": 15, "x1": 345, "y0": 43, "y1": 83, "h": 41, "font_size": 37},
        {"x0": 10, "x1": 350, "y0": 91, "y1": 143, "h": 53, "font_size": 45},
    ]},
    "t15": {"family": "GmarketSansBold", "cleanup_y0": 54,
        "cleanup_regions_extra": [{"role": "header-clean", "x": 0, "y": 0, "width": 360, "height": 54, "background": "#557E78"}],
        "channel_box": {"x": 92, "y": 14, "width": 176, "height": 30, "background": "#557E78", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 22, "font_family": "GmarketSansBold", "font_weight": 400},
        "lines": [
            {"x0": 15, "x1": 345, "y0": 64, "y1": 105, "h": 42, "font_size": 38},
            {"x0": 12, "x1": 348, "y0": 111, "y1": 157, "h": 47, "font_size": 42},
        ]},
    "t17": {"cleanup_regions_extra": [{"role": "header-clean", "x": 0, "y": 0, "width": 360, "height": 79, "background": "#010101"}]},
    "t19": {"family": "JalnanGothic", "lines": [
        {"x0": 16, "x1": 344, "y0": 45, "y1": 86, "h": 42, "font_size": 38, "color": "#FFFFFF"},
        {"x0": 12, "x1": 348, "y0": 94, "y1": 142, "h": 49, "font_size": 44, "color": "#00F0E8"},
    ], "white_box": {"y0": 169, "y1": 240, "background": "#FFFFFF", "text": None}},
    "s0056": {"family": "GmarketSansBold", "cleanup_y0": 0, "video_from": {"y": 161, "pct": 37.8},
        "channel_box": {"x": 64, "y": 12, "width": 112, "height": 27, "background": "#000000", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 18, "font_family": "GmarketSansBold", "font_weight": 400},
        "lines": [
            {"x0": 8, "x1": 232, "y0": 45, "y1": 76, "h": 32, "font_size": 28, "color": "#FFFFFF"},
            {"x0": 7, "x1": 233, "y0": 80, "y1": 116, "h": 37, "font_size": 32, "color": "#F2CC11"},
        ], "white_box": {"y0": 127, "y1": 160, "background": "#D7D7D7", "text": None}},
}


def apply_hook_visual_patch(frame: dict | None, key: str) -> dict | None:
    if not frame or key not in HOOK_VISUAL_PATCHES:
        return frame
    patch = HOOK_VISUAL_PATCHES[key]
    if "family" in patch:
        frame["font_family"] = patch["family"]
    for field in ("cleanup_y0", "video_from", "white_box", "channel_box", "channel_boxes", "cleanup_regions_extra"):
        if field in patch:
            frame[field] = patch[field]
    if "lines" in patch:
        source_lines = frame.get("lines", [])
        frame["lines"] = []
        for index, line_patch in enumerate(patch["lines"]):
            base = dict(source_lines[index]) if index < len(source_lines) else {}
            base.update(line_patch)
            frame["lines"].append(base)
    return frame


def load_measure(key: str) -> tuple[dict, str, str]:
    if key.startswith("t"):
        found = sorted(TOP.glob(f"{key}_*.json"))
        if not found:
            raise FileNotFoundError(key)
        data = json.loads(found[0].read_text(encoding="utf-8"))
        stem = key
        return data, f"장면꾸미기_작업대/스타일수집/top20_views/{stem}_hook.png", f"장면꾸미기_작업대/스타일수집/top20_views/{stem}_body.png"
    styles = json.loads((COLLECT / "final_styles.json").read_text(encoding="utf-8"))
    data = next(row for row in styles if row["slug"] == key)
    if key == "s0101":
        return data, "장면꾸미기_작업대/원본프레임/숏템_훅.png", "장면꾸미기_작업대/원본프레임/숏템_본문.png"
    return data, f"장면꾸미기_작업대/스타일수집/프레임/{key}_{data['name']}_훅.png", f"장면꾸미기_작업대/스타일수집/프레임/{key}_{data['name']}_본문.png"


def compact_frame(frame: dict | None) -> dict | None:
    if not frame:
        return None
    if "size" in frame:
        width, height = map(int, frame["size"].split("x"))
    else:
        width, height = frame["width"], frame["height"]
    lines = frame.get("lines", [])
    title_lines = [line for line in lines if "y0" in line and "y1" in line]
    cleanup_regions = []
    if title_lines:
        top_band = frame.get("top_band")
        channel_boxes = frame.get("channel_boxes", []) or ([frame["channel_box"]] if frame.get("channel_box") else [])
        if frame.get("cleanup_y0") is not None:
            y0 = min(height, frame["cleanup_y0"])
        elif channel_boxes:
            y0 = min(height, max(box["y"] + box["height"] for box in channel_boxes) + 10)
        elif top_band:
            y0 = min(height, top_band["y1"] + 1)
        else:
            y0 = min(line["y0"] for line in title_lines) - 22
        # 제목과 흰 설명띠 사이에 남던 원본 글자/로고까지 영상 시작점 직전에서 전부 지운다.
        y1 = min(height, (frame.get("video_from") or {}).get("y", max(line["y1"] for line in title_lines) + 16))
        cleanup_regions.append({
            "role": "original-title", "x": 0, "y": y0, "width": width,
            "height": y1 - y0, "background": frame.get("title_bg") or "#111111",
        })
    cleanup_regions.extend(frame.get("cleanup_regions_extra", []))
    return {
        "width": width,
        "height": height,
        "top_band": frame.get("top_band"),
        "title_bg": frame.get("title_bg"),
        "font_family": frame.get("font_family"),
        "font_weight": frame.get("font_weight"),
        "lines": lines,
        "white_box": frame.get("white_box"),
        "video_from": frame.get("video_from"),
        "fingerprint": frame.get("fingerprint"),
        "channel_box": frame.get("channel_box"),
        "channel_boxes": frame.get("channel_boxes", []),
        "boxes": frame.get("boxes", []),
        "cleanup_regions": cleanup_regions,
    }


def polish_hook(frame: dict | None, key: str) -> dict | None:
    if not frame or key == "s0101":
        return frame
    profile = HOOK_TYPE_PROFILES.get(key, {"family": "JalnanGothic", "weight": 400, "tracking": -0.8, "stroke": 1.0, "shadow": 1.0})
    family = profile["family"]
    frame["font_family"] = family
    frame["font_weight"] = profile["weight"]
    for line in frame.get("lines", []):
        line["font_family"] = family
        line["font_weight"] = frame["font_weight"]
        line["letter_spacing"] = min(float(line.get("letter_spacing", profile["tracking"])), profile["tracking"])
        # 굵기는 폰트 자체로 만든다. 테두리와 그림자는 영상 위 분리용 보조 수단이다.
        line["stroke"] = min(float(line.get("stroke") or profile["stroke"]), profile["stroke"])
        line["shadow_y"] = min(float(line.get("shadow_y") or profile["shadow"]), profile["shadow"])
    return frame


def add_footer_cleanup(frame: dict | None, image_path: str, key: str) -> dict | None:
    if not frame:
        return frame
    path = ROOT / "out" / image_path
    slot = detect_bottom_caption_slot(path)
    if key in STORY_FOOTER_OVERRIDES:
        y = STORY_FOOTER_OVERRIDES[key]
        slot.update({"mode": "reserved", "y": y, "height": frame["height"] - y,
                     "ratio": round((frame["height"] - y) / frame["height"], 3)})
    slot = extend_reserved_slot_over_source_text(path, slot)
    if slot["mode"] == "reserved":
        frame["cleanup_regions"].append({
            "role": "source-footer", "x": 0, "y": slot["y"], "width": frame["width"],
            "height": frame["height"] - slot["y"], "background": slot["background"],
        })
    return frame


def main() -> None:
    rows = []
    for rank, name, views, key in META:
        measured, hook_path, body_path = load_measure(key)
        if key in MANUAL:
            measured = {**measured, **MANUAL[key]}
        if key == "t07":
            measured["hook"]["lines"][0].update({"font_size": 31})
            measured["hook"]["lines"][1].update({"color": "#00F9ED", "font_size": 39})
        if key == "t05" and len(measured.get("hook", {}).get("lines", [])) > 1:
            measured["hook"]["lines"][1]["color"] = "#FF7F9D"
        measured["hook"] = apply_hook_visual_patch(measured.get("hook"), key)
        sample = SAMPLES.get(name, [f"{name}에서 발견한", "놀라운 생활 아이디어"])
        rows.append({
            "rank": rank,
            "id": key,
            "name": name,
            "views": views,
            "hook_image": hook_path,
            "body_image": body_path,
            "sample": {"hook1": sample[0], "hook2": sample[1], "bodyTitle": " ".join(sample), "caption": "이런 방법이 있었네요"},
            "hook": add_footer_cleanup(polish_hook(compact_frame(measured.get("hook")), key), hook_path, key),
            "body": add_footer_cleanup(compact_frame(measured.get("body")), body_path, f"{key}-body"),
        })
    rows.sort(key=lambda row: (row["id"] != "s0101", int(row["rank"])))
    text = "window.PRECISION20=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n"
    DEST.write_text(text, encoding="utf-8")
    print(f"{DEST} ({len(rows)} presets)")


if __name__ == "__main__":
    main()
