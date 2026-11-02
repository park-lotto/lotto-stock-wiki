# -*- coding: utf-8 -*-
"""샥탬스토리 25편 Snow in Seconds — 벤치 해외쇼츠 N2SNg-9RDEc(「한여름에 집에서 / 눈이 내린다고?!」 110만, 46.2초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/25편_SnowInSeconds/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Kevin HATES Snow In Seconds Product' 8X9tQmmGUJU, 1080p 30fps, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/25편_SnowInSeconds/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청·제안 띠(86~95·314~318·396~399·410~412초)와 470초 뒤 끝 화면('SHARK TANK WATCH MORE')은 안 쓰는 구간. 쓰는 컷은 띠 없음.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '7400만원'·'33% 지분'(금액·지분)·'아이들에게도 안전'(안전성)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/25편_SnowInSeconds/src")
CLIP = "8X9tQmmGUJU"
FILES = {CLIP: ("8X9tQmmGUJU.mp4", 0.0, (1920, 1080))}
AUDIO = "8X9tQmmGUJU_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 이름/요청/제안 띠(86~95·314~318·396~399·410~412초)는 안 쓰는 구간 · 470초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (96.70, 98.46), "en": "It's a Christmas miracle.",
     "sub": ["크리스마스 기적이네!"], "facts": ["f1"], "cap_at": [96.70], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 투자자 손에 들린 눈 그릇) — 벤치 0~1.0 투자자 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 143.20, 144.96, 1205, ours="투자자 손에 들린 눈 그릇(원본 샷 141.91~145.01, 얼굴 없음 — 소리 = 투자자 원음 'It's a Christmas miracle.' cover, 말한 사람은 화면 밖)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "한여름 집 안에서도 눈을 펑펑 내리게 한다는 가루가 있는데",
     "tts": "한여름 집 안에서도, 눈을 펑펑 내리게 한다는 가루가 있는데",
     "sub": ["한여름 집 안에서도", "눈을 펑펑 내리게 한다는", "가루가 있는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5('한여름 천장에서 내리기 시작하는 눈')",
     "cuts": [C(CLIP, 97.98, 99.50, ours="무대 위에서 눈을 맞는 투자자(원본 샷 97.96~99.53, 소리 끔)"),
              C(CLIP, 99.56, 102.28, ours="쏟아지는 눈을 올려다보는 다른 투자자(샷 99.53~102.30, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(한 마디)", "audio": (46.76, 50.72), "en": "Just take one small scoop of our powder, add water.",
     "sub": ["가루 한 숟갈 넣고", "물만 부으세요"], "facts": ["f3"], "cap_at": [46.76, 49.80],
     "cuts": [C(CLIP, 46.76, 48.40, ours="말하는 창업자 본인(원본 샷 45.31~48.42)"),
              C(CLIP, 48.45, 49.83, 1150, cover=True, ours="숟가락으로 가루를 뜨는 손(샷 48.42~49.85 — 소리 = 창업자 원음 이어서 cover)"),
              C(CLIP, 51.25, 52.14, 900, cover=True, ours="그릇에 물을 붓는 손(샷 51.18~56.62 — 소리 = 창업자 원음 이어서 cover)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(시연)", "text": "물만 부으면 몇 초 만에 폭신한 눈으로 부풀어 오른다는데",
     "tts": "물만 부으면, 몇 초 만에 폭신한 눈으로 부풀어 오른다는데",
     "sub": ["물만 부으면", "몇 초 만에 폭신한 눈으로", "부풀어 오른다는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 16.5('물을 넣으면 몇 초 만에 눈처럼')",
     "cuts": [C(CLIP, 52.20, 56.55, 820, ours="물을 붓자 그릇 안에서 하얗게 부푸는 가루(원본 샷 51.18~56.62, 소리 끔)"),
              C(CLIP, 68.40, 70.30, 1450, ours="유리 그릇 가득 부푼 눈을 손으로 뒤적임(샷 68.33~74.21 중 뒤 포스터 아이 사진 보이기 전, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "반응(직접 해 봄)", "audio": (140.92, 143.52), "en": "Oh, wow. There it goes. Woo! It's growing.",
     "sub": ["오 와! 된다 된다!", "커지고 있어!"], "facts": ["f4"], "cap_at": [140.92, 142.80],
     "cuts": [C(CLIP, 135.40, 135.90, 1150, cover=True, ours="숟가락으로 가루를 뜨는 투자자 손(원본 샷 135.30~136.74 — 소리 = 투자자 원음 cover)"),
              C(CLIP, 157.90, 160.00, cover=True, ours="눈을 손에 쥐고 감탄하는 투자자(샷 157.86~160.06 — 직접 해 본 투자자, 소리 = 원음 이어서 cover)")]},
    {"id": "N3", "kind": "나레", "beat": "체험(촉감)", "text": "만지면 차갑고 보송보송한데 녹지도 않는다는데",
     "tts": "만지면 차갑고 보송보송한데, 녹지도 않는다는데",
     "sub": ["만지면 차갑고", "보송보송한데", "녹지도 않는다는데"], "facts": ["f5"],
     "fx": "초록 번쩍 — 벤치 24.2('절대 녹지 않고')",
     "cuts": [C(CLIP, 149.30, 150.70, 900, ours="눈을 손가락으로 집어 보는 손(원본 샷 149.25~150.78, 소리 끔)"),
              C(CLIP, 151.10, 153.00, 1100, ours="눈을 집어 뿌려 보는 투자자 손(샷 150.78~153.09, 소리 끔)")]},
    {"id": "N4", "kind": "나레", "beat": "숫자(15년)", "text": "근데 15년 동안 차고에서 아이들이랑 직접 포장해서 팔았다는데",
     "tts": "근데 십오 년 동안, 차고에서 아이들이랑 직접 포장해서 팔았다는데",
     "sub": ["근데 15년 동안", "차고에서 아이들이랑", "직접 포장해서 팔았다는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 164.00, 166.30, 1100, ours="물병과 Snow in Seconds 봉지(원본 샷 163.23~166.37, 제품 브랜드, 소리 끔)"),
              C(CLIP, 191.00, 195.70, ours="말하는 창업자(샷 190.69~195.76, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "지분 경쟁(독설)", "audio": (345.71, 347.39), "en": "This deal sucks. I'm out.",
     "sub": ["이건 진짜 최악이야", "난 빠질게!"], "facts": ["f7"], "cap_at": [345.71, 346.75],
     "fx": "빨강 번쩍 — 벤치 지분 경쟁",
     "cuts": [C(CLIP, 345.71, 347.39, ours="말하는 투자자 본인(원본 샷 345.58~347.48)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁(거절)", "text": "그 말에 샤크들이 줄줄이 빠지는데 바바라만 손을 내밀었다는데",
     "tts": "그 말에 샤크들이 줄줄이 빠지는데, 바바라만 손을 내밀었다는데",
     "sub": ["그 말에 샤크들이", "줄줄이 빠지는데", "바바라만 손을 내밀었다는데"], "facts": ["f7", "f8"],
     "cuts": [C(CLIP, 350.80, 352.60, ours="빠지겠다고 말하는 투자자(원본 샷 350.75~352.65, 소리 끔)"),
              C(CLIP, 356.40, 359.00, ours="제안을 고민하는 바바라(샷 356.26~359.09 — 이름은 396초 Barbara offer 띠·원음으로 확인, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "결정(수락)", "audio": (418.66, 422.90), "en": "That is a fantastic offer. I would be happy to accept it.",
     "sub": ["정말 멋진 제안이에요", "기꺼이 받을게요!"], "facts": ["f8"], "cap_at": [418.66, 421.46],
     "fx": "초록 번쩍 — 성사",
     "cuts": [C(CLIP, 418.66, 422.90, ours="말하는 창업자 본인(원본 샷 417.88~422.96)")]},
    {"id": "N6", "kind": "나레", "beat": "결과(한마디)", "text": "결국 바바라와 손을 잡자 독설하던 샤크가 한마디 했다는데",
     "tts": "결국 바바라와 손을 잡자, 독설하던 샤크가 한마디 했다는데",
     "sub": ["결국 바바라와 손을 잡자", "독설하던 샤크가", "한마디 했다는데"], "facts": ["f8", "f9"],
     "cuts": [C(CLIP, 427.20, 429.80, 960, ours="무대로 나와 창업자에게 다가가는 바바라(원본 샷 427.13~429.86, 소리 끔)"),
              C(CLIP, 330.20, 332.80, ours="독설하던 투자자(샷 328.43~334.00, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "끝(되받기)", "audio": (435.12, 438.80), "en": "The fact that you got a deal is a Christmas miracle.",
     "sub": ["네가 투자받은 게", "크리스마스 기적이다!"], "facts": ["f9"], "cap_at": [435.12, 437.20],
     "cuts": [C(CLIP, 434.92, 436.15, cover=True, ours="말하는 투자자 본인(원본 샷 434.90~436.17 — 소리 = 이 줄 원음, 입 모양 0.2초 앞섬)"),
              C(CLIP, 436.20, 437.05, cover=True, ours="웃는 창업자와 바바라(샷 436.17~437.24 — 소리 = 투자자 원음 이어서 cover, 첫 자막 '네가 투자받은 게' 칸)"),
              C(CLIP, 438.30, 439.02, cover=True, ours="손 흔들며 말하는 투자자 본인(샷 437.24~439.04 중 바바라가 지나간 뒤 — 둘째 자막 '크리스마스 기적이다!' 칸)"),
              C(CLIP, 308.40, 309.25, cover=True, ours="그 투자자 얼굴(샷 308.31~310.91 — 소리 = 원음 이어서 cover)")]},
    {"id": "N7", "kind": "나레", "beat": "끝(결과)", "text": "한여름 눈 가루 하나로 결국 샤크까지 잡았다는데",
     "tts": "한여름 눈 가루 하나로, 결국 샤크까지 잡았다는데",
     "sub": ["한여름 눈 가루 하나로", "결국 샤크까지", "잡았다는데"], "facts": ["f8"],
     "cuts": [C(CLIP, 442.20, 446.20, 960, ours="무대 뒤로 걸어 나오는 창업자(원본 샷 440.47~448.98, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/25편_SnowInSeconds/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 25편 Snow in Seconds — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "가루에 물만 부으면", "line2": "눈이 생긴다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 96.70~98.46 'It's a Christmas miracle.'(스피치매틱스 enhanced 영어 — 투자자 원음, 이름은 자막에 안 씀) · 화면은 같은 원본 143.2초 투자자 손에 들린 눈 그릇(cover)", "url": U + CLIP + "&t=96s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 39.88~45.16 'With snow in seconds, we bring the magic of snow indoors.' · 95.38~96.54 'It falls like snow.' · 화면 98~102 무대에 눈이 내림", "url": U + CLIP + "&t=39s", "kind": "방송 원음+화면"},
    "f3": {"text": "원본 46.76~58.48 'Just take one small scoop of our powder, add water. And watch as it instantly grows into fluffy white snow.' · 화면 48~57 시연", "url": U + CLIP + "&t=46s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 137.36~144.92 'take your water and pour it up about 80 to 90% of the way.' 'Oh, wow. There it goes. Woo! It's growing.' 'Oh that's cool.' · 화면 138~145 투자자가 직접 함", "url": U + CLIP + "&t=137s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 59.60~63.54 'That looks and feels real but never melts' · 68.90~71.18 'Snow in seconds is cold to the touch.' · 155.32~157.72 'It feels very powdery and soft.'", "url": U + CLIP + "&t=59s", "kind": "방송 원음"},
    "f6": {"text": "원본 175.36~199.55 'We've been selling it for 15 years' · 'in 15 years, out of our one stall garage with my children and I packaging and shipping every single bag, we have sold $2 million.' — 금액은 대본에 안 씀", "url": U + CLIP + "&t=175s", "kind": "방송 원음"},
    "f7": {"text": "원본 321.31~326.03 '…for those reasons solely, I'm out.' · 345.71~347.39 'This deal sucks. I'm out.' · 349.67~352.75 'not investable for me. I'm out.' · 396.58~401.30 '…so I'm out.' (네 명)", "url": U + CLIP + "&t=321s", "kind": "방송 원음+화면"},
    "f8": {"text": "원본 389.78~394.10 바바라 제안('So I'll take a flyer on this…') · 396~398 띠 'Barbara's offer' · 418.66~423.02 'That is a fantastic offer. I would be happy to accept it.' — 금액·지분은 대본에 안 씀", "url": U + CLIP + "&t=389s", "kind": "방송 원음+화면"},
    "f9": {"text": "원본 435.12~438.80 'The fact that you got a deal is a Christmas miracle.'", "url": U + CLIP + "&t=435s", "kind": "방송 원음+화면"},
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
        "topic": "Snow in Seconds(스노우 인 세컨즈) — 물만 부으면 몇 초 만에 눈이 되는 가루. 미네소타 창업자가 15년 동안 차고에서 아이들과 포장해 팜, 무대 눈 시연 → 독설 샤크 '최악' → 줄줄이 빠짐 → 바바라와 성사 → '크리스마스 기적'",
        "product": "Snow in Seconds instant snow powder(물만 부으면 눈이 되는 가루)",
        "bench": {"id": "N2SNg-9RDEc", "channel": "해외쇼츠 @foreignshowshow", "title": "It's Snowing Inside the House?! (화면 제목: 한여름에 집에서 / 눈이 내린다고?!)",
                  "dur": 46.2, "views": 1100000, "window": [0, 434, 1080, 1052], "cut_median": 1.6, "_cut_median_how": "2초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '33% 지분에 7400만원 투자'(금액·지분) → 금액 없이 거절·성사만",
            "벤치 '아이들에게도 안전하다고'(안전성 주장) — 쓰지 않음",
            "벤치 16~23초 남의 욕조 영상(아이 얼굴) — 이 원본 밖 → 원본 무대 시연으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '한여름에 집에서 / 눈이 내린다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [311, 765, 768, 1018], "target_what": "투자자 손에 들린 눈 그릇 — 143.2·143.45초 원본 프레임 눈 측정(창 크롭 [651,0,1109,1080] 안 x 970~1440·y 340~600, ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품으로 만든 눈) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 16.5 해답"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 24.2 '절대 녹지 않고'"},
    {"line": "O4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 지분 경쟁"},
    {"line": "O5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "성사"},
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
    mat = {"_note": "샥탬스토리 25편 Snow in Seconds 재료 계획. 창 1080x1052(벤치 N2SNg-9RDEc, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(8X9tQmmGUJU_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Kevin HATES Snow In Seconds Product", "해상도": "1920x1080 30fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 490.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(86~95·314~318·396~399·410~412초) 안 씀 · 470초 뒤 끝 화면 안 씀 · 무대 'SNOW IN SECONDS' 글 = 제품 브랜드"}},
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
