# -*- coding: utf-8 -*-
"""샥탬스토리 30편 Prank-O — 벤치 해외쇼츠 Jlo0i1kEtkQ(「안에 있는 선물이랑 선물 박스가 다르다고?!」 43.2만, 45.3초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/30편_PrankO/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Hilarious Prank-O Pitch Has The Sharks In Stitches!' -hrbP_slqRI, 1080p 29.97fps,
영어 원음 140-4 'English (US) original (default)' — 자동 더빙 트랙 4개(de·es·hi·it)가 있어 yt-dlp -F 로 원어 번호를 골라 -f 137+140-4, 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/30편_PrankO/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청·제안 띠 구간은 안 쓴다. 쓰는 컷은 띠 없음. 화면 속 가짜 상품 상자(Crib Dribbler·PET VR·Roto Wipe)·'RYNARIK' 간판·'prank-o' 글 = 이 회사 제품·연출.
★화면이 빨강(창업자 티셔츠·포장지)·분홍(상자) — 자막 강조색 빨강·분홍·주황 금지(체크리스트 ④, emph_ban).
★앞은 하이브리드 재료 — 하이브리드는 O2 끝에서 자른다. 벤치의 '원가 1,000원·판매 11,000원'·'박스 하나 디자인 40시간'·'빚더미'(금액·출처 약한 숫자)는 쓰지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/30편_PrankO/src")
CLIP = "hrbP_slqRI"
FILES = {CLIP: ("hrbP_slqRI.mp4", 0.0, (1920, 1080))}
AUDIO = "hrbP_slqRI_audio.m4a"        # 영어 원음(140-4 'English (US) original (default)' — 더빙 트랙 4개 중 원어, yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 이름/요청/제안 띠는 안 쓰는 구간 · 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (131.85, 136.37), "en": "I got a baby feeder for the... Virtual reality headset for... a cat.",
     "sub": ["아기 밥 먹이는 기계?", "고양이용 VR 헤드셋?!"], "facts": ["f1"], "cap_at": [131.85, 133.30], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 투자자가 뜯은 'Crib Dribbler' 가짜 상품 상자 속 젖병 그림) — 벤치 0~1.0 '기상천외한 물건을 받은 투자자들'(우리는 물건 원)",
     "cuts": [C(CLIP, 133.25, 134.68, 1110, ours="뜯은 상자 근접 — 아기 침대에 매단 젖병 그림 'Crib Dribbler'(원본 샷 131.63~134.70 뒤쪽, 손·상자만 — 소리 = 투자자 원음 'I got a baby feeder for the' cover, 이 상자 이야기)", cover=True),
              C(CLIP, 139.60, 141.38, ours="고양이 VR 상자를 들고 말하는 투자자(원본 샷 139.57~141.41 — 소리 = 이 상자를 받은 투자자 원음 'Virtual reality headset for' cover)", cover=True),
              C(CLIP, 134.72, 136.03, ours="상자를 뜯어 든 투자자들 전경(원본 샷 134.70~136.67 — 소리 = 원음 '…for a cat' cover)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "창업자가 샤크들한테 선물을 하나씩 돌렸는데 포장을 뜯어 보니",
     "tts": "창업자가 샤크들한테, 선물을 하나씩 돌렸는데, 포장을 뜯어 보니",
     "sub": ["창업자가 샤크들한테", "선물을 하나씩 돌렸는데", "포장을 뜯어 보니"], "facts": ["f2"],
     "fx": "빨강 번쩍 — 벤치 0.8('기상천외한 물건을 받은')",
     "cuts": [C(CLIP, 120.25, 122.75, ours="줄무늬 포장을 뜯는 투자자(원본 샷 120.22~122.79, 소리 끔)"),
              C(CLIP, 122.82, 124.80, 960, ours="빨간 포장지를 뜯는 손 근접(샷 122.79~124.82, 손만, 소리 끔)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(반전 예고)", "text": "세상에 없는 황당한 물건 상자들이 줄줄이 나오는데",
     "tts": "세상에 없는, 황당한 물건 상자들이, 줄줄이 나오는데",
     "sub": ["세상에 없는", "황당한 물건 상자들이", "줄줄이 나오는데"], "facts": ["f1", "f3"],
     "fx": "초록 번쩍 — 벤치 4.0('사실 이건 존재하지 않는')",
     "cuts": [C(CLIP, 124.86, 126.76, ours="고양이 VR 상자를 든 투자자(원본 샷 124.82~126.79, 소리 끔)"),
              C(CLIP, 145.62, 146.89, 960, ours="'Roto Wipe' 가짜 상품 상자 근접(샷 145.58~147.58, 손·상자만, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(정체)", "audio": (146.89, 150.40), "en": "Our actual company is Prank-O. We sell prank gift boxes.",
     "sub": ["우리 진짜 회사는 프랭크오!", "장난 선물 상자를 팔아요"], "facts": ["f3"], "cap_at": [146.89, 149.13], "style": "원음반응_크게",
     "cuts": [C(CLIP, 146.89, 147.56, 960, ours="같은 'Roto Wipe' 상자 근접 이어서(샷 145.58~147.58 — 소리 = 창업자 원음 그 시각)"),
              C(CLIP, 147.60, 150.40, ours="겉옷을 벗고 'prank-o' 티셔츠를 드러낸 창업자 둘(원본 샷 147.58~150.52 — 말하는 본인)")]},
    {"id": "N3", "kind": "나레", "beat": "해답(쓰는 법)", "text": "진짜 선물은 이 상자 안에 숨기고 받는 사람 표정을 구경하는 거라는데",
     "tts": "진짜 선물은 이 상자 안에 숨기고, 받는 사람 표정을, 구경하는 거라는데",
     "sub": ["진짜 선물은 이 상자 안에 숨기고", "받는 사람 표정을", "구경하는 거라는데"], "facts": ["f4"],
     "cuts": [C(CLIP, 165.30, 167.97, 960, ours="진열대의 장난 선물 상자 'Auto Sauna'(원본 샷 165.27~168.00, 사람 없음, 소리 끔)"),
              C(CLIP, 168.03, 170.50, 960, ours="진열대의 장난 선물 상자 'Spit N Slide'(샷 168.00~170.54, 사람 없음, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/30편_PrankO/work/render/render_info.json")


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
                          "url": f"https://www.youtube.com/watch?v=-{vid}", "src_orig_span": [a, round(a + dur, 3)], "ss": ss,
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
    d.text((8, 8), f"샥탬스토리 30편 Prank-O — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "선물 뜯었더니", "line2": "황당한 물건이?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 131.85~136.37 'I got a baby feeder for the…' 'Virtual reality headset for… a cat.'(스피치매틱스 enhanced 영어 — 투자자 원음, 이름은 자막에 안 씀) · 화면 131.6~134.7 'Crib Dribbler' 상자·125~127·139~141 'PET VR' 상자", "url": U + "-hrbP_slqRI&t=131s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 103.55~119.79 'Our gifts to you.' 'Oh, presents.' … 'Go unwrap them.' · 화면 107~124 창업자가 선물을 돌리고 투자자들이 뜯음", "url": U + "-hrbP_slqRI&t=103s", "kind": "방송 원음+화면"},
    "f3": {"text": "원본 146.89~150.57 'Our actual company is Prank-O. We sell prank gift boxes.' · 156.25~160.77 'Is there actually something in here?' 'No.' 'That's the whole point.'", "url": U + "-hrbP_slqRI&t=146s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 163.69~169.97 'Simply buy any of our prank boxes. You hide your real gift inside, and you sit back and watch as the fun unfolds.'", "url": U + "-hrbP_slqRI&t=163s", "kind": "방송 원음"},
    "f5": {"text": "원본 479.34~489.72 마크 제안 · 629.37~642.61 'it's going to be a great partnership. We got a deal.' — 금액·로열티는 대본에 안 씀(앞 칼카피는 O2 뒤에서 잘려 하이브리드에 안 들어감)", "url": U + "-hrbP_slqRI&t=479s", "kind": "방송 원음+화면"},
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
        "topic": "Prank-O(프랭크오) — 세상에 없는 황당한 가짜 상품이 인쇄된 선물 포장 상자. 창업자가 선물을 돌림 → 뜯어 보니 고양이 VR·아기 젖병 매달이 같은 황당한 물건 → '진짜 회사는 장난 선물 상자' → 진짜 선물은 안에 숨기고 표정 구경 → 마크와 성사",
        "product": "Prank-O prank gift box(장난 선물 포장 상자)",
        "bench": {"id": "Jlo0i1kEtkQ", "channel": "해외쇼츠 @foreignshowshow", "title": "선물 없는 선물 박스?! (화면 제목: 안에 있는 선물이랑 / 선물 박스가 다르다고?!)",
                  "dur": 45.3, "views": 432000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "1초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '제조원가 1000원에 판매는 1만 1000원'(금액) → 쓰지 않음",
            "벤치 '박스 하나당 디자인만 40시간'·'빚더미'(출처 약한 숫자·과장) → 쓰지 않음",
            "벤치 남의 영상(이스라엘 방송 등) — 이 원본 밖 → 원본 무대·상자 컷으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '안에 있는 선물이랑 / 선물 박스가 다르다고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [440, 554, 720, 774], "target_what": "상자 그림 속 아기 침대에 매단 젖병 주머니 — 133.5초 원본 프레임 눈 측정(창 크롭 [555,0,1109,1080] 안 젖병 주머니 윗부분 → 완성본 좌표 — 아래 아기 얼굴 그림과 원판이 안 겹치게, 132.6~133.2 흰 번쩍 뒤부터)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.8"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 4.0 반전 예고"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [0.7, 1.15], "color": "초록", "how": "auto", "why": "정체 공개(티셔츠)"},
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
    mat = {"_note": "샥탬스토리 30편 Prank-O 재료 계획. 창 1080x1052(벤치 Jlo0i1kEtkQ, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(hrbP_slqRI_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Hilarious Prank-O Pitch Has The Sharks In Stitches!", "해상도": "1920x1080 29.97fps (137) + 140-4 영어 원어(더빙 4개 중 original)",
                      "길이": 663.1, "받은 구간": "전체",
                      "남의 글자": "이름/요청/제안 띠 안 씀 · 끝 화면 안 씀 · 가짜 상품 상자·'RYNARIK' 간판·'prank-o' 티셔츠 = 이 회사 제품·연출"}},
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
