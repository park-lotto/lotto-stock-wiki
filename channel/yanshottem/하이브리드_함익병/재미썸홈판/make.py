# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 2호 함익병 도브 비누 — 재미썸홈판 (관제 097, 2026-10-17). 엔진 코드는 안 고친다(부르기만).

    PYTHONUTF8=1 py make.py plan      # 대본.json·재료.json·plan/계획_시트.jpg (TTS 전)
    PYTHONUTF8=1 py make.py tts       # 필재 Typecast 1회(narr_full.mp3 있으면 안 부름)
    PYTHONUTF8=1 py make.py render    # A(얜샷템 틀, 원음 하이라이트+TTS 한마디) + B(재미썸홈 t11 틀) → render/final.mp4 → 바탕화면

흐름: [A 0~약 10.6초] 함익병 원음 O1a·O1b·O2(제철건강 A8Q-vnrpOr4) → 필재 TTS 한마디(F1) — 얜샷템 틀(channel/mantem/frame_얜샷템.json, '출처 : 제철건강')
      [B] 다리 "저 영상 보고 나도…" → 써 보니 ①② → 원장님 말(녹는다·말려라) → 마무리 — 재미썸홈 t11 틀(scene_style.compose, 본문만 body_all)
소리: TTS 1회를 A 끝 한마디 + B 나레로 나눠 쓴다(같은 파일·같은 크기). 원음은 나레 크기에 맞춘다. A만 BGM(얜샷템 규칙, 원음 밑 덕킹),
      B는 BGM 없음 + 숏템 효과음팩 density=low(재미썸홈 수정2 규칙). 시각의 주인 = 이 파일 PLAN 상수들.
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

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_함익병/재미썸홈판")
SRC = W / "src"
R = W / "render"
DESK = Path.home() / "Desktop" / "칼카피영상" / "얜샷템" / "칼카피_얜샷템_함익병도브_재미썸홈판.mp4"
HAM = "ham_A8Q.mp4"                        # 제철건강 A8Q-vnrpOr4 1080p 전체(137+140)
VOICE = "tc_68257f68bc6e3c161ab5078d"      # 필재
TC_TEMPO = 1.25                            # voice_presets 필재 1.25(숏템 그대로) — 나머지는 atempo(≤1.27)
CPS = 8.8                                  # 재미썸홈 프리셋 measured.speech_rate
FPS = 30
FRAME_A = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_B = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
TITLE_A = "함익병 원장이\n주로 쓴다는 비누"
LABEL_A = "출처 : 제철건강"
BODY_TITLE = "함익병 원장 따라 써 본 비누"
WIN_A = 1080                               # 얜샷템 영상 칸 1080×1080
WIN_B = (1080, 1407)                       # t11 영상 칸
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"   # 박세리·한고은 편과 같은 약한 처리
BGM_A, BGM_A_DB, DUCK_DB = "sweets", -27.0, -10.0   # 얜샷템(만템 8/8 BGM) — A 구간만, 원음 밑 덕킹
TARGET_LUFS = -14.0                        # 얜샷템 −16 / 재미썸홈 −13.4 사이(한 파일 한 크기 — 나레 크기를 두 틀에서 같게)

# ── 원음(함익병 본인 말) — silencedetect −35dB/0.12 + 받아쓰기 3회로 고른 구간(근거.md) ──
#   O1a 1272.93~1274.68 "그럼 내가 특정 제품을 얘기를 하면" / (1274.72~1275.15 MC '네' 잘라 냄)
#   O1b 1275.18~1279.20 "제가 뭐 주로 쓰는 비누이기도 한데 도브가 가장 그게 보습력이 많아요" / (1279.29~1280.12 '써 보면'+MC '네' 잘라 냄)
#   O2  1280.42~1283.20 "세수하고 나면 웬만한 지성이라도 덜 당겨요" (원본 컷 1283.25 앞)
ORIG = [("O1a", 1272.93, 1274.68), ("O1b", 1275.18, 1279.20), ("O2", 1280.42, 1283.20)]
# 원음 자막(흰) — (원본 초, 글) 원본 자동자막 어절 시각
ORIG_CAPS = [(1272.93, "그럼 내가 특정 제품을"), (1273.84, "얘기를 하면"),
             (1275.18, "제가 뭐 주로 쓰는"), (1275.72, "비누이기도 한데"), (1277.12, "도브가 가장"), (1277.96, "그게 보습력이 많아요"),
             (1280.42, "세수하고 나면"), (1281.30, "웬만한 지성이라도"), (1282.42, "덜 당겨요")]
# A 화면: (원본 시작, 크롭 [x,y,w,h]) — 왼쪽 위 채널 글자(x<600,y<275)·아래 편집 자막(y≥920) 밖. 이음매마다 크기를 바꿔 점프컷을 가린다
A_SHOTS = [(1272.93, [640, 0, 720, 720]), (1275.18, [690, 40, 560, 560]), (1280.42, [640, 0, 720, 720])]
GAP_O_F1 = 0.12                            # 원음 끝 → TTS 한마디
F1_SHOT = ("src_cSzFp63NmwY.mp4", 23.45, [490, 0, 860, 860])   # 도브 광고(PH) 바에 크림이 부어지는 장면(23.42~25.65 한 샷) — 아래 'After 7-day usage'(y≈940) 밖
F1_SHOT2 = ("src_l20qnFWsxzQ.mp4", 8.30, [560, 60, 740, 740])  # '바로 이 도브' = 도브 공식(한국) 바 윗면 새 무늬 — 오른쪽 '저자극으로'(x≥1470)·아래 알약 칸(y≥865) 밖, 10.1초 '¼' 글자 전

LINES = [   # (칸, 화면 글 text, 읽는 글 tts) — 0 = A 끝 한마디(F1), 1~ = B
    ("f1", "함익병 원장이 주로 쓴다는 비누, 바로 이 도브.", "함익병 원장이 주로 쓴다는 비누, 바로 이 도브."),
    ("bait", "저 영상 보고 나도 당장 따라 샀는데,", "저 영상 보고 나도 당장 따라 샀는데,"),
    ("limit", "이게 말도 안 되는 게 세수하고 나서 얼굴이 진짜 덜 당기더라.", "이게 말도 안 되는 게 세수하고 나서 얼굴이 진짜 덜 당기더라."),
    ("more", "심지어 이게 거품이 크림처럼 부드럽게 올라와서 금방 헹궈져.", "심지어 이게 거품이 크림처럼 부드럽게 올라와서 금방 헹궈져."),
    ("twist", "근데 진짜 충격적인 포인트는 비누가 물기를 다 빨아먹는다는 거.", "근데 진짜 충격적인 포인트는 비누가 물기를 다 빨아먹는다는 거."),
    ("more", "원장님 말로는 욕실에 그냥 두면 일주일도 못 가 녹아서 꼭 꺼내 말려 둬야 한대.", "원장님 말로는 욕실에 그냥 두면 일주일도 못 가 녹아서 꼭 꺼내 말려 둬야 한대."),
    ("more", "댓글에도 나도 도브 쓴다는 사람이 여럿이던데,", "댓글에도 나도 도브 쓴다는 사람이 여럿이던데,"),
    ("land", "비싼 세안제 사기 전에 비누 하나만 바꿔 봐.", "비싼 세안제 사기 전에 비누 하나만 바꿔 봐."),
]
# 자막 조각(≤13자) · 재료 — (조각, 소스 파일|"+", 소스 시작초, 크롭 [x,y,h](폭 = h×1080/1407), 종류, 화면에 보이는 것)
#   "+" = 앞 컷을 끊지 않고 이어감(같은 묶음 이웃 토막은 한 컷 — 재미썸홈 수정2 규칙)
PIECES = [
    # F1 (A 틀, 컷은 F1_SHOT 한 컷)
    ("함익병 원장이", None, None, None, "제품", "(A) 도브 바에 크림이 부어짐"),
    ("주로 쓴다는 비누", None, None, None, "제품", "(A) 〃"),
    ("바로 이 도브", None, None, None, "제품", "(A) 도브 바 윗면 새 무늬"),
    # L1 다리
    ("저 영상 보고 나도", "src_cSzFp63NmwY.mp4", 27.70, [40, 0, 1080], "제품", "하얀 도브 상자 위 도브 바(포장째 산 제품)"),
    ("당장 따라 샀는데", "+", None, None, "제품", "(이어감)"),
    # L2 ① 세수 → 덜 당김
    ("이게 말도 안 되는 게", "src_sYdJEYWmfMg.mp4", 6.05, [20, 40, 760], "제품", "도브 거품으로 얼굴 씻는 여성(세 칸 중 왼쪽 얼굴 칸만)"),
    ("세수하고 나서", "+", None, None, "제품", "(이어감)"),
    ("얼굴이 진짜 덜 당기더라", "src_cSzFp63NmwY.mp4", 17.10, [700, 0, 1080], "제품", "세안 뒤 두 손으로 볼을 감싸며 웃는 여성(도브 광고)"),
    # L3 ② 거품
    ("심지어 이게", "src_uPJjF0q2gIY.mp4", 32.60, [560, 100, 980], "제품", "하얀 도브 바를 손에 쥐고 거품 내는 손(세면대)"),
    ("거품이 크림처럼", "+", None, None, "제품", "(이어감) 손에 하얀 거품"),
    ("부드럽게 올라와서", "src_uPJjF0q2gIY.mp4", 71.50, [560, 100, 980], "제품", "같은 손에 크림처럼 두툼하게 올라온 거품(앞 컷 39초 뒤)"),
    ("금방 헹궈져", "+", None, None, "제품", "(이어감)"),
    # L4 반전 — 물기를 빨아먹는다
    ("근데 진짜", "src_uPJjF0q2gIY.mp4", 17.60, [560, 100, 980], "제품", "젖은 손바닥 위 하얀 도브 바(같은 손·같은 세면대)"),
    ("충격적인 포인트는", "+", None, None, "제품", "(이어감)"),
    ("비누가 물기를", "src_uPJjF0q2gIY.mp4", 22.80, [560, 100, 980], "제품", "같은 손이 젖은 바를 손안에서 굴림(앞 컷 3.7초 뒤 — B13 ±3초 밖)"),
    ("다 빨아먹는다는 거", "+", None, None, "제품", "(이어감)"),
    # L5 원장님 말 — 녹는다 → 말려라
    ("원장님 말로는", "src_c1IvDrByGrc.mp4", 155.80, [560, 0, 1080], "유사", "물 고인 비누 받침에 흐물흐물 녹아 붙은 비누"),
    ("욕실에 그냥 두면", "+", None, None, "유사", "(이어감)"),
    ("일주일도 못 가 녹아서", "src_c1IvDrByGrc.mp4", 12.30, [560, 0, 1080], "유사", "같은 받침을 들어 보이는 손 — 바닥에 녹아 붙은 비누"),
    ("꼭 꺼내 말려 둬야 한대", "src_spFXZnqXIhI.mp4", 14.70, [560, 0, 1080], "유사", "물 빠지는 구멍 받침 위에 하얀 비누를 올려 둠"),
    # L6 남들도
    ("댓글에도 나도", "src_ZcsmCplywSE.mp4", 20.20, [540, 0, 1080], "제품", "도브 바를 쓰는 여러 사람 얼굴 모음(도브 광고)"),
    ("도브 쓴다는 사람이", "+", None, None, "제품", "(이어감)"),
    ("여럿이던데", "+", None, None, "제품", "(이어감)"),
    # L7 마무리(끝 컷 ≥1.5초)
    ("비싼 세안제", "src_MUzRiCp23JM.mp4", 27.05, [400, 0, 1080], "제품", "도브 상자 위 하얀 도브 바(끝 컷)"),
    ("사기 전에", "+", None, None, "제품", "(이어감)"),
    ("비누 하나만 바꿔 봐", "+", None, None, "제품", "(이어감)"),
]
SFX_ROLES = [l[0] for l in LINES[1:]]
TEMPO, TEMPO_LAST = 1.27, 1.15   # 나레 atempo(지휘 상한 1.27, 8.73자/초) · 끝 문장만 1.15(TTS가 끝 문장을 빨리 읽음 11.7→10.4자/초, −9.4% ≤ B17 10%)
# 문장부호 쉼 자리(atempo 뒤·쉼 모양 전 narr_pre.wav 초, silencedetect −40dB 실측) — 비누, | 도브. | 샀는데, | 당기더라. | 헹궈져. | 거. | 한대. | 여럿이던데,
#   받아쓰기 2초 토막(flash-latest)으로 줄 머리 대조. 낱말 안 쉼(4.85 '안 되는 게|'·11.04 '포인트는|'·16.6 '댓글에도|')은 건드리지 않는다
PUNCT_AT = [(",", 1.36), (".", 2.23), (",", 3.90), (".", 6.68), (".", 9.26), (".", 12.83), (".", 16.10), (",", 18.38)]
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
    for (name, a, b), (ss, cr) in zip(ORIG, A_SHOTS):
        rows.append({"label": f"A {name} 원음 {o_t:.2f}+{b - a:.2f}", "src": HAM, "a": a, "b": b, "crop": [cr[0], cr[1], cr[2]], "size": (300, 300),
                     "caps": " / ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b), "seen": "함익병 본인(말하는 사람) 단독 화면", "kind": "원음"})
        o_t += b - a
    f1d = sum(nchar(p[0]) for p in PIECES[:3]) / CPS
    f1a = sum(nchar(p[0]) for p in PIECES[:2]) / CPS + GAP_O_F1
    rows.append({"label": f"A F1 TTS {o_t:.2f}+{f1a:.2f}", "src": F1_SHOT[0], "a": F1_SHOT[1], "b": F1_SHOT[1] + f1a, "crop": F1_SHOT[2],
                 "size": (300, 300), "caps": " / ".join(p[0] for p in PIECES[:2]), "seen": "도브 바에 크림이 부어짐(제품만)", "kind": "제품"})
    rows.append({"label": f"A F1 TTS {o_t + f1a:.2f}+{f1d + GAP_O_F1 - f1a:.2f}", "src": F1_SHOT2[0], "a": F1_SHOT2[1], "b": F1_SHOT2[1] + f1d + GAP_O_F1 - f1a,
                 "crop": F1_SHOT2[2], "size": (300, 300), "caps": PIECES[2][0], "seen": "도브 바 윗면 새 무늬(제품만)", "kind": "제품"})
    for g in gs:
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g['kind']}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": g["crop"], "size": (230, 300), "caps": " / ".join(PIECES[k][0] for k in g["pieces"]), "seen": g["seen"], "kind": g["kind"]})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 3 * 300 + 330, 310, 2
    head = 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 함익병 도브 — 재미썸홈판 계획 시트(TTS 전) · 예상 {times[-1][1]:.1f}초 · A 원음 {sum(b - a for _, a, b in ORIG):.2f}초 + TTS · B 컷 {len(gs)}",
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
        "channel": "얜샷템 하이브리드(재미썸홈판)", "topic": "함익병 원장이 주로 쓴다는 도브 비누 — 원음 하이라이트 → 나도 샀다 → 써 보니 ①② → 원장님 팁 → 마무리",
        "frames": {"A": str(FRAME_A.relative_to(ROOT)), "A_title": TITLE_A, "A_label": LABEL_A, "B": "channel/evenshopping/preset/숏템템플릿 (t11, frameRule body_all)", "B_bodyTitle": BODY_TITLE},
        "orig_audio": [{"id": n, "src": "A8Q-vnrpOr4", "span": [a, b], "said": " ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b)} for n, a, b in ORIG],
        "lines": [{"slot": s, "text": t, "tts": tt, "chars": nchar(tt)} for s, t, tt in LINES],
        "tts_one_call": " ".join(l[2] for l in LINES), "voice": f"Typecast 필재 {VOICE} tempo {TC_TEMPO} 1회",
        "pieces": [{"i": k + 1, "line": pl[k], "caption": p[0], "t": list(times[k]), "est": est} for k, p in enumerate(PIECES)],
        "hype": {"①센 시작": "원음 '그럼 내가 특정 제품을 얘기를 하면' + '저 영상 보고 나도 당장 따라 샀는데'", "②권위": "함익병 원장 본인 말(원음)",
                 "③진짜 핵심 반전": "근데 진짜 충격적인 포인트는", "④심지어": "심지어 이게", "⑤남들도": "댓글에도 나도 도브 쓴다는 사람이 여럿"},
        **(extra or {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps({
        "A": [{"id": n, "src": HAM, "ss": a, "dur": round(b - a, 3), "crop_xywh": cr, "zoom": round(WIN_A / cr[2], 2), "audio": "원음(본인 말)"}
              for (n, a, b), (_, cr) in zip(ORIG, A_SHOTS)] + [{"id": "F1", "src": F1_SHOT[0], "ss": F1_SHOT[1], "crop_xywh": F1_SHOT[2],
                                                                 "zoom": round(WIN_A / F1_SHOT[2][2], 2), "audio": "무음(나레)"},
                                                                {"id": "F1b", "src": F1_SHOT2[0], "ss": F1_SHOT2[1], "crop_xywh": F1_SHOT2[2],
                                                                 "zoom": round(WIN_A / F1_SHOT2[2][2], 2), "audio": "무음(나레)"}],
        "B": [{k: v for k, v in g.items()} for g in gs],
        "src_urls": {"ham_A8Q.mp4": "https://youtu.be/A8Q-vnrpOr4 (제철건강, 1080p)", "src_l20qnFWsxzQ.mp4": "Dove 공식 한국 l20qnFWsxzQ 1080p",
                     "src_cSzFp63NmwY.mp4": "Dove PH cSzFp63NmwY 1080p", "src_sYdJEYWmfMg.mp4": "Dove South Africa sYdJEYWmfMg 1080p",
                     "src_uPJjF0q2gIY.mp4": "soapy asmr uPJjF0q2gIY 1080p(0~240초)", "src_c1IvDrByGrc.mp4": "돋보기김선생 c1IvDrByGrc 1080p",
                     "src_spFXZnqXIhI.mp4": "해강TV spFXZnqXIhI 1080p", "src_ZcsmCplywSE.mp4": "Dove US ZcsmCplywSE 1080p", "src_MUzRiCp23JM.mp4": "Dove UK MUzRiCp23JM 1080p"},
        "audio_rule": "B 재료 원음 전부 끔(-an). A 원음 = 함익병 말만(MC '네' 두 곳 잘라 냄).",
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
