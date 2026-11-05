# -*- coding: utf-8 -*-
"""샥탬스토리 1편 STORMBAG — 계획 한 벌(줄·컷 정의 한 곳) → 대본.json · 재료.json · plan/계획_시트.jpg (plan/계획.md 는 이 결과로 손으로 씀) (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/foreignshowshow/1편_STORMBAG/plan/build_plan.py [--no-sheet]

TTS·렌더 전 선검수용. 시각은 말속도 7.1자/초(벤치 나레 실측) 추정 — TTS 뒤 받아쓰기로 다시 맞춘다.
원음 구간은 받아쓰기 2모델로 경계 확인(asr/orig_spans_r1~r3.json, git 밖).
"""
import json
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parents[1]
SRC_DIR = "C:/숏템_칼카피/foreignshowshow/src_stormbag"
FR_DIR = Path("C:/숏템_칼카피/foreignshowshow/1편_STORMBAG/plan_frames")
CPS = 7.1          # 벤치 나레 실측(받아쓰기 시각, 194자/27.2초)
GAP = 0.08         # 줄 사이
WIN = (1080, 1052)  # 벤치 창(뜯기 layout [0,434,1080,1052])

SOURCES = {
    "8UW": {"file": "8UW-es-eTl0.mp4", "url": "https://www.youtube.com/watch?v=8UW-es-eTl0", "채널": "Sony Pictures Television",
            "제목": "Shark Tank US | Stormbag's Entrepreneur Gets Emotional In The Tank", "업로드": "2025-04-21", "해상도": "1920x1080 29.97fps", "길이": 642,
            "남의 글자": "하단 자막 띠(Seeking $200k… / 이름 / 제안 조건, y≈900~965) 85.8~86.4·310~312·416~434·468~470·554~558초 — 그 컷은 h=880으로 위만 씀"},
    "3s0": {"file": "3s0CwrcqWCU.mp4", "url": "https://www.youtube.com/watch?v=3s0CwrcqWCU", "채널": "Swiss Link(제품 판매사)",
            "제목": "StormBag Overview: The Sandless Sandbag as Seen on Shark Tank", "업로드": "2024-09-03", "해상도": "1920x1080 24fps", "길이": 177,
            "남의 글자": "영어 자막 burn-in(y≈990~1030) — 모든 컷 h=960으로 위만 씀"},
}

FULL = (405, 0, 1109, 1080)        # 가운데 전높이
LT = (508, 0, 904, 880)            # 하단 자막 띠(y≈900~965) 피함(8UW)
TV = (508, 90, 904, 880)           # 스튜디오 화면 속 타임랩스 — 위아래 베젤 뺌
SUB3 = (468, 0, 985, 960)          # burn-in 자막 피함(3s0)


def crop_x(base, x):
    return (x, base[1], base[2], base[3])


# 줄: id, kind(tts|orig), text(화면 자막), tts(읽는 글), caps(자막 조각 ≤13자), facts, (orig: src, span, en, who)
# 컷: (src, ss, dur, crop, 화면에 보이는 것)
LINES = [
    {"id": "O1", "fn": "0초 결말 반응", "kind": "orig", "src": "8UW", "span": [67.25, 67.75], "en": "What?", "who": "투자자(남·남색 셔츠) — 이름 불명(화면 글자 없음)",
     "caps": ["뭐라고?!"], "facts": ["f1"],
     "shots": [("8UW", 67.25, 0.50, crop_x(FULL, 640), "의자에 앉은 투자자(남·남색 셔츠), 놀란 얼굴")]},
    {"id": "N1", "fn": "시연", "kind": "tts", "text": "이 자루를 물에 담가 두면", "tts": "이 자루를 물에 담가 두면",
     "caps": ["이 자루를", "물에 담가 두면"], "facts": ["f2"],
     "shots": [("3s0", 133.00, 1.41, crop_x(SUB3, 468), "외바퀴 수레 물에 잠긴 STORMBAG 자루들")]},
    {"id": "N2", "fn": "시연(숫자)", "kind": "tts", "text": "3~5분이면 물 15리터쯤 먹고, 빵빵하게 부푼다는데",
     "tts": "삼에서 오 분이면 물 십오 리터쯤 먹고, 빵빵하게 부푼다는데",
     "caps": ["3~5분이면", "물 15리터쯤 먹고", "빵빵하게 부푼다는데"], "facts": ["f3"],
     "shots": [("8UW", 58.00, 1.90, TV, "잔디 위 STORMBAG 자루가 부푸는 타임랩스(스튜디오 화면 속)"),
               ("8UW", 61.85, 1.62, TV, "같은 타임랩스 — 자루가 더 부풂")]},
    {"id": "N3", "fn": "기존 불편(대체)", "kind": "tts", "text": "홍수 때마다 쌓던 모래주머니, 대신 쓰려고 만든 거라고",
     "tts": "홍수 때마다 쌓던 모래주머니, 대신 쓰려고 만든 거라고",
     "caps": ["홍수 때마다 쌓던", "모래주머니 대신", "쓰려고 만든 거라고"], "facts": ["f4"],
     "shots": [("3s0", 33.90, 1.90, crop_x(SUB3, 468), "마른 땅에 쌓인 모래주머니 더미"),
               ("8UW", 38.80, 1.06, crop_x(FULL, 405), "무대 와이드 — STORMBAG 로고 화면·모래주머니 벽 앞 두 창업자(제품 소개 순간)")]},
    {"id": "O3", "fn": "기존 불편", "kind": "orig", "src": "8UW", "span": [17.95, 23.85],
     "en": "Traditional sandbags require back-breaking labor, not to mention thousands of pounds of sand.", "who": "창업자(남) — 방송 원본도 이 시각엔 모래주머니 자료화면(말하는 사람 안 나옴)",
     "caps": ["기존 모래주머니는", "허리가 끊어지고", "모래만 수천 파운드죠"], "facts": ["f5"],
     "shots": [("8UW", 17.95, 5.90, crop_x(FULL, 405), "화면 가득 모래주머니 더미(방송 원본 같은 시각 — 소리·화면 같은 원본 초)")]},
    {"id": "N4", "fn": "기존 불편→차이", "kind": "tts", "text": "하나하나 들어 옮겨 쌓던 모래주머니랑은 다르게",
     "tts": "하나하나 들어 옮겨 쌓던 모래주머니랑은 다르게",
     "caps": ["하나하나 들어 옮겨 쌓던", "모래주머니랑은 다르게"], "facts": ["f6"],
     "shots": [("3s0", 18.25, 2.82, crop_x(SUB3, 468), "모래주머니를 던져 쌓고 한 개씩 들어 옮기는 손·다리")]},
    {"id": "O4", "fn": "해결", "kind": "orig", "src": "8UW", "span": [45.25, 50.00],
     "en": "Almost takes no labor to deploy, all you simply do is add water.", "who": "창업자(남·자루 든 사람)",
     "caps": ["설치할 때", "힘이 거의 안 들고", "그냥 물만 부으면 돼요"], "facts": ["f7"],
     "shots": [("8UW", 45.25, 4.75, crop_x(FULL, 560), "자루 든 창업자(45.25~47.61) → 47.61 원본 컷 무대 와이드 두 창업자 — 소리와 같은 원본 초")]},
    {"id": "N5", "fn": "숫자(무게)", "kind": "tts", "text": "물길에 놓기만 하면, 13킬로그램 넘는 둑이 된다고",
     "tts": "물길에 놓기만 하면, 십삼 킬로그램 넘는 둑이 된다고",
     "caps": ["물길에 놓기만 하면", "13kg 넘는 둑이", "된다고"], "facts": ["f8"],
     "shots": [("3s0", 168.40, 1.60, crop_x(SUB3, 468), "외바퀴 수레 물에서 불어난 자루를 꺼내 드는 남자"),
               ("3s0", 174.00, 1.50, crop_x(SUB3, 468), "땅에 줄지어 놓인 불은 자루 둑")]},
    {"id": "O5", "fn": "질문(재사용)", "kind": "orig", "src": "8UW", "span": [110.65, 112.30], "en": "Is there any way to get it back?", "who": "투자자(남·민머리·검정 정장)",
     "caps": ["다시 되돌릴 수 있어요?"], "facts": ["f9"],
     "shots": [("8UW", 110.65, 1.65, crop_x(FULL, 560), "의자에서 손가락으로 가리키며 묻는 투자자(민머리·검정 정장)")]},
    {"id": "N6", "fn": "재사용", "kind": "tts", "text": "햇볕에 두면 다시 납작하게 마르고, 세 번까지 다시 쓴다고",
     "tts": "햇볕에 두면 다시 납작하게 마르고, 세 번까지 다시 쓴다고",
     "caps": ["햇볕에 두면", "다시 납작하게 마르고", "세 번까지 다시 쓴다고"], "facts": ["f10"],
     "shots": [("3s0", 42.42, 2.24, crop_x(SUB3, 600), "납작한 마른 자루를 펼쳐 보이는 남자(제품사 영상)"),
               ("3s0", 50.35, 1.00, crop_x(SUB3, 468), "납작한 자루를 다시 드는 남자(제품사 영상)")]},
    {"id": "O6", "fn": "반응", "kind": "orig", "src": "8UW", "span": [85.95, 87.05], "en": "That's pretty cool.", "who": "투자자(남·남색 셔츠)",
     "caps": ["그거 꽤 괜찮네요"], "facts": ["f11"],
     "shots": [("8UW", 85.95, 1.10, crop_x(LT, 650), "의자에 앉은 투자자(남·남색 셔츠)(하단 자막 띠 위만)")]},
    {"id": "O7", "fn": "숫자 질문", "kind": "orig", "src": "8UW", "span": [243.15, 244.15], "en": "You making any money?", "who": "투자자(남·민머리·검정 정장)",
     "caps": ["돈은 좀 벌고 있어요?"], "facts": ["f12"],
     "shots": [("8UW", 243.15, 1.00, crop_x(FULL, 560), "투자자(민머리·검정 정장) 상반신")]},
    {"id": "O8", "fn": "숫자(매출)", "kind": "orig", "src": "8UW", "span": [259.90, 261.25],
     "en": "…and we did $90,000,", "who": "창업자(남) — 무대 와이드에 두 창업자, 입 모양으로 누구인지는 불명",
     "caps": ["9만 달러 벌었어요"], "facts": ["f12"],
     "shots": [("8UW", 259.90, 1.35, crop_x(FULL, 700), "무대 와이드 — 두 창업자(말하는 중, 소리와 같은 원본 초)")]},
    {"id": "N7", "fn": "자신감", "kind": "tts", "text": "광고는 아직 한 번도 안 했다며, 제대로만 하면 수백만 달러도 노린다고 자신하는데",
     "tts": "광고는 아직 한 번도 안 했다며, 제대로만 하면 수백만 달러도 노린다고 자신하는데",
     "caps": ["광고는 아직", "한 번도 안 했다며", "제대로만 하면", "수백만 달러도 노린다고", "자신하는데"], "facts": ["f12", "f13"],
     "shots": [("8UW", 263.05, 1.30, crop_x(FULL, 405), "듣고 있는 투자자(여·연두 옷)"),
               ("8UW", 266.92, 2.06, crop_x(FULL, 405), "안경 쓴 창업자 클로즈업(말하는 중)"),
               ("8UW", 269.05, 1.46, crop_x(FULL, 405), "물 수조 속 부푼 STORMBAG 자루")]},
    {"id": "O9", "fn": "지분 제안", "kind": "orig", "src": "8UW", "span": [464.06, 466.85],
     "en": "…the $200,000, but for 30%.", "who": "투자자(여·연두 옷) — 화면에 말하는 본인",
     "caps": ["20만 달러 드릴게요", "대신 지분은 30%로요"], "facts": ["f14"],
     "shots": [("8UW", 464.06, 2.79, crop_x(LT, 380), "제안하는 투자자(여·연두 옷) — 소리와 같은 원본 초")]},
    {"id": "O10", "fn": "지분 경쟁", "kind": "orig", "src": "8UW", "span": [550.60, 552.62],
     "en": "We'll do 30 also.", "who": "투자자(남·남색 재킷) — 화면에 말하는 본인",
     "caps": ["우리도 30%로 할게요!"], "facts": ["f15"],
     "shots": [("8UW", 550.60, 2.02, crop_x(FULL, 560), "웃으며 말하는 투자자(남·남색 재킷) — 소리와 같은 원본 초")]},
    {"id": "N8", "fn": "지분 경쟁", "kind": "tts", "text": "처음 두 명도 30%로 내리면서, 네 명이 한판 붙었는데",
     "tts": "처음 두 명도 삼십 퍼센트로 내리면서, 네 명이 한판 붙었는데",
     "caps": ["처음 두 명도", "30%로 내리면서", "네 명이 한판 붙었는데"], "facts": ["f14", "f15"],
     "shots": [("8UW", 552.69, 1.03, crop_x(LT, 508), "투자자석 와이드(남 두 명)"),
               ("8UW", 542.35, 1.45, crop_x(FULL, 405), "의자에 앉은 투자자(남·자주색 정장)"),
               ("8UW", 543.85, 1.50, crop_x(FULL, 405), "의자에 앉은 투자자(여·연두 옷)")]},
    {"id": "O11", "fn": "결정", "kind": "orig", "src": "8UW", "span": [577.80, 579.05],
     "en": "Lori, Mark, you got a deal.", "who": "창업자(남) — 화면 창업자 클로즈업, 둘 중 누구 말인지는 불명",
     "caps": ["로리, 마크!", "두 분이랑 할게요"], "facts": ["f16"],
     "shots": [("8UW", 577.80, 1.25, crop_x(FULL, 500), "웃는 창업자(남·큰 체격) 클로즈업 — 소리와 같은 원본 초")]},
    {"id": "N9", "fn": "방송 안 결과(성사)", "kind": "tts", "text": "10%만 주려다, 결국 30%에 두 투자자와 손잡았다고",
     "tts": "십 퍼센트만 주려다, 결국 삼십 퍼센트에 두 투자자와 손잡았다고",
     "caps": ["10%만 주려다", "결국 30%에", "두 투자자와 손잡았다고"], "facts": ["f17"],
     "shots": [("8UW", 584.50, 1.90, crop_x(FULL, 405), "무대에서 투자자(여)와 창업자가 끌어안는 장면(손잡음)"),
               ("8UW", 592.10, 1.80, crop_x(FULL, 405), "두 창업자가 웃으며 무대를 걸어 나감(끝 컷 ≥1.5초)")]},
]

FACTS = {
    "f1": ("8UW 66.8~67.75 'What?'(받아쓰기 2모델 r3 67.25~67.75 일치) · 67.23 컷부터 투자자(남·남색 셔츠) 화면", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=66"),
    "f2": ("제품사 3s0 60.0~64.7 'fill this wheelbarrow with a little bit of water and submerge the StormBags' + 132.9~140.6 수레 물 속 자루 화면 · 8UW 53.9~57.6 창업자 'You can see the time-lapse right there' · 52.42~53.40 'Pretty cool'(2모델)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=50"),
    "f3": ("8UW 62.7~66.8 창업자 'in three to five minutes, it weighs a whopping 30 pounds' · 제품사 3s0 45.3~50.1 'absorb between four and five gallons' · stormbag.co 블로그 'absorbs roughly four gallons of fresh water in three to five minutes'(4갤런=15.1L)",
           "https://stormbag.co/blogs/stormbag-flood-protection-blog/stormbag-on-shark-tank-the-sandless-sandbag-that-won-a-200k-deal"),
    "f4": ("8UW 12.8~17.6 창업자 'when a flood is on the way, the last thing you want to be doing is shoveling sand' · 30.0~37.7 'build a wall like this with no shoveling and no sand'", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=12"),
    "f5": ("8UW 17.95~23.85 원음(r6 2모델) 'Traditional sandbags require back-breaking labor, not to mention thousands of pounds of sand.'(r1 2모델 일치, 1명)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=17"),
    "f6": ("제품사 3s0 3.8~11.1 'the last thing that you want to be doing is shoveling sand. Traditional sandbags require back-breaking labor' + 3s0 18~24초 삽질 화면", "https://www.youtube.com/watch?v=3s0CwrcqWCU"),
    "f7": ("8UW 45.25~50.00 원음 'almost takes no labor to deploy, all you simply do is add water.'(r2 2모델 일치, 1명)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=45"),
    "f8": ("8UW 62.7~66.8 '30 pounds'(=13.6kg → '13킬로그램 넘는') · 8UW 30.0~37.7 'build a wall like this' · 3s0 50.1~54.6 '1-lb bag into a fully usable 35-lb sandbag'", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=62"),
    "f9": ("8UW 110.65~112.30 원음 'Is there any way to get it back?'(r4 2모델 일치 — 112.10 은 'back' 잘림, 112.30 에서 자름, 뒤 'or is it a one-time deal' 제외)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=110"),
    "f10": ("8UW 113.3~118.5 창업자 'if you have it out in the sun … it will dehydrate again flat' · 121.5 'Three times.' (★벤치 '2~3주 내로 건조'는 원본상 화분 물주기 주기(364.5~367.4) — 우리는 안 씀)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=113"),
    "f11": ("8UW 85.95~87.05 원음 'That's pretty cool.'(r1 2모델 일치) · 85.89~87.39 투자자(남·남색 셔츠) 화면", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=85"),
    "f12": ("8UW 243.15~244.15 투자자 'You making any money?' · 원음 259.90~261.25 '…and we did $90,000,'(r5 2모델) · 261.6~263.6 'but we have so far done absolutely zero marketing'(r2·r3 2모델 — 나레 N7 근거, 화면이 듣는 투자자라 원음으로는 안 씀)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=240"),
    "f13": ("8UW 264.6~269.8 창업자 'there's a huge untapped potential to make millions'", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=264"),
    "f14": ("원음 464.06~466.85 '…the 200,000, but for 30%'(r6 2모델) · 8UW 410.9~426.8 투자자 2명(화면 띠 'Daymond & Daniel\'s offer: $200k for a 40% stake' 7:08~7:14) '$200,000 for 40%' · 463.0~466.6 투자자(여) '$200,000, but for 30%'(화면 띠 'Lori & Mark\'s offer: $200k for a 30% stake' 7:48~7:50)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=410"),
    "f15": ("원음 550.60~552.62 'We'll do thirty also'(r7) · 8UW 550.6~553.1 투자자 'We'll do 30 also' · 다른 투자자 'We'll do 30, we'll match it' → 투자자 4명이 같은 30% 조건(553.2 'now they're equal' · 화면 띠 'Daymond & Daniel\'s revised offer: $200k for a 30% stake' 9:14~9:18)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=550"),
    "f16": ("8UW 577.80~579.05 'Lori, Mark, you got a deal.'(r5 2모델)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=577"),
    "f17": ("화면 띠 'Seeking $200k for a 10% stake'(1:16~1:24·5:10) + 8UW 5.9~12.0 'seeking 200,000 … for 10%' · 화면 띠 'Lori & Mark\'s offer: $200k for a 30% stake'(7:48) · 577.8~579.9 'Lori, Mark, you got a deal.' + 584~588 무대 포옹 — 방송 안에서 확인된 결과만(방송 뒤 계약·판매는 출처 상충·회사 단독이라 안 씀)", "https://www.youtube.com/watch?v=8UW-es-eTl0&t=577"),
}


def nchar(s):
    return len("".join(ch for ch in s if not ch.isspace() and ch not in ",.?!~"))


def build():
    t = 0.0
    out_lines, shots = [], []
    for k, L in enumerate(LINES):
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
        for j, f in enumerate((0.06, 0.5, 0.94)):
            tt = s["ss"] + s["dur"] * f
            out = FR_DIR / f"s{s['i']:02d}_{j}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tt:.3f}", "-i", f"{SRC_DIR}/{s['src']}", "-frames:v", "1",
                            "-vf", f"crop={w}:{h}:{x}:{y},scale=200:195", str(out)], check=True)
            s.setdefault("_fr", []).append(str(out))
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
    d.text((10, 8), "샥탬스토리 1편 STORMBAG 계획 시트 — 컷마다 처음·가운데·끝 프레임(창 1080x1052 비율 크롭) · 원음=노랑 · 나레=파랑", fill="black", font=FB)
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
        for seg in _wrap(body, 17) + _wrap("자막: " + cap, 17) + _wrap("화면: " + s["ours"], 17):
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
        "topic": "샤크탱크 STORMBAG — 물에 담그면 부푸는 모래 없는 모래주머니, 투자자 넷이 같은 조건으로 붙은 편(벤치 그대로 칼카피, 방송 원음 위주)",
        "voice": {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "engine": "typecast", "why": "벤치 나레 4편 f0 중앙 116.4Hz(남) — 지훈 견본 129.0Hz 1.79반음, 후보 중 가장 가까움(plan/voice_measure.json)"},
        "brand": "샥탬스토리", "style": "현장썰(한국어 나레 + 영어 원음 번역 자막 + 제품)",
        "bench": bench,
        "titles": {"hook": "홍수를 막을 수 있는\n역대급 모래 주머니?!", "rule": "벤치 그대로(사장님 10-18 ③) — 1줄 노랑 [211,304] / 2줄 흰 [318,407], 끝 '?!'. 벤치에 로고 없음 → 로고 넣지 않음(페이블 10-18). 기록만, 구현은 페이블 OK 뒤"},
        "facts": {k: {"text": v[0], "url": v[1]} for k, v in FACTS.items()},
        "final": {"lines": lines, "est_total_sec": total, "cps_target": CPS,
                  "orig_audio": [{"id": L["id"], "src": SOURCES[L["src"]]["file"], "span": L["span"], "en": L["en"], "ko_caps": L["caps"], "who": L["who"]}
                                 for L in lines if L["kind"] == "orig"]},
        "effects_record": [
            {"at": "O1", "fx": "빨간 원(투자자 얼굴 — 벤치와 같은 자리·같은 0초)", "bench": "0.0~0.6초"},
            {"at": "O3", "fx": "빨간 점선 원(삽질 장면)", "bench": "9.1~11.9초"},
            {"at": "O3 둘째 조각", "fx": "분홍 위 화살표", "bench": "11.9~14.2초"},
            {"at": "O9", "fx": "날개 돈다발 이모지", "bench": "38.6~41.1초"},
            {"at": "자막", "fx": "흰 글자+검정 테두리, 핵심어 형광(민트·초록·빨강·분홍)", "bench": "전 구간"}],
        "notes": ["TTS·렌더 전. 효과·제목 띠는 기록만(구현 안 함).",
                  "벤치 나레 연속 3어절 일치 0 — check_copy() 로 잰다(대본.json check.copy3).",
                  "페이블 10-18 판정: 정부 인증·방송 뒤 계약/재고 줄 뺌(출처 상충·회사 단독), 끝은 방송 안 결과로 닫음. 로고 넣지 않음(벤치에 없음)."],
    }
    doc["final"]["check"] = check_copy(lines)
    (D / "대본.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    mat = {"_note": "샥탬스토리 1편 재료 계획 — TTS·렌더 전. 창 1080x1052(벤치 뜯기 layout). 시각은 말속도 7.1자/초 추정 — TTS 뒤 다시 맞춘다. 원음 줄은 audio_span 을 원본에서 그대로(쉼 자르기 없음).",
           "cand_dir": SRC_DIR, "window": list(WIN), "sources": SOURCES, "shots": shots,
           "check": {"cut_count": len(shots), "cut_median": _median([s["dur"] for s in shots]), "first_cut": shots[0]["dur"],
                     "last_cut": shots[-1]["dur"], "min_scale_res": min(s["scale"] for s in shots), "max_scale": max(s["scale"] for s in shots),
                     "est_total_sec": total, "bench_total": 50.467, "same_src_within3s": same_src_close(shots)}}
    (D / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(mat["check"], ensure_ascii=False), json.dumps(doc["final"]["check"], ensure_ascii=False))


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return round((xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2), 2)


def same_src_close(shots):
    """B13 — 같은 소스 재사용: 원본 구간이 겹치거나, 뒤에 나온 컷이 앞 컷보다 이른 원본 시각으로 3초 안에 되돌아감. 앞으로만 가는 이어감·건너뜀은 제외."""
    bad = []
    for a in shots:
        for b in shots:
            if b["i"] <= a["i"] or a["src"] != b["src"]:
                continue
            a0, a1 = a["src_span"]
            b0, b1 = b["src_span"]
            overlap = b0 < a1 - 0.01 and a0 < b1 - 0.01
            back = b0 < a0 and a0 - b1 < 3
            if overlap or back:
                bad.append([a["i"], b["i"], a["src"][:3], [a0, a1], [b0, b1]])
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
    return {"copy3": hits, "max_cap_chars": max(len(c) for L in lines for c in L["caps"])}


if __name__ == "__main__":
    main()
