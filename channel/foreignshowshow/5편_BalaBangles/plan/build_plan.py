# -*- coding: utf-8 -*-
"""샥탬스토리 5편 Bala Bangles — 계획 한 벌(줄·컷 정의 한 곳) → 대본.json · 재료.json · plan/계획_시트.jpg (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/foreignshowshow/5편_BalaBangles/plan/build_plan.py [--no-sheet]

1편 STORMBAG build_plan.py 꼴 그대로(렌더러 tools/calcopy/shark/render.py 1편꼴 입력). TTS·렌더 전 선검수용.
시각은 말속도 7.1자/초(벤치 나레 실측, 1편과 같은 값) 추정 — TTS 뒤 다시 맞춘다.
원음 구간 경계 = 받아쓰기 2모델(C:/숏템_칼카피/foreignshowshow/5편_BalaBangles/asr/*.json, git 밖) + 원본 컷 경계(scd.txt, scene>0.25).
"""
import json
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parents[1]
SRC_DIR = "C:/숏템_칼카피/foreignshowshow/5편_BalaBangles/src"
FR_DIR = Path("C:/숏템_칼카피/foreignshowshow/5편_BalaBangles/plan_frames")
CPS = 7.1
NL = chr(10)
GAP = 0.08
WIN = (1080, 1052)

SOURCES = {
    "RAD": {"file": "RADCBcHJO_k.mp4", "url": "https://www.youtube.com/watch?v=RADCBcHJO_k", "채널": "Sony Pictures Television",
            "제목": "Shark Tank US | All Five Sharks Fight To Secure A Deal With Bala Bangles", "업로드": "2021-09-16", "해상도": "1920x1080 29.97fps", "길이": 583.6,
            "받은 형식": "137+140(yt-dlp 기본 클라이언트 — web 클라이언트는 '이미지만' 응답이라 못 받음)",
            "남의 글자": "하단 자막 띠(y≈905~1025): 이름 18~24 · Seeking 25~27·247~251 · Kevin's offer 313~318 · Counter offer 441~445 · Lori's offer 476~480 · Maria & Mark's offer 512.5~518 — 그 시각 컷은 h=880(위만). 화면 구석 워터마크 없음(프레임 확인). 끝 564~ 엔드카드(안 씀)"},
}

FULL = (405, 0, 1109, 1080)   # 전높이 1109x1080 (창 1080x1052 비율, ×0.974 — 확대 없음)
LT = (508, 0, 904, 880)       # 하단 자막 띠 피함(위 880만, ×1.195)


def cx(base, x):
    return (x, base[1], base[2], base[3])


LINES = [
    {"id": "O1", "fn": "0초 반응(숫자)", "kind": "orig", "src": "RAD", "span": [207.45, 208.60], "en": "1.2 million?",
     "who": "투자자(남·검정 정장·초록 넥타이) — 이 사람 이름이 적힌 화면 글자 없음 → 불명",
     "caps": ["120만 달러?!"], "facts": ["f1"],
     "shots": [("RAD", 207.45, 1.15, cx(FULL, 210), "의자에 앉아 되묻는 투자자(남·검정 정장·초록 넥타이) — 소리와 같은 원본 초")]},
    {"id": "N1", "fn": "시연(무엇)", "kind": "tts", "text": "손목 발목에 차기만 하면, 운동이 더 힘들어지는 팔찌가 있는데",
     "tts": "손목 발목에 차기만 하면, 운동이 더 힘들어지는 팔찌가 있는데",
     "caps": ["손목 발목에", "차기만 하면", "운동이 더 힘들어지는", "팔찌가 있는데"], "facts": ["f2"],
     "shots": [("RAD", 95.30, 1.80, cx(FULL, 300), "팔을 머리 위로 뻗은 두 사람 손목에 파랑·회색 팔찌(제품사 영상, 방송 안 삽입)"),
               ("RAD", 109.20, 1.70, cx(FULL, 405), "손목에 회색 팔찌 찬 두 사람 → 110.94 전 팔찌 찬 손목 근접(제품사 영상)")]},
    {"id": "N2", "fn": "기존 불편→차이", "kind": "tts", "text": "80년대 에어로빅 때 차던 모래 주머니를, 예쁜 팔찌로 바꾼 거라고",
     "tts": "팔십 년대 에어로빅 때 차던 모래 주머니를, 예쁜 팔찌로 바꾼 거라고",
     "caps": ["80년대 에어로빅 때", "차던 모래 주머니를", "예쁜 팔찌로", "바꾼 거라고"], "facts": ["f3"],
     "shots": [("RAD", 55.00, 1.90, cx(FULL, 500), "80년대 에어로빅 차림(민소매·헤어밴드) 남자가 분홍 팔찌 찬 팔로 근육 자랑"),
               ("RAD", 240.30, 1.85, cx(FULL, 405), "흰 팔찌 제품 근접(제품 위 bala 글자 = 제품 자체)")]},
    {"id": "O2", "fn": "시연(반응)", "kind": "orig", "src": "RAD", "span": [173.95, 177.27],
     "en": "I like the fact that you don't have to hold anything.", "who": "투자자(여·금발·남색 옷, 손목에 분홍 팔찌) — 화면에 말하는 본인. 이름 글자는 476초 'Lori's offer' 띠(같은 사람이 470초 제안)",
     "caps": ["손에 뭘 안 들어도", "되는 게 좋네요"], "cap_at": [173.95, 175.30], "facts": ["f4"],
     "shots": [("RAD", 173.95, 3.32, cx(FULL, 0), "분홍 팔찌 찬 손목을 만지며 말하는 투자자(여·금발) + 옆 투자자(남) — 소리와 같은 원본 초")]},
    {"id": "N3", "fn": "시연(쓰임)", "kind": "tts", "text": "그래서 덤벨 없이도, 요가 동작을 그대로 할 수 있다는데",
     "tts": "그래서 덤벨 없이도, 요가 동작을 그대로 할 수 있다는데",
     "caps": ["그래서 덤벨 없이도", "요가 동작을", "그대로 할 수 있다는데"], "facts": ["f5"],
     "shots": [("RAD", 177.30, 1.35, cx(FULL, 405), "O2 화면에서 그대로 이어지는 두 창업자 — 요가 강사인 창업자(여)가 말하기 시작(소리 끔). 원본 컷 경계 ≈177.2 가 O2 끝(177.27)보다 앞이라 이어 붙여 번쩍임을 없앰"),
               ("RAD", 184.80, 1.70, cx(FULL, 405), "손목·발목 팔찌를 찬 채 한 발 들어 요가 자세 잡는 모델(무대 세움 사진)")]},
    {"id": "N4", "fn": "숫자(매출)", "kind": "tts", "text": "첫 6개월에 26만 달러, 올해는 220만 달러를 찍는다고",
     "tts": "첫 육 개월에 이십육만 달러, 올해는 이백이십만 달러를 찍는다고",
     "caps": ["첫 6개월에", "26만 달러", "올해는 220만 달러를", "찍는다고"], "facts": ["f6"],
     "shots": [("RAD", 215.60, 1.25, cx(FULL, 405), "손목에 흰 팔찌 찬 두 창업자, 남자가 손짓하며 설명"),
               ("RAD", 220.60, 1.20, cx(FULL, 405), "투자자석 와이드(다섯 명이 창업자 쪽을 봄)"),
               ("RAD", 233.80, 1.25, cx(FULL, 300), "의자에 앉아 듣는 투자자(남·남색 정장)")]},
    {"id": "N5", "fn": "요구", "kind": "tts", "text": "40만 달러에 지분 10%를 내걸자",
     "tts": "사십만 달러에 지분 십 퍼센트를 내걸자",
     "caps": ["40만 달러에", "지분 10%를 내걸자"], "facts": ["f7"],
     "shots": [("RAD", 13.00, 1.20, cx(FULL, 405), "무대에 선 두 창업자(남·회색 티 / 여·회색 재킷), 인사하며 말하는 중"),
               ("RAD", 28.10, 1.10, cx(FULL, 700), "무대 와이드 — 커튼 앞에 선 두 창업자(피치 시작)")]},
    {"id": "O4", "fn": "제안 1(빚)", "kind": "orig", "src": "RAD", "span": [300.40, 304.35],
     "en": "I'll give you the $400,000 as debt for three years, okay?", "who": "투자자(남·민머리·검정 정장·빨간 행커치프) — 313~318초 화면 띠 'Kevin's offer'가 이 사람 말하는 화면 위",
     "caps": ["40만 달러를", "3년짜리 빚으로 드리죠"], "cap_at": [300.45, 302.20], "facts": ["f8"],
     "shots": [("RAD", 300.40, 3.95, cx(FULL, 405), "듣는 두 창업자(300.4~302.5) → 302.50 원본 컷 말하는 투자자(남·민머리) — 소리와 같은 원본 초")]},
    {"id": "O5", "fn": "제안 2(30%)", "kind": "orig", "src": "RAD", "span": [377.92, 381.95],
     "en": "I would take 30%.", "who": "투자자(여·갈색 정장) — 이름은 화면 띠 'Maria & Mark's offer'(512.5~518)·말 'Maria, you threw out an offer'(403~)",
     "caps": ["저는 30%를 원해요"], "facts": ["f9"],
     "shots": [("RAD", 377.92, 4.03, cx(FULL, 300), "투자자석 옆모습(남색 정장 남·갈색 정장 여·민머리 남) → 381.11 원본 컷 창업자(남) 근접 — 소리와 같은 원본 초")]},
    {"id": "N7", "fn": "지분 경쟁", "kind": "tts", "text": "다른 투자자들까지, 같은 조건으로 따라붙더니",
     "tts": "다른 투자자들까지, 같은 조건으로 따라붙더니",
     "caps": ["다른 투자자들까지", "같은 조건으로", "따라붙더니"], "facts": ["f10"],
     "shots": [("RAD", 386.75, 2.25, cx(FULL, 405), "손짓하며 말하는 투자자(남·검정 정장·초록 넥타이) → 투자자(여·금발)")]},
    {"id": "O7", "fn": "지분 경쟁(셋째)", "kind": "orig", "src": "RAD", "span": [466.38, 468.10],
     "en": "I'm gonna make my own offer.", "who": "투자자(여·금발) — 화면에 말하는 본인(466.37~467.57) → 467.57 원본 컷 창업자(남) 근접. 476~480초 화면 띠 'Lori's offer'",
     "caps": ["저는 따로", "제안할게요"], "cap_at": [466.38, 467.00], "facts": ["f11"],
     "shots": [("RAD", 466.38, 1.72, cx(FULL, 405), "말하는 투자자(여·금발) → 467.57 원본 컷 창업자(남) 근접 — 소리와 같은 원본 초")]},
    {"id": "N8", "fn": "지분 경쟁(숫자)", "kind": "tts", "text": "로리는 50만 달러에 18%를 불렀는데",
     "tts": "로리는 오십만 달러에 십팔 퍼센트를 불렀는데",
     "caps": ["로리는", "50만 달러에", "18%를 불렀는데"], "facts": ["f11"],
     "shots": [("RAD", 476.20, 1.70, cx(LT, 508), "제안을 듣고 귓속말하는 두 창업자(하단 'Lori's offer' 띠는 위 880만 잘라 뺌)"),
               ("RAD", 481.90, 1.00, cx(FULL, 300), "나란히 앉은 투자자(남·남색 정장)와 투자자(여·갈색 정장)")]},
    {"id": "N9", "fn": "결정타", "kind": "tts", "text": "결국 마크가 마리아와 손잡고, 90만 달러에 30%를 주겠다고 하자",
     "tts": "결국 마크가 마리아와 손잡고, 구십만 달러에 삼십 퍼센트를 주겠다고 하자",
     "caps": ["결국 마크가", "마리아와 손잡고", "90만 달러에 30%를", "주겠다고 하자"], "facts": ["f12"],
     "shots": [("RAD", 500.60, 2.60, cx(FULL, 150), "말하는 투자자(남·남색 정장) → 501.67 원본 컷 투자자석 와이드"),
               ("RAD", 507.30, 2.05, cx(FULL, 380), "나란히 앉은 투자자(남·남색 정장)와 투자자(여·갈색 정장), 남자가 손짓하며 제안")]},
    {"id": "O8", "fn": "성사", "kind": "orig", "src": "RAD", "span": [518.60, 520.60],
     "en": "You've got a deal. / Yes!", "who": "창업자(여) — 화면에 말하는 본인(두 창업자 2인 화면) → 'Yes!'는 다른 목소리(누구인지 불명)",
     "caps": ["계약할게요!", "좋아요!"], "cap_at": [518.60, 519.85], "facts": ["f12"],
     "shots": [("RAD", 518.60, 2.00, cx(FULL, 405), "두 창업자 — 여자가 '계약'을 말하고 남자가 팔 벌려 환호 → 519.92 원본 컷 투자자석 와이드(일어서는 투자자) — 소리와 같은 원본 초")]},
    {"id": "O9", "fn": "경쟁 정리", "kind": "orig", "src": "RAD", "span": [533.60, 539.30],
     "en": "Well, I must say, it's the first time in Shark Tank history I've actually seen Sharks fight to be a partner.",
     "who": "투자자(남) — 투자자석 와이드, 입 모양으로 누구인지는 불명",
     "caps": ["샤크탱크 역사상", "투자자끼리 서로 하겠다고", "싸우는 건 처음 봐요"], "cap_at": [533.60, 536.00, 537.60], "facts": ["f13"],
     "shots": [("RAD", 533.60, 5.70, cx(FULL, 405), "투자자석 와이드(다섯 명) → 538.40 원본 컷 투자자(여·갈색 정장) — 소리와 같은 원본 초")]},
    {"id": "N10", "fn": "방송 후 결과", "kind": "tts", "text": "방송이 나간 그해, 매출이 200만 달러에서 2,000만 달러로 뛰었다고",
     "tts": "방송이 나간 그해, 매출이 이백만 달러에서 이천만 달러로 뛰었다고",
     "caps": ["방송이 나간 그해", "매출이 200만 달러에서", "2,000만 달러로", "뛰었다고"], "facts": ["f14"],
     "shots": [("RAD", 547.30, 2.10, cx(FULL, 405), "무대 뒤에서 두 팔 들고 기뻐하는 두 창업자"),
               ("RAD", 346.00, 1.80, cx(FULL, 405), "회색 팔찌 세트·bala 상자 제품 근접(끝 컷 ≥1.5초)")]},
]

A = "https://www.youtube.com/watch?v=RADCBcHJO_k"
FACTS = {
    "f1": ("원음 207.45~208.60 '1.2 million?' — 클립 단독 받아쓰기 2모델(clip_r9 '1.2 million.'·'One point two million', clip_r4: 3-flash 'One point two million.' · flash-latest '1.2 million.', 둘 다 1명). 207.25 시작은 앞 창업자 말 꼬리 'And' 가 들려(clip_r3) 207.45 로 당김. 앞 창업자 말 '…this year so far, we're at 1.2 million'(204.0~207.24)을 되물음. 207.04~208.78 원본 컷 = 이 투자자 근접", A + "&t=204"),
    "f2": ("창업자 94.7~101.2 'Adding our weights to your workout will increase heart rate, burn fat, and build muscle' · 149.6~151.3 'These are going to make it incrementally harder' · 142~145 'our first product is the 1-lb wrist and ankle weight'(full_60s 2모델)", A + "&t=94"),
    "f3": ("창업자 26.0~39.8 'you remember the 80s, aerobics were all the rage … from leg warmers to … wrist and ankle weights' · 78.1~87.3 'the sweaty, loose, sand-filled wrist and ankle weight' · 89.4~94.5 'Introducing Bala Bangles, the world's first stylish, wearable weights'(창업자 주장 → '~라고' 전언)", A + "&t=26"),
    "f4": ("원음 173.95~177.27 'I like the fact that you don't have to hold anything.'(clip_r4 2모델 일치·1명·잘림 없음). 173.75 시작은 앞말 꼬리 '~ce' 가 들리고(clip_r1), 177.10 끝은 'any~' 잘림(clip_r2) → 이 구간으로 확정. 173.71~177.28 원본 컷 = 말하는 투자자(여·금발) 2인 화면", A + "&t=172"),
    "f5": ("창업자(여) 177.4~190.4 'that's how it was designed … I'm a certified yoga instructor … it's hands-free so I can do yoga, all of my poses without having to pick up dumbbells'(full_60s 2모델)", A + "&t=177"),
    "f6": ("창업자(여) 197.6~211.1 'last year, which were our first 6 months in business, we did 260,000 … this year so far, we're at 1.2 million … We'll end the year with 2.2 million'(full_60s 2모델 일치) — '찍는다고'는 창업자 예상의 전언", A + "&t=197"),
    "f7": ("창업자 17.7~25.6 'we're seeking $400,000 in exchange for 10% equity'(2모델) · 화면 띠 'Seeking $400k for a 10% stake'(25~27·247~251) · 191.4~195.2 투자자 '$400,000 for 10% of the company, correct?'", A + "&t=17"),
    "f8": ("원음 300.40~304.35 'I'll give you the $400,000 as debt for three years, okay?'(clip_r2 2모델 일치·1명, 앞 300.0~300.4 −50dB 쉼) · 305~311 '7.5% interest … 5% equity' · 화면 띠 'Kevin's offer: $400k as a loan at 7.5% interest for a 5% stake'(313~318, 이 투자자 화면 위)", A + "&t=300"),
    "f9": ("원음 377.92~381.95 'I would take 30%.'(clip_r9 2모델 일치·1명, 뒤 381.1~381.95 말 없음 — 381.11 원본 컷 창업자(남) 근접까지 넣어 장면 경계 −0.2초) · 같은 투자자(여·갈색 정장) 349~362 'I'll give you 200,000 if you can get another 200 from another shark … But 10% is not enough for me'", A + "&t=349"),
    "f10": ("382.5~395 투자자들(받아쓰기 3명) 'I would match that. I would jump in there with her' · 'I would match that as well' · 'Maria, I will do it with you. $200,000 from me, $200,000 for you, for 30%'(clip_r7 2모델) · 403~410 'You now have two sharks fighting to be your partner' · Sony 클립 제목 'All Five Sharks Fight To Secure A Deal'", A + "&t=382"),
    "f11": ("원음 466.38~468.10 'I'm gonna make my own offer.'(clip_r6 2모델 일치·1명) · 469.5~475 'So, my offer is 500,000, 18%.'(clip_r7 2모델) · 화면 띠 'Lori's offer: $500k for an 18% stake'(476~480)", A + "&t=463"),
    "f12": ("화면 띠 'Counter offer: $900k for a 30% stake, a $3M valuation'(441~445) · 505.2~513.1 'offer you the $900,000 for the 30%, just what you asked for'(full_60s 2모델) · 화면 띠 \"Maria & Mark's offer: $900k for a 30% stake\"(512.5~518) · 원음 518.60~520.60 'You've got a deal.' / 'Yes!'(clip_r2 2모델, 2명) · 552~554 창업자 'Having Maria and Mark is a dream come true' · CNBC 2020-03-01 기사 제목 'Mark Cuban and Maria Sharapova invest in bangle weights'", A + "&t=505"),
    "f13": ("원음 533.60~539.30 'Well, I must say, it's the first time in Shark Tank history (that) I've actually seen sharks fight to be a partner.'(clip_r5 2모델 — 끝까지 들림) · 535.3~537.3 다른 투자자(여) 'I love that' 겹침(2명). 539.05 끝은 'part~' 잘림(clip_r4), 539.6 끝은 다음 말 'What?/Well,' 섞임(clip_r3)", A + "&t=533"),
    "f14": ("Glossy 2021-07-20(Sara Spruch-Feiner) 본문 'In 2020, the brand grew its earnings from $2 million to $20 million.' · 방송 시기 = CNBC 기사 2020-03-01 · 보조: Forbes 2020-11-30 지면(PressReader — 403 으로 본문 못 엶, 검색 요약만) '2020년 50만 개, 매출 1,900만 달러 예상(전년 200만)' — 루퍼(2차) 숫자는 안 씀",
            "https://www.glossy.co/fashion/how-bala-became-the-it-fitness-accessory-of-the-pandemic/"),
}


def nchar(s):
    return len("".join(ch for ch in s if not ch.isspace() and ch not in ",.?!~"))


def build():
    t = 0.0
    out_lines, shots = [], []
    for L in LINES:
        dur = round(L["span"][1] - L["span"][0], 2) if L["kind"] == "orig" else round(nchar(L["tts"]) / CPS, 2)
        L2 = {kk: vv for kk, vv in L.items() if kk != "shots"}
        L2["est_sec"] = dur
        L2["t_final"] = [round(t, 2), round(t + dur, 2)]
        out_lines.append(L2)
        st = t
        for (src, ss, d, crop, see) in L["shots"]:
            shots.append({"i": len(shots), "line": L["id"], "src": SOURCES[src]["file"], "url": SOURCES[src]["url"], "ss": ss, "dur": d,
                          "src_span": [ss, round(ss + d, 2)], "t_final": [round(st, 2), round(st + d, 2)], "src_crop": list(crop),
                          "res": SOURCES[src]["해상도"].split()[0], "scale": round(WIN[0] / crop[2], 3), "ours": see,
                          "mute": L["kind"] == "tts",
                          **({"audio_src": SOURCES[L["src"]]["file"], "audio_span": L["span"]} if L["kind"] == "orig" else {})})
            st += d
        t += dur + GAP
    return out_lines, shots, round(t - GAP, 2)


def frames(shots):
    FR_DIR.mkdir(parents=True, exist_ok=True)
    for s in shots:
        x, y, w, h = s["src_crop"]
        s["_fr"] = []
        for j, f in enumerate((0.06, 0.5, 0.94)):
            tt = s["ss"] + s["dur"] * f
            out = FR_DIR / f"s{s['i']:02d}_{j}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tt:.3f}", "-i", f"{SRC_DIR}/{s['src']}", "-frames:v", "1",
                            "-vf", f"crop={w}:{h}:{x}:{y},scale=200:195", str(out)], check=True)
            s["_fr"].append(str(out))
            if j == 1:
                s["Y"] = _mean_y(out)


def _mean_y(p):
    from PIL import Image
    im = Image.open(p).convert("L")
    px = list(im.getdata())
    return round(sum(px) / len(px))


def sheet(lines, shots, out):
    from PIL import Image, ImageDraw, ImageFont
    F = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 15)
    FB = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 16)
    byid = {L["id"]: L for L in lines}
    cols, cw, ch = 2, 930, 300
    rows = (len(shots) + cols - 1) // cols
    im = Image.new("RGB", (cols * cw, rows * ch + 40), "white")
    d = ImageDraw.Draw(im)
    d.text((10, 8), "샥탬스토리 5편 Bala Bangles 계획 시트 — 컷마다 처음·가운데·끝 프레임(창 1080x1052 비율 크롭) · 원음=노랑 · 나레=파랑", fill="black", font=FB)
    for s in shots:
        r, c = divmod(s["i"], cols)
        x0, y0 = c * cw + 8, r * ch + 40
        L = byid[s["line"]]
        col = (255, 236, 150) if L["kind"] == "orig" else (200, 225, 255)
        d.rectangle([x0, y0, x0 + cw - 16, y0 + ch - 8], fill=col)
        for j, p in enumerate(s["_fr"]):
            im.paste(Image.open(p), (x0 + 4 + j * 204, y0 + 4))
        tx = x0 + 620
        d.text((tx, y0 + 4), f"#{s['i']} {s['line']} {L['fn']}", fill="black", font=FB)
        d.text((tx, y0 + 26), f"완성 {s['t_final'][0]:.2f}~{s['t_final'][1]:.2f}s ({s['dur']:.2f}s)", fill="black", font=F)
        d.text((tx, y0 + 46), f"{s['src'][:11]} {s['ss']:.2f}~{s['ss'] + s['dur']:.2f}", fill="black", font=F)
        d.text((tx, y0 + 66), f"크롭 {s['src_crop']} ×{s['scale']} Y{s.get('Y')}", fill="black", font=F)
        body = (f"원음: {L['en']}" if L["kind"] == "orig" else f"나레: {L['text']}")
        cap = " / ".join(L["caps"])
        yy = y0 + 92
        for seg in _wrap(body, 17) + _wrap("자막: " + cap, 17):
            if yy > y0 + ch - 26:
                break
            d.text((tx, yy), seg, fill="black", font=F)
            yy += 19
        y_text = y0 + 205
        for seg in _wrap("화면: " + s["ours"], 38)[:3]:
            d.text((x0 + 6, y_text), seg, fill=(60, 60, 60), font=F)
            y_text += 19
    im.save(out, quality=88)


def _wrap(s, n):
    return [s[i:i + n] for i in range(0, len(s), n)] or [""]


SCD = Path("C:/숏템_칼카피/foreignshowshow/5편_BalaBangles/scd.txt")   # 원본 컷 경계(ffmpeg scene>0.25, 240p 사본)


def real_pieces(shots):
    """완성본에 보일 실제 컷 길이 — 우리 컷 + 그 안의 원본 편집 경계(scd)로 쪼갬. 0.3초 미만 조각은 따로 셈(번쩍임)."""
    cuts = [float(x) for x in SCD.read_text().split()] if SCD.exists() else []
    out = []
    for s in shots:
        a, b = s["src_span"]
        inner = [c for c in cuts if a + 0.05 < c < b - 0.05]
        edges = [a] + inner + [b]
        out += [round(edges[k + 1] - edges[k], 2) for k in range(len(edges) - 1)]
    return out


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return round((xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2), 2)


def same_src_close(shots):
    """B13 — 같은 소스 원본 구간이 겹치거나 3초 안에서 뒤로 되돌아감(1편과 같은 판정)."""
    bad = []
    for a in shots:
        for b in shots:
            if b["i"] <= a["i"] or a["src"] != b["src"]:
                continue
            a0, a1 = a["src_span"]
            b0, b1 = b["src_span"]
            if (b0 < a1 - 0.01 and a0 < b1 - 0.01) or (b0 < a0 and a0 - b1 < 3):
                bad.append([a["i"], b["i"], [a0, a1], [b0, b1]])
    return bad


def within3_any(shots):
    """더 엄한 판정(검수 B13 글 그대로) — 순서 상관없이 같은 소스 두 컷 사이 간격 < 3초."""
    bad = []
    for a in shots:
        for b in shots:
            if b["i"] <= a["i"] or a["src"] != b["src"]:
                continue
            a0, a1 = a["src_span"]
            b0, b1 = b["src_span"]
            gap = max(b0 - a1, a0 - b1)
            if gap < 3:
                bad.append([a["i"], b["i"], round(gap, 2)])
    return bad


BENCH_NARR = ["여기 물에 넣어두면 3분 내로 15L 물을 빨아들이는 봉투가 있는데", "홍수가 나기 전에 쌓아두는 모래주머니를 이걸로 대체할 수 있다고",
              "무겁고 옮기기 힘들었던 모래주머니와 달리", "홍수 자리에 놓기만 하면 15kg짜리 방수벽을 만들 수 있고",
              "햇빛에 말려두면 2, 3주 내로 바짝 건조돼서 세 번은 더 쓸 수 있다고", "마케팅만 잘하면 돈 벌 자신이 있다는데",
              "같은 조건으로 네 명의 투자자가 붙게 되고", "방송 후 재고가 모두 다 나갔고 정부 인증까지 받게 되자 지분 거래를 취소했다고"]


def check_copy(lines):
    def toks(s):
        return [w.strip(",.?!~") for w in s.split() if w.strip(",.?!~")]
    grams = set()
    for b in BENCH_NARR:
        t = toks(b)
        grams |= {tuple(t[i:i + 3]) for i in range(len(t) - 2)}
    hits = []
    for L in lines:
        if L["kind"] != "tts":
            continue
        t = toks(L["text"])
        hits += [(L["id"], " ".join(g)) for g in (tuple(t[i:i + 3]) for i in range(len(t) - 2)) if g in grams]
    return {"copy3": hits, "max_cap_chars": max(len(c) for L in lines for c in L["caps"]),
            "max_cap": max((c for L in lines for c in L["caps"]), key=len)}


def main():
    lines, shots, total = build()
    if "--no-sheet" not in sys.argv:
        frames(shots)
        sheet(lines, shots, D / "plan" / "계획_시트.jpg")
    for s in shots:
        s.pop("_fr", None)
    bench = {"id": "QMJtjJz4M6w", "channel": "해외쇼츠 @foreignshowshow", "title": "홍수 막아주는 모래 주머니?!", "dur": 50.467, "views": 12470000,
             "lufs": -7.8, "tp": 1.0, "cut_median": 1.27, "first_cut": 0.57, "window": [0, 434, 1080, 1052], "title_bands": [[211, 304], [318, 407]]}
    doc = {
        "topic": "샤크탱크 Bala Bangles — 차기만 하면 되는 손목·발목 웨이트 팔찌, 투자자들이 서로 하겠다고 싸운 끝에 마크·마리아가 90만 달러/30% (벤치 그대로 칼카피, 방송 원음 위주)",
        "voice": {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "engine": "typecast", "speed": 1.1, "why": "채널 목소리(샥탬스토리_시작.md §1 — 6편 전부 같은 목소리)"},
        "brand": "샥탬스토리", "style": "현장썰(한국어 나레 + 영어 원음 번역 자막 + 제품)",
        "bench": bench,
        "render": {"gap": 0.0, "why": "원음 컷 끝이 원본 장면 경계에 붙어 있어(O2 177.27/경계 177.28) 줄 사이 0.08초 늘임이 경계를 넘김 → 0"},
        "titles": {"hook": "투자자 5명이 전부\n달려든 운동 팔찌?!", "line1": "투자자 5명이 전부", "line2": "달려든 운동 팔찌?!",
                   "rule": "벤치 그대로(사장님 10-18 ③) — 1줄 노랑 [211,304] / 2줄 흰 [318,407], 끝 '?!'. 벤치에 로고 없음 → 로고 넣지 않음(1편 페이블 판정 따름). 근거: Sony 클립 제목 'All Five Sharks Fight To Secure A Deal'"},
        "facts": {k: {"text": v[0], "url": v[1]} for k, v in FACTS.items()},
        "final": {"lines": lines, "est_total_sec": total, "cps_target": CPS,
                  "orig_audio": [{"id": L["id"], "src": SOURCES[L["src"]]["file"], "span": L["span"], "en": L["en"], "ko_caps": L["caps"], "who": L["who"]}
                                 for L in lines if L["kind"] == "orig"]},
        "effects_record": [
            {"at": "O1", "fx": "빨간 원(투자자 얼굴 — 벤치와 같은 0초)", "bench": "0.0~0.6초"},
            {"at": "N2 둘째 컷(흰 팔찌 근접)", "fx": "빨간 점선 원(제품)", "bench": "9.1~11.9초"},
            {"at": "O2", "fx": "분홍 화살표(투자자 손목 분홍 팔찌)", "bench": "11.9~14.2초"},
            {"at": "N9", "fx": "날개 돈다발 이모지(90만 달러)", "bench": "38.6~41.1초"},
            {"at": "자막", "fx": "흰 글자+검정 테두리, 핵심어 형광(민트·초록·빨강·분홍)", "bench": "전 구간"}],
        "notes": ["TTS·렌더 전. 효과·제목 띠는 기록만(좌표는 페이블 OK 뒤 재료 effects 에).",
                  "벤치 나레 연속 3어절 일치 — check_copy() 로 잰다(final.check.copy3).",
                  "★지시문의 '마크 큐반 단독 딜'은 원본과 다름: 화면 띠 \"Maria & Mark's offer: $900k for a 30% stake\" + 창업자 'Having Maria and Mark' + CNBC 2020-03-01 → 마크·마리아 공동. 대본은 공동으로 씀.",
                  "후일담: 루퍼(2차) 대신 Glossy 2021 기사 본문(1차 취재) — 2020년 200만→2,000만 달러. 포브스 지면은 PressReader 403 으로 본문 못 열어 보조로만."],
    }
    doc["final"]["check"] = check_copy(lines)
    (D / "대본.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    mat = {"_note": "샥탬스토리 5편 재료 계획 — TTS·렌더 전. 창 1080x1052(벤치 뜯기 layout). 시각은 말속도 7.1자/초 추정 — TTS 뒤 다시 맞춘다. 원음 줄은 audio_span 을 원본에서 그대로(쉼 자르기 없음).",
           "cand_dir": SRC_DIR, "window": list(WIN), "sources": SOURCES, "shots": shots,
           "effects": [
               {"line": "O1", "kind": "red_circle", "at": [610, 684], "size": 330, "stroke": 8, "t": [0.0, 1.25],
                "why": "벤치 0초 빨간 원(투자자 얼굴) — 207.9초 크롭 x=210 프레임에서 얼굴 중심(창 610,250 → 완성 610,684)"},
               {"line": "N9", "kind": "emoji", "emoji": "💸", "at": [540, 640], "size": 170, "t": [2.3, 4.0],
                "why": "벤치 38.6~41.1초 날개 돈다발 — N9 둘째 컷(마크 x≈146·마리아 x≈936) 동안만, 두 얼굴 사이 배경 위(B5). 1차 렌더에서 첫 컷(마크 가운데) 얼굴을 가려 시각 옮김"}],
           "check": {"cut_count": len(shots), "cut_median_plan": _median([s["dur"] for s in shots]), "first_cut": shots[0]["dur"],
                     "last_cut": shots[-1]["dur"], "max_scale": max(s["scale"] for s in shots),
                     "est_total_sec": total, "bench_total": 50.467, "same_src_close_B13": same_src_close(shots), "gap_lt3_any_order": within3_any(shots),
                     "Y_min": min((s.get("Y") or 999) for s in shots),
                     "real_pieces": real_pieces(shots), "real_cut_median": _median(real_pieces(shots)),
                     "real_slivers_lt0.3": [x for x in real_pieces(shots) if x < 0.3]}}
    (D / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(mat["check"], ensure_ascii=False), json.dumps(doc["final"]["check"], ensure_ascii=False))
    write_docs(doc, mat)


def write_docs(doc, mat):
    """근거.md · plan/계획.md — 대본.json·재료.json 과 같은 값에서 쓴다(손으로 따로 적지 않음)."""
    F = doc["final"]
    L = F["lines"]
    g = ["# 샥탬스토리 5편 Bala Bangles — 근거 (TTS·렌더 전 선검수, 관제 097)", "",
         "벤치: 해외쇼츠 QMJtjJz4M6w 「홍수 막아주는 모래 주머니?!」(50.5초) 꼴 그대로. 소스: Sony Pictures Television `RADCBcHJO_k` 「Shark Tank US | All Five Sharks Fight To Secure A Deal With Bala Bangles」(2021-09-16, 1920x1080, 583.6초) 한 편만.",
         "받아쓰기: 무료 제미나이 키 풀(받아쓰기만, 장면 판독은 클로드 눈). 전체 60초 묶음 2모델 `asr/full_60s.json` + 원음 구간 클립 단독 2모델 `asr/clip_r1~r10.json` (git 밖 `C:/숏템_칼카피/foreignshowshow/5편_BalaBangles/`).",
         "사람 이름: 화면 띠 글자로만 — Kevin(313~318)·Lori(476~480)·Maria & Mark(512.5~518)·창업자 Max Kislevitz & Natalie Holloway(18~24). 나머지 투자자는 '불명'.", "",
         "## 줄별", "", "| 줄 | 종류 | 글(자막) | 근거 |", "|---|---|---|---|"]
    for x in L:
        body = x.get("text") if x["kind"] == "tts" else f"원음 {x['span'][0]}~{x['span'][1]} “{x['en']}” → {' / '.join(x['caps'])}"
        g.append(f"| {x['id']} | {'나레' if x['kind'] == 'tts' else '원음'} | {body} | {', '.join(x['facts'])} |")
    g += ["", "## 근거", "", "| # | 내용 | 출처 |", "|---|---|---|"]
    g += [f"| {k} | {v['text']} | {v['url']} |" for k, v in doc["facts"].items()]
    g += ["", "## 원음 줄 — 말하는 사람·받아쓰기", "", "| 줄 | 구간 | 영어 | 누구(화면) |", "|---|---|---|---|"]
    g += [f"| {o['id']} | {o['span'][0]}~{o['span'][1]} | {o['en']} | {o['who']} |" for o in F["orig_audio"]]
    g += ["", "## 다룬 결정", ""] + [f"- {n}" for n in doc["notes"]]
    (D / "근거.md").write_text(NL.join(g) + NL, encoding="utf-8")
    c = mat["check"]
    m = ["# 계획 — 샥탬스토리 5편 Bala Bangles (TTS·렌더 전)", "",
         f"- 꼴: 나레(지훈 speed 1.1)↔영어 원음(번역 자막) 교대, 렌더러 `tools/calcopy/shark/render.py`, 프리셋 `preset/샤크탱크_검정띠2줄`",
         f"- 제목: {doc['titles']['line1']} / {doc['titles']['line2']} (1줄 노랑·2줄 흰, 벤치 그대로·로고 없음)",
         "- 접촉 시트: `plan/계획_시트.jpg` (컷마다 처음·가운데·끝, 창 1080x1052 비율 크롭)",
         f"- 길이 추정 {F['est_total_sec']}초(7.1자/초) · render --plan 8.4자/초 추정은 work/plan/컷표.md · 벤치 50.47초",
         f"- 컷 {c['cut_count']}개 · 실제 컷(원본 편집 경계 포함) 중앙 {c['real_cut_median']}초(벤치 1.27) · 첫 컷 {c['first_cut']} · 끝 컷 {c['last_cut']} · 확대 최대 ×{c['max_scale']}",
         f"- B13 같은 소스 3초 안 재사용 {c['same_src_close_B13']} / 순서 무관 3초 안 {c['gap_lt3_any_order']} · 번쩍 조각(<0.3초) {c['real_slivers_lt0.3']} · 프레임 평균 Y 최저 {c['Y_min']}",
         f"- 벤치 나레 3어절 겹침 {F['check']['copy3']} · 자막 조각 최대 {F['check']['max_cap_chars']}자", "",
         "## 줄 ↔ 컷", "", "| 줄 | 글 | 컷(원본 초·크롭) | 화면에 보이는 것 |", "|---|---|---|---|"]
    byl = {}
    for s_ in mat["shots"]:
        byl.setdefault(s_["line"], []).append(s_)
    for x in L:
        for k, s_ in enumerate(byl[x["id"]]):
            txt = (x.get("text") or x.get("en")) if k == 0 else "〃"
            m.append(f"| {x['id'] if k == 0 else ''} | {txt} | {s_['ss']}~{s_['src_span'][1]} {s_['src_crop']} ×{s_['scale']} Y{s_.get('Y')} | {s_['ours']} |")
    m += ["", "## 효과(벤치 그대로)", ""]
    m += [f"- {e['at']}: {e['fx']} (벤치 {e['bench']})" for e in doc["effects_record"]]
    m += [f"- 좌표 적은 것(렌더러가 그림): {e['line']} {e['kind']} at {e['at']} size {e['size']} — {e['why']}" for e in mat.get("effects", [])]
    m += ["- 빨간 점선 원·분홍 화살표 = 렌더러(narr_video.overlay_png)에 없는 꼴 → 엔진 요청(못 그림)."]
    (D / "plan" / "계획.md").write_text(NL.join(m) + NL, encoding="utf-8")


if __name__ == "__main__":
    main()
