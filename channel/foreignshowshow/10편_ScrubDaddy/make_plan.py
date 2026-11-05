# -*- coding: utf-8 -*-
"""샥탬스토리 10편 Scrub Daddy — 소재 벤치 BIG BAG HUSTLE BVMDZG6mEKY('Best Negotiation EVER on Shark Tank', 2,078만) 원음 순간 +
foreignshowshow 공식 6박자·효과 꼴 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py channel/foreignshowshow/10편_ScrubDaddy/make_plan.py [--no-sheet]
줄·컷 정본(LINES) 하나에서 대본.json(final.lines) · 재료.json · plan/계획_시트.jpg · plan/hook_vs_bench.jpg 를 만든다.
원음 줄 = 벤치(BBH)가 쓴 원음 순간을 **같은 공식 원본(Shark Tank Global ae5MssJ8en4, 741초 1080p) 시각**으로 — 근거.md §2 표.
크롭 가운데 = 컷 가운데 프레임의 검출(cx 'face' = YuNet 가장 큰 얼굴 / 'yellow' = 노란 수세미 덩어리) — 눈대중 좌표 아님.
0초 빨간 원·첫 컷 크롭 = fx_place.hook_circle(얼굴 검출). 화살표 대상 = 노란 수세미 덩어리 상자(검출) → fx_place.on_target.
나레 시각은 7.8자/초 추정 — TTS 뒤(render.py --tts-only) render_info 로 줄 길이만 다시 잰다.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.shark import fx_measure as FM, fx_place as FP  # noqa: E402

BASE = Path("C:/숏템_칼카피/foreignshowshow/10편_ScrubDaddy")
SRC = BASE / "src"
BENCH_MP4 = BASE / "bench/BVMDZG6mEKY.webm"
QMJ_MP4 = Path("C:/숏템_칼카피/foreignshowshow/mp4/QMJtjJz4M6w.mp4")
CLIP = "ae5MssJ8en4"
FILES = {CLIP: ("ae5MssJ8en4.mp4", 0.0, (1920, 1080))}
AUDIO = "ae5MssJ8en4_audio.m4a"        # 원본 영어 원음(140) — 영상에서 소리만 뺀 것
VOICE = {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "speed": 1.25}
RATE = 7.8
WIN = (1080, 1052)
AR = WIN[0] / WIN[1]
H_BANNER = 810      # 제안 띠('Lori's offer…'·'Daymond's offer…', 1080p y 820~970)를 빼는 크롭 높이(O5~O7)
CACHE = BASE / "work/crop_cache.json"
_cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def _frame(t: float) -> np.ndarray:
    a, _, _ = FP._src_frame(SRC / FILES[CLIP][0], t)
    return a


def _yellow_box(a: np.ndarray):
    """노란 수세미(Scrub Daddy 노랑) 픽셀 덩어리 상자 [x0,y0,x1,y1] — 소스 좌표. 없으면 None."""
    r, g, b = (a[..., k].astype(int) for k in range(3))
    m = (r > 170) & (g > 150) & (b < 120) & (r - b > 90) & (abs(r - g) < 70)
    import cv2
    m8 = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m8, 8)
    if n < 2:
        return None
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))          # 가장 큰 노란 덩어리 = 수세미(유리 상판 반사·주황 셔츠 번짐 제외)
    if st[k, cv2.CC_STAT_AREA] < 800:
        return None
    x, y, w, h = (int(st[k, j]) for j in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
    return [x, y, x + w, y + h]


def center(a: float, b: float, how) -> float:
    """크롭 가로 가운데(소스 x). how = 숫자 | 'face' | 'yellow' — 컷 가운데 프레임 검출(캐시)."""
    if isinstance(how, (int, float)):
        return float(how)
    k = f"{how}@{(a + b) / 2:.3f}"
    if k not in _cache:
        fr = _frame((a + b) / 2)
        if how == "face":
            fs = FM.faces(fr)
            _cache[k] = round(fs[0]["cx"], 1) if fs else 960.0
        else:
            bx = _yellow_box(fr)
            _cache[k] = round((bx[0] + bx[2]) / 2, 1) if bx else 960.0
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return _cache[k]


def crop(a, b, how, h=1080, y=0):
    W, H = FILES[CLIP][2]
    w = int(round(h * AR))
    cx = center(a, b, how)
    x = max(0, min(W - w, int(cx - w / 2)))
    return [x, y, w, h]


def C(a, b, how, what, h=1080):
    return (CLIP, a, b, crop(a, b, how, h), what)


# 원음 줄 audio = (원본 시작, 끝) — 원본 초. cut = (소스, 원본 시작, 원본 끝, [x,y,w,h], 화면에 보이는 것)
LINES = [
    {"id": "O1", "kind": "원음", "beat": "의문(반응 먼저)", "audio": (401.32, 406.90),
     "en": "if it's a hero or a zero. And I think what you've got here is a hero.",
     "sub": ["히어로인지 제로인지", "이건 히어로예요!"], "facts": ["f1"], "cap_at": [401.32, 403.6],
     "fx": "0초 빨간 실선 원(투자자 로리 얼굴, fx_place.hook_circle) — 벤치 BBH 0초 = 같은 로리 'I can tell instantly…'(효과 없음) · foreignshowshow 0초 결말 반응 원",
     "cuts": ["HOOK",
              C(403.203, 404.838, "face", "창업자 에런(주황 셔츠)이 수세미 들고 들음(원본 편집 그대로)"),
              C(404.838, 406.206, "face", "투자자 데이먼드 반응(원본 편집 그대로 — 원음은 로리)"),
              C(406.206, 406.90, "face", "로리가 'is a hero' 말함(말하는 본인)")]},
    {"id": "N1", "kind": "나레", "beat": "해답(제품)", "text": "웃는 얼굴 수세미가 보통이 아니라는데", "tts": "웃는 얼굴 수세미가 보통이 아니라는데",
     "sub": ["웃는 얼굴 수세미가", "보통이 아니라는데"], "facts": ["f2"],
     "fx": "초록 아래 화살표(수세미 위 끝) — 벤치 QMJ 0.567 둘째 컷 제품",
     "cuts": [C(157.20, 159.40, "yellow", "웃는 얼굴 노란 수세미를 손에 든 근접(얼굴 없음)")]},
    {"id": "O2", "kind": "원음", "beat": "시연(원리)", "audio": (32.75, 37.00),
     "en": "Scrub Daddy completely changes its texture by just adjusting your water temperature.",
     "sub": ["물 온도만 바꾸면", "질감이 완전히 바뀌어요"], "facts": ["f3"], "cap_at": [32.75, 34.9],
     "fx": "초록 번쩍(장면 넘김) — 벤치 QMJ 7.1",
     "cuts": [C(32.75, 35.936, "yellow", "에런이 두 손에 수세미를 들고 말함(말하는 본인, 가슴 높이)"),
              C(35.936, 37.00, "face", "에런 상반신(말하는 본인)")]},
    {"id": "N2", "kind": "나레", "beat": "시연", "text": "찬물에선 딱딱해져서 눌어붙은 때를 벗겨 내고", "tts": "찬물에선 딱딱해져서 눌어붙은 때를 벗겨 내고",
     "sub": ["찬물에선 딱딱해져서", "눌어붙은 때를 벗겨 내고"], "facts": ["f4"],
     "fx": "빨간 곡선 화살표(유리 상판을 문지르는 수세미)+휙 — 벤치 QMJ 20.367 둘째 시연",
     "cuts": [C(57.95, 59.95, 960, "4.5kg 아령 두 개를 수세미 위에 — 한쪽은 눌리고 한쪽은 버팀(딱딱)"),
              C(71.80, 73.80, "yellow", "수세미로 탄 자국 난 유리 상판을 문지름(근접)")]},
    {"id": "N3", "kind": "나레", "beat": "시연", "text": "따뜻한 물에선 말랑해져서 흠집도 안 낸다는데", "tts": "따뜻한 물에선 말랑해져서 흠집도 안 낸다는데",
     "sub": ["따뜻한 물에선 말랑해져서", "흠집도 안 낸다는데"], "facts": ["f4"],
     "cuts": [C(79.95, 81.60, "yellow", "스테인리스 팬 안을 수세미로 닦음(근접)"),
              C(98.25, 99.90, "yellow", "수세미를 손에 끼고 유리컵 안을 닦음(근접)")]},
    {"id": "O3", "kind": "원음", "beat": "시연", "audio": (102.44, 104.55), "en": "And that smiley mouth, that cleans spoons,",
     "sub": ["웃는 입으로는", "숟가락까지 닦아요"], "facts": ["f5"], "cap_at": [102.44, 103.6],
     "cuts": [C(102.436, 104.55, "face", "에런이 수세미를 들고 시연하며 말함(말하는 본인)")]},
    {"id": "N4", "kind": "나레", "beat": "시연", "text": "입에 숟가락을 끼우면 앞뒤가 한 번에 닦인다고", "tts": "입에 숟가락을 끼우면 앞뒤가 한 번에 닦인다고",
     "sub": ["입에 숟가락을 끼우면", "앞뒤가 한 번에 닦인다고"], "facts": ["f5"],
     "cuts": [C(106.30, 109.80, "yellow", "웃는 입 구멍에 숟가락을 끼워 앞뒤로 닦음(근접)")]},
    {"id": "N5", "kind": "나레", "beat": "숫자", "text": "넉 달 만에 10만 달러 넘게 팔았다는데",
     "tts": "넉 달 만에 십만 달러 넘게 팔았다는데",
     "sub": ["넉 달 만에 10만 달러", "넘게 팔았다는데"], "facts": ["f6"],
     "fx": "분홍 위 화살표(숫자 자막 '넉 달 만에 10만 달러') — 벤치 QMJ 12.017 숫자 조각",
     "cuts": [C(139.35, 141.00, "face", "투자자 로리가 수세미를 눌러 봄"),
              C(141.10, 142.30, "face", "투자자 로버트가 수세미를 들어 봄")]},
    {"id": "N6", "kind": "나레", "beat": "지분 경쟁", "text": "그러자 샤크들끼리 입찰 전쟁이 붙었는데", "tts": "그러자 샤크들끼리 입찰 전쟁이 붙었는데",
     "sub": ["그러자 샤크들끼리", "입찰 전쟁이 붙었는데"], "facts": ["f7"],
     "cuts": [C(515.75, 517.33, 960, "무대 와이드: 에런 앞에 투자자석"),
              C(518.99, 519.87, 960, "투자자석 와이드: 서로 말을 끊음")]},
    {"id": "O5", "kind": "원음", "beat": "지분 경쟁(제안)", "audio": (468.40, 472.60), "en": "I'm going to give you $150,000 for 25%.",
     "sub": ["15만 달러 줄게요", "지분 25%에!"], "facts": ["f8"], "cap_at": [468.4, 470.4],
     "fx": "초록 번쩍 + 날개 돈다발 — 벤치 QMJ 38.7 투자 제안 금액",
     "cuts": [C(468.40, 469.402, "face", "에런이 듣는 얼굴(원본 편집 그대로)", H_BANNER),
              C(469.402, 470.337, "face", "투자자 데이먼드가 제안(말하는 본인)", H_BANNER),
              C(470.337, 471.137, "face", "투자자 케빈 반응", H_BANNER),
              C(471.137, 471.871, "face", "로리 반응", H_BANNER),
              C(471.871, 472.60, 960, "투자자석 와이드", H_BANNER)]},
    {"id": "O6", "kind": "원음", "beat": "지분 경쟁(제안)", "audio": (592.55, 598.10),
     "en": "150,000 for 25%. I'll make you a millionaire within a year.",
     "sub": ["15만 달러에 25%!", "1년 안에", "백만장자 만들어 줄게요"], "facts": ["f9"], "cap_at": [592.55, 596.05, 596.9],   # 렌더 뒤 ASR(asr/o6_words.json lite 2창 I'll@596.03·596.10 + 원본 소리 크기 596.0~598.0 큼 + 로리 화면 596.1~)
     "cuts": [C(592.55, 595.094, "face", "로리가 제안(말하는 본인)", H_BANNER),
              C(595.094, 596.096, "face", "에런 반응", H_BANNER),
              C(596.096, 597.397, "face", "로리(말하는 본인)", H_BANNER),
              C(597.397, 598.10, "face", "에런 반응", H_BANNER)]},
    {"id": "O7", "kind": "원음", "beat": "지분 경쟁(제안)", "audio": (605.95, 610.00), "en": "Mine just went to two. / Whoa!",
     "sub": ["난 20만으로 올렸어요", "와우!"], "facts": ["f9"], "cap_at": [605.95, 607.7],
     "fx": "빨강 번쩍(에런 '와우' 컷 첫 프레임) — 벤치 QMJ 와우 포인트",
     "cuts": [C(605.95, 608.808, 960, "투자자석 와이드(로리 말함 — 원본 편집 그대로)", H_BANNER),
              C(608.808, 610.00, "face", "에런이 입을 벌리고 놀람", H_BANNER)]},
    {"id": "O8", "kind": "원음", "beat": "결정", "audio": (658.25, 662.45),
     "en": "You need to tell me right now whether you're going with me or not, or I'm out.",
     "sub": ["지금 당장 말해요", "나랑 할 건지 말 건지", "아니면 난 빠질게요"], "facts": ["f10"], "cap_at": [658.25, 659.6, 660.85],
     "fx": "빨강 번쩍 — 벤치 QMJ 44.4 결정",
     "cuts": [C(658.25, 659.025, "face", "에런이 들음(원본 편집 그대로)"),
              C(659.025, 661.694, "face", "로리가 몰아붙임(말하는 본인)"),
              C(661.694, 662.45, "face", "에런 반응")]},
    {"id": "O9", "kind": "원음", "beat": "결정", "audio": (673.15, 675.30), "en": "Would you consider coming down to 20?",
     "sub": ["지분 20%로", "낮춰 줄 수 있나요?"], "facts": ["f10"], "cap_at": [673.15, 674.1],
     "cuts": [C(673.15, 674.507, "face", "에런이 되물음(말하는 본인)"),
              C(674.507, 675.30, "face", "투자자 케빈 반응")]},
    {"id": "O10", "kind": "원음", "beat": "결정(성사)", "audio": (680.75, 684.55), "en": "You know what, I will. I'll go to 20. / We got a deal.",
     "sub": ["좋아요, 그렇게 해요", "20%로 할게요", "계약 성사!"], "facts": ["f10"], "cap_at": [680.75, 681.6, 682.6],
     "fx": "초록 번쩍('We got a deal' 에런 컷 첫 프레임) — 벤치 QMJ 45.7 거래 성공",
     "cuts": [C(680.75, 683.183, "face", "로리가 수락(말하는 본인)"),
              C(683.183, 684.55, "face", "에런 'We got a deal'(말하는 본인)")]},
    {"id": "N7", "kind": "나레", "beat": "결과", "text": "방송 다음 날 홈쇼핑에서 7분도 안 돼 4만 2천 개가 팔렸다고",
     "tts": "방송 다음 날 홈쇼핑에서 칠 분도 안 돼 사만 이천 개가 팔렸다고",
     "sub": ["방송 다음 날 홈쇼핑에서", "7분도 안 돼", "4만 2천 개가 팔렸다고"], "facts": ["f11"],
     "fx": "초록 번쩍 — 벤치 QMJ 49.3 방송 후 결과",
     "cuts": [C(690.95, 692.45, "face", "로리와 에런이 포옹(거래 직후)"),
              C(701.00, 704.30, 1300, "에런이 수세미를 들고 무대 밖으로 걸어 나감(끝 컷 ≥1.5)")]},
]


def hook_cut():
    """O1 첫 컷 = 로리 399.80~403.203 — 크롭·원 자리는 fx_place.hook_circle(얼굴 검출) 한 곳."""
    # 원·크롭 = 같은 샷(399.40~403.20, 카메라 고정) 전체로 잰 hook_circle 그대로 — 페이블 10-19 "원은 로리 얼굴 그대로(자리·크기 OK)".
    # 첫 컷만 401.32~ 로 줄이면 로리가 앞으로 기운 뒤 프레임만 재게 돼 얼굴/창 0.39 로 hook_circle 이 멈춤(허용 0.38) — 같은 샷이라 크롭은 같다
    r = FP.hook_circle(SRC / FILES[CLIP][0], 399.80, 403.203 - 399.80)
    r["why"] += " · 측정 창 399.80~403.20(같은 샷), 쓰는 컷 401.32~403.20"
    return r, (CLIP, 401.32, 403.203, r["src_crop"], "투자자 로리가 'I can tell instantly if it's a hero or a zero'(말하는 본인, 상반신 중간 샷)")


HOOK, HOOK_CUT = hook_cut()
for L in LINES:
    L["cuts"] = [HOOK_CUT if c == "HOOK" else c for c in L["cuts"]]


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


RINFO = BASE / "work/render/render_info.json"


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
        if L["kind"] == "나레" and scale > 1.0:
            raise ValueError(f"{L['id']} 컷 합 {cut_total:.2f} < 줄 {d:.2f} — 컷이 원본 장면 끝을 넘어감")
        for c in L["cuts"]:
            vid, a, b, cr, ours = c
            dur = round((b - a) * scale, 3)
            au = {"mute": True} if L["kind"] == "나레" else {"mute": False, "audio_src": AUDIO, "audio_ss": a, "audio_dur": dur}
            shots.append({"i": len(shots), "line": L["id"], "kind": L["kind"], "src": FILES[vid][0], **au,
                          "url": f"https://www.youtube.com/watch?v={vid}", "src_orig_span": [a, round(a + dur, 3)], "ss": round(a, 3),
                          "dur": dur, "t_final_est": [round(t, 2), round(t + dur, 2)], "res": "%dx%d" % FILES[vid][2],
                          "src_crop": cr, "scale": round(WIN[0] / cr[2], 3), "ours": ours,
                          "audio": "원본 소리(원음)" if L["kind"] == "원음" else "원본 소리 끔 + TTS"})
            t += dur
    return shots, round(t, 2)


def to_final(cr, box):
    """소스 상자 → 완성본 좌표(창 [0,434,1080,1052])."""
    x, y, w, h = cr
    s = WIN[0] / w
    return [int((box[0] - x) * s), int((box[1] - y) * s + 434), int((box[2] - x) * s), int((box[3] - y) * s + 434)]


def target_box(shots, line, k=0, frac=0.5):
    s = [x for x in shots if x["line"] == line][k]
    bx = _yellow_box(_frame(s["ss"] + s["dur"] * frac))
    if not bx:
        raise ValueError(f"{line} 컷{k} 수세미 검출 못 함")
    fb = to_final(s["src_crop"], bx)
    return [max(0, fb[0]), max(434, fb[1]), min(1080, fb[2]), min(1486, fb[3])], s


def frame(path: str, ss: float, cr, size=(270, 263)) -> Image.Image:
    x, y, w, h = cr
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-i", path, "-frames:v", "1", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale={size[0]}:{size[1]}", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(b)).convert("RGB")


def _wrap(s: str, n: int):
    out, cur = [], ""
    for w in s.split(" "):
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


def sheet(shots, eff, out: Path, title: str):
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 15)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 13)
    byline = {L["id"]: L for L in LINES}
    rowh, cw = 263 + 8, 270
    S = Image.new("RGB", (60 + 3 * cw + 520, rowh * len(shots) + 40), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.text((8, 8), f"샥탬스토리 10편 Scrub Daddy — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로, 빨간 표시 = 꾸밈 자리) · 제목: {title}", fill=(0, 0, 0), font=font)
    for k, s in enumerate(shots):
        y0 = 40 + k * rowh
        L = byline[s["line"]]
        d.text((6, y0 + 4), f"#{s['i']}", fill=(200, 0, 0), font=font)
        d.text((6, y0 + 24), s["line"], fill=(0, 0, 0), font=small)
        first = s == next(x for x in shots if x["line"] == s["line"])
        for j, frac in enumerate((0.05, 0.5, 0.95)):
            im = frame(str(SRC / s["src"]), s["ss"] + s["dur"] * frac, s["src_crop"])
            dd = ImageDraw.Draw(im)
            for e in eff:
                if e["line"] != s["line"] or e["kind"] == "flash":
                    continue
                ln_t0 = next(x for x in shots if x["line"] == s["line"])["t_final_est"][0]
                tt = s["t_final_est"][0] + s["dur"] * frac - ln_t0
                if not (e["t"][0] <= tt <= e["t"][1]):
                    continue
                fx_, fy_ = e["at"][0] / 4, (e["at"][1] - 434) / 4
                if e["kind"] == "red_circle":
                    r = e["size"] / 2 / 4
                    dd.ellipse([fx_ - r, fy_ - r, fx_ + r, fy_ + r], outline=(255, 30, 30), width=3)
                else:
                    dd.ellipse([fx_ - 8, fy_ - 8, fx_ + 8, fy_ + 8], outline=(255, 0, 255), width=3)
                    dd.text((fx_ + 10, fy_ - 8), e["kind"], fill=(255, 0, 255), font=small)
            S.paste(im, (60 + j * cw, y0))
        tx = 60 + 3 * cw + 8
        col = (0, 90, 200) if L["kind"] == "원음" else (0, 0, 0)
        d.text((tx, y0 + 2), f"{L['kind']} · {L['beat']} · {s['t_final_est'][0]:.2f}~{s['t_final_est'][1]:.2f}s ({s['dur']:.2f}s)", fill=col, font=font)
        for n, part in enumerate(_wrap(L.get("en") if L["kind"] == "원음" else L["text"], 34)[:4]):
            d.text((tx, y0 + 24 + n * 18), part, fill=(0, 0, 0), font=small)
        d.text((tx, y0 + 100), "자막: " + " / ".join(L["sub"]), fill=(120, 0, 120), font=small)
        d.text((tx, y0 + 140), f"원본 {s['src_orig_span'][0]}~{s['src_orig_span'][1]} 크롭 {s['src_crop']} ×{s['scale']}", fill=(90, 90, 90), font=small)
        for n, part in enumerate(_wrap(s["ours"], 34)[:2]):
            d.text((tx, y0 + 160 + n * 18), part, fill=(0, 100, 0), font=small)
        if L.get("fx") and first:
            for n, part in enumerate(_wrap("효과: " + L["fx"], 40)[:3]):
                d.text((tx, y0 + 200 + n * 16), part, fill=(200, 0, 0), font=small)
    S.save(out, quality=82)


def hook_sheet(shots, eff, out: Path):
    """0초 훅을 벤치와 같은 시각에 나란히(0.1·0.5·0.9·1.3·2.0·3.0초): 1줄 BBH 소재 벤치 · 2줄 QMJ 효과 벤치 · 3줄 우리 계획(크롭+원 자리)."""
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 18)
    ts = (0.1, 0.5, 0.9, 1.3, 2.0, 3.0)
    tw, th = 300, 292
    S = Image.new("RGB", (tw * len(ts), (th + 26) * 3), (255, 255, 255))
    d = ImageDraw.Draw(S)
    rc = next(e for e in eff if e["kind"] == "red_circle")
    s0 = shots[0]
    rows = [("BBH BVMDZG6mEKY", lambda t: frame(str(BENCH_MP4), t, [0, int(2304 * 0.2265), 1296, int(1296 / AR)], (tw, th))),
            ("QMJ(foreignshowshow)", lambda t: frame(str(QMJ_MP4), t, [0, 434, 1080, 1052], (tw, th)) if QMJ_MP4.exists() else Image.new("RGB", (tw, th), (200, 200, 200))),
            ("10편 계획", lambda t: frame(str(SRC / s0["src"]), s0["ss"] + t, s0["src_crop"], (tw, th)))]
    for r, (name, fn) in enumerate(rows):
        for j, t in enumerate(ts):
            y0 = r * (th + 26)
            d.text((j * tw + 4, y0 + 2), f"{name} {t}s", fill=(0, 0, 0), font=font)
            im = fn(t)
            if r == 2 and t < s0["dur"]:
                dd = ImageDraw.Draw(im)
                k = tw / 1080
                cx, cy, rr = rc["at"][0] * k, (rc["at"][1] - 434) * k, rc["size"] / 2 * k
                dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(250, 40, 40), width=max(2, int(11 * k)))
            S.paste(im, (j * tw, y0 + 26))
    S.save(out, quality=85)


def check(shots, total):
    durs = sorted(s["dur"] for s in shots)
    med = durs[len(durs) // 2] if len(durs) % 2 else (durs[len(durs) // 2 - 1] + durs[len(durs) // 2]) / 2
    seen, overlap = [], []
    for s in shots:
        a, b = s["src_orig_span"]
        for (a2, b2, i2, l2) in seen:
            forward = a >= b2 - 0.01 and (l2 == s["line"] or i2 == s["i"] - 1)
            if a < b2 + 3 and a2 < b + 3 and not forward:
                overlap.append((i2, s["i"]))
        seen.append((a, b, s["i"], s["line"]))
    narr = sum(nchar(L["tts"]) for L in LINES if L["kind"] == "나레")
    narr_s = sum(line_dur(L) for L in LINES if L["kind"] == "나레")
    return {"길이_추정": round(total + 0.03 * (len(LINES) - 1), 2), "컷": len(shots), "컷_중앙": round(med, 2), "컷_최소": durs[0],
            "끝컷": shots[-1]["dur"], "±3초_재사용(다른 줄)": overlap, "나레_자수(TTS,공백뺌)": narr, "나레_초": round(narr_s, 2),
            "자막_최대자수": max(len(x) for L in LINES for x in L["sub"]),
            "원음_초": round(sum(line_dur(L) for L in LINES if L["kind"] == "원음"), 2),
            "최대배율": max(s["scale"] for s in shots)}


TITLES = {"line1": "샤크들이 서로 싸운", "line2": "웃는 수세미?!"}


def effects(shots):
    E = []
    rc = {"line": "O1", "kind": "red_circle", "at": HOOK["at"], "size": HOOK["size"], "t": [0.0, round(403.203 - 401.32, 3)], "how": "face",
          "face_src": HOOK["face_src"], "fh_win": HOOK["fh_win"],
          "why": "foreignshowshow 0초 결말 반응 투자자 얼굴 빨간 실선 원(QMJ 0.0~0.533, 첫 컷 내내) — " + HOOK["why"]}
    E.append(rc)
    box, _ = target_box(shots, "N1", 0, 0.17)   # 화살표가 뜨는 0~0.7초 가운데 프레임
    E.append({"line": "N1", "kind": "arrow_green_down", "t": [0.0, 0.7], "how": "target", "target": box, "target_what": "웃는 얼굴 수세미(노란 덩어리 검출)",
              "why": "벤치 QMJ 0.567~1.267 둘째 컷 제품 위 초록 아래 화살표", **FP.on_target("arrow_green_down", box)})
    box2, s2 = target_box(shots, "N2", 1, 0.3)
    t_c = round(s2["t_final_est"][0] - next(x for x in shots if x["line"] == "N2")["t_final_est"][0], 3)
    E.append({"line": "N2", "kind": "arrow_curve_red", "t": [t_c, round(t_c + s2["dur"], 3)], "how": "target", "target": box2,
              "target_what": "유리 상판을 문지르는 수세미(노란 덩어리 검출)", "why": "벤치 QMJ 20.367~22.9 둘째 시연 빨간 곡선 화살표(찌르기)+휙",
              **FP.on_target("arrow_curve_red", box2)})
    E.append({"line": "N5", "kind": "arrow_pink_up", "at": [533, 1230], "t": [0.0, 1.0], "how": "auto",
              "why": "벤치 QMJ 12.017~13.82 숫자 조각 분홍 위 화살표 — 자막 첫 조각 '넉 달 만에 10만 달러'"})
    E.append({"line": "O5", "kind": "money_emoji", "at": [537, 1189], "t": [0.033, 1.333], "how": "auto", "why": "벤치 QMJ 38.7~40.0 날개 돈다발(제안 금액 줄)"})

    def fl(line, color, t0, why):
        E.append({"line": line, "kind": "flash", "at": [540, 960], "t": [t0, round(t0 + 0.45, 3)], "color": color, "how": "auto", "why": why})
    fl("O2", "초록", 0.0, "벤치 QMJ 7.1 장면 넘김 초록 번쩍(시연 시작)")
    fl("O5", "초록", 0.0, "벤치 QMJ 38.667 투자 제안 초록 번쩍")
    fl("O7", "빨강", round(608.808 - 605.95, 3), "벤치 QMJ 11.2 와우 빨강 번쩍 — 에런 놀란 얼굴 컷 첫 프레임")
    fl("O8", "빨강", 0.0, "벤치 QMJ 44.367 결정 빨강 번쩍")
    fl("O10", "초록", round(683.183 - 680.75, 3), "벤치 QMJ 45.667 거래 성공 초록 번쩍 — 'We got a deal' 컷 첫 프레임")
    fl("N7", "초록", 0.0, "벤치 QMJ 49.3 방송 후 결과 초록 번쩍")
    return E


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
    S.update(META)
    S.setdefault("final", {})["lines"] = out
    S["final"]["cps_target"] = 7.8
    S["voice"] = VOICE
    S["titles"] = {**TITLES, "rule": "1줄 노랑·2줄 흰, 끝 '?!' — 벤치 BBH 제목 'Best Negotiation EVER on Shark Tank'(영어)와 겹침 없음, 줄당 ≤12자(10·7자)"}
    S["render"] = {**(S.get("render") or {}), "gap": 0.03}
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")


META = {
    "topic": "Scrub Daddy(물 온도로 딱딱해졌다 말랑해지는 웃는 얼굴 수세미) — 샤크탱크 S4E7 10만 달러/10% 요청 → 데이먼드·케빈·로리 입찰 전쟁 → 로리 20만 달러/20% 성사",
    "bench": {"id": "BVMDZG6mEKY", "channel": "BIG BAG HUSTLE @BIGBAGHUSTLE(소재·원음 순간 벤치)", "title": "Best Negotiation EVER on Shark Tank",
              "dur": 51.56, "views": 20781379, "form_bench": "foreignshowshow 공식 6박자·효과 꼴(QMJtjJz4M6w 실측 rules.json) — foreignshowshow·Spark·海外ショーショー 에 Scrub Daddy 쇼츠 없음(근거.md §0)",
              "window": [0, 434, 1080, 1052]},
    "form": "foreignshowshow 꼴 — 방송 원음(영어)+한국어 번역 자막 / 한국어 TTS 나레(반말 전언체)+자막 번갈아. 원음 순간 = BBH 벤치가 고른 입찰 장면. 틀 = preset 「샤크탱크_검정띠2줄」",
    "facts": {
        "f1": {"text": "원본 401.32~406.9 로리 '(I can tell instantly) if it's a hero or a zero. And I think what you've got here is a hero.'(구간 단독 2모델 asr/span_v1.json · 401.32 부터 자른 클립도 2모델 모두 'If it's a hero or a zero' 로 들음 asr/hook_start.json — 페이블 10-19 첫 컷 ≤1.9초 지시로 '딱 보면 알아요' 버림) · 이름 = 화면 띠 'Lori's offer…'(596초 등)", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음"},
        "f2": {"text": "원본 94.1~96.7 창업자 'Sharks, that's not just another smiling face.' · 20.8~23.4 'the cutest but most high-tech scrubbing tool'(30초 창 2모델 asr/src_seg.json) — 창업자 주장 → 전언체", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음(창업자 주장)"},
        "f3": {"text": "원본 32.75~37.0 'Scrub Daddy completely changes its texture by just adjusting your water temperature.'(2모델 span_v1 — 한 모델은 'scrubbing it' 으로 들음)", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음"},
        "f4": {"text": "원본 47~60 '10-pound weights … soft and compressible … gentle scrubbing / hard and firm … heavy-duty scrubbing' · 60~82 'burned on … scrubbing it right off … It won't scratch any of your surfaces' · 위키백과 Scrub Daddy: 'firm in cold water and soft in warm water'(NBR 2016-05-13 인용)", "url": "https://en.wikipedia.org/wiki/Scrub_Daddy", "kind": "방송 원음+백과"},
        "f5": {"text": "원본 102.0~111.6 'And that smiling mouth, that cleans spoons, knives, forks, spatulas … on both sides at the same time.'(30초 창 2모델) · O3 원음 102.44~104.55 'And that smiley mouth, that cleans spoons,'(구간 단독 2모델 asr/span_v3.json + 102.44 부터 자른 클립 2모델 asr/span_seg3.json)", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음(창업자 시연 — 전언체)"},
        "f6": {"text": "원본 136.5~147.7 'I've been on QVC three times … every time I go on, they reorder 30% more than the last time.' · 150~154.9 'total sales? QVC, wholesale' — 'Just north of $100,000, only in four months.'(구간 단독 2모델 span_v1)", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음(창업자 말 — 전언체)"},
        "f7": {"text": "공식 원본 제목 'A Bidding War Breaks Out During Scrub Daddy's Pitch'(Shark Tank Global) · 원본 386~600 케빈(10만 달러+개당 로열티)·데이먼드·로리 제안이 차례로 바뀜(30초 창 받아쓰기) · 화면 띠 'Kevin's offer'·'Daymond's offer'·'Lori's offer'", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "공식 제목+방송"},
        "f8": {"text": "원본 468.4~472.6 데이먼드 'I'm going to give you $150,000 for 25%.'(2모델 span_v1·v2) · 화면 띠 475~480초 'Daymond's offer: $150k for a 25% stake'", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음+화면 띠"},
        "f9": {"text": "원본 592.55~598.1 로리 '150,000 for 25%. I'll make you a millionaire within a year.'(창·구간 4모델, 낱말 시각 ±0.7초 갈림) · 화면 띠 596초 'Lori's offer: $150k for a 25% stake' · 600~602 데이먼드 'Mine just went to 175' · 605.95~610 'Mine just went to two. / Whoa!'(2모델) — 'two' = 20만 달러(위키백과 '20% … for $200,000')", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음+화면 띠"},
        "f10": {"text": "원본 658.25~662.45 로리 'You need to tell me right now whether you're going with me or not, or I'm out.'(2모델) · 673.15~675.3 에런 'Would you consider coming down to 20?'(2모델) · 680.75~684.55 로리 'You know what, I will. I'll go to 20.' + 'We got a deal.'(2모델)", "url": "https://www.youtube.com/watch?v=ae5MssJ8en4", "kind": "방송 원음"},
        "f11": {"text": "위키백과 Scrub Daddy: 'The following day, Greiner and Krause sold 42,000 sponges in under seven minutes on QVC.'(Bustle 2014-12-05 인용)", "url": "https://en.wikipedia.org/wiki/Scrub_Daddy", "kind": "백과(기사 인용)"},
    },
    "dropped": [
        "BBH 1.7~5.6 'No offense, Daymond, I don't need you / You don't?' · 8.4~14.7 로리 첫 제안 '$100,000 for 30% … all retail stores … within literally weeks' — 길이(전체 60초 넘음) 때문에 뺌, 로리의 다음 제안(O6)으로 이어짐",
        "BBH 26.5~29.6 로리 '$100,000 but for 25%' · 33.7~38.4 데이먼드 'mine just went to 175 / whoa / up to 175?' — 길이 때문에 뺌(O7 '20만으로 올렸어요'가 경쟁 고조를 대신)",
        "케빈 로열티 제안(440~460·630~645) — BBH 도 뺌",
        "누적 매출(9억 2,600만 달러, Investopedia 2023-05 — 위키백과 인용) — 나레 길이 때문에 뺌. 방송 직후 결과(QVC 7분 4만 2천 개)만 씀",
        "원본 첫 제안 요청 '$100,000 for 10%'(24.5~28.5) — BBH 도 안 다룸",
    ],
}


def main():
    shots, total = build()
    eff = effects(shots)
    mat = {"_note": "샥탬스토리 10편 Scrub Daddy 재료 계획 — TTS·렌더 전. 창 1080x1052. make_plan.py LINES 가 정본(이 파일은 생성물). 원음 컷은 src_orig_span 그대로 원본 소리(ae5MssJ8en4_audio.m4a).",
           "sources": {CLIP: {"채널": "Shark Tank Global(공식)", "제목": "A Bidding War Breaks Out During Scrub Daddy's Pitch | Shark Tank US | Shark Tank Global",
                              "해상도": "1920x1080 29.97fps (137 + 140 영어 원음)", "길이": 740.97, "받은 구간": "전체", "조회": 22163835,
                              "남의 글자": "이름·제안 띠(y 820~970: 'AARON KRAUSE / SCRUB DADDY' 15~30초 · 'Kevin's/Daymond's/Lori's offer…' 422~640초) — 띠가 뜨는 O5·O6·O7 컷은 크롭 높이 810 으로 뺌, 나머지 쓴 구간은 띠 없음(시트 확인). 모서리 로고 없음(20·596초 원본 확인). 끝 720~741 'SHARK TANK WATCH MORE' 판 안 씀"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": TITLES, "shots": shots, "cand_dir": str(SRC).replace("\\", "/"), "effects": eff,
           "sfx_not_drawn": ["벤치 6박자 '기존 불편' 점선 원 — 이 편엔 불편을 겪는 사람 컷이 원본에 없음(창업자 시연뿐) → 안 넣음(벤치와 다른 점)"]}
    doc_update()
    (HERE / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--no-sheet" not in sys.argv:
        (HERE / "plan").mkdir(exist_ok=True)
        sheet(shots, eff, HERE / "plan" / "계획_시트.jpg", " / ".join(TITLES.values()))
        hook_sheet(shots, eff, HERE / "plan" / "hook_vs_bench.jpg")
    c = check(shots, total)
    print(json.dumps(c, ensure_ascii=False))
    print("HOOK", json.dumps(HOOK, ensure_ascii=False))
    for e in eff:
        print("FX", e["line"], e["kind"], e.get("at"), e["t"], e.get("target", ""))
    for x in shots:
        print(x["i"], x["line"], x["src_orig_span"], x["dur"], x["t_final_est"], x["src_crop"], x["scale"], file=sys.stderr)
    return shots, c


if __name__ == "__main__":
    main()
