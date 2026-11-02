# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 3호 장윤정 테클라 수건 — 재미썸홈판 (2026-10-17). 정본 = 하이브리드_함익병/재미썸홈판/make.py 를 그대로 따름.
엔진 코드는 안 고친다(부르기만). A 원음 밑 화면만 '원음 조각 1개 = 컷 1개'에서 '원음 상대 초 컷 목록(A_VIS)'으로 바꿈.

    PYTHONUTF8=1 py make.py plan      # 대본.json·재료.json·plan/계획_시트.jpg (TTS 전)
    PYTHONUTF8=1 py make.py tts       # 필재 Typecast 1회(narr_full.mp3 있으면 안 부름)
    PYTHONUTF8=1 py make.py render    # A(얜샷템 틀, 원음 하이라이트+TTS 한마디) + B(재미썸홈 t11 틀) → render/final.mp4 → 바탕화면

흐름: [A 0~약 11초] 장윤정 원음 O1a·O1b·O3a·O3b(장공장장윤정 XzCEZtLDV-A) → 필재 TTS 한마디(F1) — 얜샷템 틀('출처 : 장공장장윤정')
      [B] 다리 "저 영상 보고 나도…" → 써 보니 ①② → 반전(비슷한 디자인 많다) → 라벨 확인 → 남들도(연예인 집) → 마무리 — 재미썸홈 t11 틀
소리: TTS 1회를 A 끝 한마디 + B 나레로 나눠 쓴다. A만 BGM(얜샷템, 원음 밑 덕킹), B는 BGM 없음 + 숏템 효과음팩 density=low.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parents[3]
sys.path.insert(0, str(ROOT))

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_장윤정/재미썸홈판")
SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_장윤정/src")
R = W / "render"
DESK = Path.home() / "Desktop" / "칼카피영상" / "얜샷템" / "하이브리드" / "칼카피_얜샷템_장윤정테클라수건_재미썸홈판.mp4"
HAM = "jyj_XzCEZtLDV-A.mp4"                 # 장공장장윤정 XzCEZtLDV-A 1080p 전체 (이름은 정본 변수 그대로)
VOICE = "tc_68257f68bc6e3c161ab5078d"      # 필재
TC_TEMPO = 1.25                            # voice_presets 필재 1.25(숏템 그대로) — 나머지는 atempo
CPS = 8.8                                  # 재미썸홈 프리셋 measured.speech_rate
FPS = 30
FRAME_A = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_B = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
TITLE_A = "수건에 미친 장윤정이\n덴마크서 사 온 수건"
LABEL_A = "출처 : 장공장장윤정"
BODY_TITLE = "장윤정 따라 산 덴마크 수건"
WIN_A = 1080                               # 얜샷템 영상 칸 1080×1080
WIN_B = (1080, 1407)                       # t11 영상 칸
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
BGM_A, BGM_A_DB, DUCK_DB = "sweets", -27.0, -10.0
TARGET_LUFS = -14.0

# ── 원음(장윤정 본인 말) — 기본편(channel/yanshottem/장윤정_덴마크수건) 20ms RMS 경계 + 조각 단독 받아쓰기 2회(화자 1) ──
#   O1a 224.80~225.98 "저는 수건" / (225.98~226.40 쉼 잘라 냄)
#   O1b 226.40~231.00 "미치는 애거든요. 수건을 저희 집에 보면 수건이 수십 개씩 있어요"
#   O3a 261.95~263.02 "확실히 짱짱하다" / (263.02~264.56 쉼 잘라 냄)  O3b 264.56~265.45 "확실히 도톰하다"
ORIG = [("O1a", 224.80, 225.98), ("O1b", 226.40, 231.00), ("O3a", 261.95, 263.02), ("O3b", 264.56, 265.45)]
ORIG_CAPS = [(224.80, "저는 수건"), (226.48, "미치는 애거든요"), (227.44, "수건을 저희 집에 보면"), (229.12, "수건이 수십 개씩 있어요"),
             (261.95, "확실히 짱짱하다"), (264.56, "확실히 도톰하다")]
# A 원음 밑 화면: (원음 상대 초, 소스, 시작초, 크롭 [x,y,w,h]) — 원본 아래 편집 자막(y≥865) 밖. 원음 O1b 뒤 1.8초는 제품 컷(소리는 원음 그대로)
# 2026-10-18 첫 화면 = 장윤정 얼굴 크게(사장님 '썸네일·첫 화면은 무조건 연예인') — 옛 0.00 컷 224.80 [500,0,870,870](멀리 작은 장윤정) 대신
#   TEKLA 줄무늬 수건 들고 말하는 얼굴 근접(원본 164.4~167.5 컷). 소리는 O1a 원음 그대로(입 모양은 다른 말)
A_VIS = [(0.00, HAM, 164.95, [560, 0, 800, 800]), (1.18, HAM, 226.40, [455, 0, 870, 870]), (3.98, HAM, 132.00, [450, 0, 860, 860]),
         (4.88, HAM, 153.00, [560, 0, 870, 870]), (5.78, HAM, 261.95, [590, 0, 870, 870]), (6.85, HAM, 264.56, [455, 0, 870, 870])]
A_VIS_SEE = ["TEKLA 줄무늬 수건을 들고 말하는 장윤정 얼굴 근접(원본 164.95~, 첫 화면)", "두 손을 들며 말하는 장윤정(입 모양 맞음)", "노란 탁자 위 접힌 파랑 줄무늬 TEKLA 수건(제품만)",
             "TEKLA 라벨 근접(제품만)", "수건을 쥐어 보는 본인 손", "수건 덮고 말하는 장윤정(입 모양 맞음)"]
GAP_O_F1 = 0.12                            # 원음 끝 → TTS 한마디
F1_SHOT = (HAM, 127.00, [430, 0, 870, 870])    # 무릎 위 파랑 줄무늬 TEKLA 수건을 펼치는 본인 손(얼굴 없음)
F1_SHOT2 = (HAM, 147.20, [330, 0, 870, 870])   # '바로 이 테클라' = TEKLA 라벨 근접(제품만)

L104 = "tekla/K-1Hwjo6N2U.mp4"             # Liam Stanley 'Tekla Towel Unbagging'
HNK = "tekla/qATfuOQLprQ.mp4"              # 하눅 '테클라 TEKLA 리뷰' (아래 자막 y≈970~ → 크롭 y+h ≤ 950)
LINES = [   # (칸, 화면 글 text, 읽는 글 tts) — 0 = A 끝 한마디(F1), 1~ = B
    ("f1", "장윤정이 덴마크에서 물어물어 사 온 수건, 바로 이 테클라.", "장윤정이 덴마크에서 물어물어 사 온 수건, 바로 이 테클라."),
    ("bait", "저 영상 보고 나도 당장 따라 샀는데,", "저 영상 보고 나도 당장 따라 샀는데,"),
    ("limit", "이게 말도 안 되는 게 두께가 진짜 샤워가운처럼 도톰해.", "이게 말도 안 되는 게 두께가 진짜 샤워가운처럼 도톰해."),
    ("more", "심지어 얼굴 닦으면 물기를 한 번에 쫙 먹어.", "심지어 얼굴 닦으면 물기를 한 번에 쫙 먹어."),
    ("twist", "근데 진짜 충격적인 건 인기가 너무 많아서 비슷한 디자인이 엄청 많다는 거.", "근데 진짜 충격적인 건 인기가 너무 많아서 비슷한 디자인이 엄청 많다는 거."),
    ("more", "그러니까 살 때 테클라 라벨 꼭 확인해.", "그러니까 살 때 테클라 라벨 꼭 확인해."),
    ("more", "장윤정 말로는 연예인 집에 다 있다던데,", "장윤정 말로는 연예인 집에 다 있다던데,"),
    ("land", "얇은 수건 여러 장 사기 전에 이거 한 장부터 바꿔 봐.", "얇은 수건 여러 장 사기 전에 이거 한 장부터 바꿔 봐."),
]
# 자막 조각(≤13자) · 재료 — (조각, 소스|"+", 시작초, 크롭 [x,y,h](폭 = h×1080/1407), 종류, 화면에 보이는 것)
PIECES = [
    ("장윤정이 덴마크에서", None, None, None, "제품", "(A) 무릎 위 TEKLA 수건을 펼치는 본인 손"),
    ("물어물어 사 온 수건", None, None, None, "제품", "(A) 〃"),
    ("바로 이 테클라", None, None, None, "제품", "(A) TEKLA 라벨 근접"),
    ("저 영상 보고 나도", L104, 104.0, [520, 300, 780], "제품", "TEKLA 로고 포장 봉투째 든 새 수건(언박싱)"),
    ("당장 따라 샀는데", "+", None, None, "제품", "(이어감)"),
    ("이게 말도 안 되는 게", L104, 117.0, [680, 380, 700], "제품", "TEKLA 택 달린 네이비 수건 결 근접(손으로 만짐)"),
    ("두께가 진짜", "+", None, None, "제품", "(이어감)"),
    ("샤워가운처럼 도톰해", L104, 209.5, [450, 0, 1080], "제품", "도톰한 네이비 TEKLA 배스 시트를 허리에 감싸 두름"),
    ("심지어 얼굴 닦으면", L104, 227.35, [650, 150, 924], "제품", "수건에 얼굴을 묻어 닦음"),
    ("물기를 한 번에 쫙 먹어", "+", None, None, "제품", "(이어감)"),
    ("근데 진짜 충격적인 건", HNK, 354.3, [650, 0, 950], "제품", "TEKLA 라벨 붙은 파랑 줄무늬 수건을 돌돌 만 것"),
    ("인기가 너무 많아서", HNK, 374.6, [350, 0, 950], "제품", "TEKLA 라벨 수건이 가득한 수건장"),
    ("비슷한 디자인이", "+", None, None, "제품", "(이어감)"),
    ("엄청 많다는 거", "+", None, None, "제품", "(이어감)"),
    ("그러니까 살 때", HNK, 19.7, [650, 0, 950], "제품", "파랑 줄무늬 수건 가운데 TEKLA 라벨 근접"),
    ("테클라 라벨 꼭 확인해", "+", None, None, "제품", "(이어감)"),
    ("장윤정 말로는", HNK, 383.6, [450, 0, 880], "제품", "욕실 수건걸이에 걸린 네이비 줄무늬 TEKLA 수건"),
    ("연예인 집에 다 있다던데", "+", None, None, "제품", "(이어감)"),
    ("얇은 수건 여러 장", HNK, 8.0, [650, 0, 950], "제품", "파랑 줄무늬 수건 위 TEKLA 라벨(끝 컷)"),
    ("사기 전에", "+", None, None, "제품", "(이어감)"),
    ("이거 한 장부터 바꿔 봐", "+", None, None, "제품", "(이어감)"),
]
SFX_ROLES = [l[0] for l in LINES[1:]]
TEMPO, TEMPO_LAST = 1.12, 1.01   # 필재 1회(narr_full 20.36초) 원속 7.90자/초 → atempo 1.12(8.85) · 끝 문장은 원속 8.97자/초(평균보다 13% 빠름) → 1.01(−9.8% ≤ B17 10%)
# 문장부호 쉼 자리(atempo 뒤·쉼 모양 전 narr_pre.wav 초) — narr_full silencedetect −40dB 실측(수건, 2.17~2.32 | 테클라. 2.89~3.14 | 샀는데, 4.72~4.84 |
#   도톰해. 7.31~7.49 | 먹어. 9.80~9.99 | 거. 13.72~13.85 | 확인해. 15.55~15.83 | 다던데, 17.75~17.96)을 (t−0.297)/1.12 로 옮김. 받아쓰기 2회로 줄 대조.
#   낱말 안 쉼(5.72 '안 되는 게|'·11.26 '충격적인 건|')은 건드리지 않는다
PUNCT_AT = [(",", 1.74), (".", 2.42), (",", 4.00), (".", 6.34), (".", 8.57), (".", 12.04), (".", 13.74), (",", 15.67)]
END_PAD = 0.7      # 끝 컷 늘림(B4 끝 컷 ≥1.5초)


def nchar(s):
    return len(re.findall(r"[가-힣A-Za-z0-9]", s))


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


def probe(p):
    j = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(p)]).stdout)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def check_pieces():
    for li in range(len(LINES)):
        pass
    whole = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(l[1] for l in LINES)))
    pcs = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(p[0] for p in PIECES)))
    assert whole == pcs, "자막 조각이 대사와 다르다"
    assert max(len(p[0]) for p in PIECES) <= 13, [p[0] for p in PIECES if len(p[0]) > 13]


def piece_lines():
    """조각 → 줄 번호(대사 순서대로 소비)."""
    out, li, used = [], 0, 0
    for p in PIECES:
        while used >= nchar(LINES[li][1]):
            li, used = li + 1, 0
        out.append(li); used += nchar(p[0])
    return out


def groups_of(times):
    """B 조각 시각 [(t0,t1)] → 컷 묶음 [{src,ss,crop,kind,t0,t1,pieces,seen}]."""
    gs = []
    for k, (p, (a, b)) in enumerate(zip(PIECES, times)):
        if p[1] is None:
            continue
        if p[1] == "+":
            gs[-1]["t1"] = b; gs[-1]["pieces"].append(k)
        else:
            gs.append({"src": p[1], "ss": p[2], "crop": p[3], "kind": p[4], "t0": a, "t1": b, "pieces": [k], "seen": p[5]})
    return gs


def frame_png(src, t, crop, size):
    import io
    from PIL import Image
    x, y, h = crop[0], crop[1], crop[2]
    w = int(round(h * size[0] / size[1]))
    png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(SRC / src), "-frames:v", "1", "-vf",
                          f"crop={w}:{h}:{x}:{y},scale={size[0]}:{size[1]}", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert("RGB")


# ── plan(TTS 전) ───────────────────────────────────────────────────────────
def plan():
    from PIL import Image, ImageDraw, ImageFont
    check_pieces()
    pl = piece_lines()
    # 예상 시각: A = 원음 그대로 + F1 글자÷8.8 / B = 글자÷8.8
    t = sum(b - a for _, a, b in ORIG) + GAP_O_F1
    times = []
    for k, p in enumerate(PIECES):
        d = nchar(p[0]) / CPS
        times.append((round(t, 2), round(t + d, 2))); t += d
    times[-1] = (times[-1][0], round(times[-1][1] + END_PAD, 2))
    gs = groups_of(times)
    for g in gs:   # 소스 길이·크롭 범위 검사
        w, h, sd = probe(SRC / g["src"])
        cw = int(round(g["crop"][2] * WIN_B[0] / WIN_B[1]))
        assert g["ss"] + (g["t1"] - g["t0"]) <= sd, (g["src"], g["ss"], g["t1"] - g["t0"], sd)
        assert g["crop"][0] + cw <= w and g["crop"][1] + g["crop"][2] <= h, (g["src"], g["crop"], w, h)
        g["res"] = f"{w}x{h}"; g["zoom"] = round(WIN_B[1] / g["crop"][2], 2)
    # 계획 시트: A 원음 3컷 + F1 + B 묶음
    rows = []
    o_t = 0.0
    o_len = sum(b - a for _, a, b in ORIG)
    for k, (at, src, ss, cr) in enumerate(A_VIS):
        nxt = A_VIS[k + 1][0] if k + 1 < len(A_VIS) else o_len
        rows.append({"label": f"A 원음 {at:.2f}+{nxt - at:.2f}", "src": src, "a": ss, "b": ss + nxt - at, "crop": [cr[0], cr[1], cr[2]], "size": (300, 300),
                     "caps": "", "seen": A_VIS_SEE[k], "kind": "원음"})
    o_t = o_len
    f1d = sum(nchar(p[0]) for p in PIECES[:3]) / CPS
    f1a = sum(nchar(p[0]) for p in PIECES[:2]) / CPS + GAP_O_F1
    rows.append({"label": f"A F1 TTS {o_t:.2f}+{f1a:.2f}", "src": F1_SHOT[0], "a": F1_SHOT[1], "b": F1_SHOT[1] + f1a, "crop": F1_SHOT[2],
                 "size": (300, 300), "caps": " / ".join(p[0] for p in PIECES[:2]), "seen": "무릎 위 TEKLA 수건(본인 손)", "kind": "제품"})
    rows.append({"label": f"A F1 TTS {o_t + f1a:.2f}+{f1d + GAP_O_F1 - f1a:.2f}", "src": F1_SHOT2[0], "a": F1_SHOT2[1], "b": F1_SHOT2[1] + f1d + GAP_O_F1 - f1a,
                 "crop": F1_SHOT2[2], "size": (300, 300), "caps": PIECES[2][0], "seen": "TEKLA 라벨 근접(제품만)", "kind": "제품"})
    for g in gs:
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g['kind']}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": g["crop"], "size": (230, 300), "caps": " / ".join(PIECES[k][0] for k in g["pieces"]), "seen": g["seen"], "kind": g["kind"]})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 3 * 300 + 330, 310, 2
    head = 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 장윤정 테클라 — 재미썸홈판 계획 시트(TTS 전) · 예상 {times[-1][1]:.1f}초 · A 원음 {sum(b - a for _, a, b in ORIG):.2f}초 + TTS · B 컷 {len(gs)}",
           fill="black", font=font)
    d.text((10, 34), "프레임 3장 = 컷 시작+0.1 · 가운데 · 끝−0.1, 완성본 크롭 그대로(A 1080², B 1080×1407)", fill="#444", font=small)
    for k, r in enumerate(rows):
        x0, y0 = (k % PER) * COLW, head + (k // PER) * ROWH
        for j, tt in enumerate((r["a"] + 0.1, (r["a"] + r["b"]) / 2, r["b"] - 0.1)):
            sheet.paste(frame_png(r["src"], tt, r["crop"], r["size"]), (x0 + j * 300, y0))
        tx = x0 + 905
        d.text((tx, y0 + 2), r["label"], fill="black", font=font)
        d.text((tx, y0 + 26), f"{r['src'][:22]} {r['a']:.2f}~{r['b']:.2f}", fill="#333", font=small)
        cap = r["caps"]
        for i in range(0, min(len(cap), 120), 20):
            d.text((tx, y0 + 48 + i // 20 * 20), cap[i:i + 20], fill="#000", font=font)
        seen = r["seen"]
        for i in range(0, min(len(seen), 60), 20):
            d.text((tx, y0 + 180 + i // 20 * 18), seen[i:i + 20], fill="#555", font=small)
    (D / "plan").mkdir(exist_ok=True)
    sheet.save(D / "plan/계획_시트.jpg", quality=85)
    write_docs(times, gs, est=True)
    print("est", times[-1][1], "B cuts", len(gs), "max cap", max(len(p[0]) for p in PIECES), "max zoom", max(g["zoom"] for g in gs))


def write_docs(times, gs, est, extra=None):
    pl = piece_lines()
    (D / "대본.json").write_text(json.dumps({
        "channel": "얜샷템 하이브리드(재미썸홈판)", "topic": "장윤정이 덴마크에서 물어물어 사 온 TEKLA 수건 — 원음 하이라이트 → 나도 샀다 → 써 보니 ①② → 반전(비슷한 디자인) → 라벨 확인 → 남들도 → 마무리",
        "frames": {"A": str(FRAME_A.relative_to(ROOT)), "A_title": TITLE_A, "A_label": LABEL_A, "B": "channel/evenshopping/preset/숏템템플릿 (t11, frameRule body_all)", "B_bodyTitle": BODY_TITLE},
        "orig_audio": [{"id": n, "src": "XzCEZtLDV-A", "span": [a, b], "said": " ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b)} for n, a, b in ORIG],
        "lines": [{"slot": s, "text": t, "tts": tt, "chars": nchar(tt)} for s, t, tt in LINES],
        "tts_one_call": " ".join(l[2] for l in LINES), "voice": f"Typecast 필재 {VOICE} tempo {TC_TEMPO} 1회",
        "pieces": [{"i": k + 1, "line": pl[k], "caption": p[0], "t": list(times[k]), "est": est} for k, p in enumerate(PIECES)],
        "hype": {"①센 시작": "원음 '저는 수건 미치는 애거든요' + '저 영상 보고 나도 당장 따라 샀는데'", "②권위": "장윤정 본인 말(원음)",
                 "③진짜 핵심 반전": "근데 진짜 충격적인 건", "④심지어": "심지어 얼굴 닦으면", "⑤남들도": "장윤정 말로는 연예인 집에 다 있다던데"},
        **(extra or {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps({
        "A": [{"id": f"O{k}", "at": at, "src": src, "ss": ss, "crop_xywh": cr, "zoom": round(WIN_A / cr[2], 2), "audio": "원음(본인 말)", "see": A_VIS_SEE[k]}
              for k, (at, src, ss, cr) in enumerate(A_VIS)] + [{"id": "F1", "src": F1_SHOT[0], "ss": F1_SHOT[1], "crop_xywh": F1_SHOT[2],
                                                                 "zoom": round(WIN_A / F1_SHOT[2][2], 2), "audio": "무음(나레)"},
                                                                {"id": "F1b", "src": F1_SHOT2[0], "ss": F1_SHOT2[1], "crop_xywh": F1_SHOT2[2],
                                                                 "zoom": round(WIN_A / F1_SHOT2[2][2], 2), "audio": "무음(나레)"}],
        "B": [{k: v for k, v in g.items()} for g in gs],
        "src_urls": {HAM: "https://www.youtube.com/watch?v=XzCEZtLDV-A (장공장장윤정, 2026-03-18, 1080p)",
                     HNK: "https://youtu.be/qATfuOQLprQ (하눅hanuk '수건정리 … 테클라 TEKLA 리뷰', 2024-04-13, 1080p)",
                     L104: "https://youtu.be/K-1Hwjo6N2U (Liam Stanley 'Tekla Towel Unbagging', 1080p 24fps)"},
        "audio_rule": "B 재료 원음 전부 끔(-an). A 원음 = 장윤정 말만(쉼 두 곳 잘라 냄, 조각 단독 받아쓰기 화자 1).",
    }, ensure_ascii=False, indent=1), encoding="utf-8")


# ── TTS 1회 ───────────────────────────────────────────────────────────────
def tts():
    R.mkdir(parents=True, exist_ok=True)
    full = R / "narr_full.mp3"
    if full.exists():
        print("있음 — 다시 안 부른다:", full); return
    from shopping_shorts.channelkit import providers
    providers.typecast_synth(VOICE, tempo=TC_TEMPO)(" ".join(l[2] for l in LINES), str(full))
    print("TTS 1회:", full, dur_of(full))


if __name__ == "__main__":
    {"plan": plan, "tts": tts}[sys.argv[1]]() if sys.argv[1] != "render" else __import__("render_hybrid").main()
