# -*- coding: utf-8 -*-
"""4편 Spikeball 재료.json 생성원 — 줄↔컷 계획(shark/render.py 입력 꼴). python shots_src.py → 재료.json (관제 097)

원음 컷 규칙(페이블 10-18, 1편 확정): 화면 = 소리와 같은 원본 시각(sync 0) · 그 시각에 화면에 있는 사람 = 원본 방송 편집 그대로.
소스 파일: cnbc15a.mp4 = CNBC vyvIN8J_vj0 원본 15~125초(파일 0초 = 원본 15초), cnbc170a.mp4 = 원본 170~337초(파일 0초 = 170초).
  두 파일 모두 영상 = 구간 받기 mp4(소리 깨짐) + 소리 = 같은 클립 m4a 통째에서 같은 원본 시각으로 다시 붙임(상호상관 오프셋 0.000초 실측).
"""
import json
from pathlib import Path

CAND = "C:/숏템_칼카피/foreignshowshow/4편_Spikeball/src"
FILES = {"c15": ("cnbc15a.mp4", 15.0), "c170": ("cnbc170a.mp4", 170.0), "demo76": ("demo76_6pC9CovZuBY.mp4", 0.0)}
URL = {"c15": "https://www.youtube.com/watch?v=vyvIN8J_vj0", "c170": "https://www.youtube.com/watch?v=vyvIN8J_vj0", "demo76": "https://www.youtube.com/watch?v=6pC9CovZuBY"}
CROP = [406, 0, 1109, 1080]   # 창 1080x1052 비율, 0.974배(확대 없음)


def cn(t):
    return "c15" if t < 170 else "c170"


# (줄, 소스키(None=cnbc 자동), 원본 시작, 원본 끝, 보이는 것, 왜, 꾸밈, 원음?, crop)
S = [
 ("L1", None, 220.45, 222.20, "검은 정장 대머리 투자자(이름 자막 없음 — 불명) 정면, 말하는 본인", "원음 'a ball in a net' — 같은 시각 말하는 본인(sync 0). 벤치 0초 투자자 반응 자리", "빨간 원(얼굴)", True, None),
 ("L2", "demo76", 3.00, 4.20, "야자수 잔디밭에서 4명이 노란 그물 둘레로 경기", "'공 하나랑 그물 하나로'", "초록 화살표(아래, 그물)", False, None),
 ("L2", "demo76", 15.50, 16.70, "해변 모래 위 4명 경기, 공이 떠 있음", "'한 해 140만 달러어치를'", None, False, None),
 ("L2", "demo76", 31.60, 32.80, "넓은 잔디 운동장 4명 경기", "'판 게임이 있는데'", None, False, None),
 ("L3", None, 32.60, 34.02, "창업자가 노란 공을 두 손으로 들고 돌림(말하는 본인의 손·가슴, 같은 시각)", "원음 'All you need is this ball, that net,' — 원본 편집 그대로 sync 0", None, True, None),
 ("L3", None, 34.02, 37.10, "무대 — 노란 유니폼 선수 2명·대형 로고 앞에서 말하는 창업자(오른쪽)", "원음 '…one of these backpacks, and you can take it absolutely anywhere' sync 0 — 왼쪽 아래 CNBC.COM 글자(x200~800) 크롭 x811~ 로 뺌", None, True, [811, 0, 1109, 1080]),
 ("L4", "demo76", 22.60, 23.90, "흰 실내 코트, 4명이 그물에 공을 내리침", "'그물에 공을 튕겨 서브하면'", "빨간 점선 원(그물)", False, None),
 ("L4", None, 83.00, 84.20, "샤크탱크 무대 위 노란/검은 유니폼 4명 시범 경기(와이드)", "'상대는 세 번 안에'", None, False, None),
 ("L4", "demo76", 27.00, 28.20, "흰 실내 코트, 선수가 공을 그물로 내리꽂음", "'다시 내리꽂아야 하고'", None, False, None),
 ("L5", None, 20.95, 24.20, "창업자(0:05 이름 자막 CHRIS RUDER) 정면, 노란 공 들고 말하는 본인", "원음 'very easy to learn, but really, really difficult to master' sync 0", None, True, None),
 ("L6", "demo76", 38.30, 39.80, "눈 덮인 숲 속 4명이 경기", "'편 가를 필요도 없어서, 눈밭이든'", "분홍 화살표(그물)", False, None),
 ("L6", "demo76", 10.40, 11.90, "분수대 물 속에서 4명이 경기", "'물속이든 다 된다고'", None, False, None),
 ("L7", None, 176.00, 177.40, "Spikeball 상자와 노란 공 2개 근접", "'올해만 2만 9천 개를 팔았다는데'", None, False, None),
 ("L7", None, 185.40, 186.85, "갈색 양복 투자자(데이먼드 — 255초 화면 자막) 듣는 얼굴", "'만드는 데 드는 돈은'", None, False, None),
 ("L8", None, 197.50, 199.30, "창업자 정면, 답하는 본인", "원음 'A little over fourteen' sync 0 — 앞 질문·'29,000 units'(화면이 투자자·상자)는 원음에서 빼고 나레로", None, True, None),
 ("L9", None, 192.40, 193.80, "금발 여성 투자자(이름 자막 없음) 듣는 얼굴", "'그걸 59달러 99센트에'", None, False, None),
 ("L9", "demo76", 52.00, 53.30, "사막 급수탑 앞 4명 경기", "'팔고 있었는데'", None, False, None),
 ("L10", None, 240.00, 242.30, "갈색 양복 투자자(데이먼드) 손 모으고 말함", "'이때 데이먼드가 50만 달러를 내걸면서'", None, False, None),
 ("L11", None, 249.37, 253.75, "투자자석 와이드 — 데이먼드가 손짓하며 말함(끝 0.4초 = 원본 편집 그대로 창업자 측면 컷)", "원음 '(I would be) interested in, for 25% of the whole company' sync 0 — 253.35 에서 자르면 'company' 가 잘려 원본 컷 경계를 0.4초 넘김", "날개 돈다발 이모지", True, None),
 ("L12", None, 269.60, 270.97, "무대 와이드 — 시범 선수 4명과 말하는 창업자(멀리)", "원음 'Would you consider 500k' sync 0", None, True, None),
 ("L12", None, 270.97, 273.60, "창업자 정면, 말하는 본인", "원음 '…at 15 percent?' sync 0", None, True, None),
 ("L13", None, 303.70, 305.75, "투자자석 와이드(데이먼드·대머리 투자자)", "원음 '(is) one of those moments that you can lose it all' sync 0 — 화자 이름 자막 없음", None, True, None),
 ("L14", None, 319.70, 322.30, "갈색 양복 투자자(데이먼드) 박수", "'결국 20%에 손을 잡으면서 투자가 성사됐는데'", None, False, None),
 ("L15", None, 215.75, 217.20, "창업자 얼굴 근접, 고개 숙임", "'알고 보니 방송이 나가기도 전에'", None, False, None),
 ("L15", None, 291.40, 292.90, "창업자 정면, 굳은 표정", "'이 딜이 깨졌다고'", None, False, None),
 ("L16", None, 264.00, 265.40, "창업자 정면", "'스파이더맨 세트를 내자는 말에'", None, False, None),
 ("L16", None, 282.00, 283.40, "창업자 정면", "'장난감처럼 보일까 봐'", None, False, None),
 ("L16", None, 287.00, 288.30, "창업자 정면", "'창업자가 반대했다는 거야'", None, False, None),
 ("L17", "demo76", 44.00, 45.30, "호숫가 모래밭 4명 경기(산 배경)", "'그래도 2019년엔 한 해'", None, False, None),
 ("L17", "demo76", 58.60, 60.40, "바위산 앞 사막 4명 경기(끝 컷 ≥1.5초)", "'1,900만 달러를 버는 회사가 됐다고'", None, False, None),
]


def build():
    shots, t = [], 0.0
    for i, (ln, key, a, b, see, why, fx, orig, crop) in enumerate(S):
        key = key or cn(a)
        f, off = FILES[key]
        d = round(b - a, 2)
        c = crop or CROP
        s = {"i": i, "line": ln, "src": f, "url": URL[key], "ss": round(a - off, 3), "dur": d, "src_orig_span": [a, b],
             "t_final_est": [round(t, 2), round(t + d, 2)], "res": "1920x1080", "src_crop": c, "scale": round(1080 / c[2], 3),
             "ours": see, "why": why, "fx": fx, "mute": not orig}
        if orig:
            s["audio_src"] = f
            s["audio_span"] = [round(a - off, 3), round(b - off, 3)]
        shots.append(s)
        t += d
    return shots


if __name__ == "__main__":
    shots = build()
    doc = {"_note": "샥탬스토리 4편 Spikeball 재료 — shark/render.py 입력. 창 [0,434,1080,1052](대본 bench.window). ss·audio_span = 파일 시각(src_orig_span = 원본 클립 시각). 원음 컷은 화면=소리 같은 시각(sync 0).",
           "cand_dir": CAND,
           "sources": {"cnbc15a": {"원본": "CNBC Ambition vyvIN8J_vj0 'The Sharks Couldn't Score With Spikeball | Shark Tank MISSES | CNBC Prime' 2022-12-08", "구간": "원본 15~125초", "해상도": "1920x1080"},
                       "cnbc170a": {"원본": "같은 클립", "구간": "원본 170~337초", "해상도": "1920x1080"},
                       "demo76_6pC9CovZuBY": {"원본": "Spikeball 공식 'Spikeball: Rally Anywhere' 2022-04-19", "해상도": "1920x1080", "남의 글자": "0~2·67~75초 글자 안 씀"}},
           "window": [1080, 1052], "shots": shots,
           "effects": [
               {"line": "L1", "kind": "red_circle", "at": [500, 734], "size": 340, "stroke": 8, "t": [0.0, 0.6], "why": "벤치 0.0~0.6초 투자자 얼굴 빨간 원 — 대머리 투자자 얼굴 중심(창 500,300)"},
               {"line": "L11", "kind": "emoji", "emoji": "💸", "at": [900, 1290], "size": 220, "t": [0.3, 2.8], "why": "벤치 38.6~41.1초 제안 순간 날개 돈다발 — 얼굴 안 가리는 오른쪽 아래(손 자리)"}],
           "effects_not_drawable": ["L2 초록 화살표(아래) 그물", "L4 빨간 점선 원 그물", "L6 분홍 화살표(위) 그물 — 엔진 overlay_png 가 red_circle·emoji 만 그림(엔진 요청)"],
           "check": {"shots": len(shots), "est_total": shots[-1]["t_final_est"][1]}}
    Path(__file__).with_name("재료.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(shots), shots[-1]["t_final_est"][1])
