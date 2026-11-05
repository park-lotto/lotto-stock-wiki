# -*- coding: utf-8 -*-
"""샥탬스토리 16편 Rocketbook — 벤치 해외쇼츠 pc1_ezP__eY(「샤크들이 놓쳐서 / 가장 후회한 제품?!」 180만, 32.5초) 줄 단위 칼카피 (관제 097, 2026-10-27).

    PYTHONUTF8=1 py channel/foreignshowshow/16편_Rocketbook/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(15편 make_plan 꼴).
원음 줄 = 같은 회차 원본(CNBC Ambition 공식 'The Sharks Blast to the Future | Shark Tank Misses' bjW4T3xp8vc, 1080p, 영어 원어 140-7)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/16편_Rocketbook/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt.
★CNBC 원본은 왼쪽 아래 공작 로고·'CNBC.COM/CHANNELFINDER'·제안/이름 띠가 y≥920 에 있다 → 모든 컷 크롭 높이 900(y 0~900)으로 뺀다.
★앞은 하이브리드 재료 — 하이브리드는 N2 끝(약 13초)에서 자른다. 벤치의 '매년 150억'·'600억 회사'(금액)·아마존 화면·바닷가 뒤 영상(원본 밖)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/16편_Rocketbook/src")
CLIP = "bjW4T3xp8vc"
FILES = {CLIP: ("bjW4T3xp8vc.mp4", 0.0, (1920, 1080))}
AUDIO = "bjW4T3xp8vc_audio.m4a"        # 영어 원음(140-7 en-US original — 이 업로드엔 더빙 트랙 7개가 있어 원어만 따로 받음)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# 왼쪽 아래 CNBC 공작 로고(x 0~250·y≈950~1050 — 크롭 x≥298 이면 y 150~180 까지 내려도 안 걸림)·'CNBC.COM/CHANNELFINDER'(20~54초 y≈1000)·제안/이름 띠(25~31초 y≈920~1000) → 크롭 높이 900. 330초 뒤 끝 글자 화면 안 씀.
H_DEF = {CLIP: 900}
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (179.84, 182.72), "en": "This is the funniest, wackiest, most ridiculous thing I've heard in a long time.",
     "sub": ["이렇게 웃기고 황당한 건", "진짜 오랜만이네요"], "facts": ["f1"], "cap_at": [179.84, 181.12], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 투자자가 든 로켓북 노트) — 벤치 0~1.0 투자자석 와이드(우리는 물건 원)",
     "cuts": [C(CLIP, 107.60, 108.20, 760, 150, 900, ours="투자자(정장)가 창업자에게 받은 로켓북 노트를 들고 있음(원본 샷 106.81~111.01, 소리 = 다음 컷 투자자 원음 cover)", cover=True),
              C(CLIP, 180.44, 182.25, ours="검은 옷 투자자가 웃으며 '이렇게 웃기고 황당한 건 오랜만'(말하는 본인, 샷 179.61~182.28)"),
              C(CLIP, 182.32, 182.72, ours="검은 셔츠 투자자 반응(샷 182.28~183.28)")]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "샤크탱크 역사상 손꼽히게 아깝게 놓친 제품이라는 이 노트",
     "tts": "샤크탱크 역사상 손꼽히게 아깝게 놓친 제품이라는 이 노트",
     "sub": ["샤크탱크 역사상", "손꼽히게 아깝게 놓친", "제품이라는 이 노트"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 1.5('가장 후회한 제품')",
     "cuts": [C(CLIP, 17.90, 19.70, ours="금발 투자자가 웃으며 듣는 모습(원본 샷 17.85~20.05, 소리 끔)"),
              C(CLIP, 3.40, 5.60, 1150, ours="우주복 입은 창업자 둘이 'ROCKETBOOK' 표지판 앞에 서 있음(와이드, 샷 3.34~8.24)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(소개)", "audio": (8.32, 11.38), "en": "And we make notebooks from the future.",
     "sub": ["저희는 미래에서 온", "노트를 만들어요"], "facts": ["f3"], "cap_at": [8.32, 9.40],
     "cuts": [C(CLIP, 8.32, 11.36, 1330, ours="검은 머리 창업자가 노트를 들고 소개(말하는 본인 — 입 모양 확인, 샷 8.24~11.38 · 중간 cover 컷은 넣지 않음: 투자자 얼굴=1인칭 자막 오해, TV 기호=멈춤, 창업자 투샷=입 모양 안 맞음)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(기능)", "text": "필기하고 앱으로 찍으면 클라우드에 바로 저장되고, 지워서 다시 쓸 수도 있다는데",
     "tts": "필기하고 앱으로 찍으면 클라우드에 바로 저장되고, 지워서 다시 쓸 수도 있다는데",
     "sub": ["필기하고 앱으로 찍으면", "클라우드에 바로 저장되고", "지워서 다시 쓸 수도", "있다는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 4.5('사진을 찍으면')",
     "cuts": [C(CLIP, 32.00, 34.45, 1000, 30, 900, ours="무대 TV: 필기한 페이지를 휴대폰으로 찍어 올리는 화면(원본 샷 31.97~34.53 — 왼쪽 구글 드라이브·에버노트 아이콘 줄은 크롭 밖)"),
              C(CLIP, 49.00, 51.30, 960, 30, 900, ours="무대 TV: 페이지 아래 기호에 펜으로 X 표시(샷 48.52~54.05)")]},
    {"id": "O3", "kind": "원음", "beat": "해답(지우기)", "audio": (71.92, 76.32), "en": "You can make your entire notebook contents disappear.",
     "sub": ["노트에 쓴 내용을", "통째로 사라지게 할 수 있어요"], "facts": ["f4"], "cap_at": [71.92, 73.36],
     "fx": "빨강 번쩍 — 벤치 9.0('모두 지워져')",
     "cuts": [C(CLIP, 71.92, 72.38, ours="검은 셔츠 투자자가 턱을 괴고 듣는 중(샷 70.64~72.41)"),
              C(CLIP, 72.45, 74.08, 1340, ours="검은 머리 창업자(말하는 본인 — 입 모양 확인, 샷 72.41~74.11)"),
              C(CLIP, 74.13, 76.32, 960, ours="우주복 소매 앞 로켓북 노트 근접(샷 74.11~77.01)")]},
    {"id": "N3", "kind": "나레", "beat": "시연(전자레인지)", "text": "방법은 노트에 물 한 컵 올려서 전자레인지에 돌리는 거라는데",
     "tts": "방법은 노트에 물 한 컵 올려서 전자레인지에 돌리는 거라는데",
     "sub": ["방법은 노트에", "물 한 컵 올려서", "전자레인지에 돌리는 거라는데"], "facts": ["f4"],
     "cuts": [C(CLIP, 116.50, 119.05, 960, 180, 900, ours="무대 전자레인지에 투자자가 노트를 넣음(원본 샷 116.42~119.09)"),
              C(CLIP, 121.30, 123.85, 960, 180, 900, ours="전자레인지 속 노트 위에 물 컵을 올림(샷 121.25~123.89)")]},
    {"id": "O4", "kind": "원음", "beat": "문제(반대)", "audio": (151.44, 156.56), "en": "Why would I want to erase it? Why wouldn't I want to make them throw it out or burn it and buy another one?",
     "sub": ["대체 왜 지워요?", "버리거나 태우고", "새로 사게 해야죠"], "facts": ["f5"], "cap_at": [151.44, 153.04, 155.04],
     "fx": "빨강 번쩍 — 벤치 16.5('두번째 책은 안 팔 생각인거야?')",
     "cuts": [C(CLIP, 151.44, 154.10, ours="대머리 투자자가 손짓하며 반대(말하는 본인, 샷 151.42~154.12)"),
              C(CLIP, 154.15, 156.56, 1000, ours="투자자석 — 창업자가 노트를 나눠 주는 중(샷 154.12~156.82)")]},
    {"id": "O5", "kind": "원음", "beat": "결정(거절)", "audio": (186.80, 190.48), "en": "And 2 to 3 years from now, I think people will get tired of it. So I'm out.",
     "sub": ["2~3년 지나면", "다들 질릴 거예요", "그래서 전 빠질게요"], "facts": ["f6"], "cap_at": [186.80, 188.20, 189.76],
     "cuts": [C(CLIP, 186.80, 189.70, ours="검은 머리 창업자 근접 — 듣는 표정(샷 186.25~189.72, 말은 화면 밖 검은 옷 투자자)"),
              C(CLIP, 189.75, 190.48, ours="검은 옷 투자자 'So I'm out'(말하는 본인, 샷 189.72~190.66)")]},
    {"id": "N4", "kind": "나레", "beat": "결정(전원 거절)", "text": "결국 샤크 다섯 명이 줄줄이 빠졌는데",
     "tts": "결국 샤크 다섯 명이 줄줄이 빠졌는데",
     "sub": ["결국 샤크 다섯 명이", "줄줄이 빠졌는데"], "facts": ["f6"],
     "fx": "초록 번쩍 — 벤치 23.0('모든 투자자들의 거절')",
     "cuts": [C(CLIP, 204.80, 206.12, ours="양복 투자자가 빠지겠다고 말함(원본 샷 204.74~206.17, 소리 끔)"),
              C(CLIP, 278.05, 279.40, ours="금발 투자자가 빠지겠다고 말함(샷 278.01~279.45, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(마지막 거절)", "audio": (320.60, 322.36), "en": "I'm out, I'm out.",
     "sub": ["전 빠질게요, 빠질게요"], "facts": ["f6"], "cap_at": [320.60],
     "cuts": [C(CLIP, 320.60, 321.40, ours="검은 셔츠 투자자 'I'm out'(말하는 본인, 샷 317.38~321.45)"),
              C(CLIP, 321.50, 322.36, 1330, ours="창업자 반응(샷 321.45~323.16)")]},
    {"id": "N5", "kind": "나레", "beat": "끝(결과)", "text": "근데 몇 년 뒤 이 회사가 볼펜으로 유명한 빅에 팔렸다는데",
     "tts": "근데 몇 년 뒤 이 회사가 볼펜으로 유명한 빅에 팔렸다는데",
     "sub": ["근데 몇 년 뒤", "이 회사가 볼펜으로 유명한", "빅에 팔렸다는데"], "facts": ["f2"],
     "cuts": [C(CLIP, 326.02, 327.25, 960, ours="우주복 창업자 둘이 무대를 걸어 나감(와이드, 원본 샷 325.99~327.29, 소리 끔)"),
              C(CLIP, 327.35, 329.05, ours="검은 셔츠 투자자가 씁쓸하게 말함(샷 327.29~329.10, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/16편_Rocketbook/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 16편 Rocketbook — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "샤크 5명이 거절한", "line2": "미래에서 온 노트?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 179.84~182.72 'This is the funniest, wackiest, most ridiculous thing I've heard in a long time.'(스피치매틱스 enhanced 영어) — 화면 179.61~182.28 검은 옷 투자자(말하는 본인)", "url": U + CLIP, "kind": "방송 원음"},
    "f2": {"text": "원본 330~336초 CNBC 화면 글 'ROCKETBOOK WAS ONE OF THE BIGGEST MISSES IN SHARK TANK HISTORY. THE COMPANY WAS ACQUIRED IN DECEMBER 2020 BY PEN MAKER BIC FOR $40 MILLION.' — 대본엔 금액 안 씀", "url": U + CLIP, "kind": "방송사 화면 글(CNBC)"},
    "f3": {"text": "원본 8.32~11.48 'And we make notebooks from the future.' · 30.12~41.16 'take notes in your Rocketbook and scan them with the Rocketbook app to instantly blast those notes to popular cloud services' · 66.56~70.80 '…the Rocketbook Wave, to be reusable.'", "url": U + CLIP, "kind": "방송 원음"},
    "f4": {"text": "원본 71.92~76.32 'You can make your entire notebook contents disappear.' · 117.00~122.92 'you're gonna microwave your notebook here, and Commander Epstein is going to give you a little mug of water to place right on the circles on the cover.' · 175.36~179.80 'The water absorbs a lot of the microwave energy'", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f5": {"text": "원본 151.32~156.56 'Why would I want to erase it? Why wouldn't I want to make them throw it out or burn it and buy another one?'", "url": U + CLIP, "kind": "방송 원음"},
    "f6": {"text": "원본 189.76 'So I'm out.' · 205.72 'I'm out.' · 230.96 'I'm out.' · 278.08~279.72 'So for that reason, I'm out.' · 320.60~322.36 'I'm out, I'm out.' — 투자자 다섯 모두 거절", "url": U + CLIP, "kind": "방송 원음"},
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
        "topic": "Rocketbook(로켓북 — 필기 뒤 앱으로 찍어 클라우드에 올리고, 전자레인지·물로 지워 다시 쓰는 노트) — 우주복 차림 창업자 둘, 투자자 다섯이 전부 거절 → CNBC 가 '샤크탱크 역사상 가장 큰 놓침 중 하나'로 꼽고 2020년 12월 BIC 이 인수",
        "product": "Rocketbook(로켓북)",
        "bench": {"id": "pc1_ezP__eY", "channel": "해외쇼츠 @foreignshowshow", "title": "The product that the sharks missed the most was the most regrettable. (화면 제목: 샤크들이 놓쳐서 / 가장 후회한 제품?!)",
                  "dur": 32.534, "views": 1800000, "window": [0, 434, 1080, 1052], "cut_median": 1.23, "_cut_median_how": "check.scene_cuts 같은 자 23조각 중앙 — 10-27 실측"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '매년 150억을 벌고 600억의 회사를 팔게 된' — 금액(대본 금액 금지) → '볼펜으로 유명한 빅에 팔렸다'(CNBC 화면 글, 금액 뺌)",
            "벤치 0초 투자자 단체 화면·'가장 후회한' 투자자 인터뷰·아마존 순위 화면·바닷가 뒤 영상 — 이 원본 밖 → 원본 안 장면으로",
            "벤치 '가장 후회한' — 투자자 본인 후회 발언 출처를 못 찾음 → CNBC 화면 글 'one of the biggest misses in Shark Tank history' 그대로 '손꼽히게 아깝게 놓친'",
            "벤치 끝 '다들 우리가 돈을 못 벌 거라고 했지' 뒤 인터뷰 — 하이브리드 뒤(쿠팡 체험)가 그 자리를 대신함"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '샤크들이 놓쳐서 / 가장 후회한 제품?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.6], "target": [345, 935, 630, 1305], "target_what": "투자자가 든 로켓북 노트(제품) — 손 상자 = 108초 원본 프레임 눈 측정(완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "O1", "kind": "flash", "at": [540, 960], "t": [0.6, 0.98], "color": "초록", "how": "auto", "why": "원 다음 얼굴 컷 첫 프레임(14·15편과 같은 꼴)"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 1.5 '가장 후회한 제품'"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 4.5 '사진을 찍으면'"},
    {"line": "O3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 9.0 '모두 지워져'"},
    {"line": "O4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 16.5 '두번째 책은 안 팔 생각인거야?'"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 23.0 '모든 투자자들의 거절'"},
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
    mat = {"_note": "샥탬스토리 16편 Rocketbook 재료 계획. 창 1080x1052(벤치 pc1_ezP__eY, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(bjW4T3xp8vc_audio.m4a).",
           "sources": {
               CLIP: {"채널": "CNBC Ambition(공식)", "제목": "The Sharks Blast to the Future | Shark Tank Misses", "해상도": "1920x1080 29.97fps (137) + 140-7 영어 원어(더빙 트랙 7개는 안 씀)",
                      "길이": 349.0, "받은 구간": "전체",
                      "남의 글자": "왼쪽 아래 CNBC 공작 로고·'CNBC.COM/CHANNELFINDER'·이름/제안 띠 = 화면 아래 y≥920 → 모든 컷 크롭 높이 900 · 330초 뒤 끝 글자 화면·0초 CNBC 로고 안 씀 · 무대 'ROCKETBOOK' 표지판·노트 = 제품 브랜드 · 무대 TV 속 구글 드라이브 아이콘 화면(31~41초)은 안 씀"}},
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
