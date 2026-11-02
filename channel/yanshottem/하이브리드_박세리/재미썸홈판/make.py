# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 3호 박세리 라프레리 스킨 — 재미썸홈판 (관제 097, 2026-10-17). 함익병 재미썸홈판 make.py 를 복사해 상수만 바꿨다. 엔진 코드는 안 고친다(부르기만).

    PYTHONUTF8=1 py make.py plan      # 대본.json·재료.json·plan/계획_시트.jpg (TTS 전)
    PYTHONUTF8=1 py make.py tts       # 필재 Typecast 1회(narr_full.mp3 있으면 안 부름)
    PYTHONUTF8=1 py make.py render    # A(얜샷템 틀, 원음 하이라이트+TTS 한마디) + B(재미썸홈 t11 틀) → render/final.mp4 → 바탕화면

흐름: [A 0~약 10초] 박세리 원음 O1a·O1b·O3(박세리의 속사정 WHzwVWvEvQ8) → 필재 TTS 한마디(F1) — 얜샷템 틀(channel/mantem/frame_얜샷템.json, '출처 : 박세리의 속사정')
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

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_박세리/재미썸홈판")
SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_박세리/src")   # 제품 영상 lp/ · 박세리 원본은 절대 경로
R = W / "render"
DESK = Path.home() / "Desktop" / "칼카피영상" / "얜샷템" / "하이브리드" / "칼카피_얜샷템_박세리라프레리_재미썸홈판.mp4"
HAM = "C:/숏템_칼카피/yanshottem/박세리_면세점/src/seri_WHzwVWvEvQ8.mp4"   # 박세리의 속사정 WHzwVWvEvQ8 1080p
VOICE = "tc_68257f68bc6e3c161ab5078d"      # 필재
TC_TEMPO = 1.25                            # voice_presets 필재 1.25(숏템 그대로) — 나머지는 atempo(≤1.27)
CPS = 8.8                                  # 재미썸홈 프리셋 measured.speech_rate
FPS = 30
FRAME_A = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_B = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
TITLE_A = "박세리가 면세점 갈 때마다\n6병씩 사는 스킨"
LABEL_A = "출처 : 박세리의 속사정"
BODY_TITLE = "박세리 따라 사 본 스킨"
WIN_A = 1080                               # 얜샷템 영상 칸 1080×1080
WIN_B = (1080, 1407)                       # t11 영상 칸
VOICE_AF = "highpass=f=90,dynaudnorm=f=150:g=7:p=0.9:m=12"   # 원음 끝 '제일 좋은 거 같아'가 −24~−39dB 로 작아 고르게(조사.md §3, 잇썸홈판과 같은 처리 — 완성본 받아쓰기 4/4)
BGM_A, BGM_A_DB, DUCK_DB = "sweets", -27.0, -10.0   # 얜샷템(만템 8/8 BGM) — A 구간만, 원음 밑 덕킹
TARGET_LUFS = -14.0                        # 얜샷템 −16 / 재미썸홈 −13.4 사이(한 파일 한 크기 — 나레 크기를 두 틀에서 같게)

# ── 원음(박세리 본인 말) — 조사.md §3 받아쓰기(원본·완성본)로 고른 구간 ──
ORIG = [("O1a", 130.86, 134.36), ("O1b", 134.82, 137.10)]   # O3 '쟁여 놓고 쓰거든'(143.90~144.90)은 잇썸홈판엔 넣었으나 이 편에선 뺌 — 오늘 쓸 수 있는 받아쓰기 모델(2.5-flash)이 원본 단독도 '댕겨와'로 들어 B17 확인 불가
# 원음 자막(흰) — (원본 초, 글) 원본 자동자막 어절 시각(130.96 꼭·132.12 여섯·133.60 기본·134.76 또·136.12 스킨·136.56 제일·143.92 쟁여)
ORIG_CAPS = [(130.86, "꼭 나갈 때마다"), (131.95, "한 여섯 개씩"), (133.55, "기본 사고"),
             (134.82, "또 틈만 나면 사는 거야"), (136.10, "스킨 중에"), (136.55, "제일 좋은 거 같아")]
# A 화면: (원본 시작, 크롭 [x,y,w,h]) — 아래 흰 편집 자막(y≥900)·'(스킨 과소비형)'(y 860~980) 밖. 이음매마다 크기를 바꿔 점프컷을 가린다
A_SHOTS = [(130.86, [560, 0, 850, 850]), (134.82, [620, 60, 720, 720])]
GAP_O_F1 = 0.12                            # 원음 끝 → TTS 한마디
F1_SHOT = ("lp/RZnIG6hNFkA.mp4", 630.45, [150, 100, 740, 740])   # 뚜껑 연 젖빛 병(분홍 액·병 글자 CELLULAR SOFTENING AND BALANCING LOTION·아래 la prairie) — 오른쪽 리뷰어 얼굴(x≥900) 밖
F1_SHOT2 = ("lp/NsQAvi8zxkk.mp4", 304.62, [180, 150, 680, 680])  # '바로 이 라프레리' = 다른 리뷰어가 같은 병을 들어 보임(은 뚜껑·la prairie 글자)

LINES = [   # (칸, 화면 글 text, 읽는 글 tts) — 0 = A 끝 한마디(F1), 1~ = B
    ("f1", "박세리가 갈 때마다 여섯 병씩 산다는 스킨, 바로 이 라프레리.", "박세리가 갈 때마다 여섯 병씩 산다는 스킨, 바로 이 라프레리."),
    ("bait", "저 영상 보고 나도 면세점에서 바로 집어 왔는데,", "저 영상 보고 나도 면세점에서 바로 집어 왔는데,"),
    ("limit", "이게 말도 안 되는 게 화장솜으로 한 번 닦았을 뿐인데 피부가 진짜 보들보들해지더라.", "이게 말도 안 되는 게 화장솜으로 한 번 닦았을 뿐인데 피부가 진짜 보들보들해지더라."),
    ("more", "심지어 이게 끈적임 하나 없이 스며들어서 다음 크림까지 쫙 먹어.", "심지어 이게 끈적임 하나 없이 스며들어서 다음 크림까지 쫙 먹어."),
    ("twist", "근데 진짜 충격적인 포인트는 제작진이 한 방울만 발라 보자니까,", "근데 진짜 충격적인 포인트는 제작진이 한 방울만 발라 보자니까,"),
    ("more", "박세리가 웃으면서 수납장 맨 안쪽에 숨겨 버렸대.", "박세리가 웃으면서 수납장 맨 안쪽에 숨겨 버렸대."),
    ("more", "댓글에도 이 스킨 어디 거냐는 질문이 계속 달렸던데,", "댓글에도 이 스킨 어디 거냐는 질문이 계속 달렸던데,"),
    ("land", "면세점 갈 일 있으면 장바구니에 이것부터 담아 둬.", "면세점 갈 일 있으면 장바구니에 이것부터 담아 둬."),
]
SERI = HAM
PIECES = [
    # F1 (A 틀, 컷은 F1_SHOT·F1_SHOT2)
    ("박세리가 갈 때마다", None, None, None, "제품", "(A) 뚜껑 연 분홍 토너 병(병 글자)"),
    ("여섯 병씩 산다는 스킨", None, None, None, "제품", "(A) 〃"),
    ("바로 이 라프레리", None, None, None, "제품", "(A) 같은 병을 든 다른 리뷰어(la prairie 글자)"),
    # L1 다리 — 산 제품 상자
    ("저 영상 보고 나도", "lp/NCDOo6quRg8.mp4", 1771.90, [260, 0, 1080], "제품", "매장에서 사 온 이 토너의 은색 상자를 들어 보임(la prairie)"),
    ("면세점에서", "+", None, None, "제품", "(이어감)"),
    ("바로 집어 왔는데", "+", None, None, "제품", "(이어감)"),
    # L2 ① 화장솜 → 보들보들
    ("이게 말도 안 되는 게", "lp/RZnIG6hNFkA.mp4", 645.42, [420, 0, 1080], "제품", "토너 적신 화장솜을 들어 보임(원본 컷 646.80 앞)"),
    ("화장솜으로 한 번", "lp/RZnIG6hNFkA.mp4", 647.30, [380, 0, 1080], "제품", "화장솜으로 이마를 닦아 냄"),
    ("닦았을 뿐인데", "+", None, None, "제품", "(이어감)"),
    ("피부가 진짜", "lp/NsQAvi8zxkk.mp4", 320.30, [450, 0, 1080], "제품", "다른 리뷰어가 같은 토너 화장솜으로 볼을 닦음"),
    ("보들보들해지더라", "lp/NsQAvi8zxkk.mp4", 328.90, [400, 0, 1080], "제품", "화장솜으로 볼을 꾹꾹 누르며 닦음"),
    # L3 ② 안 끈적 → 크림까지
    ("심지어 이게", "lp/Wk-Z_e_K2nM.mp4", 310.85, [650, 0, 880], "제품", "손바닥에 펴 바르는 묽은 토너(제형) — 가격 글자(x<480)·자막(y≥925) 밖"),
    ("끈적임 하나 없이", "+", None, None, "제품", "(이어감)"),
    ("스며들어서", "+", None, None, "제품", "(이어감)"),
    ("다음 크림까지", "lp/Wk-Z_e_K2nM.mp4", 315.40, [700, 0, 900], "제품", "토너 바른 뒤 윤기 도는 얼굴을 손끝으로 만짐"),
    ("쫙 먹어", "+", None, None, "제품", "(이어감)"),
    # L4 반전 — 제작진 부탁
    ("근데 진짜", "lp/RZnIG6hNFkA.mp4", 639.40, [380, 0, 1080], "제품", "뚜껑 연 분홍 토너 병을 기울여 보임(원본 컷 641.29 앞)"),
    ("충격적인 포인트는", "+", None, None, "제품", "(이어감)"),
    ("제작진이 한 방울만", SERI, 137.25, [620, 0, 880], "원본", "병 든 채 제작진 말을 듣는 박세리(원본 컷 137.04 뒤) — 아래 노랑 제작진 자막(y≥900) 밖"),
    ("발라 보자니까", "+", None, None, "원본", "(이어감)"),
    # L5 박세리가 숨김
    ("박세리가 웃으면서", SERI, 138.78, [520, 0, 880], "원본", "병 든 채 웃는 박세리 — 오른쪽 '(싫은뎅?)'(x≥1200) 밖"),
    ("수납장 맨 안쪽에", SERI, 142.20, [640, 0, 860], "원본", "병을 수납장 안쪽 칸에 넣는 박세리 손 — 아래 노랑 자막(y≥900)·오른쪽 제작진(x≥1700) 밖"),
    ("숨겨 버렸대", SERI, 123.98, [520, 0, 860], "원본", "박세리 수납장 칸칸이 쌓인 화장품('보물창고') — 아래 노랑 자막(y≥870) 밖. 142.2 컷을 이어 가면 143.51 뒤 흐린 뒷머리가 나와(1판 시트) 바꿈"),
    # L6 남들도 궁금
    ("댓글에도 이 스킨", "lp/Wk-Z_e_K2nM.mp4", 319.60, [700, 0, 900], "제품", "이 토너 바른 뒤 촉촉한 얼굴(앞 컷 316.8 끝에서 2.8초 뒤 — 다른 각도로 고개 돌림)"),
    ("어디 거냐는 질문이", "+", None, None, "제품", "(이어감)"),
    ("계속 달렸던데", "+", None, None, "제품", "(이어감)"),
    # L7 마무리(끝 컷 ≥1.5초)
    ("면세점 갈 일 있으면", "lp/RZnIG6hNFkA.mp4", 624.45, [130, 0, 1080], "제품", "은 뚜껑 젖빛 병(분홍 액·병 글자)"),
    ("장바구니에 이것부터", "lp/Wk-Z_e_K2nM.mp4", 277.10, [200, 60, 1000], "제품", "분홍 토너 병을 든 손(끝 컷) — 오른쪽 제품 딱지(x≥1440)·281초부터 뜨는 가격 글자 전"),
    ("담아 둬", "+", None, None, "제품", "(이어감)"),
]
SFX_ROLES = [l[0] for l in LINES[1:]]
TEMPO, TEMPO_LAST = 1.24, 0.92   # 나레 atempo(필재 1회 원속 7.10자/초 → 8.80 = 재미썸홈 measured) · 끝 문장만 0.92(TTS가 끝 문장을 9.63자/초로 빨리 읽어 → 8.86, 늘림 −8% ≤ B17 10%·B15 끝 줄 ≤ 평균)
# 문장부호 쉼 자리(atempo 뒤·쉼 모양 전 narr_pre.wav 초, silencedetect −40dB/0.1 실측) — 스킨, | 라프레리. | 왔는데, | 보들보들해지더라. | 먹어. | 보자니까, | 버렸대. | 달렸던데,
#   줄 글자 수 ÷ 8.8자/초 누적과 맞춘 뒤 2초 토막 받아쓰기(gemini-2.5-flash)로 줄 머리 대조. 낱말 안 쉼(6.19 '안 되는 게|')은 건드리지 않는다
PUNCT_AT = [(",", 1.66), (".", 2.80), (",", 4.94), (".", 9.31), (".", 11.94), (",", 14.60), (".", 16.93), (",", 19.19)]
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
                     "caps": " / ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b), "seen": "박세리 본인(말하는 사람) 단독 화면", "kind": "원음"})
        o_t += b - a
    f1d = sum(nchar(p[0]) for p in PIECES[:3]) / CPS
    f1a = sum(nchar(p[0]) for p in PIECES[:2]) / CPS + GAP_O_F1
    rows.append({"label": f"A F1 TTS {o_t:.2f}+{f1a:.2f}", "src": F1_SHOT[0], "a": F1_SHOT[1], "b": F1_SHOT[1] + f1a, "crop": F1_SHOT[2],
                 "size": (300, 300), "caps": " / ".join(p[0] for p in PIECES[:2]), "seen": "뚜껑 연 분홍 토너 병(제품만)", "kind": "제품"})
    rows.append({"label": f"A F1 TTS {o_t + f1a:.2f}+{f1d + GAP_O_F1 - f1a:.2f}", "src": F1_SHOT2[0], "a": F1_SHOT2[1], "b": F1_SHOT2[1] + f1d + GAP_O_F1 - f1a,
                 "crop": F1_SHOT2[2], "size": (300, 300), "caps": PIECES[2][0], "seen": "같은 병을 든 다른 리뷰어(제품)", "kind": "제품"})
    for g in gs:
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g['kind']}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": g["crop"], "size": (230, 300), "caps": " / ".join(PIECES[k][0] for k in g["pieces"]), "seen": g["seen"], "kind": g["kind"]})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 3 * 300 + 330, 310, 2
    head = 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 박세리 라프레리 — 재미썸홈판 계획 시트(TTS 전) · 예상 {times[-1][1]:.1f}초 · A 원음 {sum(b - a for _, a, b in ORIG):.2f}초 + TTS · B 컷 {len(gs)}",
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
        "channel": "얜샷템 하이브리드(재미썸홈판)", "topic": "박세리가 면세점 갈 때마다 6병씩 사는 라프레리 셀루라 소프트닝 앤 밸런싱 로션 — 원음 하이라이트 → 나도 샀다 → 써 보니 ①② → 제작진에게도 숨김 → 남들도 궁금 → 마무리",
        "frames": {"A": str(FRAME_A.relative_to(ROOT)), "A_title": TITLE_A, "A_label": LABEL_A, "B": "channel/evenshopping/preset/숏템템플릿 (t11, frameRule body_all)", "B_bodyTitle": BODY_TITLE},
        "orig_audio": [{"id": n, "src": "A8Q-vnrpOr4", "span": [a, b], "said": " ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b)} for n, a, b in ORIG],
        "lines": [{"slot": s, "text": t, "tts": tt, "chars": nchar(tt)} for s, t, tt in LINES],
        "tts_one_call": " ".join(l[2] for l in LINES), "voice": f"Typecast 필재 {VOICE} tempo {TC_TEMPO} 1회",
        "pieces": [{"i": k + 1, "line": pl[k], "caption": p[0], "t": list(times[k]), "est": est} for k, p in enumerate(PIECES)],
        "hype": {"①센 시작": "원음 '꼭 나갈 때마다 한 여섯 개씩 기본 사고' + '저 영상 보고 나도 면세점에서 바로 집어 왔는데'", "②권위": "박세리 본인 말(원음)",
                 "③진짜 핵심 반전": "근데 진짜 충격적인 포인트는(제작진에게도 안 발라 줌)", "④심지어": "심지어 이게", "⑤남들도": "댓글에도 이 스킨 어디 거냐는 질문이 계속"},

        **(extra or {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps({
        "A": [{"id": n, "src": HAM, "ss": a, "dur": round(b - a, 3), "crop_xywh": cr, "zoom": round(WIN_A / cr[2], 2), "audio": "원음(본인 말)"}
              for (n, a, b), (_, cr) in zip(ORIG, A_SHOTS)] + [{"id": "F1", "src": F1_SHOT[0], "ss": F1_SHOT[1], "crop_xywh": F1_SHOT[2],
                                                                 "zoom": round(WIN_A / F1_SHOT[2][2], 2), "audio": "무음(나레)"},
                                                                {"id": "F1b", "src": F1_SHOT2[0], "ss": F1_SHOT2[1], "crop_xywh": F1_SHOT2[2],
                                                                 "zoom": round(WIN_A / F1_SHOT2[2][2], 2), "audio": "무음(나레)"}],
        "B": [{k: v for k, v in g.items()} for g in gs],
        "src_urls": {HAM: "https://youtu.be/WHzwVWvEvQ8 (박세리의 속사정, 1080p)",
                     "lp/RZnIG6hNFkA.mp4": "Everyday Luxe Beauty RZnIG6hNFkA 1080p — 10:20~ 'next is the cellular softening and balancing lotion this is my toner'",
                     "lp/NsQAvi8zxkk.mp4": "Everyday Luxe Beauty NsQAvi8zxkk 1080p — 5:04~ 'this is the cellular softening and balancing lotion'",
                     "lp/Wk-Z_e_K2nM.mp4": "프롬베이지 Wk-Z_e_K2nM 1080p — 4:33~ '리치 언니가 여섯 개를 쟁여 놓고 사용한다는 바로 그 토너 라프레리 셀룰러 소프트닝 앤 밸런싱 로션'",
                     "lp/NCDOo6quRg8.mp4": "Everyday Luxe Beauty NCDOo6quRg8 1080p — 29:25~ 'i also picked up a toner this is their cellular softening and balancing lotion'"},
        "audio_rule": "B 재료 원음 전부 끔(-an). A 원음 = 박세리 말만(O1a·O1b·O3, 제작진 말 137.2~ 앞에서 끊음).",
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
