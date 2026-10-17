# -*- coding: utf-8 -*-
"""핫템리포트 틀(frame_OE11/로봇폰) → 숏템리폿 새 판(10-17 v2): 원작 템플릿과 8항목 중 6+ 다르게. 제목 글만 원본에서 가져온다."""
import json
from pathlib import Path
H = Path(__file__).resolve().parent
NAVY, BAND, GOLD, OFF, GRAY, BOXC, R = [13, 20, 40], [20, 31, 60], [205, 170, 110], [244, 245, 248], [160, 171, 192], [18, 27, 52], 14   # 남색 계열 + 중성 + 포인트 1색(샴페인 골드)
def make(src, dst):
    o = json.loads((H / src).read_text(encoding="utf-8"))
    title = next(l for l in o["layers"] if l.get("role") == "title")
    cap = next(l for l in o["layers"] if l.get("role") == "caption")
    t = dict(title, x=64, y=96, w=952, align="left", font="PretendardXBold", size=100, line_h=106, rgb=OFF,
             line_rgb=[GRAY, OFF], line_scale=[0.46, 1.0], outline=None, line_outline=[[0, 0, 0, 0], [0, 0, 0, 0]],
             shadow=None, glow=None, box=None)
    c = dict(cap, font="CcPretendard-Bold", size=68, line_h=96, y=1540, w=1000, rgb=OFF, outline=None,
             box={"rgb": BOXC, "pad": 20, "radius": R})
    brand = {"kind": "text", "role": "brand", "text": "숏템리폿", "x": 64, "y": 52, "w": 360, "align": "left", "lines": 1, "font": "GmarketSansBold",
             "size": 34, "line_h": 40, "rgb": GOLD, "outline": None, "shadow": None, "glow": None,
             "box": {"rgb": BOXC, "pad": 12, "radius": R}, "italic": False, "letter_spacing": 3}
    d = {"canvas": [1080, 1920], "template_off": None, "made_by": "calcopy_frame v1 · 숏템리폿 v2(10-17)", "source": f"{src} 의 제목 글만 · 나머지 새 설계(깊은 남색+중성+골드 1색·Pretendard 위계·왼쪽 라벨 채널명·박스 자막·가는 골드 선)",
         "layers": [{"kind": "bg", "rgb": NAVY},
                    {"kind": "video", "x": 0, "y": 340, "w": 1080, "h": 1580, "radius": 0},
                    {"kind": "band", "x": 0, "y": 0, "w": 1080, "h": 330, "rgb": BAND, "radius": 0},
                    {"kind": "band", "x": 64, "y": 330, "w": 120, "h": 3, "rgb": GOLD, "radius": 0},
                    brand, t, c]}
    (H / dst).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
make("칼카피_OE11/frame_OE11.json", "칼카피_OE11/frame_숏템리폿.json")
make("칼카피_로봇폰/frame_로봇폰.json", "칼카피_로봇폰/frame_숏템리폿.json")
