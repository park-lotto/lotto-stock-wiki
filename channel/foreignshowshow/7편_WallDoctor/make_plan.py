# -*- coding: utf-8 -*-
"""샥탬스토리 7편 Wall Doctor Rx — 벤치 vbxJ_v132ao(해외쇼츠 「구멍난 벽을 쉽게 고쳐준다는 제품」) 진짜 칼카피 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py channel/foreignshowshow/7편_WallDoctor/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획.md · plan/계획_시트.jpg 를 만든다.
원음 줄 = 벤치가 쓴 원음 순간을 **같은 원본(CNBC 공식 클립 h99r2Xmp-Xg) 시각**으로 — 근거.md §2 표.
나레 시각은 7.8자/초(벤치 QMJ 실측) 추정 — TTS 뒤(render.py --tts-only) render_info 로 줄 길이만 다시 잰다.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = Path("C:/숏템_칼카피/foreignshowshow/7편_WallDoctor/src")
CLIP, BULB, OIVP, MZ = "h99r2Xmp-Xg", "dupCFG4B4CM", "oivPxlXroNU", "8MZUyVissao"
FILES = {CLIP: ("h99r2Xmp-Xg.mp4", 0.0, (1920, 1080)), BULB: ("dupCFG4B4CM.mp4", 0.0, (1920, 1080)),
         OIVP: ("oivPxlXroNU.mp4", 0.0, (1280, 720)), MZ: ("8MZ_160.mp4", 160.0, (1920, 1080))}   # (파일, 파일 0초 = 원본 초, 크기)
AUDIO = "h99r2Xmp-Xg_audio.m4a"        # 클립 영어 원음(140-7 'English original') — 더빙 트랙 섞임 방지(원리서 §9 3편)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# 크롭 높이: CLIP 은 왼쪽 아래 CNBC 공작 로고·'SHARK TANK TONIGHT 10P ET' 띠(y≥950)를 빼려고 h≤940 / 112~114초 이름 띠(y≥800)는 h≤795
H_DEF = {CLIP: 940, BULB: 1080, OIVP: 720, MZ: 1080}


def crop(vid, cx, y=0, h=None):
    W, H = FILES[vid][2]
    h = h or H_DEF[vid]
    w = int(round(h * AR))
    x = max(0, min(W - w, int(cx - w / 2)))
    return [x, y, w, h]


# 원음 줄 audio = (원본 시작, 끝) — 원본 초. cut = (소스, 원본 시작, 원본 끝, [x,y,w,h], 화면에 보이는 것)
LINES = [
    {"id": "N1", "kind": "나레", "beat": "의문(행동 먼저)", "text": "망치로 벽부터 부숴 버리는 남자", "tts": "망치로 벽부터 부숴 버리는 남자",
     "sub": ["망치로 벽부터", "부숴 버리는 남자"], "facts": ["f1"],
     "fx": "0초 빨간 원(망치가 벽을 치는 자리) — 벤치 0~1.43 빨간 실선 원(망치 따라감, r121)",
     "cuts": [(CLIP, 20.3, 21.813, [150, 280, 657, 640], "창업자가 팔을 뻗어 망치로 하얀 벽을 침(벤치 0초 컷과 같은 원본 샷 19.5~21.83) — 10-20 R3: 크롭을 망치 위쪽으로(자막 띠 밖·얼굴 밖), 재료.json shots[0].why_crop")]},
    {"id": "O2", "kind": "원음", "beat": "의문(해결 예고)", "audio": (23.00, 25.55), "en": "Now, in order to fix that hole,",
     "sub": ["자, 이 구멍을", "고쳐 볼게요"], "facts": ["f3"], "cap_at": [23.25, 24.15],
     "fx": "빨강 번쩍 — 벤치 2.20(같은 원음 줄 첫 컷)",
     "cuts": [(CLIP, 23.00, 23.583, crop(CLIP, 1000), "파란 재킷 투자자가 웃으며 봄(원본 반응 컷 — 벤치도 같은 자리)"),
              (CLIP, 23.583, 25.125, crop(CLIP, 1050), "창업자가 벽을 가리키며 말함(말하는 본인)"),
              (CLIP, 25.125, 25.55, crop(CLIP, 960), "벽에 난 구멍 근접")]},
    {"id": "O1", "kind": "원음", "beat": "반응", "audio": (80.80, 81.55), "en": "Wow.", "sub": ["와우!"], "style": "원음반응_크게", "facts": ["f2"],
     "cuts": [(CLIP, 80.80, 81.55, crop(CLIP, 880), "회색 정장·빨간 넥타이 투자자가 '와우'(샷 80.75~81.58, 말하는 본인)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(제품)", "text": "근데 필요한 건 딱 두 가지뿐이라는데", "tts": "근데 필요한 건 딱 두 가지뿐이라는데",
     "sub": ["근데 필요한 건", "딱 두 가지뿐이라는데"], "facts": ["f4"],
     "cuts": [(CLIP, 38.70, 39.70, crop(CLIP, 980), "창업자가 빨간 'WALL Rx' 봉지를 들어 보임"),
              (BULB, 24.45, 25.40, crop(BULB, 980), "공식 광고(BulbHead): 봉지 + 받침판 + 줄무늬 틀 구성품(포장 글자 = 제품 브랜드)")]},
    {"id": "O3", "kind": "원음", "beat": "시연", "audio": (53.00, 55.45), "en": "and place it over your hole.",
     "sub": ["구멍 위에", "딱 올려 주세요"], "facts": ["f5"], "cap_at": [53.1, 54.05],
     "cuts": [(CLIP, 53.00, 54.875, crop(CLIP, 1050), "창업자가 'WALL Rx' 진열대 옆 벽에서 시연(말하는 본인, 와이드)"),
              (CLIP, 54.875, 55.45, crop(CLIP, 960), "손이 벽 구멍 위에 받침판을 댐(근접)")]},
    {"id": "N3", "kind": "나레", "beat": "시연(실사용)", "text": "구멍 위에 받침 판을 먼저 대 주고", "tts": "구멍 위에 받침 판을 먼저 대 주고",
     "sub": ["구멍 위에", "받침 판을 먼저 대 주고"], "facts": ["f5", "f11"],
     "cuts": [(OIVP, 19.30, 21.00, crop(OIVP, 720), "실사용(집 벽, 720p): 남자가 민트색 벽 구멍에 톱니 모양 받침판을 붙임")]},
    {"id": "O4", "kind": "원음", "beat": "시연", "audio": (59.62, 61.30), "en": "with your special compound",
     "sub": ["특수 반죽이", "담긴 틀이에요"], "facts": ["f6"], "cap_at": [59.7, 60.4],
     "fx": "초록 번쩍 — 벤치 11.87(창업자가 틀 든 컷 첫 프레임)",
     "cuts": [(CLIP, 59.62, 61.30, crop(CLIP, 900), "창업자가 줄무늬 틀(반죽)을 들어 보임(말하는 본인)")]},
    {"id": "N4", "kind": "나레", "beat": "시연(실사용)", "text": "반죽 든 틀을 덮고 손으로 쓱 펴 바른 다음", "tts": "반죽 든 틀을 덮고 손으로 쓱 펴 바른 다음",
     "sub": ["반죽 든 틀을 덮고", "손으로 쓱 펴 바른 다음"], "facts": ["f6", "f11"],
     "cuts": [(OIVP, 47.50, 48.60, crop(OIVP, 800), "실사용: 줄무늬 틀을 벽에 대고 두 손으로 누름"),
              (CLIP, 64.40, 65.40, crop(CLIP, 960), "방송: 줄무늬 틀 위를 손바닥으로 문질러 폄(근접)")]},
    {"id": "N5", "kind": "나레", "beat": "해답(결과)", "text": "하루 이틀 말려서 사포로 갈면 감쪽같아진다고",
     "tts": "하루 이틀 말려서 사포로 갈면 감쪽같아진다고", "sub": ["하루 이틀 말려서", "사포로 갈면", "감쪽같아진다고"], "facts": ["f7", "f11"],
     "fx": "초록 번쩍 — 벤치 16.07(마른 반죽 근접 첫 프레임)",
     "cuts": [(BULB, 59.30, 60.55, crop(BULB, 960), "공식 광고: 마른 흰 반죽을 사포 블록으로 갊(벤치 16~19초와 같은 광고 장면)"),
              (OIVP, 113.00, 114.30, crop(OIVP, 520), "실사용: 틀을 뗀 벽에 메워진 흰 자국을 가리키는 남자")]},
    {"id": "O5", "kind": "원음", "beat": "해답(반응)", "audio": (70.75, 71.55), "en": "Done.", "sub": ["끝!"], "style": "원음반응_크게", "facts": ["f7"],
     "fx": "빨강 번쩍 — 벤치 20.43('끝이야!')",
     "cuts": [(CLIP, 70.75, 71.55, crop(CLIP, 960), "창업자가 두 팔을 벌림(말하는 본인, 샷 70.17~71.79)")]},
    {"id": "N6", "kind": "나레", "beat": "전개(현장)", "text": "공구도 기술도 필요 없어서 누구나 집에서 고칠 수 있다는데",
     "tts": "공구도 기술도 필요 없어서 누구나 집에서 고칠 수 있다는데",
     "sub": ["공구도 기술도", "필요 없어서", "누구나 집에서", "고칠 수 있다는데"], "facts": ["f8"],
     "fx": "띠링(번쩍 없이) — 벤치 22.04 현장 컷 첫머리",
     "cuts": [(MZ, 162.50, 164.20, crop(MZ, 1000), "현장(집 고치는 부부, 1080p): 두 사람이 석고보드 판을 같이 들어 올림"),
              (MZ, 210.20, 211.90, crop(MZ, 900), "현장: 둘이 석고보드를 천장에 밀어 붙임(근접)")]},
    {"id": "O7", "kind": "원음", "beat": "지분 경쟁(제안)", "audio": (86.85, 88.55), "en": "I'd like to make you an interesting offer.",
     "sub": ["흥미로운 제안을", "하나 할게요"], "facts": ["f9"], "cap_at": [86.9, 87.75],
     "cuts": [(CLIP, 86.85, 87.667, crop(CLIP, 1000), "대머리 검은 정장 투자자(원본 반응 컷 — 원본 편집 그대로)"),
              (CLIP, 87.667, 88.55, crop(CLIP, 900), "파란 재킷 투자자가 턱을 괴고 제안(말하는 본인, 샷 87.667~88.583)")]},
    {"id": "O8", "kind": "원음", "beat": "지분 경쟁(금액)", "audio": (93.97, 97.65), "en": "I'll give you the 150,000, no equity,",
     "sub": ["15만 달러 줄게요", "지분은 필요 없어요"], "facts": ["f9"], "cap_at": [94.0, 96.8],
     "fx": "띠링(번쩍 없이) — 벤치 27.50 '2억 3천만원 줄게'",
     "cuts": [(CLIP, 93.97, 97.65, crop(CLIP, 960), "투자자석 와이드(제안하는 투자자 포함)")]},
    {"id": "O9", "kind": "원음", "beat": "지분 경쟁(조건)", "audio": (101.05, 103.40), "en": "you give me exclusive rights for this product,",
     "sub": ["대신 이 제품", "해외 독점권을 줘요"], "facts": ["f9"], "cap_at": [101.1, 101.68],
     "cuts": [(CLIP, 101.05, 103.40, crop(CLIP, 900), "파란 재킷 투자자가 두 손을 모으며 제안(말하는 본인)")]},
    {"id": "O10", "kind": "원음", "beat": "지분 경쟁(조건)", "audio": (108.67, 113.40),
     "en": "I'll buy it at two dollars from you and sell to the rest of the world. / Wow.",
     "sub": ["개당 2달러에 사서", "전 세계에 팔게요", "와우"], "facts": ["f9"], "cap_at": [108.7, 110.4, 112.75],
     "cuts": [(CLIP, 108.67, 112.0, crop(CLIP, 900), "파란 재킷 투자자 제안(말하는 본인)"),
              (CLIP, 112.0, 113.40, crop(CLIP, 980, 0, 795), "창업자 '와우'(아래 이름 띠 'Robert's offer…' y≥800 은 크롭으로 뺌)")]},
    {"id": "O11", "kind": "원음", "beat": "결정", "audio": (206.30, 208.15), "en": "Robert, your deal is phenomenal.",
     "sub": ["로버트,", "제안이 정말 최고예요"], "facts": ["f10"], "cap_at": [206.32, 206.8],
     "cuts": [(CLIP, 206.30, 208.15, crop(CLIP, 1250), "창업자가 손뼉 치며 말함(말하는 본인, 샷 206.29~208.21)")]},
    {"id": "O12", "kind": "원음", "beat": "결정(성사)", "audio": (303.67, 306.70),
     "en": "I'm there. Let's do it. I'm there, man. / Do I hear a yes?",
     "sub": ["좋아요, 합시다!", "콜이에요!", "'예스' 맞죠?"], "facts": ["f10"],
     "cap_at": [303.75, 304.95, 305.68],
     "cuts": [(CLIP, 303.67, 305.125, crop(CLIP, 960), "창업자 정면 근접"),
              (CLIP, 305.125, 306.70, crop(CLIP, 900), "파란 재킷 투자자가 일어서며 확인")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/7편_WallDoctor/work/render/render_info.json")


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
        for c in L["cuts"]:
            vid, a, b, cr, ours = c
            dur = round((b - a) * scale, 3)
            f, ss = src_of(vid, a)
            au = {"mute": True} if L["kind"] == "나레" else {"mute": False, "audio_src": AUDIO, "audio_ss": a, "audio_dur": dur}
            shots.append({"i": len(shots), "line": L["id"], "kind": L["kind"], "src": f, **au,
                          "url": f"https://www.youtube.com/watch?v={vid}", "src_orig_span": [a, round(a + dur, 3)], "ss": ss,
                          "dur": dur, "t_final_est": [round(t, 2), round(t + dur, 2)], "res": "%dx%d" % FILES[vid][2],
                          "src_crop": cr, "scale": round(WIN[0] / cr[2], 3), "ours": ours,
                          "audio": "원본 소리(원음)" if L["kind"] == "원음" else "원본 소리 끔 + TTS"})
            t += dur
    return shots, round(t, 2)


def frame(path: str, ss: float, cr) -> Image.Image:
    x, y, w, h = cr
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-i", path, "-frames:v", "1", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale=270:263", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
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
    d.text((8, 8), f"샥탬스토리 7편 Wall Doctor Rx — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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
        if L.get("fx") and s == next(x for x in shots if x["line"] == s["line"]):
            for n, part in enumerate(_wrap("효과: " + L["fx"], 40)):
                d.text((tx, y0 + 215 + n * 16), part, fill=(200, 0, 0), font=small)
    S.save(out, quality=82)


def check(shots, total):
    durs = sorted(s["dur"] for s in shots)
    med = durs[len(durs) // 2] if len(durs) % 2 else (durs[len(durs) // 2 - 1] + durs[len(durs) // 2]) / 2
    seen, overlap = [], []
    for s in shots:
        vid = s["url"][-11:]
        a, b = s["src_orig_span"]
        for (v2, a2, b2, i2, l2) in seen:
            forward = a >= b2 - 0.01 and (l2 == s["line"] or i2 == s["i"] - 1)
            if v2 == vid and a < b2 + 3 and a2 < b + 3 and not forward:
                overlap.append((i2, s["i"]))
        seen.append((vid, a, b, s["i"], s["line"]))
    narr = sum(nchar(L["tts"]) for L in LINES if L["kind"] == "나레")
    narr_s = sum(line_dur(L) for L in LINES if L["kind"] == "나레")
    return {"길이_추정": total, "컷": len(shots), "컷_중앙": round(med, 2), "컷_최소": durs[0],
            "±3초_재사용(다른 줄)": overlap, "나레_자수(TTS,공백뺌)": narr, "나레_초": round(narr_s, 2),
            "자막_최대자수": max(len(x) for L in LINES for x in L["sub"]),
            "원음_초": round(sum(line_dur(L) for L in LINES if L["kind"] == "원음"), 2)}


TITLES = {"line1": "공구 없이 벽 구멍", "line2": "메워 준다는 제품?!"}


def doc_update():
    p = HERE / "대본.json"
    S = json.loads(p.read_text(encoding="utf-8"))
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
    S.setdefault("final", {})["lines"] = out
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '구멍난 벽을 쉽게 / 고쳐준다는 제품'과 3어절 연속 겹침 0, 줄당 ≤12자(rules title.line_chars_max)"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    shots, total = build()
    mat = {"_note": "샥탬스토리 7편 Wall Doctor Rx 재료 계획 — TTS·렌더 전. 창 1080x1052(벤치 vbxJ_v132ao 창 [0,435,1080,1050] ≒ 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물). 원음 컷은 src_orig_span 그대로 원본 소리(영어 원음 트랙 h99r2Xmp-Xg_audio.m4a).",
           "sources": {
               CLIP: {"채널": "CNBC Ambition(공식)", "제목": "Two Sharks Make Quick Offers For The Wall Doctor Rx. | Shark Tank | CNBC Prime",
                      "해상도": "1920x1080 24fps (137 + 140-7 영어 원음)", "길이": 329.6, "받은 구간": "전체",
                      "남의 글자": "왼쪽 아래 CNBC 공작 로고 + 'SHARK TANK TONIGHT 10P ET'/'TO FIND CNBC…' 띠(y≥950) — 모든 컷 크롭 h≤940 로 뺌. "
                                 "이름·제안 띠(31~35·112~117·122~126초, y≥800) — 112~113.4 컷만 쓰고 h 795 로 뺌. 창업자 가운 'The WallDoctor' 자수 = 제품 브랜드"},
               BULB: {"채널": "BulbHead(판매사 공식)", "제목": "Learn how to fix a hole in the wall with Wall Doctor", "업로드": "2016-10-17",
                      "해상도": "1920x1080 (137, 영상만)", "길이": 71.4, "남의 글자": "26~28초 'Support Disc'·'Frame with Compound'·48~56초 'NO …' 글자 — 안 씀. 쓴 24.2~25.1·59.3~60.6 은 글자 없음(포장 글자 = 제품)"},
               OIVP: {"채널": "FIX IT Home Improvement Channel(실사용 리뷰)", "제목": "Repairing Drywall Without Tools - Wall Doctor", "업로드": "2016-05-23",
                      "해상도": "1280x720 (136, 최대 화질 — 1080p 없음)", "길이": 118.6, "남의 글자": "없음(시트 0.5~2초 간격 눈 확인)"},
               MZ: {"채널": "Life Uncontained(집 고치는 부부 브이로그)", "제목": "Hanging DRYWALL!", "업로드": "2021-01-07",
                    "해상도": "1920x1080 (137)", "받은 구간": "160~245초 8MZ_160.mp4", "남의 글자": "없음"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": TITLES, "shots": shots, "cand_dir": str(SRC).replace("\\", "/")}
    # 꾸밈 — 벤치 vbxJ 실측(30fps 색 평균·bench_rings·스펙트로그램) 자리 그대로. 번쩍 at = 창 가운데(auto)
    mat["effects"] = [
        {"line": "N1", "kind": "red_circle", "stroke": 5, "t": [0.0, 0.58], "how": "object", "target": [60, 670, 520, 820],
         "target_what": "창업자가 벽에 댄 망치 전체(머리+자루, 손 앞까지) — 원본 20.35초 완성본 격자 r3/n1_2035.jpg",
         "why": "R3(10-20): 0초 원 = 망치 전체, fx_place.fix(hook_object)가 추적·크기·얼굴 겹침 검사로 at·size·track 을 채운다 — 정본은 재료.json(R3_7편.json)"},
        {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 2.20 빨강 번쩍(+띠링 낮은 두 음 1.57·2.10kHz)"},
        {"line": "O4", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 11.87 초록 번쩍(+띠링 9.7·5.46kHz 12.12)"},
        {"line": "N5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 16.07 초록 번쩍(+띠링 2.64kHz 16.14)"},
        {"line": "O5", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 20.43 빨강 번쩍(벤치는 뒤 띠링 없음)"}]
    mat["sfx_not_drawn"] = ["O1 '와우' 컷 첫머리 '띠용' 스프링 소리(벤치 1.44~1.86, 2.2→1.5→3.1kHz 휘는 줄) — 팩21 칸(두둥·뽁·둥·띠링·휙·틱·딸깍)에 없음",
                            "N6 첫머리 띠링(번쩍 없이, 벤치 22.04) · O8 '15만 달러' 띠링(번쩍 없이, 벤치 27.50) — rules sfx.on 은 번쩍·곡선화살표에만 소리를 붙임"]
    doc_update()
    (HERE / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--no-sheet" not in sys.argv:
        (HERE / "plan").mkdir(exist_ok=True)
        sheet(shots, HERE / "plan" / "계획_시트.jpg", " / ".join(TITLES.values()))
    c = check(shots, total)
    print(json.dumps(c, ensure_ascii=False))
    for x in shots:
        print(x["i"], x["line"], x["kind"], x["src"], x["src_orig_span"], x["dur"], x["t_final_est"], x["src_crop"], file=sys.stderr)
    return shots, c


if __name__ == "__main__":
    main()
