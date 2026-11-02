# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""샥탬스토리 23편 Stretchlace — 벤치 해외쇼츠 yeUP61IW6bM(「신발끈 평생 / 안묶어도 된다고?!」 24만, 45.0초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/23편_Stretchlace/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Mark Cuban Tries To Pit The Original Stretchlace's Entrepreneurs Against Robert' FW4-8lfU-4o, 1080p 30fps, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/23편_Stretchlace/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청·제안 띠(62~65·67~69·466~476·500~504·568~572초)와 596초 뒤 끝 화면은 안 쓰는 구간. 쓰는 컷은 띠 없음.
★벤치는 '결국 모두 거래를 거절'로 끝내지만 원본은 다섯 명 모두 빠진 뒤 로버트가 마음을 바꿔 거래 성사(435~594초) — 원본 사실대로.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '2만원'·'매출 2억'·'연간 14억'(금액)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/23편_Stretchlace/src")
CLIP = "FW4-8lfU-4o"
FILES = {CLIP: ("FW4-8lfU-4o.mp4", 0.0, (1920, 1080))}
AUDIO = "FW4-8lfU-4o_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 이름/요청/제안 띠(62~65·67~69·466~476·500~504·568~572초)는 안 쓰는 구간 · 596초 뒤 끝 화면 안 씀.
H_DEF = {CLIP: 1080}
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (123.76, 125.44), "en": "it really works.",
     "sub": ["진짜 되네?!"], "facts": ["f1"], "cap_at": [123.76], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 흰 끈을 꿴 검정 운동화) — 벤치 0~1.0 신발 바꿔 신는 발",
     "cuts": [C(CLIP, 92.80, 94.48, 1100, ours="받침대 위 흰 끈 검정 운동화 두 짝(원본 샷 92.73~94.53, 사람 없음 · 상표 없음 — 소리 = 끈을 끼워 본 투자자 원음 'it really works.' cover, 말한 사람은 화면 밖)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "아침마다 삼 형제 신발끈 묶어 주다 지쳐 버린 엄마가 있었는데",
     "tts": "아침마다 삼 형제 신발끈 묶어 주다, 지쳐 버린 엄마가 있었는데",
     "sub": ["아침마다 삼 형제", "신발끈 묶어 주다", "지쳐 버린 엄마가 있었는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5('3초 만에')",
     "cuts": [C(CLIP, 201.15, 204.60, ours="두 창업자가 사연을 말함(원본 샷 201.07~204.70, 소리 끔)"),
              C(CLIP, 215.00, 217.80, ours="세 아들 이야기를 하는 창업자 제이미(샷 214.25~, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "문제(한 마디)", "audio": (36.36, 38.40), "en": "You have to tie them every day,",
     "sub": ["매일 묶어야 하잖아요"], "facts": ["f3"], "cap_at": [36.36],
     "cuts": [C(CLIP, 36.36, 38.40, 880, y=140, h=740, cover=True, ours="무대 화면 속 아이들이 신발을 신는 영상(원본 샷 34.30~41.37, 화면 안쪽만 자름 — 소리 = 창업자 원음 cover, 말하는 사람은 화면 밖)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "그래서 한 번만 묶어 두면 그냥 쑥 신는 늘어나는 신발끈을 만들어 버렸다는데",
     "tts": "그래서 한 번만 묶어 두면, 그냥 쑥 신는 늘어나는 신발끈을 만들어 버렸다는데",
     "sub": ["그래서 한 번만 묶어 두면", "그냥 쑥 신는", "늘어나는 신발끈을", "만들어 버렸다는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 10.0('고무줄 운동화끈')",
     "cuts": [C(CLIP, 47.70, 49.50, ours="창업자가 신발끈을 쭉 늘여 보임(원본 샷 45.41~49.58, 소리 끔)"),
              C(CLIP, 50.30, 53.80, 900, ours="'TURN LACE UP SHOES INTO SLIP-ONS' 제품 상자들(샷 49.58~57.12 — 제품 자기 상자 글, 소리 끔)")]},
    {"id": "N3", "kind": "나레", "beat": "시연(10초 갈아신기)", "text": "샤크들 카운트다운 한 번에 부츠 벗고 운동화로 쑥 갈아 신는데",
     "tts": "샤크들 카운트다운 한 번에, 부츠 벗고 운동화로 쑥 갈아 신는데",
     "sub": ["샤크들 카운트다운 한 번에", "부츠 벗고 운동화로", "쑥 갈아 신는데"], "facts": ["f5"],
     "fx": "초록 번쩍 — 벤치 6.0('신발을 갈아신는 남자')",
     "cuts": [C(CLIP, 71.15, 74.15, 960, ours="부츠를 벗고 운동화에 발을 넣는 창업자 발(원본 샷 71.07~74.21, 소리 끔)"),
              C(CLIP, 74.25, 75.40, ours="웃으며 보는 투자자(샷 74.21~75.44, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "반응(너무 빠름)", "audio": (83.58, 84.58), "en": "Too fast. Too fast.",
     "sub": ["너무 빠르잖아!"], "facts": ["f5"], "cap_at": [83.58],
     "cuts": [C(CLIP, 75.50, 76.50, 960, cover=True, ours="운동화에 쑥 들어가는 발(원본 샷 75.44~77.34 — 소리 = 투자자 원음 'Too fast' cover, 말한 사람은 화면 밖)")]},
    {"id": "N4", "kind": "나레", "beat": "체험(샤크)", "text": "샤크들도 직접 끈을 끼워 보더니 다들 신기해서 난리가 났다는데",
     "tts": "샤크들도 직접 끈을 끼워 보더니, 다들 신기해서 난리가 났다는데",
     "sub": ["샤크들도 직접 끈을 끼워 보더니", "다들 신기해서", "난리가 났다는데"], "facts": ["f6"],
     "fx": "초록 번쩍 — 벤치 24.0('오 마이 갓')",
     "cuts": [C(CLIP, 112.75, 114.30, ours="신발에 끈을 끼우는 투자자(원본 샷 112.65~114.38, 소리 끔)"),
              C(CLIP, 114.45, 116.70, ours="신발을 신어 보는 다른 투자자(샷 114.38~116.78, 소리 끔)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁(거절)", "text": "근데 막상 투자 얘기가 나오자 샤크들이 줄줄이 손을 뗐는데",
     "tts": "근데 막상 투자 얘기가 나오자, 샤크들이 줄줄이 손을 뗐는데",
     "sub": ["근데 막상 투자 얘기가 나오자", "샤크들이 줄줄이", "손을 뗐는데"], "facts": ["f7"],
     "fx": "빨강 번쩍 — 벤치 41.0('결국 모두 거래를 거절')",
     "cuts": [C(CLIP, 383.85, 386.50, ours="빠지겠다고 말하는 투자자(원본 샷 383.78~386.59, 소리 끔)"),
              C(CLIP, 397.00, 400.80, ours="빠지겠다고 말하는 다른 투자자(샷 396.80~401.23, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "반응(독설)", "audio": (339.47, 341.17), "en": "You are shoelace cockroaches.",
     "sub": ["너흰 신발끈 바퀴벌레야"], "facts": ["f7"], "cap_at": [339.47],
     "cuts": [C(CLIP, 339.47, 341.17, ours="투자자석 넓은 화면 — 말하는 본인이 오른쪽(원본 샷 337.34~341.17)")]},
    {"id": "N6", "kind": "나레", "beat": "반전", "text": "다섯 명이 다 빠진 그때 로버트가 마음을 바꿨다는데",
     "tts": "다섯 명이 다 빠진 그때, 로버트가 마음을 바꿨다는데",
     "sub": ["다섯 명이 다 빠진 그때", "로버트가", "마음을 바꿨다는데"], "facts": ["f8"],
     "fx": "초록 번쩍 — 반전",
     "cuts": [C(CLIP, 391.75, 394.50, ours="고개 숙인 창업자 제이미 근접(원본 샷 391.66~394.59, 소리 끔)"),
              C(CLIP, 414.55, 417.95, ours="말을 꺼내는 로버트(샷 414.45~418.05, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "결정(제안)", "audio": (442.71, 443.51), "en": "I'll make you an offer.",
     "sub": ["내가 제안 하나 할게"], "facts": ["f8"], "cap_at": [442.71],
     "cuts": [C(CLIP, 442.71, 443.51, ours="제안하는 로버트(원본 샷 442.61~443.51, 말하는 본인)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(반응)", "audio": (445.41, 446.19), "en": "Are you nuts?",
     "sub": ["너 미쳤어?"], "facts": ["f8"], "cap_at": [445.41],
     "cuts": [C(CLIP, 445.41, 446.19, 1350, ours="놀라 묻는 투자자(원본 샷 445.41~446.25, 말하는 본인)")]},
    {"id": "O7", "kind": "원음", "beat": "결정(성사)", "audio": (576.55, 577.71), "en": "Congratulations, guys.",
     "sub": ["축하해요!"], "facts": ["f9"], "cap_at": [576.55],
     "fx": "초록 번쩍 — 성사",
     "cuts": [C(CLIP, 575.86, 577.00, cover=True, ours="두 팔 들고 기뻐하는 로버트(원본 샷 575.84~577.01 — 소리 = 다른 투자자 원음 cover)")]},
    {"id": "N7", "kind": "나레", "beat": "끝(결과)", "text": "신발끈 묶기 지친 엄마가 결국 샤크 한 명을 잡았다는데",
     "tts": "신발끈 묶기 지친 엄마가, 결국 샤크 한 명을 잡았다는데",
     "sub": ["신발끈 묶기 지친 엄마가", "결국 샤크 한 명을", "잡았다는데"], "facts": ["f9"],
     "cuts": [C(CLIP, 587.00, 590.00, 960, ours="손잡고 무대 뒤로 걸어 나오는 두 창업자(원본 샷 586.05~, 소리 끔)"),
              C(CLIP, 590.10, 593.40, 960, ours="복도를 걸어 나오는 두 창업자(같은 샷, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/23편_Stretchlace/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 23편 Stretchlace — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "신발끈 한 번만 묶고", "line2": "평생 쑥 신는다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 122.42~125.44 'Oh my gosh, it really works.'(스피치매틱스 enhanced 영어 — 끈을 끼워 본 투자자 원음, 이름은 자막에 안 씀) 중 123.76~125.44 · 화면은 같은 원본 92.8초 운동화(cover)", "url": U + CLIP + "&t=122s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 201.14~213.66 'I have three boys, and getting ready in the mornings was crazy. I was tying three pairs of shoes… And it just kind of ruined my day.'", "url": U + CLIP + "&t=201s", "kind": "방송 원음"},
    "f3": {"text": "원본 34.56~41.04 'Traditional laces are restrictive. You have to tie them every day, sometimes multiple times a day.'", "url": U + CLIP + "&t=34s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 51.08~58.84 'The original stretch lace is a stretchy lace… by turning your tie shoes into slip ons.' · 110.82~116.38 'You just lace them like standard laces. Leave a little bit of room at the top, tie them, and then you just slip your shoes on.'", "url": U + CLIP + "&t=51s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 59.00~64.78 'Let's see if David could slip into his boots and back into his sneakers in less than 10s.' · 69.62~80 샤크들 카운트다운 · 83.58~84.58 'Too fast. Too fast.'", "url": U + CLIP + "&t=59s", "kind": "방송 원음+화면"},
    "f6": {"text": "원본 107.14~125.44 샤크들이 끈을 받아 직접 끼워 봄 'So how does it work?'·'Oh my gosh, it really works.' · 화면 112~117", "url": U + CLIP + "&t=107s", "kind": "방송 원음+화면"},
    "f7": {"text": "원본 331.95 'I'm out.' · 339.47~341.31 'You are shoelace cockroaches.' · 343.03 'I'm out.' · 369 'I'm out.' · 388 'I'm out.' · 407 'I'm out.' · 435.11~436.87 'All five sharks are out.'", "url": U + CLIP + "&t=331s", "kind": "방송 원음+화면"},
    "f8": {"text": "원본 437.11~442.67 'But Robert has had a change of heart. Seeing the untapped potential in Jamie as an entrepreneur.' · 442.71~443.63 'I'll make you an offer.' · 445.35~446.19 'Are you nuts?'", "url": U + CLIP + "&t=435s", "kind": "방송 원음+화면"},
    "f9": {"text": "원본 571.55~572.59 'I will take 30.' · 576.55~577.71 'Congratulations, guys.' · 590.55~594.23 'It feels so wonderful to have gotten a deal with Robert.' — 금액·지분은 대본에 안 씀", "url": U + CLIP + "&t=571s", "kind": "방송 원음+화면"},
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
        "topic": "The Original Stretchlace(스트레치레이스) — 한 번 묶어 두면 그냥 쑥 신는 늘어나는 신발끈. 아침마다 아들 셋 신발끈을 묶어 주던 엄마가 만듦, 10초 갈아신기 시연 → 샤크 다섯 명 모두 빠짐 → 로버트가 마음을 바꿔 성사",
        "product": "The Original Stretchlace(스트레치레이스 늘어나는 신발끈)",
        "bench": {"id": "yeUP61IW6bM", "channel": "해외쇼츠 @foreignshowshow", "title": "신발끈 평생 안묶어도 된다고?! (화면 제목: 신발끈 평생 / 안묶어도 된다고?!)",
                  "dur": 45.0, "views": 243000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "1초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '2만원이라는 비싼 가격'·'올해 매출 2억'·'연간 14억'(금액) → 금액 없이 거절·반전·성사만",
            "벤치 '결국 모두 거래를 거절' → 원본 사실대로 다섯 명 모두 빠진 뒤 로버트가 마음을 바꿔 성사",
            "벤치 8~23초 남의 리뷰·광고 영상(아이·운동화 근접) — 이 원본 밖 → 원본 안 시연·제품 화면으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '신발끈 평생 / 안묶어도 된다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [423, 755, 949, 1174], "target_what": "오른쪽 운동화의 흰 끈 — 93.6초 원본 프레임 눈 측정(창 크롭 [546,0,1108,1080] 안 x 434~974·y 330~760, ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5 '3초 만에'"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 10.0 '고무줄 운동화끈'"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 6.0 '신발을 갈아신는 남자'"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 24.0 '오 마이 갓'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 41.0 '결국 모두 거래를 거절'"},
    {"line": "O7", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "성사"},
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
    mat = {"_note": "샥탬스토리 23편 Stretchlace 재료 계획. 창 1080x1052(벤치 yeUP61IW6bM, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(FW4-8lfU-4o_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Mark Cuban Tries To Pit The Original Stretchlace's Entrepreneurs Against Robert", "해상도": "1920x1080 30fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 615.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(62~65·67~69·466~476·500~504·568~572초) 안 씀 · 596초 뒤 끝 화면 안 씀 · 옷·상자 'STRETCHLACE' = 제품 브랜드"}},
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
