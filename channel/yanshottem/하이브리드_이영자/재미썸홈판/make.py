# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 이영자 고렌샤크(GallonShark) 미끄럼방지 요가 신발 — 재미썸홈판 (2026-10-17). 엔진 코드는 안 고친다(부르기만).
정본 = 하이브리드_최은경/재미썸홈판/make.py — 소재 상수(원음·화면·대사·조각)만 바꿈.

    PYTHONUTF8=1 py make.py plan      # 대본.json·재료.json·plan/계획_시트.jpg (TTS 전)
    PYTHONUTF8=1 py make.py tts       # 필재 Typecast 1회(narr_full.mp3 있으면 안 부름)
    PYTHONUTF8=1 py make.py render    # A(얜샷템 틀, 원음 하이라이트+TTS 한마디) + B(재미썸홈 t11 틀) → render/final.mp4 → 바탕화면

흐름: [A 약 8초] 이영자 원음 O1·O2(이영자 TV BHuue4ga-w0) → 필재 TTS 한마디(F1) — 얜샷템 틀('출처 : 이영자 TV')
      [B] 다리 "저 영상 보고 나도…" → 써 보니 ①② → 진짜 포인트(상표) → 남들도(피디) → 마무리 — 재미썸홈 t11 틀
소리: TTS 1회를 A 끝 한마디 + B 나레로 나눠 쓴다. A만 BGM(원음 밑 덕킹), B는 BGM 없음 + 숏템 효과음팩 density=low.
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

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_이영자/재미썸홈판")
SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_이영자/src")
R = W / "render"
DESK = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/하이브리드/칼카피_얜샷템_이영자고렌샤크요가신발_재미썸홈판.mp4")
HAM = "C:/숏템_칼카피/yanshottem/이영자_실내화/src/yj_BHuue4ga-w0.mp4"   # 이영자 TV BHuue4ga-w0 1080p50(AV1→h264 crf18). 이름은 정본 상수 그대로
VOICE = "tc_68257f68bc6e3c161ab5078d"      # 필재
TC_TEMPO = 1.25                            # voice_presets 필재 1.25(숏템 그대로) — 나머지는 atempo
CPS = 8.8                                  # 재미썸홈 프리셋 measured.speech_rate
FPS = 30
FRAME_A = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_B = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
TITLE_A = "이영자가 피디한테 건넨\n미끄럼방지 요가 신발"
LABEL_A = "출처 : 이영자 TV"
BODY_TITLE = "이영자 따라 산 고렌샤크 요가 신발"
WIN_A = 1080                               # 얜샷템 영상 칸 1080×1080
WIN_B = (1080, 1407)                       # t11 영상 칸
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
BGM_A, BGM_A_DB, DUCK_DB = "sweets", -27.0, -10.0
TARGET_LUFS = -14.0

# ── 원음(이영자 본인 말) — 0.04초 RMS + 받아쓰기(gemini-2.5-pro·flash, 화자 1)로 고른 구간(근거.md) ──
#   O1 117.82~119.42 "PD님 걸어 다니기 힘들죠?" (원본 컷 117.80 뒤)
#   O2 123.45~126.34 "요가할 때 신는 건데 이거 신고 하세요. 그럼 편하실 거예요." (126.4부터 원본 화면에 남의 손 → 그 앞에서 끊음)
ORIG = [("O1", 117.82, 119.42), ("O2", 123.45, 126.34)]
ORIG_CAPS = [(117.82, "PD님 걸어 다니기"), (118.60, "힘들죠?"),
             (123.45, "요가할 때 신는 건데"), (124.38, "이거 신고 하세요"), (125.30, "그럼 편하실 거예요")]
# A 화면: 원음 토막마다 [(원본 시작, 크롭 [x,y,w,h], 길이 또는 None=끝까지)] — 원본 편집 자막(y≥840) 밖, 화면 인물 = 이영자 본인만
A_SHOTS = [[(117.82, [700, 0, 820, 820], None)],
           [(123.45, [450, 0, 820, 820], None)]]
GAP_O_F1 = 0.12                            # 원음 끝 → TTS 한마디
F1_SHOT = ("stills/g1_logo_sq.mp4", 0.0, [0, 0, 1080, 1080])  # 쿠팡 상품 사진 g1 — GallonShark 로고 + 그레이 한 켤레 + 세 색상
F1_SHOT2 = None                            # 이영자 편: F1 은 한 컷(같은 사진 두 번 안 씀)

LINES = [   # (칸, 화면 글 text, 읽는 글 tts) — 0 = A 끝 한마디(F1), 1~ = B
    ("f1", "방송인 이영자가 피디한테 직접 꺼내 준 요가 신발, 바로 이거.", "방송인 이영자가 피디한테 직접 꺼내 준 요가 신발, 바로 이거."),   # 1차 '이영자가…'는 2.5-flash 2/2 '이용자가' → name_fix F1~F4 중 F1 '방송인 이영자가' 3/3(10-18)
    ("bait", "저 영상 보고 나도 당장 따라 샀는데,", "저 영상 보고 나도 당장 따라 샀는데,"),
    ("limit", "이게 말도 안 되는 게 바닥이 전부 오돌토돌 고무라 마루에서도 안 미끄러져.", "이게 말도 안 되는 게 바닥이 전부 오돌토돌 고무라 마루에서도 안 미끄러져."),
    ("more", "심지어 양말처럼 쏙 신기는데 세탁기에 막 돌려도 돼.", "심지어 양말처럼 쏙 신기는데 세탁기에 막 돌려도 돼."),
    ("twist", "근데 진짜 중요한 포인트는 상표야.", "근데 진짜 중요한 포인트는 상표야."),
    ("more", "비슷하게 생긴 요가 양말이 많아서 고렌샤크인지 꼭 봐야 돼.", "비슷하게 생긴 요가 양말이 많아서 고렌샤크인지 꼭 봐야 돼."),
    ("more", "피디도 신어 보고 편해서 놀랐다잖아.", "피디도 신어 보고 편해서 놀랐다잖아."),
    ("land", "실내화 사기 전에 이거 한 켤레 먼저 담아 둬.", "실내화 사기 전에 이거 한 켤레 먼저 담아 둬."),
]
# 자막 조각(≤13자) · 재료 — (조각, 소스 파일|"+", 소스 시작초, 크롭 [x,y,h](폭 = h×1080/1407), 종류, 화면에 보이는 것)
#   "+" = 앞 컷을 끊지 않고 이어감. 모든 재료 = 같은 제품(고렌샤크 미끄럼방지 요가 신발): 이영자 TV 원본 · 쿠팡/알리 상품 사진·페이지 · 같은 제품 판매 사진
PIECES = [
    ("방송인 이영자가 피디한테", None, None, None, "제품", "(A) 쿠팡 상품 사진 g1 — GallonShark 로고·그레이 한 켤레"),
    ("직접 꺼내 준 요가 신발", None, None, None, "제품", "(A) 〃"),
    ("바로 이거", None, None, None, "제품", "(A) 〃"),
    # bait
    ("저 영상 보고 나도", "stills/t8_black_t11.mp4", 0.0, [0, 0, 1407], "제품", "같은 제품 검정 한 켤레를 손에 든 판매 사진(T8M 24.0초)"),
    ("당장 따라 샀는데", "+", None, None, "제품", "(이어감)"),
    # limit ① 고무 밑창 → 안 미끄러짐
    ("이게 말도 안 되는 게", "stills/g5_black_t11.mp4", 0.0, [0, 0, 1407], "제품", "쿠팡 상품 사진 g5 — 검정을 신고 걷는 발, 바닥면"),
    ("바닥이 전부", "stills/g2_sole_t11.mp4", 0.0, [0, 0, 1407], "제품", "쿠팡 상품 사진 g2 — 밑창 테두리의 오돌토돌한 고무 알갱이 근접"),
    ("오돌토돌 고무라", "+", None, None, "제품", "(이어감)"),
    ("마루에서도", "stills/g4_gym_t11.mp4", 0.0, [0, 0, 1407], "제품", "쿠팡 상품 사진 g4 — 그레이를 신은 발이 바닥 위에"),
    ("안 미끄러져", "+", None, None, "제품", "(이어감)"),
    # more ② 양말처럼·세탁기
    ("심지어 양말처럼", "stills/g3_fold_t11.mp4", 0.0, [0, 0, 1407], "제품", "쿠팡 상품 사진 g3 — 아이보리를 손가락으로 반 접음"),
    ("쏙 신기는데", "+", None, None, "제품", "(이어감)"),
    ("세탁기에 막", "stills/lj_black_t11.mp4", 0.0, [0, 0, 1407], "제품", "같은 제품 검정 한 켤레 상품 사진(lJb 40.8초, 좌우 되돌림)"),
    ("돌려도 돼", "+", None, None, "제품", "(이어감)"),
    # twist 상표
    ("근데 진짜", "stills/t8_ivory_t11.mp4", 0.0, [0, 0, 1407], "제품", "같은 제품 아이보리 한 켤레를 손에 든 판매 사진(T8M 14.5초)"),
    ("중요한 포인트는", "+", None, None, "제품", "(이어감)"),
    ("상표야", "+", None, None, "제품", "(이어감)"),
    # more 비슷한 것 많다
    ("비슷하게 생긴", "stills/t8_grey_t11.mp4", 0.0, [0, 0, 1407], "제품", "같은 제품 그레이 한 켤레를 손에 든 판매 사진(T8M 2.5초)"),
    ("요가 양말이 많아서", "+", None, None, "제품", "(이어감)"),
    ("고렌샤크인지", "stills/ali_pink_t11.mp4", 0.0, [0, 0, 1407], "제품", "GallonShark 로고 + 핑크 한 켤레(알리 1005012379840358 대표 사진, 같은 모델)"),
    ("꼭 봐야 돼", "+", None, None, "제품", "(이어감)"),
    # more 남들도(피디)
    ("피디도 신어 보고", HAM, 129.12, [730, 20, 900], "제품", "그 신발을 신고 걸어 들어와 서는 다른 사람(피디 추정)의 다리·발 — 원본 편집 자막 '[진짜 편해서 놀랐다고 한다]'(y≥925) 밖"),
    ("편해서 놀랐다잖아", "+", None, None, "제품", "(이어감)"),
    # land(끝 컷 ≥1.5초)
    ("실내화 사기 전에", "stills/page_t11.mp4", 0.0, [0, 0, 1407], "제품", "쿠팡 상품 페이지 — 상품명 '고렌샤크 미끄럼방지 요가 신발 … Gallonshark'·가격·GallonShark 로고 사진·장바구니/바로구매(끝 컷)"),
    ("이거 한 켤레", "+", None, None, "제품", "(이어감)"),
    ("먼저 담아 둬", "+", None, None, "제품", "(이어감)"),
]
SFX_ROLES = [l[0] for l in LINES[1:]]
TEMPO, TEMPO_LAST = 1.27, 1.27   # 나레 atempo(지휘 상한 1.27) · 끝 문장 따로(TTS 뒤 실측해 정함)
# 문장부호 쉼 자리(atempo 뒤·쉼 모양 전 narr_pre.wav 초, silencedetect −40dB/0.06 실측 10-18) — 신발, | 이거. | 샀는데, | 미끄러져. | 돼. | 상표야. | 돼. | 놀랐다잖아.
#   줄 머리는 gemini-2.5-pro 토막 받아쓰기로 대조(4.4~7.05 = limit 한 줄 통째, 9.5~11.16 = twist)
PUNCT_AT = [(",", 1.96), (".", 2.58), (",", 4.28), (".", 7.09), (".", 9.29), (".", 11.28), (".", 14.21), (".", 15.36)]
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
                         "caps": " / ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b), "seen": "이영자 본인(말하는 사람) 단독 화면", "kind": "원음"})
            o_t += d_; left -= d_
    f1d = sum(nchar(p[0]) for p in PIECES[:3]) / CPS + GAP_O_F1
    rows.append({"label": f"A F1 TTS {o_t:.2f}+{f1d:.2f}", "src": F1_SHOT[0], "a": F1_SHOT[1], "b": F1_SHOT[1] + f1d, "crop": F1_SHOT[2],
                 "size": (300, 300), "caps": " / ".join(p[0] for p in PIECES[:3]), "seen": PIECES[0][5], "kind": "제품"})
    for g in gs:
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g['kind']}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": g["crop"], "size": (230, 300), "caps": " / ".join(PIECES[k][0] for k in g["pieces"]), "seen": g["seen"], "kind": g["kind"]})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 3 * 300 + 330, 310, 2
    head = 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 이영자 고렌샤크 요가 신발 — 재미썸홈판 계획 시트(TTS 전) · 예상 {times[-1][1]:.1f}초 · A 원음 {sum(b - a for _, a, b in ORIG):.2f}초 + TTS · B 컷 {len(gs)}",
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
        "channel": "얜샷템 하이브리드(재미썸홈판)", "topic": "이영자가 이사 날 피디에게 꺼내 준 고렌샤크(GallonShark) 미끄럼방지 요가 신발 — 원음 하이라이트 → 나도 샀다 → 써 보니 ①② → 진짜 포인트(상표) → 남들도(피디) → 마무리",
        "frames": {"A": str(FRAME_A.relative_to(ROOT)), "A_title": TITLE_A, "A_label": LABEL_A, "B": "channel/evenshopping/preset/숏템템플릿 (t11, frameRule body_all)", "B_bodyTitle": BODY_TITLE},
        "orig_audio": [{"id": n, "src": "BHuue4ga-w0", "span": [a, b], "said": " ".join(c for t_, c in ORIG_CAPS if a - 0.01 <= t_ < b)} for n, a, b in ORIG],
        "lines": [{"slot": s, "text": t, "tts": tt, "chars": nchar(tt)} for s, t, tt in LINES],
        "tts_one_call": " ".join(l[2] for l in LINES), "voice": f"Typecast 필재 {VOICE} tempo {TC_TEMPO} 1회",
        "pieces": [{"i": k + 1, "line": pl[k], "caption": p[0], "t": list(times[k]), "est": est} for k, p in enumerate(PIECES)],
        "hype": {"①센 시작": "원음 'PD님 걸어 다니기 힘들죠? … 요가할 때 신는 건데 이거 신고 하세요. 그럼 편하실 거예요' + '저 영상 보고 나도 당장 따라 샀는데'", "②권위": "이영자 본인 말(원음)",
                 "③진짜 핵심 반전": "근데 진짜 중요한 포인트는 상표야", "④심지어": "심지어 양말처럼 쏙 신기는데 세탁기에 막 돌려도 돼", "⑤남들도": "피디도 신어 보고 편해서 놀랐다잖아"},
        **(extra or {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps({
        "A": [{"id": n, "src": HAM, "span": [a, b], "shots": [{"ss": ss, "crop_xywh": cr, "dur": dd, "zoom": round(WIN_A / cr[2], 2)} for ss, cr, dd in shots],
               "audio": "원음(본인 말)"} for (n, a, b), shots in zip(ORIG, A_SHOTS)] + [{"id": "F1", "src": F1_SHOT[0], "ss": F1_SHOT[1], "crop_xywh": F1_SHOT[2],
                                                                 "zoom": round(WIN_A / F1_SHOT[2][2], 2), "audio": "무음(나레)"}],
        "B": [{k: v for k, v in g.items()} for g in gs],
        "src_urls": {HAM: "https://www.youtube.com/watch?v=BHuue4ga-w0 (이영자 TV, 2024-06-30, 1080p50) — 편집 자막 2:04.5 '(고렌샤크 미끄럼방지 요가 신발)'",
                     "stills/*": "쿠팡 상품 9623667803 사진 5장 + 상품 페이지(2026-10-17 조회) · 알리 1005012379840358 대표 사진 · 같은 제품 판매 사진(T8Maxl8-uP0·lJbKVjunSr8 영상 속 사진 칸) → 조사/make_stills.py 로 8초 다가가기 영상"},
        "audio_rule": "B 재료 원음 전부 끔(-an). A 원음 = 이영자 말만(O1·O2, 받아쓰기 화자 1).",
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
