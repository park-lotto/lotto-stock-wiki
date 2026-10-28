# -*- coding: utf-8 -*-
"""샥탬스토리 27편 Just the Cheese — 벤치 해외쇼츠 s920FioMSvY(「치즈 100% 과자 / 산다 vs 안산다」 280만, 56.6초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/27편_JustTheCheese/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Shark Tank Global 공식 'The Sharks Offer Entrepreneur Cheesy Deals for Just The Cheese' EI9C5IHWdYk, 1080p 30fps, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/27편_JustTheCheese/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청·제안 띠(96~101·338~341·378~381·586~589·600~605·614~617·626~634·640~645초)·시즌 카드(492~497초)·688초 뒤 끝 화면은 안 쓰는 구간. 쓰는 컷은 띠 없음.
★화면이 빨강·주황(창업자 옷·모자·무대 지도) 투성이 — 자막 강조색 빨강·분홍·주황 금지(체크리스트 ④, emph_ban).
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '50억 7천만원 매출'·'6억 8천만원에 지분 15%'·'마진 17~20%'(금액·지분)·'한 개에 75칼로리'(영양 수치)는 쓰지 않는다.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
SRC = Path("C:/숏템_칼카피/foreignshowshow/27편_JustTheCheese/src")
CLIP = "EI9C5IHWdYk"
FILES = {CLIP: ("EI9C5IHWdYk.mp4", 0.0, (1920, 1080)),
         "z109": ("z109.mp4", 109.45, (1920, 1080)),   # 109.45~111.83 을 1.25배 천천히 다가가는 사본(zoomclip.py — 원경 창업자 멈춤 0.5초 대응, 98 #170)
         "z118": ("z118.mp4", 118.0, (1920, 1080))}    # 118.0~119.52 를 1.2배 다가가는 사본(같은 이유 · 소리는 원음 m4a 그 시각 그대로)
AUDIO = "EI9C5IHWdYk_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Shark Tank Global 원본: 고정 로고 없음 · 이름/요청/제안 띠는 안 쓰는 구간 · 492~497초 시즌 카드·688초 뒤 끝 화면 안 씀.
H_DEF = {CLIP: 1080, "z109": 1080, "z118": 1080}
_FACE_CACHE: dict = {}


def face_cx(vid, t):
    key = (vid, round(t, 2))
    if key not in _FACE_CACHE:
        from tools.calcopy.shark.fx_place import _src_frame
        from tools.calcopy.shark import fx_measure as FM
        a, _, _ = _src_frame(SRC / FILES[vid][0], t)
        fs = FM.faces(a)
        _FACE_CACHE[key] = max(fs, key=lambda f: f["h"])["cx"] if fs else None
    return _FACE_CACHE[key]


def crop(vid, cx, y=0, h=None, t=None):
    W, H = FILES[vid][2]
    h = h or H_DEF[vid]
    w = min(W, int(round(h * AR)))
    if cx == "face":
        cx = face_cx(vid, t) or W / 2
    x = max(0, min(W - w, int(cx - w / 2)))
    y = max(0, min(H - h, y))
    return [x, y, w, h]


def C(vid, a, b, cx="face", y=0, h=None, ours="", **kw):
    return (vid, a, b, crop(vid, cx, y, h, t=(a + b) / 2), ours, kw)


LINES = [
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (168.77, 171.89), "en": "Really good. I have to admit, I've had this before.",
     "sub": ["진짜 맛있어!", "나 이거 먹어 봤어"], "facts": ["f1"], "cap_at": [168.77, 169.85], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 투자자 손에 든 구운 치즈 바) — 벤치 0~1.0 투자자 원(우리는 물건 원)",
     "cuts": [C(CLIP, 162.56, 163.76, 820, ours="투자자 손에 든 구운 치즈 바(원본 샷 162.53~166.57 첫 1.2초, 얼굴 없음 — 소리 = 투자자 원음 'Really good.' cover, 말한 사람은 다음 컷)", cover=True),
              C(CLIP, 169.97, 171.89, ours="치즈 바를 먹으며 말하는 투자자 본인(원본 샷 168.57~171.91 — 소리 = 이 줄 원음 이어서, 화면초 169.97 = 소리초 169.97)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "치즈 샌드위치를 구우면 팬에 눌어붙은 바삭한 치즈가 제일 맛있다는 남자가 있는데",
     "tts": "치즈 샌드위치를 구우면, 팬에 눌어붙은 바삭한 치즈가, 제일 맛있다는 남자가 있는데",
     "sub": ["치즈 샌드위치를 구우면", "팬에 눌어붙은 바삭한 치즈가", "제일 맛있다는 남자가 있는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5('늘어붙은 치즈가 최고라는 이 남자')",
     "cuts": [C("z109", 109.45, 111.80, 1366, ours="무대 위 창업자와 제품 간판(원본 샷 109.41~111.85 을 천천히 다가가는 사본 z109.mp4, 제품 브랜드, 소리 끔)"),
              C(CLIP, 111.90, 114.58, ours="말하는 창업자(샷 111.85~114.61, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(한 마디)", "audio": (114.63, 119.49), "en": "Well, most people look at that and think, man, I wish I could eat just the cheese.",
     "sub": ["다들 이거 보면", "치즈만 먹고 싶다 하죠!"], "facts": ["f2"], "cap_at": [115.00, 116.88],
     "cuts": [C(CLIP, 114.63, 115.83, ours="듣고 있는 투자자(원본 샷 114.61~115.85 — 소리 = 창업자 원음 그 시각)"),
              C(CLIP, 115.87, 117.95, ours="말하는 창업자 본인(샷 115.85~117.98)"),
              C("z118", 118.01, 119.49, 1366, ours="무대 위 창업자 본인(샷 117.98~121.55 를 천천히 다가가는 사본 z118.mp4 — 소리 = 원음 그 시각)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(시연)", "text": "그래서 직접 만든 치즈를 틀에 살짝 넣고 오븐에 굽기만 했다는데",
     "tts": "그래서 직접 만든 치즈를, 틀에 살짝 넣고, 오븐에 굽기만 했다는데",
     "sub": ["그래서 직접 만든 치즈를", "틀에 살짝 넣고", "오븐에 굽기만 했다는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 9.0('자체 생산한 치즈를 가지고')",
     "cuts": [C(CLIP, 134.20, 136.00, 1000, ours="쿠키 틀에 치즈를 넣는 손(원본 샷 134.17~136.04, 손만, 소리 끔)"),
              C(CLIP, 136.08, 138.60, ours="오븐에 넣는 창업자(샷 136.04~140.94, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "해답(구호)", "audio": (143.49, 145.33), "en": "It's just the cheese.",
     "sub": ["그냥 치즈", "그 자체예요!"], "facts": ["f3"], "cap_at": [143.49, 144.30],
     "cuts": [C(CLIP, 143.49, 145.33, 960, ours="오븐에서 꺼낸 판 위 구운 치즈 바(원본 샷 142.84~145.71 — 이 말을 할 때 방송 화면 그대로)")]},
    {"id": "N3", "kind": "나레", "beat": "체험(시식)", "text": "샤크들도 한 입씩 먹어 보는데 아마존에서만 하루에 수백 박스씩 팔린다는데",
     "tts": "샤크들도 한 입씩 먹어 보는데, 아마존에서만 하루에, 수백 박스씩 팔린다는데",
     "sub": ["샤크들도 한 입씩 먹어 보는데", "아마존에서만 하루에", "수백 박스씩 팔린다는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 21.4('투자자도 사 먹어 봤을 정도로')",
     "cuts": [C(CLIP, 179.00, 181.15, ours="치즈 바를 먹어 보는 샤크들(원본 샷 178.98~181.21, 소리 끔)"),
              C(CLIP, 181.25, 183.15, ours="치즈 바를 씹어 보는 투자자(샷 181.21~183.18, 소리 끔)")]},
    {"id": "N4", "kind": "나레", "beat": "숫자(베끼기)", "text": "근데 이렇게 간단한 걸 아무나 따라 만들면 어떡하냐는 말이 나오는데",
     "tts": "근데 이렇게 간단한 걸, 아무나 따라 만들면, 어떡하냐는 말이 나오는데",
     "sub": ["근데 이렇게 간단한 걸", "아무나 따라 만들면", "어떡하냐는 말이 나오는데"], "facts": ["f5"],
     "cuts": [C(CLIP, 193.93, 195.60, ours="질문을 듣는 창업자(원본 샷 193.89~195.63, 소리 끔)"),
              C(CLIP, 195.66, 198.20, ours="'아무나 할 수 있잖아' 묻는 투자자(샷 195.63~198.26, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "지분 경쟁(독설)", "audio": (203.32, 205.29), "en": "There's a ton of brands out there ahead of you.",
     "sub": ["이미 앞선 브랜드가", "널렸어요"], "facts": ["f6"], "cap_at": [203.32, 204.21],
     "fx": "빨강 번쩍 — 벤치 지분 경쟁",
     "cuts": [C(CLIP, 203.32, 205.29, ours="말하는 투자자 본인(원본 샷 203.30~207.17)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁(거절)", "text": "결국 비슷한 게 너무 많다며 샤크들이 하나둘 빠지는데",
     "tts": "결국 비슷한 게 너무 많다며, 샤크들이 하나둘 빠지는데",
     "sub": ["결국 비슷한 게 너무 많다며", "샤크들이", "하나둘 빠지는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 460.40, 462.10, ours="빠지겠다고 말하는 투자자(원본 샷 460.33~463.10, 소리 끔)"),
              C(CLIP, 469.10, 470.60, ours="샤크들 자리 전경(샷 469.07~473.57, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "지분 경쟁(포기)", "audio": (482.86, 484.42), "en": "So for those reasons, I'm out.",
     "sub": ["그런 이유로", "난 빠질게요"], "facts": ["f7"], "cap_at": [482.86, 483.82],
     "cuts": [C(CLIP, 482.86, 484.42, ours="말하는 투자자 본인(원본 샷 481.25~484.42)")]},
    {"id": "N6", "kind": "나레", "beat": "결정(거절)", "text": "과자 하나마다 평생 돈을 떼 가겠다는 제안까지 거절하고 빈손으로 나갔다는데",
     "tts": "과자 하나마다 평생, 돈을 떼 가겠다는 제안까지, 거절하고 빈손으로 나갔다는데",
     "sub": ["과자 하나마다 평생", "돈을 떼 가겠다는 제안까지", "거절하고 빈손으로 나갔다는데"], "facts": ["f8"],
     "fx": "빨강 번쩍 — 거절",
     "cuts": [C(CLIP, 507.10, 513.55, ours="평생 로열티를 말하는 투자자(원본 샷 507.07~513.61, 띠 없음, 소리 끔)"),
              C(CLIP, 672.95, 676.60, ours="무대에서 걸어 나가는 창업자(샷 672.91~676.64, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "끝(되받기)", "audio": (684.15, 687.35), "en": "that I couldn't bring home a deal, but I hope they're proud of me anyway.",
     "sub": ["투자는 못 받았지만", "가족들이", "자랑스러워했으면 해요"], "facts": ["f8"], "cap_at": [684.15, 685.91, 686.39],
     "cuts": [C(CLIP, 684.15, 687.35, ours="말하는 창업자 본인(원본 샷 683.32~687.65)")]},
    {"id": "N7", "kind": "나레", "beat": "끝(결과)", "text": "근데 몇 년 뒤 견과류로 유명한 식품 회사가 이 브랜드를 통째로 사 갔다는데",
     "tts": "근데 몇 년 뒤, 견과류로 유명한 식품 회사가, 이 브랜드를 통째로 사 갔다는데",
     "sub": ["근데 몇 년 뒤", "견과류로 유명한 식품 회사가", "이 브랜드를 통째로 사 갔다는데"], "facts": ["f9"],
     "fx": "초록 번쩍 — 후일담",
     "cuts": [C(CLIP, 430.20, 432.55, 960, ours="Just the Cheese 포장 세 개(원본 샷 430.16~432.60, 제품 브랜드, 소리 끔)"),
              C(CLIP, 446.00, 448.40, 960, ours="포장 세 개 근접(샷 445.61~448.45, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/27편_JustTheCheese/work/render/render_info.json")


def _real():
    if not RINFO.exists():
        return {}
    d = json.loads(RINFO.read_text(encoding="utf-8"))
    return {l["id"]: round(l["t1"] - l["t0"], 3) for l in d["lines"]} if d.get("mode") != "plan" else {}


REAL = _real()


def line_dur(L: dict) -> float:
    if L["kind"] == "원음":
        return round(L["audio"][1] - L["audio"][0], 2)
    return REAL.get(L["id"]) or round(nchar(L["tts"]) / RATE, 2)


def build():
    shots, t = [], 0.0
    for L in LINES:
        d = line_dur(L)
        cut_total = sum(c[2] - c[1] for c in L["cuts"])
        scale = d / cut_total if L["kind"] == "나레" else 1.0
        a_line = L.get("audio", (0, 0))[0]
        acc = 0.0
        for k, c in enumerate(L["cuts"]):
            vid, a, b, cr, ours, kw = c
            dur = round((b - a) * scale, 3)
            f, ss = src_of(vid, a)
            if L["kind"] == "나레" or kw.get("mute"):
                au = {"mute": True}
            elif kw.get("cover"):       # 화면만 다른 장면, 소리는 이 줄 원음(줄 시작부터)
                au = {"mute": False, "audio_src": AUDIO, "audio_ss": round(a_line + acc, 3), "audio_dur": dur, "cover": True}
            else:
                au = {"mute": False, "audio_src": AUDIO, "audio_ss": a, "audio_dur": dur}
            shots.append({"i": len(shots), "line": L["id"], "kind": L["kind"], "src": f, **au,
                          "url": f"https://www.youtube.com/watch?v={vid}", "src_orig_span": [a, round(a + dur, 3)], "ss": ss,
                          "dur": dur, "t_final_est": [round(t, 2), round(t + dur, 2)], "res": "%dx%d" % FILES[vid][2],
                          "src_crop": cr, "scale": round(WIN[1] / cr[3], 3), "ours": ours,
                          "audio": "원본 소리(원음)" if L["kind"] == "원음" else "원본 소리 끔 + TTS"})
            t += dur
            acc += dur
    return shots, round(t, 2)


def frame(path: str, ss: float, cr) -> Image.Image:
    x, y, w, h = cr
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-i", path, "-frames:v", "1", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale=270:263", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return Image.open(io.BytesIO(b)).convert("RGB")


def _wrap(s: str, n: int):
    out, cur = [], ""
    for w in s.split(" "):
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


def sheet(shots, out: Path, title: str):
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 15)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 13)
    byline = {L["id"]: L for L in LINES}
    rowh, cw = 263 + 8, 270
    S = Image.new("RGB", (60 + 3 * cw + 520, rowh * len(shots) + 40), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.text((8, 8), f"샥탬스토리 27편 Just the Cheese — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
    for k, s in enumerate(shots):
        y0 = 40 + k * rowh
        L = byline[s["line"]]
        d.text((6, y0 + 4), f"#{s['i']}", fill=(200, 0, 0), font=font)
        d.text((6, y0 + 24), s["line"], fill=(0, 0, 0), font=small)
        for j, frac in enumerate((0.05, 0.5, 0.95)):
            S.paste(frame(str(SRC / s["src"]), s["ss"] + s["dur"] * frac, s["src_crop"]), (60 + j * cw, y0))
        tx = 60 + 3 * cw + 8
        col = (0, 90, 200) if L["kind"] == "원음" else (0, 0, 0)
        d.text((tx, y0 + 2), f"{L['kind']} · {L['beat']} · {s['t_final_est'][0]:.2f}~{s['t_final_est'][1]:.2f}s ({s['dur']:.2f}s)", fill=col, font=font)
        for n, part in enumerate(_wrap(L.get("en") if L["kind"] == "원음" else L["text"], 34)):
            d.text((tx, y0 + 24 + n * 18), part, fill=(0, 0, 0), font=small)
        d.text((tx, y0 + 100), "자막: " + " / ".join(L["sub"]), fill=(120, 0, 120), font=small)
        d.text((tx, y0 + 140), f"{s['src']} @원본 {s['src_orig_span'][0]}~{s['src_orig_span'][1]} 크롭 {s['src_crop']} ×{s['scale']}", fill=(90, 90, 90), font=small)
        for n, part in enumerate(_wrap(s["ours"], 34)):
            d.text((tx, y0 + 160 + n * 18), part, fill=(0, 100, 0), font=small)
    S.save(out, quality=82)


def check(shots, total):
    durs = sorted(s["dur"] for s in shots)
    med = durs[len(durs) // 2] if len(durs) % 2 else (durs[len(durs) // 2 - 1] + durs[len(durs) // 2]) / 2
    narr = sum(nchar(L["tts"]) for L in LINES if L["kind"] == "나레")
    return {"길이_추정": total, "컷": len(shots), "컷_중앙": round(med, 2), "컷_최소": durs[0], "나레_자수(TTS,공백뺌)": narr,
            "자막_최대자수": max(nchar(x) for L in LINES for x in L["sub"]),
            "원음_초": round(sum(line_dur(L) for L in LINES if L["kind"] == "원음"), 2), "확대_최대": max(s["scale"] for s in shots)}


TITLES = {"line1": "치즈만 구워서", "line2": "과자를 만든다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 168.77~172.01 'Really good. I have to admit, I've had this before.'(스피치매틱스 enhanced 영어 — 투자자 원음, 이름은 자막에 안 씀) · 화면은 같은 원본 162.56초 투자자 손에 든 치즈 바(cover) + 말한 투자자 본인", "url": U + CLIP + "&t=168s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 110.40~119.49 'when you make a grilled cheese sandwich, the best part is the cheese that melts off into the pan and gets crunchy. Well, most people look at that and think, man, I wish I could eat just the cheese.'", "url": U + CLIP + "&t=110s", "kind": "방송 원음"},
    "f3": {"text": "원본 127.29~145.33 'First, we start with Wisconsin milk. Make our own fresh cheese in-house. Shred just a little bit into a cookie cutter mold. Pop it in the oven and that is it. … It's just the cheese.' · 화면 134~145 시연", "url": U + CLIP + "&t=127s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 169.85~179.29 'I have to admit, I've had this before.' 'I bought it on Amazon.' 'We sell between 4 and 700 boxes a day on Amazon.' · 화면 160~183 샤크들 시식", "url": U + CLIP + "&t=169s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 191.77~196.73 'Why can't anybody knock you off? I mean, you're doing something so simple. Anybody can do this, right?'", "url": U + CLIP + "&t=191s", "kind": "방송 원음"},
    "f6": {"text": "원본 202.69~205.29 'There's a ton of brands out there ahead of you.'", "url": U + CLIP + "&t=202s", "kind": "방송 원음+화면"},
    "f7": {"text": "원본 409.93~412.25 'I don't like the taste of it.' · 438.38~441.10 'I just don't think there's space and I'm out.' · 462.30~463.02 'So I'm out.' · 482.86~484.42 'So for those reasons, I'm out.' · 498.30~499.78 'Four sharks are out.'", "url": U + CLIP + "&t=409s", "kind": "방송 원음+화면"},
    "f8": {"text": "원본 507.06~514.26 'I give you half $1 million. I ask for $0.20 a bar. As a royalty, I get no equity in perpetuity.' · 631.10~632.78 'Yes, but I'm going to have to decline.' · 661.07~666.19 'It's a reasonable offer, but I'm going to politely and respectfully say no.' · 681.87~687.35 '…that I couldn't bring home a deal, but I hope they're proud of me anyway.' — 금액은 대본에 안 씀", "url": U + CLIP + "&t=507s", "kind": "방송 원음+화면"},
    "f9": {"text": "John B. Sanfilippo & Son, Inc. 보도자료(2022-12-16, Business Wire) 'announces acquisition of Just the Cheese brand' — Specialty Cheese Company 로부터 브랜드 사업 자산 인수, 금액 비공개 · Sanfilippo = 견과류·말린 과일 회사(Fisher·Orchard Valley Harvest)", "url": "https://www.foodprocessing.com/business-of-food-beverage/mergers-acquisitions/news/21441635/sanfilippo-expands-from-nuts-into-cheese-snacks", "url2": "https://www.businesswire.com/news/home/20221216005470/en", "kind": "업계지 기사(직접 확인)+회사 보도자료"},
}


def doc_update():
    p = HERE / "대본.json"
    S = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    old = {l["id"]: l for l in (S.get("final") or {}).get("lines", [])}
    out = []
    for L in LINES:
        x = {"id": L["id"], "kind": L["kind"], "fn": L["beat"], "facts": L["facts"], "caps": L["sub"]}
        if L["kind"] == "원음":
            if L.get("cap_at"):
                x["cap_at"] = L["cap_at"]
            x.update({"span": list(L["audio"]), "orig_en": L["en"], "text": " ".join(L["sub"]), "style": L.get("style", "보통")})
        else:
            x.update({"text": L["text"], "tts": L["tts"]})
        if L.get("fx"):
            x["fx"] = L["fx"]
        if old.get(L["id"], {}).get("emph"):
            x["emph"] = old[L["id"]]["emph"]
        out.append(x)
    S.update({
        "topic": "Just the Cheese(저스트 더 치즈) — 치즈만 틀에 넣어 구운 바삭한 치즈 과자. 위스콘신 치즈 집안 아들, 팬에 눌어붙은 치즈가 제일 맛있다 → 치즈만 구움 → 샤크 시식 '나 이거 사 먹어 봤어' → 베끼기 쉽다며 줄줄이 빠짐 → 남은 제안도 거절, 빈손 → 몇 년 뒤 큰 식품 회사가 브랜드 인수",
        "product": "Just the Cheese baked cheese snack bar(치즈만 구운 과자)",
        "bench": {"id": "s920FioMSvY", "channel": "해외쇼츠 @foreignshowshow", "title": "치즈 100% 과자?! (화면 제목: 치즈 100% 과자 / 산다 vs 안산다)",
                  "dur": 56.6, "views": 2800000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "1초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '50억 7천만원을 팔았어요'·'6억 8천만원에 지분 15%'·'마진 17~20%'(금액·지분) → 금액 없이 거절·빈손만",
            "벤치 '한 개에 몇 칼로리야 / 75칼로리요'(영양 수치) — 쓰지 않음",
            "벤치 '대형 제과회사가 50억에 회사를 사갔다고'(금액, 1차 출처는 '금액 비공개') → '견과류로 유명한 식품 회사가 브랜드를 통째로' 로(Business Wire 보도자료)",
            "벤치 6~7초 남의 틱톡 화면(남의 얼굴·글자) — 이 원본 밖 → 원본 무대 시연으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '치즈 100% 과자 / 산다 vs 안산다'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [423, 979, 656, 1203], "target_what": "투자자 손에 든 구운 치즈 바 — 162.7초 원본 프레임 눈 측정(창 크롭 [266,0,1109,1080] 안 x 434~674·y 560~790, ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 9.0 해답"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "시식"},
    {"line": "O4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 지분 경쟁"},
    {"line": "N7", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "후일담"},
]


def main():
    shots, total = build()
    old = {}
    mp = HERE / "재료.json"
    if mp.exists():      # fx_place fix 가 계산해 넣은 값(at·size·track…)은 다시 만들 때도 지킨다
        old = {(e["line"], e["kind"], tuple(e.get("t") or [])[:1]): e for e in json.loads(mp.read_text(encoding="utf-8")).get("effects") or []}
    eff = []
    for e in EFFECTS:
        o = old.get((e["line"], e["kind"], tuple(e["t"])[:1]))
        eff.append({**e, **{k: v for k, v in (o or {}).items() if k not in e or k in ("t",)}} if o else e)
    mat = {"_note": "샥탬스토리 27편 Just the Cheese 재료 계획. 창 1080x1052(벤치 s920FioMSvY, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(EI9C5IHWdYk_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global(공식)", "제목": "The Sharks Offer Entrepreneur Cheesy Deals for Just The Cheese | Shark Tank US | Shark Tank Global", "해상도": "1920x1080 30fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 708.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(96~101·338~341·378~381·586~589·600~605·614~617·626~634·640~645초) 안 씀 · 492~497 시즌 카드·688초 뒤 끝 화면 안 씀 · 무대·포장 'JUST THE CHEESE' 글 = 제품 브랜드"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": TITLES, "shots": shots, "cand_dir": str(SRC).replace("\\", "/"), "effects": eff}
    doc_update()
    mp.write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--no-sheet" not in sys.argv:
        (HERE / "plan").mkdir(exist_ok=True)
        sheet(shots, HERE / "plan" / "계획_시트.jpg", " / ".join(TITLES.values()))
    print(json.dumps(check(shots, total), ensure_ascii=False))
    for x in shots:
        print(x["i"], x["line"], x["kind"], x["src"], x["src_orig_span"], x["dur"], x["t_final_est"], x["src_crop"], x["scale"], file=sys.stderr)


if __name__ == "__main__":
    main()
