# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 1호 한고은 채소통 — 재미썸홈판 계획(대본·재료·시트). 관제 097, 2026-10-17.

흐름(사장님 확정): 연예인이 좋다고 함(원음) → "저 영상 보고 나도 샀다"(다리) → 써 보니 좋다 ①② → 사고 싶게 마무리.
앞 = 얜샷템 틀(channel/mantem/frame_얜샷템.json, 1080×1080 칸) · 다리부터 = 재미썸홈(숏템 t11, 1080×1407 칸, body_all).
화면 크롭 = [x, y, w, h] 원본 픽셀. 원본 아래 자막·꾸밈 글은 크롭 밖(시트로 눈 확인).
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/재미썸홈판/make_plan.py
"""
import io
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
W = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/재미썸홈판")
HG = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/src/hge_LcQv9yOh3Wc.mp4")
MEME = Path("C:/숏템_칼카피/packs/meme/meme_pack")
PRESET = json.loads((ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
CPS = PRESET["measured"]["speech_rate"]["chars_per_s_total"]   # 8.8
WIN_F, WIN_B = (1080, 1080), (1080, 1407)
HG_URL = "https://www.youtube.com/watch?v=LcQv9yOh3Wc"
BC_URL = "https://display.cjonstyle.com/p/item/2067440818"

# ── 앞(얜샷템 틀) ─────────────────────────────────────────────
FRONT_TITLE = "두 달 신선한 한고은\n채소통 직접 써봄"   # 1차 '한고은이 두 달 신선하다는'(13자)는 칸 밖으로 넘침(1초 시트)
FRONT_LABEL = "출처 : 고은언니 한고은"
FRONT_TTS = {"text": "한고은이 1킬로씩 사도 안 버린다는 보관통의 정체.", "tts": "한고은이 일 킬로씩 사도 안 버린다는 보관통의 정체.",
             "caps": ["한고은이 1킬로씩 사도", "안 버린다는", "보관통의 정체"]}
# 원음(본인 말) — 자막 시각은 원음 구간 안 상대초(앞 편 근거.md §2 받아쓰기 3회·자동자막 낱말 시각)
ORIG = {
    # H 끝 783.86: 1차 783.72 는 '신선해요'의 '요'가 잘림(완성본 받아쓰기 2/2 '신선해') — 원본 쉼 783.85~783.98, 원본 컷 783.92
    "H": {"audio": [[780.62, 783.86]], "said": "정말 난 너무 놀랬어. 한 달, 두 달이 가도 너무 신선해요.",
          "caps": [(0.0, "정말 난 너무 놀랬어"), (1.33, "한 달, 두 달이 가도"), (2.43, "너무 신선해요")],
          "shots": [{"ss": 780.62, "dur": 3.10, "crop": [640, 60, 720, 720], "seen": "한고은 상반신·얼굴(말하는 입 = 같은 시각). 오른쪽 통 그림(x1400~)·아래 노란 자막(y840~) 밖"}]},
    "O5": {"audio": [[788.18, 791.55], [791.62, 793.59]], "said": "그냥 보관을 하셔서 먹고 싶을 때 씻어서 하셔도 되고. 저는 씻어서 보관해요. 귀찮으니까.",
           "caps": [(0.06, "그냥 보관을 하셔서"), (1.18, "먹고 싶을 때"), (2.22, "씻어서 하셔도 되고"), (3.54, "저는 씻어서 보관해요"), (4.62, "귀찮으니까")],
           "shots": [{"ss": 788.18, "dur": 3.37, "crop": [560, 0, 840, 840], "seen": "한고은 손이 상추 담은 통에 투명 뚜껑(초록 다이얼) 덮음. '[이거 진짜 꿀팁이야]'(y855~) 밖"},
                     {"ss": 791.55, "dur": 1.97, "crop": [710, 200, 715, 715], "seen": "손사래 치며 말하는 한고은 얼굴(입 = 같은 시각). 빨간 꾸밈 글(y92~183) 위로 잘라 뺌"}]},
}
FRONT_TTS_SHOT = {"ss": 751.10, "crop": [520, 0, 820, 820], "seen": "검은 쟁반 위 상추·로메인 더미, 한고은 손(노란 소매) — '1킬로씩 사도'. '[푸릇푸릇]'(y861~) 밖"}

# ── 뒤(재미썸홈 t11) ──────────────────────────────────────────
BODY_TITLE = "한고은 채소통 직접 사 봄"
LINES = [   # (칸, 화면·읽는 글)  — 35자 넘는 문장 없음(B17)
    # 2판(관제 097, 10-17): 제품 같은 모델 못 찾음 → 뒤는 원본 한고은 영상 안 보관통 화면만. 다른 회사(K1-0163) 사진·남의 방송 짤·남의 손 영상 0.
    #   '이거 진짜 미쳤음'(짤 자리) 뺌 · 끝 줄 '댓글로 줄줄이 묻는 중'(댓글 유도로 보임) → 바로 할 행동. TTS 는 끝 줄 1줄만 새로(make_tts --patch2).
    ("bait", "한고은이 저렇게까지 말하길래 반신반의하고 직접 사 봤는데,"),
    ("reveal", "이건 바로 물 빠지는 채반 보관통."),
    ("twist", "근데 진짜 충격적인 포인트는, 씻은 채소를 그냥 넣었는데 물이 바닥으로 쫙 빠진다는 거."),
    ("more", "그래서 잎이 하나도 안 무르고 멀쩡함."),
    ("more", "심지어 일주일 지나도 아삭해서 채소를 처음으로 안 버림."),
    ("land", "버리는 채소값이면 이미 본전이라,"),
    ("land", "냉장고 칸 높이만 재 보고, 바로 들여놓는 거 추천함."),
]
HGS = "hg"     # 소스 별명
# (자막 조각, 소스, 시작초, 크롭[x,y,w,h], 화면에 보이는 것)  "+" = 앞 컷 이어감. 소스 d* = 원본을 이어 붙이거나 늦춘 조각(../재료/make_derived.py)
CUTS = [
    ("한고은이 저렇게까지", HGS, 769.45, [660, 0, 599, 780], "[한고은] 두 손 펴며 말하는 한고은 — '한고은이 말하길래'(주황 자막 y820~ 밖)"),
    ("말하길래", "+", 0, None, ""),
    ("반신반의하고", "dA", 0.0, [440, 0, 700, 912], "[원본 보관통] 빈 스텐 겉통 근접(거의 정지 샷 3배 늦춤) — 아래 자막 y920~ 밖"),
    ("직접 사 봤는데", "+", 0, None, ""),
    ("이건 바로", "dB", 0.0, [560, 0, 700, 912], "[원본 보관통] 구멍 뚫린 채반을 기울여 보여 주는 손(3배 늦춤·움직임 보간) — 아래 자막 y920~ 밖"),
    ("물 빠지는 채반 보관통", "+", 0, None, ""),
    ("근데 진짜", HGS, 798.30, [700, 0, 828, 1080], "[원본 손] 싱크 앞에서 상추 잎을 손으로 씻음(노란 소매) — 글자 없음"),
    ("충격적인 포인트는", "+", 0, None, ""),
    ("씻은 채소를", "+", 0, None, ""),
    ("그냥 넣었는데", "+", 0, None, ""),
    ("물이 바닥으로", "dGH", 0.0, [560, 0, 660, 860], "[원본 보관통] 수돗물 아래 채반 → 채반을 들자 구멍으로 물이 빠짐 — 주황 자막 y870~ 밖"),
    ("쫙 빠진다는 거", "+", 0, None, ""),
    ("그래서 잎이 하나도", "dI", 0.0, [560, 370, 545, 710], "[원본 보관통] 겉통에 얹은 채반 속 윤기 나는 상추(1.3배 늦춤) — 빨간 꾸밈 글 y≤360 밖"),
    ("안 무르고 멀쩡함", "+", 0, None, ""),
    ("심지어 일주일 지나도", HGS, 758.25, [760, 0, 640, 834], "[원본 손] 씻어 둔 싱싱한 상추 밑동을 두 손으로 들어 보임 — '(이미 깔끔한 밑동)' y870~ 밖"),
    ("아삭해서", "+", 0, None, ""),
    ("채소를 처음으로 안 버림", HGS, 937.00, [620, 0, 660, 860], "[원본] 채소·토마토·파프리카 샐러드 볼(손 없음) — 분홍 '먹음직스럽죠' y880~ 밖"),
    ("버리는 채소값이면", HGS, 763.25, [620, 0, 637, 830], "[원본] 넉넉히 산 상추·로메인 더미 근접 — '[궁금할 수 있어]' y860~ 밖"),
    ("이미 본전이라", "+", 0, None, ""),
    ("냉장고 칸 높이만", "dFR", 0.0, [600, 0, 637, 830], "[원본] 냉장고 문 안 → 채소 봉지를 꺼내 듦(1.65배 늦춤, 뒷머리·얼굴 샷 빼고) — 손글씨 자막 y880~ 밖"),
    ("재 보고,", "+", 0, None, ""),
    ("바로 들여놓는 거 추천함", "+", 0, None, ""),
]
# 같은 꼴 상품 사진(벨라쿠진 K1-0163 CJ 상세) — 상품 각인(bella cuisine SUS304 4000ml)은 흐림 처리할 상자(1000px 기준)
IMG = {"L": {"file": "bc_L.jpg", "blur": [[320, 315, 425, 370], [655, 720, 740, 775]]},
       "L8": {"file": "bc_L8.jpg", "blur": [[320, 620, 430, 695]]},
       "L2": {"file": "bc_L2.jpg", "blur": [[575, 395, 680, 440], [575, 700, 680, 742]]},
       "L9": {"file": "bc_L9.jpg", "blur": [[360, 465, 465, 520], [355, 710, 470, 762]]}}
SRCS = {HGS: HG, "mly": W / "src/src_MlYgolhRuzc.mp4", "jct": W / "src/src_j-ctyCKjM9Q.mp4",
        "dA": W / "src/d_A.mp4", "dB": W / "src/d_B.mp4", "dGH": W / "src/d_GH.mp4", "dI": W / "src/d_I.mp4", "dFR": W / "src/d_FR.mp4"}
SRC_INFO = {HGS: ("고은언니 한고은 LcQv9yOh3Wc(2026-03-26) — 그 제품 실물", HG_URL),
            "mly": ("엄지척 집밥 MlYgolhRuzc '시든 상추 살리는 비법' — 유사(상추)", "https://www.youtube.com/watch?v=MlYgolhRuzc"),
            "jct": ("StopWaste j-ctyCKjM9Q 'Reviving Wilted Greens' — 유사(샐러드 그릇)", "https://www.youtube.com/watch?v=j-ctyCKjM9Q"),
            "d": ("원본 LcQv9yOh3Wc 를 이어 붙이거나 늦춘 조각 — ../재료/make_derived.py DERIVED", HG_URL),
            "meme": ("숏템 짤 팩", "C:/숏템_칼카피/packs/meme/meme_pack")}


def nchar(s):
    return len(re.findall(r"[가-힣A-Za-z0-9]", s))


def path_of(src):
    if src.startswith("meme:"):
        return MEME / f"{src[5:]}.mp4"
    if src.startswith("img:"):
        return W / "src" / IMG[src[4:]]["file"]
    return SRCS[src]


def kind_of(src):
    return "짤" if src.startswith("meme:") else "제품사진(같은꼴)" if src.startswith("img:") else "유사" if src in ("mly", "jct") else "제품(원본·조각)" if src.startswith("d") else "제품(원본)"


def probe(p):
    if str(p).endswith(".jpg"):
        w, h = Image.open(p).size
        return w, h, 999.0
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(p)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    j = json.loads(o)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def meme_crop(w, h, win):
    """짤: 가운데에서 칸 비율로 최대 크롭."""
    r = win[0] / win[1]
    if w / h > r:
        cw = int(h * r) // 2 * 2
        return [(w - cw) // 2, 0, cw, h]
    ch = int(w / r) // 2 * 2
    return [0, (h - ch) // 2, w, ch]


def still_img(name):
    """상품 사진 + 각인 흐림 → PIL 이미지(재료 파일)."""
    im = Image.open(W / "src" / IMG[name]["file"]).convert("RGB")
    for b in IMG[name]["blur"]:
        reg = im.crop(tuple(b)).filter(ImageFilter.GaussianBlur(9))
        im.paste(reg, (b[0], b[1]))
    return im


def grab(src, t, crop, size):
    p = path_of(src)
    if src.startswith("img:"):
        im = still_img(src[4:])
        x, y, w, h = crop
        return im.crop((x, y, x + w, y + h)).resize(size)
    x, y, w, h = crop
    png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1", "-vf", f"crop={w}:{h}:{x}:{y},scale={size[0]}:{size[1]}",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return Image.open(io.BytesIO(png)).convert("RGB")


def back_rows():
    whole = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(s for _, s in LINES)))
    pieces = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(c[0] for c in CUTS)))
    assert whole == pieces, "자막 조각이 대사와 다르다"
    rows, prev, t = [], None, 0.0
    for i, (cap, src, ss, crop, seen) in enumerate(CUTS):
        d = round(nchar(cap) / CPS, 2)
        cont = src == "+"
        if cont:
            src, crop, ss, seen = prev["src"], prev["crop"], prev["src_t1"], "(이어감)"
        w, h, sd = probe(path_of(src))
        if crop is None:
            crop = meme_crop(w, h, WIN_B)
        rows.append({"i": i + 1, "t0": round(t, 2), "dur": d, "caption": cap, "caption_chars": len(cap), "src": src, "kind": kind_of(src),
                     "src_t0": ss, "src_t1": round(ss + d, 2), "res": f"{w}x{h}", "crop": crop, "zoom": round(WIN_B[1] / crop[3], 2), "seen": seen, "cont": cont})
        prev = rows[-1]
        t += d
    return rows, round(t, 2), nchar(whole)


def main():
    rows, total_b, chars_b = back_rows()
    est_tts = round(nchar(FRONT_TTS["text"]) / CPS, 2)
    front_len = round(3.10 + 0.10 + est_tts + 0.10 + 5.34, 2)
    (HERE / "plan").mkdir(exist_ok=True)
    (HERE / "대본.json").write_text(json.dumps({
        "channel": "얜샷템 하이브리드 → 재미썸홈판", "flow": "원음(연예인 좋다) → 다리(나도 샀다) → 좋다①② → 사고 싶게(댓글 유도 없음)",
        "front": {"frame": "channel/mantem/frame_얜샷템.json", "title": FRONT_TITLE, "label": FRONT_LABEL,
                  "order": ["원음 H", "TTS 한마디", "원음 O5"], "orig": {k: {"audio": v["audio"], "said": v["said"], "caps": v["caps"]} for k, v in ORIG.items()},
                  "tts": FRONT_TTS, "est_sec": front_len},
        "back": {"frame": "숏템 t11(재미썸홈, frameRule body_all)", "bodyTitle": BODY_TITLE,
                 "spine": [{"slot": k, "line": s, "tts": s, "chars": nchar(s)} for k, s in LINES], "chars": chars_b, "est_sec": total_b, "cps": CPS,
                 "hype": {"①센 시작": "1킬로씩 사도 안 버린다는 … 정체", "②반신반의→직접": "반신반의하고 직접 사 봤는데", "③진짜 핵심": "근데 진짜 충격적인 포인트는",
                          "④심지어": "심지어 일주일 지나도", "⑤마무리": "버리는 채소값이면 이미 본전 · 냉장고 칸 재 보고 바로 들여놓기"},
                 "pieces": [{k: r[k] for k in ("i", "t0", "dur", "caption", "caption_chars")} for r in rows]},
        "voice": "타입캐스트 필재 tc_68257f68bc6e3c161ab5078d — 1판 앞 한마디+뒤 나레 1회 합성 · 2판 끝 줄 1줄만 새로 1회(make_tts --patch2)",
        "est_total": round(front_len + total_b + 0.5, 2),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    cnt = {}
    for r in rows:
        cnt[r["kind"]] = cnt.get(r["kind"], 0) + 1
    (HERE / "재료.json").write_text(json.dumps({
        "sources": {k: {"what": v[0], "url": v[1]} for k, v in SRC_INFO.items()},
        "front": {"tts_shot": FRONT_TTS_SHOT, "orig": {k: v["shots"] for k, v in ORIG.items()}},
        "back_mix": cnt, "back": rows,
        "img_blur": IMG,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 계획 시트: 앞 4컷(정사각) + 뒤 컷(세로) 2프레임씩
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    fr = []
    for k, o in ORIG.items():
        for s in o["shots"]:
            fr.append((f"앞 원음{k} {s['ss']}~{round(s['ss'] + s['dur'], 2)}", HGS, s["ss"], s["dur"], s["crop"], s["seen"], (200, 200)))
    fr.insert(1, ("앞 TTS 한마디 751.10~", HGS, 751.10, 2.3, FRONT_TTS_SHOT["crop"], FRONT_TTS_SHOT["seen"], (200, 200)))
    groups = []
    for r in rows:
        if r["cont"]:
            groups[-1]["caps"].append(r["caption"]); groups[-1]["dur"] = round(groups[-1]["dur"] + r["dur"], 2)
        else:
            groups.append({"src": r["src"], "ss": r["src_t0"], "dur": r["dur"], "crop": r["crop"], "seen": r["seen"], "caps": [r["caption"]], "kind": r["kind"], "zoom": r["zoom"]})
    COLW, ROWH, PER, head = 2 * 200 + 260, 261 + 10, 3, 80
    allc = fr + [(f"뒤 {gi + 1} [{g['kind']}] {g['src'][:14]} {g['ss']}~{round(g['ss'] + g['dur'], 2)} ×{g['zoom']}", g["src"], g["ss"], g["dur"], g["crop"],
                  " / ".join(g["caps"]) + " ← " + g["seen"], (200, 261)) for gi, g in enumerate(groups)]
    nrow = (len(allc) + PER - 1) // PER
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * nrow), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), f"얜샷템 하이브리드 한고은 채소통 — 재미썸홈판 계획(TTS 전) · 앞 {front_len}초(얜샷템) + 뒤 {total_b}초(재미썸홈 t11) · 뒤 컷 {len(groups)} · {cnt}", fill="black", font=font)
    d.text((10, 40), "프레임 2장 = 컷 시작+0.1초 · 끝−0.1초, 칸 비율 크롭 그대로(앞 1080×1080 · 뒤 1080×1407). 상품 사진 각인 흐림 처리", fill="#444", font=small)
    for k, (lab, src, ss, dur, crop, seen, size) in enumerate(allc):
        x0, y0 = (k % PER) * COLW, head + (k // PER) * ROWH
        for j, tt in enumerate((ss + 0.1, ss + max(0.15, dur - 0.1))):
            sheet.paste(grab(src, tt, crop, size), (x0 + j * 200, y0))
        tx = x0 + 405
        words = lab + " · " + seen
        for li in range(0, min(len(words), 15 * 13), 15):
            d.text((tx, y0 + 2 + li // 15 * 19), words[li:li + 15], fill="black" if li == 0 else "#333", font=small)
    sheet.save(HERE / "plan/계획_시트.jpg", quality=85)
    print("front", front_len, "back", total_b, "chars", chars_b, "groups", len(groups), cnt, "max cap", max(r["caption_chars"] for r in rows),
          "zoom max", max(g["zoom"] for g in groups))


if __name__ == "__main__":
    main()
