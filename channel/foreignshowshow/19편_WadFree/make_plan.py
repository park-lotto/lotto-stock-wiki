# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""샥탬스토리 19편 Wad-Free — 벤치 해외쇼츠 eQ8jfp6lU7M(「비싼 이불도 절대 / 안 말리게 하는 클립」 46만, 52.6초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/19편_WadFree/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(18편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Can Wad-Free Persuade The Sharks To Make An Offer?' pYFznP9V0SU, 1080p, 영어 원어 140-6)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/19편_WadFree/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt.
★Sony 원본 이름·요청 띠(110~113·115~117초)는 안 쓰는 구간. 쓰는 컷은 띠 없음 → 크롭 높이 1080.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝(15.70초)에서 자른다. 벤치의 '8억'·'3억'·'13억'(금액)은 쓰지 않는다(지분 %만).
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/19편_WadFree/src")
CLIP = "pYFznP9V0SU"
FILES = {CLIP: ("pYFznP9V0SU.mp4", 0.0, (1920, 1080))}
AUDIO = "pYFznP9V0SU_audio.m4a"        # 영어 원음(140-6 en-US original — 이 업로드엔 자동 더빙 트랙 6개가 있어 원어만 받음, 98 #176)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 이름/요청 띠(110~113·115~117초)는 안 쓰는 구간 · 590초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (126.45, 127.97), "en": "I sleep naked",
     "sub": ["난 잘 때 다 벗고 자요"], "facts": ["f1"], "cap_at": [126.45], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 케빈 손에 든 시트와 와드프리 클립) — 벤치 0~1.5 케빈 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 125.70, 127.22, 960, ours="케빈이 흰 시트에 끼운 와드프리 클립을 만지작거리며 말함(원본 샷 124.62~127.86 — 소리 = 이 줄 원음 cover, 같은 샷 0.75초 앞)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "묻지도 않은 잠버릇까지 털어놓은 이 투자자",
     "tts": "묻지도 않은 잠버릇까지 털어놓은 이 투자자",
     "sub": ["묻지도 않은", "잠버릇까지 털어놓은", "이 투자자"], "facts": ["f1"],
     "fx": "빨강 번쩍 — 벤치 1.6('내게 아무도 안 물어본 습관을')",
     "cuts": [C(CLIP, 129.85, 131.40, ours="데이먼드가 손으로 얼굴을 가리고 웃음(원본 샷 129.80~131.43, 소리 끔)"),
              C(CLIP, 131.47, 133.70, ours="로버트가 흰 시트를 들고 머리를 감싸며 웃음(샷 131.43~133.73, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "문제(질문)", "audio": (140.73, 145.81), "en": "Is this going to damage my fine Egyptian cotton when I'm jamming it up into this clip?",
     "sub": ["이 클립에 꽉 끼우면", "내 비싼 이집트 면 이불", "상하는 거 아니에요?"], "facts": ["f2"], "cap_at": [140.73, 142.25, 144.01],
     "fx": "초록 번쩍 — 벤치 6.0('이게 나의 비싼 이불을')",
     "cuts": [C(CLIP, 140.73, 143.52, ours="케빈이 시트를 쥐고 묻는 얼굴(원본 샷 140.67~143.54, 말하는 본인)"),
              C(CLIP, 143.60, 145.89, 960, cover=True, ours="반지 낀 손이 클립을 시트에 끼우는 근접(샷 143.54~145.95 — 소리 = 이 줄 원음 이어서)")]},
    {"id": "N2", "kind": "나레", "beat": "반전(질문 뜻)", "text": "근데 이 질문, 사실 제품이 안전한지 떠보려던 거였는데",
     "tts": "근데 이 질문, 사실 제품이 안전한지 떠보려던 거였는데",
     "sub": ["근데 이 질문", "사실 제품이 안전한지", "떠보려던 거였는데"], "facts": ["f3"],
     "cuts": [C(CLIP, 151.30, 153.28, ours="케빈이 클립을 손에 들고 살펴봄(원본 샷 151.22~153.32, 소리 끔)"),
              C(CLIP, 155.55, 158.05, ours="케빈이 클립을 들어 올려 봄(샷 155.46~158.09, 소리 끔)")]},
    {"id": "O3", "kind": "원음", "beat": "해답(창업자)", "audio": (146.01, 150.33), "en": "This is not going to damage your sheets if you use it properly.",
     "sub": ["제대로만 쓰시면", "시트 절대 안 상해요"], "facts": ["f3"], "cap_at": [146.01, 148.93],
     "fx": "초록 번쩍 — 벤치 18.0 '제대로만 끼우면'",
     "cuts": [C(CLIP, 146.01, 148.95, ours="창업자가 파란 시트에 끼운 클립을 들고 답함(원본 샷 145.95~148.98, 말하는 본인)"),
              C(CLIP, 149.02, 150.40, 960, cover=True, ours="파란 시트에 끼운 흰 클립 근접(샷 148.98~151.22 — 소리 = 이 줄 원음 이어서)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(원리)", "text": "세탁기 안에서 이불이 돌돌 말려 덜 빨리고 안 마르는 걸 막아 준다는 이 물건",
     "tts": "세탁기 안에서 이불이 돌돌 말려 덜 빨리고 안 마르는 걸 막아 준다는 이 물건",
     "sub": ["세탁기 안에서 이불이", "돌돌 말려 덜 빨리고", "안 마르는 걸", "막아 준다는 이 물건"], "facts": ["f4"],
     "fx": "초록 번쩍 — 벤치 20.0 제품 소개",
     "cuts": [C(CLIP, 98.65, 100.95, ours="와드프리 포장과 흰 클립(원본 샷 98.60~101.00, 소리 끔)"),
              C(CLIP, 101.05, 103.55, ours="와드프리 포장 근접(샷 101.00~103.60, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "해답(시연)", "audio": (88.71, 93.19), "en": "Then you transfer it to the dryer where it runs wad free.",
     "sub": ["건조기로 옮겨도", "하나도 안 엉켜요"], "facts": ["f4"], "cap_at": [88.71, 90.23],
     "cuts": [C(CLIP, 88.71, 91.42, ours="창업자가 세탁기 앞에서 시트를 꺼냄(원본 샷 88.02~91.46, 말하는 본인)"),
              C(CLIP, 91.50, 93.27, cover=True, ours="창업자가 펼쳐진 시트를 들어 보임(샷 91.46~93.36 — 소리 = 이 줄 원음 이어서)")]},
    {"id": "N4", "kind": "나레", "beat": "지분 경쟁", "text": "결국 로리와 케빈이 서로 데려가겠다고 맞붙었는데",
     "tts": "결국 로리와 케빈이 서로 데려가겠다고 맞붙었는데",
     "sub": ["결국 로리와 케빈이", "서로 데려가겠다고", "맞붙었는데"], "facts": ["f5"],
     "fx": "빨강 번쩍 — 벤치 39.0 지분 경쟁",
     "cuts": [C(CLIP, 399.92, 402.42, ours="케빈이 말함(원본 샷 399.87~402.47, 소리 끔)"),
              C(CLIP, 404.72, 407.25, ours="로리가 웃으며 말함(샷 404.67~407.31, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "결정(성사)", "audio": (547.62, 552.82), "en": "Lori, I love you, but Mr. Wonderful, I'm going to take your deal.",
     "sub": ["로리, 정말 좋지만", "미스터 원더풀,", "당신 제안 받을게요"], "facts": ["f5"], "cap_at": [547.62, 550.06, 551.66],
     "fx": "초록 번쩍 — 벤치 49.0 '거래할게요'",
     "cuts": [C(CLIP, 547.62, 552.80, ours="창업자가 두 손을 모으고 케빈을 고름(원본 샷 545.34~552.82, 말하는 본인)")]},
    {"id": "N5", "kind": "나레", "beat": "끝(결과)", "text": "결국 지분을 덜 가져가겠다는 케빈 손을 잡았다는데",
     "tts": "결국 지분을 덜 가져가겠다는 케빈 손을 잡았다는데",
     "sub": ["결국 지분을", "덜 가져가겠다는", "케빈 손을 잡았다는데"], "facts": ["f5"],
     "cuts": [C(CLIP, 560.58, 561.90, ours="데이먼드가 손뼉 치며 웃음(원본 샷 560.53~561.93, 소리 끔)"),
              C(CLIP, 561.98, 563.62, ours="케빈과 창업자가 포옹(샷 561.93~563.66, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/19편_WadFree/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 19편 Wad-Free — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "이불 돌돌 말림", "line2": "클립 하나로 끝?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 123.85~128.25 'Now here's what I'm concerned about. I sleep naked'(스피치매틱스 enhanced 영어, 케빈 오리어리 — 화면 124.6~127.9 케빈이 시트·클립을 들고 말함) · 129~133 데이먼드·로버트 웃음", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f2": {"text": "원본 133.21~137.45 'And I buy the most expensive Egyptian cotton' · 140.73~145.81 'Is this going to damage my fine Egyptian cotton when I'm jamming it up into this clip?'", "url": U + CLIP, "kind": "방송 원음"},
    "f3": {"text": "원본 146.01~150.33 'This is not going to damage your sheets if you use it properly.' — '안전한지 떠보려던 질문'은 벤치 해석을 우리 말로(질문 뒤 창업자가 안전성 답)", "url": U + CLIP, "kind": "방송 원음"},
    "f4": {"text": "원본 21.80~54.80 'tornado wad… burrito wad, where one sheet wraps itself around everything else… nothing inside dries' · 62.83~93.19 'Wad-Free for bed sheets… attaches to the four corners… Then you transfer it to the dryer where it runs wad free.' · 화면 98~103 포장", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f5": {"text": "원본 306.63~310.46 케빈 10% 제안 · 377.56~383.40 로리 25% 제안 · 474.27~478.39 케빈 'drop my equity take to 5%' · 536.62 로리 'The lowest I'll go is 20' · 547.62~552.82 'Lori, I love you, but Mr. Wonderful, I'm going to take your deal.' · 562 포옹 — 금액은 대본에 안 씀", "url": U + CLIP, "kind": "방송 원음+화면"},
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
        "topic": "Wad-Free(와드프리) — 침대 시트 네 귀퉁이에 끼우는 클립으로 세탁기·건조기 안에서 시트가 돌돌 말리는 걸 막는 제품. 케빈 '난 다 벗고 자는데 이집트 면이 상하냐' 질문 → 로리·케빈 경쟁 → 창업자가 케빈 선택",
        "product": "Wad-Free for Bed Sheets(와드프리)",
        "bench": {"id": "eQ8jfp6lU7M", "channel": "해외쇼츠 @foreignshowshow", "title": "The clip that keeps your bedding from tangling (화면 제목: 비싼 이불도 절대 / 안 말리게 하는 클립)",
                  "dur": 52.574, "views": 462000, "window": [0, 434, 1080, 1052], "cut_median": 1.3, "_cut_median_how": "0.5초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '8억 정도 벌었어요'·'3억 투자할게요'·'13억 회수할 때까지'(금액) → 금액 없이 지분 경쟁·결정만",
            "벤치 0초 케빈 얼굴 원 → R3 물건 원(케빈 손의 시트·클립)"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '비싼 이불도 절대 / 안 말리게 하는 클립'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [482, 1116, 638, 1291], "target_what": "케빈 손에 든 와드프리 클립(흰 플라스틱) — 125.9초 원본 프레임 눈 측정(원본 x 900~1060·y 700~880, 크롭 [405,0,1109,1080] ×0.974 → 완성본 좌표 · 시트 전체로 잡으면 원 525px 창 밖이라 클립만)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 1.6 '아무도 안 물어본 습관'"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 6.0 '이게 나의 비싼 이불을'"},
    {"line": "O3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 18.0 '제대로만 끼우면'"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 20.0 제품 소개"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 39.0 지분 경쟁"},
    {"line": "O5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 49.0 '거래할게요'"},
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
    mat = {"_note": "샥탬스토리 19편 Wad-Free 재료 계획. 창 1080x1052(벤치 eQ8jfp6lU7M, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(pYFznP9V0SU_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Can Wad-Free Persuade The Sharks To Make An Offer?", "해상도": "1920x1080 29.97fps (137) + 140-6 영어 원어(자동 더빙 6개는 안 씀)",
                      "길이": 616.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청 띠(110~113·115~117초) 안 씀 · 590초 뒤 끝 화면 안 씀 · 무대 'Wad-Free' 간판·포장 = 제품 브랜드"}},
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
