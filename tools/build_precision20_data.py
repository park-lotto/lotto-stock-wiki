# -*- coding: utf-8 -*-
"""조회수 검증 20세트의 훅·본문 실측 JSON을 사용자 UI용 단일 데이터로 묶는다.

원본 프레임과 실측값이 정의처다. UI 안에 좌표를 두 번 적지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path


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
}

# 자동 실측기를 원본 프레임과 픽셀 대조해 수정한 값.
# 이 표에 들어온 프리셋만 "초정밀" 검수 대상이다.
MANUAL = {
    "s0101": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#2B271D", "top_band": None,
            "channel_boxes": [
                {"x": 145, "y": 27, "width": 70, "height": 36, "background": "#2B271D", "color": "#050505", "radius": 0, "border": None, "font_size": 28}
            ],
            "lines": [
                {"x0": 9, "x1": 351, "y0": 70, "y1": 130, "h": 61, "lpct": 2.5, "rpct": 2.5, "color": "#FFFFFF", "background": "#2B271D", "font_size": 52, "stroke": 3.1, "shadow_y": 4, "patch_top": 5, "patch_bottom": 5},
                {"x0": 10, "x1": 350, "y0": 134, "y1": 188, "h": 55, "lpct": 2.8, "rpct": 2.8, "color": "#FFE500", "background": "#2B271D", "font_size": 47, "stroke": 3.1, "shadow_y": 4, "patch_top": 4, "patch_bottom": 5},
            ],
            "white_box": {"y0": 191, "y1": 248, "text": {"x0": 20, "x1": 340, "y0": 207, "y1": 236, "h": 30, "font_size": 24, "stroke": 0, "shadow_y": 0}},
            "video_from": {"y": 249, "pct": 38.9}, "fingerprint": "manual-shortem-hook-v2",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None,
            "channel_boxes": [
                {"x": 145, "y": 27, "width": 70, "height": 36, "background": "#FFE9A8", "color": "#050505", "radius": 0, "border": None, "font_size": 28},
                {"x": 80, "y": 101, "width": 57, "height": 30, "background": "#FFFFFF", "color": "#050505", "radius": 0, "border": None, "font_size": 21}
            ],
            "lines": [
                {"x0": 38, "x1": 322, "y0": 158, "y1": 184, "h": 27, "lpct": 10.6, "rpct": 10.6, "color": "#050505", "background": "#FFFFFF", "font_size": 23, "stroke": 0, "shadow_y": 0, "patch_top": 4, "patch_bottom": 5},
                {"x0": 102, "x1": 258, "y0": 210, "y1": 236, "h": 27, "lpct": 28.3, "rpct": 28.3, "color": "#050505", "background": "#FFFFFF", "font_size": 23, "stroke": 0, "shadow_y": 0, "patch_top": 5, "patch_bottom": 6},
            ],
            "white_box": None, "video_from": {"y": 250, "pct": 39.1}, "fingerprint": "manual-shortem-body-v2",
        },
    },
    "t01": {
        "hook": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF",
            "channel_box": {"x": 91, "y": 55, "width": 151, "height": 25, "background": "#FFFFFF", "color": "#111111", "radius": 0, "border": None, "font_size": 22},
            "lines": [
                {"x0": 5, "x1": 355, "y0": 127, "y1": 164, "h": 38, "lpct": 1.4, "rpct": 1.1, "color": "#FFFFFF", "background": "#FFFFFF", "font_size": 31, "accent": "#00EFEA", "accent_words": 1, "stroke": 2.2, "shadow_y": 4, "patch_top": 4, "patch_bottom": 7},
                {"x0": 73, "x1": 287, "y0": 168, "y1": 207, "h": 40, "lpct": 20.3, "rpct": 20.0, "color": "#00EFEA", "background": "#FFFFFF", "font_size": 32, "stroke": 2.2, "shadow_y": 4, "patch_top": 5, "patch_bottom": 9},
            ],
            "white_box": None, "video_from": {"y": 214, "pct": 33.4}, "fingerprint": "manual-t01-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF",
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
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None,
            "lines": [
                {"x0": 10, "x1": 350, "y0": 118, "y1": 162, "h": 45, "lpct": 2.8, "rpct": 2.5, "color": "#050505", "background": "#FFFFFF", "font_size": 37, "stroke": 0, "shadow_y": 0, "patch_top": 5, "patch_bottom": 4},
                {"x0": 78, "x1": 282, "y0": 169, "y1": 213, "h": 45, "lpct": 21.7, "rpct": 21.4, "color": "#050505", "background": "#FFFFFF", "font_size": 37, "stroke": 0, "shadow_y": 0, "patch_top": 4, "patch_bottom": 6},
            ],
            "white_box": None, "video_from": {"y": 239, "pct": 37.3}, "fingerprint": "manual-t02-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None,
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
            "width": 360, "height": 640, "title_bg": "#514D3D", "top_band": None,
            "lines": [
                {"x0": 12, "x1": 348, "y0": 52, "y1": 94, "h": 43, "lpct": 3.3, "rpct": 3.1, "color": "#FFFFFF", "background": "#514D3D", "font_size": 38, "stroke": 2.2, "shadow_y": 2, "patch_top": 5, "patch_bottom": 4},
                {"x0": 37, "x1": 323, "y0": 101, "y1": 143, "h": 43, "lpct": 10.3, "rpct": 10.0, "color": "#31F65C", "background": "#514D3D", "font_size": 38, "stroke": 2.2, "shadow_y": 2, "patch_top": 4, "patch_bottom": 8},
            ],
            "white_box": {"y0": 169, "y1": 212, "text": {"x0": 22, "x1": 338, "y0": 176, "y1": 204, "h": 29, "font_size": 24, "stroke": 0, "shadow_y": 0}},
            "video_from": {"y": 231, "pct": 36.1}, "fingerprint": "manual-t03-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#FFFFFF", "top_band": None,
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
            "width": 360, "height": 640, "title_bg": "#F8F7FF", "top_band": None,
            "channel_box": {"x": 91, "y": 29, "width": 183, "height": 44, "background": "#FF5D5E", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 28},
            "boxes": [{"x": 74, "y": 111, "width": 214, "height": 81, "background": "#F8F7FF", "border": "#FFFFFF", "border_width": 4, "shadow": "0 3px 9px #111111"}],
            "lines": [
                {"x0": 84, "x1": 279, "y0": 120, "y1": 151, "h": 32, "lpct": 23.3, "rpct": 22.2, "color": "#FFFFFF", "background": "#F8F7FF", "font_size": 26, "stroke": 2.3, "shadow_y": 2, "skip_patch": True},
                {"x0": 86, "x1": 278, "y0": 154, "y1": 187, "h": 34, "lpct": 23.9, "rpct": 22.5, "color": "#35EF58", "background": "#F8F7FF", "font_size": 27, "stroke": 2.3, "shadow_y": 2, "skip_patch": True},
            ],
            "white_box": None, "video_from": {"y": 222, "pct": 34.7}, "fingerprint": "manual-t04-hook-v1",
        },
        "body": {
            "width": 360, "height": 640, "title_bg": "#F8F7FF", "top_band": None,
            "channel_box": {"x": 91, "y": 29, "width": 183, "height": 44, "background": "#FF5D5E", "color": "#FFFFFF", "radius": 0, "border": None, "font_size": 28},
            "lines": [
                {"x0": 46, "x1": 316, "y0": 103, "y1": 129, "h": 27, "lpct": 12.8, "rpct": 12.2, "color": "#080808", "background": "#F8F7FF", "font_size": 22, "stroke": 0, "shadow_y": 0, "patch_top": 4, "patch_bottom": 4},
                {"x0": 120, "x1": 241, "y0": 164, "y1": 188, "h": 25, "lpct": 33.3, "rpct": 33.1, "color": "#111111", "background": "#F8F7FF", "font_size": 21, "stroke": 0, "shadow_y": 0, "patch_top": 5, "patch_bottom": 6},
            ],
            "white_box": None, "video_from": {"y": 222, "pct": 34.7}, "fingerprint": "manual-t04-body-v1",
        },
    }
}


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
    return {
        "width": width,
        "height": height,
        "top_band": frame.get("top_band"),
        "title_bg": frame.get("title_bg"),
        "lines": frame.get("lines", []),
        "white_box": frame.get("white_box"),
        "video_from": frame.get("video_from"),
        "fingerprint": frame.get("fingerprint"),
        "channel_box": frame.get("channel_box"),
        "channel_boxes": frame.get("channel_boxes", []),
        "boxes": frame.get("boxes", []),
    }


def main() -> None:
    rows = []
    for rank, name, views, key in META:
        measured, hook_path, body_path = load_measure(key)
        if key in MANUAL:
            measured = {**measured, **MANUAL[key]}
        sample = SAMPLES.get(name, [f"{name}에서 발견한", "놀라운 생활 아이디어"])
        rows.append({
            "rank": rank,
            "id": key,
            "name": name,
            "views": views,
            "hook_image": hook_path,
            "body_image": body_path,
            "sample": {"hook1": sample[0], "hook2": sample[1], "bodyTitle": " ".join(sample), "caption": "이런 방법이 있었네요"},
            "hook": compact_frame(measured.get("hook")),
            "body": compact_frame(measured.get("body")),
        })
    rows.sort(key=lambda row: (row["id"] != "s0101", int(row["rank"])))
    text = "window.PRECISION20=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n"
    DEST.write_text(text, encoding="utf-8")
    print(f"{DEST} ({len(rows)} presets)")


if __name__ == "__main__":
    main()
