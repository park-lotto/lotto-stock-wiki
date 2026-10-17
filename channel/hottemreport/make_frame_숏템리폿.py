# -*- coding: utf-8 -*-
"""숏템리폿 v3(사장님 샘플 B 블랙·핑크네온, 10-17): mock.py 값 그대로. 제목 글만 원본 frame 에서."""
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parent
BLACK, CORE, GLOW, PINK = [8, 8, 12], [255, 230, 245], [255, 50, 165], [255, 130, 195]
Y_BRAND, Y_T1, Y_T2 = int(sys.argv[1]) if len(sys.argv) > 1 else 62, int(sys.argv[2]) if len(sys.argv) > 2 else 212, int(sys.argv[3]) if len(sys.argv) > 3 else 338
def make(src, dst):
    o = json.loads((H / src).read_text(encoding="utf-8"))
    title = next(l for l in o["layers"] if l.get("role") == "title")
    cap = next(l for l in o["layers"] if l.get("role") == "caption")
    t = dict(title, x=540, y=Y_T1, w=1040, align="center", font="BlackHanSans", size=136, line_h=126, rgb=[255, 255, 255],
             line_rgb=[[255, 255, 255], PINK], line_scale=[94 / 136, 1.0], outline=None, line_outline=None,
             shadow={"dx": 0, "dy": 5, "blur": 0, "rgb": [0, 0, 0]}, glow=None, box=None)
    c = dict(cap, font="CcPretendard-Bold", size=62, line_h=88, y=1500, w=1000, rgb=[255, 255, 255], outline=None,
             box={"rgb": [10, 10, 14], "pad": 30, "radius": 22})   # 알파 205 는 스키마에 없다 — 불투명 블랙
    def brand(px):
        return {"kind": "text", "role": "brand", "text": "숏템리폿", "x": 540, "y": Y_BRAND, "w": 700, "align": "center", "lines": 1, "font": "GmarketSansBold",
                "size": 70, "line_h": 80, "rgb": CORE, "outline": None, "shadow": None, "glow": {"px": px, "rgb": GLOW}, "box": None, "italic": False, "letter_spacing": 0}
    d = {"canvas": [1080, 1920], "template_off": None, "made_by": "calcopy_frame v1 · 숏템리폿 v3(샘플B)", "source": f"{src} 의 제목 글만 · 블랙 띠 560+48 그라데이션·핑크 네온 채널명·BlackHanSans 흰/핑크 제목·박스 자막",
         "layers": [{"kind": "bg", "rgb": BLACK},
                    {"kind": "video", "x": 0, "y": 560, "w": 1080, "h": 1360, "radius": 0},
                    {"kind": "band", "x": 0, "y": 0, "w": 1080, "h": 608, "rgb": BLACK, "radius": 0, "fade": [0, 48]},
                    brand(30), brand(16), brand(7), brand(2),
                    {"kind": "band", "x": 470, "y": 172, "w": 140, "h": 3, "rgb": GLOW, "radius": 0},
                    t, c]}
    (H / dst).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
make("칼카피_OE11/frame_OE11.json", "칼카피_OE11/frame_숏템리폿.json")
make("칼카피_로봇폰/frame_로봇폰.json", "칼카피_로봇폰/frame_숏템리폿.json")
