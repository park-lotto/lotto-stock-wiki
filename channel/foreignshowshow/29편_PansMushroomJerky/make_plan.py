# -*- coding: utf-8 -*-
"""샥탬스토리 29편 Pan's Mushroom Jerky — 벤치 해외쇼츠 Qu3S7KKz4JM(「이게 육포가 진짜 아니라고?!」 57.6만, 47.9초) 줄 단위 칼카피 (관제 097, 2026-10-28).

    PYTHONUTF8=1 py channel/foreignshowshow/29편_PansMushroomJerky/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg 를 만든다(앞 편 make_plan 꼴).
원음 줄 = 같은 회차 원본(Sony Pictures Television 공식 'Shark Tank US | Sharks Fight To Get A Deal With Pan's Mushroom Jerky' Gsb98jeXm14, 1080p 30fps,
영어 원음 140-6 'English (US) original (default)' — 자동 더빙 트랙 6개(hi·pt·fr·es·id·de)가 있어 yt-dlp -F 로 원어 번호를 골라 -f 137+140-6, 10-28)에서.
받아쓰기 = 스피치매틱스 enhanced 영어·화자 구분(C:/숏템_칼카피/foreignshowshow/29편_PansMushroomJerky/asr/src_sm.json·src_sm.txt). 샷 경계 = asr/src_scenes12.txt(scene>0.12).
★원본 이름·요청 띠(116~126초 'MICHAEL PAN'·'Seeking $300k')·제안 띠 구간은 안 쓴다. 쓰는 컷은 띠 없음.
★화면이 주황(포장·무대 간판)·빨강(투자자 소매) — 자막 강조색 빨강·분홍·주황 금지(체크리스트 ④, emph_ban).
★앞은 하이브리드 재료 — 하이브리드는 O3 끝에서 자른다. 벤치의 '원가 2,300원·판매가 11,000~13,000원'·'4억에 지분 20%'·'몇십억 매출'(금액·지분·출처 없는 매출)·'채식주의자에게 어필'(건강 주장)은 쓰지 않는다. 섬유질·비타민·건강 주장도 하지 않는다.
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
SRC = Path("C:/숏템_칼카피/foreignshowshow/29편_PansMushroomJerky/src")
CLIP = "Gsb98jeXm14"
FILES = {CLIP: ("Gsb98jeXm14.mp4", 0.0, (1920, 1080))}
AUDIO = "Gsb98jeXm14_audio.m4a"        # 영어 원음(140-6 'English (US) original (default)' — 더빙 트랙 6개 중 원어, yt-dlp -F 확인 10-28)
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
# Sony 원본: 고정 로고 없음 · 116~126초 이름/요청 띠·제안 띠는 안 쓰는 구간 · 끝 화면 안 씀.
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
    {"id": "O1", "kind": "원음", "beat": "반응(결말 반응 0초)", "audio": (89.38, 91.70), "en": "Really good. I love it.",
     "sub": ["진짜 맛있다!", "완전 좋은데?"], "facts": ["f1"], "cap_at": [89.38, 91.14], "style": "원음반응_크게",
     "fx": "0초 빨간 원(R3 물건 = 도마 위 버섯 육포 덩어리) — 벤치 0~1.0 투자자 육포 씹기(우리는 물건 원)",
     "cuts": [C(CLIP, 180.80, 182.00, 554, ours="도마 위 버섯 육포 덩어리와 오리지널·제스티 타이 봉지(원본 샷 179.21~182.22, 사람 없음 — 소리 = 투자자 원음 'Really good.' cover, 말한 사람은 다음 컷)", cover=True),
              C(CLIP, 90.58, 91.70, ours="육포를 먹으며 말하는 투자자 본인(원본 샷 88.56~91.79 — 소리 = 이 줄 원음 이어서, 화면초 = 소리초)", cover=True)]},
    {"id": "N1", "kind": "나레", "beat": "문제(훅)", "text": "샤크들이 쫄깃한 육포를 한 입씩 씹어 보는데 다들 맛있다고 난리인데",
     "tts": "샤크들이 쫄깃한 육포를, 한 입씩 씹어 보는데, 다들 맛있다고 난리인데",
     "sub": ["샤크들이 쫄깃한 육포를", "한 입씩 씹어 보는데", "다들 맛있다고 난리인데"], "facts": ["f1"],
     "fx": "빨강 번쩍 — 벤치 0.5('육포를 씹는 투자자들')",
     "cuts": [C(CLIP, 78.46, 80.70, ours="육포를 씹는 투자자(원본 샷 78.45~80.71, 소리 끔)"),
              C(CLIP, 82.79, 84.91, ours="육포를 먹는 투자자(샷 82.78~84.92, 소리 끔)")]},
    {"id": "N2", "kind": "나레", "beat": "해답(반전 예고)", "text": "그때 창업자가 이 고기 같은 식감에 대해 고백할 게 있다는데",
     "tts": "그때 창업자가, 이 고기 같은 식감에 대해, 고백할 게 있다는데",
     "sub": ["그때 창업자가", "이 고기 같은 식감에 대해", "고백할 게 있다는데"], "facts": ["f2"],
     "fx": "초록 번쩍 — 벤치 6.4('그런데 사실은')",
     "cuts": [C(CLIP, 15.00, 18.50, ours="무대에서 말하는 창업자(원본 샷 12.41~21.29, 띠 없음, 소리 끔 — 84.9초 전신 컷은 거의 멈춰 freezedetect 0.53초라 바꿈)"),
              C(CLIP, 46.60, 49.60, 960, ours="화면 속 육포를 손으로 찢는 근접(원본 샷 46.41~54.52, 손·제품만, 소리 끔)")]},
    {"id": "O2", "kind": "원음", "beat": "해답(정체)", "audio": (91.80, 95.84), "en": "Is actually... mushrooms.",
     "sub": ["사실은…", "버섯이에요!"], "facts": ["f2"], "cap_at": [91.80, 95.20], "style": "원음반응_크게",
     "cuts": [C(CLIP, 91.80, 93.47, ours="말하는 창업자 본인(원본 샷 91.79~93.49)"),
              C(CLIP, 169.00, 170.39, 960, ours="오리지널 봉지 앞 도마 위 버섯 육포 덩어리(원본 샷 168.87~171.07, 사람 없음 — 소리 = 창업자 원음 그 시각의 쉼)", cover=True),
              C(CLIP, 94.86, 95.84, ours="말하는 창업자 본인(샷 94.86~95.90 — 소리 = 원음 그 시각)")]},
    {"id": "O3", "kind": "원음", "beat": "해답(반응)", "audio": (99.66, 102.15), "en": "I was wondering why I love it even more.",
     "sub": ["어쩐지!", "더 맛있더라"], "facts": ["f3"], "cap_at": [99.66, 100.60],
     "cuts": [C(CLIP, 29.25, 30.82, 1000, ours="창업자 손끝에 든 육포 한 조각(원본 샷 28.76~31.43, 얼굴 없음 — 소리 = 투자자 원음 cover)", cover=True),
              C(CLIP, 101.24, 102.15, ours="말하는 투자자 본인(원본 샷 101.23~102.24 — 렌더가 원음 줄을 0.05초 늘려도 옆 샷이 안 섞이게 102.15 에서 끊음 — 화면초 = 소리초)")]},
    {"id": "N3", "kind": "나레", "beat": "계기", "text": "알고 보니 말레이시아 사촌이 만든 간식을 고기인 줄 알았다는데",
     "tts": "알고 보니, 말레이시아 사촌이 만든 간식을, 고기인 줄 알았다는데",
     "sub": ["알고 보니", "말레이시아 사촌이 만든 간식을", "고기인 줄 알았다는데"], "facts": ["f4"],
     "cuts": [C(CLIP, 145.60, 149.40, ours="말레이시아 이야기를 하는 창업자(원본 샷, 소리 끔)")]},
]


def src_of(vid: str, t: float) -> tuple[str, float]:
    f, base, _ = FILES[vid]
    return f, round(t - base, 3)


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = Path("C:/숏템_칼카피/foreignshowshow/29편_PansMushroomJerky/work/render/render_info.json")


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
    d.text((8, 8), f"샥탬스토리 29편 Pan's Mushroom Jerky — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: {title}", fill=(0, 0, 0), font=font)
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


TITLES = {"line1": "샤크들이 씹은 육포", "line2": "정체가 버섯이라고?!"}
U = "https://www.youtube.com/watch?v="
FACTS = {
    "f1": {"text": "원본 89.38~91.70 'Really good.' 'I love it.'(스피치매틱스 enhanced 영어 — 투자자 원음, 이름은 자막에 안 씀) · 화면 78~85 투자자들이 육포를 씹음 · 0초 화면은 같은 원본 180.8초 도마 위 버섯 육포(cover)", "url": U + CLIP + "&t=78s", "kind": "방송 원음+화면"},
    "f2": {"text": "원본 80.70~99.62 'But before you share them, I have to admit something. That marvelously meaty texture that you're experiencing … is actually … mushrooms. That's right. Pan's mushroom jerky.'", "url": U + CLIP + "&t=80s", "kind": "방송 원음+화면"},
    "f3": {"text": "원본 99.66~102.02 'I was wondering why I love it even more.'(투자자 원음) · 128.49~129.89 'These are all shiitakes, by the way.'", "url": U + CLIP + "&t=99s", "kind": "방송 원음+화면"},
    "f4": {"text": "원본 134.05~161.01 'So my father was born and raised in a small fishing village in Malaysia. … I reach in and try it … It must be pork. … The person who served it was my cousin and he was vegetarian…'", "url": U + CLIP + "&t=134s", "kind": "방송 원음"},
    "f5": {"text": "원본 556.30~564.06 '18. You got a deal?' 'I'll do it for 15.' 'Mark, you got a deal?' — 금액·지분은 대본에 안 씀(앞 칼카피는 O3 뒤에서 잘려 하이브리드에 안 들어감)", "url": U + CLIP + "&t=556s", "kind": "방송 원음+화면"},
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
        "topic": "Pan's Mushroom Jerky(판스 버섯 육포) — 표고버섯으로 만든 육포. 샤크들이 '진짜 맛있다'며 씹은 쫄깃한 육포의 정체가 버섯 → '어쩐지 더 맛있더라' → 말레이시아 사촌의 간식에서 시작 → 투자 경쟁 끝에 마크와 성사",
        "product": "Pan's Mushroom Jerky(표고버섯 육포)",
        "bench": {"id": "Qu3S7KKz4JM", "channel": "해외쇼츠 @foreignshowshow", "title": "이게 육포가 아니라고?! (화면 제목: 이게 육포가 / 진짜 아니라고?!)",
                  "dur": 47.9, "views": 576000, "window": [0, 434, 1080, 1052], "cut_median": 1.5, "_cut_median_how": "1초 시트 눈 측정 — 10-28"},
        "form": "벤치 그대로 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 틀 = preset 「샤크탱크_검정띠2줄」",
        "dropped": [
            "벤치 '원가 2,300원·판매가 11,000~13,000원'·'4억에 지분 20%'(금액·지분) → 쓰지 않음",
            "벤치 '채식주의자에게 어필이 되며'·원본 'high in fiber and vitamin D'·'so healthy'(건강·영양 주장) → 쓰지 않음",
            "벤치 끝 '방송 나간 뒤 이틀 만에 투자액을 거둬들였고 지금은 몇십억 매출'(1차 출처 못 찾음) → 쓰지 않음",
            "벤치 남의 틱톡·리뷰 영상(남의 얼굴) — 이 원본 밖 → 원본 무대·제품 컷으로"],
    })
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 '이게 육포가 / 진짜 아니라고?!'과 3어절 연속 겹침 0, 줄당 ≤12자"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    S["facts"] = FACTS
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


EFFECTS = [
    {"line": "O1", "kind": "red_circle", "how": "object", "t": [0.0, 0.45], "target": [282, 1100, 672, 1245], "target_what": "도마 위 버섯 육포 덩어리(오리지널 봉지 앞) — 181.0초 원본 프레임 눈 측정(창 크롭 [0,0,1109,1080] 안 x 290~690·y 690~830 → ×0.974 완성본 좌표)",
     "why": "R3 0초 원 = 물건(제품) — 사장님 10-19 '처음에 빨간원 얼굴에 하지말고'"},
    {"line": "N1", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "빨강", "how": "auto", "why": "벤치 0.5"},
    {"line": "N2", "kind": "flash", "at": [540, 960], "t": [0.0, 0.45], "color": "초록", "how": "auto", "why": "벤치 6.4 반전 예고"},
    {"line": "O2", "kind": "flash", "at": [540, 960], "t": [3.3, 3.75], "color": "초록", "how": "auto", "why": "정체 공개(버섯)"},
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
    mat = {"_note": "샥탬스토리 29편 Pan's Mushroom Jerky 재료 계획. 창 1080x1052(벤치 Qu3S7KKz4JM, 채널 고정 [0,434,1080,1052]). "
                    "make_plan.py LINES 가 정본(이 파일은 생성물, effects 의 fx_place 계산값은 유지). 원음 컷은 원본 소리(Gsb98jeXm14_audio.m4a).",
           "sources": {
               CLIP: {"채널": "Sony Pictures Television(공식)", "제목": "Shark Tank US | Sharks Fight To Get A Deal With Pan's Mushroom Jerky", "해상도": "1920x1080 30fps (137) + 140-6 영어 원어(더빙 6개 중 original)",
                      "길이": 650.0, "받은 구간": "전체",
                      "남의 글자": "116~126초 이름/요청 띠·제안 띠 안 씀 · 끝 화면 안 씀 · 무대·포장 'Pan's'·'MUSHROOM JERKY' 글 = 제품 브랜드"}},
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
