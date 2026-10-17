# -*- coding: utf-8 -*-
"""샥탬스토리 2편 Squatty Potty — 대본·재료·계획 한 벌(이 파일 한 곳에서 줄·컷을 정한다) (관제 097, 2026-10-18).
    py channel/foreignshowshow/2편_SquattyPotty/make_plan.py [--no-sheet]
쓰는 것: 대본.json · 재료.json · plan/계획.md · plan/계획_시트.jpg
화면 틀 = 벤치 QMJtjJz4M6w 그대로(창 [0,434,1080,1052] = 가로 원본 높이 1052 맞춤 가운데 크롭, 위 검정 띠 2줄 제목, 아래 검정).
"""
import json, subprocess, sys, tempfile
from pathlib import Path
from statistics import median
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
WORK = Path("C:/숏템_칼카피/foreignshowshow/2편_SquattyPotty")
SRC = {
    "shark": {"id": "2atjT5fKK8A", "file": WORK / "src/2atj_full_v.mp4", "audio": WORK / "src/2atjT5fKK8A_audio.m4a",
              "what": "Shark Tank Global 공식 클립(558초, 1920x1080)", "url": "https://www.youtube.com/watch?v=2atjT5fKK8A"},
    "ad": {"id": "YbYWhdLO43Q", "file": WORK / "src/Ybad_full.mp4", "what": "Squatty Potty 공식 유니콘 광고(173초, 1920x1080 받음)",
           "url": "https://www.youtube.com/watch?v=YbYWhdLO43Q"},
    "cnbc": {"id": "eW9uh884ll8", "file": WORK / "src/eW9_full.mp4", "what": "CNBC 'Shark Tank: How It's Going' 후일담 포함(316초, 1920x1080)",
             "url": "https://www.youtube.com/watch?v=eW9uh884ll8"},
}
WIN_W, WIN_H, BENCH_MED = 1080, 1052, 1.27
CPS = 7.8   # 벤치 나레 말속도(받아쓰기 181자/23.2초 실측, 공백 뺀 글자)

# 줄: kind N(나레)/O(원음). O 는 sub=[(영어 원음, 한국어 번역 자막)], N 은 text(화면)·tts(읽는 글)·chunks(자막 조각 ≤13자)
# 컷: (소스, a, b, 화면에 보이는 것, 옵션{zoom, top, cx, fx})
LINES = [
 {"beat": "1 결말 반응", "kind": "O",
  "sub": [("Holy crap!", "헐 대박!"), ("You're selling—", "그걸 판다고?"), ("Holy crap, right? There's a crapload of money in Squatty Potty.", "대박이죠? 이 발판에 돈이 똥더미로 쌓여요")],
  "asr": "155.96~157.12 'Holy crap!' 2모델 일치(asr_clips.json) · 157.12~157.9 'You're selling' 2모델(asr_clips2.json, 겹친 말) · 157.12~160.3 'Holy crap, right? There's a crap load of money in Squatty Potty.' 60초 묶음 2모델 일치(asr_2atj.json 3-flash 157~160·asr 첫판 latest 157.53~160.38)",
  "cuts": [("shark", 155.96, 157.12, "분홍 셔츠 남자 투자자 입 벌리고 웃음(이름 화면 글자 없음=불명)", {"fx": "빨간 원(투자자 얼굴, 벤치 0초 그대로)"}),
           ("shark", 157.12, 158.36, "창업자 모자(母子) 둘이 서서 웃으며 말함", {}),
           ("shark", 158.36, 159.29, "남색 재킷 남자 투자자 손 모으고 크게 웃음(이름 불명)", {}),
           ("shark", 159.29, 160.3, "투자자석 넓은 화면(웃는 투자자들)", {})]},
 {"beat": "2 시연", "kind": "N",
  "text": "변기 앞에 이 발판 하나만 놓고 두 발을 올리면 쪼그려 앉은 자세가 된다는데",
  "tts": "변기 앞에 이 발판 하나만 놓고, 두 발을 올리면 쪼그려 앉은 자세가 된다는데",
  "chunks": ["변기 앞에", "이 발판 하나만 놓고", "두 발을 올리면", "쪼그려 앉은 자세가", "된다는데"],
  "src_note": "창업자 피치 89~100초 'A simple stool… allows the user to squat in a healthy position while still enjoying… their Western toilet'(asr_2atj_b 2모델)",
  "cuts": [("shark", 44.21, 45.51, "천을 걷자 흰 변기+그 앞 흰 발판이 드러남", {}),
           ("ad", 65.57, 67.0, "유니콘 인형이 변기에 앉아 두 발을 발판에 올림(장 그림 곧게, 무지개 짧게)", {}),
           ("shark", 188.0, 189.76, "흰 변기 앞에 끼워진 흰 발판 근접(오른쪽 위 사람 손 → 크롭 왼쪽 cx0.25로 뺌)", {"cx": 0.25, "fx": "빨간 점선 원(발판, 벤치 10~12초 그대로)"})]},
 {"beat": "3 기존 불편", "kind": "N",
  "text": "그냥 앉으면 장 끝 근육이 꺾여서 잘 안 나오는데 쪼그려 앉으면 쭉 펴진다고",
  "tts": "그냥 앉으면 장 끝 근육이 꺾여서 잘 안 나오는데, 쪼그려 앉으면 쭉 펴진다고",
  "chunks": ["그냥 앉으면", "장 끝 근육이 꺾여서", "잘 안 나오는데", "쪼그려 앉으면", "쭉 펴진다고"],
  "src_note": "창업자 61.5~84.5초 'puborectalis muscle… forming a kink… sitting… only partially relaxes… only in a squat position… completely relax'(asr_2atj_b 2모델) — 출연자 주장이라 전언체",
  "cuts": [("ad", 38.5, 40.6, "유니콘 엉덩이 근접 위 장·근육 그림 — 꺾인 관(글자 없음)", {"fx": "분홍 화살표(꺾인 곳, 벤치 14초 그대로)"}),
           ("ad", 72.49, 74.7, "발판 위 유니콘 옆모습, 장 그림이 곧게 펴짐(안에 무지개 조금)", {})]},
 {"beat": "4 숫자", "kind": "N",
  "text": "엄마랑 아들이 35만 달러에 지분 5%를 걸었는데",
  "tts": "엄마랑 아들이 삼십오만 달러에 지분 오 퍼센트를 걸었는데",
  "chunks": ["엄마랑 아들이", "35만 달러에", "지분 5%를 걸었는데"],
  "src_note": "21~25.5초 'This is my mother Judy… seeking $350,000 for a 5% share'(2모델) · 화면 이름표 38~39초 'BOBBY & JUDY EDWARDS'·40~42초 'Seeking $350k for a 5% stake'",
  "cuts": [("shark", 2.5, 3.6, "어두운 복도에서 창업자 둘이 걸어 들어옴", {}),
           ("shark", 22.46, 24.9, "창업자 둘이 서서 피치(아들 말함)", {})]},
 {"beat": "4 숫자", "kind": "O",
  "sub": [("The first year in business, we sold a million dollars in Squatty Potty.", "첫해에만 100만 달러어치 팔았어요"), ("Come on!", "말도 안 돼!")],
  "asr": "136.74~139.34 2모델 'First year in business, we sold $1 million in Squa-'(장면 끝에서 단어가 잘려 소리는 다음 컷으로 이어 둔다) · 139.34~140.0 웅얼거림(모델마다 'Hey everybody'/'party party' — 번역 안 함) · 140.0~140.7 'Come on' 3/4회(60초 묶음 2모델+클립 latest, 클립 3-flash 는 'Mama, I'm on TV!' — 불일치 1회)",
  "cuts": [("shark", 136.74, 139.34, "창업자 둘, 아들이 손짓하며 말함", {}),
           ("shark", 139.34, 140.91, "분홍 셔츠 남자 투자자 놀라 웃음", {})]},
 {"beat": "4 숫자", "kind": "O",
  "sub": [("The year after that?", "그다음 해는요?"), ("The year after, we did 2.7 million.", "다음 해엔 270만 달러요")],
  "asr": "140.91~143.61 2모델 'The year after that / (The year after) we did 2.7 million'",
  "cuts": [("shark", 140.91, 142.21, "대머리 남자 투자자 손짓하며 물음(이름 불명)", {}),
           ("shark", 142.21, 143.61, "창업자 둘, 아들이 답함", {})]},
 {"beat": "4 숫자", "kind": "O",
  "sub": [("Yes, I like it.", "좋아, 맘에 드네")],
  "asr": "143.61~144.44 2모델 'Yes, I like it.'",
  "cuts": [("shark", 143.61, 144.44, "대머리 남자 투자자 손가락 들고 말함", {})]},
 {"beat": "5 지분 경쟁", "kind": "N",
  "text": "케빈이 같은 돈에 10%를 달라는데",
  "tts": "케빈이 같은 돈에 십 퍼센트를 달라는데",
  "chunks": ["케빈이 같은 돈에", "10%를 달라는데"],
  "src_note": "334~337초 'I'd give you the $350,000 for 10%'(2모델) · 화면 이름표 337~340초 'Kevin's offer: $350k for a 10% stake'(얼굴↔이름 연결은 안 함)",
  "cuts": [("shark", 331.8, 333.4, "투자자석 넓은 화면(창업자 쪽에서)", {}),
           ("shark", 341.6, 342.9, "아들 얼굴 근접, 듣는 표정", {})]},
 {"beat": "5 지분 경쟁", "kind": "O",
  "sub": [("Yeah, 700,000 for 10%.", "그럼 70만 달러에 10%로 하죠")],
  "asr": "381.75~384.0 2모델 'Yeah, 700,000 for 10%.'(끝 383.55~384.05 → 컷 끝 383.72 = 장면 바뀜)",
  "cuts": [("shark", 381.75, 383.72, "창업자 둘, 아들이 역제안(아래 이름표 띠 → 1.35배 위쪽 크롭, 말하는 아들 쪽 cx0.25)", {"zoom": 1.35, "top": True, "cx": 0.25})]},
 {"beat": "5 지분 경쟁", "kind": "N",
  "text": "로리도 35만 달러에 10%를 고집하자",
  "tts": "로리도 삼십오만 달러에 십 퍼센트를 고집하자",
  "chunks": ["로리도 35만 달러에", "10%를 고집하자"],
  "src_note": "412.3~416.5초 'I feel that the 350,000 for 10% is right'(2모델) · 화면 이름표 416~418초 \"Lori's offer: $350k for a 10% stake\"",
  "cuts": [("shark", 403.77, 405.5, "금발 여자 투자자 말함(이 사람 컷에 'Lori's offer' 이름표가 415초에 뜸)", {"fx": "날개 돈다발 이모지(벤치 40초 그대로)"}),
           ("shark", 408.78, 410.1, "금발 여자 투자자 말함", {})]},
 {"beat": "5 지분 경쟁", "kind": "O",
  "sub": [("How about 10% for 500,000?", "50만 달러에 10%는 어때요?")],
  "asr": "416.45~418.92 2모델 'How about 10% for 500,000?'",
  "cuts": [("shark", 416.45, 418.92, "아들이 제안(이름표 띠 → 1.35배 위쪽 크롭, 아들 쪽 cx0.25)", {"zoom": 1.35, "top": True, "cx": 0.25})]},
 {"beat": "5 지분 경쟁", "kind": "O",
  "sub": [("I don't accept that.", "그건 안 받아요")],
  "asr": "425.75~427.4 2모델 'I don't accept that.'(끝 426.95~427.19 → 컷 끝 427.0 = 장면 바뀜)",
  "cuts": [("shark", 425.75, 427.0, "금발 여자 투자자 단호하게 말함(이름표 띠 → 1.35배 위쪽 크롭)", {"zoom": 1.35, "top": True})]},
 {"beat": "5 지분 경쟁", "kind": "O",
  "sub": [("Actually, we're going to take Lori's offer.", "로리 제안 받을게요"), ("There you go. Great.", "좋았어!")],
  "asr": "513.45~515.25 2모델 'Actually, we're going to take Lori's offer.' · 515.25~517.0 3-flash 'There you go. / Great.'(60초 묶음 2모델도 516.2 'There you go' 517.1 'Great')",
  "cuts": [("shark", 513.45, 515.25, "창업자 둘, 아들이 결정 발표", {}),
           ("shark", 515.25, 517.1, "금발 여자 투자자 놀라며 웃음", {})]},
 {"beat": "6 방송 후 결과", "kind": "N",
  "text": "그렇게 손을 잡고 방송 뒤 20개 나라에 진출해서 450만 개 넘게 팔렸고",
  "tts": "그렇게 손을 잡고, 방송 뒤 스무 개 나라에 진출해서 사백오십만 개 넘게 팔렸고",
  "chunks": ["그렇게 손을 잡고", "방송 뒤 20개 나라에", "진출해서", "450만 개 넘게 팔렸고"],
  "src_note": "CNBC eW9uh884ll8 256~265초 'We've now sold over 4.5 million… partnered with over 20 major retailers… in 20 countries'(유튜브 자막 + asr_eW9.json 2모델 일치) — 출처 1곳",
  "cuts": [("shark", 520.15, 521.6, "금발 여자 투자자와 아들 포옹", {}),
           ("shark", 522.4, 523.9, "금발 여자 투자자와 엄마 포옹", {}),
           ("cnbc", 257.2, 258.8, "회의실 긴 탁자, 창업자·투자자 회의(아래 방송 글자 → 1.12배 위쪽 크롭)", {"zoom": 1.12, "top": True})]},
 {"beat": "6 방송 후 결과", "kind": "N",
  "text": "방송 이후 매출만 1억 7,500만 달러를 찍었다고",
  "tts": "방송 이후 매출만 일억 칠천오백만 달러를 찍었다고",
  "chunks": ["방송 이후 매출만", "1억 7,500만 달러를", "찍었다고"],
  "src_note": "CNBC eW9uh884ll8 265~271초 'We've now done 175 million dollars in sales since Shark Tank'(유튜브 자막 + asr_eW9.json 2모델 일치) — 출처 1곳(전언체)",
  "cuts": [("cnbc", 268.2, 269.8, "창업자 모자 인터뷰, 웃으며 말함(1.12배 위쪽 크롭 — 아래 방송 글자 뺌)", {"zoom": 1.12, "top": True}),
           ("cnbc", 283.6, 285.5, "새 집 앞 금발 여자 투자자·엄마·남자 둘 웃으며 서 있음(1.12배 위쪽 크롭)", {"zoom": 1.12, "top": True})]},
]
TITLE = ["볼일이 술술 나온다는", "변기 발판?!"]


def nospace(s):
    return len(s.replace(" ", "").replace(",", ""))


def build():
    t = 0.0
    rows, lines_out, cuts_all = [], [], []
    for i, L in enumerate(LINES, 1):
        dur = round(sum(b - a for _, a, b, *_ in L["cuts"]), 2)
        need = round(nospace(L["tts"]) / CPS + 0.25, 2) if L["kind"] == "N" else dur
        lo = {"n": i, "beat": L["beat"], "kind": "나레" if L["kind"] == "N" else "원음", "t0": round(t, 2), "t1": round(t + dur, 2), "dur": dur}
        if L["kind"] == "N":
            lo.update(text=L["text"], tts_text=L["tts"], chunks=L["chunks"], est_tts_sec=need, src=L["src_note"])
        else:
            lo.update(orig=[e for e, _ in L["sub"]], sub_ko=[k for _, k in L["sub"]], asr=L["asr"])
        lines_out.append(lo)
        ct = t
        for (s, a, b, what, opt) in L["cuts"]:
            c = {"line": i, "src": s, "id": SRC[s]["id"], "a": a, "b": b, "dur": round(b - a, 2), "t0": round(ct, 2),
                 "res": "1920x1080", "what": what, "zoom": opt.get("zoom", 1.0), "top": opt.get("top", False), "fx": opt.get("fx", ""), "cx": opt.get("cx", 0.5)}
            cuts_all.append(c); ct += b - a
        rows.append((i, L, dur, need))
        t += dur
    return lines_out, cuts_all, round(t, 2)


def checks(cuts_all, lines_out):
    out = []
    # 같은 소스 겹침/±3초 재사용(되감김) — 앞으로 이어지는 연속 컷은 허용, 되돌아가거나 3초 안에서 다시 쓰면 걸림
    bad = []
    for i, c in enumerate(cuts_all):
        for d in cuts_all[i + 1:]:
            if c["src"] != d["src"]:
                continue
            overlap = d["a"] < c["b"] and c["a"] < d["b"]
            back = d["a"] < c["a"] and (c["a"] - d["b"]) < 3
            if overlap or back:
                bad.append(f'{c["id"]} {c["a"]}-{c["b"]} ↔ {d["a"]}-{d["b"]}')
    out.append(("같은 구간 재사용·되감김", "0건" if not bad else "; ".join(bad)))
    short = [l["n"] for l in lines_out if l["kind"] == "나레" and l["dur"] + 1e-6 < l["est_tts_sec"]]
    out.append(("나레 줄 컷 < 예상 말 길이", "0줄" if not short else str(short)))
    long_chunk = [ch for l in lines_out for ch in l.get("chunks", []) if len(ch) > 13]
    out.append(("자막 조각 >13자", "0개" if not long_chunk else str(long_chunk)))
    return out


def frame(src, t, zoom, top, w, cx=0.5):
    sh = int(round(WIN_H * zoom / 2)) * 2
    y = "0" if top else f"(ih-{WIN_H})/2"
    vf = f"scale=-2:{sh},crop={WIN_W}:{WIN_H}:(iw-{WIN_W})*{cx}:{y},scale={w}:-2"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "f.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-vf", vf, str(p)], check=True)
        return Image.open(p).copy()


def sheet(lines_out, cuts_all, path):
    W = 150
    fnt = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 15)
    fb = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 16)
    th = int(W * WIN_H / WIN_W)
    rowh = th + 8
    colw = 3 * W + 470
    cols = 2
    n = len(cuts_all)
    per = (n + cols - 1) // cols
    img = Image.new("RGB", (cols * colw + 20, per * rowh + 70), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 8), f"샥탬스토리 2편 Squatty Potty 계획 시트 — 제목 「{TITLE[0]} / {TITLE[1]}」 · 컷 {n}개 · 중앙 {median([c['dur'] for c in cuts_all]):.2f}초(벤치 {BENCH_MED}) · 컷마다 처음·가운데·끝 프레임(창 크롭 그대로)", font=fb, fill=(0, 0, 0))
    byline = {l["n"]: l for l in lines_out}
    for k, c in enumerate(cuts_all):
        col, r = divmod(k, per)
        x0, y0 = 10 + col * colw, 40 + r * rowh
        src = SRC[c["src"]]["file"]
        for j, tt in enumerate((c["a"] + 0.12, (c["a"] + c["b"]) / 2, c["b"] - 0.12)):
            img.paste(frame(src, tt, c["zoom"], c["top"], W, c["cx"]), (x0 + j * W, y0))
        L = byline[c["line"]]
        txt = L.get("text") or " / ".join(f"{e} → {ko}" for e, ko in zip(L["orig"], L["sub_ko"]))
        clr = (0, 0, 160) if L["kind"] == "나레" else (170, 0, 0)
        tx = x0 + 3 * W + 8
        d.text((tx, y0 + 2), f'#{k+1} 줄{c["line"]}({L["kind"]}·{L["beat"]})  {c["t0"]:.1f}초~ {c["dur"]:.2f}초', font=fb, fill=clr)
        d.text((tx, y0 + 24), f'{c["id"]} {c["a"]:.2f}~{c["b"]:.2f}' + (f' ×{c["zoom"]}' if c["zoom"] != 1 else "") + (f' · {c["fx"]}' if c["fx"] else ""), font=fnt, fill=(80, 80, 80))
        # 줄 글자 접기
        s, ln, yy = txt, "", y0 + 46
        for ch in s:
            ln += ch
            if d.textlength(ln, font=fnt) > 455:
                d.text((tx, yy), ln, font=fnt, fill=(0, 0, 0)); yy += 19; ln = ""
                if yy > y0 + th - 18:
                    break
        if ln and yy <= y0 + th - 18:
            d.text((tx, yy), ln, font=fnt, fill=(0, 0, 0))
        d.text((tx, y0 + th - 20), c["what"][:40], font=fnt, fill=(0, 110, 0))
    img.save(path, quality=85)


def main():
    lines_out, cuts_all, total = build()
    med = round(median([c["dur"] for c in cuts_all]), 2)
    chk = checks(cuts_all, lines_out)
    narr_chars = sum(nospace(l["text"]) for l in lines_out if l["kind"] == "나레")
    orig_sec = round(sum(l["dur"] for l in lines_out if l["kind"] == "원음"), 2)
    dae = {"channel": "foreignshowshow(샥탬스토리 벤치)", "ep": "2편_SquattyPotty", "bench": "QMJtjJz4M6w", "frame": "벤치 그대로(1080x1920, 위 검정 띠 2줄 제목 1줄 노랑·2줄 흰, 창 [0,434,1080,1052], 아래 검정, 로고 자리 '샥탬스토리')",
           "title": {"line1_yellow": TITLE[0], "line2_white": TITLE[1]}, "length_sec": total, "narr_chars": narr_chars, "orig_sec": orig_sec,
           "tone": "나레 = 한국어 반말 전언체(~는데/~다고/~고/~자), 원음 = 영어 방송 원음 + 한국어 번역 자막",
           "fx_bench_same": ["0초 빨간 원(투자자 얼굴)", "빨간 점선 원(발판)", "분홍 화살표(장 꺾인 곳)", "날개 돈다발 이모지(지분 경쟁)", "자막 흰+형광 핵심어 강조, 검정 테두리"],
           "lines": lines_out}
    (HERE / "대본.json").write_text(json.dumps(dae, ensure_ascii=False, indent=1), encoding="utf-8")
    jae = {"sources": {k: {kk: str(vv) for kk, vv in v.items()} for k, v in SRC.items()}, "window": [0, 434, WIN_W, WIN_H],
           "crop_rule": "가로 원본을 높이 1052(×zoom)로 키워 가운데 1080 크롭, top=True 면 위에 붙여 아래 글자 띠를 뺀다",
           "cut_median": med, "bench_median": BENCH_MED, "checks": chk, "cuts": cuts_all}
    (HERE / "재료.json").write_text(json.dumps(jae, ensure_ascii=False, indent=1), encoding="utf-8")
    # 계획.md
    md = [f"# 샥탬스토리 2편 Squatty Potty — 계획 (관제 097, make_plan.py 생성)", "",
          f"- 제목 띠: 1줄(노랑) **{TITLE[0]}** / 2줄(흰) **{TITLE[1]}**",
          f"- 길이 {total}초(벤치 50.5) · 나레 {narr_chars}자(벤치 181) · 원음 {orig_sec}초 · 컷 {len(cuts_all)}개 · 컷 중앙 {med}초(벤치 {BENCH_MED})",
          "- 틀 = 벤치 QMJtjJz4M6w 그대로: 위 검정 띠 2줄 제목·가운데 가로 원본 확대 크롭·아래 검정·자막 흰+형광 강조·0초 빨간 원·빨간 점선 원·분홍 화살표·날개 돈다발 이모지. 바꾸는 것 = 로고 자리 '샥탬스토리'뿐.",
          "", "## 점검(자동)", ""] + [f"- {k}: {v}" for k, v in chk] + ["", "## 줄 ↔ 컷", "",
          "| 줄 | 박자 | 종류 | 시각 | 글(나레) / 원음 → 번역 | 컷: 소스 · 구간 · 해상도 · 화면 |", "|---|---|---|---|---|---|"]
    for l in lines_out:
        txt = l.get("text") or " / ".join(f"{e} → {k}" for e, k in zip(l["orig"], l["sub_ko"]))
        cs = "<br>".join(f'{c["id"]} {c["a"]:.2f}~{c["b"]:.2f}({c["dur"]:.2f}초) {c["res"]}' + (f' ×{c["zoom"]}위' if c["zoom"] != 1 else "") + f' · {c["what"]}' + (f' · **{c["fx"]}**' if c["fx"] else "")
                         for c in cuts_all if c["line"] == l["n"])
        md.append(f'| {l["n"]} | {l["beat"]} | {l["kind"]} | {l["t0"]:.1f}~{l["t1"]:.1f} | {txt} | {cs} |')
    md += ["", "## 소스", ""] + [f'- {v["id"]} — {v["what"]} — {v["url"]}' for v in SRC.values()]
    (HERE / "plan").mkdir(exist_ok=True)
    (HERE / "plan" / "계획.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"길이 {total}초 · 컷 {len(cuts_all)} · 중앙 {med} · 나레 {narr_chars}자 · 원음 {orig_sec}초")
    for k, v in chk:
        print(" ", k, v)
    for l in lines_out:
        print(f'  {l["n"]:2} {l["kind"]} {l["t0"]:5.1f}-{l["t1"]:5.1f} dur {l["dur"]:.2f}' + (f' est {l["est_tts_sec"]}' if l["kind"] == "나레" else ""))
    if "--no-sheet" not in sys.argv:
        sheet(lines_out, cuts_all, HERE / "plan" / "계획_시트.jpg")
        print("시트", HERE / "plan" / "계획_시트.jpg")


if __name__ == "__main__":
    main()
