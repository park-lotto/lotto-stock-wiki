# -*- coding: utf-8 -*-
"""이영자 실내화 편 — 대본.json·재료.json·frame 을 한 곳에서 만든다(손 수치는 근거.md §2·§4 실측). 관제 097.

    PYTHONIOENCODING=utf-8 py channel/yanshottem/이영자_실내화/_build_json.py [--narr 1.23,4.56]   # TTS 뒤 나레 줄 실측 길이(초)
"""
import json
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parents[2]
URL = "https://www.youtube.com/watch?v=BHuue4ga-w0"
SRC = "yj_BHuue4ga-w0.mp4"
CPS = 8.3      # 추정 말속도(미나 1.35) — TTS 뒤 --narr 로 실측 길이를 넣는다
LEAD = 0.08
END_TAIL = 0.30
N = [
    {"id": "N1", "fn": "나레 다리 1(인물·때·제품 정체 ~라는데)",
     "text": "이영자가 드림하우스로, 이사하던 날, 짐 정리하다, 피디에게 꺼내 준, 요가 신발이라는데",
     "tts": "이영자가 드림하우스로 이사하던 날 짐 정리하다 피디에게 꺼내 준 요가 신발이라는데",
     "facts": ["f1", "f2", "f3", "f4"]},
    {"id": "N2", "fn": "나레 마무리(~라네요 전언)",
     "text": "신어 본 피디도, 편해서 놀랐다네요",
     "tts": "신어 본 피디도 편해서 놀랐다네요.",
     "facts": ["f5"]},
]
O = [
    {"id": "O1", "spans": [[117.82, 119.42]], "said": "PD님 걸어 다니기 힘들죠?",
     "caps": [["PD님 걸어 다니기", 0.0, 1.0], ["힘들죠?", 1.0, 1.6]]},
    {"id": "O2", "spans": [[119.62, 126.32]],
     "said": "올해 또 만난 나의 NEW 슈즈 (쉼 0.9초) 요가할 때 신는 건데 이거 신고 하세요 그럼 편하실 거예요",
     "caps": [["올해 또 만난", 0.0, 1.3], ["나의 NEW 슈즈", 1.3, 3.88], ["요가할 때 신는 건데", 3.88, 4.78],
              ["이거 신고 하세요", 4.78, 5.74], ["그럼 편하실 거예요", 5.74, 6.70]]},
]
narr_real = None
if "--narr" in sys.argv:
    narr_real = [float(x) for x in sys.argv[sys.argv.index("--narr") + 1].split(",")]
for o in O:
    o["dur"] = round(sum(b - a for a, b in o["spans"]), 2)
for k, n in enumerate(N):
    n["chars"] = len(n["tts"].replace(" ", "").replace(".", ""))
    n["est_sec"] = round(narr_real[k] if narr_real else n["chars"] / CPS, 3)
# 순서: O1 → N1 → O2 → N2 (만템 결: 원음으로 연다·나레 2줄·~라는데/~라네요)
seq = [("O", 0), ("N", 0), ("O", 1), ("N", 1)]
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
    blocks.append({"block": (O[i] if kind == "O" else N[i])["id"], "t": [round(a, 3), round(b, 3)]})
    t = b
dur = round(t + END_TAIL, 3)
facts = {
    "f1": {"text": "원본 제목 '드디어 드림하우스로 이사하는 날❗️3도4촌 시작합니다🏠 (이효리 오징엇국)' · 업로드 2024-06-30 · 이영자 TV", "url": URL, "kind": "제목·메타"},
    "f2": {"text": "같은 영상 1:28.8~1:32 편집 자막 '더 이상 지체할 수 없다 / 드디어 정리 시작!'(짐 상자 정리 화면) → 1:57.8~1:59.4 짐 가방에서 검은 신발 주머니를 꺼냄", "url": URL, "kind": "화면 자막·화면"},
    "f3": {"text": "본인 말 1:57.8 'PD님 걸어 다니기 힘들죠?'(편집 자막 같은 글) → 2:03.5 '요가할 때 신는 건데 이거 신고 하세요'", "url": URL, "kind": "본인 말(원음으로 그대로 씀)"},
    "f4": {"text": "편집 자막 2:04.5~2:08 '(고렌샤크 미끄럼방지 요가 신발)'(노랑) — 제품 정체", "url": URL, "kind": "화면 자막"},
    "f5": {"text": "편집 자막 2:08.2~2:10.5 '[진짜 편해서 놀랐다고 한다]' — 그 신발을 신은 사람(카키 반바지·흰 양말, 이영자의 흰 반바지와 다른 사람)이 걷는 화면. '피디'라는 정체는 직전 본인 말 'PD님 … 이거 신고 하세요'에서 이은 해석 → 전언체", "url": URL, "kind": "화면 자막·화면(해석 전언)"},
}
S = {
    "topic": "이영자가 드림하우스 이사 날 짐 정리하다 PD에게 꺼내 준 고렌샤크 미끄럼방지 요가 신발 — 'PD님 걸어 다니기 힘들죠? 요가할 때 신는 건데 이거 신고 하세요'",
    "bench": {"id": "nt6WIGFmILE", "channel": "안나픽", "title": "품절대란 난리 난 이영자 추천 미끄럼방지 초경량 실내화 #shorts",
              "dur": 16.0, "views": 209029, "upload": "2026-10-16", "source_label": "화면 하단 '출처 : 이영자 TV'"},
    "titles": {"hook": "이영자가 피디에게 준\n미끄럼방지 요가 신발",
               "rule": "만템 틀: 1줄 흰(인물·상황) / 2줄 민트(제품) — 벤치 '이영자 때문에 / 전국 품절사태'와 다른 말, 사실은 f3·f4"},
    "facts": facts,
    "final": {
        "lines": [{"fn": n["fn"], "text": n["text"], "tts": n["tts"], "facts": n["facts"], "sources": [URL], "est_sec": n["est_sec"], "chars": n["chars"]} for n in N],
        "orig_audio": [{"id": o["id"], "before_line": (0 if k == 0 else None), "after_line": (None if k == 0 else 0), "spans": o["spans"], "dur": o["dur"],
                        "said": o["said"], "facts": ["f3"], "t_final": o["t_final"], "speaker": "이영자 1명(받아쓰기 근거.md §2)"} for k, o in enumerate(O)],
        "order": [b["block"] for b in blocks],
        "model": "오푸스 손 작성(제미나이 안 씀). 만템 결(비교 보고서 §2·§3): 원음으로 연다 → 나레 '[인물]이 … ~라는데' → 원음 증언(길게) → 나레 '~라네요' 마무리. 사실은 원본 본인 말·편집 자막·화면만.",
        "check": {"chars_no_space": [n["chars"] for n in N], "total_chars": sum(n["chars"] for n in N), "rate_cps": (None if narr_real else CPS),
                  "narr_sec": [n["est_sec"] for n in N], "narr_measured": bool(narr_real), "orig_sec": [o["dur"] for o in O],
                  "orig_share": round(sum(o["dur"] for o in O) / dur, 3), "dur": dur, "bench_dur": 16.0, "ratio": round(dur / 16.0, 3),
                  "superlative": 0, "numbers": 0, "english_in_tts": 0, "max_sentence_chars": max(n["chars"] for n in N),
                  "bench_copy": "벤치 나레('이영자가 매일 신고 있다는 실내화가 화제라는데' / '초경량에 미끄럼방지까지 완벽해서 집이나 운동할 때 신기 딱이라고요')와 2어절 이상 연속 겹침 0 — 겹치는 낱말은 '이영자가' 1개"}},
    "captions_plan": caps,
    "caption_events": [{"kind": "emph", "text": c["text"], "rgb": [255, 255, 255], "t0": c["t0"], "dur": round(c["t1"] - c["t0"], 3),
                        "basis": "원음 — 원본 편집 자막 글 그대로(근거.md §2)"} for c in caps],
    "notes": ["자막 꼴(만템): 나레 = 노랑 [245,255,22] Cafe24Ohsquare 기울임(틀 caption 층) · 원음 = 흰색, 따옴표 없음. 엔진 emph 는 틀 caption 층 글꼴·자리만 써서 원음_흰글자(GmarketSansBold·y1320)는 못 씀 — 엔진 요청(1편과 같음).",
              "나레 시각은 TTS 전 8.3자/초 추정(--narr 없을 때). 원음 구간 안 상대 시각은 원본 그대로."],
    "plan_est": {"blocks": blocks, "dur": dur},
}
(D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")

# 재료 — 컷 6개(원음 구간은 원본 시각 그대로 → 입 모양 맞음, 같은 테이크는 앞으로만)
bt = {b["block"]: b["t"] for b in blocks}
n1a, n1b = bt["N1"]
n1s = round(n1a + (n1b - n1a) * 0.42, 3)   # '짐 정리하다' 앞에서 컷(자막 조각 경계 근처)
o2a, o2b = bt["O2"]
cuts = [
    ("O1", 0.0, bt["O1"][1], 117.82, [700, 0, 820, 820], True,
     "짐 가방 위로 몸을 숙여 검은 신발 주머니를 꺼냄(이영자 본인, 흰 반바지·초록 셔츠)", "원음 'PD님 걸어 다니기 힘들죠?' 117.82~119.42 — 원본 편집 자막(y≈940) 밖. 117.80 원본 컷 뒤"),
    ("N1", bt["O1"][1], n1s, 86.55, [450, 0, 820, 820], False,
     "새 집 주방 조리대 앞에 선 이영자(창밖 나무)", "'이영자가 드림하우스로 이사하던 날' — f1 제목·이사 날 화면. 자막 '[볼수록 그저 감탄]'(y≈950) 밖. 88.42 원본 컷 전에 끊음"),
    ("N1", n1s, o2a, 88.50, [640, 0, 760, 760], False,
     "짐 상자(파란 통) 위로 숙여 짐을 꺼내는 이영자", "'짐 정리하다 피디에게 꺼내 준 요가 신발이라는데' — f2 '드디어 정리 시작!' 자막(왼쪽 아래 y≥760) 밖. 92.04 원본 컷 전"),
    ("O2", o2a, o2b, 119.62, [450, 0, 820, 820], True,
     "신발 주머니 들고 정면 보며 말하는 이영자 → 신발 꺼내 듦 → 그 신발 신은 이영자 다리(흰 반바지) → 바닥(한 테이크, 카메라가 따라감)",
     "원음 '올해 또 만난 나의 NEW 슈즈 … 요가할 때 신는 건데 이거 신고 하세요 / 그럼 편하실 거예요' 119.62~126.32 한 테이크 그대로(자르면 같은 테이크 크롭이 바뀌어 점프 줌 → 크롭 하나). 자막(y≥840) 밖. 126.4~127.4 남의 손이 신발 바닥을 드는 장면은 A13 때문에 안 씀"),
    ("N2", o2b, dur, 128.42, [600, 85, 820, 820], False,
     "그 신발을 신고 걷는 사람의 발(카키 반바지·흰 양말 — 이영자와 다른 사람)", "'신어 본 피디도 편해서 놀랐다네요' — f5 '[진짜 편해서 놀랐다고 한다]' 자막(y≥910) 밖. 130.52 원본 컷 전. 끝 컷 ≥1.5초"),
]
shots = []
for i, (line, a, b, ss, crop, snd, ours, why) in enumerate(cuts):
    d = round(b - a, 3)
    sh = {"i": i, "line": line, "src": SRC, "url": URL, "src_date": "이영자 TV 유튜브 2024.06.30", "ss": ss, "dur": d,
          "src_span": [ss, round(ss + d, 3)], "t_final": [round(a, 3), round(b, 3)], "kind": "원본재편집", "full": True,
          "src_crop": crop, "res": "1920x1080", "scale": round(1080 / crop[2], 2), "ours": ours, "why": why}
    if snd:
        sh["audio_src"] = SRC
        sh["audio_ss"] = ss
    else:
        sh["mute"] = True
    shots.append(sh)
LIMIT = {86.55: 88.42, 88.50: 92.04, 117.82: 119.45, 119.62: 126.40, 128.42: 130.52}   # 128.16~128.35 남의 손 근접(A13) → 128.42부터   # 원본 컷 경계(scene 실측) 넘으면 멈춤
for s in shots:
    assert s["ss"] + s["dur"] <= LIMIT[s["ss"]] + 1e-6, f"컷 {s['i']} 원본 컷 경계 넘음: {s['ss']}+{s['dur']} > {LIMIT[s['ss']]}"
lens = sorted(s["dur"] for s in shots)
med = lens[len(lens) // 2] if len(lens) % 2 else round((lens[len(lens) // 2 - 1] + lens[len(lens) // 2]) / 2, 3)
M = {"_note": "얜샷템 이영자 실내화 편(벤치 안나픽 nt6WIGFmILE) 재료. 원본 = 이영자 TV BHuue4ga-w0(1080p50 AV1 → h264 변환). 창 1080x1080(frame_얜샷템). _build_json.py 가 만든다.",
     "cand_dir": "C:/숏템_칼카피/yanshottem/이영자_실내화/src",
     "narration": "일레븐랩스 미나(kr-mina, voice aiUUgjHa4mpHf6UenZuf, eleven_v3, 1.0 합성 + atempo 1.35) — 벤치 나레 여성 차분한 설명체 8.01자/초",
     "sources": {"BHuue4ga-w0": {"채널": "이영자 TV", "제목": "드디어 드림하우스로 이사하는 날❗️3도4촌 시작합니다🏠 (이효리 오징엇국)", "업로드": "2024-06-30",
                                 "해상도": "1920x1080 50fps(AV1 webm → libx264 crf18 변환본 yj_BHuue4ga-w0.mp4)", "길이": 488.34, "조회": 2165422}},
     "shots": shots,
     "source_audio": {"keep": True, "note": "원음 = 이영자 본인 말만(받아쓰기 2회+, 근거.md §2). 원본 구간 LUFS −13.2/−15.0/−18.0(웅얼거림 아님)."},
     "caption_effects": {"now": "나레 = 틀 caption(나레_노랑) · 원음 = caption_events emph 흰색(따옴표 없음)", "planned": "원음_흰글자(GmarketSansBold·y1320) 하위 스타일 — 엔진 요청"},
     "check": {"total": dur, "bench": 16.0, "ratio": round(dur / 16.0, 3), "n_shots": len(shots), "shot_median": med,
               "bench_cut_median": 0.77, "mantem_cut_median": 1.40, "max_scale": max(s["scale"] for s in shots), "orig_share": S["final"]["check"]["orig_share"],
               "cap_max_chars": max(len(c["text"].replace(" ", "")) for c in caps), "sources_used": ["이영자 TV 유튜브 2024.06.30"]}}
(D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")

fr = json.loads((ROOT / "channel/mantem/frame_얜샷템.json").read_text(encoding="utf-8"))
next(l for l in fr["layers"] if l.get("role") == "title")["text"] = S["titles"]["hook"]
next(l for l in fr["layers"] if l.get("role") == "label")["text"] = "출처 : 이영자 TV"
fr["made_from"]["episode"] = "얜샷템 이영자_실내화 — title·label 글만 바꿈"
(D / "frame_이영자.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"blocks": blocks, "dur": dur, "check": M["check"]}, ensure_ascii=False))
