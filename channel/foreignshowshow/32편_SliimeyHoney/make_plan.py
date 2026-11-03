# -*- coding: utf-8 -*-
"""샥탬스토리 32편 Sliimey Honey — 벤치 해외쇼츠 Lbct5sgnyjM(「스트레스 풀리는 슬라임 산다 vs 안산다」 52.5만, 51.5초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/32편_SliimeyHoney/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Homemade Slime Slimey Honey Entrepreneur Keeps Asking For More' AJTIEVJn7x4, 1080p 30fps,
영어 원음 140-7 'English (US) original (default)' — 자동 더빙 트랙 7개(de·es·fr·hi·id·it·pt)가 있어 yt-dlp -F 로 원어 번호를 골라 -f 137+140-7, 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/32편_SliimeyHoney/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청 띠(103~107초 'MARK LIN'·'Seeking $150k')·제안 띠 구간은 안 쓴다. 쓰는 컷은 띠 없음. 88초 'COME JOIN OUR SLIME' 글 화면 안 씀.
★원음 줄 화면 = 말하는 본인 또는 사람 없는 손·슬라임 화면(cover) — 다른 투자자 얼굴 위에 남의 말을 얹지 않는다(98 #174 ⑤).
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '스트레스까지 싹 풀린다'·원본 'stress relieving'·'anxiety relieving'(효능)·'먹어도 안 죽는다'(안전성)·
매출·마진·지분 숫자(금액)는 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/32편_SliimeyHoney/src")
CLIP = "AJTIEVJn7x4"
FILES = {CLIP: ("AJTIEVJn7x4.mp4", 0.0, (1920, 1080))}
AUDIO = "AJTIEVJn7x4_audio.m4a"        # 영어 원음(140-7 'English (US) original (default)' — 더빙 트랙 7개 중 원어, yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 103~107초 이름/요청 띠·제안 띠는 안 쓰는 구간 · 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (224.09, 228.61), "en": "I mean, can you help me? I'm slimed. Yeah. What do I do?",
     "sub": ["이거 좀 도와줘…", "완전 슬라임 범벅!", "어떡해?"], "facts": ["f1"], "cap_at": [224.09, 225.37, 228.09], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 투자자 두 손에 엉겨 붙은 흰 슬라임) — 벤치 0~1.0 슬라임 든 투자자(우리는 물건 원)",
     "cuts": [C(CLIP, 235.60, 236.80, 960, ours="두 손에 엉겨 붙은 흰 슬라임 근접(원본 샷 235.47~237.94, 얼굴 없음 — 소리 = 투자자 원음 cover)", cover=True),
              C(CLIP, 225.29, 228.61, ours="슬라임 묻은 손을 들고 말하는 투자자 본인(원본 샷 223.86~229.10 — 화면초 = 소리초)")]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "열일곱 살 고등학생이 코로나 때 집에 갇혀서 차고에서 만든 슬라임인데",
     "tts": "열일곱 살 고등학생이, 코로나 때 집에 갇혀서, 차고에서 만든 슬라임인데",
     "sub": ["열일곱 살 고등학생이", "코로나 때 집에 갇혀서", "차고에서 만든 슬라임인데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.5",
     "cuts": [C(CLIP, 20.50, 24.00, ours="무대에서 말하는 창업자(원본 샷 16.75~27.86, 띠 없음, 소리 끔)"),
              C(CLIP, 140.05, 141.65, 960, ours="음식 모양 슬라임이 늘어선 진열대(원본 샷 139.97~141.71, 사람 없음, 소리 끔)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "진짜 음식처럼 생기고 냄새까지 똑같은데, 제일 잘 팔리는 게 바나나우유 슬라임이라는데",
     "tts": "진짜 음식처럼 생기고, 냄새까지 똑같은데, 제일 잘 팔리는 게, 바나나우유 슬라임이라는데",
     "sub": ["진짜 음식처럼 생기고", "냄새까지 똑같은데", "제일 잘 팔리는 게", "바나나우유 슬라임이라는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 7.7",
     "cuts": [C(CLIP, 52.80, 54.75, 960, ours="와플 모양 슬라임(원본 샷 52.75~54.82, 사람 없음, 소리 끔)"),
              C(CLIP, 54.88, 56.26, 960, ours="음식 이름 붙은 슬라임 통들(원본 샷 54.82~56.32, 사람 없음, 소리 끔)"),
              C(CLIP, 56.40, 58.70, 960, ours="여러 맛 슬라임 통 더미(원본 샷 56.32~58.76, 사람 없음, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(정체·잉?)", "audio": (62.88, 67.96),
     "en": "Growing up with Asian culture, one of my favorite snacks was always banana milk from Korean markets.",
     "sub": ["어릴 때부터 제일 좋아한 간식이", "한국 마트 바나나우유였거든요"], "facts": ["f4"],
     "cap_at": [62.88, 65.84], "style": "원음반응_크게",
     "cuts": [C(CLIP, 78.72, 79.98, 960, ours="바나나 장식 든 손바닥 근접(원본 샷 78.71~80.01, 사람 얼굴 없음 — 소리 = 창업자 원음 cover)", cover=True),
              C(CLIP, 64.14, 67.52, 1500, ours="슬라임 진열대 옆에서 말하는 창업자 본인(원본 샷 63.00~67.53 — 화면초 = 소리초)"),
              C(CLIP, 85.90, 86.34, 960, ours="슬라임 통 뚜껑들 근접(원본 샷 85.82~87.19, 사람 없음 — 소리 = 창업자 원음 cover)", cover=True)]},
    {"id": "O3", "kind": "원음", "beat": "반응", "audio": (108.92, 112.84), "en": "I can't wait to smell it because you made it sound like… They smell. Amazing.",
     "sub": ["냄새 너무 궁금해", "말만 들어도 맛있겠어", "냄새 진짜 좋아요", "대박!"], "facts": ["f5"], "cap_at": [108.92, 110.08, 111.72, 112.08],
     "cuts": [C(CLIP, 124.50, 125.10, 960, ours="슬라임 통 뚜껑을 여는 그 투자자의 손 근접(원본 샷 124.22~128.13, 얼굴 없음 — 소리 = 투자자 원음 cover)", cover=True),
              C(CLIP, 109.52, 112.84, ours="슬라임 통을 받아 든 말하는 투자자 본인(원본 샷 109.51~112.95 — 화면초 = 소리초)")]},
    {"id": "N3", "kind": "나레", "beat": "결과", "text": "엄마가 밤새 포장을 돕고 고등학교 친구들까지 차고로 출근한다는데",
     "tts": "엄마가 밤새 포장을 돕고, 고등학교 친구들까지, 차고로 출근한다는데",
     "sub": ["엄마가 밤새 포장을 돕고", "고등학교 친구들까지", "차고로 출근한다는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 131.70, 134.00, ours="손에 슬라임을 들고 말하는 창업자(원본 샷 131.53~134.13, 소리 끔)"),
              C(CLIP, 149.40, 151.50, ours="슬라임 진열대 옆 창업자(원본 샷 149.32~151.62, 소리 끔)"),
              C(CLIP, 95.00, 96.60, ours="말하는 창업자(원본 샷 94.76~98.87, 띠 없음, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/32편_SliimeyHoney/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 32편 Sliimey Honey — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "17살이 만든 슬라임", "line2": "한국 바나나우유 맛?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 224.09~228.61 'I mean, can you help me?' 'I'm slimed.' 'Yeah.' 'What do I do?'(투자자 원음 — 이름은 자막에 안 씀) · 화면 223.86~229.10 슬라임 묻은 손을 든 투자자 · 0초 화면은 같은 원본 235.6초 그 손 근접(cover)", "url": U + CLIP + "&t=222s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 2.92~9.48 'a teen entrepreneur who started his business while stuck at home during the pandemic lockdown' · 91.88~95 'I may only be 17' · 142.81~145.53 'I'm currently producing everything out of my house's garage.'", "url": U + CLIP + "&t=2s", "kind": "방송 원음"},
    "f3": {"text": "원본 42.48~52.96 'Slimy Honey Gourmet Next Level slime that looks and smells like your favorite foods.' · 67.96~72.64 'our best selling glossy slime banana milk'", "url": U + CLIP + "&t=42s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 62.88~72.64 'Growing up with Asian culture, one of my favorite snacks was always banana milk from Korean markets. So I turned that into our best selling glossy slime banana milk'", "url": U + CLIP + "&t=62s", "kind": "방송 원음+화면"},
    "f5": {"text": "원본 108.92~112.84 'I can't wait to smell it because you made it sound like.' 'They smell.' 'Amazing.'(투자자·창업자 원음 — 화면 109.51~112.95 = 슬라임 통을 받은 투자자)", "url": U + CLIP + "&t=108s", "kind": "방송 원음+화면"},
    "f6": {"text": "원본 145.69~158.45 'My mom does a lot to help me. She's spent all nighters with me packing orders. I actually hired many of my high school friends … They come Monday through Friday' · 결말 628.43~630.39 'Damon. I will take your offer.' — 금액·지분은 대본에 안 씀(앞 칼카피 N3 은 하이브리드에서 잘림)", "url": U + CLIP + "&t=145s", "kind": "방송 원음"},
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
        "topic": "Sliimey Honey(슬라이미 허니) — 진짜 음식처럼 생기고 향도 나는 수제 슬라임. 투자자가 슬라임 범벅 → 17살 고등학생이 코로나 때 차고에서 시작 → 제일 잘 팔리는 게 한국 마트 바나나우유 슬라임 → 엄마·친구들과 차고에서 포장 → 데이먼드와 성사",
        "product": "Sliimey Honey 음식 향 슬라임(바나나우유 슬라임)",
        "bench": {"id": "Lbct5sgnyjM", "channel": "해외쇼츠 @foreignshowshow", "title": "스트레스 풀린다는 슬라임 (화면 제목: 스트레스 풀리는 슬라임 / 산다 vs 안산다)",
                  "dur": 51.5, "views": 525000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "1초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '만지다 보면 스트레스까지 싹 풀린다'·원본 'stress relieving'·'anxiety relieving'(효능) → 쓰지 않음",
            "원본 '먹어도 안 죽는다'(안전성) → 쓰지 않음",
            "벤치·원본 매출·마진·투자 금액·지분(금액) → 쓰지 않음"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '스트레스 풀리는 슬라임 / 산다 vs 안산다'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [370, 800, 625, 1060], "target_what": "투자자 두 손에 엉겨 붙은 흰 슬라임 덩이(235.7초 프레임 눈 측정, 창 크롭 [405,0,1109,1080] 안 x190~320·y190~325 of 554 → 완성본 좌표) — fx_place fix 가 완성본 좌표로 다시 잼",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 7.7"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [3.0, 3.45], "color": "초록", "how": "auto", "why": "한국 바나나우유"},
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
    mat = {"_note": "샥탬스토리 32편 Sliimey Honey 재료 계획. 창 1080x1052(벤치 Lbct5sgnyjM, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(AJTIEVJn7x4_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Homemade Slime Slimey Honey Entrepreneur Keeps Asking For More", "해상도": "1920x1080 30fps (137) + 140-7 영어 원어(더빙 7개 중 original)",
                      "길이": 691.0, "받은 구간": "전체",
                      "남의 글자": "103~107초 이름/요청 띠·제안 띠 안 씀 · 88초 'COME JOIN OUR SLIME' 안 씀 · 끝 화면 안 씀 · 'sliimey honey' 간판·티셔츠·통 글 = 이 회사 브랜드"}},
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
