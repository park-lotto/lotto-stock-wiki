# -*- coding: utf-8 -*-
"""샥탬스토리 8편 Flipstik — 소재 벤치 BIG BAG HUSTLE ec6-kas1jVs(2,330만) + 꼴 벤치 해외쇼츠 공식 6박자 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py channel/foreignshowshow/8편_Flipstik/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(7편 make_plan 꼴).
원음 줄 = 공식 원본 Sony Pictures Television MJO3kI8D974(1080p) 시각. 원음 경계 = faster-whisper 낱말 시각(asr/fw_words.json)
+ 20ms RMS 골(쉼) — 내용은 구간 단독 받아쓰기 2모델(asr/span_v1~v4.json)로 확인. 근거.md §2.
나레 시각은 7.8자/초 추정 — TTS 뒤(render.py --tts-only) render_info 로 줄 길이만 다시 잰다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/8편_Flipstik/src")
CLIP = "MJO3kI8D974"
FILES = {CLIP: ("MJO3kI8D974.mp4", 0.0, (1920, 1080))}
AUDIO = "MJO3kI8D974_audio.m4a"        # 원본 영어 원음(140, 단일 트랙 — 더빙 없음)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
H_DEF = {CLIP: 1080}     # 쓰는 구간엔 이름·제안 띠 없음(띠 72~77·79~81·380~382·390~392·528~548초 = 안 씀)


def crop(vid, cx, y=0, h=None):
    W, H = FILES[vid][2]
    h = h or H_DEF[vid]
    w = int(round(h * AR))
    x = max(0, min(W - w, int(cx - w / 2)))
    return [x, y, w, h]


def _hook():
    """0초 원 컷 크롭 = 얼굴 검출(fx_place.hook_circle, 눈대중 금지). 렌더 단계 fx_place.fix 가 같은 함수로 다시 잰다."""
    from tools.calcopy.shark import fx_place as P
    return P.hook_circle(SRC / FILES[CLIP][0], 501.85, 1.45)


HOOK = _hook()

# 원음 줄 audio = (원본 시작, 끝) — 원본 초. cut = (소스, 원본 시작, 원본 끝, [x,y,w,h], 화면에 보이는 것)
LINES = [
    {"id": "O1", "kind": "원음", "beat": "결말 반응(0초 훅)", "audio": (501.85, 503.30), "en": "You should have taken it.",
     "sub": ["그냥 받았어야지!"], "style": "원음반응_크게", "facts": ["f12"],
     "fx": "0초 빨간 실선 원(케빈 얼굴, fx_place.hook_circle) — 벤치 foreignshowshow 공식 6박자 0초 결말 반응 + BBH 0초도 케빈 얼굴",
     "cuts": [(CLIP, 501.85, 503.30, HOOK["src_crop"], "케빈이 손가락질하며 '받았어야지'(말하는 본인, 샷 499.90~505.94 상반신)")]},
    {"id": "O2", "kind": "원음", "beat": "소개(BBH 0초 원음)", "audio": (88.70, 90.45), "en": "This is Flipstick.",
     "sub": ["이게 플립스틱이에요"], "facts": ["f1"],
     "cuts": [(CLIP, 88.70, 89.222, crop(CLIP, 880), "케빈이 웃으며 봄(원본 반응 컷 — BBH 0초 컷과 같은 샷)"),
              (CLIP, 89.222, 90.45, crop(CLIP, 1060), "무대 와이드: 창업자가 폰 뒤를 들어 보임 + 뒤 화면 제품 로고 'flipstik DEFY GRAVITY'(제품 글자)")]},
    {"id": "N1", "kind": "나레", "beat": "시연(제품)", "text": "종이처럼 얇은 걸 폰 뒤에 붙였는데", "tts": "종이처럼 얇은 걸 폰 뒤에 붙였는데",
     "sub": ["종이처럼 얇은 걸", "폰 뒤에 붙였는데"], "facts": ["f2"],
     "cuts": [(CLIP, 93.30, 94.40, crop(CLIP, 700), "폰 뒷면 근접: 파란 플립스틱 덮개를 손가락으로 젖힘"),
              (CLIP, 95.60, 96.80, crop(CLIP, 1050), "폰 뒷면 근접: 플립스틱 붙은 금색 폰을 돌려 보임")]},
    {"id": "O3", "kind": "원음", "beat": "시연(핵심)", "audio": (107.20, 109.95), "en": "Essentially, it lets you stick your phone anywhere.",
     "sub": ["폰을 어디든", "붙일 수 있어요"], "facts": ["f3"], "cap_at": [107.28, 108.58],
     "fx": "초록 아래 화살표(판에 붙은 폰) — 벤치 QMJ 0.567~1.267 첫 시연 제품",
     "cuts": [(CLIP, 107.20, 109.009, crop(CLIP, 960), "'STICK YOUR PHONE HERE' 판(제품 시연 소품)에 폰을 탁 붙임(근접)"),
              (CLIP, 109.009, 109.95, crop(CLIP, 900), "분홍 블라우스 투자자가 봄(원본 반응 컷)")]},
    {"id": "O4", "kind": "원음", "beat": "반응", "audio": (110.18, 110.75), "en": "Cool.", "sub": ["멋지네"], "style": "원음반응_크게", "facts": ["f3"],
     "cuts": [(CLIP, 110.18, 110.75, crop(CLIP, 880), "마크가 웃으며 '쿨'(말하는 본인, 샷 110.18~110.81 — BBH 6.4초와 같은 컷)")]},
    {"id": "O5", "kind": "원음", "beat": "시연(핵심)", "audio": (110.75, 113.70), "en": "And when I say stick, I mean it really sticks.",
     "sub": ["붙는다는 건", "진짜 딱 붙는다는 거예요"], "facts": ["f3"], "cap_at": [110.78, 112.08],
     "fx": "초록 번쩍(장면 넘김) — 판 근접 컷 첫 프레임",
     "cuts": [(CLIP, 110.75, 112.345, crop(CLIP, 900), "창업자가 판을 두드리며 말함(말하는 본인, 무대)"),
              (CLIP, 112.345, 113.70, crop(CLIP, 1040), "판에 붙은 폰 근접(안 떨어짐)")]},
    {"id": "N2", "kind": "나레", "beat": "시연(떼기)", "text": "살짝 비틀기만 하면 쏙 떨어진다는데", "tts": "살짝 비틀기만 하면 쏙 떨어진다는데",
     "sub": ["살짝 비틀기만 하면", "쏙 떨어진다는데"], "facts": ["f4"],
     "cuts": [(CLIP, 116.30, 117.30, crop(CLIP, 960), "판에 붙은 폰 근접"),
              (CLIP, 117.40, 118.50, crop(CLIP, 800), "손가락으로 폰을 비틀어 떼어냄(근접)")]},
    {"id": "N3", "kind": "나레", "beat": "기존 불편(더러움 시험)", "text": "근데 머리카락에 모래, 스파게티까지 잔뜩 묻히는데",
     "tts": "근데 머리카락에 모래, 스파게티까지 잔뜩 묻히는데", "sub": ["근데 머리카락에 모래", "스파게티까지", "잔뜩 묻히는데"], "facts": ["f5"],
     "fx": "빨간 점선 원(머리카락 묻히는 창업자, 사람) + 빨강 번쩍 — 벤치 QMJ 9.3~11.5 불편 장면 점선 원·11.2 빨강",
     "cuts": [(CLIP, 148.20, 149.50, crop(CLIP, 800), "창업자가 폰 뒤 플립스틱에 머리카락을 문지름(무대)"),
              (CLIP, 154.00, 155.20, crop(CLIP, 1100), "모래 그릇에 폰 뒤를 비빔(근접)"),
              (CLIP, 156.70, 157.90, crop(CLIP, 900), "스파게티 그릇에 폰 뒤를 담금(근접, 아래 제품 포장 'flipstik' = 제품 글자)")]},
    {"id": "O6", "kind": "원음", "beat": "기존 불편(의문)", "audio": (162.10, 164.50), "en": "This ain't sticking to nothing, all right?",
     "sub": ["이제 아무 데도", "안 붙겠죠?"], "facts": ["f5"], "cap_at": [162.18, 163.46],
     "cuts": [(CLIP, 162.10, 164.50, crop(CLIP, 960), "창업자가 손을 들며 말함(말하는 본인, 샷 161.03~164.50)")]},
    {"id": "N4", "kind": "나레", "beat": "해답(닦기)", "text": "쓱 닦아 내고 다시 붙여 보면", "tts": "쓱 닦아 내고 다시 붙여 보면",
     "sub": ["쓱 닦아 내고", "다시 붙여 보면"], "facts": ["f6"],
     "cuts": [(CLIP, 171.00, 173.10, crop(CLIP, 1000), "흰 천으로 플립스틱 면을 닦음(근접, 샷 170.90~173.21)")]},
    {"id": "O7", "kind": "원음", "beat": "해답(예고)", "audio": (175.80, 179.08), "en": "And so, who thinks it's gonna stick? / I do.",
     "sub": ["붙을 것 같은 사람?", "저요!"], "facts": ["f6"], "cap_at": [175.88, 177.44],
     "cuts": [(CLIP, 175.80, 177.511, crop(CLIP, 900), "창업자가 판 쪽으로 몸을 숙이며 물음(말하는 본인)"),
              (CLIP, 177.511, 179.08, crop(CLIP, 900), "로리가 웃으며 봄(원본 반응 컷 — BBH 42.5초 '저요' 컷과 같은 샷)")]},
    {"id": "O8", "kind": "원음", "beat": "해답(성공)", "audio": (179.08, 181.95), "en": "I have a lot of believers here. Hey!",
     "sub": ["믿는 분이 많네요", "짠!"], "facts": ["f6"], "cap_at": [179.10, 180.68],
     "fx": "초록 번쩍 — 더러운 폰이 판에 붙은 컷 첫 프레임(BBH 끝 44.5~45.8 같은 장면)",
     "cuts": [(CLIP, 179.08, 180.681, crop(CLIP, 900), "창업자가 더러운 폰을 판에 댐(말하는 본인)"),
              (CLIP, 180.681, 181.95, crop(CLIP, 1000), "스파게티 범벅 폰이 판에 그대로 붙어 있음(근접)")]},
    {"id": "O9", "kind": "원음", "beat": "숫자", "audio": (315.70, 318.92), "en": "On average, it costs us 58 cents to make. We sell these for $15,",
     "sub": ["원가는 58센트", "15달러에 팔아요"], "facts": ["f7"], "cap_at": [315.72, 317.88],
     "fx": "분홍 위 화살표(숫자 조각 '58센트') — 벤치 QMJ 12.0 숫자 조각",
     "cuts": [(CLIP, 315.70, 318.92, crop(CLIP, 960), "창업자가 말함(말하는 본인, 샷 315.68~318.92)")]},
    {"id": "O10", "kind": "원음", "beat": "지분 경쟁(제안)", "audio": (386.45, 389.39),
     "en": "I'll give you a hundred thousand for twenty percent, exactly what you want",
     "sub": ["10만 달러에 20%", "원하는 그대로 줄게"], "facts": ["f8"], "cap_at": [386.46, 388.46],
     "fx": "초록 번쩍 + 날개 돈다발 — 벤치 QMJ 38.7 제안 금액 줄",
     "cuts": [(CLIP, 386.45, 389.389, crop(CLIP, 880), "케빈이 제안(말하는 본인, 샷 384.82~389.39)")]},
    {"id": "N5", "kind": "나레", "beat": "전개(망설임)", "text": "근데 바로 안 받고 경쟁사 얘기만 늘어놓는데", "tts": "근데 바로 안 받고 경쟁사 얘기만 늘어놓는데",
     "sub": ["근데 바로 안 받고", "경쟁사 얘기만", "늘어놓는데"], "facts": ["f9"],
     "cuts": [(CLIP, 398.00, 399.40, crop(CLIP, 960), "창업자가 두 손을 모으고 말함(무대 정면)"),
              (CLIP, 402.00, 403.40, crop(CLIP, 1040), "창업자가 손뼉 치며 설명")]},
    {"id": "O11", "kind": "원음", "beat": "결정(취소)", "audio": (484.65, 489.60),
     "en": "I made you an offer exactly what you wanted before you told me that you only sold $1,500",
     "sub": ["딱 원하는 걸 줬잖아", "1,500달러밖에", "못 팔았단 말 전엔!"], "facts": ["f10"], "cap_at": [484.65, 487.12, 488.58],
     "fx": "빨강 번쩍 — 벤치 QMJ 44.4 결정 빨강",
     "cuts": [(CLIP, 484.65, 489.60, crop(CLIP, 840), "케빈이 손짓하며 말함(말하는 본인, 샷 484.65~490.92)")]},
    {"id": "O12", "kind": "원음", "beat": "지분 경쟁(다른 제안)", "audio": (512.62, 518.95),
     "en": "So, here's my offer. I'm gonna give you the $100,000, but I want 25%.",
     "sub": ["내 제안은 이거야", "10만 달러 줄게", "대신 25%야"], "facts": ["f11"], "cap_at": [512.62, 514.32, 516.72],
     "cuts": [(CLIP, 512.62, 514.55, crop(CLIP, 1000), "창업자가 듣는 얼굴(원본 반응 컷 — 원본 편집 그대로, 샷 512.08~514.55)"),
              (CLIP, 514.55, 518.95, crop(CLIP, 960), "로리가 손짓하며 제안(말하는 본인, 샷 514.55~519.39)")]},
    {"id": "O13", "kind": "원음", "beat": "결정(성사)", "audio": (597.45, 601.60), "en": "So I'm taking a deal with Lori. / Hey, guys! Yes!",
     "sub": ["로리랑 할게요!", "예스!"], "facts": ["f13"], "cap_at": [597.50, 600.95],
     "fx": "초록 번쩍 — 벤치 QMJ 45.7 거래 성공(두 팔 든 컷 첫 프레임)",
     "cuts": [(CLIP, 597.45, 598.198, crop(CLIP, 960), "마크가 봄(원본 반응 컷)"),
              (CLIP, 598.198, 598.898, crop(CLIP, 1000), "창업자가 웃으며 말함(말하는 본인)"),
              (CLIP, 598.898, 599.766, crop(CLIP, 960), "케빈 반응"),
              (CLIP, 599.766, 600.80, crop(CLIP, 880), "로리가 손뼉 침"),
              (CLIP, 600.80, 601.60, crop(CLIP, 1320), "창업자가 두 팔을 들고 환호")]},
    {"id": "N7", "kind": "나레", "beat": "방송 결과", "text": "결국 케빈 제안은 날아가고 로리 손을 잡았다고",
     "tts": "결국 케빈 제안은 날아가고 로리 손을 잡았다고", "sub": ["결국 케빈 제안은 날아가고", "로리 손을 잡았다고"], "facts": ["f12", "f13"],
     "cuts": [(CLIP, 607.95, 610.60, crop(CLIP, 1365), "창업자가 활짝 웃으며 팔을 듦(근접, 샷 607.91~611.88)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/8편_Flipstik/work/render/render_info.json")


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
        for c in L["cuts"]:
            vid, a, b, cr, ours = c
            dur = round((b - a) * scale, 3)
            f, ss = src_of(vid, a)
            au = {"mute": True} if L["kind"] == "나레" else {"mute": False, "audio_src": AUDIO, "audio_ss": a, "audio_dur": dur}
            shots.append({"i": len(shots), "line": L["id"], "kind": L["kind"], "src": f, **au,
                          "url": f"https://www.youtube.com/watch?v={vid}", "src_orig_span": [a, round(a + dur, 3)], "ss": ss,
                          "dur": dur, "t_final_est": [round(t, 2), round(t + dur, 2)], "res": "%dx%d" % FILES[vid][2],
                          "src_crop": cr, "scale": round(WIN[0] / cr[2], 3), "ours": ours,
                          "audio": "원본 소리(원음)" if L["kind"] == "원음" else "원본 소리 끔 + TTS"})
            t += dur
    return shots, round(t, 2)


def frame(path: str, ss: float, cr) -> Image.Image:
    x, y, w, h = cr
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-i", path, "-frames:v", "1", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale=270:263", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
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
    d.text((8, 8), f"샥탬스토리 8편 Flipstik — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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
        if L.get("fx") and s == next(x for x in shots if x["line"] == s["line"]):
            for n, part in enumerate(_wrap("효과: " + L["fx"], 40)):
                d.text((tx, y0 + 215 + n * 16), part, fill=(200, 0, 0), font=small)
    S.save(out, quality=82)


def check(shots, total):
    durs = sorted(s["dur"] for s in shots)
    med = durs[len(durs) // 2] if len(durs) % 2 else (durs[len(durs) // 2 - 1] + durs[len(durs) // 2]) / 2
    seen, overlap = [], []
    for s in shots:
        vid = s["url"][-11:]
        a, b = s["src_orig_span"]
        for (v2, a2, b2, i2, l2) in seen:
            forward = a >= b2 - 0.01 and (l2 == s["line"] or i2 == s["i"] - 1)
            if v2 == vid and a < b2 + 3 and a2 < b + 3 and not forward:
                overlap.append((i2, s["i"]))
        seen.append((vid, a, b, s["i"], s["line"]))
    narr = sum(nchar(L["tts"]) for L in LINES if L["kind"] == "나레")
    narr_s = sum(line_dur(L) for L in LINES if L["kind"] == "나레")
    return {"길이_추정": total, "컷": len(shots), "컷_중앙": round(med, 2), "컷_최소": durs[0],
            "±3초_재사용(다른 줄)": overlap, "나레_자수(TTS,공백뺌)": narr, "나레_초": round(narr_s, 2),
            "자막_최대자수": max(len(x) for L in LINES for x in L["sub"]),
            "원음_초": round(sum(line_dur(L) for L in LINES if L["kind"] == "원음"), 2)}


TITLES = {"line1": "어디든 폰 붙이는", "line2": "스티커의 반전?!"}

FACTS = {
    "f1": ("원본 88.86~90.30 'This is Flipstick.'(faster-whisper 낱말 시각 + 구간 2모델 span_v4 앞부분 'This is') · BBH 벤치 0.16초 같은 말", "방송 원음"),
    "f2": ("원본 90.80~93.74 'Flipstick is a paper-thin device that goes on the back of your phone'(whisper·span_v2 2모델 일치) · 화면 91~97 폰 뒷면 근접", "방송 원음(창업자 설명 — 전언체)"),
    "f3": ("원본 107.28~109.84 'essentially it lets you stick your phone anywhere' · 110.20 'Cool.'(마크 샷 110.18~110.81) · 110.78~113.54 'And when I say stick, I mean it really sticks'(whisper·span_v3 2모델)", "방송 원음"),
    "f4": ("원본 113.54~119.16 'this is not going anywhere until you give it a little twist and it comes off'(whisper·span_v2 2모델 일치). 뒤 낱말은 갈림(whisper·BBH 자막 'without damaging the surface' / 30초 창 1모델 'without residue') → 나레에 안 씀", "방송 원음(창업자 주장 — 전언체)"),
    "f5": ("원본 140.0~145.6 'I have hair, I got sand, and I got my mama's homemade spaghetti' · 146.2~159.8 'get this Flipstick really dirty … hair … sand … spaghetti' · 162.18~164.46 'This ain't sticking to nothing, all right?'(whisper + 30초 창 2모델 'isn't/ain't')", "방송 원음+화면"),
    "f6": ("원본 167.3~175.1 'Watch as we wipe away all the dirt and grit and sand … Nice and clean' · 175.88~177.78 'And so, who thinks it's gonna stick? / I do.'(whisper·span_v4 1모델) · 178.88~181.2 'I have a lot of believers here. Hey!'(whisper·span_v3 2모델) · 화면 181.0~181.98 범벅 폰이 판에 붙음", "방송 원음+화면"),
    "f7": ("원본 315.72~318.88 'On average, it costs us 58 cents to make. We sell these for $15'(whisper·span_v1·v3 2모델 일치)", "방송 원음(창업자 숫자)"),
    "f8": ("원본 386.46~389.52 케빈 'I'll give you a hundred thousand for twenty percent, exactly what you want'(whisper·span_v3 2모델) · 화면 띠 390~392 'Kevin's offer: $100k for a 20% stake'(이름 확인)", "방송 원음+화면 글자"),
    "f9": ("원본 371.2~381.2 'I really want to tell you about competition'(30초 창) · 391.8~413.4 'tell me about your competition … PopSocket … I made you an offer'(30초 창 2모델) — 제안에 바로 답하지 않고 경쟁사 설명", "방송 원음(해석 — 전언체)"),
    "f10": ("원본 484.60~489.60 케빈 'I made you an offer exactly what you wanted before you told me that you only sold $1,500'(whisper·span_v3 2모델) · 456~460 창업자 'last month … $1,500'(span_v2 2모델)", "방송 원음"),
    "f11": ("원본 512.62~518.94 로리 'So, here's my offer. I'm gonna give you the $100,000, but I want 25%'(whisper·span_v5 2모델) · 화면 띠 528~530 'Lori's offer: $100k for a 25% stake' · 처음 요청 74.6~78.4 '$100,000 for 20%'(30초 창) — 5%p 차이", "방송 원음+화면 글자"),
    "f12": ("원본 492.8~504.7 케빈 'When I make an offer on Shark Tank, I am the only Mr. Wonderful … You should have taken it. Now you only have one shark.'(whisper·span_v2 2모델) · 공식 제목 'Kevin Retracts His Offer After Flipstik Entrepreneur Hesitates'", "방송 원음+공식 제목"),
    "f13": ("원본 597.50~598.70 'So I'm taking a deal with Lori.'(whisper·span_v3 2모델) · 599.6~601.4 'Hey, guys! … Yes!'", "방송 원음"),
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
    S["topic"] = ("Flipstik(폰 뒤에 붙이는 초박형 접착 덮개) — 샤크탱크 S12E4, 10만 달러/20% 요청 → 케빈이 그대로 제안 → 창업자가 바로 안 받고 설명을 이어가자 "
                  "케빈이 제안 취소 → 로리 10만 달러/25% 수락(방송 안 결과)")
    S["bench"] = {"id": "ec6-kas1jVs", "channel": "BIG BAG HUSTLE @BIGBAGHUSTLE(소재·원음 순간)", "title": "Phone Gadget That Changes Everything",
                  "dur": 45.81, "views": 23283041,
                  "form_bench": "해외쇼츠 @foreignshowshow 공식 6박자(0초 결말 반응 빨간 원·효과·자막 꼴) — 같은 제품 판 없음(채널 4곳 쇼츠 목록 검색, 근거.md §0)",
                  "window": [0, 434, 1080, 1052]}
    S["form"] = "방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」"
    S["facts"] = {k: {"text": v[0], "url": f"https://www.youtube.com/watch?v={CLIP}", "kind": v[1]} for k, v in FACTS.items()}
    S["dropped"] = ["BBH 1.0~6.4 'paper thin device … on the back of your phone' 원음 → 나레 N1 로(같은 사실, 컷 길이 맞춤)",
                    "BBH 16.7~22 'It's not just glass … textured tile surface' 원음 — 길이 때문에 뺌",
                    "'comes off without damaging the surface' — 받아쓰기 갈림('without residue') → 나레 N2 는 '쏙 떨어진다'까지만",
                    "케빈 'Now you only have one shark. I'm out.'(503.68~) — 0초 훅(501.85~503.30)과 3초 안 → 재사용 검사(B13) 때문에 뺌, 끝 나레 N7 '케빈 제안은 날아가고'로",
                    "바바라·데이먼드 빠짐(경쟁사 Love Handle, 420~452초)·로리 설득(457~480)·마크 침묵 — 길이 때문에 뺌",
                    "방송 뒤 결과(실제 계약·매출) — 벤치도 안 다룸, 조사 안 함 → 넣지 않음"]
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — BBH 제목 'Phone Gadget That Changes Everything'·해외쇼츠 꼴, 줄당 ≤12자(rules title.line_chars_max)"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    shots, total = build()
    mat = {"_note": "샥탬스토리 8편 Flipstik 재료 계획 — TTS·렌더 전. 창 1080x1052(채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물). 원음 컷은 src_orig_span 그대로 원본 소리(MJO3kI8D974_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Kevin Retracts His Offer After Flipstik Entrepreneur Hesitates",
                      "업로드": "2021-06-07", "해상도": "1920x1080 29.97fps (137 + 140 영어 단일 트랙)", "길이": 635.8, "받은 구간": "전체",
                      "남의 글자": "방송 이름·제안 띠(72~77·79~81·380~382·390~392·528~548초) — 그 구간 안 씀. 로고·워터마크 없음(시트 확인). "
                                 "화면의 'flipstik DEFY GRAVITY' 무대 화면·'STICK YOUR PHONE HERE' 시연 판·티셔츠·포장 = 제품 자체 글자"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": TITLES, "shots": shots, "cand_dir": str(SRC).replace("\\", "/")}
    # 꾸밈 — 해외쇼츠 공식 박자(rules placement) 자리. 원 = 얼굴 검출, 점선 원 = 사람, 화살표 = 대상 상자(사람이 고름) → 렌더 전 fx_place.fix 가 다시 잰다
    win_s = WIN[1] / 1080
    o3 = next(L for L in LINES if L["id"] == "O3")["cuts"][0][3]
    ph = [600, 160, 1440, 580]          # 원본 108.0초 판에 붙은 폰 상자(sheet/full1.jpg 100px 격자 눈 판독)
    tgt = [int((ph[0] - o3[0]) * win_s), int(434 + ph[1] * win_s), int((ph[2] - o3[0]) * win_s), int(434 + ph[3] * win_s)]
    n3 = next(L for L in LINES if L["id"] == "N3")["cuts"][0][3]
    pb = [380, 360, 1020, 1080]         # 원본 148.5초 창업자 몸 상자(full1.jpg)
    pbox = [int((pb[0] - n3[0]) * win_s), int(434 + pb[1] * win_s), int((pb[2] - n3[0]) * win_s), min(1486, int(434 + pb[3] * win_s))]
    from tools.calcopy.shark import fx_place as P
    A = P.on_target("arrow_green_down", tgt)
    D = P.on_target("dashed_circle", pbox)
    mat["effects"] = [
        {"line": "O1", "kind": "red_circle", "at": HOOK["at"], "size": HOOK["size"], "t": [0.0, 1.45], "how": "face", "face_src": HOOK["face_src"],
         "fh_win": HOOK["fh_win"], "why": "해외쇼츠 공식 0초 결말 반응 얼굴 빨간 실선 원(QMJ 0.0~0.533, r209 고정) — " + HOOK["why"]},
        {"line": "O3", "kind": "arrow_green_down", "at": A["at"], "t": [0.0, 0.7], "how": "target", "target": tgt, "target_what": "'STICK YOUR PHONE HERE' 판에 붙는 폰",
         "why": "벤치 QMJ 0.567~1.267 첫 시연 제품 위 초록 아래 화살표(위아래 ±9px)"},
        {"line": "O5", "kind": "flash", "color": "초록", "at": [540, 960], "t": [1.595, 2.045], "how": "auto", "why": "벤치 QMJ 7.1·28.1 장면 넘김 초록 번쩍 — 판에 붙은 폰 근접 컷 첫 프레임"},
        {"line": "N3", "kind": "dashed_circle", "t": [0.2, 1.3], "how": "target", "target": "person", "target_what": "폰에 머리카락을 문지르는 창업자(첫 컷)",
         "at": D["at"], "radius": D["radius"], "target_box": pbox, "why": "벤치 QMJ 9.27~11.53 기존 불편을 겪는 사람 빨간 점선 원(중심 고정·150°/초)"},
        {"line": "N3", "kind": "flash", "color": "빨강", "at": [540, 960], "t": [0.0, 0.45], "how": "auto", "why": "벤치 QMJ 11.2 불편 줄 빨강 번쩍"},
        {"line": "O8", "kind": "flash", "color": "초록", "at": [540, 960], "t": [1.601, 2.051], "how": "auto", "why": "벤치 QMJ 45.7 성공 초록 번쩍 — 범벅 폰이 판에 붙은 컷 첫 프레임"},
        {"line": "O9", "kind": "arrow_pink_up", "at": [533, 1230], "t": [0.0, 1.5], "how": "auto", "why": "벤치 QMJ 12.017~13.82 숫자 조각 분홍 위 화살표 — '원가는 58센트'"},
        {"line": "O10", "kind": "flash", "color": "초록", "at": [540, 960], "t": [0.0, 0.45], "how": "auto", "why": "벤치 QMJ 38.667 투자 제안 컷 초록 번쩍(돈다발과 같은 프레임)"},
        {"line": "O10", "kind": "money_emoji", "at": [537, 1189], "t": [0.033, 1.333], "how": "auto", "why": "벤치 QMJ 38.7~40.0 날개 돈다발(제안 금액 줄)"},
        {"line": "O11", "kind": "flash", "color": "빨강", "at": [540, 960], "t": [0.0, 0.45], "how": "auto", "why": "벤치 QMJ 44.367 결정 빨강 번쩍 — 케빈 취소"},
        {"line": "O13", "kind": "flash", "color": "초록", "at": [540, 960], "t": [3.35, 3.80], "how": "auto", "why": "벤치 QMJ 45.667 거래 성공 초록 번쩍 — 두 팔 든 컷 첫 프레임"}]
    doc_update()
    (HERE / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--no-sheet" not in sys.argv:
        (HERE / "plan").mkdir(exist_ok=True)
        sheet(shots, HERE / "plan" / "계획_시트.jpg", " / ".join(TITLES.values()))
    c = check(shots, total)
    print(json.dumps(c, ensure_ascii=False))
    for x in shots:
        print(x["i"], x["line"], x["kind"], x["src_orig_span"], x["dur"], x["t_final_est"], x["src_crop"], file=sys.stderr)
    return shots, c


if __name__ == "__main__":
    main()
