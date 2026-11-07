# 경로·설정·글꼴·공용 계산
import os, sys, re, json, math, wave, subprocess, importlib.util, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(HERE, *a)                     # 공용 재료(글꼴·효과음·배경음)
WORK = os.path.abspath(os.environ.get("SHORCL_WORK") or os.getcwd())   # 편마다 다른 것(대본·샷·녹음·그림·결과)
E = lambda *a: os.path.join(WORK, *a)
CFG = json.load(open(P("channel.json"), encoding="utf-8"))
if os.path.exists(E("channel.json")) and E("channel.json") != P("channel.json"):
    CFG.update(json.load(open(E("channel.json"), encoding="utf-8")))
W, H = CFG["width"], CFG["height"]; FPS = CFG["fps_num"] / CFG["fps_den"]
C = {k: tuple(v) for k, v in CFG["colors"].items()}
spec = importlib.util.spec_from_file_location("shots", E("장면표.py")); SH = importlib.util.module_from_spec(spec); spec.loader.exec_module(SH)
for _s in SH.S:
    if _s.get("article"):
        if os.path.exists(E("material", "news", _s["article"] + ".png")) and os.path.exists(E("material", "news", _s["article"] + ".json")):
            _s["type"] = "article"; _s.pop("src", None)
        else: print(f"[경고] 기사 캡처 없음 {_s['article']} — 글자 카드로 대신함", flush=True)
NARR = E("voice"); BUILD = E("_work"); os.makedirs(BUILD, exist_ok=True)

_fc = {}
def face(name, size):
    k = (name, size)
    if k not in _fc:
        path = {"B": "Pretendard-Bold.otf", "XB": "Pretendard-ExtraBold.otf", "K": "Pretendard-Black.otf", "M": "Pretendard-Medium.otf",
                "R": "Pretendard-Regular.otf", "SB": "Pretendard-SemiBold.otf", "SERIF": "HANBatangB.ttf",
                "HAN": "BlackHanSans-Regular.ttf", "PEN": "NanumPenScript-Regular.ttf", "AN": "Anton-Regular.ttf", "MONO": "JetBrainsMono-Bold.ttf", "GM": CFG.get("font_main", "GmarketSansBold.otf")}[name]
        _fc[k] = ImageFont.truetype(P("fonts", path), size)
    return _fc[k]


def width_of(d, s, f): b = d.textbbox((0, 0), s, font=f); return b[2] - b[0]
def smooth(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3

