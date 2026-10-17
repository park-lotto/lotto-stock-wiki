# -*- coding: utf-8 -*-
"""4편 Spikeball 재료.json 생성원 — 줄↔컷 계획(TTS 전, 말속도 8자/초 추정). python shots_src.py → 재료.json (관제 097)"""
import json
from pathlib import Path
SRC = "C:/숏템_칼카피/foreignshowshow/4편_Spikeball/src"
C1 = ("cnbc_vyvIN8J_vj0_15.mp4", 15.0)    # 파일 0초 = 원본 15초
C2 = ("cnbc_vyvIN8J_vj0_170.mp4", 170.0)  # 파일 0초 = 원본 170초
D = ("demo76_6pC9CovZuBY.mp4", 0.0)
URL = {"cnbc": "https://www.youtube.com/watch?v=vyvIN8J_vj0", "demo76": "https://www.youtube.com/watch?v=6pC9CovZuBY"}
CROP = [406, 0, 1109, 1080]   # 창 1080x1052 비율, 1920x1080 에서 0.974배(확대 없음)

def C(t0):
    return C1 if t0 < 170 else C2

# (줄, 소스키, 원본 시작, 원본 끝, 보이는 것, 왜, 꾸밈, 원음(소리 원본 구간) or None, crop)
S = [
 ("L1", "cnbc", 220.45, 222.20, "검은 정장 대머리 투자자(이름 자막 없음 — 이름 불명) 정면, 말하는 입", "원음 'a ball in a net'(받아쓰기 3/3) — 벤치 0초 투자자 반응 자리. 220.05 시작은 앞말 'for' 끝이 걸려 220.45 로 당김", "빨간 원(얼굴)", [220.45, 222.20], None),
 ("L2", "demo76", 3.00, 4.20, "야자수 잔디밭에서 4명이 노란 그물 둘레로 경기", "'공 하나랑 그물 하나로'", "초록 화살표(아래, 그물)", None, None),
 ("L2", "demo76", 15.50, 16.70, "해변 모래 위 4명 경기, 공이 떠 있음", "'한 해 140만 달러어치를'", None, None, None),
 ("L2", "demo76", 31.60, 32.80, "넓은 잔디 운동장 4명 경기", "'판 게임이 있는데'", None, None, None),
 ("L3", "cnbc", 32.60, 34.00, "창업자가 노란 공을 두 손으로 들고 돌림(가슴 근접, 창업자 본인 손)", "원음 'All you need is this ball, that net,'(창업자 본인 말 — 화면도 본인)", None, [32.60, 34.00], None),
 ("L3", "cnbc", 34.05, 37.10, "무대 — 노란 유니폼 선수 2명·대형 Spikeball 로고 앞에서 말하는 창업자(오른쪽)", "원음 '…one of these backpacks, and you can take it absolutely anywhere'(받아쓰기 2모델 일치) — 왼쪽 아래 CNBC.COM 글자(x200~800)는 크롭 x811~ 로 뺌", None, [34.05, 37.10], [811, 0, 1109, 1080]),
 ("L4", "demo76", 22.60, 23.90, "흰 실내 코트, 4명이 그물에 공을 내리침", "'그물에 공을 튕겨 서브하면'", "빨간 점선 원(그물)", None, None),
 ("L4", "cnbc", 83.00, 84.20, "샤크탱크 무대 위 노란/검은 유니폼 4명 시범 경기(와이드)", "'상대는 세 번 안에'", None, None, None),
 ("L4", "demo76", 27.00, 28.20, "흰 실내 코트, 선수가 공을 그물로 내리꽂음", "'다시 내리꽂아야 하고'", None, None, None),
 ("L5", "cnbc", 20.95, 24.20, "검은 Spikeball 티셔츠 창업자(0:05 이름 자막 CHRIS RUDER) 정면, 노란 공 들고 말함", "원음 'very easy to learn, but really, really difficult to master'(받아쓰기 4/4)", None, [20.95, 24.20], None),
 ("L6", "demo76", 38.30, 39.80, "눈 덮인 숲 속 4명이 경기", "'편 가를 필요도 없어서, 눈밭이든'", "분홍 화살표(그물)", None, None),
 ("L6", "demo76", 10.40, 11.90, "분수대 물 속에서 4명이 경기", "'물속이든 다 된다고'", None, None, None),
 ("L7", "cnbc", 192.40, 193.84, "금발 여성 투자자(이름 자막 없음) 듣는 얼굴 — 원본 방송 편집 그대로", "원음 'We've sold 29,000 units.'(창업자 목소리) — 소리 192.40~199.30 한 덩어리, 받아쓰기 2모델 화자 2명", None, [192.40, 193.84], None),
 ("L7", "cnbc", 193.90, 196.00, "Spikeball 상자·노란 공 근접", "원음 이어서 '…units. And how much did they cost to make?'", None, [193.90, 196.00], None),
 ("L7", "cnbc", 196.05, 197.45, "갈색 양복 투자자(데이먼드 — 255초 화면 자막으로 확인) 앉아 있는 얼굴", "원음 질문 끝 — 질문한 사람 이름은 자막에 안 씀", None, [196.05, 197.45], None),
 ("L7", "cnbc", 197.50, 199.30, "창업자 정면 답함", "원음 'A little over fourteen'", None, [197.50, 199.30], None),
 ("L8", "cnbc", 176.00, 177.30, "Spikeball 상자와 노란 공 2개 근접", "'그걸 59달러 99센트에'", None, None, None),
 ("L8", "cnbc", 185.40, 186.85, "갈색 양복 투자자(데이먼드) 듣는 얼굴", "'팔고 있었는데' — 창업자 컷(182)은 L7 끝 창업자 컷과 A-B-A 가 돼 교체", None, None, None),
 ("L9", "cnbc", 240.00, 242.30, "갈색 양복 투자자(데이먼드) 손 모으고 말함", "'이때 데이먼드가 50만 달러를 내걸면서'", None, None, None),
 ("L10", "cnbc", 249.40, 253.35, "투자자석 와이드 — 데이먼드가 손짓하며 말함", "원음 '(I would be) interested in, for 25% of the whole company' — 소리 249.40~253.80(253.35 에서 자르면 '...of the whole' 로 끊김, 받아쓰기 2/2). 소리 꼬리 0.45초는 다음 컷(L11 와이드) 위로 넘김", "날개 돈다발 이모지", [249.30, 253.80], None),
 ("L11", "cnbc", 269.15, 270.95, "무대 와이드 — 시범 선수 4명과 창업자(멀리, 입 모양 작음)", "처음 0.45초 = L10 원음 꼬리 'company', 이어 원음 'Would you consider 500k'(창업자, 소리 269.60~)", None, [269.60, 270.95], None),
 ("L11", "cnbc", 271.00, 273.60, "창업자 정면 말함", "원음 '…at 15 percent?'(273.4 에서 자르면 'p-' 로 끊김 → 273.6)", None, [271.00, 273.60], None),
 ("L12", "cnbc", 303.70, 305.75, "투자자석 와이드(데이먼드·대머리 투자자, 입 모양 작음)", "원음 '(is) one of those moments that you can lose it all'(받아쓰기 4/4)", None, [303.70, 305.75], None),
 ("L13", "cnbc", 319.70, 322.30, "갈색 양복 투자자(데이먼드) 박수", "'결국 20%에 손을 잡으면서 투자가 성사됐는데'", None, None, None),
 ("L14", "cnbc", 215.75, 217.20, "창업자 얼굴 근접, 고개 숙임", "'알고 보니 방송이 나가기도 전에'", None, None, None),
 ("L14", "cnbc", 291.40, 292.90, "창업자 정면, 굳은 표정", "'이 딜이 깨졌다고'", None, None, None),
 ("L15", "cnbc", 264.00, 265.40, "창업자 정면 말함", "'스파이더맨 세트를 내자는 말에'", None, None, None),
 ("L15", "cnbc", 282.00, 283.40, "창업자 정면 말함", "'장난감처럼 보일까 봐'", None, None, None),
 ("L15", "cnbc", 287.00, 288.30, "창업자 정면", "'창업자가 반대했다는 거야'", None, None, None),
 ("L16", "demo76", 44.00, 45.30, "호숫가 모래밭 4명 경기(산 배경)", "'그래도 2019년엔'", None, None, None),
 ("L16", "demo76", 51.50, 52.80, "사막 급수탑 앞 4명 경기", "'한 해 1,900만 달러를'", None, None, None),
 ("L16", "demo76", 58.60, 60.40, "바위산 앞 사막 4명 경기(끝 컷 ≥1.5초)", "'버는 회사가 됐다고'", None, None, None),
]

def build(crops=None):
    shots = []
    t = 0.0
    for i, (ln, key, a, b, see, why, fx, orig, crop) in enumerate(S):
        if key == "cnbc":
            f, off = C(a)
        else:
            f, off = D
        d = round(b - a, 2)
        shots.append({"i": i, "line": ln, "src": f"{SRC}/{f}", "url": URL[key], "src_orig_span": [a, b], "ss": round(a - off, 2), "dur": d,
                      "t_final_est": [round(t, 2), round(t + d, 2)], "res": "1920x1080", "src_crop": (crops or {}).get(i) or crop or CROP,
                      "scale": round(1080 / ((crops or {}).get(i) or crop or CROP)[2], 3), "ours": see, "why": why, "fx": fx,
                      "audio": ({"kind": "원음", "src_span": orig, "ss": round(orig[0] - off, 2)} if orig else {"kind": "나레(원음 무음)"})})
        t += d
    return shots

if __name__ == "__main__":
    import sys
    crops = {}
    p = Path(__file__).with_name("crops.json")
    if p.exists():
        crops = {int(k): v for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    shots = build(crops)
    doc = {"_note": "샥탬스토리 4편 Spikeball 재료 계획 — TTS·렌더 전. 창 1080x1052(벤치 QMJtjJz4M6w 창 [0,434,1080,1052]). 시각은 나레 8자/초 추정 — TTS 뒤 줄 끝에 맞춰 컷 길이 재조정. 원음 컷은 audio.ss(파일 기준)부터 원본 소리.",
           "sources": {"vyvIN8J_vj0": {"채널": "CNBC Ambition", "제목": "The Sharks Couldn't Score With Spikeball | Shark Tank MISSES | CNBC Prime", "업로드": "2022-12-08", "해상도": "1920x1080", "길이": 351,
                                       "받은 구간": "15~125초(cnbc_vyvIN8J_vj0_15.mp4) · 170~337초(cnbc_vyvIN8J_vj0_170.mp4)", "남의 글자": "왼쪽 아래 NBC 공작 로고(x<70, 크롭 밖) · 하단 이름/제안 자막(255~260·274~281·310~314초 등 — 그 구간 안 씀) · 35~50초 CNBC.COM 글자(안 씀) · 324~334초 결말 글자 카드(안 씀)"},
                       "6pC9CovZuBY": {"채널": "Spikeball(공식)", "제목": "Spikeball: Rally Anywhere", "업로드": "2022-04-19", "해상도": "1920x1080", "길이": 76, "남의 글자": "0~2초·67~75초 'Rally ANYWHERE' 글자 — 안 씀"}},
           "window": [0, 434, 1080, 1052], "shots": shots,
           "check": {"shots": len(shots), "est_total": shots[-1]["t_final_est"][1]}}
    Path(__file__).with_name("재료.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(shots), shots[-1]["t_final_est"][1])
