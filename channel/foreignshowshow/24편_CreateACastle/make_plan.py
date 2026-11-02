# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""샥탬스토리 24편 Create A Castle — 벤치 해외쇼츠 YCosCkpODLc(「몇분만에 완벽한 / 모래성을 만든다고?!」 120만, 47.0초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/24편_CreateACastle/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Shark Tank Global 공식 'The Sharks Fight For A Deal With Create A Castle | Shark Tank US' WIcEFgXDVsY, 1080p 30fps, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/24편_CreateACastle/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청·제안 띠(103~111·340~342·440~442·476~490·540~542초)와 591초 뒤 제작진 이름·끝 화면은 안 쓰는 구간. 쓰는 컷은 띠 없음.
★무대 화면 속 영상(48~51 양동이·76~86 해변 시연·155~162 눈)은 화면 안쪽만 자른다 · 160초 눈 성 뒤 'LIFEGUARD FIRST AID' 간판 구간은 안 씀.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '41억원'·'4억 8천만원'(금액)·'12개의 특허'는 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/24편_CreateACastle/src")
CLIP = "WIcEFgXDVsY"
FILES = {CLIP: ("WIcEFgXDVsY.mp4", 0.0, (1920, 1080))}
AUDIO = "WIcEFgXDVsY_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Shark Tank Global 원본: 고정 로고 없음 · 이름/요청/제안 띠(103~111·340~342·440~442·476~490·540~542초)는 안 쓰는 구간 · 591초 뒤 제작진 이름·끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (117.98, 119.46), "en": "You can build that entire castle.",
     "sub": ["이 성을 통째로 만든다고?"], "facts": ["f1"], "cap_at": [117.98], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 무대 위 모래성 탑) — 벤치 0~1.0 투자자 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 41.25, 42.73, 980, ours="무대 위 모래성 탑 근접(원본 샷 40.74~43.31, 사람 없음 — 소리 = 투자자 원음 'You can build that entire castle.' cover, 말한 사람은 화면 밖)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "해변에 가면 가족은 뒷전이고 몇 시간씩 모래성만 쌓던 남편이 있었는데",
     "tts": "해변에 가면 가족은 뒷전이고, 몇 시간씩 모래성만 쌓던 남편이 있었는데",
     "sub": ["해변에 가면 가족은 뒷전이고", "몇 시간씩 모래성만 쌓던", "남편이 있었는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5('41억원?!' 자리 — 우리는 금액 없음)",
     "cuts": [C(CLIP, 30.20, 33.10, 900, ours="무대 위 큰 모래성과 두 창업자(원본 샷 ~24~33.27, 소리 끔)"),
              C(CLIP, 34.00, 36.60, ours="나란히 선 두 창업자(샷 33.27~39.51, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "문제(한 마디)", "audio": (47.80, 49.56), "en": "The wet sand sticks in the bucket.",
     "sub": ["젖은 모래가 통에 달라붙어요"], "facts": ["f3"], "cap_at": [47.80],
     "cuts": [C(CLIP, 47.98, 49.74, 960, y=146, h=740, cover=True, ours="무대 화면 속 초록 양동이를 뒤집는 손(원본 샷 47.95~51.42, 화면 안쪽만 자름 — 소리 = 창업자 원음 cover)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "그래서 반으로 쪼개지는 모래성 틀을 아예 만들어 버렸다는데",
     "tts": "그래서 반으로 쪼개지는, 모래성 틀을 아예 만들어 버렸다는데",
     "sub": ["그래서 반으로 쪼개지는", "모래성 틀을 아예", "만들어 버렸다는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 8.0('모래성을 만들 수 없어요' → 해답)",
     "cuts": [C(CLIP, 63.00, 67.30, 1100, ours="두 쪽짜리 파란 틀을 버클로 채우고 푸는 손(원본 샷 62.60~67.43, 소리 끔)")]},
    {"id": "N3", "kind": "나레", "beat": "시연(틀 열기)", "text": "틀에 모래를 꾹꾹 담고 열기만 하면 모래 탑이 뚝딱 선다는데",
     "tts": "틀에 모래를 꾹꾹 담고, 열기만 하면 모래 탑이 뚝딱 선다는데",
     "sub": ["틀에 모래를 꾹꾹 담고", "열기만 하면", "모래 탑이 뚝딱 선다는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 10.0('몇 시간 걸리던 작업을')",
     "cuts": [C(CLIP, 80.95, 84.85, 1050, y=155, h=690, ours="무대 화면 속 해변 시연 — 파란 틀에 모래를 다지는 손(원본 샷 80.88~84.92, 화면 안쪽만, 소리 끔)"),
              C(CLIP, 84.97, 86.35, 1140, y=170, h=700, ours="틀을 열자 선 모래 탑(샷 84.92~86.39, 화면 안쪽만, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "반응(두 시간)", "audio": (121.06, 122.54), "en": "That took me under two hours.",
     "sub": ["두 시간도 안 걸렸어요"], "facts": ["f5"], "cap_at": [121.06],
     "cuts": [C(CLIP, 120.65, 122.13, 960, cover=True, ours="모래성 근접(원본 샷 120.59~122.32 — 소리 = 창업자 원음 cover, 말하는 사람은 화면 밖)")]},
    {"id": "N4", "kind": "나레", "beat": "체험(겨울)", "text": "샤크들도 깜짝 놀랐는데 겨울엔 눈으로도 똑같이 쌓는다는데",
     "tts": "샤크들도 깜짝 놀랐는데, 겨울엔 눈으로도 똑같이 쌓는다는데",
     "sub": ["샤크들도 깜짝 놀랐는데", "겨울엔 눈으로도", "똑같이 쌓는다는데"], "facts": ["f5", "f6"],
     "fx": "초록 번쩍 — 벤치 38.0('겨울에 눈으로도')",
     "cuts": [C(CLIP, 123.22, 124.05, ours="놀라는 투자자(원본 샷 123.19~124.09, 소리 끔)"),
              C(CLIP, 147.40, 149.18, ours="'눈에서도 된다'며 말하는 창업자(샷 147.35~149.22, 소리 끔)"),
              C(CLIP, 155.75, 157.28, 830, y=110, h=840, ours="무대 화면 속 눈밭에서 초록 틀을 채우는 손(샷 155.69~157.32, 화면 안쪽만, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "반응(엘사)", "audio": (161.30, 162.34), "en": "Elsa's castle.",
     "sub": ["엘사 성이네!"], "facts": ["f6"], "cap_at": [161.30],
     "cuts": [C(CLIP, 157.36, 158.40, 880, y=110, h=840, cover=True, ours="무대 화면 속 눈으로 쌓은 탑(샷 157.32~159.46, 화면 안쪽만 — 소리 = 투자자 원음 cover)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁(거절)", "text": "근데 수익 얘기가 나오자 샤크 세 명이 줄줄이 빠졌는데",
     "tts": "근데 수익 얘기가 나오자, 샤크 세 명이 줄줄이 빠졌는데",
     "sub": ["근데 수익 얘기가 나오자", "샤크 세 명이", "줄줄이 빠졌는데"], "facts": ["f7"],
     "fx": "빨강 번쩍 — 벤치 지분 경쟁",
     "cuts": [C(CLIP, 324.10, 327.00, ours="빠지겠다고 말하는 투자자(원본 샷 324.02~330.96, 소리 끔)"),
              C(CLIP, 349.00, 352.00, ours="빠지겠다고 말하는 다른 투자자(샷 348.68~352.22, 소리 끔)")]},
    {"id": "N6", "kind": "나레", "beat": "지분 경쟁(두 제안)", "text": "남은 샤크 두 명이 서로 데려가겠다고 붙었다는데",
     "tts": "남은 샤크 두 명이, 서로 데려가겠다고 붙었다는데",
     "sub": ["남은 샤크 두 명이", "서로 데려가겠다고", "붙었다는데"], "facts": ["f8"],
     "cuts": [C(CLIP, 432.05, 434.05, ours="제안하는 투자자(원본 샷 431.96~434.13, 소리 끔)"),
              C(CLIP, 454.00, 457.00, ours="다른 제안을 내미는 투자자(샷 453.79~, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "결정(가로채기)", "audio": (448.99, 451.08), "en": "Wait wait wait wait, hold on.",
     "sub": ["잠깐 잠깐", "기다려 봐!"], "facts": ["f8"], "cap_at": [448.99, 450.55],
     "cuts": [C(CLIP, 448.99, 450.12, 960, cover=True, ours="무대 위 두 창업자(원본 샷 448.35~450.15 — 소리 = 투자자 원음 cover)"),
              C(CLIP, 450.18, 451.06, cover=True, ours="'잠깐'을 외치는 투자자 본인(샷 450.15~451.08, 소리 = 이 줄 원음 이어서)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(성사)", "audio": (573.17, 574.45), "en": "Yay! Oh my God.",
     "sub": ["야호! 세상에!"], "facts": ["f9"], "cap_at": [573.17],
     "fx": "초록 번쩍 — 성사",
     "cuts": [C(CLIP, 573.17, 574.45, ours="투자자와 끌어안는 창업자(원본 샷 572.14~576.18, 말하는 본인)")]},
    {"id": "N7", "kind": "나레", "beat": "끝(결과)", "text": "가족은 뒷전이던 모래성 아빠가 결국 샤크까지 잡았다는데",
     "tts": "가족은 뒷전이던 모래성 아빠가, 결국 샤크까지 잡았다는데",
     "sub": ["가족은 뒷전이던 모래성 아빠가", "결국 샤크까지", "잡았다는데"], "facts": ["f9"],
     "cuts": [C(CLIP, 581.00, 583.40, 960, ours="무대 뒤로 걸어 나오는 두 창업자(원본 샷 580.75~583.55, 소리 끔)"),
              C(CLIP, 584.00, 587.00, ours="무대 뒤 인터뷰하는 두 창업자(샷 583.72~593.66 중 제작진 이름 뜨기 전, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/24편_CreateACastle/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 24편 Create A Castle — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "틀 하나로 이런", "line2": "모래성이 된다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 117.98~119.46 'You can build that entire castle.'(스피치매틱스 enhanced 영어 — 투자자 원음, 이름은 자막에 안 씀) · 화면은 같은 원본 41.25초 무대 위 모래성(cover)", "url": U + CLIP + "&t=117s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 33.32~42.52 'if you're anything like my husband here, you like to spend hours and hours and hours ignoring his family building the most elaborate sand castles.'", "url": U + CLIP + "&t=33s", "kind": "방송 원음"},
    "f3": {"text": "원본 42.52~52.48 'it's impossible to build a real sandcastle using the traditional fill and flip buckets. The wet sand sticks in the bucket. Even at its best, it just looks boring.' · 화면 48~51 초록 양동이", "url": U + CLIP + "&t=42s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 53.04~69.33 'we invented Create a Castle revolutionary split mold sandcastle kits… Just buckle it, pack it, unbuckle it, and well, create a castle.' · 114.05 'the mold split in half' · 화면 63~67·77~86 시연", "url": U + CLIP + "&t=53s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 119.94~123.74 'How long does that take?' 'That took me under two hours.' 'Wow.'", "url": U + CLIP + "&t=119s", "kind": "방송 원음+화면"},
    "f6": {"text": "원본 147.86~162.34 'It works in the snow… it works year round… And you can stack like crazy.' 'Elsa's castle.' · 화면 155~162 눈 시연", "url": U + CLIP + "&t=147s", "kind": "방송 원음+화면"},
    "f7": {"text": "원본 328.65~330.73 'And so for those reasons, I'm out.' · 346.61~362.14 'it's not investable yet because the business model isn't nailed down… I'm out.' · 381.62~384.86 'You're doing everything right… but I'm out.' (세 명)", "url": U + CLIP + "&t=328s", "kind": "방송 원음+화면"},
    "f8": {"text": "원본 419.87~444.67 'I'm going to give you an offer…' · 448.99~451.11 'Wait wait wait wait, hold on.' · 478.84~484.64 'I will give you the $350,000 for 25%' (두 샤크 경쟁) — 금액·지분은 대본에 안 씀", "url": U + CLIP + "&t=419s", "kind": "방송 원음+화면"},
    "f9": {"text": "원본 561.21~563.81 'But I think we're going to go with Kendra at the 20.' · 573.17~574.45 'Yay! Oh my God.' · 581.49~593.58 인터뷰 — 금액·지분은 대본에 안 씀", "url": U + CLIP + "&t=561s", "kind": "방송 원음+화면"},
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
        "topic": "Create A Castle(크리에이트 어 캐슬) — 반으로 쪼개지는 모래성 틀. 해변에서 몇 시간씩 모래성을 쌓던 남편과 아내가 만듦, 해변·눈 시연 → 샤크 세 명 빠짐 → 두 샤크 경쟁 → 켄드라와 성사",
        "product": "Create A Castle split mold sandcastle kit(반으로 쪼개지는 모래성 틀)",
        "bench": {"id": "YCosCkpODLc", "channel": "해외쇼츠 @foreignshowshow", "title": "모래성을 쉽게 만든다고?! (화면 제목: 몇분만에 완벽한 / 모래성을 만든다고?!)",
                  "dur": 47.0, "views": 1200000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "2초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '41억원'·'약 4억 8천만원에'(금액) → 금액 없이 거절·경쟁·성사만",
            "벤치 '12개의 특허'·'국제완구상 수상' — 대본 사실 줄로는 안 씀(수상은 원본에 없음)",
            "벤치 2~22초 남의 해변 영상 — 이 원본 밖 → 원본 무대 화면 속 시연으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '몇분만에 완벽한 / 모래성을 만든다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [442, 502, 637, 824], "target_what": "모래성 꼭대기 탑(창문·고깔) — 42.0초 원본 프레임 눈 측정(창 크롭 [426,0,1108,1080] 안 x 454~654·y 70~400, ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품으로 만든 성) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 8.0 해답"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 10.0 '몇 시간 걸리던 작업을'"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 38.0 '겨울에 눈으로도'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 지분 경쟁"},
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
    mat = {"_note": "샥탬스토리 24편 Create A Castle 재료 계획. 창 1080x1052(벤치 YCosCkpODLc, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(WIcEFgXDVsY_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global(공식)", "제목": "The Sharks Fight For A Deal With Create A Castle | Shark Tank US | Shark Tank Global", "해상도": "1920x1080 30fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 644.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(103~111·340~342·440~442·476~490·540~542초) 안 씀 · 591초 뒤 제작진 이름·끝 화면 안 씀 · 160초 'LIFEGUARD FIRST AID' 간판 안 씀 · 무대 뒤 'CREATE A CASTLE' 글 = 제품 브랜드"}},
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
