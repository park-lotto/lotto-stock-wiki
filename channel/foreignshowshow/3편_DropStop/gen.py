# -*- coding: utf-8 -*-
"""3편 Drop Stop — 대본.json·재료.json 생성(계획 단계, TTS·렌더 전). 시각은 추정(나레 6.5자/초)."""
import json, re
from pathlib import Path
OUT = Path(r"C:/Users/CH/Desktop/로또의 주식/.tracks/칼카피숏템엔진/channel/foreignshowshow/3편_DropStop")
SRC = "ME64bRiQi24.mp4"
URL = "https://www.youtube.com/watch?v=ME64bRiQi24"
CPS = 6.5
W, H = 965, 940            # src_crop 크기(창 1080x1052 비율, 아래 CNBC 띠 y>=950 밖) → 확대 1.119
BOX = [0, 434, 1080, 1052]

facts = {
 "f1": {"text": "소스 = CNBC Ambition 'Drop Stop Fills The Gap | Shark Tank: How It Started | CNBC Prime' ME64bRiQi24(330.65초, 1920x1080 29.97, 영어 원음 140-7). 방송 시즌4 피치 + 시즌9 후일담 편집본(화면 'SEASON 4 | THE DROP STOP'·'SEASON 9 UPDATE' 띠)", "url": URL, "kind": "출처"},
 "f2": {"text": "피치 원음 18.0~32.0 '그 틈(seat and center console gap)… black hole, dark abyss, pit of doom … eats up your cell phone, your keys, loose change … french fry'(영어 자동자막 단어 시각) · 화면 23.96~27.53·33.9~36.2·65.3~68.3 콘솔 칸 감자튀김+좌석 틈 근접", "url": URL, "kind": "원음+화면"},
 "f3": {"text": "피치 원음 44.3~49.4 'who hasn't struggled, gotten on their hands and knees, butt up in the air trying to retrieve…' · 화면 44.9~47.9 무대에서 창업자가 좌석 옆에 몸을 숙여 시늉", "url": URL, "kind": "원음+화면"},
 "f4": {"text": "피치 원음 76.5~90.0 'the built-in slot is designed to fit easily around the seat belt catch … anchors it to the seat so it can never fall through to the floor … wherever your seat goes, Drop Stop follows' · 화면 79.41~84.15·85.05~90.59 손이 틈에 끼우고 좌석이 움직이는 근접", "url": URL, "kind": "원음+화면"},
 "f5": {"text": "원음 111.2~113.8 'We have actually sold over 260,000 units'(받아쓰기 4회) · 139.6~145.0 'our cost to us is four dollars … for retail it sells for 19.99'(자동자막)", "url": URL, "kind": "본인 말"},
 "f6": {"text": "투자자 2명 하차: 175~177 '…not something that I believe in, I'm out'(자동자막 단어) · 177~190.2 '…but guys I have to say I'm out'(화면 182~191 같은 투자자, 이름 화면 글자 없음 → '투자자'로만)", "url": URL, "kind": "본인 말"},
 "f7": {"text": "케빈 제안: 194.1~203.6 'I'll give you the 300,000, I don't want any equity … every time you sell one of these foam weenies I get two dollars back'(받아쓰기 4회 198.3~203.6) · 이름 = 화면 아래 띠 205~211 'Kevin's offer: $300k for a royalty of $2 per unit'", "url": URL, "kind": "본인 말+화면 글자"},
 "f8": {"text": "로리 제안: 219.7~222.3 'I can easily make you millionaires' · 222.9~227.3 'I'm going to offer you the three hundred thousand dollars but I'm going to ask for 20'(받아쓰기 4회 225.9~227.5) · 이름 = 화면 아래 띠 234~238 'Lori's offer: $300k for a 20% stake' · 위키 'agreed to 20% equity in Drop Stop for $300,000'", "url": "https://en.wikipedia.org/wiki/Drop_Stop", "kind": "본인 말+화면 글자+위키"},
 "f9": {"text": "딜: 265.8~267.3 'on behalf of both of us, Lori'(자동자막) → 268.9~270.4 로리 환호(화면) · 후일담 314.2~317.9 'five years since doing a deal with Lori we've hit 28 million'(창업자 말, 받아쓰기 2회 '…we've hit 28 million') — 위키는 '2017년 12월 기준 240만 개·매출 2,400만 달러'(CNBC 2017 인용)라 숫자가 다름 → 창업자 말로 전언", "url": URL, "kind": "본인 말"},
 "f10": {"text": "LA 경찰: 274~300 'Los Angeles'·경찰 본부 회의(화면) · 291.8~299.3 경찰 간부 'after three months we've had zero traffic related accidents, so we will be outfitting 3,000 of our police cars with Drop Stops'(자동자막) · 위키 'three-month long test … zero traffic-related accidents … equip 3,000 patrol vehicles'", "url": "https://en.wikipedia.org/wiki/Drop_Stop", "kind": "원음+위키"},
}

# kind: N=나레(원음 끔) / O=원음(영어)+한국어 번역 자막
L = [
 dict(id="O1", fn="0~3초 결말 반응(로리 제안, 빨간 원)", kind="O", text="대신 지분 20%는 받을게요", orig="But I'm going to ask for 20", a=(225.95, 227.5), facts=["f8"],
      shots=[(225.95, 1.55, 300, "로리 얼굴(말하는 본인, 225.9~228.3 단독 컷)")], fx="빨간 원(로리 얼굴) 0초 — 벤치 그대로"),
 dict(id="N1", fn="시연(제품 한 줄)", kind="N", text="운전석이랑 콘솔 사이 틈을 막아서, 폰이 안 빠지게 해 준다는 물건이 있는데",
      tts="운전석이랑 콘솔 사이 틈을 막아서 폰이 안 빠지게 해 준다는 물건이 있는데", facts=["f2", "f4"],
      shots=[(65.75, 1.6, 477, "콘솔 칸(감자튀김)과 좌석 사이 틈 근접"), (70.5, 2.0, 477, "무대 좌석 세트 옆 창업자 둘(넓게)")]),
 dict(id="O2", fn="기존 불편(원음)", kind="O", text="그 블랙홀, 그 어두운 구렁", orig="That black hole, that dark abyss", a=(24.5, 26.95), facts=["f2"],
      shots=[(24.5, 2.45, 477, "틈 근접(손이 틈을 누름) — 말하는 사람 화면 밖(피치 해설), 화면=소리 같은 원본 시각")], fx="빨간 점선 원(틈) — 벤치 10~12초 자리"),
 dict(id="N2", fn="기존 불편(나레)", kind="N", text="폰이며 열쇠며 감자튀김까지, 삼켜 버리는 그 틈 때문에",
      tts="폰이며 열쇠며 감자튀김까지 삼켜 버리는 그 틈 때문에", facts=["f2"],
      shots=[(33.95, 1.5, 477, "콘솔 칸 감자튀김·틈에 손이 들어가는 근접"), (59.9, 1.5, 477, "무대 좌석 세트 옆 창업자 둘")]),
 dict(id="O3", fn="기존 불편(원음, 웃음 포인트)", kind="O", text="무릎 꿇고, 엉덩이 치켜들고", orig="Gotten on their hands and knees, butt up in the air", a=(45.45, 47.7), facts=["f3"],
      shots=[(45.45, 2.25, 900, "창업자가 좌석 옆에 몸 숙여 시늉(무대 넓게)")]),
 dict(id="N3", fn="시연(설치)", kind="N", text="벨트 꽂는 자리 홈에 끼워 두기만 하면, 바닥으로 안 빠진다는데",
      tts="벨트 꽂는 자리 홈에 끼워 두기만 하면 바닥으로 안 빠진다는데", facts=["f4"],
      shots=[(75.6, 1.5, 477, "창업자가 제품(홈 있는 막대)을 들어 보임"), (80.2, 1.5, 477, "손이 제품을 좌석 틈에 끼움(근접)")], fx="분홍 화살표(벨트 홈) — 벤치 14초 자리"),
 dict(id="O4", fn="시연(원음)", kind="O", text="의자가 어디로 가든, 드롭스탑이 따라가요", orig="Wherever your seat goes, Drop Stop follows", a=(86.9, 90.1), facts=["f4"],
      shots=[(86.9, 3.2, 477, "좌석이 앞뒤로 움직여도 제품이 따라감(근접)")]),
 dict(id="O5", fn="숫자(원음)", kind="O", text="26만 개 넘게 팔았어요", orig="We've actually sold over 260,000 units", a=(111.15, 113.37), facts=["f5"],
      shots=[(111.15, 2.22, 477, "창업자 둘(말하는 본인) — 113.5초 컷 전까지(원음도 113.45에서 끊음, 'units' 뺌)")]),
 dict(id="N4", fn="숫자(나레)", kind="N", text="만드는 데 4달러 드는 걸, 20달러 가까이 받고 판다는데",
      tts="만드는 데 사 달러 드는 걸 이십 달러 가까이 받고 판다는데", facts=["f5"],
      shots=[(134.2, 1.5, 477, "로리(원가 묻는 장면 앞, 소리 끔)"), (142.2, 1.5, 477, "창업자 둘이 설명(무대)")]),
 dict(id="N5", fn="투자자 반응(나레)", kind="N", text="투자자 둘은 빠졌는데, 케빈은 지분 말고",
      tts="투자자 둘은 빠졌는데 케빈은 지분 말고", facts=["f6", "f7"],
      shots=[(187.0, 2.0, 477, "하차한 투자자(이름 화면 글자 없음, 하차 발언 장면)")]),
 dict(id="O6", fn="지분 경쟁(원음)", kind="O", text="이거 하나 팔릴 때마다, 2달러씩 받을게요", orig="Every time you sell one of these foam weenies, I get two dollars back", a=(198.3, 203.6), facts=["f7"],
      shots=[(198.3, 5.3, 520, "케빈(말하는 본인), 200초부터 제품을 들어 보임")]),
 dict(id="N6", fn="지분 경쟁(나레)", kind="N", text="로리는 백만장자로 만들어 주겠다며, 30만 달러에 지분 20%를 불렀고",
      tts="로리는 백만장자로 만들어 주겠다며 삼십만 달러에 지분 이십 퍼센트를 불렀고", facts=["f8"],
      shots=[(240.0, 1.3, 477, "투자자석 넓게(케빈·로리 등)"), (217.05, 1.3, 300, "로리 얼굴(말하는 중, 소리 끔)"), (251.35, 1.3, 300, "로리 얼굴(다른 장면)")], fx="날개 돈다발 이모지 — 벤치 40초 자리"),
 dict(id="N7", fn="결말+후일담(나레)", kind="N", text="결국 로리 손을 잡았고, 5년 뒤 매출은",
      tts="결국 로리 손을 잡았고 오 년 뒤 매출은", facts=["f9"],
      shots=[(275.9, 2.1, 477, "로리와 창업자 둘이 걸어 들어옴(시즌9 후일담)")]),
 dict(id="O8", fn="후일담(원음)", kind="O", text="2,800만 달러 찍었어요", orig="We've hit 28 million", a=(316.5, 318.33), facts=["f9"],
      shots=[(316.5, 1.83, 520, "창업자 둘 인터뷰(말하는 본인)")]),
 dict(id="N9", fn="후일담(나레, 끝)", kind="N", text="LA 경찰이 석 달간 사고 0건이라며, 순찰차 3천 대에 달기로 했다고",
      tts="엘에이 경찰이 석 달간 사고 영 건이라며 순찰차 삼천 대에 달기로 했다고", facts=["f10"],
      shots=[(297.0, 1.35, 477, "경찰 본부 회의(넓게)"), (323.35, 1.35, 477, "경찰들과 하이파이브(로리 포함)"), (310.35, 1.6, 477, "경찰들과 본부 밖으로 걸어 나옴(끝 컷)")]),
]

t = 0.0
shots, lines = [], []
for ln in L:
    if ln["kind"] == "N":
        est = round(len(re.sub(r"[\s,.]", "", ln["tts"])) / CPS, 2)
    else:
        est = round(ln["a"][1] - ln["a"][0], 2)
    pic = round(sum(s[1] for s in ln["shots"]), 2)
    dur = pic
    if ln["kind"] == "N" and est > pic + 0.05: print("나레 넘침", ln["id"], est, pic)
    t0 = t
    tt = t
    for k, (ss, d, x, ours) in enumerate(ln["shots"]):
        d2 = d if k < len(ln["shots"]) - 1 else round(dur - (tt - t0), 2)
        sh = {"i": len(shots), "line": ln["id"], "src": SRC, "url": URL, "src_date": "CNBC Ambition 유튜브(Shark Tank 시즌4 2013 + 시즌9 후일담)",
              "ss": ss, "dur": d2, "src_span": [ss, round(ss + d2, 2)], "kind": "원본재편집", "box": BOX, "src_crop": [x, 0, W, H],
              "res": "1920x1080", "scale": round(1052 / H, 3), "ours": ours,
              "why": (f"원음 '{ln['orig']}' — 소리·화면 같은 시각" if ln["kind"] == "O" else f"나레 '{ln['text'][:24]}' — 원본 소리 끔") + " · 아래 CNBC 띠(y≥950) 크롭 밖",
              "mute": ln["kind"] == "N", "t_final": [round(tt, 2), round(tt + d2, 2)]}
        if ln["kind"] == "O":
            sh["audio_src"] = SRC; sh["audio_ss"] = ln["a"][0]; sh["audio_dur"] = est
        if ln.get("fx") and k == 0:
            sh["fx"] = ln["fx"]
        shots.append(sh)
        tt += d2
    t = t0 + dur
    lines.append({"id": ln["id"], "fn": ln["fn"], "kind": "원음" if ln["kind"] == "O" else "나레", "text": ln["text"],
                  **({"tts": ln["tts"]} if ln["kind"] == "N" else {"orig_en": ln["orig"], "orig_span": list(ln["a"])}),
                  "facts": ln["facts"], "est_sec": dur, "t_est": [round(t0, 2), round(t, 2)], **({"fx": ln["fx"]} if ln.get("fx") else {})})

S = {"topic": "Drop Stop(운전석·콘솔 틈 메우개) — 샤크탱크 시즌4 피치 → 로리 30만 달러/20% 딜 → 5년 뒤 2,800만 달러·LA 경찰 3천 대",
     "bench": {"id": "QMJtjJz4M6w", "channel": "해외쇼츠 @foreignshowshow", "title": "홍수 막아주는 모래 주머니?!", "dur": 50.5, "views": 12000000},
     "titles": {"line1": "운전석 틈 블랙홀을", "line2": "막아버린 발명품?!", "rule": "1줄 노랑·2줄 흰, 끝 '~?!'(벤치 띠 그대로). '블랙홀' = 피치 원음 'that black hole'(f2)"},
     "facts": facts,
     "final": {"lines": lines, "est_total": round(t, 2), "narr_cps_assumed": CPS, "cps_target": 8.2,
               "voice": "지훈 tc_61f0859907085fc68561c9a1 — 반말 전언체(TTS 는 페이블 OK 뒤 1회)"},
     "voice": {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈", "engine": "typecast", "speed": 1.25, "why": "채널 공통 성우(벤치 나레 f0 116Hz 실측 최근접, 페이블 10-18)"},
     "notes": ["원음 줄(O*) = 영어 원음 + 한국어 번역 자막(받아쓰기 근거 근거.md §2)", "사람 이름은 화면 글자로 확인된 케빈·로리만(창업자 이름띠는 누가 누군지 갈리지 않아 안 씀)",
               "시각은 추정 — TTS 뒤 확정"]}
M = {"_note": "샥탬스토리 3편 Drop Stop — 재료 계획(TTS·렌더 전). 창 1080x1052 y434(벤치 뜯기 layout). src_crop 965x940(위 0~940) = 아래 CNBC 로고·'SHARK TANK SUN-THU 8P ET'·'CNBC.COM/CHANNELFINDER'·'SEASON 9 UPDATE' 띠(y≥950) 제외. 이름띠(5~16·205~211·234~238·288~289·293~294초) 구간은 안 씀.",
     "cand_dir": "C:/숏템_칼카피/foreignshowshow/3편_DropStop/src",
     "narration": "타입캐스트 지훈 tc_61f0859907085fc68561c9a1 반말 전언체(페이블 OK 뒤 1회)",
     "sources": {"ME64bRiQi24": {"채널": "CNBC Ambition", "제목": "Drop Stop Fills The Gap | Shark Tank: How It Started | CNBC Prime", "해상도": "1920x1080 29.97fps", "길이": 330.65, "소리": "140-7 en-US original"}},
     "overlays_bench": ["제목 띠 2줄(1줄 노랑·2줄 흰 '~?!')", "0초 빨간 원(투자자 얼굴)", "빨간 점선 원(10~12초)", "분홍 화살표(14초)", "날개 돈다발 이모지(40초)", "색 필터 번쩍임(벤치 시각 미측정)", "로고 자리 = '샥탬스토리'"],
     "shots": shots}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
print("total", round(t, 2), "shots", len(shots))
for s in shots:
    print(s["i"], s["line"], s["ss"], s["dur"], s["t_final"])
# 검사: 같은 소스 ±3초
sp = sorted((s["src_span"][0], s["src_span"][1], s["i"]) for s in shots)
for a, b in zip(sp, sp[1:]):
    if b[0] - a[1] < 3.0:
        print("±3초 걸림", a, b)
print("최소 컷", min(s["dur"] for s in shots), "중앙", sorted(s["dur"] for s in shots)[len(shots) // 2])
