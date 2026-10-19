# -*- coding: utf-8 -*-
"""샥탬스토리 12편 Chill Systems — 소재 벤치 Spark_Moment qRhDJRH63Ec(「가장 큰 경쟁자는 얼음」 180만) 칼카피 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py channel/foreignshowshow/12편_ChillSystems/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json · 재료.json · plan/계획_시트.jpg 를 만든다(7편 make_plan.py 꼴).
원음 줄 = 벤치가 쓴 원음 순간을 **공식 원본(Shark Tank Global ULws5gyPTHY 597초) 시각**으로 — 근거.md §2 표.
같은 제품 쇼츠: @foreignshowshow·@BIGBAGHUSTLE·海外ショーショー 채널 검색 0편(근거.md §0) → 줄 흐름은 Spark 쇼츠, 0초 훅·효과·자막 꼴은 foreignshowshow 공식 6박자.
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
WORK = Path("C:/숏템_칼카피/foreignshowshow/12편_ChillSystems")
SRC = WORK / "src"
CLIP = "ULws5gyPTHY"
FILES = {CLIP: ("ULws5gyPTHY.mp4", 0.0, (1920, 1080))}
AUDIO = "ULws5gyPTHY_audio.m4a"        # 공식 원본 영어 원음(140, 더빙 트랙 없음 — yt-dlp 포맷 목록 실측)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
H_DEF = {CLIP: 1080}                   # 원본에 방송사 로고·띠 없음(133·562초 전체 프레임 눈 확인) — 109~117초 이름·금액 띠 구간은 안 씀
URL = f"https://www.youtube.com/watch?v={CLIP}"


def crop(vid, cx, y=0, h=None):
    W, H = FILES[vid][2]
    h = h or H_DEF[vid]
    w = int(round(h * AR))
    x = max(0, min(W - w, int(cx - w / 2)))
    return [x, y, w, h]


# 원음 줄 audio = (원본 시작, 끝). cut = (소스, 원본 시작, 원본 끝, [x,y,w,h], 화면에 보이는 것). 샷 경계 = asr/src_scenes012.txt(scene>0.12)
LINES = [
    {"id": "O1", "kind": "원음", "beat": "0초 훅(질문)", "audio": (301.30, 303.00), "en": "Who is your number one competitor?",
     "sub": ["가장 큰 경쟁자가", "누구예요?"], "facts": ["f1"], "cap_at": [301.30, 302.29],
     "fx": "0초 빨간 실선 원 — 제품(분홍 Chill 쿨러 로고). 벤치 Spark 0초 = 같은 제품 컷 + 같은 질문 원음",
     "cuts": [(CLIP, 301.30, 301.915, crop(CLIP, 1000), "분홍 'Chill' 쿨러 제품 컷 + 얼음 조각(원본 299.87~301.94 샷 끝, 벤치 0초와 같은 샷)"),
              (CLIP, 301.915, 303.00, crop(CLIP, 890), "빨간 원피스 금발 투자자가 질문(말하는 본인, 샷 301.94~303.34)")]},
    {"id": "O2", "kind": "원음", "beat": "0초 훅(답)", "audio": (303.40, 304.10), "en": "Ice.", "sub": ["얼음이요"], "style": "원음반응_크게",
     "facts": ["f1"], "cap_at": [303.45],
     "cuts": [(CLIP, 303.40, 304.10, crop(CLIP, 920), "창업자 두 사람이 손 모으고 '얼음'(말하는 본인 쪽, 샷 303.34~304.14)")]},
    {"id": "O3", "kind": "원음", "beat": "0초 훅(반응)", "audio": (304.20, 306.40), "en": "Ice? (투자자 웃음)", "sub": ["얼음이라고요?"],
     "style": "원음반응_크게", "facts": ["f1"], "cap_at": [304.55],
     "cuts": [(CLIP, 304.20, 305.585, crop(CLIP, 920), "금발 투자자가 되물음(말하는 본인, 샷 304.14~305.61)"),
              (CLIP, 305.585, 306.40, crop(CLIP, 1000), "남색 정장 투자자가 얼굴을 감싸고 웃음(원본 다음 샷 — 웃음소리, 말 없음 306.53 전까지)")]},
    {"id": "N1", "kind": "나레", "beat": "시연(정체)", "text": "얼음 없이 음료를 차갑게 해 준다는 쿨러인데", "tts": "얼음 없이 음료를 차갑게 해 준다는 쿨러인데",
     "sub": ["얼음 없이 음료를", "차갑게 해 준다는", "쿨러인데"], "facts": ["f2"],
     "cuts": [(CLIP, 65.00, 66.30, crop(CLIP, 960), "검은 원통 쿨러에 병을 꽂아 들어 보이는 손 근접(샷 64.93~67.17)"),
              (CLIP, 79.10, 80.40, crop(CLIP, 680), "빨간 원통 쿨러에 병이 꽂힌 근접(샷 78.91~82.58)")]},
    {"id": "O4", "kind": "원음", "beat": "기존 불편", "audio": (30.05, 31.80), "en": "Sorry I'm late. I had to buy ice.",
     "sub": ["늦어서 죄송해요", "얼음 사 오느라고요"], "facts": ["f3"], "cap_at": [30.10, 30.86],
     "fx": "빨간 점선 원(얼음 봉지 든 창업자) + 빨강 번쩍 — foreignshowshow 불편 박자(벤치 Spark 엔 이 장면 없음)",
     "cuts": [(CLIP, 30.05, 31.80, crop(CLIP, 1250), "늦게 온 창업자가 얼음 봉지를 들고 들어와 말함(말하는 본인, 샷 28.43~31.83)")]},
    {"id": "O5", "kind": "원음", "beat": "숫자(문제)", "audio": (130.07, 136.40),
     "en": "It only holds three cans. I mean, I don't know about you, but I'll get through this in about 45 minutes.",
     "sub": ["딱 세 캔밖에", "안 들어가네요", "솔직히 저는", "45분이면 다 마셔요"], "facts": ["f4"], "cap_at": [130.07, 130.94, 132.36, 134.14],
     "fx": "초록 번쩍 — 장면 넘김(벤치 Spark 7.8 같은 원음)",
     "cuts": [(CLIP, 130.07, 132.112, crop(CLIP, 920), "대머리 투자자가 'KEVIN' 쿨러 샘플을 들고 말함(말하는 본인, 샷 130.06~132.13)"),
              (CLIP, 132.112, 133.914, crop(CLIP, 920), "키 큰 창업자가 듣고 있음(원본 반응 컷 — 원본 편집 그대로)"),
              (CLIP, 133.914, 136.40, crop(CLIP, 900), "대머리 투자자가 이어 말함(샷 133.93~136.74)")]},
    {"id": "O6", "kind": "원음", "beat": "도발", "audio": (136.76, 141.20),
     "en": "And you know, Kevin, we've heard that feedback before from macho men on the internet. Only three beers?",
     "sub": ["그런 말 많이 들었어요", "인터넷 마초들한테요", "'겨우 세 캔?'이냐고"], "facts": ["f5"], "cap_at": [136.98, 138.62, 140.28],
     "cuts": [(CLIP, 136.76, 139.987, crop(CLIP, 900), "키 큰 창업자가 웃으며 받아침(말하는 본인, 샷 136.74~140.01)"),
              (CLIP, 139.987, 141.20, crop(CLIP, 1250), "무대 와이드 — 창업자가 투자자 말투를 흉내(샷 140.01~142.14)")]},
    {"id": "N3", "kind": "나레", "beat": "도발(해설)", "text": "투자자를 인터넷 마초에 빗대 버린 셈인데", "tts": "투자자를 인터넷 마초에 빗대 버린 셈인데",
     "sub": ["투자자를", "인터넷 마초에", "빗대 버린 셈인데"], "facts": ["f5"],
     "cuts": [(CLIP, 142.30, 144.80, crop(CLIP, 1000), "대머리 투자자가 쿨러를 무릎에 두고 듣는 얼굴(샷 142.14~145.05)")]},
    {"id": "O7", "kind": "원음", "beat": "숫자(원가)", "audio": (160.20, 165.38),
     "en": "What's the cost? OK. The chiller you have in front of you, our product cost is awful.",
     "sub": ["원가가 얼마죠?", "앞에 놓인 그 제품은", "원가가 끔찍해요"], "facts": ["f6"], "cap_at": [160.26, 162.06, 164.18],
     "cuts": [(CLIP, 160.20, 162.175, crop(CLIP, 800), "남색 정장 투자자가 질문(말하는 본인, 샷 160.09~162.20)"),
              (CLIP, 162.175, 164.044, crop(CLIP, 960), "투자자석 쪽 와이드(원본 편집 그대로)"),
              (CLIP, 164.044, 165.38, crop(CLIP, 960), "짧은 머리 창업자가 '끔찍해요'(말하는 본인, 샷 164.06~165.40)")]},
    {"id": "N5", "kind": "나레", "beat": "숫자(해설)", "text": "원가를 다시 따져 보니 자꾸 불어났다는데", "tts": "원가를 다시 따져 보니 자꾸 불어났다는데",
     "sub": ["원가를 다시", "따져 보니", "자꾸 불어났다는데"], "facts": ["f7"],
     "cuts": [(CLIP, 176.60, 177.95, crop(CLIP, 920), "짧은 머리 창업자가 원가를 하나씩 설명(샷 176.~177.98)"),
              (CLIP, 181.00, 182.60, crop(CLIP, 900), "두 창업자 무대 중간 샷(샷 180.28~183.65)")]},
    {"id": "O9", "kind": "원음", "beat": "숫자(37달러)", "audio": (185.60, 187.83),
     "en": "$37 for that one that you have in front of you. / To make it?",
     "sub": ["앞에 있는 그 제품이", "37달러까지 갔어요", "만드는 데요?"], "facts": ["f7"], "cap_at": [185.60, 186.40, 187.42],
     "fx": "분홍 위 화살표('37달러' 조각) + 초록 번쩍 — 숫자 박자",
     "cuts": [(CLIP, 185.60, 186.433, crop(CLIP, 920), "짧은 머리 창업자 근접(말하는 본인, 샷 184.99~186.45)"),
              (CLIP, 186.433, 187.83, crop(CLIP, 920), "대머리 투자자가 듣다가 '만드는 데요?'(샷 186.45~187.85 — 앞 1초는 듣는 얼굴, 원본 편집 그대로)")]},
    {"id": "O10", "kind": "원음", "beat": "결정(거절)", "audio": (382.45, 384.56), "en": "This is a really bad idea.",
     "sub": ["이건 정말", "최악의 아이디어예요"], "facts": ["f8"], "cap_at": [382.45, 383.03],
     "fx": "빨강 번쩍 — 결정",
     "cuts": [(CLIP, 382.45, 384.56, crop(CLIP, 910), "대머리 투자자(말하는 본인, 샷 382.45~384.58)")]},
    {"id": "O12", "kind": "원음", "beat": "결정(거절)", "audio": (397.55, 399.84), "en": "Look, first of all, your presentation sucked.",
     "sub": ["우선 발표부터가", "형편없었어요"], "facts": ["f8"], "cap_at": [397.55, 398.81],
     "cuts": [(CLIP, 397.55, 398.612, crop(CLIP, 910), "대머리 투자자 듣는 얼굴(원본 반응 컷 — 원본 편집 그대로)"),
              (CLIP, 398.612, 399.84, crop(CLIP, 960), "남색 정장 투자자가 말함(말하는 본인, 샷 398.63~399.87)")]},
    {"id": "N7", "kind": "나레", "beat": "결과", "text": "결국 샤크 누구도 투자하지 않았는데", "tts": "결국 샤크 누구도 투자하지 않았는데",
     "sub": ["결국 샤크", "누구도 투자하지", "않았는데"], "facts": ["f9"],
     "cuts": [(CLIP, 551.00, 552.40, crop(CLIP, 1030), "두 창업자가 고개 숙여 인사하고 돌아섬(샷 550.88~553.29)"),
              (CLIP, 553.40, 555.00, crop(CLIP, 1100), "두 창업자가 복도로 걸어 나감(샷 553.29~560.03)")]},
    {"id": "O13", "kind": "원음", "beat": "결과(퇴장 인터뷰)", "audio": (562.00, 563.72), "en": "and the sharks are gonna wish that they invested.",
     "sub": ["샤크들이", "투자 안 한 걸", "후회할 거예요"], "facts": ["f10"], "cap_at": [562.05, 562.37, 562.79],
     "fx": "초록 번쩍 — 결과",
     "cuts": [(CLIP, 562.00, 563.72, crop(CLIP, 1080), "퇴장 인터뷰 — 키 큰 창업자가 말함(말하는 본인, 샷 560.16~563.83)")]},
]

FACTS = {
    "f1": "원본 301.41~302.91 'Who is your number one competitor?' · 303.57~303.81 'Ice.' · 304.61~305.17 'Ice?' (whisper-small 낱말 시각 + 구간 단독 gemini-flash-latest·3.5-flash-lite 2모델 asr/span_v1.json) · 화면 299.87~301.94 분홍 Chill 쿨러 → 301.94 금발 투자자 → 303.34 창업자 → 304.14 금발 투자자 → 305.61 남색 정장 투자자 웃음",
    "f2": "원본 19.20~21.94 'It's a portable beverage cooler with freezing gel built in.'(whisper + flash-latest·flash-lite-latest asr/span_v1·v2) · 32.04~34.16 'the chiller doesn't need ice'(whisper + 2모델) · 화면 76.28~82.58 분홍·빨간 쿨러",
    "f3": "원본 28.24~31.82 'Hey sharks. This is Brian. Sorry I'm late. I had to buy ice.'(whisper + 2모델 일치) · 화면 28.43~31.83 얼음 봉지 든 창업자. 이름 띠 109~114초 'CHASE MITCHELL & BRIAN BLOCH'(화면 글자) — 자막에는 이름 안 씀",
    "f4": "원본 130.02~131.78 'It only holds three cans.' · 132.36~136.36 'I mean, I don't know about you, but I'll get through this in about 45 minutes.'(whisper + 2모델 일치) · 투자자 앞 쿨러 샘플 글자 'KEVIN'(화면)",
    "f5": "원본 136.66~141.18 'Sure. And you know, Kevin, we've heard that feedback before from macho men on the internet. Only three beers?'(whisper 'Macho Man' · flash-latest 'macho men' · flash-lite-latest 'Macho Man' — 마초 3/3, 단·복수만 갈림) → '빗대 버린 셈'은 해석 → 전언체 '~셈인데'",
    "f6": "원본 160.26~160.94 'What's the cost?' · 162.06~165.38 'The chiller you have in front of you, our product cost is awful.'(whisper + flash-lite-latest)",
    "f7": "원본 172.90~187.42 '$18 a unit to build' → 'import $3.50' → '$22' → 'sleeves another $11' → '$32' → 'all the way up to $37 for that one that you have in front of you' · 187.42~189.08 'To make it? To make it? The cost?' · 190.10 '$37.' · 193.8~196.76 'since then … bring that cost down to $18'(whisper 전체 + d37·wow 구간 flash-lite-latest)",
    "f8": "원본 382.43~384.61 'This is a really bad idea.' · 389.39~394.77 'I don't even buy the sustainability thing … I hate it. I'm out.' · 397.55~399.89 'Look, first of all, your presentation sucked.'(whisper + flash-lite-latest)",
    "f9": "원본 'I'm out' 5회: 394.47 · 414.63('for those reasons, I'm out') · 511.77 · 530.23('So I'm sorry I'm out') · 545.53('I personally am out')(whisper 전체 받아쓰기) + 551~560 두 창업자 퇴장 화면 · 벤치 Spark '아무한테서도 투자받지 못하고'",
    "f10": "원본 562.05~563.67 'and the sharks are gonna wish that they invested.'(whisper + flash-lite-latest) · 화면 560.16~563.83 퇴장 인터뷰(방송 안)",
}


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = WORK / "work/render/render_info.json"


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
            shots.append({"i": len(shots), "line": L["id"], "kind": L["kind"], "src": f, **au, "url": URL,
                          "src_orig_span": [a, round(a + dur, 3)], "ss": ss, "dur": dur, "t_final_est": [round(t, 2), round(t + dur, 2)],
                          "res": "%dx%d" % FILES[vid][2], "src_crop": cr, "scale": round(WIN[0] / cr[2], 3), "ours": ours,
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
    d.text((8, 8), f"샥탬스토리 12편 Chill Systems — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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
        for n, part in enumerate(_wrap(L.get("en") if L["kind"] == "원음" else L["text"], 34)[:4]):
            d.text((tx, y0 + 24 + n * 18), part, fill=(0, 0, 0), font=small)
        d.text((tx, y0 + 100), "자막: " + " / ".join(L["sub"]), fill=(120, 0, 120), font=small)
        d.text((tx, y0 + 140), f"{s['src']} @원본 {s['src_orig_span'][0]}~{s['src_orig_span'][1]} 크롭 {s['src_crop']} ×{s['scale']}", fill=(90, 90, 90), font=small)
        for n, part in enumerate(_wrap(s["ours"], 34)[:3]):
            d.text((tx, y0 + 160 + n * 18), part, fill=(0, 100, 0), font=small)
        if L.get("fx") and s == next(x for x in shots if x["line"] == s["line"]):
            for n, part in enumerate(_wrap("효과: " + L["fx"], 40)[:2]):
                d.text((tx, y0 + 215 + n * 16), part, fill=(200, 0, 0), font=small)
    S.save(out, quality=82)


def check(shots, total):
    durs = sorted(s["dur"] for s in shots)
    med = durs[len(durs) // 2] if len(durs) % 2 else (durs[len(durs) // 2 - 1] + durs[len(durs) // 2]) / 2
    seen, overlap = [], []
    for s in shots:
        a, b = s["src_orig_span"]
        for (a2, b2, i2, l2) in seen:
            forward = a >= b2 - 0.01 and (l2 == s["line"] or i2 == s["i"] - 1)
            if a < b2 + 3 and a2 < b + 3 and not forward:
                overlap.append((i2, s["i"]))
        seen.append((a, b, s["i"], s["line"]))
    narr = sum(nchar(L["tts"]) for L in LINES if L["kind"] == "나레")
    narr_s = sum(line_dur(L) for L in LINES if L["kind"] == "나레")
    return {"길이_추정": total, "컷": len(shots), "컷_중앙": round(med, 2), "컷_최소": durs[0],
            "±3초_재사용(다른 줄)": overlap, "나레_자수(TTS,공백뺌)": narr, "나레_초": round(narr_s, 2),
            "자막_최대자수": max(len(x) for L in LINES for x in L["sub"]),
            "원음_초": round(sum(line_dur(L) for L in LINES if L["kind"] == "원음"), 2)}


TITLES = {"line1": "경쟁자가 얼음이라는", "line2": "3캔짜리 쿨러?!"}


def doc():
    p = HERE / "대본.json"
    old = {}
    if p.exists():
        S0 = json.loads(p.read_text(encoding="utf-8"))
        old = {l["id"]: l for l in (S0.get("final") or {}).get("lines", [])}
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
    S = {"topic": "Chill Systems(얼음 없이 냉동 젤로 캔 3개를 차갑게 하는 휴대 쿨러) — 15만 달러/15% 요청 → '가장 큰 경쟁자는 얼음' · 3캔·원가 37달러 · 발표 태도 → 샤크 전원 거절(방송 안 결과)",
         "bench": {"id": "qRhDJRH63Ec", "channel": "Spark_Moment @Spark_Moments6", "title": "가장 큰 경쟁자는 얼음🧊 (화면 제목: 가장 큰 경쟁자는? / ??: 얼음이요)",
                   "dur": 38.05, "views": 1807648, "window": [0, 434, 1080, 1052],
                   "form_bench": "foreignshowshow 같은 제품 쇼츠 없음 → 소재·원음 순간 = Spark, 0초 훅·효과·자막 꼴 = foreignshowshow 공식 6박자(공통 지시)"},
         "form": "방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
         "voice": VOICE,
         "facts": {k: {"text": v, "url": URL, "kind": "방송 원음+화면"} for k, v in FACTS.items()},
         "dropped": [
             "벤치 나레 '이 제품은 한 번에 음료 세 병을 칠링할 수 있는 아이스박스입니다' — 존댓말 설명체 → 우리 반말 전언체 N1('얼음 없이 … 쿨러인데')로, 3병은 O5 원음(Kevin)으로",
             "벤치 나레 '이들은 또 큰 실수를 합니다' + 원음 'Never ever start …'(167.40~168.56) — 받아쓰기 끝이 잘림('never ever start' 뒤 낱말 없음) = 번역 확정 못 함 + 길이 → 뺌",
             "벤치 나레 '비용을 다시 묻자' → 원본엔 다시 묻는 말이 없음(창업자가 이어서 원가를 쌓아 설명, 172.9~187.4) → N5 '원가를 다시 따져 보니 자꾸 불어났다는데'",
             "벤치 나레 '하지만 발표자들의 태도에 분노하는데' — 원본 근거 = 플라스틱·친환경 주장 불신(389~393)·발표(397~399). '분노'는 해석 → 빼고 원음 O10·O12 로 보여 줌",
             "벤치 마무리 '방송 후 이야기는 댓글에서 확인하세요' — 방송 후 사실(매출·회사 현황) 조사 안 함 → 방송 안 퇴장 인터뷰 원음(O13)으로 닫음",
             "원본 '6시간'(150.52) — 2모델 갈림('Six hours'/'12 hours') → 안 씀",
             "15만 달러/15% 요청(110.32~113.40, 화면 띠 'Seeking $150k for a 15% stake') — 벤치도 안 다룸, 길이 → 뺌"],
         "final": {"lines": out, "cps_target": 7.8},
         "titles": {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '가장 큰 경쟁자는? / ??: 얼음이요'와 3어절 연속 겹침 0, 줄당 ≤12자(rules title.line_chars_max)"},
         "render": {"gap": 0.03}}
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    shots, total = build()
    mat = {"_note": "샥탬스토리 12편 Chill Systems 재료 계획 — TTS·렌더 전. 창 1080x1052(채널 고정 [0,434,1080,1052]). make_plan.py LINES 가 정본(이 파일은 생성물). "
                    "원음 컷은 src_orig_span 그대로 원본 소리(영어 원음 ULws5gyPTHY_audio.m4a).",
           "sources": {CLIP: {"채널": "Shark Tank Global(공식)", "제목": "\"It Only Holds Three Cans?\" The Sharks Question Chill Systems | Shark Tank US | Shark Tank Global",
                              "해상도": "1920x1080 29.97fps (137 + 140 영어 원음)", "길이": 596.99, "받은 구간": "전체", "업로드": "2022-01-25", "조회": 1921948,
                              "남의 글자": "방송사 로고 없음(133·562초 전체 프레임). 109~117초 이름·금액 띠 'CHASE MITCHELL & BRIAN BLOCH'·'Seeking $150k for a 15% stake' — 그 구간 안 씀. "
                                         "392.4~394.3 제품 'YOUR LOGO HERE' 글자 — 안 씀. 쿨러 'Chill'·셔츠 'CS CHILL SYSTEMS'·샘플 'KEVIN' = 제품·소품 글자"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": TITLES, "shots": shots, "cand_dir": str(SRC).replace("\\", "/")}
    # 꾸밈 — foreignshowshow 공식 6박자 자리(rules placement). 빨간 원 = 제품(Chill 로고) 물건 원: 크롭 [446,0,1108,1080] ×0.975 에서 로고 중심 원본 (1050,465) → 완성본 (589,887)
    mat["effects"] = [
        {"line": "O1", "kind": "red_circle", "at": [589, 887], "size": 430, "stroke": 11, "t": [0.0, 0.615], "how": "target", "target": "object",
         "target_what": "분홍 Chill 쿨러의 'Chill' 로고(원본 301.6초 프레임 sheet/hook_301.6.jpg 격자 — 로고 상자 원본 x 880~1220·y 370~560)",
         "why": "foreignshowshow 0초 빨간 실선 원(QMJ 0.000~0.533, 첫 컷과 같이 사라짐) — 벤치 Spark 0초가 같은 제품 컷이라 물건 원(벤치 8편 중 3편이 물건 원). 크기·선은 rules 고정값",
         "engine": "fx_place.fix 금지(red_circle 을 얼굴로 덮어씀, 7편과 같은 엔진 요청)"},
        {"line": "O4", "kind": "dashed_circle", "at": [560, 900], "t": [0.17, 1.77], "how": "target", "target": "person", "radius": 300,
         "target_what": "얼음 봉지를 든 늦게 온 창업자(사람 검출로 자리 계산 — fx_place, at 은 자리표)", "why": "벤치 QMJ 9.27~11.53 기존 불편 사람 빨간 점선 원(컷 +0.17 등장)"},
        {"line": "O4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "불편 박자 빨강 번쩍(QMJ 11.2)"},
        {"line": "O5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "장면 넘김 초록 번쩍(QMJ 7.1)"},
        {"line": "O9", "kind": "arrow_pink_up", "at": [533, 1230], "t": [0.8, 2.6], "how": "auto", "why": "숫자 조각 분홍 위 화살표 — '37달러까지 갔어요'(QMJ 12.017~13.82)"},
        {"line": "O9", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "숫자 와우 초록 번쩍"},
        {"line": "O10", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "결정(거절) 빨강 번쩍(QMJ 44.4)"},
        {"line": "O13", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "결과 초록 번쩍(QMJ 45.7)"}]
    doc()
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
