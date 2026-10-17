# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 3호 최은경 자라 스웨이드 로퍼(1554/810/700) — 재미썸홈판 (2026-10-17). 엔진 코드는 안 고친다(부르기만).
정본 = 하이브리드_함익병/재미썸홈판/make.py — 소재 상수(원음·화면·대사·조각)만 바꿈. A 원음 화면은 한 토막 안에서 샷을 나눌 수 있게(A_SHOTS 리스트).

    PYTHONUTF8=1 py make.py plan      # 대본.json·재료.json·plan/계획_시트.jpg (TTS 전)
    PYTHONUTF8=1 py make.py tts       # 필재 Typecast 1회(narr_full.mp3 있으면 안 부름)
    PYTHONUTF8=1 py make.py render    # A(얜샷템 틀, 원음 하이라이트+TTS 한마디) + B(재미썸홈 t11 틀) → render/final.mp4 → 바탕화면

흐름: [A 약 10초] 최은경 원음 O1·O2(최은경의 관리사무소 5ublOh8gB4o) → 필재 TTS 한마디(F1) — 얜샷템 틀('출처 : 최은경의 관리사무소')
      [B] 다리 "저 영상 보고 나도…" → 써 보니 ①② → 사이즈 팁 → 남들도·품절 임박 → 마무리 — 재미썸홈 t11 틀(scene_style.compose, 본문만 body_all)
소리: TTS 1회를 A 끝 한마디 + B 나레로 나눠 쓴다. 원음은 나레 크기에 맞춘다. A만 BGM(원음 밑 덕킹), B는 BGM 없음 + 숏템 효과음팩 density=low.
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

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_최은경/재미썸홈판")
SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_최은경/src")
R = W / "render"
DESK = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/하이브리드/칼카피_얜샷템_최은경자라로퍼_재미썸홈판.mp4")
HAM = "C:/숏템_칼카피/yanshottem/최은경_자라슈즈/src/ceg_5ublOh8gB4o.mp4"   # 최은경의 관리사무소 5ublOh8gB4o 1080p 전체(이름은 정본 상수 그대로)
VOICE = "tc_68257f68bc6e3c161ab5078d"      # 필재
TC_TEMPO = 1.25                            # voice_presets 필재 1.25(숏템 그대로) — 나머지는 atempo
CPS = 8.8                                  # 재미썸홈 프리셋 measured.speech_rate
FPS = 30
FRAME_A = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_B = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
TITLE_A = "최은경이 자라에서 건진\n명품 같은 주름 로퍼"
LABEL_A = "출처 : 최은경의 관리사무소"
BODY_TITLE = "최은경 따라 산 자라 주름 로퍼"
WIN_A = 1080                               # 얜샷템 영상 칸 1080×1080
WIN_B = (1080, 1407)                       # t11 영상 칸
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
BGM_A, BGM_A_DB, DUCK_DB = "sweets", -27.0, -10.0
TARGET_LUFS = -14.0

# ── 원음(최은경 본인 말) — 원본 자동자막 어절 시각 + 받아쓰기 2모델(화자 1)로 고른 구간(근거.md) ──
#   O1 508.40~512.50 "작년부터 강타하고 있는 주름 로퍼잖아요. 너무 잘 만들잖아요." (원본 컷 512.57 앞)
#   O2 516.52~520.08 "YSL 이거 하나 붙었다고 200이 넘더라고요." (515.1~516.5 '그래서 내가 보니까 여기에' 잘라 냄)
ORIG = [("O1", 508.40, 512.50), ("O2", 516.52, 520.08)]
ORIG_CAPS = [(508.40, "작년부터 강타하고"), (509.88, "있는 주름 로퍼잖아요"), (511.40, "너무 잘 만들잖아요"),
             (516.52, "YSL 이거 하나"), (518.04, "붙었다고"), (518.88, "200이 넘더라고요")]
# A 화면: 원음 토막마다 [(원본 시작, 크롭 [x,y,w,h], 길이 또는 None=끝까지)] — 원본 큰 자막(y≥760)·로고(x<300,y<180) 밖
#   O2 는 519.47부터 원본이 YSL 등 남의 제품 사진이라, 마지막 0.6초는 527.25 최은경이 로퍼 든 화면(J컷)
A_SHOTS = [[(508.40, [600, 0, 760, 760], None)],
           [(516.52, [540, 0, 840, 840], 2.87), (527.25, [620, 0, 840, 840], None)]]
GAP_O_F1 = 0.12                            # 원음 끝 → TTS 한마디
F1_SHOT = (HAM, 505.55, [170, 180, 900, 900])                  # 민트 바탕 위 이 로퍼가 도는 제품 컷(최은경 원본 505.47~508.33) — 오른쪽 품번 딱지(x≥1155)·로고 밖
F1_SHOT2 = ("stills/e1_side_sq.mp4", 0.0, [0, 0, 1080, 1080])  # '바로 이거' = 자라 공식 사진 e1 옆모습

LINES = [   # (칸, 화면 글 text, 읽는 글 tts) — 0 = A 끝 한마디(F1), 1~ = B
    ("f1", "최은경이 자라에서 건진 주름 로퍼, 바로 이거.", "최, 은경이 자라에서 건진 주름 로퍼, 바로 이거."),
    ("bait", "저 영상 보고 나도 당장 따라 샀는데,", "저 영상 보고 나도 당장 따라 샀는데,"),
    ("limit", "이게 말도 안 되는 게 앞코 주름 하나로 명품 느낌이 그대로 나.", "이게 말도 안 되는 게 앞코 주름 하나로 명품 느낌이 그대로 나."),
    ("more", "심지어 굽이 2.5cm 플랫이라 어떤 바지에 신어도 다 어울려.", "심지어 굽이 이 점 오 센티 플랫이라 어떤 바지에 신어도 다 어울려."),
    ("twist", "근데 진짜 중요한 포인트는 사이즈야.", "근데 진짜 중요한 포인트는 사이즈야."),
    ("more", "최은경이도 앞이 꽉 찬다고 한 사이즈 크게 사라고 했거든.", "최, 은경이도 앞이 꽉 찬다고 한 사이즈 크게 사라고 했거든."),
    ("more", "작년부터 다들 신는 주름 로퍼라 자라에서도 벌써 품절 임박이 떴더라.", "작년부터 다들 신는 주름 로퍼라 자라에서도 벌써 품절 임박이 떴더라."),
    ("land", "로고값 200 쓰기 전에 이걸로 먼저 해결해 봐.", "로고값 이백 쓰기 전에 이걸로 먼저 해결해 봐."),
]
# 자막 조각(≤13자) · 재료 — (조각, 소스 파일|"+", 소스 시작초, 크롭 [x,y,h](폭 = h×1080/1407), 종류, 화면에 보이는 것)
#   "+" = 앞 컷을 끊지 않고 이어감. 모든 재료 = 같은 제품(자라 1554/810/700): 최은경 원본 · 자라 공식 사진(stills/*_t11 = 1080×1408)
PIECES = [
    ("최은경이 자라에서", None, None, None, "제품", "(A) 민트 바탕 위 이 로퍼가 도는 제품 컷"),
    ("건진 주름 로퍼", None, None, None, "제품", "(A) 〃"),
    ("바로 이거", None, None, None, "제품", "(A) 자라 공식 사진 옆모습"),
    # bait
    ("저 영상 보고 나도", HAM, 546.40, [920, 0, 900], "제품", "최은경이 두 손으로 든 이 로퍼(얼굴 밖 x<900·원본 자막 y≥930 밖)"),
    ("당장 따라 샀는데", "+", None, None, "제품", "(이어감)"),
    # limit ① 앞코 주름 → 명품 느낌
    ("이게 말도 안 되는 게", "stills/e3_toe_t11.mp4", 0.0, [0, 0, 1407], "제품", "자라 공식 사진 e3 — 정면 앞코 셔링"),
    ("앞코 주름 하나로", "+", None, None, "제품", "(이어감)"),
    ("명품 느낌이 그대로 나", HAM, 582.60, [1000, 150, 740], "제품", "최은경이 든 이 로퍼를 손가락으로 짚는 근접 — 앞코 주름·스웨이드 결(576.47~584.67 샷, 얼굴·자막 밖) · B13: 원음 끝 512.50과 70초, 끝 컷 576.6~579.17과 3.4초 떨어짐(10-17 수정 — 전엔 512.62 디테일 컷이 원음 끝과 0.12초)"),
    # more ② 굽 2.5cm 플랫 → 어떤 바지에도
    ("심지어 굽이 2.5cm", "stills/f1_flat_t11.mp4", 0.0, [0, 0, 1407], "제품", "자라 공식 사진 f1 — 옆모습, 납작한 구두창"),
    ("플랫이라", "+", None, None, "제품", "(이어감)"),
    ("어떤 바지에 신어도", "stills/p_model_t11.mp4", 0.0, [0, 0, 1407], "제품", "자라 공식 사진 p — 남색 와이드 바지에 이 로퍼 신은 모델 → 발 쪽으로"),
    ("다 어울려", "+", None, None, "제품", "(이어감)"),
    # twist 사이즈
    ("근데 진짜", "stills/e4_back_t11.mp4", 0.0, [0, 0, 1407], "제품", "자라 공식 사진 e4 — 뒤에서 본 발 넣는 입구·풀탭"),
    ("중요한 포인트는", "+", None, None, "제품", "(이어감)"),
    ("사이즈야", "+", None, None, "제품", "(이어감)"),
    # more 최은경도
    ("최은경이도 앞이", HAM, 556.40, [940, 0, 900], "제품", "최은경이 로퍼를 들고 사이즈 얘기하는 손(얼굴 밖)"),
    ("꽉 찬다고", "+", None, None, "제품", "(이어감)"),
    ("한 사이즈 크게", "stills/a1_worn_t11.mp4", 0.0, [0, 0, 1407], "제품", "자라 공식 사진 a1 — 이 로퍼를 신은 두 발"),
    ("사라고 했거든", "+", None, None, "제품", "(이어감)"),
    # more 남들도 · 품절 임박
    ("작년부터 다들 신는", "stills/e2_pair_t11.mp4", 0.0, [0, 0, 1407], "제품", "자라 공식 사진 e2 — 한 켤레 사선"),
    ("주름 로퍼라", "+", None, None, "제품", "(이어감)"),
    ("자라에서도 벌써", "stills/page_soldout_t11.mp4", 4.5, [0, 0, 1407], "제품", "자라 한국 공식몰 상품 페이지(10-17 조회) '품절 임박 · 스웨이드 로퍼 · ₩99,900'"),
    ("품절 임박이 떴더라", "+", None, None, "제품", "(이어감)"),
    # land(끝 컷 ≥1.5초)
    ("로고값 200", HAM, 576.60, [960, 0, 900], "제품", "최은경이 들고 보여 주는 이 로퍼(손·로퍼, 끝 컷)"),
    ("쓰기 전에", "+", None, None, "제품", "(이어감)"),
    ("이걸로 먼저 해결해 봐", "+", None, None, "제품", "(이어감)"),
]
SFX_ROLES = [l[0] for l in LINES[1:]]
TEMPO, TEMPO_LAST = 1.27, 1.143  # 나레 atempo(지휘 상한 1.27 → 8.47자/초) · 끝 문장만 1.143(TTS가 끝 문장을 빨리 읽음 원속 8.28 vs 6.67자/초, −10% = B17 한도)
# narr_full.mp3 = narr_full_orig.mp3 에서 '샀는데,' 뒤 숨소리(5.58~6.23초, −30dB)만 0으로(쉼 자리를 무음으로 잡히게)
#   + 이름 줄 둘만 갈아 끼움(10-17): 1차 '최은경이…'·'최은경도…'가 받아쓰기에서 최혜경·최영영·**최화정**으로 들림 →
#   후보 9개(name_fix/F1~F3·G1~G6) 단독 받아쓰기로 F2 '최, 은경이 …'·G6 '최, 은경이도 …'(각 4/4 '최은경') 골라
#   orig 0.28~2.95 → F2 0.157~2.95 · orig 16.20~18.65 → G6 0.19~3.10 (경계는 무음 안), 두 줄만 atempo 0.9(이름 또렷하게 — 최종 1.143 = B17 −10% 한도)
# 문장부호 쉼 자리(atempo 뒤·쉼 모양 전 narr_pre.wav 초, silencedetect −40dB/0.06 실측) — 로퍼, | 이거. | 샀는데, | 나. | 어울려. | 사이즈야. | 했거든. | 떴더라.
#   받아쓰기 토막(flash-latest)으로 줄 머리 대조. '근데|진짜'(10.52) 구절 쉼은 건드리지 않는다
PUNCT_AT = [(",", 1.85), (".", 2.71), (",", 4.58), (".", 7.64), (".", 10.44), (".", 12.38), (".", 15.17), (".", 18.15)]   # 이름 줄 갈아 끼우고(0.9배 느리게) 다시 잼(10-17)
END_PAD = 0.7


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
    if len(crop) == 4:
        x, y, w, h = crop
    else:
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
    for (name, a, b), shots in zip(ORIG, A_SHOTS):
        left = b - a
        for ss, cr, dd in shots:
            d_ = left if dd is None else dd
            rows.append({"label": f"A {name} 원음 {o_t:.2f}+{d_:.2f}", "src": HAM, "a": ss, "b": ss + d_, "crop": cr, "size": (300, 300),
                         "caps": " / ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b), "seen": "최은경 본인(말하는 사람) 단독 화면", "kind": "원음"})
            o_t += d_; left -= d_
    f1d = sum(nchar(p[0]) for p in PIECES[:3]) / CPS
    f1a = sum(nchar(p[0]) for p in PIECES[:2]) / CPS + GAP_O_F1
    rows.append({"label": f"A F1 TTS {o_t:.2f}+{f1a:.2f}", "src": F1_SHOT[0], "a": F1_SHOT[1], "b": F1_SHOT[1] + f1a, "crop": F1_SHOT[2],
                 "size": (300, 300), "caps": " / ".join(p[0] for p in PIECES[:2]), "seen": "민트 바탕 위 이 로퍼가 도는 제품 컷", "kind": "제품"})
    rows.append({"label": f"A F1 TTS {o_t + f1a:.2f}+{f1d + GAP_O_F1 - f1a:.2f}", "src": F1_SHOT2[0], "a": F1_SHOT2[1], "b": F1_SHOT2[1] + f1d + GAP_O_F1 - f1a,
                 "crop": F1_SHOT2[2], "size": (300, 300), "caps": PIECES[2][0], "seen": "자라 공식 사진 e1 옆모습", "kind": "제품"})
    for g in gs:
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g['kind']}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": g["crop"], "size": (230, 300), "caps": " / ".join(PIECES[k][0] for k in g["pieces"]), "seen": g["seen"], "kind": g["kind"]})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 3 * 300 + 330, 310, 2
    head = 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 최은경 자라 로퍼 — 재미썸홈판 계획 시트(TTS 전) · 예상 {times[-1][1]:.1f}초 · A 원음 {sum(b - a for _, a, b in ORIG):.2f}초 + TTS · B 컷 {len(gs)}",
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
        "channel": "얜샷템 하이브리드(재미썸홈판)", "topic": "최은경이 자라에서 내돈내산한 스웨이드 주름 로퍼(1554/810/700) — 원음 하이라이트 → 나도 샀다 → 써 보니 ①② → 사이즈 팁 → 남들도·품절 임박 → 마무리",
        "frames": {"A": str(FRAME_A.relative_to(ROOT)), "A_title": TITLE_A, "A_label": LABEL_A, "B": "channel/evenshopping/preset/숏템템플릿 (t11, frameRule body_all)", "B_bodyTitle": BODY_TITLE},
        "orig_audio": [{"id": n, "src": "5ublOh8gB4o", "span": [a, b], "said": " ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b)} for n, a, b in ORIG],
        "lines": [{"slot": s, "text": t, "tts": tt, "chars": nchar(tt)} for s, t, tt in LINES],
        "tts_one_call": " ".join(l[2] for l in LINES), "voice": f"Typecast 필재 {VOICE} tempo {TC_TEMPO} 1회",
        "pieces": [{"i": k + 1, "line": pl[k], "caption": p[0], "t": list(times[k]), "est": est} for k, p in enumerate(PIECES)],
        "hype": {"①센 시작": "원음 '작년부터 강타하고 있는 주름 로퍼잖아요. 너무 잘 만들잖아요' + '저 영상 보고 나도 당장 따라 샀는데'", "②권위": "최은경 본인 말(원음) — 'YSL 붙으면 200 넘는다'",
                 "③진짜 핵심 반전": "근데 진짜 중요한 포인트는 사이즈야", "④심지어": "심지어 굽이 2.5cm", "⑤남들도": "작년부터 다들 신는 · 품절 임박"},
        **(extra or {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps({
        "A": [{"id": n, "src": HAM, "span": [a, b], "shots": [{"ss": ss, "crop_xywh": cr, "dur": dd, "zoom": round(WIN_A / cr[2], 2)} for ss, cr, dd in shots],
               "audio": "원음(본인 말)"} for (n, a, b), shots in zip(ORIG, A_SHOTS)] + [{"id": "F1", "src": F1_SHOT[0], "ss": F1_SHOT[1], "crop_xywh": F1_SHOT[2],
                                                                 "zoom": round(WIN_A / F1_SHOT[2][2], 2), "audio": "무음(나레)"},
                                                                {"id": "F1b", "src": F1_SHOT2[0], "ss": F1_SHOT2[1], "crop_xywh": F1_SHOT2[2],
                                                                 "zoom": round(WIN_A / F1_SHOT2[2][2], 2), "audio": "무음(나레)"}],
        "B": [{k: v for k, v in g.items()} for g in gs],
        "src_urls": {HAM: "https://youtu.be/5ublOh8gB4o (최은경의 관리사무소, 2026-10-09, 1080p) — 화면 506.5초 품번 딱지 '스웨이드 로퍼 브라운 1554/810/700'",
                     "stills/*": "자라 한국 공식몰 https://www.zara.com/kr/ko/-p11554810.html 상품 사진 7장(11554810700-a1·e1~e4·f1·p) + 상품 페이지 화면(2026-10-17 조회) → 조사/make_stills.py 로 8초 다가가기 영상"},
        "audio_rule": "B 재료 원음 전부 끔(-an). A 원음 = 최은경 말만(O1·O2, 받아쓰기 화자 1).",
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
