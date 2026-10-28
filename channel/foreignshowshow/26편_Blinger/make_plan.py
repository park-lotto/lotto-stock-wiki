# -*- coding: utf-8 -*-
"""샥탬스토리 26편 Blinger — 벤치 해외쇼츠 opK6XXBLrks(「딸깍 한번에 / 머리카락에 보석이?!」 20만, 49.9초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/26편_Blinger/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Can Mother-Daughter Duo Sell Blinger Product To The Sharks?' xZZ-uy34x1I, 1080p 30fps, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/26편_Blinger/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청·제안 띠(118~125·442~445·580~583·596~599·680~683초)와 708초 뒤 끝 화면은 안 쓰는 구간. 쓰는 컷은 띠 없음.
★화면이 분홍(옷·무대) 투성이 — 자막 강조색 빨강·분홍·주황 금지(체크리스트 ④).
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '2억 7천에 지분 25%'(금액·지분)·'의료용 등급 접착제·어린아이도 안심'(성분·안전성)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/26편_Blinger/src")
CLIP = "xZZ-uy34x1I"
FILES = {CLIP: ("xZZ-uy34x1I.mp4", 0.0, (1920, 1080))}
AUDIO = "xZZ-uy34x1I_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 이름/요청/제안 띠(118~125·442~445·580~583·596~599·680~683초)는 안 쓰는 구간 · 708초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (83.94, 84.96), "en": "Wow, that was so easy.",
     "sub": ["와 진짜 쉽네!"], "facts": ["f1"], "cap_at": [83.94], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 투자자 손에 든 분홍 블링거) — 벤치 0~1.0 투자자 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 154.90, 155.92, 1140, y=280, h=800, ours="블링거를 손에 들고 만져 보는 투자자(원본 샷 154.89~155.92 — 83.2~84.5초 이 말을 할 때 화면도 이 투자자, 소리 = 그 원음 cover)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "머리에 대고 딸깍 누르기만 하면 보석이 박히는 도구가 있는데",
     "tts": "머리에 대고 딸깍 누르기만 하면, 보석이 박히는 도구가 있는데",
     "sub": ["머리에 대고 딸깍", "누르기만 하면", "보석이 박히는 도구가 있는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5('딸깍 한 번에 머리에 보석이 박히는')",
     "cuts": [C(CLIP, 44.00, 46.80, 960, ours="분홍 블링거 상자들(원본 샷 42.64~47.28, 제품 브랜드, 소리 끔)"),
              C(CLIP, 68.40, 71.30, ours="머리카락에 블링거를 대고 누르는 손(샷 65.50~71.40 — O2 63.7~65.3 과 3초 떨어지게 뒤쪽, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(한 마디)", "audio": (63.74, 65.30), "en": "Click and bling.",
     "sub": ["딸깍 누르면 반짝!"], "facts": ["f2"], "cap_at": [63.74],
     "cuts": [C(CLIP, 63.74, 65.30, ours="블링거를 들고 말하는 창업자 본인(원본 샷 59.56~65.50)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(빼기)", "text": "열도 안 쓰고 뺄 때는 빗질 한 번이면 끝이라는데",
     "tts": "열도 안 쓰고, 뺄 때는 빗질 한 번이면 끝이라는데",
     "sub": ["열도 안 쓰고", "뺄 때는 빗질", "한 번이면 끝이라는데"], "facts": ["f2", "f3"],
     "fx": "초록 번쩍 — 벤치 8.7('열도 전혀 사용하지 않아')",
     "cuts": [C(CLIP, 78.00, 80.60, ours="딸 머리에 블링거를 대 주는 엄마(원본 샷 77.78~83.18, 소리 끔)"),
              C(CLIP, 102.40, 105.50, ours="보석을 보여 주며 설명하는 두 창업자(샷 102.34~105.54, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "해답(구호)", "audio": (107.70, 109.25), "en": "Bling in, brush out.",
     "sub": ["딸깍 넣고", "쓱 빼기!"], "facts": ["f3"], "cap_at": [107.70, 108.55],
     "cuts": [C(CLIP, 107.70, 109.25, ours="구호를 외치는 두 창업자 본인(원본 샷 107.31~109.28)")]},
    {"id": "N3", "kind": "나레", "beat": "체험(가발)", "text": "까다로운 샤크도 가발까지 쓰고 직접 해 봤다는데",
     "tts": "까다로운 샤크도, 가발까지 쓰고 직접 해 봤다는데",
     "sub": ["까다로운 샤크도", "가발까지 쓰고", "직접 해 봤다는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 시연",
     "cuts": [C(CLIP, 168.50, 170.30, ours="가발을 쓰고 보석을 만져 보는 투자자(원본 샷 168.40~170.34, 소리 끔)"),
              C(CLIP, 172.10, 173.90, ours="블링거를 손에 들고 살펴보는 다른 투자자(샷 172.04~173.94, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "반응(해냈다)", "audio": (163.32, 164.92), "en": "Amazing. You did it!",
     "sub": ["대박!", "해냈네!"], "facts": ["f4"], "cap_at": [163.32, 164.28],
     "cuts": [C(CLIP, 163.32, 164.92, ours="손뼉 치며 반응하는 투자자(원본 샷 163.23~164.96)")]},
    {"id": "N4", "kind": "나레", "beat": "숫자(사연)", "text": "꿈에서 떠오른 아이디어 하나로 집까지 팔아 가며 만들었다는데",
     "tts": "꿈에서 떠오른 아이디어 하나로, 집까지 팔아 가며 만들었다는데",
     "sub": ["꿈에서 떠오른", "아이디어 하나로", "집까지 팔아 가며", "만들었다는데"], "facts": ["f5"],
     "cuts": [C(CLIP, 198.00, 203.60, ours="사연을 말하는 창업자(원본 샷 197.83~203.74, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "숫자(집)", "audio": (242.15, 243.14), "en": "I sold the house.",
     "sub": ["집을 팔았어요"], "facts": ["f5"], "cap_at": [242.15],
     "fx": "빨강 번쩍 — 벤치 사연",
     "cuts": [C(CLIP, 242.15, 243.14, ours="말하는 창업자 본인(원본 샷 242.11~245.65)")]},
    {"id": "N5", "kind": "나레", "beat": "숫자(대박·짝퉁)", "text": "장난감 회사와 손잡고 대박이 났지만 짝퉁이 쏟아졌다는데",
     "tts": "장난감 회사와 손잡고 대박이 났지만, 짝퉁이 쏟아졌다는데",
     "sub": ["장난감 회사와 손잡고", "대박이 났지만", "짝퉁이 쏟아졌다는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 257.70, 259.60, 960, ours="블링거 상자 묶음(원본 샷 257.62~259.69, 제품 브랜드, 소리 끔)"),
              C(CLIP, 305.90, 310.70, ours="사연을 말하는 창업자(샷 305.87~310.84, 소리 끔)")]},
    {"id": "N6", "kind": "나레", "beat": "지분 경쟁(거절)", "text": "회사가 엉망이라며 샤크들이 줄줄이 빠지는데",
     "tts": "회사가 엉망이라며, 샤크들이 줄줄이 빠지는데",
     "sub": ["회사가 엉망이라며", "샤크들이", "줄줄이 빠지는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 497.30, 500.70, ours="'엉망'이라며 빠지는 투자자(원본 샷 497.10~500.83, 소리 끔)"),
              C(CLIP, 514.50, 516.75, ours="빠지겠다고 말하는 다른 투자자(샷 514.41~516.85, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(제안)", "audio": (531.20, 533.56), "en": "Wait a minute. I'm going to give you an offer right now.",
     "sub": ["잠깐만요", "지금 바로 제안할게요!"], "facts": ["f8"], "cap_at": [531.20, 531.68],
     "fx": "초록 번쩍 — 제안",
     "cuts": [C(CLIP, 536.00, 538.36, cover=True, ours="제안하는 바바라 본인(원본 샷 535.64~539.51 — 소리 = 이 줄 원음, 같은 사람의 이어지는 말 화면)")]},
    {"id": "O7", "kind": "원음", "beat": "결정(성사)", "audio": (684.10, 685.40), "en": "All right, let's do a deal, then.",
     "sub": ["좋아요", "거래할게요!"], "facts": ["f8"], "cap_at": [684.10, 684.62],
     "cuts": [C(CLIP, 684.10, 685.40, 1400, ours="말하는 창업자 본인(원본 샷 682.65~685.45 — 684.3초까지 왼아래 제안 띠가 사라지는 중이라 크롭을 오른쪽 끝 x 811~ 로, 띠 x<800 밖)")]},
    {"id": "O8", "kind": "원음", "beat": "결정(포옹)", "audio": (689.62, 690.58), "en": "I'm so proud of you.",
     "sub": ["너무 자랑스러워!"], "facts": ["f8"], "cap_at": [689.62],
     "cuts": [C(CLIP, 689.62, 690.58, 1400, ours="끌어안는 두 창업자(원본 샷 686.89~691.69 — 왼쪽 제품 광고 사진은 크롭을 오른쪽으로)")]},
    {"id": "N7", "kind": "나레", "beat": "끝(결과)", "text": "꿈 하나로 시작한 엄마가 결국 샤크까지 잡았다는데",
     "tts": "꿈 하나로 시작한 엄마가, 결국 샤크까지 잡았다는데",
     "sub": ["꿈 하나로 시작한 엄마가", "결국 샤크까지", "잡았다는데"], "facts": ["f8"],
     "cuts": [C(CLIP, 693.10, 694.80, 960, ours="무대로 나와 창업자들에게 다가가는 바바라(원본 샷 693.03~694.83, 소리 끔)"),
              C(CLIP, 698.20, 700.90, ours="창업자들과 끌어안는 바바라(샷 698.16~701.17, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/26편_Blinger/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 26편 Blinger — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "머리에 딸깍 하면", "line2": "보석이 박힌다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 83.94~84.98 'Wow, that was so easy.'(스피치매틱스 enhanced 영어 — 투자자 원음, 이름은 자막에 안 씀) · 화면은 같은 원본 154.9초 블링거를 든 같은 투자자(cover — 83.2~84.5초 이 말 화면도 이 투자자)", "url": U + CLIP + "&t=83s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 43.00~54.32 'Blinger is the styling tool that allows fashionistas of all ages to effortlessly add crystals, pearls, and other gems to their hair without heat…' · 58.60~65.30 'You simply load. Click and bling.' · 화면 65~71 시연", "url": U + CLIP + "&t=43s", "kind": "방송 원음+화면"},
    "f3": {"text": "원본 103.70~109.42 'And when you are ready to remove them, you simply brush them out. Bling in, brush out.'", "url": U + CLIP + "&t=103s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 119.06~124.92 'for you gentlemen, you'll notice that there's wigs…' · 152.44~170.36 투자자가 가발에 직접 해 봄 'Amazing.' 'You did it!' · 화면 156~170", "url": U + CLIP + "&t=152s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 31.44~34.60 'The idea for my invention came to me one night in a dream.' · 220.14~243.14 'what if we sell the house…' 'I sold the house.'", "url": U + CLIP + "&t=220s", "kind": "방송 원음+화면"},
    "f6": {"text": "원본 260.64~285.40 'I scheduled two pitches with two toy companies… licensing deal… royalty… In 2019, they did over $20 million wholesale' · 332.34~340.02 'we had illegal infringers all over the internet… totally knocked off' — 금액은 대본에 안 씀", "url": U + CLIP + "&t=260s", "kind": "방송 원음"},
    "f7": {"text": "원본 463.10~478.26 'We don't have a CFO… I really need a bookkeeper' · 502.72~510.16 'what a mess you've got on your hands… I'm out.' · 528.80~531.00 'everything's a mess. And so for those reasons, I'm out.'", "url": U + CLIP + "&t=463s", "kind": "방송 원음+화면"},
    "f8": {"text": "원본 531.20~533.56 'Wait a minute. I'm going to give you an offer right now.' · 596~598 띠 'Barbara's offer' · 684.10~685.54 'All right, let's do a deal, then.' · 689.62~690.58 'I'm so proud of you.' — 금액·지분은 대본에 안 씀", "url": U + CLIP + "&t=531s", "kind": "방송 원음+화면"},
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
        "topic": "Blinger(블링거) — 머리에 대고 누르면 보석이 박히는 도구. 꿈에서 떠올린 엄마가 집을 팔아 만듦, 시연·가발 쓴 샤크 → 장난감 회사 대박·짝퉁 → 엉망인 회사에 줄줄이 빠짐 → 바바라와 성사",
        "product": "Blinger hair gem styling tool(머리에 보석을 박는 도구)",
        "bench": {"id": "opK6XXBLrks", "channel": "해외쇼츠 @foreignshowshow", "title": "딸깍 한번에 머리카락에 보석이?! (화면 제목: 딸깍 한번에 / 머리카락에 보석이?!)",
                  "dur": 49.9, "views": 203000, "window": [0, 434, 1080, 1052], "cut_median": 1.8, "_cut_median_how": "2초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '2억 7천에 지분 25%'·'매출'(금액·지분) → 금액 없이 거절·성사만",
            "벤치 '의료용 등급 접착제'·'어린아이도 안심하고'(성분·안전성) — 쓰지 않음",
            "벤치 남의 광고 모델 얼굴 컷 — 이 원본 무대 시연으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '딸깍 한번에 / 머리카락에 보석이?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [434, 1026, 644, 1276], "target_what": "투자자 손에 든 분홍 블링거 — 154.9초 원본 프레임 눈 측정(창 크롭 [730,280,821,800] 안 x 1060~1220·y 730~920, ×1.315 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 8.7 해답"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "시연"},
    {"line": "O5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "사연"},
    {"line": "O6", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "제안"},
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
    mat = {"_note": "샥탬스토리 26편 Blinger 재료 계획. 창 1080x1052(벤치 opK6XXBLrks, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(xZZ-uy34x1I_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Can Mother-Daughter Duo Sell Blinger Product To The Sharks?", "해상도": "1920x1080 30fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 728.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(118~125·442~445·580~583·596~599·680~683초) 안 씀 · 708초 뒤 끝 화면 안 씀 · 무대 'blinger' 글 = 제품 브랜드"}},
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
