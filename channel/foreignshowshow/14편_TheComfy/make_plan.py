# -*- coding: utf-8 -*-
"""샥탬스토리 14편 The Comfy — 벤치 해외쇼츠 D6H6sj3pap4(「방송 나오고 0원에서 / 7800억 팔린 담요?!」 420만, 61.2초) 줄 단위 칼카피 (관제 097, 2026-10-27).

    PYTHONUTF8=1 py channel/foreignshowshow/14편_TheComfy/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(13편 make_plan 꼴).
원음 줄 = 벤치가 쓴 원음 순간을 같은 원본(Shark Tank Global 공식 IK_JDKOLP8g, 1080p, 영어 원음 한 트랙)에서.
받아쓰기 = 스피치매틱스 enhanced 영어(C:/숏템_칼카피/foreignshowshow/14편_TheComfy/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes.txt.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝(약 15초)에서 자른다. 벤치 뒤쪽 '방송 후 매출 7800억'(출처 없는 금액)·QVC 화면은 쓰지 않고 거래 성사까지만(벤치 61.2초 → 우리 약 41초, 앞 check B1 은 짧음으로 뜬다 — 뒤 하이브리드가 그 자리를 대신함).
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/14편_TheComfy/src")
CLIP, ISF = "IK_JDKOLP8g", "ISf6BtA7kXk"
FILES = {CLIP: ("IK_JDKOLP8g.mp4", 0.0, (1920, 1080)), ISF: ("ISf6BtA7kXk.mp4", 0.0, (1920, 1080))}
AUDIO = "IK_JDKOLP8g_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# 이름·제안 띠(16~20·22~24·442~448·589·604~610·634초 아래쪽 파란 띠) 시각은 안 쓴다. 로고 없음.
H_DEF = {CLIP: 1080, ISF: 1080}
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (93.27, 94.29), "en": "Oh my God.",
     "sub": ["어머 세상에!"], "facts": ["f1"], "cap_at": [93.27], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 창업자 티셔츠의 the original Comfy 로고) — 벤치 0~1.4 빨간 실선 원(웃는 투자자 얼굴, 우리는 물건)",
     "cuts": [C(CLIP, 37.90, 38.54, 1054, ours="무대: 창업자 가슴의 'the original Comfy' 로고 티셔츠(원본 샷 33.37~42.78, 소리 = 다음 컷 투자자 'Oh my God' cover · R3 원 후보 바닷가 홍보 영상·검은 컴피 투자자·제품 근접 로고는 얼굴 겹침·추적 신뢰·크기로 거절)", cover=True),
              C(CLIP, 93.92, 94.29, ours="정장 투자자가 크게 웃으며 'Oh my God'(말하는 본인, 샷 93.89~95.70) — 벤치 0초 같은 투자자")]},
    {"id": "N1", "kind": "나레", "beat": "문제(첫 반응)", "text": "투자자 대부분이 시큰둥했던 이 입는 담요",
     "tts": "투자자 대부분이 시큰둥했던 이 입는 담요",
     "sub": ["투자자 대부분이", "시큰둥했던", "이 입는 담요"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 1.5(담요 컷)",
     "cuts": [C(CLIP, 94.33, 95.66, ours="같은 투자자가 계속 웃음(앞 컷 이어서, 소리 끔)"),
              C(CLIP, 46.10, 47.90, 1300, ours="무대: 창업자가 회색 컴피를 머리부터 뒤집어씀(원본 샷 46.05~47.98)")]},
    {"id": "O2", "kind": "원음", "beat": "문제(혹평)", "audio": (379.36, 382.40), "en": "(This) is not unique enough. I'm sorry. I'm out.",
     "sub": ["이건 특별할 게 없어요", "미안하지만 전 빠질게요"], "facts": ["f3"], "cap_at": [379.36, 380.81],
     "cuts": [C(CLIP, 379.36, 382.40, ours="금발 투자자가 '특별하지 않다, 빠지겠다'(말하는 본인, 샷 379.35~382.58)")]},
    {"id": "N2", "kind": "나레", "beat": "반전 예고", "text": "근데 이게 몇 년 뒤 바바라의 역대 최고 투자가 됐다는데",
     "tts": "근데 이게 몇 년 뒤 바바라의 역대 최고 투자가 됐다는데",
     "sub": ["근데 이게 몇 년 뒤", "바바라의", "역대 최고 투자가 됐다는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 6.0(반전 컷)",
     "cuts": [C(CLIP, 69.55, 71.50, ours="흰 옷 투자자(바바라 — 원음 '바바라' 호명·이름 띠로 확인)가 손뼉 치며 웃음(원본 샷 69.50~71.57, 소리 끔)"),
              C(CLIP, 86.90, 88.40, 960, ours="투자자석 와이드(원본 샷 86.85~88.42, 바바라 포함 — 앞 판의 흰 로고 화면은 자막 '바바라의'가 흰 글자 위에 겹쳐 안 읽혀 바꿈)")]},
    {"id": "O3", "kind": "원음", "beat": "문제(창업자)", "audio": (74.39, 78.99), "en": "It's cold outside. It's nasty. All you want is to be warm and cozy,",
     "sub": ["밖은 춥고", "궂은 날씨잖아요", "그저 따뜻하고 포근하고 싶죠"], "facts": ["f5"], "cap_at": [74.39, 75.27, 76.23],
     "cuts": [C(CLIP, 74.39, 78.99, 1300, ours="검은 셔츠 창업자가 손짓하며 설명(말하는 본인, 왼쪽 가장자리에 회색 컴피 모자를 쓴 형제 — 샷 71.57~79.38)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(소재)", "text": "겉은 극세사, 안은 양털 같은 셰르파로 만든 입는 담요라",
     "tts": "겉은 극세사, 안은 양털 같은 셰르파로 만든 입는 담요라",
     "sub": ["겉은 극세사", "안은 양털 같은 셰르파로", "만든 입는 담요라"], "facts": ["f6"],
     "fx": "초록 번쩍 — 벤치 18.0(소재 컷)",
     "cuts": [C(CLIP, 114.30, 116.38, 960, ours="회색 컴피 겉감·안감 근접(원본 샷 114.25~116.42)"),
              C(CLIP, 118.75, 120.22, 960, ours="큰 앞주머니에 손을 넣어 보임(근접, 샷 118.72~120.25)")]},
    {"id": "O4", "kind": "원음", "beat": "해답(반전 기능)", "audio": (147.34, 153.22), "en": "But the comfy, sharks, is also, wait for it… reversible,",
     "sub": ["게다가 이 컴피는", "자, 기다려 보세요", "뒤집어 입을 수도 있어요"], "facts": ["f6"], "cap_at": [147.34, 149.50, 151.54],
     "fx": "빨강 번쩍 — 벤치 26.0('뒤집어 입을 수도')",
     "cuts": [C(CLIP, 147.34, 149.45, 1300, ours="무대: 창업자가 컴피를 벗어 들고 말함(말하는 본인)"),
              C(CLIP, 149.52, 153.22, 800, ours="창업자가 흰색 면이 나오게 뒤집어 입음(샷 149.48~153.29)")]},
    {"id": "N4", "kind": "나레", "beat": "시연(투자자 체험)", "text": "샤크들도 직접 입고 소파에 눕더니 하나같이 포근하다며 웃었는데",
     "tts": "샤크들도 직접 입고 소파에 눕더니 하나같이 포근하다며 웃었는데",
     "sub": ["샤크들도 직접 입고", "소파에 눕더니", "하나같이 포근하다며 웃었는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 211.80, 214.70, 900, ours="투자자들이 컴피를 입고 무대 소파에 앉음"),
              C(CLIP, 225.00, 227.50, 900, ours="소파에 누운 투자자들(컴피 입음)")]},
    {"id": "O5", "kind": "원음", "beat": "문제(판매 없음)", "audio": (244.00, 248.32), "en": "So have you sold any, or is this a brand new invention? / Brand new.",
     "sub": ["팔아 본 적은 있어요?", "완전 새 발명품이에요?", "완전 새거예요"], "facts": ["f8"], "cap_at": [244.00, 245.56, 247.64],
     "cuts": [C(CLIP, 244.00, 245.45, ours="투자자가 묻는 중(원본 샷 241.17~245.48)"),
              C(CLIP, 245.50, 247.40, ours="원본 다음 샷(245.48~247.41)"),
              C(CLIP, 247.45, 248.32, ours="창업자 형제 'Brand new'(말하는 본인, 샷 247.41~250.12)")]},
    {"id": "O6", "kind": "원음", "beat": "문제(판매 없음 반응)", "audio": (252.48, 253.64), "en": "You have no sales, no sales yet.",
     "sub": ["판매가 아예 없다고요?"], "facts": ["f8"], "cap_at": [252.48],
     "fx": "빨강 번쩍 — 벤치 30.5('판매가 아예 없다고?')",
     "cuts": [C(CLIP, 252.48, 253.64, ours="투자자 반문(원본 샷 251.85~253.65 — 'yet' 꼬리는 샷 경계에서 끊음)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁", "text": "결국 바바라가 지분 30%를 부르며 손을 내밀었는데",
     "tts": "결국 바바라가 지분 삼십 퍼센트를 부르며 손을 내밀었는데",
     "sub": ["결국 바바라가", "지분 30%를 부르며", "손을 내밀었는데"], "facts": ["f9"],
     "fx": "초록 번쩍 — 벤치 45.0(지분 컷)",
     "cuts": [C(CLIP, 571.10, 574.60, ours="흰 옷 투자자(바바라)가 손짓하며 말함(원본 샷 570.94~574.67, 소리 끔)"),
              C(CLIP, 582.90, 584.33, ours="창업자 형제가 웃으며 듣는 모습(샷 582.85~584.38)")]},
    {"id": "O7", "kind": "원음", "beat": "결정(성사)", "audio": (640.41, 645.16), "en": "Barbara, you have a deal. / Okie dokie. / Let's get comfy together.",
     "sub": ["바바라,", "거래하죠!", "좋아요~", "같이 따뜻하게 가 봐요"], "facts": ["f9"], "cap_at": [640.41, 641.97, 642.93, 644.33],
     "fx": "초록 번쩍 — 벤치 끝 거래 성사",
     "cuts": [C(CLIP, 640.41, 640.75, ours="창업자 형제 'Barbara,'(말하는 본인, 샷 638.71~640.77)"),
              C(CLIP, 640.80, 641.86, ours="바바라(원본 반응 컷, 샷 640.77~641.88)"),
              C(CLIP, 641.90, 643.06, ours="창업자 'you have a deal'(말하는 본인, 샷 641.88~643.08)"),
              C(CLIP, 643.10, 644.02, ours="바바라 'Okie dokie'(말하는 본인, 샷 643.08~644.04)"),
              C(CLIP, 644.06, 645.16, ours="무대 와이드 — 창업자가 바바라에게 걸어감(샷 644.04~645.18)")]},
    {"id": "N6", "kind": "나레", "beat": "끝(결과)", "text": "다들 혹평하던 그 담요가 그렇게 투자를 따냈다는데",
     "tts": "다들 혹평하던 그 담요가 그렇게 투자를 따냈다는데",
     "sub": ["다들 혹평하던", "그 담요가", "그렇게 투자를 따냈다는데"], "facts": ["f9"],
     "cuts": [C(CLIP, 645.20, 647.05, ours="창업자 형제가 서로 끌어안고 웃음(원본 샷 645.18~647.08, 소리 끔)"),
              C(CLIP, 649.10, 651.00, ours="바바라가 창업자와 포옹(원본 샷, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/14편_TheComfy/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 14편 The Comfy — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "샤크들이 비웃은", "line2": "입는 담요의 반전?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 93.27~94.27 'Oh my God.'(스피치매틱스 enhanced 영어) — 홍보 영상(바닷가·자동차·아이) 상영 중 투자자 반응. 화면 93.89~95.70 정장 투자자 웃음", "url": U + CLIP, "kind": "방송 원음"},
    "f2": {"text": "원본 353~382 금발 투자자 '…the big elephant in the room… Snuggie… This is not unique enough. I'm out.' · 409~428 'I think you have a lot of work to do… I'm out' · 620 'I'm out' — 다섯 명 중 셋이 빠짐(시큰둥)", "url": U + CLIP, "kind": "방송 원음"},
    "f3": {"text": "원본 379.17~382.21 'This is not unique enough. I'm sorry. I'm out.'", "url": U + CLIP, "kind": "방송 원음"},
    "f4": {"text": "Yahoo Finance 'Barbara Corcoran Reveals Her Best Shark Tank Investment Has Made Her $468 Million So Far — And Nobody Wanted It'(2023 팟캐스트 본인 발언, https://finance.yahoo.com/news/barbara-corcoran-reveals-her-best-131202826.html) · CNBC 2020-03-16 'Barbara Corcoran invested in a company with no sales'(https://www.cnbc.com/2020/03/16/shark-tank-barbara-corcoran-invested-in-a-company-with-no-sales.html) — 대본엔 금액 안 씀('역대 최고 투자'만, 본인 발언 전언)", "url": "https://finance.yahoo.com/news/barbara-corcoran-reveals-her-best-131202826.html", "kind": "기사(본인 발언)"},
    "f5": {"text": "원본 71.55~79.59 'Imagine sharks… It's cold outside. It's nasty. All you want is to be warm and cozy, you know?'", "url": U + CLIP, "kind": "방송 원음"},
    "f6": {"text": "원본 109.83~115.83 'It's made of a soft microfiber on the outside and an even more luxurious Sherpa on the inside.' · 116.11~123.70 'The pocket is large enough…' · 147.34~153.22 '…the comfy sharks is also wait for it… reversible'", "url": U + CLIP, "kind": "방송 원음"},
    "f7": {"text": "원본 199~243 창업자 'We'd love if you guys would come up and try it on the couch' → 투자자들이 입고 소파에 앉음 · 217.17 'It's pretty comfy.' · 화면 210~229", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f8": {"text": "원본 244.00~248.32 'So have you sold any, or is this a brand new invention? / Brand new.' · 252.48~253.88 'You have no sales, no sales yet.'", "url": U + CLIP, "kind": "방송 원음"},
    "f9": {"text": "원본 584.22~585.82 바바라 'A 50 for 30%.' · 640.41~645.77 'Barbara, you have a deal. / Okie dokie. / Let's get comfy together.' · 화면 645~651 포옹 — '바바라' 이름은 원음 호명(575.46 'Barbara', 640.41)과 이름 띠", "url": U + CLIP, "kind": "방송 원음"},
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
        "topic": "The Comfy(입는 담요 — 겉 극세사·안 셰르파 후드 담요) — 판매 0 상태로 나온 스페셜 형제, 투자자 셋이 빠지고(스너기와 다를 게 없다) 바바라가 30%에 거래 → 바바라 본인이 꼽는 역대 최고 투자",
        "product": "The Comfy Original(더 컴피 오리지널)",
        "bench": {"id": "D6H6sj3pap4", "channel": "해외쇼츠 @foreignshowshow", "title": "방송 나오고 대박난 담요?! (화면 제목: 방송 나오고 0원에서 / 7800억 팔린 담요?!)",
                  "dur": 61.161, "views": 4200000, "window": [0, 434, 1080, 1052], "cut_median": 1.23, "_cut_median_how": "check.scene_cuts 같은 자 46조각 중앙 — 10-27 실측"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 제목·나레 '7800억'·'200억 매출' — 출처를 못 찾은 금액(바바라 본인 발언은 '내 몫 4억 6,800만 달러', 회사 매출과 다름) → 금액 없이 '바바라의 역대 최고 투자'(본인 발언 전언)",
            "벤치 7.5~8.5 QVC 홈쇼핑 화면·57.5~61 다른 채널 인터뷰 화면 — 방송 원본 밖 남의 영상 → 안 씀",
            "벤치 46~57 역제안(25%)·거절 대목 — 길이·하이브리드 자르는 자리 때문에 바바라 30% 제안 → 성사로 줄임",
            "벤치 끝 '방송 후 매출' 나레 — 하이브리드 뒤(쿠팡 체험)가 그 자리를 대신함"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '방송 나오고 0원에서 / 7800억 팔린 담요?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.64], "target": [588, 984, 825, 1134], "target_what": "창업자 티셔츠의 the original Comfy 로고(제품 상표) — 손 상자 = 37.9초 완성본 격자 sheet/sh.jpg 눈 측정",
     "why": "R3 0초 원 = 물건(제품) — 벤치 0~1.4 원은 웃는 투자자 얼굴이지만 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "O1", "kind": "flash", "at": [540, 960], "t": [0.64, 1.02], "color": "초록", "how": "auto", "why": "원 다음 얼굴 컷 첫 프레임(13편과 같은 꼴)"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 1.5 담요 컷"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 6.0 반전 컷"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 18.0 소재 컷"},
    {"line": "O4", "kind": "flash", "at": [540, 960], "t": [2.18, 2.63], "color": "빨강", "how": "auto", "why": "벤치 26.0 '뒤집어 입을 수도' — 원본 149.52 = 줄 안 2.18"},
    {"line": "O6", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 30.5 '판매가 아예 없다고?'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 45.0 지분 컷"},
    {"line": "O7", "kind": "flash", "at": [540, 960], "t": [1.49, 1.94], "color": "초록", "how": "auto", "why": "거래 성사 'you have a deal' — 원본 641.90 = 줄 안 1.49"},
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
    mat = {"_note": "샥탬스토리 14편 The Comfy 재료 계획. 창 1080x1052(벤치 D6H6sj3pap4, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(IK_JDKOLP8g_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global(공식)", "제목": "The Sharks Snuggle Down With Comfy! | Shark Tank US | Shark Tank Global", "해상도": "1920x1080 29.97fps (137) + 140 영어(소리 트랙 하나)",
                      "길이": 705.9, "받은 구간": "전체",
                      "남의 글자": "아래 파란 이름·제안 띠(16~20·22~24·442~448·589·604~610·634초) 시각 안 씀 · 686초 뒤 SHARK TANK 끝 화면 안 씀 · 화면 속 TV 홍보 영상의 'Comfy' 글자 = 제품 브랜드"},
               ISF: {"채널": "In The Know(리뷰)", "제목": "The Comfy from 'Shark Tank' is our new favorite wearable blanket", "해상도": "1920x1080 23.976fps", "길이": 95.5,
                     "남의 글자": "7.5~9.8 'IN THE KNOW' 글자·오른쪽 위 작은 채널 표식 — 쓴 58.3~58.9 로고 근접엔 없음(시트 눈 확인)"}},
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
