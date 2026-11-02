# -*- coding: utf-8 -*-
"""샥탬스토리 11편 Copper Cow Coffee — 소재 벤치 BIG BAG HUSTLE MzQdks2-D-I(「Perfect Coffee Without a Machine」 1,279만) 칼카피 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py channel/foreignshowshow/11편_CopperCow/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json · 재료.json · plan/계획_시트.jpg 를 만든다.
원음 줄 = 벤치가 쓴 원음 순간을 **같은 원본(Sony 공식 풀 피치 Ij6BNYohK2o) 시각**으로 — 근거.md §2 표.
원음 시각 = 로컬 faster-whisper small 낱말 시각(asr/fw_words.json) + 장면 경계(asr/src_scenes.txt), 말 = 제미나이 2모델(asr/src_30s.json·span_w*.json) 교차.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/11편_CopperCow/src")
CLIP, TXJ, BOX = "Ij6BNYohK2o", "tXJe96m7pFE", "Pbt3hLQ5Z28"
FILES = {CLIP: ("Ij6BNYohK2o.mp4", 0.0, (1920, 1080)), TXJ: ("tXJe96m7pFE.mp4", 0.0, (1920, 1080)),
         BOX: ("Pbt3hLQ5Z28.mp4", 0.0, (1920, 1080))}   # (파일, 파일 0초 = 원본 초, 크기)
AUDIO = "Ij6BNYohK2o_audio.m4a"        # 원본 영어 원음(140, 오디오 트랙 1개뿐 — 더빙 없음 yt-dlp -F 확인)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
H_DEF = {CLIP: 1080, TXJ: 1080, BOX: 1080}   # Sony 원본은 로고·띠 없음(이름·제안 띠 구간은 안 씀 — 근거.md §5)


def crop(vid, cx, y=0, h=None):
    W, H = FILES[vid][2]
    h = h or H_DEF[vid]
    w = int(round(h * AR))
    x = max(0, min(W - w, int(cx - w / 2)))
    return [x, y, w, h]


HOOK2 = [439, 54, 1053, 1026]   # O1 둘째 컷 크롭 = fx_place.fix 가 첫 컷에 준 크롭(같은 샷 이음) — fix 뒤 값이 바뀌면 여기도 맞춘다

# 원음 줄 audio = (원본 시작, 끝) — 원본 초. cut = (소스, 원본 시작, 원본 끝, [x,y,w,h], 화면에 보이는 것)
LINES = [
    {"id": "O1", "kind": "원음", "beat": "0초 반응(훅)", "audio": (197.50, 200.95),
     "en": "I've never seen anything like it. It's really clever, this packaging.",
     "sub": ["이런 건 처음 봐요", "포장이 진짜 기발하네요"], "style": "원음반응_크게", "facts": ["f1"], "cap_at": [197.50, 199.10],
     "fx": "0초 빨간 실선 원(투자자 얼굴, fx_place.fix 얼굴 검출) — 벤치 BBH 0초 = 같은 원본 같은 순간(커피 마시는 투자자)",
     "cuts": [(CLIP, 197.50, 198.30, crop(CLIP, 930), "파란 재킷 투자자가 종이컵 커피를 마심(원본 반응 컷 — 벤치 0~3초와 같은 샷). 0초 원 = 이 컷(원 0.80초)의 얼굴로 fx_place.fix 가 크롭 계산"),
              (CLIP, 198.30, 200.27, HOOK2, "같은 샷 이어서 — 컵을 내리고 웃음(크롭 = 첫 컷 fix 크롭과 같게, 이음 없음)"),
              (CLIP, 200.27, 200.95, crop(CLIP, 900), "금발 여성 투자자가 커피 봉지를 들고 말함(말하는 본인 — 목소리 f0 210Hz 여성, 제미나이 화자 같음)")]},
    {"id": "N1", "kind": "나레", "beat": "해답(제품)", "text": "커피 머신 없이 컵에 걸어서 내려 마시는 커피", "tts": "커피 머신 없이 컵에 걸어서 내려 마시는 커피",
     "sub": ["커피 머신 없이", "컵에 걸어서", "내려 마시는 커피"], "facts": ["f2"],
     "fx": "초록 아래 화살표 — 벤치 QMJ 0.567 둘째 컷 제품(컵에 건 드립 필터)",
     "cuts": [(CLIP, 41.90, 43.70, crop(CLIP, 760), "방송 삽입 화면(분홍 배경): 유리컵에 건 드립 필터에 물을 부음 — 글자 없음"),
              (TXJ, 5.00, 6.30, crop(TXJ, 1000), "판매사 공식 영상: 두 손으로 필터 걸이를 펼치는 손 근접(카메라 고정 구간 — 7.5~8.45 는 확대 움직임이라 점프줌으로 잡혀 바꿈)")]},
    {"id": "O3", "kind": "원음", "beat": "시연", "audio": (70.28, 74.02), "en": "Gently hang it over your cup, and then tear off the top,",
     "sub": ["컵에 살짝 걸고", "윗부분을 뜯어요"], "facts": ["f3"], "cap_at": [70.28, 72.86],
     "cuts": [(CLIP, 70.28, 74.02, crop(CLIP, 960), "창업자 손이 필터를 컵에 걸고 윗부분을 뜯음(근접, 말하는 본인 손)")]},
    {"id": "N3", "kind": "나레", "beat": "시연(결과)", "text": "뜨거운 물만 부으면 커피가 컵으로 바로 똑똑 떨어지고",
     "tts": "뜨거운 물만 부으면 커피가 컵으로 바로 똑똑 떨어지고", "sub": ["뜨거운 물만 부으면", "커피가 컵으로", "바로 똑똑 떨어지고"], "facts": ["f4"],
     "fx": "빨간 곡선 화살표 — 벤치 QMJ 20.4 둘째 시연(컵으로 떨어지는 커피 줄기)",
     "cuts": [(CLIP, 77.30, 78.90, crop(CLIP, 864), "필터에서 커피가 유리컵으로 떨어짐(근접)"),
              (CLIP, 102.20, 103.90, crop(CLIP, 900), "다 내린 커피 두 잔 — 밀크 커피와 블랙(근접)")]},
    {"id": "O4", "kind": "원음", "beat": "시연", "audio": (88.12, 91.50), "en": "Once brewed, then you get to add your Copper Cow Creamer,",
     "sub": ["다 내려지면", "코퍼카우 크리머 추가!"], "facts": ["f5"], "cap_at": [88.12, 89.46],
     "cuts": [(CLIP, 88.12, 91.50, crop(CLIP, 960), "창업자가 크리머 봉지를 들어 보임(말하는 본인)")]},
    {"id": "N5", "kind": "나레", "beat": "기존 불편", "text": "한 투자자는 커피 한 잔 사려고 두 시간이나 줄을 섰었다는데",
     "tts": "한 투자자는 커피 한 잔 사려고 두 시간이나 줄을 섰었다는데", "sub": ["한 투자자는", "커피 한 잔 사려고", "두 시간이나", "줄을 섰었다는데"], "facts": ["f6"],
     "fx": "빨간 점선 원(대상 = 말하는 투자자, 사람 검출) + 빨강 번쩍 — 벤치 QMJ 9.27·11.2 불편",
     "cuts": [(CLIP, 132.00, 133.90, crop(CLIP, 930), "검은 정장·분홍 넥타이 투자자가 커피를 저으며 말함(그 말 하는 본인, 소리 끔)"),
              (CLIP, 136.30, 137.90, crop(CLIP, 886), "같은 투자자가 컵을 들고 이어 말함")]},
    {"id": "O6", "kind": "원음", "beat": "기존 불편(반응)", "audio": (141.34, 144.30), "en": "Are you telling me that I didn't have to wait out there for two hours?",
     "sub": ["그럼 두 시간이나", "줄 설 필요 없었다고요?"], "facts": ["f7"], "cap_at": [141.34, 142.70],
     "cuts": [(CLIP, 141.34, 143.44, crop(CLIP, 900), "파란 재킷 투자자(원본 반응 컷 — 원본 편집 그대로)"),
              (CLIP, 143.44, 144.30, crop(CLIP, 930), "검은 정장 투자자가 컵을 들고 말함(말하는 본인)")]},
    {"id": "O7", "kind": "원음", "beat": "해답(반응)", "audio": (144.60, 147.56), "en": "Nope. And you don't need to buy any additional equipment. / This is great.",
     "sub": ["네!", "장비도 따로 필요 없어요", "이거 좋네요!"], "facts": ["f8"], "cap_at": [144.60, 145.06, 147.06],
     "cuts": [(CLIP, 144.60, 145.04, crop(CLIP, 930), "검은 정장 투자자(앞 샷 끝)"),
              (CLIP, 145.04, 146.81, crop(CLIP, 920), "창업자가 손짓하며 답함(말하는 본인)"),
              (CLIP, 146.81, 147.56, crop(CLIP, 930), "검은 정장 투자자가 커피를 마시며 '좋네요'(말하는 본인)")]},
    {"id": "O8", "kind": "원음", "beat": "숫자", "audio": (229.66, 232.42), "en": "So total sales to date is 4 million. / 4 million?",
     "sub": ["지금까지 총매출이", "400만 달러예요", "400만 달러?!"], "facts": ["f10"], "cap_at": [229.66, 230.36, 231.76],
     "fx": "초록 번쩍 + 분홍 위 화살표('400만 달러예요' 조각) — 벤치 QMJ 12.0 숫자 조각",
     "cuts": [(CLIP, 229.66, 231.23, crop(CLIP, 908), "창업자가 두 손을 펴며 말함(말하는 본인)"),
              (CLIP, 231.23, 232.42, crop(CLIP, 930), "검은 정장 투자자 반응(원본 반응 컷)")]},
    {"id": "N7", "kind": "나레", "beat": "지분 경쟁(요구)", "text": "근데 지분 4%에 60만 달러, 회사 가치로 1,500만 달러를 불렀는데",
     "tts": "근데 지분 사 퍼센트에 육십만 달러, 회사 가치로 천오백만 달러를 불렀는데",
     "sub": ["근데 지분 4%에", "60만 달러,", "회사 가치로", "1,500만 달러를", "불렀는데"], "facts": ["f11"],
     "cuts": [(CLIP, 15.30, 16.80, crop(CLIP, 960), "창업자가 무대에서 투자 요청(소리 끔, 샷 15.18~18.49)"),
              (CLIP, 289.95, 292.75, crop(CLIP, 960), "투자자석 쪽 넓은 화면")]},
    {"id": "O9", "kind": "원음", "beat": "지분 경쟁(반응)", "audio": (295.56, 296.56), "en": "That's insane.",
     "sub": ["말도 안 돼!"], "style": "원음반응_크게", "facts": ["f12"],
     "fx": "빨강 번쩍 — 벤치 QMJ 44.4 빨강",
     "cuts": [(CLIP, 295.56, 296.56, crop(CLIP, 900), "대머리 검은 정장 투자자가 두 손을 들며 '말도 안 돼'(말하는 본인, 샷 295.56~296.60)")]},
    {"id": "O10", "kind": "원음", "beat": "지분 경쟁(제안 금액)", "audio": (519.96, 525.40), "en": "So I'll make you an offer. I'll give you the 600,000 for 8%.",
     "sub": ["제안 하나 할게요", "60만 달러에", "지분 8%"], "facts": ["f14"], "cap_at": [519.96, 521.44, 523.50],
     "fx": "초록 번쩍 + 날개 돈다발 — 벤치 QMJ 38.7 제안 금액 줄",
     "cuts": [(CLIP, 519.96, 521.32, crop(CLIP, 886), "파란 재킷 투자자가 제안(말하는 본인)"),
              (CLIP, 521.32, 522.79, crop(CLIP, 960), "회색 재킷 투자자 반응(원본 반응 컷)"),
              (CLIP, 522.79, 524.82, crop(CLIP, 930), "창업자가 듣고 웃음(원본 반응 컷)"),
              (CLIP, 524.82, 525.40, crop(CLIP, 900), "파란 재킷 투자자(말하는 본인 — 526초부터 나오는 제안 띠 전에 끊음)")]},
    {"id": "O11", "kind": "원음", "beat": "결정(성사)", "audio": (582.50, 585.70), "en": "I would love to take your offer. / Done! / All right!",
     "sub": ["제안 받을게요!", "딜!", "좋았어!"], "facts": ["f15"], "cap_at": [582.50, 584.46, 585.28],
     "fx": "빨강 번쩍 — 벤치 QMJ 44.4 결정",
     "cuts": [(CLIP, 582.50, 582.92, crop(CLIP, 900), "파란 재킷 투자자(앞 샷 끝)"),
              (CLIP, 582.92, 584.42, crop(CLIP, 900), "창업자가 웃으며 수락(말하는 본인)"),
              (CLIP, 584.42, 585.70, crop(CLIP, 900), "파란 재킷 투자자가 두 팔을 벌리며 '딜!'(말하는 본인)")]},
    {"id": "N11", "kind": "나레", "beat": "방송 후 결과", "text": "방송 뒤 투자는 결국 없던 일이 됐지만 홀푸드랑 월마트엔 들어갔다고",
     "tts": "방송 뒤 투자는 결국 없던 일이 됐지만 홀푸드랑 월마트엔 들어갔다고", "sub": ["방송 뒤 투자는", "결국 없던 일이 됐지만", "홀푸드랑 월마트엔", "들어갔다고"], "facts": ["f16", "f17"],
     "fx": "초록 번쩍 — 벤치 QMJ 45.7 결과(입점 컷 첫머리)",
     "cuts": [(CLIP, 593.50, 594.80, crop(CLIP, 960), "창업자가 무대를 걸어 나감(샷 593.33~600.90)"),
              (BOX, 0.50, 1.80, crop(BOX, 960), "실사용(Box Peel 언박싱 1080p): 분홍 'POUR OVER SET' 상자(포장 글자 = 제품)"),
              (BOX, 136.00, 137.70, crop(BOX, 960), "실사용: 집에서 컵에 건 필터에 뜨거운 물을 부음(위에서)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/11편_CopperCow/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 11편 Copper Cow Coffee — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "매출 400만 달러", "line2": "컵에 거는 커피?!"}

FW = "asr/fw_words.json(faster-whisper small 로컬, 낱말 시각)"
FACTS = {
    "f1": {"text": "원본 197.38~200.92 'I've never seen anything like it. It's really clever, this packaging.'(" + FW + " · 제미나이 3.5-flash 구간 받아쓰기 span_w1 같은 말, 30초 창 3-flash·3.5-flash 둘 다 같은 말) · 화면 197.50~200.27 파란 재킷 투자자 커피 마심 → 200.27~201.73 금발 투자자. 말한 사람 = 금발 여성 투자자로 추정(f0 210Hz 여성대, 제미나이가 194.0 'What I think is really cool is this'(화면 금발 투자자)와 같은 화자로 묶음) — 이름 화면 글자 없음 → 이름 안 씀", "kind": "방송 원음"},
    "f2": {"text": "원본 55.04~62.36 'Our single, individual pour-overs allow for anyone to make a gourmet coffee without any additional equipment.'(30초 창 2모델 + fw)", "kind": "방송 원음"},
    "f3": {"text": "원본 70.28~74.02 'Gently hang it over your cup, and then tear off the top,'(fw · 30초 창 2모델 · 벤치 자막 같은 말)", "kind": "방송 원음"},
    "f4": {"text": "원본 74.28~81.80 'and then pour hot water over the organic grounds, and immediately watch as your organic coffee drips directly into the cup.'(span_w1 74~89 2모델 + fw)", "kind": "방송 원음"},
    "f5": {"text": "원본 88.12~91.58 'Once brewed, then you get to add your Copper Cow Creamer,'(span_w1 88~100 2모델 + fw · 벤치 자막 'Copper Cow creamer')", "kind": "방송 원음"},
    "f6": {"text": "원본 129.0~139.72 'I gotta tell you … this packaging is absolutely incredible, and I just came back from Ho Chi Minh, and I stood online two hours for one coffee shop.'(fw·3-flash 'Ho Chi Minh' / 3.5-flash 'Whole Foods' — 장소 갈림 → 나레에 장소 안 씀, '두 시간' 은 3모델 같음) · 화면 132~139 같은 투자자(검은 정장·분홍 넥타이)가 컵 들고 말함", "kind": "방송 원음+화면"},
    "f7": {"text": "원본 141.34~144.30 'Are you telling me that I didn't have to wait out there for two hours?'(span_w1 138~150 3.5-flash + fw + 벤치 자막 같은 말)", "kind": "방송 원음"},
    "f8": {"text": "원본 144.60~147.56 'Nope. And you don't need to buy any additional equipment. / This is great.'(3.5-flash·벤치 자막 'don't need to buy', fw 'don't even buy' — 뜻 같음)", "kind": "방송 원음"},
    "f9": {"text": "원본 187.5~194.5 '…manufacturing it, living with my sister, making it out of her garage.' 'When was this?' 'This was four years ago.'(30초 창 2모델 + fw 192.06 'This was four years ago')", "kind": "방송 원음"},
    "f10": {"text": "원본 229.60~233.16 'So total sales to date is 4 million.' '4 million?' '4 million.'(span_w1 224~237 2모델 + fw)", "kind": "방송 원음"},
    "f11": {"text": "원본 11.88~18.22 'I'm here today seeking $600,000 in exchange for 4% of my company.'(span_w1 2모델 + fw) · 화면 띠 114·300·516초 'Seeking $600k for a 4% stake' · 원본 289.80~295.26 'And what was the valuation then?' '15 million.' '15?' 'What you're asking today?' 'Yes.'(fw + 3.5-flash) — 60만/4% = 1,500만 달러(계산 일치)", "kind": "방송 원음+화면 글자"},
    "f12": {"text": "원본 295.52~296.40 'That's insane.'(fw + 3.5-flash span_w1) · 화면 샷 295.56~296.60 대머리 투자자가 두 손을 듦(이름 글자 없음)", "kind": "방송 원음"},
    "f13": {"text": "원본 265.5~272.86 'Last year when your sales were 1.6 million, how much money did you lose?' 'We lost 1.4 million.'(fw + 3.5-flash) · 빠짐: 323.4~325.5 'Very cool, but I'm out' · 425.5~427 'I'm out' · 494.6~496.6 'I'm out' · 547.3~549.8 'for those reasons I'm out'(30초 창 받아쓰기) — 화면 422~424 대머리 투자자·494~496 검은 정장 투자자", "kind": "방송 원음+화면"},
    "f14": {"text": "원본 519.94~525.18 'So I'll make you an offer. I'll give you the 600,000 for 8%.'(span_w1 2모델 + fw) · 화면 띠 526~530 \"Robert's offer: $600k for an 8% stake\"(이름 = 화면 글자로 확인, 자막엔 이름 안 씀)", "kind": "방송 원음+화면 글자"},
    "f15": {"text": "원본 582.50~585.68 'I would love to take your offer.' 'Done!' 'All right!'(fw + 3.5-flash) · 593.78~597.10 창업자 인터뷰 \"I took Robert's offer, even though it cut my valuation in half\"(fw + 3-flash)", "kind": "방송 원음"},
    "f16": {"text": "Copper Cow Coffee 공식 블로그 'Shark Tank Update: One Year Later'(2022-06-03) 창업자 Debbie Wei Mullin: \"While we were excited that Robert made us a deal on the show, we ended up not going through with the deal after airing.\" · 'sold nationwide at Whole Foods Market, plus … Sprouts, Walmart, and H-E-B'", "url": "https://coppercowcoffee.com/blogs/blog-posts/shark-tank-update", "kind": "회사 공식 글"},
    "f17": {"text": "실사용 영상 Pbt3hLQ5Z28(Box Peel 'Copper Cow Coffee Vietnamese Pour Over - Silent Unboxing & Pouring' 1080p, 말 없음) 0~2초 상자 · 136~138초 집에서 물 붓기", "url": "https://www.youtube.com/watch?v=Pbt3hLQ5Z28", "kind": "실사용 영상 화면"},
}
for k, v in FACTS.items():
    v.setdefault("url", "https://www.youtube.com/watch?v=Ij6BNYohK2o")


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
    S["topic"] = ("Copper Cow Coffee(컵에 거는 베트남식 드립 커피 + 연유 크리머) — 샤크탱크 US S12E25, 60만 달러/4%(기업 가치 1,500만) 요청 → "
                  "매출 400만·작년 적자 140만 → 샤크 4명 빠짐 → 로버트 60만/8% 제안 수락 → 방송 뒤 거래 무산(회사 공식 글)")
    S["bench"] = {"id": "MzQdks2-D-I", "channel": "BIG BAG HUSTLE @BIGBAGHUSTLE", "title": "Perfect Coffee Without a Machine", "dur": 38.15,
                  "views": 12789683, "window": [0, 434, 1080, 1052],
                  "note": "벤치는 세로 전체 화면·원음만·낱말 한 개씩 영어 자막(나레 없음). foreignshowshow 판 같은 제품 쇼츠 없음(채널 검색 '커피'·'coffee' 0건) → 원음 순간·0초 훅 = BBH, 틀·효과 = foreignshowshow 6박자. window 는 우리 채널 고정 창"}
    S["form"] = "foreignshowshow 틀 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」"
    S["facts"] = FACTS
    S["dropped"] = [
        "BBH 벤치 'Simply take your pour-over, open it up, and grab your biodegradable filter.'(63.22~69.60) — 길이 때문에 뺌, 나레 N1 로 갈음",
        "BBH 벤치 'There are no preservatives or additives.'(94.32~96.24) — 길이 때문에 뺌",
        "BBH 벤치 끝 'Wow.'(233.42~233.72, 0.3초) — '400만 달러?!' 반응으로 끝냄",
        "케빈·데이먼드 '사회주의' 말다툼(450~500초)·마크 4%+자문 지분 역제안(552~575초) — 길이 때문에 뺌",
        "방송 뒤 시리즈 A 850만 달러(요약 기사만, 1차 출처 못 엶) — 넣지 않음",
        "N6 '4년 전만 해도 자매네 차고에서 직접 만들던 커피인데'(f9)·N9 '작년에만 140만 달러 적자라 샤크들이 줄줄이 빠지는데'(f13) — 페이블 10-19 길이 45초 이하 지시로 뺌",
        "N11·N12(방송 뒤 무산 / 입점) — 페이블 10-19 지시로 한 줄(N11)로 합침"]
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 줄당 ≤12자(rules title.line_chars_max). 숫자 = f10(원음 'total sales to date is 4 million')"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


def win_box(cr, box):
    """소스 좌표 상자 → 완성본 좌표(창 [0,434,1080,1052])."""
    x, y, w, h = cr
    k = WIN[0] / w
    return [round((box[0] - x) * k), round(434 + (box[1] - y) * k), round((box[2] - x) * k), round(434 + (box[3] - y) * k)]


def main():
    shots, total = build()
    mat = {"_note": "샥탬스토리 11편 Copper Cow Coffee 재료 계획 — TTS·렌더 전. 창 1080x1052(채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물). 원음 컷은 src_orig_span 그대로 원본 소리(영어 원음 Ij6BNYohK2o_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Mark Sticks Up For Copper Cow Coffee Entrepreneur",
                      "해상도": "1920x1080 29.97fps (137 + 140 영어 원음, 오디오 트랙 1개)", "길이": 671.9, "받은 구간": "전체",
                      "남의 글자": "로고·방송사 띠 없음. 이름·제안 띠(106~117·300~302·514~520·526~570초 화면 아래) — 쓴 컷은 띠 없는 구간만(519.94~525.60 프레임 0.5초 간격 눈 확인)"},
               TXJ: {"채널": "Copper Cow Coffee(판매사 공식)", "제목": "Copper Cow Coffee -- Portable Pourover Vietnamese Coffee",
                     "해상도": "1920x1080 24fps (137, 영상만)", "길이": 22, "남의 글자": "16.5초부터 로고 — 안 씀(쓴 7.5~8.45 글자 없음)"},
               BOX: {"채널": "Box Peel(실사용 언박싱, 말 없음)", "제목": "Copper Cow Coffee Vietnamese Pour Over - Silent Unboxing & Pouring",
                     "해상도": "1920x1080 30fps (137, 영상만)", "길이": 343, "남의 글자": "없음(포장 글자 = 제품)"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": TITLES, "shots": shots, "cand_dir": str(SRC).replace("\\", "/")}
    cr_n1 = LINES[1]["cuts"][0][3]
    cr_n3 = LINES[3]["cuts"][0][3]
    mat["effects"] = [
        {"line": "O1", "kind": "red_circle", "at": [540, 700], "size": 430, "how": "face", "t": [0.0, 0.80],
         "why": "벤치 QMJ 0초 얼굴 훅 원(반지름 209 고정) — 자리·첫 컷 크롭은 fx_place.fix 가 얼굴 검출로 계산. 길이 0.80초 = 첫 컷 끝(벤치 원 길이 0.53~1.43 안, 원은 컷과 같이 사라짐) — 고개를 들기 전(10fps 얼굴 실측 tools/hook_faces.py: 첫 컷 얼굴로 자리 잡으면 0~0.75초 얼굴 둘레 16점 전부 원 안, 옛 판(2.77초 컷 중앙값 자리·끝까지) 평균 0.76)"},
        {"line": "N1", "kind": "arrow_green_down", "at": [606, 560], "t": [0.0, 0.7], "how": "target",
         "target": win_box(cr_n1, [620, 180, 1040, 740]), "target_what": "유리컵에 건 드립 필터(원본 42.8초 프레임 격자 실측 x620~1040·y180~740)",
         "why": "벤치 QMJ 0.567~1.267 둘째 컷 제품 위 초록 아래 화살표"},
        {"line": "N3", "kind": "arrow_curve_red", "at": [400, 1100], "t": [0.3, 1.6], "how": "target",
         "target": win_box(cr_n3, [756, 259, 972, 713]), "target_what": "필터에서 컵으로 떨어지는 커피 줄기(원본 78.0초 격자 실측 x756~972·y259~713)",
         "why": "벤치 QMJ 20.367 둘째 시연 빨간 곡선 화살표(찌르기)"},
        {"line": "N5", "kind": "dashed_circle", "at": [540, 900], "t": [0.17, 1.8], "how": "target", "target": "person",
         "target_what": "두 시간 줄 섰다는 투자자(검은 정장, 사람 검출)", "why": "벤치 QMJ 9.27~11.53 불편 겪는 사람 빨간 점선 원"},
        {"line": "N5", "kind": "flash", "color": "빨강", "at": [540, 960], "t": [0.9, 1.35], "why": "벤치 QMJ 11.2 불편 빨강 번쩍(점선 원 떠 있는 동안)"},
        {"line": "O8", "kind": "flash", "color": "초록", "at": [540, 960], "t": [0.0, 0.45], "why": "벤치 QMJ 28.1·7.1 장면 넘김 초록 — 매출 숫자 줄 첫 컷"},
        {"line": "O8", "kind": "arrow_pink_up", "at": [533, 1230], "t": [0.75, 2.3], "why": "벤치 QMJ 12.017~13.82 숫자 조각 분홍 위 화살표 — 우리 '400만 달러예요' 조각"},
        {"line": "O9", "kind": "flash", "color": "빨강", "at": [540, 960], "t": [0.0, 0.45], "why": "벤치 QMJ 44.4 빨강(반응)"},
        {"line": "O10", "kind": "flash", "color": "초록", "at": [540, 960], "t": [1.38, 1.83], "why": "벤치 QMJ 38.667 제안 금액 컷 초록 번쩍(돈다발과 같은 프레임) — 우리 '60만 달러에' 조각 컷(521.32)"},
        {"line": "O10", "kind": "money_emoji", "at": [537, 1189], "t": [1.41, 2.71], "why": "벤치 QMJ 38.7~40.0 날개 돈다발"},
        {"line": "O11", "kind": "flash", "color": "빨강", "at": [540, 960], "t": [1.92, 2.37], "why": "벤치 QMJ 44.367 결정 빨강 — 우리 '딜!' 두 팔 컷(584.42)"},
        {"line": "N11", "kind": "flash", "color": "초록", "at": [540, 960], "t": [0.0, 0.45], "why": "벤치 QMJ 45.667 결과 초록 — 우리 방송 후 결과 줄 첫 컷"}]
    mat["sfx_not_drawn"] = []
    doc_update()
    (HERE / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--no-sheet" not in sys.argv:
        (HERE / "plan").mkdir(exist_ok=True)
        sheet(shots, HERE / "plan" / "계획_시트.jpg", " / ".join(TITLES.values()))
    c = check(shots, total)
    print(json.dumps(c, ensure_ascii=False))
    for x in shots:
        print(x["i"], x["line"], x["kind"], x["src"], x["src_orig_span"], x["dur"], x["t_final_est"], x["src_crop"], file=sys.stderr)
    return shots, c


if __name__ == "__main__":
    main()
