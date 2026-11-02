# -*- coding: utf-8 -*-
"""샥탬스토리 31편 Moki Doorstep — 벤치 해외쇼츠 JPsGZJ4nwz8(「방송 나와서 바로 40억을?!」 30.3만, 53.8초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/31편_MokiDoorstep/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Shark Tank Global 공식 'Things Take A WILD Turn With Moki Doorstep! | Shark Tank US' cMYX4FfMT1A, 1080p 24fps,
영어 원음 140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/31편_MokiDoorstep/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청 띠(19~27초 'ALYSSA & ZACH BROWN'·'Seeking $150k')·제안 띠 구간은 안 쓴다. 쓰는 컷은 띠 없음.
★무대 차(흰 SUV) 앞 상표·카약 상표가 크게 보이는 구도는 안 쓴다(체크리스트 ⑤) — 문·발판 근접과 사람 위주로 자른다.
★원음 줄 화면 = 말하는 본인 또는 사람 없는 손·발판 화면(cover) — 다른 투자자 얼굴 위에 남의 말을 얹지 않는다(98 #174 ⑤).
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '백만장자'·'월 1억'·'40억'(금액)·'거래 불발 뒤 대형 회사 인수'(원본 결말과 다름 — 원본은 방송에서 회사 통째 인수 제안 성사)는 쓰지 않는다.
2,200파운드를 버틴다는 걸쇠 강도(안전성 주장)는 대본에 안 쓴다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/31편_MokiDoorstep/src")
CLIP = "cMYX4FfMT1A"
FILES = {CLIP: ("cMYX4FfMT1A.mp4", 0.0, (1920, 1080)), "z47": ("z47.mp4", 47.30, (1920, 1080))}   # z47 = 47.30~50.30 를 1.2배 천천히 다가가는 사본(멈춤 0.63초 대응, zoomclip.py)
AUDIO = "cMYX4FfMT1A_audio.m4a"        # 영어 원음(140 — 더빙 트랙 없음, yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Shark Tank Global 원본: 고정 로고 없음 · 19~27초 이름/요청 띠·제안 띠는 안 쓰는 구간 · 끝 화면 안 씀.
H_DEF = {CLIP: 1080, "z47": 1080}
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (126.17, 127.93), "en": "This is... This is a great idea.",
     "sub": ["이거…", "진짜 기막힌 아이디어다!"], "facts": ["f1"], "cap_at": [126.17, 126.65], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 받침대 위 발판) — 벤치 0~1.0 감탄하는 투자자(우리는 물건 원)",
     "cuts": [C(CLIP, 71.20, 72.10, 960, ours="받침대 위에 놓인 발판(원본 샷 69.49~73.53, 사람 없음 — 0초 원 = 발판, 소리 = 투자자 원음 cover)", cover=True),
              C(CLIP, 127.07, 127.93, 1000, ours="투자자 손에 든 발판 샘플 근접(원본 샷 125.54~128.09, 얼굴 없음 — 소리 = 이 시각 투자자 원음)")]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "키 작은 아내가 차 지붕에 카약을 혼자 못 올려서 주말마다 애를 먹었다는데",
     "tts": "키 작은 아내가, 차 지붕에 카약을 혼자 못 올려서, 주말마다 애를 먹었다는데",
     "sub": ["키 작은 아내가", "차 지붕에 카약을", "혼자 못 올려서", "주말마다 애를 먹었다는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5",
     "cuts": [C("z47", 47.30, 50.30, 1055, ours="카약 실은 차 옆에 선 부부 — 1.2배 천천히 다가가는 사본 z47(차 앞·뒤 상표 자리는 창 밖)(원본 샷 47.09~52.51, 소리 끔)"),
              C(CLIP, 53.00, 55.90, ours="말하는 부부(원본 샷 52.51~58.39, 띠 없음, 소리 끔)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "그래서 만든 게 차 문 고리에 거는 발판인데, 거는 데 딱 1초면 된다는데",
     "tts": "그래서 만든 게, 차 문 고리에 거는 발판인데, 거는 데 딱 일 초면 된다는데",
     "sub": ["그래서 만든 게", "차 문 고리에 거는 발판인데", "거는 데 딱 1초면 된다는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 6.4",
     "cuts": [C(CLIP, 75.40, 78.20, ours="발판을 들고 차 문 앞에 선 창업자(원본 샷 75.03~78.54, 소리 끔)"),
              C(CLIP, 100.50, 102.20, 960, ours="받침대에 놓인 발판 제품(원본 샷 100.39~102.31, 사람 없음, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(시연)", "audio": (85.81, 87.29), "en": "And I'm up just as quick.",
     "sub": ["올라가는 것도", "이렇게 금방이에요!"], "facts": ["f3"], "cap_at": [85.81, 86.53], "style": "원음반응_크게",
     "cuts": [C(CLIP, 85.81, 87.29, ours="발판을 밟고 차 옆으로 올라선 창업자 본인(원본 샷 85.54~87.38 — 화면초 = 소리초)")]},
    {"id": "N3", "kind": "나레", "beat": "계기(잉?)", "text": "알고 보니 남편이 소방관이라, 사고 난 차 문을 뜯을 때마다 보던 그 고리에서 떠올렸다는데",
     "tts": "알고 보니 남편이 소방관이라, 사고 난 차 문을 뜯을 때마다, 보던 그 고리에서 떠올렸다는데",
     "sub": ["알고 보니 남편이 소방관이라", "사고 난 차 문을 뜯을 때마다", "보던 그 고리에서 떠올렸다는데"], "facts": ["f4"],
     "cuts": [C(CLIP, 157.30, 160.10, 650, ours="차 문을 열어 고리를 보여 주는 창업자(원본 샷 156.78~160.20, 소리 끔)"),
              C(CLIP, 160.30, 163.90, 960, ours="문 고리 근접(원본 샷 160.20~164.00, 사람 없음, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "반응", "audio": (87.49, 90.05), "en": "Wow. Thinks of these things. That's smart.",
     "sub": ["와…", "이런 걸 생각해 내다니", "똑똑하네!"], "facts": ["f5"], "cap_at": [87.49, 88.01, 89.41],
     "cuts": [C(CLIP, 81.10, 82.49, 960, ours="문 고리에 발판을 거는 손 근접(원본 샷 81.04~83.33, 사람 얼굴 없음 — 소리 = 투자자 원음 cover)", cover=True),
              C(CLIP, 131.30, 132.47, 960, ours="문 고리에 발판을 거는 손 근접(원본 샷 130.42~132.59, 사람 얼굴 없음 — 소리 = 투자자 원음 cover)", cover=True)]},
    {"id": "N4", "kind": "나레", "beat": "결과", "text": "결국 회사를 통째로 사겠다는 샤크까지 나왔다는데",
     "tts": "결국, 회사를 통째로 사겠다는 샤크까지 나왔다는데",
     "sub": ["결국", "회사를 통째로 사겠다는", "샤크까지 나왔다는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 173.10, 177.90, 1055, ours="무대 위 부부(원본 샷 173.01~178.01, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/31편_MokiDoorstep/work/render/render_info.json")


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
                          "url": f"https://www.youtube.com/watch?v={CLIP if vid == 'z47' else vid}", "src_orig_span": [a, round(a + dur, 3)], "ss": ss,
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
    d.text((8, 8), f"샥탬스토리 31편 Moki Doorstep — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "지붕이 안 닿는 아내", "line2": "남편이 만든 발판?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 126.17~127.93 'This is. This is a great idea.'(투자자 원음 — 이름은 자막에 안 씀) · 화면 = 0~0.9초 받침대 위 발판(71.2초, cover) → 127.07~ 투자자 손에 든 발판 샘플(얼굴 없음)", "url": U + CLIP + "&t=126s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 26.44~58.60 'Sharks, at a mere five feet tall … We are an outdoor loving couple, and most weekends start off with us blowing up a kayak … Alyssa has never been able to easily secure the gear on the roof of a car.'", "url": U + CLIP + "&t=26s", "kind": "방송 원음"},
    "f3": {"text": "원본 65.36~87.29 'we've invented the Moki doorstep … This hooks on in one second to the striker of the vehicle, which is standard on most cars. And I'm up just as quick.'", "url": U + CLIP + "&t=79s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 148.47~170.07 'So I'm an emergency room nurse. Zach's a firefighter. … being a firefighter, we use the jaws of life. And we always try to open the door this way. And that bolt right there … So using that knowledge, I said, hey, we can create a device to step on it' — 강도(2,200파운드)는 안전성 주장이라 대본에 안 씀", "url": U + CLIP + "&t=148s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 87.49~90.05 'Wow. Thinks of these things. That's smart.'(투자자 원음 — 화면은 사람 없는 손·발판 근접 cover)", "url": U + CLIP + "&t=87s", "kind": "방송 원음"},
    "f6": {"text": "원본 424.40~445.32 'I will offer you right now $3 million for the entire company.' … 'Let's do it.' — 금액은 대본에 안 씀(앞 칼카피 N4 는 하이브리드에서 잘림)", "url": U + CLIP + "&t=424s", "kind": "방송 원음"},
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
        "topic": "Moki Doorstep(모키 도어스텝) — 차 문 고리(스트라이커)에 걸어 밟고 올라서는 지붕용 보조 발판. 키 작은 아내가 지붕에 카약을 못 올려서 → 문 고리에 1초 만에 거는 발판 → 소방관 남편이 구조 현장의 문 고리에서 떠올림 → 회사 통째 인수 제안",
        "product": "Moki Doorstep(차량 문 고리 걸이 발판)",
        "bench": {"id": "JPsGZJ4nwz8", "channel": "해외쇼츠 @foreignshowshow", "title": "방송 나와서 바로 40억을?! (화면 제목 같음)",
                  "dur": 53.8, "views": 303000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "1초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '순식간에 백만장자'·'40억'·'월 1억'(금액) → 쓰지 않음",
            "벤치 끝 '방송 후 거래는 불발됐지만 대형 회사가 인수'(원본 결말과 다름 — 원본 424~445초 방송 중 회사 통째 인수 성사) → 쓰지 않음",
            "원본 '2,200파운드를 버티는 걸쇠'(안전성 주장) → 쓰지 않음",
            "벤치 '가격이 비싸고 짝퉁이 판칠 것'(가격 얘기) → 쓰지 않음"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '방송 나와서 / 바로 40억을?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [292, 756, 838, 1019], "target_what": "받침대 위 발판(71.6초 프레임 눈 측정, 창 크롭 [405,0,1109,1080] 안 x150~430·y165~300 of 554 → 완성본 좌표) — fx_place fix 가 완성본 좌표로 다시 잼",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 7.5 제품 공개"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.5, 0.95], "color": "초록", "how": "auto", "why": "시연(올라섬)"},
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
    mat = {"_note": "샥탬스토리 31편 Moki Doorstep 재료 계획. 창 1080x1052(벤치 JPsGZJ4nwz8, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(cMYX4FfMT1A_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global(공식)", "제목": "Things Take A WILD Turn With Moki Doorstep! | Shark Tank US | Shark Tank Global", "해상도": "1920x1080 24fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 523.0, "받은 구간": "전체",
                      "남의 글자": "19~27초 이름/요청 띠·제안 띠 안 씀 · 끝 화면 안 씀 · 무대 'MOKI' 간판·티셔츠 = 이 회사 브랜드 · 무대 SUV 앞 상표가 크게 나오는 구도 안 씀"}},
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
