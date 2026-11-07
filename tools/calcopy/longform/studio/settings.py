# 경로·설정·글꼴·공용 계산
import os, sys, re, json, math, wave, subprocess, importlib.util, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(HERE, *a)                     # 공용 재료(글꼴·효과음·배경음)
WORK = os.path.abspath(os.environ.get("SHORCL_WORK") or os.getcwd())   # 편마다 다른 것(대본·샷·녹음·그림·결과)
E = lambda *a: os.path.join(WORK, *a)
def load_cfg():
    """설정의 주인. 기본 channel.json ← 판(plates/<이름>/channel.json) ← 작업 폴더 channel.json.
    판 이름을 아는 곳은 여기 하나다(SHORCL_PLATE 가 작업 폴더 plate 칸보다 먼저). 다른 함수는 CFG 칸만 읽는다.
    판 층의 dict 칸(colors 등)은 기본 위에 칸별로 얹고, 작업 폴더 층은 예전처럼 얕게 덮는다."""
    cfg = json.load(open(P("channel.json"), encoding="utf-8"))
    work = json.load(open(E("channel.json"), encoding="utf-8")) if os.path.exists(E("channel.json")) and E("channel.json") != P("channel.json") else {}
    plate = os.environ.get("SHORCL_PLATE") or work.get("plate")
    if plate:
        pp = P("plates", plate, "channel.json")
        if not os.path.exists(pp): raise SystemExit(f"없는 판: {plate} ({pp})")
        for k, v in json.load(open(pp, encoding="utf-8")).items():
            if k.startswith("_"): continue
            cfg[k] = dict(cfg[k], **v) if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
        cfg["plate"] = plate
    cfg.update(work)
    if plate: cfg["plate"] = plate
    return cfg
CFG = load_cfg()
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

