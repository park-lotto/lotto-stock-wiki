# -*- coding: utf-8 -*-
"""얜샷템 장윤정 덴마크 수건(벤치 안나픽 ySJLtV0K1PY) — 대본.json·재료.json·frame.json 을 한 곳에서 쓰고 계획 시트를 만든다.
엔진 코드는 안 고친다(관제 097, 2026-10-17). TTS 전 선검수용 — 시각은 나레 8.4자/초 추정, TTS 뒤 다시 맞춘다.

    PYTHONUTF8=1 py channel/yanshottem/장윤정_덴마크수건/build_plan.py   → 파일 3개 + remake.py --plan-only
"""
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

D = Path(__file__).resolve().parent
ROOT = D.parents[2]
SRCDIR = Path("C:/숏템_칼카피/yanshottem/장윤정_덴마크수건/src")
SRC = "jyj_XzCEZtLDV-A.mp4"
URL = "https://www.youtube.com/watch?v=XzCEZtLDV-A"
SDATE = "장공장장윤정 유튜브 2026.03.18"
TITLE = "수건에 미친 장윤정이\n덴마크서 사 온 수건"
LABEL = "출처 : 장공장장윤정"
CPS = 8.4
# TTS 실측(10-17): 미나 1회 narr_mina.mp3(10.08초, 1.0) → atempo 1.44 narr_t144.wav(7.01초). 말 구간 = N1 0.00~3.24(26자 8.0자/초) · N2 3.90~7.01(27자 8.7자/초)
NARR_SLICE = {"N1": [0.00, 3.26], "N2": [3.88, 7.01]}
NARR_PAD = {"N1": 0.12, "N2": 0.45}   # 나레 끝 뒤 쉼(N1 → 원음 O4) · 끝 여유(N2 = 마지막 컷 ≥1.5초)

# 블록: (id, 종류, 길이 또는 None) — 원음은 spans 합, 나레는 글자/CPS
NARR = {
    "N1": {"text": "장윤정이, 덴마크에서, 물어물어 사 왔다는, 테클라 수건이라는데.",
           "tts": "장윤정이 덴마크에서 물어물어 사 왔다는 테클라 수건이라는데.",
           "caps": ["장윤정이 덴마크에서", "물어물어 사 왔다는", "테클라 수건이라는데"],
           "fn": "훅(인물·어디서·어떻게 샀나·제품 이름)", "facts": ["f1", "f2", "f3"]},
    "N2": {"text": "매장이 없다 보니, 비슷한 디자인까지, 많이 나온다는, 수건이라네요.",
           "tts": "매장이 없다 보니 비슷한 디자인까지 많이 나온다는 수건이라네요.",
           "caps": ["매장이 없다 보니", "비슷한 디자인까지", "많이 나온다는", "수건이라네요"],
           "fn": "마무리(인기·전언 '~라네요')", "facts": ["f7"]},
}
# 원음: spans(원본 초), caps = (자막, 원본 시작 초 — vtt 낱말 시각)
ORIG = {
    "O1": {"spans": [[224.80, 225.98], [226.40, 231.00]], "said": "저는 수건 미치는 애거든요. 수건을 저희 집에 보면 수건이 수십 개씩 있어요.",
           "caps": [("저는 수건", 224.96), ("미치는 애거든요", 226.48), ("수건을 저희 집에 보면", 227.44), ("수건이 수십 개씩 있어요", 229.12)],
           "facts": ["f4"], "asr": ["O1v2_a", "O1v2_b"]},
    "O4": {"spans": [[204.92, 208.24]], "said": "엄청 크지? 우리 일반 가정에서 쓰는 수건보다 크죠.",
           "caps": [("엄청 크지?", 205.04), ("일반 가정에서 쓰는", 206.08), ("수건보다 크죠?", 207.44)], "facts": ["f5"], "asr": ["O4_a", "O4_b"]},
    "O5": {"spans": [[216.80, 219.95], [221.55, 224.66]], "said": "(근데) 이거 만져 봐. 이거 네가 만져 봐야 돼. 왜 비싼지를. / 엄청 도톰하지? 우리 그 샤워가운 수준이에요.",
           "caps": [("이거 만져 봐", 217.00), ("이거 네가 만져 봐야 돼", 217.52), ("왜 비싼지를", 218.92), ("엄청 도톰하지?", 221.80),
                    ("우리 그 샤워가운", 222.68), ("수준이에요", 224.16)], "facts": ["f6"], "asr": ["O5v2_a", "O5v2_b"]},
    "O3": {"spans": [[261.95, 263.02], [264.56, 265.45]], "said": "확실히 짱짱하다. / 확실히 도톰하다.",
           "caps": [("확실히 짱짱하다", 262.12), ("확실히 도톰하다", 264.68)], "facts": ["f6"], "asr": ["O3_a", "O3_b"]},
}
ORDER = ["O1", "N1", "O4", "O5", "O3", "N2"]

# 컷: (블록, 원본 시작, 길이 또는 None=블록 나머지, crop[x,y,w,h], 화면, 왜). 원음 블록 안 B롤은 소리만 원음(audio_ss) — 그림은 제품·본인 손만.
CUTS = [
    ("O1", 224.80, 1.18, [500, 0, 870, 870], "넓은 거실, 노란 의자 위 줄무늬 수건을 펼치는 장윤정(오른쪽 위 촬영자 손 x≥1680 은 크롭 밖)", "원음 '저는 수건' — 원음 첫 마디로 연다(만템 7/8)"),
    ("O1", 226.40, 2.80, [455, 0, 870, 870], "소파에서 두 손을 머리 위로 들며 말하는 장윤정(편집 자막 '수건에 미친 자' y≈930 은 크롭 밖)", "원음 '미치는 애거든요 / 수건을 저희 집에 보면' — 입 모양 맞음"),
    ("O1", 127.00, 0.90, [430, 0, 870, 870], "무릎 위에서 포장을 벗겨 파랑 줄무늬 수건을 꺼내는 본인 손", "원음 '수건이 수십 개씩' — 수건 더미(본인 손·제품만, 얼굴 없음)"),
    ("O1", 147.20, None, [330, 0, 870, 870], "TEKLA 라벨이 달린 빨강·분홍 줄무늬 수건 근접(제품만)", "원음 '…있어요' — 제품 라벨"),
    ("N1", 111.70, 1.03, [560, 0, 870, 870], "TEKLA 로고 포장지를 들어 보이는 장윤정(편집 자막 '[북유럽 감성의 로고 디자인]' y≈930 크롭 밖)", "'장윤정이 덴마크에서' — 사 온 포장 그대로"),
    ("N1", 115.00, 1.03, [470, 0, 870, 870], "소파에 수건 더미를 안고 앉은 장윤정(원본 자막 '여기를 물어 물어 걸어 걸어가지고 사 왔어요' y≈930 크롭 밖)", "'물어물어 사 왔다는' — 바로 그 말을 한 장면"),
    ("N1", 197.70, None, [535, 0, 860, 860], "TEKLA 라벨 달린 버건디 줄무늬 수건을 펼쳐 든 장윤정('우리집은 도연우 수건' 자막 y≥893 크롭 밖)", "'테클라 수건이라는데' — 라벨이 보이는 제품"),
    ("O4", 204.92, None, [500, 0, 870, 870], "큰 줄무늬 수건을 양손으로 펼쳐 든 장윤정", "원음 '엄청 크지? … 수건보다 크죠' — 입 모양 맞음"),
    ("O5", 216.80, 3.15, [520, 0, 870, 870], "수건을 카메라 쪽으로 내미는 장윤정", "원음 '이거 만져 봐 / 만져 봐야 돼 / 왜 비싼지를' — 입 모양 맞음"),
    ("O5", 161.10, 1.04, [300, 0, 870, 870], "노란 탁자 위 TEKLA 라벨 수건 묶음(제품만, 자막 '잘 모르겠는데 이쁘지?' y≈930 크롭 밖)", "원음 '엄청 도톰하지?' — 원본 221.6~224.7 은 촬영자 손이 수건을 잡아(224.6) A13 → 제품 컷"),
    ("O5", 132.00, 1.00, [450, 0, 860, 860], "노란 탁자 위 접힌 파랑 줄무늬 수건(제품만, '✨수건✨' y≥865 크롭 밖)", "원음 '우리 그 샤워가운' — 두께 보이는 접힌 수건"),
    ("O5", 151.25, None, [560, 0, 870, 870], "TEKLA 라벨 근접(제품만, 자막 '아유 이게 이게 뭐라고' y≈930 크롭 밖)", "원음 '수준이에요'"),
    ("O3", 261.95, 1.07, [590, 0, 870, 870], "위에서 본 줄무늬 수건을 손으로 쥐어 보는 장면(본인 손)", "원음 '확실히 짱짱하다' — 입 모양 없는 손 컷(원본 그대로)"),
    ("O3", 264.56, None, [455, 0, 870, 870], "수건을 무릎에 덮고 말하는 장윤정('아 나 너무 행복하다' 자막은 265.5 부터라 이 컷엔 없음)", "원음 '확실히 도톰하다' — 입 모양 맞음"),
    ("N2", 241.00, 1.60, [410, 0, 870, 870], "파랑 세로 줄무늬 수건을 펼쳐 보는 장윤정(자막 y≈930 크롭 밖)", "'매장이 없다 보니 / 비슷한 디자인까지' — 줄무늬 디자인"),
    ("N2", 248.10, None, [470, 0, 870, 870], "빨강 줄무늬 TEKLA 수건을 펼쳐 든 장윤정(자막 'TEKLA 수건이 워낙에' y≈930 크롭 밖 · 250.25 부터 얼굴 옆 '여자분들이 막'(y≈400, 크롭 안) → 248.10 시작해 250.08 에 끝)", "'많이 나온다는 수건이라네요' — 끝 컷 ≥1.5초"),
]

FACTS = {
    "f1": {"text": "원본 첫 마디 0:10 '제가 덴마크에서 왔거든요'(자동자막) · 제목 '장공장장윤정이 픽한 내돈내산 북유럽 쇼핑템' · 해시태그 #덴마크 · 1:35 '덴마크가 물가가 상당하거든요'", "url": URL, "kind": "본인 말·제목"},
    "f2": {"text": "원본 편집 자막(화면) 1:55 '여기를 물어 물어 걸어 걸어가지고 사 왔어요' · 자동자막 1:53 '여기를 물어 물어 걸어걸어가 가지고 사왔어요'", "url": URL, "kind": "화면 자막·본인 말"},
    "f3": {"text": "원본 편집 자막 1:40 '이름이 TEKLA라는 수건인데' · 수건 라벨·포장지 'TEKLA'(1:52·2:27 화면)", "url": URL, "kind": "화면 자막·라벨"},
    "f4": {"text": "본인 말 3:44.9~3:51 '저는 수건 미치는 애거든요. 수건을 저희 집에 보면 수건이 수십 개씩 있어요'(받아쓰기 2회 일치)", "url": URL, "kind": "본인 말(원음)"},
    "f5": {"text": "본인 말 3:24.9~3:28.2 '엄청 크지? 우리 일반 가정에서 쓰는 수건보다 크죠'(받아쓰기 2회)", "url": URL, "kind": "본인 말(원음)"},
    "f6": {"text": "본인 말 3:36.8~3:44.7 '이거 네가 만져 봐야 돼. 왜 비싼지를 … 엄청 도톰하지? 우리 그 샤워가운 수준이에요' · 4:22~4:25 '확실히 짱짱하다. 확실히 도톰하다'(받아쓰기 2회)", "url": URL, "kind": "본인 말(원음)"},
    "f7": {"text": "본인 말 4:08.8~4:17.6 '테클라 수건이 워낙에 그 여자분들이 막 (갖고) 싶어 하는데 이제 매장은 없고 그러니까 이게 인기가 많은 걸 아시고 이런 디자인으로 아주 많이 나와요'(받아쓰기 2회 + 자동자막)", "url": URL, "kind": "본인 말 → 전언 '~라네요'"},
}


def ymean(t, crop):
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(SRCDIR / SRC), "-frames:v", "1", "-vf",
                        "crop={2}:{3}:{0}:{1},scale=270:270,format=gray".format(*crop), "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True).stdout
    return int(np.asarray(Image.open(io.BytesIO(b))).mean())


def main():
    # 블록 길이·시각
    blk, t = {}, 0.0
    for b in ORDER:
        if b in ORIG:
            d = round(sum(e - s for s, e in ORIG[b]["spans"]), 3)
        else:
            sl = NARR_SLICE[b]; d = round(sl[1] - sl[0] + NARR_PAD[b], 3)
        blk[b] = (round(t, 3), round(t + d, 3)); t += d
    dur = round(t, 3)
    # 컷 시각 + 원음 소리 위치(블록 안 상대 시각 → 원본 spans)
    def orig_at(b, rel):
        acc = 0.0
        for s, e in ORIG[b]["spans"]:
            if rel < acc + (e - s) - 1e-6:
                return round(s + rel - acc, 3)
            acc += e - s
        return round(ORIG[b]["spans"][-1][1], 3)
    shots, cur = [], {b: blk[b][0] for b in ORDER}
    for i, (b, ss, d, crop, ours, why) in enumerate(CUTS):
        a = cur[b]
        if d is None:
            d = round(blk[b][1] - a, 3)
        sh = {"i": i, "line": b, "src": SRC, "url": URL, "src_date": SDATE, "ss": ss, "dur": round(d, 3), "src_span": [ss, round(ss + d, 3)],
              "t_final": [round(a, 3), round(a + d, 3)], "kind": "원본재편집", "full": True, "src_crop": crop, "res": "1920x1080",
              "scale": round(1080 / crop[2], 2), "ours": ours, "why": why, "Y": ymean(ss + d / 2, crop)}
        if b in ORIG:
            sh["audio_src"], sh["audio_ss"] = SRC, orig_at(b, a - blk[b][0])
        else:
            sh["mute"] = True
        shots.append(sh); cur[b] = a + d
    for b in ORDER:   # 블록 안 컷이 블록을 정확히 채우는지
        assert abs(cur[b] - blk[b][1]) < 1e-3, (b, cur[b], blk[b])
    # 자막 계획
    caps = []
    for b in ORDER:
        a0, a1 = blk[b]
        if b in NARR:
            cs = NARR[b]["caps"]; n = sum(len(c.replace(" ", "")) for c in cs); x = a0
            talk = NARR_SLICE[b][1] - NARR_SLICE[b][0]
            for k, c in enumerate(cs):
                d = talk * len(c.replace(" ", "")) / n + (NARR_PAD[b] if k == len(cs) - 1 else 0)
                caps.append({"t0": round(x, 3), "t1": round(x + d, 3), "text": c, "kind": "나레"}); x += d
        else:
            O = ORIG[b]
            def rel(src_t):
                acc = 0.0
                for s, e in O["spans"]:
                    if s - 0.3 <= src_t <= e:
                        return acc + max(0.0, src_t - s)
                    acc += e - s
                return acc
            ts = [a0 + (0.0 if k == 0 else rel(st)) for k, (_, st) in enumerate(O["caps"])] + [a1]
            for k, (c, _) in enumerate(O["caps"]):
                caps.append({"t0": round(ts[k], 3), "t1": round(ts[k + 1], 3), "text": c, "kind": "원음"})
    lines = []
    for b in ("N1", "N2"):
        N = NARR[b]
        lines.append({"fn": N["fn"], "text": N["text"], "tts": N["tts"], "facts": N["facts"], "sources": [URL],
                      "est_sec": round(NARR_SLICE[b][1] - NARR_SLICE[b][0], 2), "block": b, "slice": NARR_SLICE[b], "t_final": list(blk[b]),
                      "cps": round(len(N["tts"].replace(" ", "").rstrip(".")) / (NARR_SLICE[b][1] - NARR_SLICE[b][0]), 2)})
    orig = []
    for b in ORDER:
        if b in ORIG:
            O = ORIG[b]
            prev = ORDER[ORDER.index(b) - 1] if ORDER.index(b) else None
            orig.append({"id": b, "after_line": (0 if prev == "N1" else (None if prev is None else ("N1" if ORDER.index(b) < ORDER.index("N2") else "N2"))),
                         "spans": O["spans"], "dur": round(blk[b][1] - blk[b][0], 3), "said": O["said"], "facts": O["facts"],
                         "t_final": list(blk[b]), "asr_files": [f"C:/숏템_칼카피/yanshottem/장윤정_덴마크수건/asr/{x}.json" for x in O["asr"]]})
    bench = {"id": "ySJLtV0K1PY", "channel": "안나픽", "title": "장윤정이 덴마크까지 가서 쓸어왔다는 수건, 연예인들 다 쓴다는 이유",
             "dur": 24.57, "views": 109690, "upload": "2026-10-10", "screen_title": "연예인집에 다 있다는 / 장윤정 덴마크 수건"}
    S = {"topic": "장윤정이 덴마크에서 물어물어 사 온 TEKLA(테클라) 줄무늬 수건 — '수건 미치는 애'가 크기·두께를 직접 만져 보며 소개",
         "bench": bench,
         "source": {"id": "XzCEZtLDV-A", "channel": "장공장장윤정", "title": "장공장장윤정이 픽한 내돈내산 북유럽 쇼핑템🛍️ l 북유럽 보따리 장수",
                    "upload": "2026-03-18", "res": "1920x1080 29.97fps", "dur": 931.5, "url": URL},
         "titles": {"hook": TITLE, "rule": "1줄 흰(인물·상황) / 2줄 민트(제품) — 얜샷템 틀. 벤치 '연예인집에 다 있다는 / 장윤정 덴마크 수건'과 다른 말"},
         "facts": FACTS,
         "final": {"lines": lines, "orig_audio": orig, "order": ORDER,
                   "model": "오푸스 손 작성(제미나이 안 씀). 만템 꼴(비교 보고서): 원음으로 열고 나레 2줄('~이라는데' 훅 · '~라네요' 마무리), 나레 비율 ≈0.27. 사실은 본인 말·원본 편집 자막·라벨만.",
                   "check": {"narr_chars_no_space": [len(NARR[b]["tts"].replace(" ", "").rstrip(".")) for b in ("N1", "N2")],
                             "est_rate_cps": CPS, "dur_est": dur, "narr_ratio": round(sum(blk[b][1] - blk[b][0] for b in NARR) / dur, 3),
                             "superlative": 0, "numbers_in_tts": 0, "english_in_tts": 0,
                             "bench_copy": "벤치 나레 '장윤정이 덴마크까지 가서 쟁여운 수건이라는데'와 겹치는 연속 어절: '장윤정이'(1)·'수건이라는데'(1) — 3어절 이상 연속 0"}},
         "captions_plan": caps,
         "notes": ["자막 꼴(만템): 나레 = 노랑(틀 caption 층) · 원음 = 흰 글자, 따옴표 없음.",
                   "시각은 8.4자/초 추정 — 미나 TTS(일레븐, 1.0 합성 + atempo 1.35) 뒤 나레 길이를 재서 블록 시각을 다시 맞춘다(원음 블록 안 상대 시각은 그대로).",
                   "O2 후보 '수건인데 여러분 (이거) 비싸요. 덴마크가 물가가 상당하거든요'(2:13~2:18)는 받아쓰기 4회 중 '수건인데'→'주원/주웠/추원/슈퍼', '상당하거든요'→'살벌/살나/상상' — B17 로 뺌."]}
    (D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    M = {"_note": "얜샷템 장윤정 덴마크 수건 재료 계획 — TTS·렌더 전. 원본 = 장공장장윤정 XzCEZtLDV-A 1080p 한 편만. 창 1080x1080(frame_얜샷템). "
                  "원본 화면 자막·편집 글자는 전부 y≥865(아래 자막 y≈905~955) 또는 왼쪽 위('아 나 너무 행복하다' 265.5~) → 크롭 y 0~870 로 뺌. "
                  "원음 블록 안 제품 컷은 audio_src/audio_ss 로 소리만 원음.",
         "cand_dir": str(SRCDIR).replace("\\", "/"),
         "narration": "일레븐랩스 미나 kr-mina(voice aiUUgjHa4mpHf6UenZuf, eleven_v3, 1.0 합성 + atempo 1.35) — 원본(만템) 나레 여성·해요체",
         "sources": {"XzCEZtLDV-A": {"채널": "장공장장윤정", "제목": S["source"]["title"], "업로드": "2026-03-18", "해상도": "1920x1080 29.97fps", "길이": 931.5}},
         "blocks": {b: list(v) for b, v in blk.items()}, "dur_est": dur,
         "source_shot_cuts": [109.01, 114.35, 122.69, 133.03, 146.05, 147.15, 155.96, 159.13, 161.03, 162.26, 195.70, 200.30, 202.90, 212.61,
                              216.65, 224.76, 226.23, 237.70, 240.04, 243.61, 261.83, 263.96, 267.43],
         "shots": shots}
    (D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads((ROOT / "channel/mantem/frame_얜샷템.json").read_text(encoding="utf-8"))
    for l in fr["layers"]:
        if l.get("role") == "title":
            l["text"] = TITLE
        if l.get("role") == "label":
            l["text"] = LABEL
    fr["made_from"]["note"] = "channel/mantem/frame_얜샷템.json 에서 제목·출처 글만 바꿈(build_plan.py)"
    (D / "frame.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    print("dur", dur, "blocks", blk)
    for s in shots:
        print(f"#{s['i']:2d} {s['line']} {s['t_final'][0]:6.2f}-{s['t_final'][1]:6.2f} ({s['dur']:.2f}) ss{s['ss']} a{s.get('audio_ss', '-')} Y{s['Y']} {s['ours'][:30]}")
    for c in caps:
        print(f"  {c['t0']:6.2f}-{c['t1']:6.2f} [{c['kind']}] {c['text']} ({len(c['text'].replace(' ', ''))}자)")
    if "--no-plan" not in sys.argv:
        r = subprocess.run([sys.executable, str(ROOT / "tools/calcopy/engine/remake.py"), str(D / "뜯기/뜯기.json"), str(D / "frame.json"),
                            "--out", str(D / "plan"), "--materials", str(D / "재료.json"), "--script", str(D / "대본.json"), "--plan-only"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        print(r.stdout[-800:], r.stderr[-1500:])


if __name__ == "__main__":
    main()
