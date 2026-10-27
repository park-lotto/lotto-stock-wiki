# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""샥탬스토리 22편 Plufl — 벤치 해외쇼츠 rlYYyUPjrug(「강아지를 질투해서 / 만든 인간용 개침대?!」 100만, 43.0초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/22편_Plufl/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(18편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Shark Tank Global 공식 'Will The Sharks Sleep On Plufl? | Shark Tank US' TQw9ISabbhU, 1080p, 영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/22편_Plufl/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt.
★원본 이름·요청·제안 띠(147~153·314~317·410~414·429~431초)는 안 쓰는 구간. 쓰는 컷은 띠 없음 → 크롭 높이 1080.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '70만원'·'2억 8천만원'·'50억'(금액)과 원본 밖 화면(남의 광고·리뷰 영상)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/22편_Plufl/src")
CLIP = "TQw9ISabbhU"
FILES = {CLIP: ("TQw9ISabbhU.mp4", 0.0, (1920, 1080))}
AUDIO = "TQw9ISabbhU_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Shark Tank Global 원본: 고정 로고 없음 · 이름/요청/제안 띠(147~153·314~317·410~414·429~431초)는 안 쓰는 구간 · 480초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (123.41, 124.81), "en": "it's really comfortable.",
     "sub": ["이거 진짜 편하네"], "facts": ["f1"], "cap_at": [123.41], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 무대 위 회색 플러플 침대) — 벤치 0~1.0 투자자 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 388.00, 389.40, 554, ours="무대 위 회색 플러플 침대(원본 샷 387.85~390.19, 사람 없음 — 소리 = 침대에 누운 투자자 원음 'it's really comfortable.' cover, 말한 사람은 화면 밖 · 55초 공개 컷은 침대가 커서 원 856px 거절)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "아무 데서나 꿀잠 자는 큰 개가 부러웠던 대학생이 있었는데",
     "tts": "아무 데서나 꿀잠 자는 큰 개가 부러웠던, 대학생이 있었는데",
     "sub": ["아무 데서나 꿀잠 자는", "큰 개가 부러웠던", "대학생이 있었는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 1.0('강아지를 질투해서')",
     "cuts": [C(CLIP, 44.20, 47.50, 600, ours="강아지 방석에 엎드린 개 '키퍼'(원본 샷 44.11~47.61, 소리 끔)"),
              C(CLIP, 181.05, 183.50, ours="개가 부러웠던 사연을 말하는 창업자(샷 180.98~183.58, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(한 마디)", "audio": (64.73, 67.61), "en": "Because if you work like a dog, why not sleep like one?",
     "sub": ["개처럼 일하면", "개처럼 자야죠"], "facts": ["f3"], "cap_at": [64.73, 66.25],
     "cuts": [C(CLIP, 63.00, 65.88, cover=True, ours="플러플 침대 테두리 근접(원본 샷 62.83~67.43 — 소리 = 창업자 원음 cover, 말하는 사람은 화면 밖)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "그래서 아예 사람이 들어가 자는 개 침대를 만들어 버렸다는데",
     "tts": "그래서 아예, 사람이 들어가 자는 개 침대를 만들어 버렸다는데",
     "sub": ["그래서 아예", "사람이 들어가 자는", "개 침대를", "만들어 버렸다는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 3.0('사람을 위한 개 침대')",
     "cuts": [C(CLIP, 70.05, 73.10, 840, ours="창업자가 플러플 침대에 들어가 몸을 웅크림(원본 샷 69.97~73.21, 소리 끔)"),
              C(CLIP, 76.45, 78.20, ours="침대에 앉은 창업자 옆으로 개가 다가옴(샷 76.38~78.28, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "시연(꿀잠)", "audio": (87.69, 90.45), "en": "Doesn't he look cozy? I wouldn't want to wake him up.",
     "sub": ["편해 보이지 않아요?", "깨우기 미안할 정도예요"], "facts": ["f4"], "cap_at": [87.69, 89.21],
     "fx": "초록 번쩍 — 벤치 15.5('언제든 편하게')",
     "cuts": [C(CLIP, 86.25, 88.10, cover=True, ours="담요를 덮고 침대에서 자는 창업자(원본 샷 86.19~88.89 — 소리 = 다른 창업자 원음 cover)"),
              C(CLIP, 88.95, 89.86, 960, cover=True, ours="잠든 창업자 곁의 개(샷 88.89~90.39, 소리 = 이 줄 원음 이어서)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(차별점)", "text": "폭신한 테두리에 손발을 쏙 넣고 어디서든 낮잠을 잘 수 있다는데",
     "tts": "폭신한 테두리에 손발을 쏙 넣고, 어디서든 낮잠을 잘 수 있다는데",
     "sub": ["폭신한 테두리에", "손발을 쏙 넣고", "어디서든 낮잠을 잘 수 있다는데"], "facts": ["f4"],
     "cuts": [C(CLIP, 94.05, 96.70, 840, ours="침대 옆을 지나가는 개(원본 샷 93.99~96.76, 소리 끔)"),
              C(CLIP, 101.55, 104.20, ours="담요를 걷으며 일어나는 창업자(샷 101.50~104.27, 소리 끔)")]},
    {"id": "N4", "kind": "나레", "beat": "체험(샤크)", "text": "샤크들도 직접 누워 보더니 다들 일어날 생각을 안 했다는데",
     "tts": "샤크들도 직접 누워 보더니, 다들 일어날 생각을 안 했다는데",
     "sub": ["샤크들도 직접 누워 보더니", "다들 일어날 생각을", "안 했다는데"], "facts": ["f5"],
     "fx": "초록 번쩍 — 벤치 21.0('투자자들도 직접 체험')",
     "cuts": [C(CLIP, 115.40, 117.30, ours="투자자가 침대에 드러누움(원본 샷 115.32~117.35, 소리 끔)"),
              C(CLIP, 120.40, 122.40, ours="담요를 덮고 누운 투자자(샷 119.19~122.52, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "반응(투자자)", "audio": (133.46, 134.34), "en": "It's actually not bad.",
     "sub": ["생각보다 괜찮은데?"], "facts": ["f5"], "cap_at": [133.46],
     "cuts": [C(CLIP, 133.46, 134.34, 1200, ours="침대에 누운 다른 투자자(원본 샷 129.40~135.60, 말하는 본인)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁", "text": "결국 샤크 두 명이 같이 데려가겠다고 손을 내밀었는데",
     "tts": "결국 샤크 두 명이, 같이 데려가겠다고 손을 내밀었는데",
     "sub": ["결국 샤크 두 명이", "같이 데려가겠다고", "손을 내밀었는데"], "facts": ["f6"],
     "fx": "빨강 번쩍 — 벤치 지분 경쟁",
     "cuts": [C(CLIP, 403.20, 404.70, ours="제안하는 투자자(원본 샷 403.17~404.77, 소리 끔)"),
              C(CLIP, 404.80, 406.05, ours="함께 제안하는 로리(샷 404.77~406.11, 소리 끔)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(성사)", "audio": (446.03, 446.75), "en": "Congratulations.",
     "sub": ["축하해요!"], "facts": ["f6"], "cap_at": [446.03],
     "fx": "초록 번쩍 — 벤치 39.5 '투자자 둘을 선택'",
     "cuts": [C(CLIP, 446.03, 446.75, ours="창업자들과 투자자가 끌어안음(원본 샷 445.78~448.68)")]},
    {"id": "O7", "kind": "원음", "beat": "결정(반응)", "audio": (459.78, 460.99), "en": "I'm gonna take a nap.",
     "sub": ["난 이제 낮잠 자러 갈래"], "facts": ["f6"], "cap_at": [459.78],
     "cuts": [C(CLIP, 459.78, 460.99, ours="웃으며 말하는 투자자(원본 샷 459.76~461.79, 말하는 본인)")]},
    {"id": "N6", "kind": "나레", "beat": "끝(결과)", "text": "개가 부러워서 만든 침대 하나로 샤크 두 명을 잡았다는데",
     "tts": "개가 부러워서 만든 침대 하나로, 샤크 두 명을 잡았다는데",
     "sub": ["개가 부러워서 만든", "침대 하나로", "샤크 두 명을 잡았다는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 465.00, 468.80, ours="무대 뒤로 걸어 나오는 두 창업자(원본 샷 463.63~468.90, 소리 끔)"),
              C(CLIP, 472.30, 474.80, ours="무대 뒤 인터뷰하는 두 창업자(샷 469.14~480.15, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/22편_Plufl/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 22편 Plufl — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "사람이 들어가 자는", "line2": "개 침대가 있다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 122.57~124.81 'Shockingly, it's really comfortable.'(스피치매틱스 enhanced 영어 — 침대에 누운 투자자 원음, 이름은 자막에 안 씀) · 화면은 같은 원본 388.0초 무대 위 침대(cover)", "url": U + CLIP + "&t=122s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 180.62~200.19 'throughout my time at school, I worked as a barista at a local college coffee shop where there lived a Great Dane… I found myself kind of jealous… Dog beds for humans.' · 화면 44~47 개 키퍼", "url": U + CLIP + "&t=180s", "kind": "방송 원음"},
    "f3": {"text": "원본 57.24~67.61 'It's a dog bed for humans… the world's first dog bed specifically designed for humans. Because if you work like a dog, why not sleep like one?'", "url": U + CLIP + "&t=57s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 69.21~90.45 'The soft pillow border allows you to tuck your hands and feet inside… turn any place into a napping space… Doesn't he look cozy? I wouldn't want to wake him up.' · 화면 69~104 시연", "url": U + CLIP + "&t=69s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 100.97~136.36 샤크들이 직접 누워 봄 'Shockingly, it's really comfortable.'·'It's actually not bad.' · 화면 113~135", "url": U + CLIP + "&t=100s", "kind": "방송 원음+화면"},
    "f6": {"text": "원본 403.86~415.74 '200,000 you asked for for 20%… The two of us together.'(화면 띠 'Mark & Lori's offer' 410~414초) · 436.10~446.75 성사·'Congratulations.' · 459.71~460.99 'I'm gonna take a nap.' · 466.07~472.75 'got a deal from Mark and Laurie' — 금액은 대본에 안 씀", "url": U + CLIP + "&t=403s", "kind": "방송 원음+화면"},
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
        "topic": "Plufl(플러플) — 사람이 들어가 자는 개 침대. 카페에서 일하며 큰 개를 부러워한 대학생이 만듦, 샤크들이 직접 누워 봄 → 마크·로리 공동 제안 → 성사",
        "product": "Plufl dog bed for humans(플러플 사람용 개 침대)",
        "bench": {"id": "rlYYyUPjrug", "channel": "해외쇼츠 @foreignshowshow", "title": "강아지를 질투해서 만든 인간용 개침대?! (화면 제목: 강아지를 질투해서 / 만든 인간용 개침대?!)",
                  "dur": 43.05, "views": 1000000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "0.5초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '가격 70만원'·'약 2억 8천만원'·'목표 매출 50억'(금액) → 금액 없이 공동 제안·결정만",
            "벤치 1~20·26~31초 남의 광고·리뷰 영상 — 이 원본 밖 → 원본 안 시연으로",
            "벤치 0초 투자자 얼굴 원 → R3 물건 원(무대 위 플러플 침대)"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '강아지를 질투해서 / 만든 인간용 개침대?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [432, 1060, 836, 1342], "target_what": "무대 위 회색 플러플 침대 — 388.0초 원본 프레임 눈 측정(창 크롭 [0,0,1108,1080] 안 x 436~866·y 636~940, ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 1.0 '강아지를 질투해서'"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 3.0 '사람을 위한 개 침대'"},
    {"line": "O3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 15.5 '언제든 편하게'"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 21.0 '투자자들도 직접 체험'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 지분 경쟁"},
    {"line": "O6", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 39.5 '투자자 둘을 선택'"},
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
    mat = {"_note": "샥탬스토리 22편 Plufl 재료 계획. 창 1080x1052(벤치 rlYYyUPjrug, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(TQw9ISabbhU_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global(공식)", "제목": "Will The Sharks Sleep On Plufl? | Shark Tank US | Shark Tank Global", "해상도": "1920x1080 29.97fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 511.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(147~153·314~317·410~414·429~431초) 안 씀 · 480초 뒤 끝 화면 안 씀 · 옷·간판 'Plufl' = 제품 브랜드"}},
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
