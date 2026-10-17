# -*- coding: utf-8 -*-
"""샥탬스토리 6편 LARQ — 줄·컷 정본(LINES) 하나에서 재료.json · plan/계획.md · plan/계획_시트.jpg 를 만든다 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/foreignshowshow/6편_LARQ/make_plan.py          # 셋 다 다시 만듦 + 자체 점검 표 출력
판단(컷 구간·크롭)은 LINES 한 곳. 시각은 나레 7.8자/초(벤치 QMJtjJz4M6w 실측 189자/24.1초) 추정 — TTS 뒤 줄 끝에 맞춰 컷 길이만 다시 잰다.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = Path("C:/숏템_칼카피/foreignshowshow/6편_LARQ/src")
CLIP = "fuM1Vh7OgfY"
DEMO = "85Dy9RIAvmo"
CLIP_SECTIONS = [(10.0, 262.0), (360.0, 447.0), (595.0, 660.0)]   # 받은 1080p 구간(파일 fuM1_<시작>.mp4, 0초 = 원본 시작초 · 정렬 실측 +0.03)
RATE = 7.8                                                         # 벤치 나레 자/초(공백 뺌)
WIN = (1080, 1052)                                                 # 벤치 창 [0,434,1080,1052]
FULL = (1109, 1080)                                                # 1920x1080 에서 창 비율 그대로(배율 0.974)
SAFE = (887, 864)                                                  # 아래 방송 그래픽(y≥870) 피하는 크롭(배율 1.217)

# 줄 정본. kind 원음 = 방송 영어 소리 그대로 + 한국어 번역 자막 / 나레 = TTS(벤치 반말 전언체) + 자막(TTS 소리 동안 원본 소리 끔)
# cut: (소스, 원본 시작초, 원본 끝초, 주피사체 가운데 x(원본 px), 크롭 y, 크롭 크기('F'|'S'), 화면에 보이는 것)
LINES = [
    {"id": "L1", "kind": "원음", "beat": "의문(반응 먼저)", "audio": (94.6, 101.99),
     "en": "500,000 for 1%? / That's correct. / Congratulations. Highest valuation ever requested in the Shark Tank.",
     "sub": ["50만 달러에 1%요?!", "맞습니다", "축하해요!", "샤크탱크 역대 최고 몸값이네요"],
     "fx": "0초 빨간 원(묻는 투자자 얼굴) — 벤치 0초 빨간 원 그대로",
     "cuts": [(CLIP, 94.6, 97.29, 870, 0, "F", "파란 재킷 투자자가 수첩 든 채 되묻는 얼굴(이름 자막 없음 — 이름 불명)"),
              (CLIP, 97.29, 99.6, 975, 0, "S", "창업자 정면(아래 'Seeking $500k…' 그래픽 y≥870 은 크롭으로 뺌)"),
              (CLIP, 99.6, 101.99, 1080, 0, "S", "대머리 검은 정장 투자자가 손가락으로 가리키며 말함(아래 그래픽 크롭으로 뺌)")]},
    {"id": "L2", "kind": "나레", "beat": "해답(제품)", "text": "버튼 한 번만 누르면 60초 만에 물병 속 세균을 없애 준다는 물병이 있는데",
     "tts": "버튼 한 번만 누르면 육십 초 만에 물병 속 세균을 없애 준다는 물병이 있는데",
     "sub": ["버튼 한 번만 누르면", "60초 만에 물병 속", "세균을 없애 준다는", "물병이 있는데"],
     "cuts": [(CLIP, 73.0, 75.0, 1350, 0, "F", "창업자 손의 흰 물병 뚜껑 — 파란 빛 고리가 켜진 근접"),
              (CLIP, 75.2, 77.1, 800, 0, "F", "같은 뚜껑 근접, 빛 고리 정면")]},
    {"id": "L3", "kind": "나레", "beat": "문제(기존 불편)", "text": "오래 쓴 물병은 냄새부터 맡아 보고 마신다는데",
     "tts": "오래 쓴 물병은 냄새부터 맡아 보고 마신다는데",
     "sub": ["오래 쓴 물병은", "냄새부터 맡아 보고", "마신다는데"],
     "cuts": [(CLIP, 24.4, 26.0, 830, 0, "F", "창업자가 파란 물병을 들고 말함"),
              (CLIP, 33.42, 34.6, 900, 0, "F", "창업자가 파란 물병 입구에 코를 대고 냄새 맡음")]},
    {"id": "L4", "kind": "원음", "beat": "문제(반응)", "audio": (34.6, 35.95), "en": "Ooh-wee!",
     "sub": ["우웩!"], "style": "원음반응_크게",
     "cuts": [(CLIP, 34.6, 35.95, 950, 0, "F", "냄새 맡고 고개를 젖히며 뚜껑을 흔드는 창업자(앞 컷과 같은 샷 이어짐)")]},
    {"id": "L5", "kind": "나레", "beat": "해답(원리)", "text": "뚜껑 속 UV 빛이 세균이랑 곰팡이를 99.99% 잡아 준다고",
     "tts": "뚜껑 속 유브이 빛이 세균이랑 곰팡이를 구십구 점 구구 퍼센트 잡아 준다고",
     "sub": ["뚜껑 속 UV 빛이", "세균이랑 곰팡이를", "99.99% 잡아 준다고"],
     "cuts": [(DEMO, 79.2, 81.3, 700, 0, "F", "공식 영상: 뚜껑 안쪽 UV 빛(보라·파랑) 근접 — 오른쪽 노란 글자는 크롭 밖"),
              (CLIP, 148.9, 151.5, 900, 0, "F", "흰 물병 뚜껑 쪽 근접(방송)")]},
    {"id": "L6", "kind": "원음", "beat": "전개(질문)", "audio": (172.4, 177.9),
     "en": "Is that safer than boiling water? / It would be the equivalent of boiling your water for like 20 minutes. / Really?",
     "sub": ["끓인 물보다 안전해요?", "물을 20분쯤 끓인 것과", "같은 수준이에요", "정말?"],
     "cuts": [(CLIP, 172.4, 174.1, 800, 0, "F", "파란 재킷 투자자 질문"),
              (CLIP, 174.1, 176.63, 990, 0, "F", "창업자 답"),
              (CLIP, 176.63, 177.9, 800, 0, "F", "파란 재킷 투자자 '정말?'(원본 대화 그대로 이어짐 — 우리 끼움 아님)")]},
    {"id": "L7", "kind": "나레", "beat": "숫자", "text": "출시 2년도 안 돼서 최근 1년 매출만 900만 달러가 넘는다는데",
     "tts": "출시 이 년도 안 돼서 최근 일 년 매출만 구백만 달러가 넘는다는데",
     "sub": ["출시 2년도 안 돼서", "최근 1년 매출만", "900만 달러가 넘는다는데"],
     "cuts": [(CLIP, 207.6, 209.6, 930, 0, "F", "창업자 근접, 매출 설명"),
              (CLIP, 212.85, 214.9, 980, 0, "F", "분홍 넥타이 투자자가 받아 적음")]},
    {"id": "L8", "kind": "나레", "beat": "반전", "text": "그런데 통장에 650만 달러가 그대로 있다는 말에",
     "tts": "그런데 통장에 육백오십만 달러가 그대로 있다는 말에",
     "sub": ["그런데 통장에", "650만 달러가", "그대로 있다는 말에"],
     "cuts": [(CLIP, 239.35, 240.85, 900, 0, "F", "회색 재킷 투자자가 묻는 얼굴"),
              (CLIP, 240.95, 243.4, 960, 0, "F", "창업자 답")]},
    {"id": "L9", "kind": "원음", "beat": "반전(하차)", "audio": (377.0, 378.75), "en": "…but I'm out.",
     "sub": ["전 빠질게요"], "style": "원음반응_크게",
     "cuts": [(CLIP, 377.0, 378.75, 990, 0, "F", "분홍 넥타이 투자자가 손짓하며 하차 선언")]},
    {"id": "L10", "kind": "나레", "beat": "투자자 경쟁", "text": "케빈은 4%, 로리는 5%는 받아야겠다고 하는데",
     "tts": "케빈은 사 퍼센트, 로리는 오 퍼센트는 받아야겠다고 하는데",
     "sub": ["케빈은 4%,", "로리는 5%는", "받아야겠다고 하는데"],
     "cuts": [(CLIP, 391.6, 393.4, 930, 0, "F", "대머리 검은 정장 투자자(=401~409초 'Kevin's offer' 화면 그래픽 붙은 사람)"),
              (CLIP, 420.2, 422.2, 900, 0, "F", "금발 투자자(=440~446초 'Lori's offer' 그래픽의 제안을 말한 사람)")]},
    {"id": "L11", "kind": "원음", "beat": "투자자 경쟁", "audio": (438.37, 440.47), "en": "500,000 for 5%.",
     "sub": ["50만 달러에 5%요"],
     "cuts": [(CLIP, 438.37, 440.47, 900, 0, "F", "금발 투자자 제안 말함")]},
    {"id": "L12", "kind": "나레", "beat": "결말", "text": "결국 케빈과 로리가 100만 달러에 지분 4%를 받기로 하고",
     "tts": "결국 케빈과 로리가 백만 달러에 지분 사 퍼센트를 받기로 하고",
     "sub": ["결국 케빈과 로리가", "100만 달러에", "지분 4%를 받기로 하고"],
     "cuts": [(CLIP, 610.4, 612.3, 960, 0, "F", "창업자가 손을 펴며 제안"),
              (CLIP, 619.5, 621.9, 960, 0, "F", "창업자 정면, 듣는 얼굴")]},
    {"id": "L13", "kind": "원음", "beat": "결말(악수)", "audio": (653.25, 658.1), "en": "Done. / Done. / All right. / Yes!",
     "sub": ["좋아요!", "좋아요!", "좋습니다", "예스!"], "style": "원음반응_크게",
     "fx": "날개 돈다발 이모지 — 벤치 40초 자리(투자 성사)",
     "cuts": [(CLIP, 653.25, 654.62, 960, 0, "F", "대머리 투자자 '좋아요'"),
              (CLIP, 654.62, 656.56, 900, 0, "F", "금발 투자자 '좋아요'"),
              (CLIP, 656.56, 658.1, 960, 0, "F", "창업자 무대에서 주먹 쥐고 환호(와이드)")]},
    {"id": "L14", "kind": "나레", "beat": "후일담", "text": "2024년엔 독일 정수 필터 회사 브리타가 이 회사를 인수했다고",
     "tts": "이천이십사 년엔 독일 정수 필터 회사 브리타가 이 회사를 인수했다고",
     "sub": ["2024년엔 독일 정수 필터", "회사 브리타가", "이 회사를 인수했다고"],
     "cuts": [(DEMO, 135.2, 137.2, 960, 0, "F", "공식 영상: 남자가 LARQ 물병으로 물 마심"),
              (DEMO, 140.0, 142.6, 960, 0, "F", "공식 영상: 색깔별 물병 5개 줄지어 선 테이블(LARQ 글자 뜨기 전)")]},
]


def src_of(vid: str, t: float) -> tuple[Path, float]:
    """원본 시각 → (받은 파일, 파일 안 시각)."""
    if vid == DEMO:
        return SRC / "demo_0.mp4", t
    for a, b in CLIP_SECTIONS:
        if a <= t <= b:
            return SRC / f"fuM1_{int(a)}.mp4", t - a
    raise ValueError(f"{t} 는 받은 구간 밖")


def nchar(s: str) -> int:
    return len(s.replace(" ", ""))


def line_dur(L: dict) -> float:
    if L["kind"] == "원음":
        return round(L["audio"][1] - L["audio"][0], 2)
    return round(nchar(L["tts"]) / RATE, 2)


def build():
    shots, t = [], 0.0
    for L in LINES:
        d = line_dur(L)
        cut_total = sum(c[2] - c[1] for c in L["cuts"])
        scale = d / cut_total if L["kind"] == "나레" else 1.0      # 나레 줄은 컷 길이를 줄 길이에 맞춰 늘림/줄임(재생 속도 아님 — 끝점 조정)
        print(f"{L['id']} {L['kind']} {d:.2f}s 컷합 {cut_total:.2f} 배 {scale:.2f}", file=sys.stderr)
        for c in L["cuts"]:
            vid, a, b, cx, y, sz, ours = c
            dur = round((b - a) * scale, 2)
            w, h = FULL if sz == "F" else SAFE
            x = max(0, min(1920 - w, int(cx - w / 2)))
            f, ss = src_of(vid, a)
            shots.append({"i": len(shots), "line": L["id"], "kind": L["kind"], "src": str(f).replace("\\", "/"),
                          "url": f"https://www.youtube.com/watch?v={vid}", "src_orig_span": [a, round(a + dur, 2)], "ss": round(ss, 3),
                          "dur": dur, "t_final_est": [round(t, 2), round(t + dur, 2)], "res": "1920x1080",
                          "src_crop": [x, y, w, h], "scale": round(WIN[0] / w, 3), "ours": ours,
                          "audio": "원본 소리(원음)" if L["kind"] == "원음" else "원본 소리 끔 + TTS"})
            t += dur
    return shots, round(t, 2)


def frame(path: str, ss: float, crop) -> Image.Image:
    x, y, w, h = crop
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-i", path, "-frames:v", "1", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale=270:263", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(b)).convert("RGB")


def sheet(shots, out: Path):
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 15)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 13)
    byline = {L["id"]: L for L in LINES}
    rowh, cw = 263 + 8, 270
    W = 60 + 3 * cw + 520
    S = Image.new("RGB", (W, rowh * len(shots) + 40), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.text((8, 8), "샥탬스토리 6편 LARQ — 계획 시트(컷마다 시작·가운데·끝, 창 크롭 그대로) · 제목: 지분 1%에 50만 달러 부른 / 스스로 씻는 물병?!", fill=(0, 0, 0), font=font)
    for k, s in enumerate(shots):
        y0 = 40 + k * rowh
        L = byline[s["line"]]
        d.text((6, y0 + 4), f"#{s['i']}", fill=(200, 0, 0), font=font)
        d.text((6, y0 + 24), s["line"], fill=(0, 0, 0), font=small)
        for j, frac in enumerate((0.05, 0.5, 0.95)):
            im = frame(s["src"], s["ss"] + (s["src_orig_span"][1] - s["src_orig_span"][0]) * frac, s["src_crop"])
            S.paste(im, (60 + j * cw, y0))
        tx = 60 + 3 * cw + 8
        col = (0, 90, 200) if L["kind"] == "원음" else (0, 0, 0)
        d.text((tx, y0 + 2), f"{L['kind']} · {L['beat']} · {s['t_final_est'][0]:.2f}~{s['t_final_est'][1]:.2f}s ({s['dur']:.2f}s)", fill=col, font=font)
        msg = L.get("en") if L["kind"] == "원음" else L["text"]
        for n, part in enumerate(_wrap(msg, 34)):
            d.text((tx, y0 + 24 + n * 18), part, fill=(0, 0, 0), font=small)
        d.text((tx, y0 + 100), "자막: " + " / ".join(L["sub"]), fill=(120, 0, 120), font=small)
        d.text((tx, y0 + 140), f"{Path(s['src']).name} @원본 {s['src_orig_span'][0]}~{s['src_orig_span'][1]} 크롭 {s['src_crop']} ×{s['scale']}", fill=(90, 90, 90), font=small)
        for n, part in enumerate(_wrap(s["ours"], 34)):
            d.text((tx, y0 + 160 + n * 18), part, fill=(0, 100, 0), font=small)
        if L.get("fx") and s == next(x for x in shots if x["line"] == s["line"]):
            d.text((tx, y0 + 230), "효과: " + L["fx"], fill=(200, 0, 0), font=small)
    S.save(out, quality=82)


def _wrap(s: str, n: int):
    out, cur = [], ""
    for w in s.split(" "):
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


def check(shots, total):
    """A표 자체 점검에 쓰는 숫자."""
    durs = sorted(s["dur"] for s in shots)
    med = durs[len(durs) // 2] if len(durs) % 2 else (durs[len(durs) // 2 - 1] + durs[len(durs) // 2]) / 2
    seen, overlap = [], []
    for s in shots:
        vid = s["url"][-11:]
        a, b = s["src_orig_span"]
        for (v2, a2, b2, i2, l2) in seen:
            forward = i2 == s["i"] - 1 and a >= b2 - 0.01          # 바로 앞 컷에서 앞으로만 이어짐(같은 샷 연속) = 재사용 아님
            if v2 == vid and a < b2 + 3 and a2 < b + 3 and not forward:
                overlap.append((i2, s["i"]))
        seen.append((vid, a, b, s["i"], s["line"]))
    narr = sum(nchar(L["tts"]) for L in LINES if L["kind"] == "나레")
    sub_max = max(len(x) for L in LINES for x in L["sub"])
    return {"길이_추정": total, "컷": len(shots), "컷_중앙": round(med, 2), "컷_최소": durs[0],
            "±3초_재사용(다른 줄)": overlap, "나레_자수(TTS,공백뺌)": narr, "자막_최대자수": sub_max,
            "원음_초": round(sum(line_dur(L) for L in LINES if L["kind"] == "원음"), 2)}


def main():
    shots, total = build()
    mat = {"_note": "샥탬스토리 6편 LARQ 재료 계획 — TTS·렌더 전. 창 1080x1052(벤치 QMJtjJz4M6w 창 [0,434,1080,1052]). "
                    "나레 시각은 7.8자/초 추정 — TTS 뒤 줄 끝에 맞춰 컷 끝점만 다시 잰다. 원음 컷은 src_orig_span 그대로 원본 소리. "
                    "make_plan.py LINES 가 정본(이 파일은 생성물).",
           "sources": {
               CLIP: {"채널": "Shark Tank Global", "제목": "Larq Has The Highest Valuation Ever On Shark Tank! | Shark Tank US | Shark Tank Global",
                      "업로드": "2022-08-18", "해상도": "1920x1080 (format 137)", "길이": 678,
                      "받은 구간": "10~262초 fuM1_10.mp4 · 360~447초 fuM1_360.mp4 · 595~660초 fuM1_595.mp4 (+소리 전체 fuM1Vh7OgfY_audio.m4a)",
                      "남의 글자": "아래 방송 그래픽(이름·제안 자막, y 870~1010): 52~60·98~101·401~409·440~446·448~452·628~634·648~652초 — L1 #1·#2 는 SAFE 크롭(y<864), 나머지 구간은 안 씀. "
                                 "창업자 티셔츠 'LARQ Drink Brilliantly' = 제품 브랜드(남의 자막 아님). 660초~ 'SHARK TANK WATCH MORE' 엔드카드 안 씀"},
               DEMO: {"채널": "LARQ(공식)", "제목": "LARQ – The World's First Self-Cleaning Water Bottle", "업로드": "2018-06-01",
                      "해상도": "1920x1080 (format 137, 24fps)", "길이": 147, "받은 구간": "0~147초 demo_0.mp4(영상만, 소리 안 씀)",
                      "남의 글자": "43~46·79~81(오른쪽)·95~102초 노란 글자, 61~64·143~147초 LARQ 글자 — 79~81 은 크롭으로 뺌, 나머지 안 씀"}},
           "window": [0, 434, 1080, 1052], "frame_preset": "channel/foreignshowshow/preset 「샤크탱크_검정띠2줄」",
           "titles": {"line1": "지분 1%에 50만 달러 부른", "line2": "스스로 씻는 물병?!"},
           "shots": shots}
    (HERE / "재료.json").write_text(json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
    sheet(shots, HERE / "plan" / "계획_시트.jpg")
    c = check(shots, total)
    print(json.dumps(c, ensure_ascii=False))
    return shots, c


if __name__ == "__main__":
    main()
