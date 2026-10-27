# -*- coding: utf-8 -*-
"""샥탬스토리 17편 Squid Socks — 벤치 해외쇼츠 pyV4RwGO2nM(「절대 사라지지 / 않는다는 양말?!」 310만, 39.9초) 줄 단위 칼카피 (관제 097, 2026-10-27).

    PYTHONUTF8=1 py channel/foreignshowshow/17편_SquidSocks/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(16편 make_plan 꼴).
원음 줄 = 같은 회차 원본(CNBC Ambition 공식 'Daymond & Robert Fight To Be Sock King | Shark Tank in 5' lrfOlA0NjaA, 1080p, 영어 원어 140-6)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/17편_SquidSocks/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt.
★CNBC 원본은 왼쪽 아래 공작 로고·'CNBC.COM/CHANNELFINDER'(40~60초)·제안/이름 띠(84~91·186~190·219~221·256~283·306~323초)가 y≥900 에 있다 → 모든 컷 크롭 높이 900(y 0~900).
★앞은 하이브리드 재료 — 하이브리드는 N3 끝(약 14.5초)에서 자른다. 벤치의 '3000억'·'1억 8천만원'·'연매출 40억'(금액)과 원본 밖 화면(남의 육아 영상·2년 뒤 인터뷰)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/17편_SquidSocks/src")
CLIP = "lrfOlA0NjaA"
FILES = {CLIP: ("lrfOlA0NjaA.mp4", 0.0, (1920, 1080))}
AUDIO = "lrfOlA0NjaA_audio.m4a"        # 영어 원음(140-6 en-US original — 이 업로드엔 자동 더빙 트랙 6개가 있어 원어만 따로 받음, 98 #176)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# 왼쪽 아래 CNBC 공작 로고·'CNBC.COM/CHANNELFINDER'·이름/제안 띠 = y≥900 → 크롭 높이 900. 0~7초 흑백 예고·343초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (121.49, 122.09), "en": "Oh, wow.",
     "sub": ["우와!"], "facts": ["f1"], "cap_at": [121.49], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 로리가 당겨도 아기 발에 그대로 남은 스퀴드 삭스) — 벤치 0~1.0 놀란 투자자 얼굴(우리는 물건 원)",
     "cuts": [C(CLIP, 121.49, 122.09, 1250, ours="로리가 양쪽 양말을 동시에 당김 — 일반 양말은 벗겨지고 스퀴드 삭스는 그대로(원본 샷 119.69~123.26 · 'Oh, wow' 말한 사람은 화면 밖)")]},
    {"id": "N1", "kind": "나레", "beat": "문제(고통)", "text": "아기 키우는 집이면 매일 한쪽씩 사라진다는 이 양말",
     "tts": "아기 키우는 집이면 매일 한쪽씩 사라진다는 이 양말",
     "sub": ["아기 키우는 집이면", "매일 한쪽씩", "사라진다는 이 양말"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 1.0('수십번 사라지는 양말')",
     "cuts": [C(CLIP, 40.45, 41.70, 960, ours="무대 '실종 수배' 게시판 — 잃어버린 양말 사진들과 빨간 실(원본 샷 40.34~41.74, 창업자 소품)"),
              C(CLIP, 45.05, 46.95, 1500, ours="'뒷마당' 메모가 붙은 잃어버린 아기 양말 사진 근접(샷 44.61~47.18)")]},
    {"id": "N2", "kind": "나레", "beat": "문제(원인)", "text": "애들이 툭하면 잡아당겨서 아무 데나 벗어 던지기 때문인데",
     "tts": "애들이 툭하면 잡아당겨서 아무 데나 벗어 던지기 때문인데",
     "sub": ["애들이 툭하면 잡아당겨서", "아무 데나", "벗어 던지기 때문인데"], "facts": ["f3"],
     "cuts": [C(CLIP, 76.50, 77.95, 1050, ours="큰 아이가 아기 발의 양말을 힘껏 잡아당김(원본 샷 73.57~79.68)"),
              C(CLIP, 78.00, 79.55, 1050, ours="같은 샷 이어서 — 계속 당기는 손")]},
    {"id": "O2", "kind": "원음", "beat": "해답(제품 공개)", "audio": (61.88, 67.24), "en": "Squid socks have squishy dots inside the cuff that hold socks on.",
     "sub": ["스퀴드 삭스는 발목 안쪽에", "말랑한 점들이 있어서", "양말을 꽉 잡아 줘요"], "facts": ["f4"], "cap_at": [61.88, 63.92, 65.12],
     "fx": "초록 번쩍 — 벤치 5.5(제품 공개 컷)",
     "cuts": [C(CLIP, 61.88, 63.03, 960, ours="스퀴드 삭스 3켤레 포장 근접(원본 샷 60.69~63.06, 말은 화면 밖 창업자)"),
              C(CLIP, 63.10, 65.78, 720, ours="홍보 영상: 스퀴드 삭스 신은 여자아이가 발을 잡고 앉아 있음(샷 63.06~65.83)"),
              C(CLIP, 65.86, 67.24, 960, ours="스퀴드 삭스 포장 근접(샷 65.83~68.97)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(차별점)", "text": "근데 이 양말은 애들이 아무리 당겨도 절대 안 빠진다는데",
     "tts": "근데 이 양말은 애들이 아무리 당겨도 절대 안 빠진다는데",
     "sub": ["근데 이 양말은", "애들이 아무리 당겨도", "절대 안 빠진다는데"], "facts": ["f5"],
     "fx": "초록 번쩍 — 벤치 7.0('당기기만 해서는')",
     "cuts": [C(CLIP, 69.10, 71.40, 1250, ours="창업자가 아이들에게 아기 양말을 당겨 보라고 함 — 무대 와이드(원본 샷 68.97~73.57, 소리 끔)"),
              C(CLIP, 97.00, 99.95, 900, ours="무대 화면 'squid socks — squiddy dots hold socks on' 배너, 양말 신은 아기 발들(샷 96.60~100.13)")]},
    {"id": "O3", "kind": "원음", "beat": "시연(당기기 시험)", "audio": (113.36, 118.24), "en": "So, Lori, on this side, we have a traditional baby sock, and on this side we have a squid sock.",
     "sub": ["로리, 이쪽은 일반 양말이고", "이쪽이 스퀴드 삭스예요"], "facts": ["f5"], "cap_at": [113.36, 116.30],
     "cuts": [C(CLIP, 113.36, 114.60, 1250, ours="무대 와이드: 로리가 양말 진열대 쪽으로 나옴(샷 111.95~114.65, 말은 아기를 안은 창업자)"),
              C(CLIP, 114.70, 117.38, 1100, ours="창업자가 아기를 안고 로리에게 설명(샷 114.65~117.42)"),
              C(CLIP, 117.45, 118.24, 1040, ours="아기를 안은 남자 창업자 근접(말하는 본인, 샷 117.42~119.69)")]},
    {"id": "O4", "kind": "원음", "beat": "시연(당기기 시험)", "audio": (118.28, 120.49), "en": "If you want to just pull on both those socks.",
     "sub": ["양쪽을 한꺼번에", "당겨 보세요"], "facts": ["f5"], "cap_at": [118.28, 119.49],
     "cuts": [C(CLIP, 118.28, 119.65, 1040, ours="아기를 안은 남자 창업자(말하는 본인, 같은 샷 이어서)"),
              C(CLIP, 125.65, 126.49, 1000, ours="투자자석 셋이 웃음(샷 125.63~127.53, 소리 = 이 줄 원음 cover)", cover=True)]},
    {"id": "N4", "kind": "나레", "beat": "시연(결과)", "text": "한쪽은 바로 쑥 빠졌는데 이 양말은 그대로 붙어 있었다는데",
     "tts": "한쪽은 바로 쑥 빠졌는데 이 양말은 그대로 붙어 있었다는데",
     "sub": ["한쪽은 바로 쑥 빠졌는데", "이 양말은", "그대로 붙어 있었다는데"], "facts": ["f5"],
     "fx": "빨강 번쩍 — 벤치 17.5('바로 벗겨지는 시중 양말')",
     "cuts": [C(CLIP, 126.55, 127.45, 1000, ours="투자자석 셋이 웃음(같은 샷 이어서, 소리 끔)"),
              C(CLIP, 127.60, 129.05, 960, ours="로리가 벗겨진 일반 양말을 들고, 아기 발엔 스퀴드 삭스가 그대로(와이드, 샷 127.53~129.10)")]},
    {"id": "O5", "kind": "원음", "beat": "시연(투자자 평)", "audio": (130.33, 132.43), "en": "Like it really stayed.",
     "sub": ["진짜 그대로 붙어 있네"], "facts": ["f5"], "cap_at": [130.33],
     "cuts": [C(CLIP, 130.33, 132.43, 1100, ours="로리가 창업자 앞에서 '진짜 그대로 붙어 있네'(샷 130.30~132.43)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁", "text": "결국 다들 양말 왕이라 부르는 샤크까지 직접 나섰는데",
     "tts": "결국 다들 양말 왕이라 부르는 샤크까지 직접 나섰는데",
     "sub": ["결국 다들", "양말 왕이라 부르는", "샤크까지 직접 나섰는데"], "facts": ["f6"],
     "fx": "초록 번쩍 — 벤치 28.5('양말 사업에 투자해')",
     "cuts": [C(CLIP, 181.60, 184.60, ours="데이먼드가 양말을 손에 들고 말함(원본 샷 180.25~184.68, 소리 끔)"),
              C(CLIP, 195.10, 197.60, ours="데이먼드 근접(샷 194.39~199.83, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "지분 경쟁(원음)", "audio": (216.13, 218.21), "en": "So I'll take it down to 33.",
     "sub": ["33%로 낮춰 줄게요"], "facts": ["f6"], "cap_at": [216.13],
     "cuts": [C(CLIP, 215.95, 218.03, ours="데이먼드가 33%로 낮춤(말하는 본인, 샷 214.48~218.05 — 샷 끝 앞에서 끝나게 화면만 0.18초 앞, 소리 = 이 줄 원음)", cover=True)]},
    {"id": "O7", "kind": "원음", "beat": "결정(성사)", "audio": (333.42, 335.58), "en": "And yes, Damon, we would love to do a deal with you.",
     "sub": ["네, 데이먼드", "같이 할게요!"], "facts": ["f7"], "cap_at": [333.42, 334.18],
     "fx": "초록 번쩍 — 벤치 36.0 '거래 받아들일게'",
     "cuts": [C(CLIP, 333.14, 335.30, 1100, ours="여자 창업자가 데이먼드 제안을 받아들임(말하는 본인, 샷 332.03~335.34 — 화면만 0.28초 앞, 소리 = 이 줄 원음)", cover=True)]},
    {"id": "N6", "kind": "나레", "beat": "끝(결과)", "text": "아기 양말 하나로 양말 왕 샤크를 사로잡았다는데",
     "tts": "아기 양말 하나로 양말 왕 샤크를 사로잡았다는데",
     "sub": ["아기 양말 하나로", "양말 왕 샤크를", "사로잡았다는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 337.20, 338.72, 1000, ours="창업자 둘이 무대에서 포옹하며 기뻐함(원본 샷 337.14~338.77, 소리 끔)"),
              C(CLIP, 340.60, 342.95, 1000, ours="창업자가 데이먼드와 포옹(샷 340.54~343.08, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/17편_SquidSocks/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 17편 Squid Socks — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "애들이 못 벗기는", "line2": "마법의 아기 양말?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 118.28~122.09 'If you want to just pull on both those socks. / Yes. / Oh, wow.'(스피치매틱스 enhanced 영어) — 화면 120.0~122.4 로리가 양쪽을 당겨 일반 양말만 벗겨짐", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f2": {"text": "원본 25.04~41.52 'Every day, thousands go lost, missing, and unaccounted for… We've all seen them on the side of the road, at the park… Baby socks.' · 화면 39~47 실종 수배 게시판(양말 사진)", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f3": {"text": "원본 88.32~94.80 'Babies and toddlers love to pull their socks off. And for busy parents, that extra hassle is just too much.'", "url": U + CLIP, "kind": "방송 원음"},
    "f4": {"text": "원본 58.64~67.24 'We have reinvented the baby sock. Squid socks have squishy dots inside the cuff that hold socks on.' · 화면 61~69 제품 포장", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f5": {"text": "원본 70.52~79.52 'Let's pull baby sock off… Pull as hard as you can.' · 113.36~118.24 'So, Lori, on this side, we have a traditional baby sock, and on this side we have a squid sock.' · 129.45~132.49 'Honestly, like it really stayed.' · 화면 120~129 일반 양말만 벗겨짐", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f6": {"text": "원본 164.41~166.81 'Damon. / Sock man. / Sock man.'(투자자들이 데이먼드를 '양말 남자'라 부름) · 213.05~218.21 'I wouldn't want to be more of an owner than the owners, so I'll take it down to 33.'", "url": U + CLIP, "kind": "방송 원음"},
    "f7": {"text": "원본 333.42~335.58 'And yes, Damon, we would love to do a deal with you.' · 화면 337~343 포옹", "url": U + CLIP, "kind": "방송 원음+화면"},
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
        "topic": "Squid Socks(스퀴드 삭스 — 발목 안쪽 말랑한 점이 잡아 줘 아기가 당겨도 안 벗겨지는 아기 양말) — 부부 창업자가 '실종 양말 수배' 연출, 로리가 일반 양말과 동시에 당기는 시험 → 데이먼드(양말 남자)와 33% 거래",
        "product": "Squid Socks(스퀴드 삭스)",
        "bench": {"id": "pyV4RwGO2nM", "channel": "해외쇼츠 @foreignshowshow", "title": "Socks That Never Get Lost?! (화면 제목: 절대 사라지지 / 않는다는 양말?!)",
                  "dur": 39.933, "views": 3100000, "window": [0, 434, 1080, 1052], "cut_median": 1.2, "_cut_median_how": "1초 시트 눈 측정(컷 약 33) — 10-27"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '양말 사업에 투자해 3000억을 벌어들인'·'1억 8천만원 투자에 33%'·'2년 뒤 연매출 40억'(금액) → 금액 없이 '양말 왕이라 부르는 샤크'(원음 'Sock man')·지분 33%만",
            "벤치 1.5~5 남의 육아 영상(양말 벗는 아기·초록 화살표)·끝 2년 뒤 인터뷰 — 이 원본 밖 → 원본 안 수배 게시판·무대 시연으로",
            "벤치 0초 놀란 투자자 얼굴 원 → R3 물건 원(아기 발에 남은 스퀴드 삭스)"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '절대 사라지지 / 않는다는 양말?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [143, 995, 587, 1205], "target_what": "로리가 당겨도 아기 발에 그대로 남은 스퀴드 삭스(제품) — 손 상자 = 121.55초 원본 프레임 눈 측정(원본 x 910~1290·y 480~660, 크롭 x 788 → 완성본 좌표 · 크롭 cx 1100 은 로리 손이 얼굴로 잡혀 거절)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 1.0 '수십번 사라지는 양말'"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 5.5 '유아용 양말을 발명'"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 7.0 '당기기만 해서는'"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 17.5 '바로 벗겨지는 시중 양말'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 28.5 '양말 사업에 투자해'"},
    {"line": "O7", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 36.0 '데이먼 거래 받아들일게'"},
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
    mat = {"_note": "샥탬스토리 17편 Squid Socks 재료 계획. 창 1080x1052(벤치 pyV4RwGO2nM, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(lrfOlA0NjaA_audio.m4a).",
           "sources": {
               CLIP: {"채널": "CNBC Ambition(공식)", "제목": "Daymond & Robert Fight To Be Sock King | Shark Tank in 5", "해상도": "1920x1080 29.97fps (137) + 140-6 영어 원어(자동 더빙 6개는 안 씀)",
                      "길이": 355.5, "받은 구간": "전체",
                      "남의 글자": "왼쪽 아래 CNBC 공작 로고·'CNBC.COM/CHANNELFINDER'·이름/제안 띠 = 화면 아래 y≥900 → 모든 컷 크롭 높이 900 · 0~7초 흑백 예고·343초 뒤 끝 화면 안 씀 · 포장·배너의 'squid socks' 글자 = 제품 브랜드 · 수배 게시판 메모 = 창업자 소품"}},
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
