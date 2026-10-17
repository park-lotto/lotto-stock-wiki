# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 강민경 포트레 워터 핏 스킨 틴트(SPF50+ 톤업 선크림) — 재미썸홈판 (2026-10-17). 엔진 코드는 안 고친다(부르기만).
정본 = 하이브리드_함익병/재미썸홈판/make.py → 하이브리드_최은경 복사본 — 소재 상수(원음·화면·대사·조각)만 바꿈.

    PYTHONUTF8=1 py make.py plan      # 대본.json·재료.json·plan/계획_시트.jpg (TTS 전)
    PYTHONUTF8=1 py make.py tts       # 필재 Typecast 1회(narr_full.mp3 있으면 안 부름)
    PYTHONUTF8=1 py make.py render    # A(얜샷템 틀, 원음 하이라이트+TTS 한마디) + B(재미썸홈 t11 틀) → render/final.mp4 → 바탕화면

흐름: [A 약 11초] 강민경 원음 O1·O2(걍밍경 WmEjrZFVRB4, 목에 발라 본 직후) → 필재 TTS 한마디(F1) — 얜샷템 틀('출처 : 걍밍경')
      [B] 다리 "저 영상 보고 나도…" → 써 보니 ①② → 색 고르기 → 남들도 → 마무리 — 재미썸홈 t11 틀(scene_style.compose, 본문만 body_all)
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

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_강민경/재미썸홈판")
SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_강민경/src")
R = W / "render"
DESK = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/하이브리드/칼카피_얜샷템_강민경포트레틴트_재미썸홈판.mp4")
HAM = "C:/숏템_칼카피/yanshottem/강민경_피부/src/kmk_WmEjrZFVRB4.mp4"   # 걍밍경 WmEjrZFVRB4 1080p 전체(이름은 정본 상수 그대로)
VOICE = "tc_68257f68bc6e3c161ab5078d"      # 필재
TC_TEMPO = 1.25                            # voice_presets 필재 1.25(숏템 그대로) — 나머지는 atempo
CPS = 8.8                                  # 재미썸홈 프리셋 measured.speech_rate
FPS = 30
FRAME_A = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_B = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
TITLE_A = "강민경이 1년 만든\n물광 톤업 선크림"
LABEL_A = "출처 : 걍밍경"
BODY_TITLE = "강민경 따라 산 톤업 선크림"
WIN_A = 1080                               # 얜샷템 영상 칸 1080×1080
WIN_B = (1080, 1407)                       # t11 영상 칸
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
BGM_A, BGM_A_DB, DUCK_DB = "sweets", -27.0, -10.0
TARGET_LUFS = -14.0

# ── 원음(강민경 본인 말) — 기본편 강민경_피부 근거.md §2(편집 자막 흰색·참고 목소리 대조·받아쓰기 2회, 화자 1) 그대로 ──
#   O1 638.24~642.95(소리만 0.06초 앞당김 — 첫 말 "너" 시작 638.26, 638.30 에서 자르면 완성본 받아쓰기 flash 가 "노는"으로 들음 · 화면은 샷 경계 638.30부터라 입이 2프레임 앞섬) "너무 신기하다 이거 진짜 / 이거는 카메라로도 무조건 비포 애프터 나오겠다"
#   O2 652.25~656.12 "진짜 찍길 잘했다 / 목 안 찍고 넘어갔으면 이거 못 믿으셨겠어"
ORIG = [("O1", 638.24, 642.95), ("O2", 652.25, 656.12)]
ORIG_CAPS = [(638.24, "너무 신기하다 이거 진짜"), (640.05, "이거는 카메라로도"), (641.35, "무조건 비포 애프터"), (642.25, "나오겠다"),
             (652.25, "진짜 찍길 잘했다"), (653.70, "목 안 찍고 넘어갔으면"), (654.95, "이거 못 믿으셨겠어")]
# A 화면: 원음 토막마다 [(원본 시작, 크롭 [x,y,w,h], 길이 또는 None=끝까지)] — 원본 자막(y≥790) 밖. 원본 샷 경계 640.39 · 643.06
A_SHOTS = [[(638.30, [770, 0, 780, 780], 2.09), (640.39, [555, 0, 780, 780], None)],
           [(652.25, [790, 0, 770, 770], None)]]
GAP_O_F1 = 0.12                            # 원음 끝 → TTS 한마디
F1_SHOT = (HAM, 631.3, [700, 0, 800, 800])          # 걍밍경 원본 631.3~(샷 631.13~634.68) 목에 바른 뒤 놀란 강민경 얼굴 근접 — 사장님 규칙 "TTS 한마디 화면 = 연예인 얼굴"(10-18)
F1_SHOT2 = (HAM, 615.0, [650, 0, 800, 800])         # "바로 이거" = 걍밍경 원본 615.0~(샷 614.82~616.99) 강민경 얼굴 근접

LINES = [   # (칸, 화면 글 text, 읽는 글 tts) — 0 = A 끝 한마디(F1), 1~ = B
    ("f1", "강민경이 일 년 걸려 직접 만든 톤업 선크림, 바로 이거.", "강민경이 일 년 걸려 직접 만든 톤업 선크림, 바로 이거."),
    ("bait", "저 영상 보고 나도 당장 따라 샀는데,", "저 영상 보고 나도 당장 따라 샀는데,"),
    ("limit", "이게 말도 안 되는 게 선크림인데 바르자마자 피부가 한 톤 맑아져.", "이게 말도 안 되는 게 선크림인데 바르자마자 피부가 한 톤 맑아져."),
    ("more", "심지어 에센스가 약 67%라 허옇게 안 뜨고 촉촉하게 붙어.", "심지어 에센스가 약 육십칠 퍼센트라 허옇게 안 뜨고 촉촉하게 붙어."),
    ("twist", "근데 진짜 중요한 포인트는 색깔이야.", "근데 진짜 중요한 포인트는 색깔이야."),
    ("more", "웜톤은 아이보리, 쿨톤은 로즈로 골라야 찰떡이거든.", "웜톤은 아이보리, 쿨톤은 로즈로 골라야 찰떡이거든."),
    ("more", "요즘 뷰티 유튜버들 파우치에도 이거 자주 보이더라.", "요즘 뷰티 유튜버들 파우치에도 이거 자주 보이더라."),
    ("land", "선크림이랑 톤업크림 따로 사지 말고 이걸로 한 번에 끝내 봐.", "선크림이랑 톤업크림 따로 사지 말고 이걸로 한 번에 끝내 봐."),
]
# 자막 조각(≤13자) · 재료 — (조각, 소스 파일|"+", 소스 시작초, 크롭 [x,y,h](폭 = h×1080/1407), 종류, 화면에 보이는 것)
#   "+" = 앞 컷을 끊지 않고 이어감. 모든 재료 = 같은 제품(포트레 워터 핏 스킨 틴트 검은 튜브): 걍밍경 원본 · 포트레 공식 상세 사진(stills/*_t11)
#   · 이 제품을 이름으로 소개한 리뷰 영상(cand/*, ss = 받은 구간 파일 안 초 · 남의 얼굴은 크롭 밖)
K = HAM
PIECES = [
    ("강민경이 일 년 걸려", None, None, None, "얼굴", "(A) 강민경 얼굴(원본 631.3~)"),
    ("직접 만든 톤업 선크림", None, None, None, "얼굴", "(A) 〃"),
    ("바로 이거", None, None, None, "얼굴", "(A) 강민경 얼굴(원본 615.0~)"),
    # bait
    ("저 영상 보고 나도", "cand/jLWBbYzmJbg_665.mp4", 6.0, [230, 80, 1000], "제품", "강쥐G 671.0~ 회색 바탕 위 이 검은 튜브 정면(오른쪽 글상자 x≥1000 밖)"),
    ("당장 따라 샀는데", "+", None, None, "제품", "(이어감)"),
    # limit ① 선크림인데 한 톤
    ("이게 말도 안 되는 게", "stills/hero_spf_t11.mp4", 0.0, [0, 0, 1407], "제품", "포트레 공식 — 물 속 튜브 + 'SPF 50+ | PA++++ 말갛게 톤업되는 선크림'"),
    ("선크림인데 바르자마자", K, 426.0, [700, 0, 760], "제품", "걍밍경 원본 426.0~ 강민경이 이 틴트를 얼굴에 펴 바름(원본 자막 y≥780 밖)"),
    ("피부가 한 톤 맑아져", "stills/beforeafter_t11.mp4", 0.0, [0, 0, 1407], "제품", "포트레 공식 BEFORE/AFTER"),
    # more ② 에센스 67%
    ("심지어 에센스가", "stills/drip_t11.mp4", 0.0, [0, 0, 1407], "제품", "포트레 공식 — 튜브 위로 흘러내리는 제형"),
    ("약 67%라", "+", None, None, "제품", "(이어감)"),
    ("허옇게 안 뜨고", "cand/n2g4FmoCj4g_165.mp4", 15.0, [560, 0, 800], "제품", "뭉컁 180.0~ 손바닥에 펴 바른 이 틴트 — 촉촉한 윤기(아래 자막 y≥830 밖)"),
    ("촉촉하게 붙어", "+", None, None, "제품", "(이어감)"),
    # twist 색깔
    ("근데 진짜", "cand/yK3C2YAMrlU_215.mp4", 6.6, [300, 0, 860], "제품", "민제 221.6~ 이 튜브 두 개(아이보리·로즈)를 들어 보임(얼굴·딱지 밖)"),
    ("중요한 포인트는", "+", None, None, "제품", "(이어감)"),
    ("색깔이야", "stills/colors_t11.mp4", 0.0, [0, 0, 1407], "제품", "포트레 공식 COLOR — IVORY(웜)·ROSE(쿨) 발색"),
    # more 웜/쿨
    ("웜톤은 아이보리", "+", None, None, "제품", "(이어감)"),
    ("쿨톤은 로즈로 골라야", "+", None, None, "제품", "(이어감)"),
    ("찰떡이거든", K, 417.0, [0, 0, 740], "제품", "걍밍경 원본 417.0~ 이 튜브 + 손등 발색(원본 글 x≥760 밖)"),
    # more 남들도
    ("요즘 뷰티 유튜버들", "cand/yeHoe--atF4_280.mp4", 9.15, [480, 0, 1042], "제품", "코코초 289.15~ 이 검은 튜브를 들어 보임(딱지 x<350 밖)"),
    ("파우치에도", "+", None, None, "제품", "(이어감)"),
    ("이거 자주 보이더라", "cand/jLWBbYzmJbg_665.mp4", 18.5, [60, 230, 700], "제품", "강쥐G 683.5~ 이 튜브에서 손가락에 짜는 손(얼굴 x≥650 밖)"),
    # land(끝 컷 ≥1.5초)
    ("선크림이랑 톤업크림", K, 661.2, [300, 0, 780], "제품", "걍밍경 원본 661.2~ 강민경이 이 검은 튜브를 들어 보임(얼굴·흰 스틱 x≥900 밖)"),
    ("따로 사지 말고", "+", None, None, "제품", "(이어감)"),
    ("이걸로 한 번에 끝내 봐", "stills/model_t11.mp4", 0.0, [0, 0, 1407], "제품", "포트레 공식 — 강민경이 이 튜브를 든 모델컷(끝 컷)"),
]
SFX_ROLES = [l[0] for l in LINES[1:]]
TEMPO, TEMPO_LAST = 1.27, 1.143  # 나레 atempo(지휘 상한 1.27 → 8.47자/초) · 끝 문장만 1.143(TTS가 끝 문장을 빨리 읽음 원속 8.28 vs 6.67자/초, −10% = B17 한도)
# narr_full.mp3 = 필재 1회 합성 그대로(손댄 곳 없음)
# 문장부호 쉼 자리(atempo 뒤·쉼 모양 전 narr_pre.wav 초 = 앞뒤 무음 자른 narr 의 silencedetect −40dB/0.06 쉼 가운데 ÷ 1.27) — 선크림, | 이거. | 샀는데, | 맑아져. | 붙어. | 색깔이야. | 찰떡이거든. | 보이더라.
#   받아쓰기 토막(2.5-pro 어절 시각 + 2.5-flash 토막)으로 줄 머리 대조. '웜톤은 아이보리,' 줄 안 쉼표는 줄 머리가 아니라 PUNCT_AT 에서 뺌(쉼 그대로)
PUNCT_AT = [(",", 1.931), (".", 2.583), (",", 4.502), (".", 7.416), (".", 10.534), (".", 12.669), (".", 14.690), (".", 16.889)]
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
                         "caps": " / ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b), "seen": "강민경 본인(말하는 사람) 단독 화면", "kind": "원음"})
            o_t += d_; left -= d_
    f1d = sum(nchar(p[0]) for p in PIECES[:3]) / CPS
    f1a = sum(nchar(p[0]) for p in PIECES[:2]) / CPS + GAP_O_F1
    rows.append({"label": f"A F1 TTS {o_t:.2f}+{f1a:.2f}", "src": F1_SHOT[0], "a": F1_SHOT[1], "b": F1_SHOT[1] + f1a, "crop": F1_SHOT[2],
                 "size": (300, 300), "caps": " / ".join(p[0] for p in PIECES[:2]), "seen": "강민경 얼굴(원본 631.3~)", "kind": "얼굴"})
    rows.append({"label": f"A F1 TTS {o_t + f1a:.2f}+{f1d + GAP_O_F1 - f1a:.2f}", "src": F1_SHOT2[0], "a": F1_SHOT2[1], "b": F1_SHOT2[1] + f1d + GAP_O_F1 - f1a,
                 "crop": F1_SHOT2[2], "size": (300, 300), "caps": PIECES[2][0], "seen": "강민경 얼굴(원본 615.0~)", "kind": "얼굴"})
    for g in gs:
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g['kind']}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": g["crop"], "size": (230, 300), "caps": " / ".join(PIECES[k][0] for k in g["pieces"]), "seen": g["seen"], "kind": g["kind"]})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 3 * 300 + 330, 310, 2
    head = 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 강민경 포트레 틴트 — 재미썸홈판 계획 시트(TTS 전) · 예상 {times[-1][1]:.1f}초 · A 원음 {sum(b - a for _, a, b in ORIG):.2f}초 + TTS · B 컷 {len(gs)}",
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
        "channel": "얜샷템 하이브리드(재미썸홈판)", "topic": "강민경이 포트레 팀과 1년 동안 만든 워터 핏 스킨 틴트(SPF50+ 톤업 선크림) — 원음 하이라이트(목에 발라 보고 놀람) → 나도 샀다 → 써 보니 ①② → 색 고르기 → 남들도 → 마무리",
        "frames": {"A": str(FRAME_A.relative_to(ROOT)), "A_title": TITLE_A, "A_label": LABEL_A, "B": "channel/evenshopping/preset/숏템템플릿 (t11, frameRule body_all)", "B_bodyTitle": BODY_TITLE},
        "orig_audio": [{"id": n, "src": "WmEjrZFVRB4", "span": [a, b], "said": " ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b)} for n, a, b in ORIG],
        "lines": [{"slot": s, "text": t, "tts": tt, "chars": nchar(tt)} for s, t, tt in LINES],
        "tts_one_call": " ".join(l[2] for l in LINES), "voice": f"Typecast 필재 {VOICE} tempo {TC_TEMPO} 1회",
        "pieces": [{"i": k + 1, "line": pl[k], "caption": p[0], "t": list(times[k]), "est": est} for k, p in enumerate(PIECES)],
        "hype": {"①센 시작": "원음 '너무 신기하다 이거 진짜, 카메라로도 무조건 비포 애프터 나오겠다' + '저 영상 보고 나도 당장 따라 샀는데'", "②권위": "강민경 본인 말(원음) — '목 안 찍고 넘어갔으면 이거 못 믿으셨겠어'", "③진짜 핵심 반전": "근데 진짜 중요한 포인트는 색깔이야", "④심지어": "심지어 에센스가 약 67%", "⑤남들도": "요즘 뷰티 유튜버들 파우치에도"},
        **(extra or {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps({
        "A": [{"id": n, "src": HAM, "span": [a, b], "shots": [{"ss": ss, "crop_xywh": cr, "dur": dd, "zoom": round(WIN_A / cr[2], 2)} for ss, cr, dd in shots],
               "audio": "원음(본인 말)"} for (n, a, b), shots in zip(ORIG, A_SHOTS)] + [{"id": "F1", "src": F1_SHOT[0], "ss": F1_SHOT[1], "crop_xywh": F1_SHOT[2],
                                                                 "zoom": round(WIN_A / F1_SHOT[2][2], 2), "audio": "무음(나레)"},
                                                                {"id": "F1b", "src": F1_SHOT2[0], "ss": F1_SHOT2[1], "crop_xywh": F1_SHOT2[2],
                                                                 "zoom": round(WIN_A / F1_SHOT2[2][2], 2), "audio": "무음(나레)"}],
        "B": [{k: v for k, v in g.items()} for g in gs],
        "src_urls": {HAM: "https://youtu.be/WmEjrZFVRB4 (걍밍경 = 강민경 본인 채널, 2026-02-20, 1080p) — 설명란 '포트레 워터 핏 스킨 틴트'",
                     "stills/*": "포트레 공식몰 https://portre.co.kr/product/detail.html?product_no=319 상세 이미지 3장(2026-10-17 받음) → 조사/make_stills.py 로 6초 다가가기 영상",
                     "cand/*": "이 제품을 이름으로 소개한 리뷰 영상 구간(조사/조사.md §1): jLWBbYzmJbg 강쥐G · n2g4FmoCj4g 뭉컁 · yK3C2YAMrlU 민제 · yeHoe--atF4 코코초"},
        "audio_rule": "B 재료 원음 전부 끔(-an). A 원음 = 강민경 말만(O1·O2, 기본편 화자 판정 3중 + 이번 완성본 받아쓰기 화자 1).",
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
