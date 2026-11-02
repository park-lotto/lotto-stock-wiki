# -*- coding: utf-8 -*-
"""샥탬스토리 18편 LUCY 드로잉 도구 — 벤치 해외쇼츠 0HbV-PW3ivw(「이것만 있으면 그림을 / 잘 그릴 수 있다고?!」 410만, 54.8초) 줄 단위 칼카피 (관제 097, 2026-10-27).

    PYTHONUTF8=1 py channel/foreignshowshow/18편_LUCY/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(17편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Entrepreneur From Season 2 Is Back With LUCIDArt Product' 49r_YvwH6lw, 1080p, 영어 원어 140-6)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/18편_LUCY/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt.
★Sony 원본은 이름·제안 띠(139~147·600~641초)가 화면 아래에 있다 → 그 시각 컷은 크롭 높이 900(y 0~900), 나머지는 1080.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝(약 15.6초)에서 자른다. 벤치의 '140억'·'18만원'·'3만 5천원'·'32억'·'4억'(금액)과 원본 밖 화면(정원 광고·빔프로젝터·남의 그림 영상)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/18편_LUCY/src")
CLIP = "49r_YvwH6lw"
FILES = {CLIP: ("49r_YvwH6lw.mp4", 0.0, (1920, 1080))}
AUDIO = "49r_YvwH6lw_audio.m4a"        # 영어 원음(140-6 en-US original — 이 업로드엔 자동 더빙 트랙 6개가 있어 원어만 따로 받음, 98 #176)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 이름/제안 띠(139~147·600~641초)만 아래에 → 그 시각은 h=900. 673초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (189.52, 190.68), "en": "Isn't that amazing?",
     "sub": ["놀랍지 않아요?"], "facts": ["f1"], "cap_at": [189.52], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 무대 TV 홍보 영상 속 루시 본체) — 벤치 0~1.0 창업자 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 99.90, 101.06, 760, 0, 1080, ours="무대 TV 홍보 영상: 과일 그릇 앞 루시 본체(검은 거울·렌즈 머리)(원본 샷 98.40~112.55 · 101.7초는 본체가 너무 커서 원이 창에 안 들어감 — 소리 = 케빈 원음 'Isn't that amazing?' cover, 말한 사람은 화면 밖)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "그림 못 그리는 사람도 바로 화가로 만들어 준다는 이 물건",
     "tts": "그림 못 그리는 사람도 바로 화가로 만들어 준다는 이 물건",
     "sub": ["그림 못 그리는 사람도", "바로 화가로", "만들어 준다는 이 물건"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 1.5('140억 벌었다는 이 제품')",
     "cuts": [C(CLIP, 120.10, 122.30, 960, ours="홍보 영상: 연필로 과일 스케치를 그려 나가는 손(원본 샷 118.32~126.83)"),
              C(CLIP, 122.35, 124.60, 960, ours="같은 샷 이어서 — 스케치가 채워짐")]},
    {"id": "O2", "kind": "원음", "beat": "해답(원리)", "audio": (103.48, 107.48), "en": "Look down to the viewing window and draw over the reflected image.",
     "sub": ["들여다보는 창을 보면서", "비친 모습 위에", "따라 그리면 돼요"], "facts": ["f3"], "cap_at": [103.48, 105.52, 106.48],
     "fx": "초록 번쩍 — 벤치 7.0('이 거울과 렌즈로 구성된')",
     "cuts": [C(CLIP, 107.55, 109.80, 960, 30, 900, ours="무대 TV 홍보 영상: 비친 과일 그림 위로 펜을 따라 그림(샷 98.40~112.55 — 소리 = 창업자 원음 cover, 화면 밖)", cover=True),
              C(CLIP, 109.85, 111.60, 960, 30, 900, ours="같은 홍보 영상 이어서 — 비친 그림과 손 그림이 겹쳐 보임(cover)", cover=True)]},
    {"id": "N2", "kind": "나레", "beat": "해답(차별점)", "text": "몇백 년 전 거장들이 몰래 쓰던 도구를 되살린 거라는데",
     "tts": "몇백 년 전 거장들이 몰래 쓰던 도구를 되살린 거라는데",
     "sub": ["몇백 년 전 거장들이", "몰래 쓰던 도구를", "되살린 거라는데"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 16.0('수세기 전부터 거장들이')",
     "cuts": [C(CLIP, 166.20, 168.40, 900, ours="투자자 케빈이 루시로 종이에 그려 봄 — 위에서 본 손(원본 샷 166.10~170.17, 소리 끔)"),
              C(CLIP, 170.50, 172.30, ours="케빈이 루시 눈대 창을 들여다봄(샷 170.17~172.41, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "시연(투자자)", "audio": (184.04, 188.92), "en": "I'm just tracing around the shark. Observe, Lori. How easy that was.",
     "sub": ["그냥 상어를 따라 그리는 거예요", "봐요 로리, 이렇게 쉬워요"], "facts": ["f5"], "cap_at": [184.04, 186.72],
     "cuts": [C(CLIP, 184.20, 185.86, 900, ours="케빈이 루시로 상어를 따라 그림 — 위에서 본 손(샷 184.18~185.89, 말하는 본인 케빈 · 앞 0.16초는 다른 샷이라 화면만 0.16초 뒤에서, 소리 = 이 줄 원음 cover)", cover=True),
              C(CLIP, 185.92, 188.92, 1000, cover=True, ours="무대 와이드: 케빈과 창업자, 뒤 'LUCY' 화면(샷 185.89~189.19)")]},
    {"id": "N3", "kind": "나레", "beat": "반전(창업자)", "text": "알고 보니 이 창업자 예전에 멀미 턱받이로 나왔던 그 사람이었는데",
     "tts": "알고 보니 이 창업자, 예전에 멀미 턱받이로 나왔던 그 사람이었는데",
     "sub": ["알고 보니 이 창업자", "예전에 멀미 턱받이로", "나왔던 그 사람이었는데"], "facts": ["f6"],
     "fx": "빨강 번쩍 — 벤치 4.5 반전 자리",
     "cuts": [C(CLIP, 45.00, 47.30, ours="창업자가 턱받이를 목에 걸고 웃음(원본 샷 43.18~47.41, 소리 끔)"),
              C(CLIP, 67.20, 69.10, 960, ours="옛 제품 '멀미 턱받이'를 건 마네킹(샷 67.10~69.24, 소리 끔)")]},
    {"id": "N4", "kind": "나레", "beat": "지분 경쟁", "text": "결국 샤크 넷이 줄줄이 빠지고 데이먼드 혼자 남았는데",
     "tts": "결국 샤크 넷이 줄줄이 빠지고 데이먼드 혼자 남았는데",
     "sub": ["결국 샤크 넷이", "줄줄이 빠지고", "데이먼드 혼자 남았는데"], "facts": ["f7"],
     "fx": "초록 번쩍 — 벤치 41.5 지분 컷",
     "cuts": [C(CLIP, 606.00, 608.40, y=0, h=900, ours="데이먼드가 손짓하며 말함(원본 샷 605.91~608.47, 소리 끔)"),
              C(CLIP, 612.00, 615.10, 1200, 0, 900, ours="창업자가 설명함(샷 611.54~615.21, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "지분 경쟁(원음)", "audio": (627.67, 628.87), "en": "17.5.",
     "sub": ["17.5%!"], "facts": ["f7"], "cap_at": [627.67],
     "cuts": [C(CLIP, 627.67, 628.87, y=0, h=900, ours="데이먼드가 17.5% 역제안(말하는 본인, 샷 627.26~629.33)")]},
    {"id": "O5", "kind": "원음", "beat": "결정(역제안)", "audio": (632.91, 636.11), "en": "The highest I can go is 15.",
     "sub": ["제가 줄 수 있는 최대는", "15%예요"], "facts": ["f7"], "cap_at": [632.91, 635.31],
     "cuts": [C(CLIP, 632.91, 636.11, y=0, h=900, ours="창업자가 15% 제시(말하는 본인, 샷 629.33~636.17)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(성사)", "audio": (638.87, 640.47), "en": "That's exactly where I wanted to land.",
     "sub": ["딱 내가 원하던 거야!"], "facts": ["f7"], "cap_at": [638.87],
     "fx": "초록 번쩍 — 벤치 50.5 '그게 내가 원하던 거였어'",
     "cuts": [C(CLIP, 638.87, 640.47, y=0, h=900, ours="데이먼드가 웃으며 받아들임(말하는 본인, 샷 636.17~641.17)")]},
    {"id": "N5", "kind": "나레", "beat": "끝(결과)", "text": "멀미 턱받이 아저씨가 그림 도구 하나로 샤크를 잡았다는데",
     "tts": "멀미 턱받이 아저씨가 그림 도구 하나로 샤크를 잡았다는데",
     "sub": ["멀미 턱받이 아저씨가", "그림 도구 하나로", "샤크를 잡았다는데"], "facts": ["f7"],
     "cuts": [C(CLIP, 646.10, 648.30, 960, ours="창업자와 데이먼드 포옹(원본 샷 645.98~648.35, 소리 끔)"),
              C(CLIP, 648.40, 649.65, ours="창업자가 웃음(샷 648.35~649.68, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/18편_LUCY/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 18편 LUCY — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "그림 못 그려도", "line2": "화가가 된다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 184.04~190.68 'I'm just tracing around the shark. Observe, Lori. How easy that was. Isn't that amazing?'(스피치매틱스 enhanced 영어, 케빈 오리어리) — 화면 184~192 케빈이 루시로 상어를 따라 그림", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f2": {"text": "원본 95.40~101.52 'At Lucid Art, we sell the Lucy drawing tool that can make anyone an artist and any artist a master.'", "url": U + CLIP, "kind": "방송 원음"},
    "f3": {"text": "원본 101.56~109.68 'Whatever you want to draw in front of the Lucy, look down to the viewing window and draw over the reflected image to start your masterpiece in minutes.' · 화면 98~126 무대 TV 홍보 영상", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f4": {"text": "원본 109.96~117.76 'The Lucy is my reinvention of a classic art tool that has been used by artists for centuries. That's right, the old masters had help.' · 170.20~176.08 'camera lucida, which was first patented in like 1807'", "url": U + CLIP, "kind": "방송 원음"},
    "f5": {"text": "원본 184.04~188.92 'I'm just tracing around the shark. Observe, Lori. How easy that was.'", "url": U + CLIP, "kind": "방송 원음"},
    "f6": {"text": "원본 43.12~60.12 'this isn't even the first time I've been on Shark Tank… It's Les Cookson, the carsick bib guy from season two… The carsick bib is the smart hands free barf bag for kids.' · 화면 43~47 턱받이를 건 창업자·64~69 마네킹", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f7": {"text": "원본 433~532 투자자 넷 'I'm out' · 592.43~595.91 'I'll offer you the $300,000 for 20%.' · 620.67 'Would you do it for 12%?' · 627.67 '17.5.' · 632.91~636.11 'the highest I can go is 15.' · 638.87~640.47 'That's exactly where I wanted to land.' · 646~650 포옹 — 금액은 대본에 안 씀", "url": U + CLIP, "kind": "방송 원음+화면"},
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
        "topic": "LUCY 드로잉 도구(루시 — 거울·렌즈로 앞의 물건이 종이 위에 겹쳐 보여 따라 그리게 해 주는 카메라 루시다를 되살린 그림 도구) — 시즌2 '멀미 턱받이' 창업자가 다시 나옴, 케빈이 직접 그려 봄 → 넷 거절·데이먼드와 15% 거래",
        "product": "LUCY drawing tool(루시 드로잉 도구)",
        "bench": {"id": "0HbV-PW3ivw", "channel": "해외쇼츠 @foreignshowshow", "title": "Can this thing actually make you a pro at drawing?! (화면 제목: 이것만 있으면 그림을 / 잘 그릴 수 있다고?!)",
                  "dur": 54.766, "views": 4100000, "window": [0, 434, 1080, 1052], "cut_median": 1.2, "_cut_median_how": "1초 시트 눈 측정(컷 약 45) — 10-27"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '140억'·'가격 18만원'·'제작비 3만 5천원'·'1년간 32억'·'4억 투자'(금액) → 금액 없이 기능·지분만",
            "벤치 2~5초 정원 광고·빔프로젝터 비교·남의 그림 영상 — 이 원본 밖 → 원본 안 홍보 영상·케빈 시연으로",
            "벤치 0초 창업자 얼굴 원 → R3 물건 원(루시 본체)"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '이것만 있으면 그림을 / 잘 그릴 수 있다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [297, 565, 648, 931], "target_what": "무대 TV 홍보 영상 속 루시 본체(검은 거울·렌즈 머리) — 99.95초 원본 프레임 눈 측정(원본 x 510~870·y 135~510, 크롭 [205,0,1109,1080] ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 1.5 '140억 벌었다는 이 제품'"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 7.0 '이 거울과 렌즈로'"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 16.0 '수세기 전부터 거장들이'"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "반전 자리"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 41.5 지분 컷"},
    {"line": "O6", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 50.5 '그게 내가 원하던 거였어'"},
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
    mat = {"_note": "샥탬스토리 18편 LUCY 재료 계획. 창 1080x1052(벤치 0HbV-PW3ivw, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(49r_YvwH6lw_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Entrepreneur From Season 2 Is Back With LUCIDArt Product", "해상도": "1920x1080 29.97fps (137) + 140-6 영어 원어(자동 더빙 6개는 안 씀)",
                      "길이": 692.3, "받은 구간": "전체",
                      "남의 글자": "이름/제안 띠(139~147·600~641초) 시각 컷은 크롭 높이 900 · 673초 뒤 끝 화면 안 씀 · 무대 'LUCY' 화면·홍보 영상 = 제품 브랜드"}},
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
