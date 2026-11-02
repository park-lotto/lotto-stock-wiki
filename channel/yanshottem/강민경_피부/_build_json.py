# -*- coding: utf-8 -*-
"""강민경 포트레 스킨 틴트 편 — 대본.json·재료.json·frame 을 한 곳에서 만든다(손 수치는 근거.md §2·§4 실측). 관제 097.

    PYTHONIOENCODING=utf-8 py channel/yanshottem/강민경_피부/_build_json.py [--narr 2.6,2.5,1.5]   # TTS 뒤 나레 줄 실측 길이(초)
"""
import json
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parents[2]
URL = "https://www.youtube.com/watch?v=WmEjrZFVRB4"
SRC = "kmk_WmEjrZFVRB4.mp4"
SRC_DATE = "걍밍경 유튜브 2026.02.20"
CPS = 8.3      # 추정 말속도(미나 1.35) — TTS 뒤 --narr 로 실측 길이를 넣는다
LEAD = 0.08
END_TAIL = 0.30
BENCH_DUR = 19.0
N = [
    {"id": "N1", "fn": "나레 다리 1(인물·제품 정체 ~라는데)",
     "text": "강민경이, 일 년 동안, 포트레 팀과 만든, 스킨 틴트라는데",
     "tts": "강민경이 일 년 동안 포트레 팀과 만든 스킨 틴트라는데",
     "caps": ["강민경이 일 년 동안", "포트레 팀과 만든", "스킨 틴트라는데"], "facts": ["f1", "f2"]},
    {"id": "N2", "fn": "나레 다리 2(만든 뜻 → 목 시험)",
     "text": "들뜸 없는 제품을, 만들자고 했다는데, 목에도 발라 보더니",
     "tts": "들뜸 없는 제품을 만들자고 했다는데 목에도 발라 보더니",
     "caps": ["들뜸 없는 제품을", "만들자고 했다는데", "목에도 발라 보더니"], "facts": ["f3", "f4"]},
    {"id": "N3", "fn": "나레 마무리(~라네요 전언)",
     "text": "실물로 보면, 티가 확 난다네요",
     "tts": "실물로 보면 티가 확 난다네요.",
     "caps": ["실물로 보면", "티가 확 난다네요"], "facts": ["f6"]},
]
# 원음 = 강민경 본인 말만(편집 자막 흰색 + 참고 목소리 대조 + 받아쓰기 2회, 근거.md §2). 구간 안 상대 시각 = 원본 그대로
O = [
    {"id": "O1", "spans": [[638.30, 642.95]], "said": "너무 신기하다 이거 진짜 (쉼) 이거는 카메라로도 무조건 비포 애프터 나오겠다",
     "caps": [["너무 신기하다 이거 진짜", 0.0, 1.75], ["이거는 카메라로도", 1.75, 3.05], ["무조건 비포 애프터", 3.05, 3.95], ["나오겠다", 3.95, 4.65]],
     "facts": ["f5"]},
    {"id": "O2", "spans": [[536.62, 538.55]], "said": "아침에 이렇게 막 급하게 바르고 나가도",
     "caps": [["아침에 이렇게", 0.0, 0.85], ["막 급하게 바르고 나가도", 0.85, 1.93]],
     "facts": ["f3"]},
    {"id": "O3", "spans": [[652.25, 656.12]], "said": "진짜 찍길 잘했다 (쉼) 목 안 찍고 넘어갔으면 이거 못 믿으셨겠어",
     "caps": [["진짜 찍길 잘했다", 0.0, 1.45], ["목 안 찍고 넘어갔으면", 1.45, 2.7], ["이거 못 믿으셨겠어", 2.7, 3.87]],
     "facts": ["f5"]},
]
# TTS 실측(10-17): 미나 1회 narr_mina.mp3(11.92초, 1.0) → atempo 1.55 narr_t155.wav(7.70초). 말 구간(silencedetect −40dB)
NARR_SLICE = {"N1": [0.00, 2.56], "N2": [2.98, 5.85], "N3": [6.13, 7.70]}
narr_real = [b - a for a, b in NARR_SLICE.values()]
if "--narr" in sys.argv:
    narr_real = [float(x) for x in sys.argv[sys.argv.index("--narr") + 1].split(",")]
for o in O:
    o["dur"] = round(sum(b - a for a, b in o["spans"]), 2)
for k, n in enumerate(N):
    n["chars"] = len(n["tts"].replace(" ", "").replace(".", ""))
    n["est_sec"] = round(narr_real[k] if narr_real else n["chars"] / CPS, 3)
# 순서: O1 → N1 → O2 → N2 → O3 → N3 (만템 결: 원음으로 연다·'~라는데' 다리·'~라네요' 마무리)
seq = [("O", 0), ("N", 0), ("O", 1), ("N", 1), ("O", 2), ("N", 2)]
t, blocks, caps = 0.0, [], []
for kind, i in seq:
    if kind == "O":
        o = O[i]
        a = t
        b = a + o["dur"]
        o["t_final"] = [round(a, 3), round(b, 3)]
        for txt, x0, x1 in o["caps"]:
            caps.append({"t0": round(a + x0, 3), "t1": round(a + x1, 3), "text": txt, "kind": "원음"})
    else:
        n = N[i]
        a = t + LEAD
        b = a + n["est_sec"]
        n["t_final"] = [round(a, 3), round(b, 3)]
        w = [len(c.replace(" ", "")) for c in n["caps"]]
        x = a
        for c, ww in zip(n["caps"], w):
            y = x + (b - a) * ww / sum(w)
            caps.append({"t0": round(x, 3), "t1": round(y, 3), "text": c, "kind": "나레"})
            x = y
    blocks.append({"block": (O[i] if kind == "O" else N[i])["id"], "t": [round(a, 3), round(b, 3)]})
    t = b
dur = round(t + END_TAIL, 3)
facts = {
    "f1": {"text": "원본 제목 'B형 독감, 인생 톤업크림, 해리언니 생파' · 업로드 2026-02-20 · 채널 걍밍경(강민경 본인 채널) · 설명란 '포트레 워터 핏 스킨 틴트'", "url": URL, "kind": "제목·메타·설명란"},
    "f2": {"text": "본인 말 5:44~5:52 '오늘은 장장 1년 동안 포트레 팀과 우리 영은 부원장님이랑 함께 만든 워터 핏 스킨 틴트가 드디어 샘플이 완성이 돼서'(편집 자막 흰색 = 강민경)", "url": URL, "kind": "본인 말(편집 자막)"},
    "f3": {"text": "본인 말 8:56.6~8:59.4 '아침에 이렇게 막 급하게 바르고 나가도 들뜸 없이 하자'(원음은 8:58.55 '나가도'까지) · 편집 자막 '아침에 이렇게 막 급하게 바르고 나가도 / 들뜸 없는 제품을 만들자'(흰색 = 강민경). 뒤 '들뜸 없이 하자'는 받아쓰기가 갈려(어떻게 줄까/줄 서지 않고) 원음에서 빼고 나레로 옮김", "url": URL, "kind": "본인 말(원음+편집 자막)"},
    "f4": {"text": "본인 말 10:15~10:20 '목에 좀 한번 발라 볼까요? 목에 바르면 조금 티가 날 거 같은데' → 편집 자막 '목에도 손으로 빠르게 샤샤샥'(목에 바르는 화면 10:21~10:24)", "url": URL, "kind": "본인 말·화면"},
    "f5": {"text": "본인 말 10:38.3~10:42.9 '너무 신기하다 이거 진짜 이거는 카메라로도 무조건 비포 애프터 나오겠다' · 10:52.3~10:56.1 '진짜 찍길 잘했다 목 안 찍고 넘어갔으면 이거 못 믿으셨겠어'", "url": URL, "kind": "본인 말(원음으로 그대로 씀)"},
    "f6": {"text": "본인 말 10:09.7~10:12.9 '아 근데 이게 실제로 봤을 때는 티가 확 나는데'(편집 자막 흰색, 참고 목소리 대조 A) — 뒤 '화면에는 잘 안 나오네'는 화자 판정이 갈려 근거에서 뺌", "url": URL, "kind": "본인 말(전언)"},
}
S = {
    "topic": "강민경이 포트레 팀과 1년 동안 만든 워터 핏 스킨 틴트 — 목에 발라 보고 '카메라로도 무조건 비포 애프터 나오겠다'",
    "bench": {"id": "v1MZ9s9kl0Y", "channel": "셀럽장바구니", "title": "\"피부 광 미쳤다\" 강민경이 밝힌 쌩얼 비밀템 ✨",
              "dur": BENCH_DUR, "views": 284341, "upload": "2026-10-11", "source_label": "화면 위 '출처 : 강민경'"},
    "titles": {"hook": "강민경이 1년 만든\n비포애프터 틴트",
               "rule": "만템 틀: 1줄 흰(인물·사실) / 2줄 민트(제품) — 벤치 '강민경처럼 맑은 피부 / 하나만 발라도 충분해'와 다른 말. '1년'=f2, '비포 애프터'=본인 말 O1"},
    "facts": facts,
    "final": {
        "lines": [{"fn": n["fn"], "text": n["text"], "tts": n["tts"], "facts": n["facts"], "sources": [URL], "est_sec": n["est_sec"], "chars": n["chars"], "slice": NARR_SLICE[n["id"]], "t_final": n["t_final"]} for n in N],
        "orig_audio": [{"id": o["id"], "spans": o["spans"], "dur": o["dur"], "said": o["said"], "facts": o["facts"], "t_final": o["t_final"],
                        "speaker": "강민경 1명(편집 자막 흰색·참고 목소리 대조·받아쓰기 2회 — 근거.md §2)"} for o in O],
        "order": [b["block"] for b in blocks],
        "model": "오푸스 손 작성(제미나이 안 씀). 만템 결: 원음으로 연다 → 나레 '[인물]이 … ~라는데' → 원음 → 나레 다리 → 원음 → 나레 '~라네요'. 사실은 원본 본인 말·편집 자막·설명란만.",
        "check": {"chars_no_space": [n["chars"] for n in N], "total_chars": sum(n["chars"] for n in N), "rate_cps": (None if narr_real else CPS),
                  "narr_sec": [n["est_sec"] for n in N], "narr_measured": bool(narr_real), "orig_sec": [o["dur"] for o in O],
                  "orig_share": round(sum(o["dur"] for o in O) / dur, 3), "dur": dur, "dur_est": dur, "tts": "일레븐랩스 미나 1회(kr-mina-expressive, 1.0 합성 11.92초) → atempo 1.55",
                  "rate_measured": [round(n["chars"] / n["est_sec"], 2) for n in N], "bench_dur": BENCH_DUR, "ratio": round(dur / BENCH_DUR, 3),
                  "superlative": 0, "numbers": 0, "english_in_tts": 0, "max_sentence_chars": max(n["chars"] for n in N),
                  "bench_copy": "벤치 나레('강민경 피부 광이 미쳤지?' / '톤업크림 딱 하나만 바른 거라는데' / '기존의 톤업크림 단점을 보완해서' / '아침에 바쁠 때 이거저거 바르지 말고 하나만 샥 바르고 나가 봐')와 2어절 이상 연속 겹침 0"}},
    "captions_plan": caps,
    "caption_events": [{"kind": "emph", "text": c["text"], "rgb": [255, 255, 255], "t0": c["t0"], "dur": round(c["t1"] - c["t0"], 3),
                        "basis": "원음 — 본인 말 그대로(근거.md §2)"} for c in caps if c["kind"] == "원음"],
    "notes": ["자막 꼴(만템): 나레 = 노랑 [245,255,22] Cafe24Ohsquare 기울임(틀 caption 층) · 원음 = 흰색, 따옴표 없음. 엔진 emph 는 틀 caption 층 글꼴·자리만 써서 원음_흰글자(GmarketSansBold·y1320)는 못 씀 — 엔진 요청(1편·이영자 편과 같음).",
              "나레 시각은 TTS 전 8.3자/초 추정(--narr 없을 때). 원음 구간 안 상대 시각은 원본 그대로.",
              "벤치가 원음으로 쓴 '이것만 썼어요'·'톤업 크림이 원래 쓰다 보면 …'·'이거 하나만 발랐을 때 광이 제일 예쁘거든요'는 원본 편집 자막 연노랑 = 메이크업 아티스트(영은 부원장) 말 — 강민경 말이 아니라 안 씀(근거.md §2)."],
    "plan_est": {"blocks": blocks, "dur": dur},
}
(D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")

# 재료 — 원음 구간은 원본 시각 그대로(입 모양), 같은 원본 샷은 앞으로만, 남의 손·몸 근접 0(A13)
bt = {b["block"]: b["t"] for b in blocks}


def split(a, b, w):
    """블록 [a,b] 를 비율 w 로 나눈 경계들."""
    out, x = [], a
    for k in w[:-1]:
        x = x + (b - a) * k / sum(w)
        out.append(round(x, 3))
    return [a] + out + [b]


o1 = bt["O1"]
o1_b1 = round(o1[0] + (640.39 - 638.30), 3)      # 원본 640.39 샷 안 확대 바뀜(원본 편집) — 거기서 크롭도 바꿈
o1_b2 = round(o1[0] + (641.85 - 638.30), 3)
n1 = split(bt["N1"][0] - LEAD, bt["N1"][1], [1, 1])
n2 = split(bt["N2"][0] - LEAD, bt["N2"][1], [1, 1])
o3 = bt["O3"]
o3_b = round(o3[0] + (654.05 - 652.25), 3)
cuts = [
    ("O1", o1[0], o1_b1, 638.30, [770, 0, 780, 780], ("O1", 638.30), "강민경 얼굴(원본 확대 샷) — '너무 신기하다 이거 진짜' 말하는 입", "원음 638.30~ · 원본 샷 635.84~640.39(확대). 편집 자막(y≥840) 밖"),
    ("O1", o1_b1, o1_b2, 640.39, [555, 0, 780, 780], ("O1", 640.39), "강민경 얼굴(원본 넓은 샷) — '이거는 카메라로도' 말하는 입", "원음 계속 · 원본 640.39 에서 원본이 확대를 풀었다(원본 편집 그대로 — 점프 줌 1회)"),
    ("O1", o1_b2, o1[1], 643.10, [760, 0, 780, 780], ("O1", 641.85), "고개를 돌린 강민경 얼굴 근접(본인 손이 목 쪽)", "원음 '무조건 비포 애프터 나오겠다' 641.85~642.95 계속, 화면은 원본 다음 샷 643.06~(얼굴 근접 — 입 모양은 다음 말 '그니까 이게 목까지', 원음과 입이 안 맞는 1.1초). 644.3 번개 꾸밈 전에 끊음"),
    ("N1", n1[0], n1[1], 667.00, [480, 0, 720, 720], None, "강민경이 검은 포트레 튜브·흰 스틱을 양손에 들고 보여 줌", "'강민경이 일 년 동안 포트레 팀과 만든' — 제품. 666.6 반짝이 뒤 · 아래 홍보 글상자(y≥750) 밖"),
    ("N1", n1[1], n1[2], 615.90, [700, 0, 780, 780], None, "검은 배경 앞 강민경 얼굴(목에 발라 보자고 말하는 중)", "'스킨 틴트라는데' — 원본 샷 609.73~621.20 안, 꾸밈 없음(613 '아..ㅠ' 뒤)"),
    ("O2", bt["O2"][0], bt["O2"][1], 536.62, [650, 0, 760, 760], ("O2", 536.62), "메이크업 의자의 강민경이 손짓하며 말함(본인 손)", "원음 '아침에 이렇게 막 급하게 바르고 나가도' 536.62~538.55(자동자막 '들뜸' 538.60 전 — 1판 538.95 는 '들뜸 없'이 새어 나레와 겹침) · 539.46 원본 컷(남의 손 퍼프 근접) 전 · 왼쪽 아티스트 머리(x<200) 밖 · 자막(y≥830) 밖"),
    ("N2", n2[0], n2[1], 609.80, [800, 0, 780, 780], None, "검은 배경 앞 강민경 얼굴(실물로 보면 티가 난다고 말하는 중)", "'들뜸 없는 제품을 만들자고 했다는데' — 원본 샷 609.73~ · 611.3 부터 얼굴이 오른쪽으로 빠져 그 전에 끊음"),
    ("N2", n2[1], n2[2], 621.30, [300, 0, 780, 780], None, "강민경이 턱을 들고 자기 손으로 목에 바름", "'목에도 발라 보더니' — f4 목에 바르는 화면. 원본 샷 621.20~624.00, 왼쪽 아티스트 뒷머리(x<240) 밖"),
    ("O3", o3[0], o3_b, 652.25, [810, 0, 780, 780], ("O3", 652.25), "강민경 얼굴 '진짜 찍길 잘했다'", "원음 652.25~ · 원본 샷 652.19~661.08 · 650~651 꾸밈 뒤"),
    ("O3", o3_b, o3[1], 661.10, [480, 0, 780, 780], ("O3", 654.05), "강민경이 검은 튜브·흰 스틱을 들고 말함", "원음 '목 안 찍고 넘어갔으면 이거 못 믿으셨겠어' 654.05~656.12 계속, 화면은 원본 661.08 샷(같은 제품 든 장면) · 664 일시정지 아이콘 전"),
    ("N3", bt["N3"][0] - LEAD, dur, 631.10, [660, 0, 780, 780], None, "목에 바른 뒤 놀란 강민경 얼굴(본인 손을 쇄골에)", "'실물로 보면 티가 확 난다네요' — 바른 뒤 반응 얼굴로 끝. 630 '어머' 꾸밈 뒤, 636 '뽀얗게' 꾸밈 전 · 끝 컷 ≥1.5초"),
]
shots = []
for i, (line, a, b, ss, crop, aud, ours, why) in enumerate(cuts):
    d = round(b - a, 3)
    sh = {"i": i, "line": line, "src": SRC, "url": URL, "src_date": SRC_DATE, "ss": ss, "dur": d,
          "src_span": [ss, round(ss + d, 3)], "t_final": [round(a, 3), round(b, 3)], "kind": "원본재편집", "full": True,
          "src_crop": crop, "res": "1920x1080", "scale": round(1080 / crop[2], 2), "ours": ours, "why": why}
    if aud:
        sh["audio_src"] = SRC
        sh["audio_ss"] = aud[1]
    else:
        sh["mute"] = True
    shots.append(sh)
# 원본 컷 경계(scene 실측 0.06) — 넘으면 멈춤
LIMIT = {638.30: 640.39, 640.39: 643.059, 643.10: 644.30, 615.90: 621.204, 667.00: 670.545, 536.62: 539.456,
         621.30: 623.998, 631.10: 635.80, 652.25: 661.077, 661.10: 664.0, 609.80: 611.30}
for s in shots:
    assert s["ss"] + s["dur"] <= LIMIT[s["ss"]] + 1e-6, f"컷 {s['i']} 원본 컷 경계 넘음: {s['ss']}+{s['dur']} > {LIMIT[s['ss']]}"
# 같은 원본 ±3초 재사용 검사(B13)
spans = sorted((s["src_span"][0], s["src_span"][1], s["i"]) for s in shots)
near = [(x[2], y[2], round(y[0] - x[1], 2)) for x, y in zip(spans, spans[1:]) if y[0] - x[1] < 3.0]
lens = sorted(s["dur"] for s in shots)
med = lens[len(lens) // 2] if len(lens) % 2 else round((lens[len(lens) // 2 - 1] + lens[len(lens) // 2]) / 2, 3)
M = {"_note": "얜샷템 강민경 포트레 스킨 틴트 편(벤치 셀럽장바구니 v1MZ9s9kl0Y) 재료. 원본 = 걍밍경 WmEjrZFVRB4(1080p 23.976 h264). 창 1080x1080(frame_얜샷템). _build_json.py 가 만든다.",
     "cand_dir": "C:/숏템_칼카피/yanshottem/강민경_피부/src",
     "narration": "일레븐랩스 미나(kr-mina, voice aiUUgjHa4mpHf6UenZuf, eleven_v3, 1.0 합성 + atempo 1.35) — 벤치 나레 여성 차분한 설명체 약 8.4자/초",
     "sources": {"WmEjrZFVRB4": {"채널": "걍밍경", "제목": "B형 독감, 인생 톤업크림, 해리언니 생파", "업로드": "2026-02-20",
                                 "해상도": "1920x1080 23.976fps h264(137)", "길이": 1337}},
     "shots": shots,
     "source_audio": {"keep": True, "note": "원음 = 강민경 본인 말만(근거.md §2). 원본 구간 LUFS O1 −16.8 · O2 −18.5 · O3 −15.5(웅얼거림 아님)."},
     "caption_effects": {"now": "나레 = 틀 caption(나레_노랑) · 원음 = caption_events emph 흰색(따옴표 없음)", "planned": "원음_흰글자(GmarketSansBold·y1320) 하위 스타일 — 엔진 요청"},
     "check": {"total": dur, "bench": BENCH_DUR, "ratio": round(dur / BENCH_DUR, 3), "n_shots": len(shots), "shot_median": med,
               "bench_cut_median": 1.2, "mantem_cut_median": 1.40, "max_scale": max(s["scale"] for s in shots), "orig_share": S["final"]["check"]["orig_share"],
               "cap_max_chars": max(len(c["text"].replace(" ", "")) for c in caps), "near_3s": near, "sources_used": [SRC_DATE]}}
(D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")

fr = json.loads((ROOT / "channel/mantem/frame_얜샷템.json").read_text(encoding="utf-8"))
next(l for l in fr["layers"] if l.get("role") == "title")["text"] = S["titles"]["hook"]
next(l for l in fr["layers"] if l.get("role") == "label")["text"] = "출처 : 걍밍경"
fr["made_from"]["episode"] = "얜샷템 강민경_피부 — title·label 글만 바꿈"
(D / "frame_강민경.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"blocks": blocks, "dur": dur, "check": M["check"], "cuts": [(s["i"], s["line"], s["ss"], s["dur"]) for s in shots]}, ensure_ascii=False))
