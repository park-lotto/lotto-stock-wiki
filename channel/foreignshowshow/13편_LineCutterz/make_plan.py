# -*- coding: utf-8 -*-
"""샥탬스토리 13편 Line Cutterz — 벤치 해외쇼츠 hZgCO9PEnO8(「오로지 낚시줄만 / 자른다는 제품?!」 670만) 줄 단위 칼카피 (관제 097, 2026-10-27).

    PYTHONUTF8=1 py channel/foreignshowshow/13편_LineCutterz/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(7·9편 make_plan 꼴).
원음 줄 = 벤치가 쓴 원음 순간을 **같은 원본(CNBC Ambition 공식 Qy7wUkIrrQ4, 1080p) 시각**으로 — 근거.md §2 표.
받아쓰기 = 스피치매틱스 enhanced 영어(C:/숏템_칼카피/foreignshowshow/13편_LineCutterz/asr/src_sm.json·src_sm.txt) — 낱말 시각 그대로.
샷 경계 = 64x36 프레임 차(asr/src_scenes.txt). 크롭 가로 자리 = 얼굴 검출(fx_measure.faces) — 눈대중 금지.
B13(같은 소스 ±3초 재사용) 때문에 0초 훅(116.32~118.29)과 얼굴 문지르기 원본(118.4~120)은 겹쳐 못 씀 → 문지르기는 공식 홍보 영상(gnb_t06Z12o) 손바닥 장면으로.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/13편_LineCutterz/src")
CLIP, GNB, A09 = "Qy7wUkIrrQ4", "gnb_t06Z12o", "a09Bkw-ypnU"
FILES = {CLIP: ("Qy7wUkIrrQ4.mp4", 0.0, (1920, 1080)), GNB: ("gnb_t06Z12o.mp4", 0.0, (1280, 720)), A09: ("a09Bkw-ypnU.mp4", 0.0, (1920, 1080))}
AUDIO = "Qy7wUkIrrQ4_audio.m4a"        # 영어 원음 140-6 'English (US) original' — 더빙 트랙(fr·es·hi·pt·it·de) 섞임 방지
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# CLIP: 왼쪽 아래 CNBC 공작 로고(y≈1035~1075)·'CNBC.COM/CHANNELFINDER' 노란 띠(44~64초, y≈1045) → h ≤ 990 으로 뺌.
#       이름·제안 띠(14~22·133~140·265~277초, y≈780~870)는 그 시각을 안 씀.
H_DEF = {CLIP: 990, GNB: 720, A09: 1080}
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


# 원음 줄 audio = (원본 시작, 끝). cut = (소스, 원본 시작, 원본 끝, [x,y,w,h], 화면에 보이는 것, 덧칸)
LINES = [
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (116.32, 118.29), "en": "That's crazy. / Stop the madness.",
     "sub": ["이거 완전 미쳤는데?!", "미친 짓 그만해!"], "facts": ["f1"], "cap_at": [116.32, 117.17], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 손가락에 낀 검은 반지 커터) — 벤치 0~0.83 빨간 실선 원(투자자 얼굴, 우리는 물건)",
     "cuts": [C(CLIP, 112.30, 112.95, 1117, 0, 700, ours="창업자 손 근접(확대 크롭 h700 — 반지가 자막 띠 아래로 오게): 손가락에 낀 검은 Line Cutterz 반지로 굵은 줄을 끊는 순간(원본 샷 111.45~114.81, 소리 = 다음 컷 투자자 'That's crazy' cover)",
                cover=True),
              C(CLIP, 116.97, 117.61, ours="파란 셔츠 투자자가 놀라 웃으며 'That's crazy'(말하는 본인, 샷 116.42~117.62)"),
              C(CLIP, 117.62, 118.29, ours="대머리 검은 정장 투자자 반응(원본 편집 그대로, 샷 117.62~118.39) — 벤치 32.0 같은 샷")]},
    {"id": "N1", "kind": "나레", "beat": "문제(사연)", "text": "낚시하다 모래 속 칼을 밟아서 발가락이 잘릴 뻔했다는 이 남자",
     "tts": "낚시하다 모래 속 칼을 밟아서 발가락이 잘릴 뻔했다는 이 남자",
     "sub": ["낚시하다 모래 속", "칼을 밟아서", "발가락이 잘릴 뻔했다는", "이 남자"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 3.03(사연 컷 넘김)",
     "cuts": [C(CLIP, 11.40, 12.90, ours="창업자가 무대 가운데 서서 인사(원본 샷 11.38~14.08, 이름 띠 전)"),
              C(GNB, 71.60, 72.95, 640, ours="공식 홍보 영상(720p): 칼 두 자루 근접 — '위험한 칼' 그림"),
              C(CLIP, 49.86, 51.80, ours="분홍 옷 투자자가 입을 벌리고 놀람(원본 샷 49.78~51.89 — '발가락 잘릴 뻔' 바로 뒤 반응)")]},
    {"id": "N2", "kind": "나레", "beat": "문제(기존 불편)", "text": "녹슨 손톱깎이랑 위험한 칼로 줄 끊는 게 지긋지긋했다는데",
     "tts": "녹슨 손톱깎이랑 위험한 칼로 줄 끊는 게 지긋지긋했다는데",
     "sub": ["녹슨 손톱깎이랑", "위험한 칼로 줄 끊는 게", "지긋지긋했다는데"], "facts": ["f3"],
     "fx": "빨강 번쩍 — 벤치 5.37(불편 컷 넘김)",
     "cuts": [C(CLIP, 52.00, 53.20, ours="창업자가 말함(원본 샷 51.89~53.3, 소리 끔)"),
              C(CLIP, 54.30, 56.50, 1500, ours="무대: 창업자가 빨간 낚시 도구함을 거꾸로 쏟음"),
              C(CLIP, 56.65, 58.15, 900, ours="바닥에 쏟아진 도구함·낚시 도구(원본 샷 56.59~58.23)")]},
    {"id": "O2", "kind": "원음", "beat": "문제(원음)", "audio": (62.97, 66.97), "en": "I've even chipped my teeth biting line the old school way twice.",
     "sub": ["옛날 식으로 이로 끊다가", "이가 두 번이나 깨졌어요"], "facts": ["f4"], "cap_at": [62.97, 64.81],
     "cuts": [C(CLIP, 62.97, 64.50, ours="창업자가 이를 가리키며 말함(말하는 본인, 샷 61.50~64.53)"),
              C(GNB, 75.60, 78.07, 640, ours="공식 홍보 영상: 낚시꾼이 이로 낚싯줄을 물어 끊는 사진(그 '옛날 방식')", mute=True)]},
    {"id": "O3", "kind": "원음", "beat": "해답(발상)", "audio": (67.61, 70.40), "en": "I thought, why not just put a cutter on your finger?",
     "sub": ["그래서 생각했죠", "손가락에 커터를 끼우면?"], "facts": ["f5"], "cap_at": [67.61, 68.45],
     "fx": "초록 번쩍 — 벤치 10.17(발명 컷 넘김)",
     "cuts": [C(GNB, 87.95, 90.75, 640, ours="공식 홍보 영상: 'LINE CUTTERZ' 셔츠 낚시꾼이 손가락 반지로 줄을 다룸(소리 = 창업자 원음 cover) — 원본 이 시각 화면은 투자자 반응(64.53~68.64)·거의 안 움직이는 무대 와이드(68.64~74.07, freezedetect 0.93초 멈춤처럼 보임)라 발상 질문 '손가락에 커터를'을 그림으로", cover=True)]},
    {"id": "O4", "kind": "원음", "beat": "해답(시제품)", "audio": (70.53, 76.97),
     "en": "So I busted out some welding putty, broke apart a dental floss cutter and hand made my first prototype.",
     "sub": ["용접 퍼티를 꺼내고", "치실 커터를 뜯어서", "첫 시제품을 손으로 만들었죠"], "facts": ["f5"], "cap_at": [70.53, 72.41, 74.69],
     "fx": "초록 번쩍 — 벤치 14.4(첫 모델 컷)",
     "cuts": [C(CLIP, 70.53, 74.06, 1500, ours="무대 와이드: 창업자가 손짓하며 설명(말하는 본인)"),
              C(CLIP, 74.09, 76.97, ours="창업자 중간 샷(말하는 본인, 샷 74.07~77.01)")]},
    {"id": "N3", "kind": "나레", "beat": "시연(예고)", "text": "그러고는 무대에서 바로 시범을 보여 주는데", "tts": "그러고는 무대에서 바로 시범을 보여 주는데",
     "sub": ["그러고는 무대에서", "바로 시범을 보여 주는데"], "facts": ["f6"],
     "cuts": [C(CLIP, 83.40, 84.80, ours="무대 진열 'LINE CUTTERZ' 간판 근접(원본 샷 83.35~85.82, 소리 끔)"),
              C(CLIP, 85.85, 87.50, ours="분홍 옷 투자자가 종이를 들고 지켜봄(원본 샷 85.82~87.52, 소리 끔) — 벤치 16.5 같은 투자자")]},
    {"id": "O5", "kind": "원음", "beat": "시연", "audio": (87.65, 95.18),
     "en": "This is 12-pound test monofilament line. / Pretty popular for catching sunny and bass. / (snap)",
     "sub": ["이건 12파운드짜리", "모노필라멘트 줄이에요", "배스 잡을 때 많이 쓰죠", "* 툭! 한 번에 끊김 *"], "facts": ["f6"],
     "cap_at": [87.65, 89.29, 90.61, 93.70],
     "fx": "빨강 번쩍 — 벤치 20.5('*딱*' 끊기는 순간)",
     "cuts": [C(CLIP, 87.65, 90.40, 1500, ours="무대 와이드: 창업자가 낚싯줄을 들어 보임(샷 87.52~90.42)"),
              C(CLIP, 90.45, 93.37, ours="창업자 중간 샷 — 줄 설명(말하는 본인, 샷 90.42~93.39)"),
              C(CLIP, 93.42, 94.50, 1500, ours="무대 와이드: 반지로 줄을 끊자 양동이가 떨어짐(샷 93.39~94.53)"),
              C(CLIP, 94.55, 95.18, ours="분홍 옷 투자자가 놀라 봄(샷 94.53~95.73) — 벤치 21.5 '단번에 끊어지는 줄' 같은 샷")]},
    {"id": "N4", "kind": "나레", "beat": "시연(고조)", "text": "상어도 잡는다는 100파운드 굵은 줄까지 한 번에 툭 끊어 버리는데",
     "tts": "상어도 잡는다는 백 파운드 굵은 줄까지 한 번에 툭 끊어 버리는데",
     "sub": ["상어도 잡는다는", "100파운드 굵은 줄까지", "한 번에 툭 끊어 버리는데"], "facts": ["f7"],
     "fx": "빨강 번쩍 — 벤치 26.9(굵은 줄 컷)",
     "cuts": [C(CLIP, 98.30, 99.90, ours="창업자가 굵은 줄 이야기를 하며 손짓(원본 샷 97.80~100.20, 소리 끔)"),
              C(GNB, 107.00, 108.70, 560, ours="공식 홍보 영상: 검은 반지 날에 줄을 걸어 끊는 근접"),
              C(A09, 56.20, 58.30, 960, ours="공식 광고(1080p): 보트 난간에서 손가락 반지로 낚싯줄을 끊음(글자 없는 구간)")]},
    {"id": "N6", "kind": "나레", "beat": "고조(피부)", "text": "날을 손바닥에 문질러도 자기 피부는 안 베인다고 자신하는데",
     "tts": "날을 손바닥에 문질러도 자기 피부는 안 베인다고 자신하는데",
     "sub": ["날을 손바닥에 문질러도", "자기 피부는 안 베인다고", "자신하는데"], "facts": ["f8"],
     "cuts": [C(GNB, 98.00, 100.40, 640, ours="공식 홍보 영상: 반지를 손바닥에 대고 문지름(벤치 29.5~31 얼굴 문지르기 대신 — B13)"),
              C(CLIP, 174.75, 176.12, ours="창업자 정면 근접(원본 샷 174.71~176.14, 소리 끔)")]},
    {"id": "O9", "kind": "원음", "beat": "끝(투자자 평)", "audio": (204.16, 206.84), "en": "I think it's genius.",
     "sub": ["이건 천재적이에요"], "facts": ["f9"], "cap_at": [204.16],
     "fx": "초록 번쩍 — 벤치 끝 반응 컷",
     "cuts": [C(CLIP, 204.16, 205.36, 620, ours="분홍 옷 투자자가 'I think it's genius'(말하는 본인, 투 숏 200.80~205.57 의 왼쪽)"),
              C(CLIP, 223.50, 225.00, ours="창업자 얼굴(원본 샷 221.02~227.56, 소리 끔 — 끝 컷 1.5초 이상을 위해 원음 뒤 화면만, 다음 말 'I really like it' 206.84 전에 소리 끊음)", mute=True)]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/13편_LineCutterz/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 13편 Line Cutterz — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "손가락에 끼우는", "line2": "낚싯줄 커터?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 116.29~117.17 'That's crazy.' · 117.17~118.29 'Stop the madness.'(스피치매틱스 enhanced 영어, 같은 화자 S3) — 100파운드 줄 시연 직후 투자자석 반응. 화면 116.42~117.62 파란 셔츠 투자자 · 117.62~118.39 대머리 투자자", "url": U + CLIP, "kind": "방송 원음"},
    "f2": {"text": "원본 35.76~50.12 창업자 'When I got it onto the beach, it thrashed around and got tangled up in my line… I ran up to my tackle box to grab my knife and it had fallen in the sand. I stepped on it and almost cut off my toe.' — 벤치 나레 '손을 크게 베었다'는 원본과 다름(발가락) → 원본대로 고침", "url": U + CLIP, "kind": "방송 원음(창업자 사연)"},
    "f3": {"text": "원본 53.04~62.77 'I was absolutely sick and tired of dealing with the same old rusty fingernail clippers and dangerous knives just to cut line.'", "url": U + CLIP, "kind": "방송 원음"},
    "f4": {"text": "원본 62.97~66.93 'I've even chipped my teeth biting line the old school way twice.'", "url": U + CLIP, "kind": "방송 원음"},
    "f5": {"text": "원본 67.61~70.37 'I thought, why not just put a cutter on your finger?' · 70.53~77.01 'So I busted out some welding putty, broke apart a dental floss cutter and hand made my first prototype.'", "url": U + CLIP, "kind": "방송 원음"},
    "f6": {"text": "원본 85.89~87.65 'I got to show you how this works.' · 87.65~93.69 'This is 12-pound test monofilament line. Pretty popular for catching sunny and bass.' · 95.21~97.81 'This is 30-pound test fluorocarbon' (스피치매틱스가 pound 를 £ 로 적음 — 'test line' 단위는 파운드) · 화면 93.39~94.53 줄 끊기고 양동이 떨어짐", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f7": {"text": "원본 108.65~115.13 'This is a 100-pound test braided nylon fishing line. You can catch a 200, 300-pound shark with this line.' · 화면 111.45~114.81 반지로 굵은 줄을 끊는 손 근접", "url": U + CLIP, "kind": "방송 원음+화면"},
    "f8": {"text": "원본 118.29~120.01 창업자 'I can't cut my skin with it either.'(창업자 주장 — 전언 '자신하는데'로만) · 화면 118.39~120.02 반지를 얼굴에 문지름 · 공식 홍보 영상 gnb_t06Z12o 98~100초 손바닥에 문지르는 장면", "url": U + CLIP, "kind": "방송 원음(창업자 주장)"},
    "f9": {"text": "원본 204.16~205.56 'I think it's genius.'(분홍 옷 투자자 — 클립 제목 'Lori Calls This Product Genius') · 화면 200.80~205.57 투 숏", "url": U + CLIP, "kind": "방송 원음"},
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
        "topic": "Line Cutterz(손가락에 끼우는 세라믹 날 반지형 낚싯줄 커터) — 낚시하다 칼을 밟아 발가락이 잘릴 뻔한 창업자가 치실 커터를 뜯어 만든 반지로 12·30·100파운드 줄을 무대에서 끊어 보임",
        "product": "Line Cutterz Ring(라인커터즈)",
        "bench": {"id": "hZgCO9PEnO8", "channel": "해외쇼츠 @foreignshowshow", "title": "A Tool Designed Only to Cut Fishing Line (화면 제목: 오로지 낚시줄만 / 자른다는 제품?!)",
                  "dur": 36.534, "views": 6700000, "window": [0, 434, 1080, 1052], "cut_median": 1.43, "_cut_median_how": "check.scene_cuts 같은 자(창 scene>th) 22조각 중앙 — 10-27 실측"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 1.0~2.6 창업자 낚시 사진·3.5~4.5 손가락 피 흘리는 사진 — 출처 없는 사진·상처 사진 → 원본 무대·공식 홍보 영상 칼 근접으로",
            "벤치 나레 '칼에 손을 크게 베었다' — 원본은 '모래 속 칼을 밟아 발가락이 잘릴 뻔'(f2) → 원본대로",
            "벤치 '5~6kg·20kg·150kg' 환산 — 원본 단위(12·30·100파운드) 그대로",
            "벤치 29.5~34.2 '얼굴에 문지름 / 미친 짓 그만해 / 피부 상처 안 입혀' 원본 순간(116~120초) — 0초 훅과 같은 원본 3초 안이라 B13 → '미친 짓 그만해'는 0초 줄로, 문지르기는 공식 영상 손바닥 장면 + 나레 전언으로",
            "벤치 '이번엔 20kg 플루오카본'(원본 30파운드 95.21~97.79) — 길이(벤치 +15% 안)를 맞추려 뺌",
            "벤치 끝 '오로지 줄만 끊을 수 있게 설계되었다고' → 투자자 평 'I think it's genius' 원음으로 닫음"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '오로지 낚시줄만 / 자른다는 제품?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.65], "target": [525, 1200, 615, 1330], "target_what": "손가락에 낀 검은 반지(Line Cutterz 반지 커터) — 손 상자 = 112.32초 완성본 격자 sheet/ring_zoom.jpg 눈 측정",
     "why": "R3 0초 원 = 물건(제품 반지) — 벤치 0~0.83 원은 투자자 얼굴이지만 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "O1", "kind": "flash", "at": [540, 960], "t": [0.65, 1.10], "color": "초록", "how": "auto", "why": "벤치 0.867 초록 번쩍(원 다음 얼굴 컷 첫 프레임)"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 3.03 빨강 번쩍(사연 컷)"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 5.37 빨강 번쩍(불편 컷)"},
    {"line": "O3", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 10.17 초록 번쩍(발명 컷)"},
    {"line": "O4", "kind": "flash", "at": [540, 960], "t": [3.56, 4.01], "color": "초록", "how": "auto", "why": "벤치 14.4 초록 번쩍(첫 모델 컷) — 원본 74.07 샷 경계 = 줄 안 3.56"},
    {"line": "O5", "kind": "flash", "at": [540, 960], "t": [5.77, 6.22], "color": "빨강", "how": "auto", "why": "벤치 20.5 끊기는 순간 — 원본 93.42 = 줄 안 5.77"},
    {"line": "N4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 26.9 빨강 번쩍(굵은 줄)"},
    {"line": "O9", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "끝 반응 컷"},
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
    mat = {"_note": "샥탬스토리 13편 Line Cutterz 재료 계획. 창 1080x1052(벤치 hZgCO9PEnO8 창 [0,435,1080,1051] ≒ 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(영어 원음 트랙 Qy7wUkIrrQ4_audio.m4a).",
           "sources": {
               CLIP: {"채널": "CNBC Ambition(공식)", "제목": "Lori Calls This Product Genius | Shark Tank In 5", "해상도": "1920x1080 29.97fps (137) + 140-6 영어 원음",
                      "길이": 368.3, "받은 구간": "전체",
                      "남의 글자": "왼쪽 아래 CNBC 공작 로고·'CNBC.COM/CHANNELFINDER' 띠(y≥1035) — 모든 컷 크롭 h≤990 으로 뺌. 이름·제안 띠(14~22·133~140·265~277초) 시각 안 씀. 창업자 셔츠 'LINE CUTTERZ' 로고 = 제품 브랜드"},
               GNB: {"채널": "Line Cutterz(판매사 공식 UC… 'Line Cutterz Ring Video')", "제목": "Line Cutterz Ring Video", "해상도": "1280x720 (136, 최대 화질)",
                     "길이": 184.2, "남의 글자": "쓴 구간(71.6~73, 75.6~78.1, 98~100.4, 107~108.7)엔 글자 없음 — 시트 눈 확인. 셔츠 로고 = 제품 브랜드"},
               A09: {"채널": "Line Cutterz(판매사 공식)", "제목": "The Patented Line Cutterz Ring - As Seen On Shark Tank", "해상도": "1920x1080 59.94fps (영상만)", "길이": 76.5,
                     "남의 글자": "21~23 'Adjustable Velcro…'·34~36 'Two-sided…'·51~52 'No Risk of injury'·64~66 'Mount Anywhere' 글자 — 안 씀. 쓴 56.2~58.3 은 글자 없음"}},
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
