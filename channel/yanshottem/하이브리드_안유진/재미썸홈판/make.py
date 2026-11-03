# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 안유진 eos 바닐라 캐시미어 바디로션 — 재미썸홈판 (관제 097, 2026-10-18). 박세리 재미썸홈판 make.py 를 복사해 상수만 바꿨다. 엔진 코드는 안 고친다(부르기만).

    PYTHONUTF8=1 py make.py plan      # 대본.json·재료.json·plan/계획_시트.jpg (TTS 전)
    PYTHONUTF8=1 py make.py tts       # 필재 Typecast 1회(narr_full.mp3 있으면 안 부름)
    PYTHONUTF8=1 py make.py render    # A(얜샷템 틀, 원음 하이라이트+TTS 한마디) + B(재미썸홈 t11 틀) → render/final.mp4 → 바탕화면

흐름: [A 0~약 12초] 안유진 원음 O1a·O1b·O2a·O2b(IVE 8o3M3DmY05E) → 필재 TTS 한마디(F1) — 얜샷템 틀('출처 : IVE')
      [B] 다리 "저 영상 보고 나도…" → 써 보니 ①② → 반전(그냥 미국 마트 로션) → 남들도(안유진도) → 마무리 — 재미썸홈 t11 틀
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

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_안유진/재미썸홈판")
SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_안유진/src")   # eos/ rv/ · IVE 원본은 절대 경로
R = W / "render"
DESK = Path.home() / "Desktop" / "칼카피영상" / "얜샷템" / "하이브리드" / "칼카피_얜샷템_안유진eos바닐라로션_재미썸홈판.mp4"
HAM = "C:/숏템_칼카피/itemhome/1편_안유진로션/src/ive_8o3M3DmY05E.mp4"   # IVE 8o3M3DmY05E 1080p
VOICE = "tc_68257f68bc6e3c161ab5078d"      # 필재
TC_TEMPO = 1.25                            # voice_presets 필재 1.25(숏템 그대로) — 나머지는 atempo
CPS = 8.8                                  # 재미썸홈 프리셋 measured.speech_rate
FPS = 30
FRAME_A = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_B = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
TITLE_A = "안유진이 SNS 보고 산\n바닐라 바디로션"
LABEL_A = "출처 : IVE"
BODY_TITLE = "안유진 따라 사 본 로션"
WIN_A = 1080
WIN_B = (1080, 1407)
VOICE_AF = "highpass=f=90,dynaudnorm=f=150:g=7:p=0.9:m=12"   # IVE 원음(편집 BGM 밑, −28~−34 LUFS) 고르게 — 조사.md 받아쓰기(처리 뒤 '이게 제가 엄청'까지 들림)
BGM_A, BGM_A_DB, DUCK_DB = "sweets", -27.0, -10.0
TARGET_LUFS = -14.0

# ── 원음(안유진 본인 말) — 조사.md 받아쓰기로 고른 구간(쉼 569.21~570.22·572.52~576.22·579.08~579.66 잘라 냄) ──
ORIG = [("O1a", 568.20, 569.25), ("O1b", 570.17, 572.52), ("O2a", 576.22, 579.08), ("O2b", 579.66, 582.47)]
ORIG_CAPS = [(568.20, "이게 제가 엄청"), (570.17, "SNS에서 많이 본"), (571.45, "아이거든요"),
             (576.22, "바닐라 향이 처음엔"), (577.70, "좀 과한가 싶다가도"), (579.66, "계속 바르다 보면"), (580.95, "묘하게 중독되는"), (581.85, "그런 향")]
# A 화면: (원본 시작, 크롭 [x,y,w,h]) — 아래 편집 자막(y≈945)·'ANYUJIN' 밖. 이음매마다 크기를 바꿔 점프컷을 가린다. 화면 = 안유진 본인만
A_SHOTS = [(568.20, [760, 0, 800, 800]), (570.17, [300, 0, 820, 820]), (576.22, [300, 0, 900, 900]), (579.66, [330, 40, 820, 820])]
A_HEAD = (565.95, 0.60, [640, 0, 840, 840])   # ★첫 0.6초 = 눈 뜨고 카메라 보는 안유진 얼굴(사장님 썸네일 규칙 10-18). O1a 첫 프레임(568.2~568.45)은 눈 감는 중이라 그 0.6초만 이 컷(원음 '이게 제가'는 그대로 깔림)
GAP_O_F1 = 0.12
F1_SHOT = (HAM, 591.10, [560, 0, 880, 880])     # ★썸네일 규칙(사장님 10-18): 첫 TTS 구간 = 안유진 얼굴 크게 — 침대에 누운 얼굴(원본 컷 590.88 뒤, 아래 'ANYUJIN' 자막 y≈945 밖)
F1_SHOT2 = (HAM, 586.00, [480, 0, 880, 880])    # 병을 볼에 대고 웃는 안유진(원음 O2b 582.47 뒤 3.5초+)

LINES = [
    ("f1", "안유진이 SNS 보고 타겟에서 산 로션, 바로 이 이오에스 로션.", "안유진이 에스엔에스 보고, 타겟에서 산 로션. 바로 이 이오에스 로션."),   # 1판 TTS 가 원속 10.9자/초로 몰아 읽어 쉼표·마침표로 끊음
    ("bait", "저 영상 보고 나도 바로 직구로 질렀는데,", "저 영상 보고 나도 바로 직구로 질렀는데,"),
    ("limit", "이게 말도 안 되는 게 샤워하고 펴 발랐을 뿐인데 끈적임 하나 없이 쫙 스며들어.", "이게 말도 안 되는 게 샤워하고 펴 발랐을 뿐인데 끈적임 하나 없이 쫙 스며들어."),
    ("more", "심지어 바닐라에 캐러멜 섞인 향이라 바르고 나면 몸에서 디저트 냄새가 나.", "심지어 바닐라에 캐러멜 섞인 향이라 바르고 나면 몸에서 디저트 냄새가 나."),
    ("twist", "근데 진짜 충격적인 포인트는 이게 백화점 브랜드도 아니고 그냥 미국 마트 로션이라는 거야.", "근데 진짜 충격적인 포인트는, 이게 백화점 브랜드도 아니고 그냥 미국 마트 로션이라는 거야."),   # 1판 TTS 가 '이게 어 백화점'(2.5-pro·flash 둘 다)으로 군말 → 쉼표
    ("more", "타겟이나 월마트 같은 데서 다 파는 걸, 안유진도 SNS 보고 집어 왔대.", "타겟이나 월마트 같은 데서 다 파는 걸, 안유진도 에스엔에스 보고 집어 왔대."),
    ("land", "바디로션 다 쓰면 장바구니에 이것부터 담아 둬.", "바디로션 다 쓰면 장바구니에 이것부터 담아 둬."),   # 1판 TTS '떨어지면은'(두 모델 같음) → 말 바꿈
]
JUG, OB, HO, DT, DA, AU = "eos/eos_JugmExyy4Qg.mp4", "rv/OBp8bB4AEvo.mp4", "eos/eos_HOGLbtiiFZE.mp4", "rv/05DTFG-e_CU.mp4", "rv/DA9gTpGjyJE.mp4", "eos/eos_85AU_3DohFs.mp4"
PIECES = [   # (자막 조각, 소스, 시작, 크롭 [x,y,h](창 1080×1407 비율), 종류, 화면 설명) — "+" = 앞 컷 이어감
    ("안유진이 SNS 보고", None, None, None, "원본", "(A) 침대에 누운 안유진 얼굴"),
    ("타겟에서 산 로션", None, None, None, "원본", "(A) 〃"),
    ("바로 이 이오에스 로션", None, None, None, "원본", "(A) 병을 볼에 대고 웃는 안유진"),
    ("저 영상 보고 나도", JUG, 0.10, [0, 170, 930], "제품", "바닐라 캐시미어 병을 들고 얘기하는 여성(eos 공식 UGC)"),
    ("바로 직구로 질렀는데", DA, 164.20, [960, 260, 1180], "제품", "탁자 위 같은 병(펌프)"),
    ("이게 말도 안 되는 게", OB, 6.43, [440, 0, 1080], "제품", "펌프를 눌러 손바닥에 흰 로션"),
    ("샤워하고 펴 발랐을", JUG, 19.80, [0, 170, 930], "제품", "팔꿈치에 로션을 문질러 펴 바름"),
    ("뿐인데", "+", None, None, "제품", "(이어감)"),
    ("끈적임 하나 없이", DT, 218.30, [800, 0, 1440], "제품", "손가락에 묻은 로션을 문질러 펴 바름(제형)"),
    ("쫙 스며들어", "+", None, None, "제품", "(이어감)"),
    ("심지어 바닐라에", OB, 7.60, [600, 0, 1080], "제품", "로션 바른 손을 코에 대고 향 맡기"),
    ("캐러멜 섞인 향이라", "+", None, None, "제품", "(이어감 — 눈 감고 손 비빔)"),
    ("바르고 나면 몸에서", JUG, 7.10, [0, 170, 930], "제품", "병을 든 채 눈 감고 웃음"),
    ("디저트 냄새가 나", HO, 10.97, [650, 0, 1080], "제품", "로션 바른 뒤 어깨를 드러내고 웃음(eos 공식, 글자 없는 샷)"),
    ("근데 진짜", HO, 12.95, [60, 0, 1080], "제품", "eos 공식 병 정면(오른쪽 'dessert for your skin' 글자 밖)"),
    ("충격적인 포인트는", "+", None, None, "제품", "(이어감)"),
    ("이게 백화점 브랜드도", JUG, 21.70, [0, 170, 930], "제품", "바닐라 캐시미어 병을 들고 얘기하는 여성(원본 컷 21.60 뒤)"),
    ("아니고", "+", None, None, "제품", "(이어감)"),
    ("그냥 미국 마트", JUG, 25.10, [0, 170, 930], "제품", "선반에 줄지은 24H 바디로션들 — 맨 앞 바닐라 캐시미어"),
    ("로션이라는 거야", "+", None, None, "제품", "(이어감)"),
    ("타겟이나 월마트", DA, 168.50, [960, 260, 1180], "제품", "탁자 위 같은 병(다른 각도, 앞 컷 165.2 와 3초+ 떨어짐)"),
    ("같은 데서 다 파는 걸", "+", None, None, "제품", "(이어감)"),
    ("안유진도 SNS 보고", HAM, 595.20, [620, 0, 880], "원본", "침대에서 머리를 넘기며 말하는 안유진(원본 컷 594.33 뒤, 아래 '[나른나른]' 자막 y≈900 밖, 소리 없음)"),
    ("집어 왔대", "+", None, None, "원본", "(이어감)"),
    ("바디로션 다 쓰면", JUG, 15.00, [0, 170, 930], "제품", "병 근접('vanilla cashmere' 라벨)"),
    ("장바구니에 이것부터", OB, 1.50, [250, 0, 1080], "제품", "병을 들어 보임(끝 컷)"),
    ("담아 둬", "+", None, None, "제품", "(이어감)"),
]
SFX_ROLES = [l[0] for l in LINES[1:]]
# 나레 줄 구간(TTS 2회째 narr_full → narr_tight(앞뒤 무음 깎고 0.28초 넘는 쉼만 0.28) 기준 초) — silencedetect −40dB/0.1 + 줄 단독 받아쓰기(2.5-pro·2.5-flash, 대본과 같음)
#   twist 앞 13.32~13.88 은 TTS 가 붙인 작은 '아'(−34dB, 2.5-pro·flash 토막 받아쓰기 둘 다 '아') → 13.90 부터 씀
LINE_SPANS_RAW = [(0.0, 3.81), (4.14, 5.95), (6.17, 9.91), (10.11, 13.22), (0.0, 99.0), (19.13, 23.07), (23.36, 25.664)]
#   twist 는 1회째(narr_full) 가 앞에 '아(와)'를 붙여(13.32~13.88 잘라도 2.5-pro·flash 둘 다 '아 근데') 그 줄만 따로 합성한 twist_a.mp3 를 쓴다(같은 필재·같은 글, 받아쓰기 2/2 대본과 같음)
LINE_SRC = {4: "twist_a.mp3"}
LINE_TEMPO = [1.00, 1.06, 1.13, 1.00, 1.35, 1.23, 1.10]   # 줄별 atempo — F1 은 1.0(1.15·1.30 이면 '안유진이'가 '아 뉴진이'·'뉴진스'로 들림: 서버 3-flash·flash-latest 토막 받아쓰기 10-18) · 원속(줄 글자÷구간) 7.09·8.84·8.29·9.65·7.36·7.61·8.25 자/초 → 줄마다 ≈9.4(쉼 넣은 전체 ≈8.8), 끝 줄은 평균 아래
INNER_PAUSES_RAW = []
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
    for (name, a, b), (ss, cr) in zip(ORIG, A_SHOTS):
        rows.append({"label": f"A {name} 원음 {o_t:.2f}+{b - a:.2f}", "src": HAM, "a": a, "b": b, "crop": [cr[0], cr[1], cr[2]], "size": (300, 300),
                     "caps": " / ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b), "seen": "안유진 본인(말하는 사람) 단독 화면", "kind": "원음"})
        o_t += b - a
    f1d = sum(nchar(p[0]) for p in PIECES[:3]) / CPS
    f1a = sum(nchar(p[0]) for p in PIECES[:2]) / CPS + GAP_O_F1
    rows.append({"label": f"A F1 TTS {o_t:.2f}+{f1a:.2f}", "src": F1_SHOT[0], "a": F1_SHOT[1], "b": F1_SHOT[1] + f1a, "crop": F1_SHOT[2],
                 "size": (300, 300), "caps": " / ".join(p[0] for p in PIECES[:2]), "seen": "침대에 누운 안유진 얼굴", "kind": "제품"})
    rows.append({"label": f"A F1 TTS {o_t + f1a:.2f}+{f1d + GAP_O_F1 - f1a:.2f}", "src": F1_SHOT2[0], "a": F1_SHOT2[1], "b": F1_SHOT2[1] + f1d + GAP_O_F1 - f1a,
                 "crop": F1_SHOT2[2], "size": (300, 300), "caps": PIECES[2][0], "seen": "병을 볼에 대고 웃는 안유진", "kind": "제품"})
    for g in gs:
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g['kind']}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": g["crop"], "size": (230, 300), "caps": " / ".join(PIECES[k][0] for k in g["pieces"]), "seen": g["seen"], "kind": g["kind"]})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 3 * 300 + 330, 310, 2
    head = 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 안유진 eos 바닐라 캐시미어 — 재미썸홈판 계획 시트(TTS 전) · 예상 {times[-1][1]:.1f}초 · A 원음 {sum(b - a for _, a, b in ORIG):.2f}초 + TTS · B 컷 {len(gs)}",
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
        "channel": "얜샷템 하이브리드(재미썸홈판)", "topic": "안유진이 SNS 보고 타겟에서 산 eos 시어 베터 24H 모이스처 바디로션 바닐라 캐시미어 — 원음 하이라이트 → 나도 샀다 → 써 보니 ①② → 반전(그냥 미국 마트 로션) → 남들도(안유진도) → 마무리",
        "frames": {"A": str(FRAME_A.relative_to(ROOT)), "A_title": TITLE_A, "A_label": LABEL_A, "B": "channel/evenshopping/preset/숏템템플릿 (t11, frameRule body_all)", "B_bodyTitle": BODY_TITLE},
        "orig_audio": [{"id": n, "src": "8o3M3DmY05E", "span": [a, b], "said": " ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b)} for n, a, b in ORIG],
        "lines": [{"slot": s, "text": t, "tts": tt, "chars": nchar(tt)} for s, t, tt in LINES],
        "tts_one_call": " ".join(l[2] for l in LINES), "voice": f"Typecast 필재 {VOICE} tempo {TC_TEMPO} 1회",
        "pieces": [{"i": k + 1, "line": pl[k], "caption": p[0], "t": list(times[k]), "est": est} for k, p in enumerate(PIECES)],
        "hype": {"①센 시작": "원음 '바닐라 향이 처음엔 좀 과한가 싶다가도 계속 바르다 보면 묘하게 중독되는 그런 향' + '저 영상 보고 나도 바로 직구로 질렀는데'", "②권위": "안유진 본인 말(원음)",
                 "③진짜 핵심 반전": "근데 진짜 충격적인 포인트는(백화점 브랜드 아닌 미국 마트 로션)", "④심지어": "심지어 바닐라에 캐러멜", "⑤남들도": "안유진도 SNS 보고 집어 왔대"},

        **(extra or {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps({
        "A": [{"id": n, "src": HAM, "ss": a, "dur": round(b - a, 3), "crop_xywh": cr, "zoom": round(WIN_A / cr[2], 2), "audio": "원음(본인 말)"}
              for (n, a, b), (_, cr) in zip(ORIG, A_SHOTS)] + [{"id": "F1", "src": F1_SHOT[0], "ss": F1_SHOT[1], "crop_xywh": F1_SHOT[2],
                                                                 "zoom": round(WIN_A / F1_SHOT[2][2], 2), "audio": "무음(나레)"},
                                                                {"id": "F1b", "src": F1_SHOT2[0], "ss": F1_SHOT2[1], "crop_xywh": F1_SHOT2[2],
                                                                 "zoom": round(WIN_A / F1_SHOT2[2][2], 2), "audio": "무음(나레)"}],
        "B": [{k: v for k, v in g.items()} for g in gs],
        "src_urls": {HAM: "https://youtu.be/8o3M3DmY05E (IVE '[IVE LOG] 강아지 가방 최초(?) 공개 in WORLD TOUR | 윶 LOG' 2026-09-17, 1080p)",
                     JUG: "eos Products JugmExyy4Qg 'the eos body lotion you NEED!' 720×1270 — 화면 글자 없음",
                     OB: "TerraTested OBp8bB4AEvo 'I was seriously surprised by this EOS body lotion.' 1080p",
                     HO: "eos Products HOGLbtiiFZE 'That OG Vanilla' 1080p",
                     DT: "That vivian 05DTFG-e_CU 'EOS vanilla cashmere Body Lotion Review' 1440p",
                     DA: "Khan Product Reviews DA9gTpGjyJE 'EOS Vanilla Cashmere Lotion Review' 1440p",
                     AU: "eos Products 85AU_3DohFs 'Vanilla Cashmere Trifecta' 1080p"},
        "audio_rule": "B 재료 원음 전부 끔(-an). A 원음 = 안유진 말만(O1a·O1b·O2a·O2b, IVE 편집 BGM 은 원음 밑에 같이 깔림 — 사람 말 아님).",
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
