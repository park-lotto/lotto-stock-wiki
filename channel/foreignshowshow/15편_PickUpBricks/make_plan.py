# -*- coding: utf-8 -*-
"""샥탬스토리 15편 Pick Up Bricks — 벤치 해외쇼츠 aKaBZjYmbRk(「아이들이 직접 / 장난감 치운다고?!」 250만, 55.2초) 줄 단위 칼카피 (관제 097, 2026-10-27).

    PYTHONUTF8=1 py channel/foreignshowshow/15편_PickUpBricks/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(14편 make_plan 꼴).
원음 줄 = 벤치가 쓴 원음 순간을 같은 회차 원본(Sony Pictures Television 공식 X25MIpQqLIU, 1080p, 영어 원음 140-1)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/15편_PickUpBricks/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★앞은 하이브리드 재료 — 하이브리드는 O3 끝(약 15초)에서 자른다. 벤치의 '소매가 14만원'·'3억'·'주문 20배'(금액·출처 없는 숫자)는 쓰지 않고, 지분 경쟁 → 성사까지만.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/15편_PickUpBricks/src")
CLIP = "X25MIpQqLIU"
FILES = {CLIP: ("X25MIpQqLIU.mp4", 0.0, (1920, 1080))}
AUDIO = "X25MIpQqLIU_audio.m4a"        # 영어 원음(140-1 en-US original — 이 업로드엔 인도네시아어 더빙 트랙도 있어 원어만 따로 받음)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# 이름·제안 띠(102~105 'STEVEN & AURORA WEINSTOCK'·106~111 'Seeking $200k'·334~336 이름·405~406 제안 띠) 시각은 안 쓴다. 522초 빨간 공 장식 앞까지만.
H_DEF = {CLIP: 1080}
TV = {"y": 155, "h": 700, "cx": 930}      # 무대 TV 속 홍보 영상(75.7~79.4) — TV 안쪽 x 280~1580·y 140~870(76.5초 눈 측정)
TV3 = {"y": 130, "h": 800, "cx": 980}     # 83.1~84.4 TV(카메라 더 당김, 안쪽 x 230~1730·y 110~950)
TV2 = {"y": 100, "h": 860, "cx": 960}     # 89.2~91.7 TV 확대 샷
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


def T(a, b, ours, tv=TV):
    return C(CLIP, a, b, tv["cx"], tv["y"], tv["h"], ours=ours)


LINES = [
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (11.56, 12.56), "en": "Oh, no.",
     "sub": ["어머, 어떡해!"], "facts": ["f1"], "cap_at": [11.56], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 무대 배너의 픽업브릭스 본체 그림) — 벤치 0~1.0 빨간 실선 원(놀란 투자자 얼굴, 우리는 물건)",
     "cuts": [C(CLIP, 9.75, 10.30, 554, ours="무대 입장 와이드: 창업자 배너의 픽업브릭스 본체 그림·진열 카트(원본 샷 9.28~10.38, 사람 얼굴 없음 — 창업자는 크롭 밖, 소리 = 다음 컷 투자자 'Oh' cover)", cover=True),
              C(CLIP, 12.11, 12.56, ours="금발 투자자가 놀라며 'no'(말하는 본인, 샷 11.58~12.78 — 창업자들이 맨발로 레고 위를 걷는 걸 보고)")]},
    {"id": "N1", "kind": "나레", "beat": "문제(고통)", "text": "애 키우는 집이면 매일 밟는다는 이 고통",
     "tts": "애 키우는 집이면 매일 밟는다는 이 고통",
     "sub": ["애 키우는 집이면", "매일 밟는다는", "이 고통"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 1.0(레고 바닥 컷)",
     "cuts": [C(CLIP, 5.45, 6.30, 960, ours="창업자 둘이 맨발로 무대 바닥을 걸어 들어옴(발 근접, 원본 샷 ~6.34)"),
              C(CLIP, 37.35, 38.70, 1060, ours="무대 바닥에 깔린 레고 카펫 — 맨발이 막 들어오는 순간(원본 샷 35.10~39.34, 다음 줄 O2 와 이어지는 같은 샷 — 미리보기 점프줌 3.03초 수리)")]},
    {"id": "O2", "kind": "원음", "beat": "문제(창업자)", "audio": (38.76, 41.72), "en": "The most painful experience a parent can face.",
     "sub": ["부모가 겪는", "가장 끔찍한 고통이죠"], "facts": ["f2"], "cap_at": [38.76, 39.88],
     "cuts": [C(CLIP, 38.76, 39.30, 1060, ours="레고 카펫 위로 맨발이 들어옴(앞 컷과 같은 샷 이어서)"),
              C(CLIP, 39.36, 40.55, 990, ours="창업자 둘(말하는 본인 — 남자 창업자, 샷 39.34~40.57)"),
              C(CLIP, 40.60, 41.72, 960, ours="레고 더미 근접(샷 40.57~43.38)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품 공개)", "text": "그래서 애들이 알아서 치우라고 만든 장난감 전용 청소기",
     "tts": "그래서 애들이 알아서 치우라고 만든 장난감 전용 청소기",
     "sub": ["그래서 애들이", "알아서 치우라고 만든", "장난감 전용 청소기"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 5.5(제품 공개 컷)",
     "cuts": [C(CLIP, 97.00, 98.70, 800, ours="홍보 영상: 아이가 픽업브릭스 청소기를 들고 바닥을 치움(원본 샷 96.83~100.90, 화면 꽉 찬 홍보 영상)"),
              C(CLIP, 98.90, 100.85, 800, ours="같은 샷 이어서: 노란 흡입구가 바닥의 레고를 빨아들임")]},
    {"id": "O3", "kind": "원음", "beat": "해답(장점)", "audio": (73.72, 79.40), "en": "We made Pick Up Bricks cordless, durable, easy to use. It's perfect for kids.",
     "sub": ["픽업브릭스는 무선에", "튼튼하고 쓰기도 쉬워요", "아이들한테 딱이죠"], "facts": ["f3"], "cap_at": [73.72, 75.88, 77.64],
     "cuts": [C(CLIP, 73.72, 75.68, 1240, ours="창업자 둘이 진열대 앞에서 설명(말하는 본인 — 여자 창업자, 샷 73.54~75.71)"),
              T(75.75, 77.40, "무대 TV 홍보 영상: 노란 흡입구로 레고를 빨아들임(TV 안쪽만 크롭, 샷 75.71~77.44)"),
              T(77.48, 78.58, "무대 TV 홍보 영상: 여자아이가 청소기 옆에 앉아 있음(샷 77.44~78.61)"),
              T(78.65, 79.40, "무대 TV 홍보 영상: 레고가 담긴 투명 통(샷 78.61~79.41)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(차별점)", "text": "심지어 먼지는 걸러 내고 장난감만 따로 모아 준다는데",
     "tts": "심지어 먼지는 걸러 내고 장난감만 따로 모아 준다는데",
     "sub": ["심지어 먼지는 걸러 내고", "장난감만", "따로 모아 준다는데"], "facts": ["f4"],
     "fx": "빨강 번쩍 — 벤치 15.5('일반 청소기와 다르게')",
     "cuts": [T(83.10, 84.35, "무대 TV 홍보 영상: 통 안에 모인 장난감(샷 83.05~84.38)", TV3),
              T(89.30, 91.65, "무대 TV 홍보 영상: 걸러진 장난감 통과 노란 흡입 통(샷 89.22~91.69)", TV2)]},
    {"id": "O4", "kind": "원음", "beat": "시연(반응)", "audio": (120.36, 122.44), "en": "Wow, this thing is serious.",
     "sub": ["와, 이거 물건이네"], "facts": ["f5"], "cap_at": [120.36],
     "fx": "빨강 번쩍 — 벤치 20.0('와우 이거 물건이네')",
     "cuts": [C(CLIP, 120.36, 121.05, 960, ours="투자자석: 노란 흡입구가 투명 상자 속 레고를 빨아들임(근접, 샷 119.55~121.09)"),
              C(CLIP, 121.12, 122.15, ours="분홍 정장 투자자가 직접 청소기를 써 봄(샷 121.09~122.16)"),
              C(CLIP, 122.18, 122.44, 960, ours="투명 통 근접(샷 122.16~124.06)")]},
    {"id": "N4", "kind": "나레", "beat": "시연(투자자 체험)", "text": "샤크들도 직접 써 보더니 다들 손을 못 떼는데",
     "tts": "샤크들도 직접 써 보더니 다들 손을 못 떼는데",
     "sub": ["샤크들도 직접 써 보더니", "다들 손을 못 떼는데"], "facts": ["f5"],
     "cuts": [C(CLIP, 124.10, 125.55, ours="분홍 옷 투자자가 몸을 숙여 청소기로 레고를 빨아들임(샷 124.06~125.59)"),
              C(CLIP, 125.62, 127.15, 960, ours="투명 상자 속 레고를 빨아들이는 흡입구 근접(샷 125.59~127.19)")]},
    {"id": "O5", "kind": "원음", "beat": "시연(창업자)", "audio": (129.20, 130.52), "en": "You don't have to clean them all up.",
     "sub": ["다 안 치우셔도 돼요~"], "facts": ["f5"], "cap_at": [129.20],
     "cuts": [C(CLIP, 129.20, 130.52, 1100, ours="정장 투자자가 끝까지 레고를 빨아들임(샷 128.60~130.70, 말은 화면 밖 창업자)")]},
    {"id": "O6", "kind": "원음", "beat": "시연(투자자 평)", "audio": (138.16, 141.08), "en": "Just picking up the bricks is fun. / Yes, exactly.",
     "sub": ["그냥 줍는 것 자체가 재밌네", "맞아, 바로 그거야"], "facts": ["f5"], "cap_at": [138.16, 140.12],
     "cuts": [C(CLIP, 138.16, 139.88, ours="정장 투자자가 손짓하며 '줍는 것 자체가 재밌다'(말하는 본인, 샷 138.04~139.91)"),
              C(CLIP, 139.94, 141.08, ours="분홍 정장 투자자가 맞장구(샷 139.91~142.24)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁", "text": "결국 샤크 넷이 줄줄이 지분을 부르며 붙었는데",
     "tts": "결국 샤크 넷이 줄줄이 지분을 부르며 붙었는데",
     "sub": ["결국 샤크 넷이", "줄줄이 지분을 부르며", "붙었는데"], "facts": ["f6"],
     "fx": "초록 번쩍 — 벤치 38.5(지분 컷)",
     "cuts": [C(CLIP, 328.60, 331.90, ours="분홍 정장 투자자가 제안하는 중(원본 샷 328.56~331.93, 소리 끔)"),
              C(CLIP, 407.10, 410.45, ours="남색 셔츠 투자자가 제안하는 중(샷 407.07~410.48, 소리 끔)")]},
    {"id": "O7", "kind": "원음", "beat": "지분 경쟁(원음)", "audio": (440.33, 443.05), "en": "I am going to go to 15%.",
     "sub": ["난 15%까지 갈게요"], "facts": ["f6"], "cap_at": [440.33],
     "cuts": [C(CLIP, 440.33, 443.05, ours="금발 투자자가 15% 제안(말하는 본인, 샷 440.31~443.14)")]},
    {"id": "O8", "kind": "원음", "beat": "결정(역제안)", "audio": (518.81, 521.41), "en": "Is there any chance you guys would do it for 16 split?",
     "sub": ["두 분이 16%로", "나눠 주실 순 없을까요?"], "facts": ["f7"], "cap_at": [518.81, 520.17],
     "cuts": [C(CLIP, 518.81, 521.41, 900, ours="창업자 둘 — 여자 창업자가 묻는 중(말하는 본인, 샷 516.15~522.72, 522초 장식 공 전까지)")]},
    {"id": "O9", "kind": "원음", "beat": "결정(성사)", "audio": (533.81, 534.57), "en": "We got a deal.",
     "sub": ["거래 성사예요!"], "facts": ["f7"], "cap_at": [533.81],
     "fx": "초록 번쩍 — 벤치 52.5 '협상 성공'",
     "cuts": [C(CLIP, 533.81, 534.57, 1000, ours="창업자 둘이 손뼉 치며 기뻐함(말하는 본인 — 남자 창업자, 샷 533.17~536.50)")]},
    {"id": "N6", "kind": "나레", "beat": "끝(결과)", "text": "애들 장난감 청소기 하나로 샤크 둘을 한 번에 잡았다는데",
     "tts": "애들 장난감 청소기 하나로 샤크 둘을 한 번에 잡았다는데",
     "sub": ["애들 장난감 청소기 하나로", "샤크 둘을", "한 번에 잡았다는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 537.70, 539.40, 1000, ours="남자 창업자가 투자자와 포옹(원본 샷 537.64~539.47, 소리 끔)"),
              C(CLIP, 539.52, 541.55, ours="금발 투자자가 창업자와 포옹(샷 539.47~541.61, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/15편_PickUpBricks/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 15편 Pick Up Bricks — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "애들이 알아서", "line2": "치우는 청소기?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 11.56~12.56 'Oh, no.'(스피치매틱스 enhanced 영어) — 창업자 둘이 맨발로 레고가 흩어진 바닥을 걸어 들어오자 금발 투자자 반응(화면 11.58~12.78)", "url": U + CLIP, "kind": "방송 원음"},
    "f2": {"text": "원본 25.16~41.72 'Pick Up Bricks… We're here to talk about pain… The dreaded walk of pain. The most painful experience a parent can face.' · 화면 5~11·35~44 맨발·레고 카펫", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f3": {"text": "원본 54.60~66.60 'The pain of getting your kids to just pick up their stuff… that's why I created Pick Up Bricks, the kid's toy vacuum that picks up bricks and other little toys.' · 73.72~79.40 'We made Pick Up Bricks cordless, durable, easy to use. It's perfect for kids.'", "url": U + CLIP, "kind": "방송 원음"},
    "f4": {"text": "원본 79.52~87.00 'But unlike a normal vacuum, our patented design separates the dirt and dust from the toys, leaving you with cleaner toys and a cleaner floor.'", "url": U + CLIP, "kind": "방송 원음"},
    "f5": {"text": "원본 110.48~115.20 'You'll each find your very own Pick Up Bricks and a pile of toys to suck up.' · 120.36 'Wow, this thing is serious.' · 129.20 'You don't have to clean them all up.' · 138.16~141.08 'Just picking up the bricks is fun. / Yes, exactly.' · 화면 115~142 투자자 다섯이 직접 써 봄", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f6": {"text": "원본 415.85~418.17 'Listen, you've got four offers.' · 440.33~443.05 'I am going to go to 15%.' · 화면 328~332·407~410 제안하는 투자자", "url": U + CLIP, "kind": "방송 원음"},
    "f7": {"text": "원본 502.81~504.41 'But you're getting two sharks.' · 518.81~521.41 'Is there any chance you guys would do it for 16 split?' · 529.25 'Sure.' · 532.25 'All right.' · 533.81~534.57 'We got a deal.' · 화면 537~541 포옹", "url": U + CLIP, "kind": "방송 원음"},
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
        "topic": "Pick Up Bricks(픽업브릭스 — 레고·작은 장난감 전용 무선 흡입 청소기, 먼지와 장난감을 따로 거름) — 맨발로 레고 밟는 고통으로 시작한 창업자 둘(원음 'my brother in law'), 투자자 다섯이 직접 써 보고 넷이 제안 → 두 샤크가 16% 나눠 거래",
        "product": "Pick Up Bricks(픽업브릭스)",
        "bench": {"id": "aKaBZjYmbRk", "channel": "해외쇼츠 @foreignshowshow", "title": "아이들이 직접 장난감 치운다고?! (화면 제목 같음)",
                  "dur": 55.174, "views": 2500000, "window": [0, 434, 1080, 1052], "cut_median": 1.4, "_cut_median_how": "check.scene_cuts 같은 자 39조각 중앙 — 10-27 실측"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '소매가격은 14만원'·'3억 줄게요'·'전 3억에' — 금액(사장님 규칙: 대본에 금액 금지) → 지분 숫자만",
            "벤치 끝 '거래 후 주문 20배 급증' — 출처를 못 찾음 → 안 씀",
            "벤치 1.5~7 남의 육아 영상(소리 지르는 남자·부서진 레고)·홍보 영상 밖 화면 — 방송 원본 밖 → 원본 안 맨발·레고 카펫으로",
            "벤치 끝 '협상 성공' 뒤 화면 — 하이브리드 뒤(쿠팡 체험)가 그 자리를 대신함"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '아이들이 직접 / 장난감 치운다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.55], "target": [490, 935, 690, 1130], "target_what": "무대 배너에 그려진 픽업브릭스 청소기 본체 그림(제품) — 손 상자 = 9.8초 원본 프레임 눈 측정(완성본 좌표). 65초 제품 근접은 원이 창에 안 들어가 거절(992px), 115초 투자자 앞 제품은 얼굴 겹침이라 안 씀",
     "why": "R3 0초 원 = 물건(제품) — 벤치 0~1.0 원은 놀란 투자자 얼굴이지만 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "O1", "kind": "flash", "at": [540, 960], "t": [0.55, 0.93], "color": "초록", "how": "auto", "why": "원 다음 얼굴 컷 첫 프레임(14편과 같은 꼴)"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 1.0 레고 바닥 컷"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 10.5 제품 공개 컷"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 15.5 '일반 청소기와 다르게'"},
    {"line": "O4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 20.0 '와우 이거 물건이네'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 38.5 지분 컷"},
    {"line": "O9", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 52.5 '협상 성공'"},
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
    mat = {"_note": "샥탬스토리 15편 Pick Up Bricks 재료 계획. 창 1080x1052(벤치 aKaBZjYmbRk, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(X25MIpQqLIU_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Pick Up Bricks' Entrepreneurs STEP ON LEGOS", "해상도": "1920x1080 29.97fps (137) + 140-1 영어 원어(인도네시아어 더빙 트랙은 안 씀)",
                      "길이": 587.2, "받은 구간": "전체",
                      "남의 글자": "아래 이름·제안 띠(102~111·334~336·405~406초) 시각 안 씀 · 무대 진열대의 'Pick up BRICKS'·'Making Cleanup Fun' 글자 = 제품 브랜드 · 무대 TV 홍보 영상 = 창업자 제품 영상"}},
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
