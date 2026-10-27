# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""샥탬스토리 21편 Snactiv — 벤치 해외쇼츠 jo1QTw7GCWs(「이제 게임하면서 / 과자 먹을수 있다고?!」 8.3만, 46.3초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/21편_Snactiv/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(18편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Shark Tank Global 공식 'Kevin Vs Kevin In A Deal For Snactiv | Shark Tank US' nlVhx46TQFg, 1080p, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/21편_Snactiv/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt.
★원본 이름·요청·제안 띠(126~134·287~292·324~334·356~359·384~389·402초)는 안 쓰는 구간. 쓰는 컷은 띠 없음 → 크롭 높이 1080.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '약 2억 7천만원'·'연간 57억'(금액)과 원본 밖 화면(남의 광고·리뷰 영상)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/21편_Snactiv/src")
CLIP = "nlVhx46TQFg"
FILES = {CLIP: ("nlVhx46TQFg.mp4", 0.0, (1920, 1080))}
AUDIO = "nlVhx46TQFg_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Shark Tank Global 원본: 고정 로고 없음 · 이름/요청/제안 띠(126~134·287~292·324~334·356~359·384~389·402초)는 안 쓰는 구간 · 489초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (174.98, 176.38), "en": "You might be my next husband.",
     "sub": ["너 내 다음 남편감이야!"], "facts": ["f1"], "cap_at": [174.98], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 진열대 가운데 빨간 스낵티브 상자) — 벤치 0~1.0 투자자 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 104.25, 105.65, 960, ours="진열대 위 스낵티브 상자 세 개 — 가운데 빨간 스낵티브 상자(원본 샷 104.20~105.77, 사람 없음 · 소리 = 투자자 원음 'You might be my next husband.' cover, 말한 사람은 화면 밖 · 107초 노트북 컷은 물건이 입으로 가 얼굴 겹침 거절)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "과자 먹다가 기름 묻은 손으로 키보드를 만지면 다들 찝찝하다는데",
     "tts": "과자 먹다가, 기름 묻은 손으로 키보드를 만지면, 다들 찝찝하다는데",
     "sub": ["과자 먹다가", "기름 묻은 손으로", "키보드를 만지면", "다들 찝찝하다는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 4.5('게임하면서 과자를 먹고 싶은데')",
     "cuts": [C(CLIP, 32.20, 34.80, ours="노트북 앞에서 맨손으로 과자를 집어 먹는 창업자(원본 샷 31.60~36.10, 소리 끔)"),
              C(CLIP, 38.40, 40.90, ours="과자 묻은 손으로 노트북을 만지는 창업자(샷 37.80~42.44, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "문제(반응)", "audio": (46.76, 48.64), "en": "Oh, it's disgusting man.",
     "sub": ["으, 진짜 더럽다"], "facts": ["f2"], "cap_at": [46.76],
     "cuts": [C(CLIP, 46.76, 47.88, ours="동료 창업자가 과자 묻은 손을 보고 질색(원본 샷 44.04~47.91, 말하는 본인)"),
              C(CLIP, 47.94, 48.64, ours="두 창업자 — 이어서 말함(샷 47.91~48.82, 말하는 본인)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "그래서 소품 만들던 사람이 손가락에 끼우는 젓가락을 만들어 버렸다는데",
     "tts": "그래서 소품 만들던 사람이, 손가락에 끼우는 젓가락을 만들어 버렸다는데",
     "sub": ["그래서 소품 만들던 사람이", "손가락에 끼우는", "젓가락을", "만들어 버렸다는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 8.0('이걸 중지와 약지 사이에')",
     "cuts": [C(CLIP, 89.55, 91.80, ours="두 창업자가 손가락에 낀 스낵티브를 들어 보임(원본 샷 89.46~91.86, 소리 끔)"),
              C(CLIP, 92.00, 93.70, 800, ours="손가락에 낀 흰·검정 스낵티브 근접(샷 91.86~93.76, 얼굴은 크롭 밖, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "시연(끼우기)", "audio": (105.57, 110.61), "en": "It installs between your pointer and middle finger and keeps your hands completely mobile and free.",
     "sub": ["검지랑 중지 사이에 끼우면", "손이 완전히 자유로워져요"], "facts": ["f4"], "cap_at": [105.57, 108.01],
     "fx": "초록 번쩍 — 벤치 10.5('완벽하게 자유로워 집니다')",
     "cuts": [C(CLIP, 113.15, 116.80, cover=True, ours="스낵티브 낀 채 과자를 먹고 노트북을 치는 창업자(원본 샷 113.08~116.88 — 소리 = 다른 창업자 원음 cover, 같은 시연)"),
              C(CLIP, 118.20, 119.59, cover=True, ours="스낵티브로 과자를 집는 창업자(샷 118.18~120.29, 소리 = 이 줄 원음 이어서)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(차별점)", "text": "끼운 채로 타자도 치고 폰도 만지면서 과자를 바로 집어 먹는다는데",
     "tts": "끼운 채로 타자도 치고 폰도 만지면서, 과자를 바로 집어 먹는다는데",
     "sub": ["끼운 채로 타자도 치고", "폰도 만지면서", "과자를 바로 집어 먹는다는데"], "facts": ["f5"],
     "fx": "초록 번쩍 — 벤치 13.0 '이걸 끼고서도'",
     "cuts": [C(CLIP, 98.00, 99.40, ours="무대 탁자에서 스낵티브를 시연하는 두 창업자(원본 샷 97.86~101.53, 소리 끔)"),
              C(CLIP, 23.05, 25.50, ours="무대에 선 두 창업자(샷 22.99~27.36, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "반응(투자자 체험)", "audio": (145.50, 147.02), "en": "Pick up your snack like instantly.",
     "sub": ["과자가 바로 집히네"], "facts": ["f5"], "cap_at": [145.50],
     "cuts": [C(CLIP, 144.10, 145.62, 880, cover=True, ours="투자자가 스낵티브로 과자를 집음 — 손 근접(원본 샷 144.08~146.65, 말하는 본인 손 · 소리 = 이 줄 원음)")]},
    {"id": "O5", "kind": "원음", "beat": "반응(투자자)", "audio": (147.02, 148.00), "en": "I just got happy.",
     "sub": ["나 방금 행복해졌어"], "facts": ["f5"], "cap_at": [147.02],
     "cuts": [C(CLIP, 147.02, 148.00, ours="게스트 샤크가 웃으며 말함(원본 샷 146.65~148.01, 말하는 본인)")]},
    {"id": "N4", "kind": "나레", "beat": "잉?(한국)", "text": "심지어 한국에도 벌써 판매처가 있다고 해서 샤크들도 놀랐는데",
     "tts": "심지어 한국에도 벌써 판매처가 있다고 해서, 샤크들도 놀랐는데",
     "sub": ["심지어 한국에도", "벌써 판매처가 있다고 해서", "샤크들도 놀랐는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 241.00, 244.00, ours="해외 판매 계획을 말하는 창업자(원본 샷 240.94~246.05, 소리 끔)"),
              C(CLIP, 246.10, 247.50, ours="투자자석 — 듣는 투자자(샷 246.05~247.58, 소리 끔)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁", "text": "결국 샤크 두 명이 반반 나눠서 같이 하자고 나섰는데",
     "tts": "결국 샤크 두 명이, 반반 나눠서 같이 하자고 나섰는데",
     "sub": ["결국 샤크 두 명이", "반반 나눠서", "같이 하자고 나섰는데"], "facts": ["f8"],
     "fx": "빨강 번쩍 — 벤치 지분 경쟁",
     "cuts": [C(CLIP, 339.35, 342.90, ours="게스트 샤크가 제안을 말함(원본 샷 339.31~342.94, 소리 끔)"),
              C(CLIP, 367.15, 368.95, ours="로리가 말함(샷 367.10~369.00 — 359.9 샷은 제안 띠라 뺌, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(성사)", "audio": (412.45, 413.33), "en": "We'll take your deal.",
     "sub": ["그 제안 받을게요!"], "facts": ["f8"], "cap_at": [412.45],
     "fx": "초록 번쩍 — 벤치 42.0 '거래할게요'",
     "cuts": [C(CLIP, 412.45, 413.33, ours="두 창업자가 제안을 받음(원본 샷 411.41~413.55, 말하는 본인)")]},
    {"id": "O7", "kind": "원음", "beat": "결정(반응)", "audio": (485.05, 486.25), "en": "We're going to blow this up.",
     "sub": ["우리 이거 제대로 터뜨려 보자"], "facts": ["f8"], "cap_at": [485.05],
     "cuts": [C(CLIP, 485.05, 486.25, ours="로리가 웃으며 말함(원본 샷 483.68~486.72, 말하는 본인)")]},
    {"id": "N6", "kind": "나레", "beat": "끝(결과)", "text": "기름 묻은 손가락 때문에 만든 젓가락이 샤크 두 명을 잡았다는데",
     "tts": "기름 묻은 손가락 때문에 만든 젓가락이, 샤크 두 명을 잡았다는데",
     "sub": ["기름 묻은 손가락 때문에", "만든 젓가락이", "샤크 두 명을 잡았다는데"], "facts": ["f8"],
     "cuts": [C(CLIP, 441.00, 444.00, ours="무대 뒤에서 기뻐하는 두 창업자(원본 샷 440.61~447.98, 소리 끔)"),
              C(CLIP, 448.25, 450.50, ours="무대 뒤 인터뷰하는 두 창업자(샷 448.21~457.12, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/21편_Snactiv/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 21편 Snactiv — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "손가락에 끼우는", "line2": "젓가락이 있다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 174.98~176.38 'You might be my next husband.'(스피치매틱스 enhanced 영어 — 투자자 원음, 화자 이름은 자막에 안 씀) · 화면은 같은 원본 104.25초 진열대 스낵티브 상자(cover)", "url": U + CLIP + "&t=174s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 74.21~82.01 'I love to enjoy a snack while I'm gaming or working, but keeping your hands and devices clean all at the same time is a challenge.' · 166.26~174.66 'I found myself licking my fingers… I was touching my mouse, my keyboard. It was disgusting.' · 46.76~48.64 'Oh, it's disgusting man.' · 화면 31~48 콩트", "url": U + CLIP + "&t=74s", "kind": "방송 원음+화면"},
    "f3": {"text": "원본 51.56~54.08 'As a prop maker, I became my own problem solver.' · 56.28~59.76 'created a snacking tool of the future' · 105.57~110.61 손가락 사이에 끼움", "url": U + CLIP + "&t=51s", "kind": "방송 원음"},
    "f4": {"text": "원본 105.57~110.61 'It installs between your pointer and middle finger and keeps your hands completely mobile and free.' · 화면 89~120 시연", "url": U + CLIP + "&t=105s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 96.29~104.97 'keeps your hands and devices clean while you're working gaming, typing, texting, or swiping' · 139.94~147.02 투자자 체험 'Pick up your snack like instantly.' · 147.02~148.10 'I just got happy.'", "url": U + CLIP + "&t=96s", "kind": "방송 원음+화면"},
    "f7": {"text": "원본 233.10~247.66 'We have plans for retail… we actually put in place an international dealer in Korea. We put in Taiwan and we're working with a Hong Kong distributor.' · 247.74 'World domination.'", "url": U + CLIP + "&t=233s", "kind": "방송 원음"},
    "f8": {"text": "원본 266.99~283.29 케빈 오리어리 로열티 제안 · 351.04~360.72 게스트 샤크 '200K and we just want 20%… for two of us… we'll go ten and ten'(로리 'Ten and ten') · 412.45~413.97 창업자 'We'll take your deal.' · 483.33~486.25 로리 'I am happy to be your partner. We're going to blow this up.' — 금액은 대본에 안 씀", "url": U + CLIP + "&t=351s", "kind": "방송 원음+화면"},
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
        "topic": "Snactiv(스낵티브) — 검지·중지 사이에 끼워 과자를 집는 손가락 젓가락. 소품 만들던 창업자가 기름 묻은 손으로 키보드 만지는 게 싫어 만듦, 한국에 이미 판매처 → 게스트 샤크·로리 반반 제안 → 성사",
        "product": "Snactiv finger chopsticks(스낵티브 손가락 젓가락)",
        "bench": {"id": "jo1QTw7GCWs", "channel": "해외쇼츠 @foreignshowshow", "title": "이제 게임하면서 과자 먹을수 있다고?! (화면 제목: 이제 게임하면서 / 과자 먹을수 있다고?!)",
                  "dur": 46.324, "views": 83000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "0.5초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '약 2억 7천만원에 지분 20%'·'연간 57억'(금액) → 금액 없이 반반 제안·결정만",
            "벤치 4~16초 남의 광고·리뷰 영상(게임 화면·초록 화면) — 이 원본 밖 → 원본 안 시연으로",
            "벤치 0초 투자자 얼굴 원 → R3 물건 원(진열대 스낵티브 상자)"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '이제 게임하면서 / 과자 먹을수 있다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [376, 535, 619, 1106], "target_what": "진열대 가운데 빨간 스낵티브 상자 — 104.4초 원본 프레임 눈 측정(창 크롭 [406,0,1108,1080] 안 x 386~636·y 104~690, ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 4.5 '게임하면서 과자를 먹고 싶은데'"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 8.0 '이걸 중지와 약지 사이에'"},
    {"line": "O3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 10.5 '완벽하게 자유로워 집니다'"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 13.0 '이걸 끼고서도'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 지분 경쟁"},
    {"line": "O6", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 42.0 '거래할게요'"},
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
    mat = {"_note": "샥탬스토리 21편 Snactiv 재료 계획. 창 1080x1052(벤치 jo1QTw7GCWs, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(nlVhx46TQFg_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global(공식)", "제목": "Kevin Vs Kevin In A Deal For Snactiv | Shark Tank US | Shark Tank Global", "해상도": "1920x1080 29.97fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 519.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(126~134·287~292·324~334·356~359·384~389·402초) 안 씀 · 489초 뒤 끝 화면 안 씀 · 티셔츠·상자 'SNACTIV' = 제품 브랜드"}},
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
