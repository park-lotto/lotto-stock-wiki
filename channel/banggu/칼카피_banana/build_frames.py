# -*- coding: utf-8 -*-
"""방구석 2편(바나나맛우유) 틀 2장 — 1편 ILIiqCJAOSI(아웃백) 실측 틀 그대로, 글만 바꿈. 원 설명: — 훅 카드 / 본문 게시글. 원본 프레임(0.8초·5.5초·9.0초) 픽셀 실측값으로 손 작성.
to_frame_multi 자동 결과(frame_auto.json)는 OCR 글이 없어(제미나이 429) 글자 층 9개가 전부 빠지고 훅 카드 띠를 y236~750 회색 한 장으로 잡아
손으로 만든다(결함은 보고에만). 크기·y 는 to_frame.size_and_top(잉크 위 끝·잉크 높이 → 글자 크기·줄 칸 y) — 틀 담당 함수 재사용.
    PYTHONUTF8=1 py channel/banggu/칼카피_ILIi/build_frames.py <출력 폴더>
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import to_frame as T
from shopping_shorts.calcopy_frame import schema

OUT = Path(sys.argv[1])
BRAND = "골방"          # 원본 손글씨 로고 '방구석' 자리 — 남의 채널 이름은 그대로 안 쓴다(rGFX 선례 '맛잘알 친구들'). 바꾸려면 여기 한 곳
POST = "50년째 모양을 못 바꾼다는 바나나맛우유"     # 게시글 제목 = 훅 띠 문장 = 나레 첫 문장
HOOK = ("바나나우유", "50년째 못 바꾼 모양")   # 첫 줄은 짧게(≡·돋보기 안 덮게, 1편 조율자 지적)
# 돋보기(원본 x904~987 y128~211, 검정 선) — 텍스트 글꼴에 없는 모양이라 작은 SVG 그림 층(공백·따옴표 없는 data URI, 300자 제한)
SEARCH = ("data:image/svg+xml,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27%20viewBox=%270%200%2084%2084%27%20fill=%27none%27"
          "%20stroke=%27black%27%20stroke-width=%277%27%3E%3Ccircle%20cx=%2734%27%20cy=%2734%27%20r=%2728%27/%3E%3Cpath%20d=%27M54%2054L80%2080%27/%3E%3C/svg%3E")


def text(role, fam, sample, ink_top, ink_h, x, w, align, rgb, lines=1, line_h=None, **kw):
    f = T.size_and_top(fam, sample, ink_top, ink_h, line_h)
    d = {"kind": "text", "role": role, "x": x, "y": f["y"], "w": w, "align": align, "lines": lines, "font": fam,
         "size": f["size"], "line_h": f["line_h"], "rgb": rgb, "line_rgb": None, "outline": None, "shadow": None, "box": None,
         "italic": False, "letter_spacing": 0, "word_spacing": 0, "enter": None}
    d.update(kw)
    return d


def head(bar_rgb, band_rgb):
    """머리띠 공통: 띠 y0~233 · 아래 검은 줄 y236~239 · ≡ 막대 3개(x79~166, y130·160·193 높이 10) · 돋보기."""
    return [{"kind": "band", "x": 0, "y": 0, "w": 1080, "h": 234, "rgb": band_rgb, "radius": 0},
            {"kind": "band", "x": 0, "y": 236, "w": 1080, "h": 4, "rgb": [36, 4, 0], "radius": 0},
            *[{"kind": "band", "x": 79, "y": y, "w": 88, "h": 10, "rgb": bar_rgb, "radius": 0} for y in (130, 160, 193)],
            {"kind": "image", "src": SEARCH, "x": 904, "y": 128, "w": 84, "h": 84}]


body = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": "ILIiqCJAOSI(틀) · 바나나맛우유 2편",
        "made_from": {"tool": "channel/banggu/칼카피_ILIi/build_frames.py",
                      "note": "원본 5.5·9.0초 실측: 바탕 253 · 머리띠 (42,161,253) y0~233 · 검은 줄 y236~239 · 로고 잉크 y120~219 · 제목 잉크 y275~342 x96~980 · 부제 회색(90) y373~411 x125~412 · 가로줄 y446~450 x60~1019 (70,70,70) · 자막 잉크 y502~551/580~630(줄 칸 79) · 그림 칸 자막 아래(뜯기2 picture_boxes)"},
        "layers": [
            {"kind": "bg", "rgb": [253, 253, 253]},
            {"kind": "video", "x": 0, "y": 660, "w": 1080, "h": 1260, "radius": 0},
            *head([0, 0, 0], [42, 161, 253]),
            text("brand", "Kkubulim", BRAND, 120, 100, 530, 400, "center", [0, 0, 0], text=BRAND),
            text("label", "CcPretendard-Bold", POST, 275, 68, 540, 960, "center", [0, 0, 0], text=POST),
            text("label", "CcPretendard-SemiBold", BRAND + " | 14:25", 375, 33, 125, 600, "left", [90, 88, 89], text=BRAND + " | 14:25", word_spacing=14),
            {"kind": "band", "x": 60, "y": 446, "w": 960, "h": 5, "rgb": [70, 70, 70], "radius": 0},
            text("caption", "CcPretendard-Bold", "아웃백에서 사람들이", 502, 50, 540, 1000, "center", [0, 0, 0], lines=2, line_h=79, valign="top"),
        ]}
hook = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": "ILIiqCJAOSI(틀) · 바나나맛우유 2편",
        "made_from": {"tool": "channel/banggu/칼카피_ILIi/build_frames.py",
                      "note": "원본 0.8초 훅 카드 실측: 본문 틀을 어둡게(바탕 95 · 머리띠 (15,59,95) · 창 아래 125) · 제목 2줄 흰(잉크 y135~232)/파랑 (43,162,252)(y258~354, x92~984) 검정 외곽선 (0,1,20) · 흰 띠 y540~800(위아래 번짐, 꽉 찬 곳 596~728) 안 검정 문장 잉크 y636~682 x227~853 · 영상 창 y760~1814 전폭"},
        "layers": [
            {"kind": "bg", "rgb": [95, 95, 95]},
            {"kind": "video", "x": 0, "y": 760, "w": 1080, "h": 1056, "radius": 0},
            {"kind": "band", "x": 0, "y": 1816, "w": 1080, "h": 104, "rgb": [125, 125, 125], "radius": 0},
            *head([0, 0, 2], [15, 59, 95]),
            {"kind": "band", "x": 60, "y": 446, "w": 960, "h": 5, "rgb": [17, 19, 19], "radius": 0},
            {"kind": "band", "x": 0, "y": 540, "w": 1080, "h": 262, "rgb": [253, 253, 253], "radius": 0, "fade": [56, 74]},
            {"kind": "band", "x": 0, "y": 583, "w": 1080, "h": 2, "rgb": [60, 60, 60], "radius": 0},   # 흰 띠 위·아래 가는 선(원본 y583~584·736 어두운 행)
            {"kind": "band", "x": 0, "y": 736, "w": 1080, "h": 1, "rgb": [60, 60, 60], "radius": 0},
            text("label", "CcPretendard-SemiBold", BRAND + " | 14:25", 375, 33, 125, 600, "left", [34, 33, 33], text=BRAND + " | 14:25", word_spacing=14),
            text("label", "CcPretendard-Regular", POST, 636, 47, 540, 960, "center", [0, 0, 0], text=POST),
            text("title", "JalnanGothic", HOOK[0], 135, 98, 540, 980, "center", [255, 255, 255], lines=2, line_h=123,
                 text="\n".join(HOOK), line_rgb=[[255, 255, 255], [43, 162, 252]], outline={"px": 6, "rgb": [0, 1, 20]},
                 shadow={"dx": 3, "dy": 4, "blur": 2, "rgb": [0, 1, 20]}),
        ]}
for name, f in (("frame_body.json", body), ("frame_hook.json", hook)):
    schema.validate(f)
    (OUT / name).write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok", name, len(f["layers"]), "층")
