# -*- coding: utf-8 -*-
"""샥탬스토리 9편 P-Nuff Crunch — 벤치 해외쇼츠 MIlHlQ1Wdg4(「살 안찌는 땅콩과자 / 산다 vs 안산다」) 줄 단위 칼카피 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py channel/foreignshowshow/9편_PNuffCrunch/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(7편 make_plan 꼴).
소재·흐름 벤치 = BIG BAG HUSTLE sVsPbjTr55Y(3,600만, 영어) / 줄 단위 벤치 = 같은 제품 foreignshowshow 판 MIlHlQ1Wdg4(34.8초).
원음 줄 = 벤치가 쓴 원음 순간을 **같은 원본(Sony 공식 wp45o5i7zhE, 720p 최대) 시각**으로 — 근거.md §2 표.
크롭 가로 자리 = 얼굴 검출(fx_measure.faces, 컷 가운데 프레임 가장 큰 얼굴) — 눈대중 금지. 0초 원·첫 컷 크롭 = fx_place.hook_circle.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/9편_PNuffCrunch/src")
CLIP, VR, IO = "wp45o5i7zhE", "vr3dPT0wnrY", "IozegR4FmTA"
FILES = {CLIP: ("wp45o5i7zhE.mp4", 0.0, (1280, 720)), VR: ("vr3dPT0wnrY.mp4", 0.0, (1080, 1920)), IO: ("IozegR4FmTA.mp4", 0.0, (1080, 1920))}
AUDIO = "wp45o5i7zhE_audio.m4a"        # 영어 원음 140-5 'English (US) original' — 원본에 더빙 트랙 5개(de·es·fr·hi·pt) 섞임 방지(원리서 §9 3편)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
H_DEF = {CLIP: 720, VR: 1052, IO: 1052}
_FACE_CACHE: dict = {}


def face_cx(vid, t):
    """(판단 주인 아님 — 크롭 가로 자리 계산) 그 시각 프레임의 가장 큰 얼굴 가운데 x. 없으면 None."""
    key = (vid, round(t, 2))
    if key not in _FACE_CACHE:
        from tools.calcopy.shark.fx_place import _src_frame
        from tools.calcopy.shark import fx_measure as FM
        a, _, _ = _src_frame(SRC / FILES[vid][0], t)
        fs = FM.faces(a)
        _FACE_CACHE[key] = max(fs, key=lambda f: f["h"])["cx"] if fs else None
    return _FACE_CACHE[key]


def crop(vid, cx, y=0, h=None, t=None):
    """cx = 숫자 | 'face'(t 시각 얼굴 검출, 실패면 가운데)."""
    W, H = FILES[vid][2]
    h = h or H_DEF[vid]
    w = min(W, int(round(h * AR)))
    if cx == "face":
        cx = face_cx(vid, t) or W / 2
    x = max(0, min(W - w, int(cx - w / 2)))
    y = max(0, min(H - h, y))
    return [x, y, w, h]


def C(vid, a, b, cx="face", y=0, h=None, ours=""):
    return (vid, a, b, crop(vid, cx, y, h, t=(a + b) / 2), ours)


# 원음 줄 audio = (원본 시작, 끝). cut = (소스, 원본 시작, 원본 끝, [x,y,w,h], 화면에 보이는 것). 장면 경계 = 원본 프레임 차(asr/src_scenes.txt·근거 §2)
LINES = [
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (384.45, 386.80), "en": "I ate the whole freaking bag.",
     "sub": ["한 봉지를", "통째로 다 먹었어요"], "facts": ["f1"], "cap_at": [384.64, 385.16],
     "fx": "0초 빨간 원(말하는 투자자 얼굴, hook_circle) — 벤치 0.0~2.2 빨간 실선 원(같은 투자자 얼굴)",
     "cuts": [(CLIP, 384.45, 386.80, None, "봉지를 든 투자자가 '한 봉지를 다 먹었다'고 말함(말하는 본인, 샷 384.40~386.84) — 벤치 0초 컷과 같은 원본 샷")]},
    {"id": "N1", "kind": "나레", "beat": "의문(소개)", "text": "맛도 잡고 건강도 잡았다는 땅콩 과자가 있는데", "tts": "맛도 잡고 건강도 잡았다는 땅콩 과자가 있는데",
     "sub": ["맛도 잡고 건강도", "잡았다는", "땅콩 과자가 있는데"], "facts": ["f2"],
     "cuts": [C(VR, 0.10, 1.05, 540, 0, 960, ours="현장(판매사 길거리 시식 쇼츠 위 절반, 1080p 세로): 여학생들이 P-Nuff 봉지에서 꺼내 맛봄(아래 절반·자막 y≈1500 은 크롭으로 뺌)"),
              C(VR, 20.45, 21.00, 540, 230, ours="현장(같은 쇼츠): 분홍 머리 여성이 P-Nuff 를 씹으며 맛봄(장면 20.43~21.03)"),
              C(CLIP, 69.30, 70.60, 430, ours="투자자가 고개를 젖히고 크게 웃음(원본 샷 69.07~71.10, 소리 끔) — 벤치 4.0~5.17 같은 투자자 웃음")]},
    {"id": "O2", "kind": "원음", "beat": "해답(제품 정체)", "audio": (43.05, 46.80), "en": "It's the first nutrition-based crunchy peanut puff snack.",
     "sub": ["영양까지 챙긴", "최초의 바삭한 땅콩 과자"], "facts": ["f3"], "cap_at": [43.12, 44.86],
     "fx": "노랑 번쩍 — 벤치 5.17(봉지 그래픽 첫 프레임)",
     "cuts": [C(CLIP, 43.05, 43.75, 640, ours="무대 와이드(P-Nuff 간판 — 원본 편집 그대로, 말하는 창업자는 화면 밖)"),
              C(CLIP, 43.78, 46.25, 640, ours="방송 그래픽: P-Nuff Crunch 봉지(벤치 5.2~6.9 와 같은 원본 그래픽 — 포장 글자 = 제품)"),
              C(CLIP, 46.28, 46.80, 640, ours="방송: 그릇에 담긴 땅콩 퍼프")]},
    {"id": "N2", "kind": "나레", "beat": "전개(창업자)", "text": "식품과학 박사에 보디빌더 출신인 창업자가 직접 만들었다는데",
     "tts": "식품과학 박사에 보디빌더 출신인 창업자가 직접 만들었다는데",
     "sub": ["식품과학 박사에", "보디빌더 출신인 창업자가", "직접 만들었다는데"], "facts": ["f4"],
     "fx": "노랑 번쩍 — 벤치 8.7(창업자가 가운을 여는 컷 첫 프레임)",
     "cuts": [C(CLIP, 59.90, 61.40, ours="창업자가 흰 가운을 활짝 열어 근육을 보여 줌(원본 샷 58.99~63.07, 소리 끔)"),
              C(CLIP, 61.45, 63.00, h=600, ours="상의 벗은 창업자가 웃음(같은 샷 확대 크롭)"),
              C(CLIP, 63.12, 64.04, ours="빨간 블라우스 투자자가 웃으며 반응(원본 샷 63.10~64.06)")]},
    {"id": "O4", "kind": "원음", "beat": "시연(장점·반응)", "audio": (83.10, 88.95),
     "en": "But they're also good for building muscle. / Cut it out! / (and) staying fit. / Oh! Oh!",
     "sub": ["근육 만드는 데도", "좋아요", "그만해요!", "몸매 유지까지요", "오우~ 오우~"], "facts": ["f5"],
     "cap_at": [83.18, 84.62, 85.84, 87.04, 88.09],
     "fx": "초록 번쩍 — 벤치 14.77(초록 옷 투자자 반응 컷 첫 프레임 = 원본 86.871 샷 경계)",
     "cuts": [C(CLIP, 83.10, 83.92, ours="초록 옷 투자자가 듣고 있음(원본 반응 컷 — 원본 편집 그대로, 벤치 11.7~13.1 같음)"),
              C(CLIP, 83.95, 85.82, ours="창업자가 팔을 접어 알통을 보여 주며 말함(말하는 본인)"),
              C(CLIP, 85.85, 86.86, ours="빨간 블라우스 투자자가 손을 저으며 'Cut it out!'(말하는 본인)"),
              C(CLIP, 86.89, 88.06, ours="초록 옷 투자자 반응(원본 반응 컷 — 벤치 14.77 같음)"),
              C(CLIP, 88.09, 88.95, 640, ours="창업자 복근 근접('오! 오!' 탄성)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(성분)", "text": "글루텐 프리에 식물성 단백질로 만들고 130칼로리밖에 안 된다는데",
     "tts": "글루텐 프리에 식물성 단백질로 만들고 백삼십 칼로리밖에 안 된다는데",
     "sub": ["글루텐 프리에", "식물성 단백질로 만들고", "130칼로리밖에", "안 된다는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 74.92, 76.95, 640, ours="방송: 나무 탁자 위 그릇 가득 담긴 땅콩 퍼프(원본 샷 74.87~77.10, 소리 끔)"),
              C(CLIP, 77.15, 78.40, ours="투자자가 퍼프를 집어 먹어 봄(원본 샷 77.10~78.98, 소리 끔)"),
              C(IO, 30.71, 31.15, 540, 250, ours="판매사 광고(1080p 세로): 땅콩 퍼프 근접(장면 30.70~31.20, 아래 자막 y≈1500 크롭으로 뺌)")]},
    {"id": "O5", "kind": "원음", "beat": "계기(투자자 경험)", "audio": (376.40, 378.75), "en": "And these things are in the pantry.",
     "sub": ["집 찬장에", "이 과자가 있었는데"], "facts": ["f7"], "cap_at": [376.48, 377.46],
     "cuts": [C(CLIP, 376.40, 378.75, 640, ours="투자자석 와이드(말하는 투자자 앞쪽, 원본 샷 376.17~379.90) — 벤치 19.4~21.8 같은 샷")]},
    {"id": "O6", "kind": "원음", "beat": "계기(반응)", "audio": (392.90, 393.75), "en": "I wanted more.",
     "sub": ["더 먹고 싶더라고요"], "facts": ["f7"], "cap_at": [393.0],
     "cuts": [C(CLIP, 392.90, 393.75, ours="창업자가 웃으며 듣는 얼굴(원본 반응 컷, 샷 392.60~393.84) — 벤치 24.0 같음")]},
    {"id": "O7", "kind": "원음", "beat": "지분 경쟁(제안)", "audio": (397.25, 401.68), "en": "So I'll give you the 300K. I want 25%. / Woo!",
     "sub": ["30만 달러 줄게요", "지분은 25% 주세요", "우~!"], "facts": ["f8"], "cap_at": [397.30, 398.90, 401.12],
     "fx": "초록 번쩍(줄 첫 컷, 벤치 24.9 '투자할게') + 빨강 번쩍(398.85 확대 컷, 벤치 27.0 '25%')",
     "cuts": [C(CLIP, 397.25, 398.85, ours="투자자가 의자에 앉아 제안(말하는 본인, 샷 396.93~399.94)"),
              C(CLIP, 398.88, 399.92, h=560, ours="같은 샷 확대 크롭 — '25%'(벤치 27.0 확대 컷)"),
              C(CLIP, 399.95, 400.85, ours="초록 옷 투자자 반응(원본 반응 컷)"),
              C(CLIP, 400.89, 401.68, ours="대머리 투자자 'Woo!'(말하는 본인, 샷 400.87~401.84)")]},
    {"id": "O9", "kind": "원음", "beat": "지분 경쟁(설득)", "audio": (403.19, 404.52), "en": "I'm going to change your life.",
     "sub": ["당신 인생을", "바꿔 줄게요"], "facts": ["f8"], "cap_at": [403.19, 403.82],
     "cuts": [C(CLIP, 403.19, 404.52, ours="투자자가 몸을 앞으로 기울여 말함(말하는 본인, 샷 403.17~404.57)")]},
    {"id": "O10", "kind": "원음", "beat": "지분 경쟁(창업자)", "audio": (411.50, 414.85),
     "en": "I know you know this is going to be $100 million brand in five, six years.",
     "sub": ["아시잖아요,", "5~6년 뒤엔", "1억 달러 브랜드예요"], "facts": ["f9"], "cap_at": [411.56, 412.36, 413.08],
     "cuts": [C(CLIP, 411.50, 414.85, ours="창업자가 투자자 쪽을 보며 말함(말하는 본인, 샷 410.67~415.27)")]},
    {"id": "O11", "kind": "원음", "beat": "지분 경쟁(반박·끝)", "audio": (415.29, 418.10), "en": "But not just with you.",
     "sub": ["근데 당신 혼자선", "안 되죠"], "facts": ["f9"], "cap_at": [415.32, 415.88],
     "fx": "빨강 번쩍 — 벤치 33.83(끝 창업자 얼굴 컷 첫 프레임)",
     "cuts": [C(CLIP, 415.29, 416.56, ours="투자자가 바로 받아침(말하는 본인, 샷 415.27~416.57)"),
              C(CLIP, 416.59, 418.10, ours="창업자 정면 근접 — 말없이 생각하는 얼굴(벤치 끝 34.0~34.7 같은 샷)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/9편_PNuffCrunch/work/render/render_info.json")


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


HOOK: dict = {}


def hook():
    """0초 원·첫 컷 크롭 — 판단 주인 fx_place.hook_circle(얼굴 검출) 결과 그대로."""
    if not HOOK:
        from tools.calcopy.shark.fx_place import hook_circle
        a, b = LINES[0]["audio"]
        HOOK.update(hook_circle(SRC / FILES[CLIP][0], a, b - a))
    return HOOK


def build():
    shots, t = [], 0.0
    for L in LINES:
        d = line_dur(L)
        cut_total = sum(c[2] - c[1] for c in L["cuts"])
        scale = d / cut_total if L["kind"] == "나레" else 1.0
        for c in L["cuts"]:
            vid, a, b, cr, ours = c
            if cr is None:
                cr = hook()["src_crop"]
            dur = round((b - a) * scale, 3)
            f, ss = src_of(vid, a)
            au = {"mute": True} if L["kind"] == "나레" else {"mute": False, "audio_src": AUDIO, "audio_ss": a, "audio_dur": dur}
            shots.append({"i": len(shots), "line": L["id"], "kind": L["kind"], "src": f, **au,
                          "url": f"https://www.youtube.com/watch?v={vid}", "src_orig_span": [a, round(a + dur, 3)], "ss": ss,
                          "dur": dur, "t_final_est": [round(t, 2), round(t + dur, 2)], "res": "%dx%d" % FILES[vid][2],
                          "src_crop": cr, "scale": round(WIN[1] / cr[3], 3), "ours": ours,
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
    d.text((8, 8), f"샥탬스토리 9편 P-Nuff Crunch — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
    for k, s in enumerate(shots):
        y0 = 40 + k * rowh
        L = byline[s["line"]]
        d.text((6, y0 + 4), f"#{s['i']}", fill=(200, 0, 0), font=font)
        d.text((6, y0 + 24), s["line"], fill=(0, 0, 0), font=small)
        for j, frac in enumerate((0.05, 0.5, 0.95)):
            im = frame(str(SRC / s["src"]), s["ss"] + s["dur"] * frac, s["src_crop"])
            if k == 0 and HOOK:      # 0초 원 자리(완성본 좌표 → 시트 축소)
                cx, cy = HOOK["at"]; r = HOOK["size"] / 2
                sx, sy = 270 / WIN[0], 263 / WIN[1]
                ImageDraw.Draw(im).ellipse([(cx - r) * sx, (cy - 434 - r) * sy, (cx + r) * sx, (cy - 434 + r) * sy], outline=(250, 41, 44), width=3)
            S.paste(im, (60 + j * cw, y0))
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
            "원음_초": round(sum(line_dur(L) for L in LINES if L["kind"] == "원음"), 2),
            "확대_최대": max(s["scale"] for s in shots)}


TITLES = {"line1": "보디빌더 박사의", "line2": "땅콩 과자 사? 말아?"}


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
        "topic": "P-Nuff Crunch(식물성 단백질 땅콩 퍼프 과자) — 식품과학 박사·보디빌더 출신 창업자가 30만 달러/10% 요청 → 한 봉지를 다 먹었다는 투자자가 30만 달러/25% 제안, '1억 달러 브랜드' 공방(벤치는 여기서 끝)",
        "bench": {"id": "MIlHlQ1Wdg4", "channel": "해외쇼츠 @foreignshowshow", "title": "살 안찌는 땅콩 과자 (화면 제목: 살 안찌는 땅콩과자 / 산다 vs 안산다)",
                  "dur": 34.8, "views": 340870, "window": [0, 434, 1080, 1052],
                  "flow_bench": {"id": "sVsPbjTr55Y", "channel": "BIG BAG HUSTLE", "title": "No One Negotiates Like Mark Cuban", "dur": 55.4, "views": 36044675}},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 2.2~4.0 남(인플루언서·먹방)이 과자 먹는 컷 — P-Nuff 와 무관한 남의 영상 → 판매사 길거리 시식 컷(vr3dPT0wnrY)으로 바꿈",
            "벤치 6.9~8.3 투자자가 과자 먹는 컷(원음 줄 밑, 원본 시각 아님) → 원음 줄 화면은 원본 시각(봉지 그래픽·그릇)으로",
            "벤치 8.3 초록 옷 투자자 '음~'(0.4초) — 짧아 뺌",
            "벤치 18~19.4 AI 근육 남자 그림 — 근거·출처 없는 그림 → 판매사 광고 퍼프 근접으로",
            "벤치 21.8 'I ate the whole freaking bag' 두 번째(0초와 같은 원본 순간 재사용) — B13 재사용 → 뺌",
            "벤치 나레 '살이 찌지 않는다' — 원본에 근거 없음(투자자 '130 calories'·'gluten-free'만) → '130칼로리밖에 안 된다는데'",
            "BBH 뒤 20초(15% 역제안 → 40만 달러/25% 성사, 원본 431~488초) — 줄 단위 벤치(해외쇼츠)가 안 다룸 → 넣지 않음(페이블께 물음)"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?' — 벤치 '살 안찌는 땅콩과자 / 산다 vs 안산다'와 3어절 연속 겹침 0, 줄당 ≤12자(rules title.line_chars_max)"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 384.64~386.68 'I ate the whole freaking bag.'(구간 단독 2모델 asr/span_v1 + 로컬 whisper small 낱말 시각) · 화면 샷 384.40~386.84 봉지 든 투자자", "url": U + CLIP, "kind": "방송 원음"},
    "f2": {"text": "원본 46.88~50.14 창업자 'It's not only delicious, but it's also healthy and nutritious.'(whisper·30초 창 2모델) — 창업자 주장 → 전언체", "url": U + CLIP, "kind": "방송 원음(창업자 주장)"},
    "f3": {"text": "원본 43.12~46.52 'It's the first nutrition-based crunchy peanut puff snack.'(span_v1 2모델 일치) · 화면 43.77~46.27 봉지 그래픽", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f4": {"text": "원본 21.20~23.48 'I'm a PhD in food science'(whisper·30초 창 2모델 'I have a PhD in food science') · 58.20~60.82 'I'm also a former competitor bodybuilder'(whisper·2모델) · 35.22~38.94 'I decided to make something better' · 화면 60.0~62.9 가운을 엶", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f5": {"text": "원본 83.18~85.84 'But they're also good for building muscle'(span_v1 2모델) · 85.84~86.80 'Cut it out!'(2모델) · 87.04~87.80 'I'm staying fit'(whisper)/'and staying fit'(30초 창 2모델)/'Stay fit'·'And stay in fit'(단독 v3 2모델) / 'Stay fair'·'And stay in bed'(단독 v1) — 'stay·fit' 4/6 △ · 88.1~88.9 'Oh! Oh!'(30초 창·v1 3.5-flash, v3 3-flash 는 헛들림)", "url": U + CLIP, "kind": "방송 원음"},
    "f6": {"text": "원본 73.36~76.06 창업자 'It's made from high-quality, plant-based protein' · 381.80~384.06 투자자 'Gluten-free, 130 calories'(봉지를 읽음) · 162.87~168.25 투자자 'Calories aren't bad, 130 calories' · 49~52초 방송 그래픽 'Gluten-Free'·'Complete Plant Protein'(whisper·30초 창 2모델)", "url": U + CLIP, "kind": "방송 원음+그래픽"},
    "f7": {"text": "원본 376.48~378.62 'And these things are in the pantry.'(span_v1 2모델) · 393.00~393.60 'I wanted more.'(2모델) — 투자자가 집에서 아내가 사 둔 과자를 먹은 이야기(372.9~393.6)", "url": U + CLIP, "kind": "방송 원음"},
    "f8": {"text": "원본 397.30~400.12 'So I'll give you the 300K. I want 25%.'(span_v1 2모델 일치) · 401.12~401.48 'Woo!'(2모델) · 403.10~404.34 'I'm going to change your life.'(span_v3 2모델 + whisper + BBH 쇼츠 유튜브 자막 일치) · 앞 97.80~102.42 창업자 요청 '$300,000 for 10% equity'", "url": U + CLIP, "kind": "방송 원음"},
    "f9": {"text": "원본 411.56~414.76 'I know you know this is going to be $100 million brand in five, six years.'(whisper + BBH 유튜브 자막) · 415.32~416.20 'But not just with you.'(whisper + BBH 자막) (span_v3 2모델 'I know, you know, this is gonna be a hundred million dollar brand…' / 'Not just with you'·'Now just with you')", "url": U + CLIP, "kind": "방송 원음"},
}


def main():
    hook()
    shots, total = build()
    mat = {"_note": "샥탬스토리 9편 P-Nuff Crunch 재료 계획 — TTS·렌더 전. 창 1080x1052(벤치 MIlHlQ1Wdg4 창 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물). 원음 컷은 src_orig_span 그대로 원본 소리(영어 원음 트랙 wp45o5i7zhE_audio.m4a = 140-5 original).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Mark Makes P-Nuff Crunch An Amazing Offer!",
                      "해상도": "1280x720 29.97fps (136 = 최대 화질, 1080p 없음 — -F 실측 src/wp45_formats.txt) + 140-5 영어 원음(더빙 de·es·fr·hi·pt 트랙 따로 있음)",
                      "길이": 549.5, "받은 구간": "전체", "남의 글자": "방송 로고·띠 없음(시트 눈 확인). 49~52초 성분 그래픽 글자 — 안 씀. 43.8~46.3 봉지 그래픽 글자 = 제품 포장"},
               VR: {"채널": "Pnuff Crunch(판매사 공식 채널 UCrkkoW3thYojWWEMNIbjTiw)", "제목": "Fans All Over Love Pnuff!", "업로드": "2025-03-23",
                    "해상도": "1080x1920 (세로 쇼츠)", "길이": 40.3, "남의 글자": "0~2.6초 위·아래 두 칸 화면 — 위 칸(y 0~960)만 씀. 영어 자막 y≈1490~1520(0~1.1·20~23초) — 크롭으로 뺌. 24.5~27.5 는 자막이 y≈1020 이라 안 씀"},
               IO: {"채널": "Pnuff Crunch(판매사 공식)", "제목": "Snack Smart with Pnuff", "업로드": "2025-03-19",
                    "해상도": "1080x1920 (세로 쇼츠)", "길이": 41.0, "남의 글자": "30.7~31.2 아래 자막 'and nutritious ingredients' y≈1500 — 크롭 y 250~1302 로 뺌"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": TITLES, "shots": shots, "cand_dir": str(SRC).replace("\\", "/")}
    H = hook()
    mat["effects"] = [
        {"line": "O1", "kind": "red_circle", "at": H["at"], "size": H["size"], "t": [0.0, round(LINES[0]["audio"][1] - LINES[0]["audio"][0], 2)], "how": "face",
         "fh_win": H["fh_win"], "why": "벤치 0.0~2.2 빨간 실선 원 = 같은 투자자 얼굴(첫 컷 내내 고정). " + H["why"]},
        {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.73, 1.18], "color": "노랑", "how": "auto", "why": "벤치 5.17 노랑 번쩍(봉지 그래픽 첫 프레임) — 원본 봉지 컷 43.78 = 줄 안 0.73"},
        {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "노랑", "how": "auto", "why": "벤치 8.70 노랑 번쩍(창업자 가운 여는 컷 첫 프레임)"},
        {"line": "O4", "kind": "flash", "at": [540, 960], "t": [3.79, 4.24], "color": "초록", "how": "auto", "why": "벤치 14.77 초록 번쩍(초록 옷 투자자 반응 컷 첫 프레임) — 원본 86.89 = 줄 안 3.79"},
        {"line": "O7", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 24.90 초록 번쩍('투자할게' 첫 프레임)"},
        {"line": "O7", "kind": "flash", "at": [540, 960], "t": [1.63, 2.08], "color": "빨강", "how": "auto", "why": "벤치 27.00 빨강 번쩍('25%' 확대 컷) — 원본 398.88 = 줄 안 1.63"},
        {"line": "O11", "kind": "flash", "at": [540, 960], "t": [1.30, 1.75], "color": "빨강", "how": "auto", "why": "벤치 33.83 빨강 번쩍(끝 창업자 얼굴 컷) — 원본 416.59 = 줄 안 1.30"}]
    doc_update()
    (HERE / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--no-sheet" not in sys.argv:
        (HERE / "plan").mkdir(exist_ok=True)
        sheet(shots, HERE / "plan" / "계획_시트.jpg", " / ".join(TITLES.values()))
    c = check(shots, total)
    print(json.dumps(c, ensure_ascii=False))
    for x in shots:
        print(x["i"], x["line"], x["kind"], x["src"], x["src_orig_span"], x["dur"], x["t_final_est"], x["src_crop"], x["scale"], file=sys.stderr)
    return shots, c


if __name__ == "__main__":
    main()
