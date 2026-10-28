# -*- coding: utf-8 -*-
"""샥탬스토리 28편 Incredible Eats — 벤치 해외쇼츠 Nc3em4FmEtM(「먹을 수 있는 숟가락 / 쓴다 vs 안쓴다」 120만, 38.0초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/28편_IncredibleEats/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Four Sharks Fight For A Deal With Incredible Eats' EU96s14zgLk, 1080p 30fps, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/28편_IncredibleEats/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청·제안 띠(80~89·406~414·470~476·504~508·520~528·570~576·590~596·604~608·622~626초)와 678초 뒤 끝 화면은 안 쓰는 구간. 쓰는 컷은 띠 없음.
★화면에 빨간 옷(투자자)·주황 글씨(창업자 옷) — 자막 강조색 빨강·분홍·주황 금지(체크리스트 ④, emph_ban).
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '7억 5천만원에 지분 15%'·'3년 동안 2억 5천'(금액·지분)·'젓가락 15칼로리'(영양 수치)는 쓰지 않는다. 먹어도 안전·환경 효과 같은 주장은 하지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/28편_IncredibleEats/src")
CLIP = "EU96s14zgLk"
FILES = {CLIP: ("EU96s14zgLk.mp4", 0.0, (1920, 1080))}
AUDIO = "EU96s14zgLk_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 이름/요청/제안 띠는 안 쓰는 구간 · 678초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (111.97, 115.01), "en": "I had one spoon here and it was fantastic.",
     "sub": ["숟가락 하나 먹었는데", "완전 끝내줘!"], "facts": ["f1"], "cap_at": [111.97, 113.97], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 거치대에 꽂힌 먹는 숟가락) — 벤치 0~1.0 투자자 손 숟가락 원(우리도 물건 원)",
     "cuts": [C(CLIP, 76.30, 77.50, 905, ours="투명 거치대에 꽂힌 먹는 숟가락들(원본 샷 76.24~78.51, 얼굴 없음 — 소리 = 투자자 원음 'I had one spoon here' cover, 말한 사람은 다음 컷)", cover=True),
              C(CLIP, 113.17, 115.01, ours="숟가락을 들고 말하는 투자자 본인(원본 샷 112.98~115.38 — 소리 = 이 줄 원음 이어서, 화면초 113.17 = 소리초 113.17)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "숟가락을 다 쓰고 나면 아예 씹어 먹어 버리는 사람들이 있는데",
     "tts": "숟가락을 다 쓰고 나면, 아예 씹어 먹어 버리는 사람들이 있는데",
     "sub": ["숟가락을 다 쓰고 나면", "아예 씹어 먹어 버리는", "사람들이 있는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5('숟가락을 씹어먹는 사람들')",
     "cuts": [C(CLIP, 93.10, 94.80, ours="숟가락을 베어 무는 투자자(원본 샷 93.06~95.53, 띠 없음, 소리 끔)"),
              C(CLIP, 95.56, 97.05, ours="숟가락을 씹어 보는 다른 투자자(샷 95.53~97.10, 띠 없음 — 88.96~90.36 컷은 아래 금액 띠라 뺌, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(한 마디)", "audio": (64.66, 68.01), "en": "eat your spoon, eat your straw,",
     "sub": ["숟가락도 드시고", "빨대도 드세요!"], "facts": ["f2"], "cap_at": [64.89, 66.97],
     "cuts": [C(CLIP, 64.66, 65.97, ours="말하는 창업자 본인(원본 샷 64.63~66.00)"),
              C(CLIP, 66.03, 68.01, ours="숟가락을 들고 말하는 창업자 본인(샷 66.00~68.13)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(정체)", "text": "플라스틱 수저 대신 통째로 먹을 수 있게 만든 숟가락이라는데",
     "tts": "플라스틱 수저 대신, 통째로 먹을 수 있게 만든, 숟가락이라는데",
     "sub": ["플라스틱 수저 대신", "통째로 먹을 수 있게 만든", "숟가락이라는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 13.5('먹을 수 있는 커틀러리')",
     "cuts": [C(CLIP, 54.00, 56.75, ours="무대 위 제품 진열대(원본 샷 53.75~56.79, 제품 브랜드, 소리 끔)"),
              C(CLIP, 56.85, 59.75, 1150, ours="먹는 숟가락과 상자(샷 56.79~59.83, 제품 브랜드, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "반응(사 먹고 싶다)", "audio": (120.33, 123.41), "en": "want to buy and eat these. Not even as a utensil.",
     "sub": ["사서 먹고 싶을 정도야", "수저 말고 간식으로!"], "facts": ["f1"], "cap_at": [120.33, 121.85],
     "cuts": [C(CLIP, 120.33, 121.84, ours="숟가락을 들고 말하는 투자자 본인(원본 샷 119.99~121.86)"),
              C(CLIP, 121.90, 123.40, ours="숟가락을 먹어 보는 다른 투자자(샷 121.86~123.42 — 소리 = 투자자 원음 그 시각)")]},
    {"id": "N3", "kind": "나레", "beat": "체험(버팀)", "text": "뜨거운 국에서도 이십 분 아이스크림에선 한 시간을 버틴다는데",
     "tts": "뜨거운 국에서도 이십 분, 아이스크림에선, 한 시간을 버틴다는데",
     "sub": ["뜨거운 국에서도 20분", "아이스크림에선", "한 시간을 버틴다는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 20.5('20분 동안 쓸 수 있고')",
     "cuts": [C(CLIP, 101.55, 103.40, ours="셔벗에 꽂힌 먹는 숟가락(원본 샷 101.50~104.04, 소리 끔)"),
              C(CLIP, 139.47, 142.50, ours="먹는 숟가락을 맛보는 투자자(샷 139.44~143.21, 소리 끔)")]},
    {"id": "N4", "kind": "나레", "beat": "숫자(가격)", "text": "근데 플라스틱 숟가락보다 열 배 넘게 비싸다는 게 문제였는데",
     "tts": "근데 플라스틱 숟가락보다, 열 배 넘게 비싸다는 게, 문제였는데",
     "sub": ["근데 플라스틱 숟가락보다", "열 배 넘게 비싸다는 게", "문제였는데"], "facts": ["f5"],
     "cuts": [C(CLIP, 240.70, 244.60, ours="숟가락을 들고 따지는 투자자(원본 샷 240.67~244.64, 소리 끔)"),
              C(CLIP, 251.25, 253.30, ours="듣고 있는 다른 투자자(샷 251.22~253.35, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "지분 경쟁(독설)", "audio": (463.80, 465.40), "en": "planet neutron. That's the problem.",
     "sub": ["딴 행성 조건이야", "그게 문제지!"], "facts": ["f6"], "cap_at": [463.80, 464.64],
     "fx": "빨강 번쩍 — 벤치 지분 경쟁",
     "cuts": [C(CLIP, 463.80, 465.40, ours="말하는 투자자 본인(원본 샷 463.63~465.57)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁(제안)", "text": "그런데도 샤크 넷이 앞다퉈 제안을 던지는데",
     "tts": "그런데도, 샤크 넷이, 앞다퉈 제안을 던지는데",
     "sub": ["그런데도", "샤크 넷이", "앞다퉈 제안을 던지는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 539.80, 541.10, ours="상자를 들고 제안하는 투자자(원본 샷 539.77~545.21, 띠 없음, 소리 끔)"),
              C(CLIP, 552.85, 554.20, ours="듣고 있는 다른 투자자(샷 552.82~555.05, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "지분 경쟁(다시 참전)", "audio": (597.99, 599.42), "en": "go ahead and come back in.",
     "sub": ["나도 다시", "들어갈게요!"], "facts": ["f7"], "cap_at": [597.99, 598.70],
     "fx": "초록 번쩍 — 제안 경쟁",
     "cuts": [C(CLIP, 597.99, 599.42, ours="빠졌다가 다시 들어오는 투자자 본인(원본 샷 597.96~599.53, 띠 없음)")]},
    {"id": "N6", "kind": "나레", "beat": "결정(선택)", "text": "결국 창업자는 처음부터 크게 봐 준 로리와 손을 잡았다는데",
     "tts": "결국 창업자는, 처음부터 크게 봐 준, 로리와 손을 잡았다는데",
     "sub": ["결국 창업자는", "처음부터 크게 봐 준", "로리와 손을 잡았다는데"], "facts": ["f8"],
     "cuts": [C(CLIP, 645.78, 647.45, ours="고민하는 창업자(원본 샷 645.75~647.48, 소리 끔)"),
              C(CLIP, 653.40, 655.80, ours="무대에 선 창업자(샷 653.35~657.72, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(성사)", "audio": (666.30, 667.78), "en": "So, Lori, you have a deal.",
     "sub": ["로리", "같이 해요!"], "facts": ["f8"], "cap_at": [666.30, 666.98],
     "fx": "초록 번쩍 — 성사",
     "cuts": [C(CLIP, 666.30, 667.78, ours="말하는 창업자 본인(원본 샷 665.43~667.80)")]},
    {"id": "N7", "kind": "나레", "beat": "끝(결과)", "text": "먹는 숟가락 하나로 결국 샤크까지 잡았다는데",
     "tts": "먹는 숟가락 하나로, 결국 샤크까지 잡았다는데",
     "sub": ["먹는 숟가락 하나로", "결국 샤크까지", "잡았다는데"], "facts": ["f8"],
     "cuts": [C(CLIP, 534.16, 536.10, 1100, ours="먹는 숟가락 상자들(원본 샷 534.13~539.77, 제품 브랜드, 소리 끔)"),
              C(CLIP, 674.20, 675.48, ours="함께 무대를 나서는 두 사람(샷 674.17~675.51, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/28편_IncredibleEats/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 28편 Incredible Eats — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "다 쓴 숟가락을", "line2": "씹어 먹는다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 111.97~115.01 'I had one spoon here and it was fantastic.' · 119.33~123.41 'I would actually want to buy and eat these. Not even as a utensil.'(스피치매틱스 enhanced 영어 — 투자자 원음, 이름은 자막에 안 씀) · 0초 화면은 같은 원본 76.3초 거치대에 꽂힌 숟가락(cover)", "url": U + CLIP + "&t=111s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 63.80~72.17 'Now you may eat your spoon, eat your straw, eat your spork, and even eat your chopsticks.' · 89.85~91.45 'Who cares? I'm gonna eat a spork.' · 화면 89~98 투자자들이 숟가락을 씹음", "url": U + CLIP + "&t=63s", "kind": "방송 원음+화면"},
    "f3": {"text": "원본 28.76~36.56 'a staggering amount of people are eating their food with single use plastic utensils.' · 48.92~60.60 'That's why we came up with incredible cutlery. The world's first mass manufacturable, totally edible utensils.'", "url": U + CLIP + "&t=28s", "kind": "방송 원음"},
    "f4": {"text": "원본 95.17~101.57 'So each spoon stays firm for up to 20 minutes in hot soups. Like a hot food and about an hour in an ice cream.' — 창업자 말 그대로 전언", "url": U + CLIP + "&t=95s", "kind": "방송 원음"},
    "f5": {"text": "원본 169.93~172.73 'A plastic spoon trends around 1 to $0.02 per spoon.' · 196.66~198.02 'We already brought it down to $0.20.' · 251.42~257.43 'Or do I want to pay ten times more for this…' · 267.07~268.55 'But do I want to pay 20 times more?' — 금액은 대본에 안 씀('열 배 넘게'만)", "url": U + CLIP + "&t=169s", "kind": "방송 원음"},
    "f6": {"text": "원본 383.72~385.60 'And so for those reasons, I'm out.'(첫 포기) · 455.84~465.40 '…choking on this 7.1 million valuation… Your deal's from the planet neutron. That's the problem.' — 금액은 대본에 안 씀", "url": U + CLIP + "&t=455s", "kind": "방송 원음+화면"},
    "f7": {"text": "원본 466.60~471.88(첫 제안) · 516.29~519.57(둘째) · 563.05~569.85(셋째) · 572.26~574.86 'So you now have three offers to consider.' · 597.62~605.30(넷째, 'I'm going to go ahead and come back in.') · 597.62~599.42 'I'm going to go ahead and come back in.' · 601.90~603.54 'Oh, it's a feeding frenzy.' — 금액·지분은 대본에 안 씀", "url": U + CLIP + "&t=466s", "kind": "방송 원음+화면"},
    "f8": {"text": "원본 656.58~660.66 'I gave you the closest.' · 666.30~667.78 'So, Lori, you have a deal.' · 570~574 띠 \"Lori's offer\" · 672 무대에서 끌어안음", "url": U + CLIP + "&t=656s", "kind": "방송 원음+화면"},
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
        "topic": "Incredible Eats(인크레더블 이츠) — 다 쓰고 나면 씹어 먹는 숟가락·빨대·젓가락. 플라스틱 일회용 수저 대신 먹는 수저, 샤크 시식 '사서 간식으로 먹고 싶다' → 비싸다며 하나 빠짐 → 넷이 앞다퉈 제안('먹이 쟁탈전') → 로리와 성사",
        "product": "Incredible Eats edible spoon(먹는 숟가락)",
        "bench": {"id": "Nc3em4FmEtM", "channel": "해외쇼츠 @foreignshowshow", "title": "An edible spoon?! (화면 제목: 먹을수 있는 숟가락 / 쓴다 vs 안쓴다)",
                  "dur": 38.0, "views": 1200000, "window": [0, 434, 1080, 1052], "cut_median": 1.4, "_cut_median_how": "1초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '7억 5천만원 줄게요'·'지분 15%'·'3년 동안 2억 5천'(금액·지분) → 금액 없이 제안 경쟁·성사만",
            "벤치 '플라스틱 소비를 줄이기 위해'·'쓰레기장에서는 평생'(환경 효과 주장) → '플라스틱 수저 대신'(창업자 말 전언)만",
            "벤치 5~6초 남의 플라스틱 더미·바다 영상과 13~14초 남의 리뷰 영상(남의 얼굴) — 이 원본 밖 → 원본 무대·제품 컷으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '먹을수 있는 숟가락 / 쓴다 vs 안쓴다'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [359, 1048, 720, 1174], "target_what": "거치대 가운데 꽂힌 먹는 숟가락 하나 — 76.6초 원본 프레임 눈 측정(창 크롭 [351,0,1109,1080] 안 x 369~739·y 630~760, ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 13.5 해답"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 20.5"},
    {"line": "O5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "제안 경쟁"},
    {"line": "O6", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "성사"},
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
    mat = {"_note": "샥탬스토리 28편 Incredible Eats 재료 계획. 창 1080x1052(벤치 Nc3em4FmEtM, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(EU96s14zgLk_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Four Sharks Fight For A Deal With Incredible Eats", "해상도": "1920x1080 30fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 698.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(80~89·406~414·470~476·504~508·520~528·570~576·590~596·604~608·622~626초) 안 씀 · 678초 뒤 끝 화면 안 씀 · 무대·상자 'incredible EATS'·'Edible Spoon' 글 = 제품 브랜드"}},
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
