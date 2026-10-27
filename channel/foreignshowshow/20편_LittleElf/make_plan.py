# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""샥탬스토리 20편 Little ELF — 벤치 해외쇼츠 a8GJnj4-oko(「포장지를 쉽게 / 자를 수 있다고?!」 6.4만, 49.6초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/20편_LittleElf/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(18편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Shark Tank Global 공식 'The Sharks Fight For A Deal With Little Elf | Shark Tank US' vhgDo-stGq8, 1080p, 영어 원음 140 — 더빙 트랙 없음)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/20편_LittleElf/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt.
★원본 이름·요청·제안 띠(45~51·404~410·424초)는 안 쓰는 구간. 쓰는 컷은 띠 없음 → 크롭 높이 1080.
★앞은 하이브리드 재료 — 하이브리드는 O3 끝(15.33초)에서 자른다. 벤치의 '2억'·'수조 원'·'연매출 14억'(금액)과 원본 밖 화면(남의 선물 포장 영상·매장 영상)은 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/20편_LittleElf/src")
CLIP = "vhgDo-stGq8"
FILES = {CLIP: ("vhgDo-stGq8.mp4", 0.0, (1920, 1080))}
AUDIO = "vhgDo-stGq8_audio.m4a"        # 영어 원음(140 — 이 업로드는 소리 트랙 하나, 더빙 없음 · yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Shark Tank Global 원본: 고정 로고 없음 · 이름/요청/제안 띠(45~51·404~410·424초)는 안 쓰는 구간 · 601초 뒤 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (96.99, 98.07), "en": "I hate cutting paper.",
     "sub": ["포장지 자르는 거 진짜 싫어!"], "facts": ["f1"], "cap_at": [96.99], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 손에 든 빨간 리틀 엘프) — 벤치 0~1.5 창업자 얼굴 원(우리는 물건 원)",
     "cuts": [C(CLIP, 64.75, 65.83, 983, ours="창업자 손에 든 빨간 리틀 엘프 근접(원본 샷 64.66~66.47 — 소리 = 투자자 원음 'I hate cutting paper.' cover, 말한 사람은 화면 밖)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "포장지를 가위로 자르면 꼭 삐뚤빼뚤 찢어져서 다들 한 번씩 성질난다는데",
     "tts": "포장지를 가위로 자르면 꼭 삐뚤빼뚤 찢어져서, 다들 한 번씩 성질난다는데",
     "sub": ["포장지를 가위로 자르면", "꼭 삐뚤빼뚤 찢어져서", "다들 한 번씩 성질난다는데"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 5.0('포장지를 가위로 자르면')",
     "cuts": [C(CLIP, 52.78, 54.70, 960, ours="찢어지고 삐뚤게 잘린 포장지 더미(원본 샷 52.72~54.75, 소리 끔)"),
              C(CLIP, 54.82, 57.85, ours="창업자가 손짓하며 설명(샷 54.75~57.92, 소리 끔)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "그래서 스물한 살 청년이 종이를 한 번에 쭉 잘라 주는 물건을 만들었다는데",
     "tts": "그래서 스물한 살 청년이, 종이를 한 번에 쭉 잘라 주는 물건을 만들었다는데",
     "sub": ["그래서 스물한 살 청년이", "종이를 한 번에", "쭉 잘라 주는 물건을", "만들었다는데"], "facts": ["f3"],
     "fx": "초록 번쩍 — 벤치 8.0('완벽하게 재단할 수 있는 제품')",
     "cuts": [C(CLIP, 68.60, 70.90, 1000, ours="초록 포장지 롤 끝에 빨간 리틀 엘프를 끼움(원본 샷 68.54~73.67, 소리 끔)"),
              C(CLIP, 70.95, 73.60, 1000, ours="같은 샷 이어서 — 리틀 엘프를 롤에 끼운 손")]},
    {"id": "O2", "kind": "원음", "beat": "시연(밀기)", "audio": (80.59, 82.83), "en": "with ease, push the little elf forward.",
     "sub": ["아주 쉽게", "앞으로 쭉 밀어 주면 돼요"], "facts": ["f4"], "cap_at": [80.59, 81.47],
     "fx": "초록 번쩍 — 벤치 12.5('아주 쉽게 앞으로 밀어주세요')",
     "cuts": [C(CLIP, 81.45, 83.69, 960, cover=True, ours="펼친 포장지 위로 리틀 엘프를 앞으로 미는 손(원본 샷 81.38~85.42 — 소리 = 창업자 원음 0.86초 앞부터, 말하는 본인 손)")]},
    {"id": "O3", "kind": "원음", "beat": "시연(결과)", "audio": (85.75, 89.35), "en": "Getting a smooth, clean, and extremely satisfying cut",
     "sub": ["매끈하고 깔끔하게", "속 시원하게 잘려요"], "facts": ["f4"], "cap_at": [85.75, 87.63],
     "cuts": [C(CLIP, 83.75, 85.10, 960, cover=True, ours="리틀 엘프를 끝까지 밀어 자르는 손(원본 샷 81.38~85.42 이어서 — 투자자석 와이드 85.4~86.8 은 멈춘 화면 0.9초(freezedetect)라 뺌, 소리 = 창업자 원음 cover)"),
              C(CLIP, 86.85, 89.10, 960, cover=True, ours="반듯하게 잘린 포장지를 들어 보임(샷 86.82~89.16, 소리 = 이 줄 원음 이어서)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(차별점)", "text": "자를 대거나 선을 그을 필요도 없어서 샤크들도 줄 서서 해 봤는데",
     "tts": "자를 대거나 선을 그을 필요도 없어서, 샤크들도 줄 서서 해 봤는데",
     "sub": ["자를 대거나", "선을 그을 필요도 없어서", "샤크들도 줄 서서 해 봤는데"], "facts": ["f5"],
     "fx": "초록 번쩍 — 벤치 22.3 '자를 대거나'",
     "cuts": [C(CLIP, 107.28, 108.45, 960, ours="로리·창업자·바바라가 탁자에서 같이 잘라 봄(원본 샷 107.24~108.48, 소리 끔)"),
              C(CLIP, 111.75, 113.90, 960, ours="바바라가 초록 포장지를 잘라 봄 — 손(샷 111.71~113.95, 소리 끔)")]},
    {"id": "O4", "kind": "원음", "beat": "반응(투자자)", "audio": (120.19, 121.71), "en": "Wow. That's pretty ingenious.",
     "sub": ["와, 이거 진짜 기발하네요"], "facts": ["f5"], "cap_at": [120.19],
     "cuts": [C(CLIP, 119.40, 120.92, 960, cover=True, ours="포장지 위를 미는 손 근접(원본 샷 119.32~121.59 — 소리 = 로리 원음 cover, 같은 샷)")]},
    {"id": "N4", "kind": "나레", "beat": "해답(반만)", "text": "반만 쓰고 싶으면 엘프를 뒤집어 끼우고 다듬으면 된다는데",
     "tts": "반만 쓰고 싶으면, 엘프를 뒤집어 끼우고 다듬으면 된다는데",
     "sub": ["반만 쓰고 싶으면", "엘프를 뒤집어 끼우고", "다듬으면 된다는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 133.10, 135.60, 1000, ours="뒤집은 리틀 엘프를 롤 끝에 끼움(원본 샷 133.03~136.70, 소리 끔)"),
              C(CLIP, 136.75, 139.80, 1000, ours="롤 끝을 다듬어 자름(샷 136.70~139.84, 소리 끔)")]},
    {"id": "N5", "kind": "나레", "beat": "지분 경쟁", "text": "결국 로리랑 케빈이 서로 데려가겠다고 맞붙었는데",
     "tts": "결국 로리랑 케빈이 서로 데려가겠다고 맞붙었는데",
     "sub": ["결국 로리랑 케빈이", "서로 데려가겠다고", "맞붙었는데"], "facts": ["f7"],
     "fx": "빨강 번쩍 — 벤치 지분 경쟁",
     "cuts": [C(CLIP, 414.98, 415.98, ours="로리가 손짓하며 말함(원본 샷 414.95~416.02, 소리 끔)"),
              C(CLIP, 416.06, 417.34, ours="케빈이 말함(샷 416.02~417.38, 소리 끔)")]},
    {"id": "O5", "kind": "원음", "beat": "결정(성사)", "audio": (588.62, 590.02), "en": "And I'd love to make a deal with you.",
     "sub": ["당신이랑 계약할게요!"], "facts": ["f7"], "cap_at": [588.62],
     "fx": "초록 번쩍 — 벤치 41.0 '제안 수락할게요'",
     "cuts": [C(CLIP, 588.80, 590.20, cover=True, ours="투자자석 케빈·로리 — 창업자 말에 로리가 두 팔을 듦(원본 샷 588.72~590.49, 말한 창업자는 화면 밖 · 소리 = 이 줄 원음, 같은 샷 0.18초 뒤)")]},
    {"id": "O6", "kind": "원음", "beat": "결정(반응)", "audio": (594.38, 595.58), "en": "I will not let you down.",
     "sub": ["절대 실망 안 시킬게요"], "facts": ["f7"], "cap_at": [594.38],
     "cuts": [C(CLIP, 594.38, 595.58, ours="로리가 창업자를 안아 줌(원본 샷 591.82~595.63, 말하는 본인)")]},
    {"id": "N6", "kind": "나레", "beat": "끝(결과)", "text": "난독증을 이겨 낸 대학생이 포장지 칼 하나로 로리를 잡았다는데",
     "tts": "난독증을 이겨 낸 대학생이, 포장지 칼 하나로 로리를 잡았다는데",
     "sub": ["난독증을 이겨 낸 대학생이", "포장지 칼 하나로", "로리를 잡았다는데"], "facts": ["f8"],
     "cuts": [C(CLIP, 597.35, 599.30, ours="로버트가 웃음(원본 샷 597.30~599.37, 소리 끔)"),
              C(CLIP, 581.45, 583.40, ours="창업자가 웃음(샷 581.38~583.45, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/20편_LittleElf/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 20편 Little ELF — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "포장지 가위질", "line2": "안 해도 된다고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 95.23~98.07 'So who's ready to join me? Me. I hate cutting paper.'(스피치매틱스 enhanced 영어 — 화면 96.9~98.1 바바라, 화자 이름은 자막에 안 씀)", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f2": {"text": "원본 47.12~53.64 'Oh, everyone hates cutting wrapping paper because it always comes out ripped, jagged, or crooked.' · 화면 52.7~54.8 찢어진 포장지", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f3": {"text": "원본 15.80~25.84 'my name is Brian Perla. I am 21 years old… I am the owner and inventor of little elf gift wrap cutter.' · 59.72~68.55 'the little elf. The easy, lightweight, and fast gift wrap cutter.'", "url": U + CLIP, "kind": "방송 원음"},
    "f4": {"text": "원본 73.07~91.07 'Just measure the paper… push the little elf forward. Wow! Getting a smooth, clean, and extremely satisfying cut every single time.' · 화면 68~91 시연", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f5": {"text": "원본 100.31~124.31 샤크들이 나와서 직접 잘라 봄 'How is it… Easy to do once you got it… Wow. That's pretty ingenious… It really was.' · 화면 102~121", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f6": {"text": "원본 127.67~141.55 'What if I only want half the sheets?… insert it into the blade slot… with the little elf upside down. And then you can trim the paper just like that.'", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f7": {"text": "원본 267.89~291.33 로리 30% 제안 · 292.17~329.80 케빈 10%+로열티 제안 · 400.08 케빈 25% · 419.32~421.96 로리 20% · 585.66~590.02 'But Lori is the best option for this. And I'd love to make a deal with you.' · 594.38~595.58 로리 'I will not let you down.' — 금액은 대본에 안 씀", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f8": {"text": "원본 155.19~194.90 'in second grade, I was diagnosed with pretty severe dyslexia… I developed and designed what is today Little elf… I was a senior in high school' · 199.26~203.46 'I am actually a junior at Stanford University' · 585.66 로리 선택", "url": U + CLIP, "kind": "방송 원음"},
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
        "topic": "Little ELF(리틀 엘프) 포장지 커터 — 포장지 롤에 끼워 밀기만 하면 반듯하게 잘리는 작은 칼. 난독증을 이겨 낸 21살 대학생 창업자, 샤크들이 직접 잘라 봄 → 로리·케빈 경쟁 → 로리 선택",
        "product": "Little ELF Gift Wrap Cutter(리틀 엘프 포장지 커터)",
        "bench": {"id": "a8GJnj4-oko", "channel": "해외쇼츠 @foreignshowshow", "title": "포장지 쉽게 자를 수 있다고?! (화면 제목: 포장지를 쉽게 / 자를 수 있다고?!)",
                  "dur": 49.554, "views": 64000, "window": [0, 434, 1080, 1052], "cut_median": 1.3, "_cut_median_how": "0.5초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '약 2억에 지분 20%'·'포장재만 수조 원'·'연매출 14억'(금액) → 금액 없이 지분 경쟁·결정만",
            "벤치 34~40초 남의 선물 포장·매장 영상 — 이 원본 밖 → 원본 안 샤크 체험으로",
            "벤치 0초 창업자 얼굴 원 → R3 물건 원(빨간 리틀 엘프)"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '포장지를 쉽게 / 자를 수 있다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [430, 668, 651, 1126], "target_what": "창업자 손에 든 빨간 리틀 엘프 — 65.0초 원본 프레임 눈 측정(원본 x 870~1096·y 240~710, 크롭 [428,0,1109,1080] ×0.974 → 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 5.0 '포장지를 가위로 자르면'"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 8.0 '완벽하게 재단할 수 있는 제품'"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 12.5 '아주 쉽게 앞으로 밀어주세요'"},
    {"line": "N3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 22.3 '자를 대거나'"},
    {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 지분 경쟁"},
    {"line": "O5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 41.0 '제안 수락할게요'"},
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
    mat = {"_note": "샥탬스토리 20편 Little ELF 재료 계획. 창 1080x1052(벤치 a8GJnj4-oko, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(vhgDo-stGq8_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global(공식)", "제목": "The Sharks Fight For A Deal With Little Elf | Shark Tank US | Shark Tank Global", "해상도": "1920x1080 29.97fps (137) + 140 영어 원음(더빙 트랙 없음)",
                      "길이": 632.0, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠(45~51·404~410·424초) 안 씀 · 601초 뒤 끝 화면 안 씀 · 제품·티셔츠 'ELF' = 제품 브랜드"}},
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
