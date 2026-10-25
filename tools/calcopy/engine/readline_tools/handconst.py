# -*- coding: utf-8 -*-
"""판 '손 상수' 칸 벤치 실측(handconst) — 판 파일 숫자 칸 중 why 가 '손 상수'인 칸을 벤치 줄판독 + 원본 소리로 잰다.

어디서 왔나: 관제 263(칼카피 공통 규칙 표준) — preset_card 가 '손 상수' why 를 근거로 치지 않게 된 뒤(b9bddde4b) 남은 칸을 재는 도구.
렌더러(render_bench)가 그 칸을 어떻게 쓰는지와 **같은 양**을 벤치에서 잰다:

| 판 칸 | 렌더러 쓰임 | 벤치에서 재는 양 |
|---|---|---|
| cps_target | timeline 글자÷cps 어림 · TTS 배속 목표 · match speech.cps.나레 | 편별 나레 글자/자막 초(kal_analyze.rules_of episodes.narr_cps) 중앙 |
| length.min/max | 길이 문턱 | 편 길이 p17·p83(내림·올림) |
| timing.gap(·gap_after_tts/orig·gap_oo) | 줄(문장) 사이 무음(gap_between) | 줄 경계(화자 바뀜 또는 앞 조각이 문장 끝) 소리 쉼 — 경계 ±0.15초 창 안 가장 긴 '쉼 프레임' 연속(checks.pauses_between 과 같은 창) · 쉼 문턱 = 편별 (말 p50 + 바닥 p5)/2 dB(BGM 이 깔려 절대 −35dB 무음이 없다) |
| timing.tail | 마지막 줄 소리 끝 → 영상 끝 | 편 길이 − 마지막 낱말 끝(로컬 위스퍼 asrwords.py 산출, p≥0.4) — 자막 꼬리는 벤치가 마지막 자막을 끝까지 붙들어 참고만 |
| caption.chunk_max_chars | 대본 자막 조각 나누기 상한 | 나레 조각 자수(공백 뺀) p90(나레 < MIN_N 이면 전체) |
| caption.typing_cps | 타이핑 덩어리 글자 시각 | 타이핑 줄 type_cps, 없으면 글자 ÷ enter_ms 의 중앙 (0줄이면 값 안 쓰임으로 보고) |
| caption.band | caption_side 자리(자막 띠 y) | 나레(없으면 전체) 픽셀 줄 y0·y1 중앙 ± 외곽 px 중앙(채움 잉크) |
| cuts.push_tts/orig | 우리 카메라 밀기 | 줄 motion(cam/still/zoom_in…) 화자별 분포 — zoom_in 이 과반이면 세기 미측정 |
| bgm.db_below_voice | 목소리 대비 BGM dB | 말 p50 − (말 없는 구간 바닥 p10, 없으면 줄 경계 쉼 프레임 중앙) |
| bgm.duck_narr_db | 말할 때 더 줄임 | 줄 경계 쉼 바닥 − 말 없는 구간 바닥(−3dB 넘게 낮을 때만, 아니면 0) |
| bgm.duck_orig_db | 원음 구간 BGM 줄임 | 원음 조각 바닥 p5 − 나레 조각 바닥 p5(−3dB 넘게 낮을 때만, 아니면 0 · 원음 0줄이면 0) |
| bgm.fade_out | 끝 페이드 초 | 끝 3~1초 전 p50 −6dB 이상인 마지막 프레임 → 영상 끝까지 초(중앙) |

소리 = 원본 mp4 를 ffmpeg 16kHz 모노로, 20ms RMS dBFS. 원본 소리는 나레+원음+BGM 이 섞여 있으므로 BGM 칸은 '신호' 급이다(분리 모델 없음).
출력: 칸별 {value, n, per_ep, method} — 판 why 에 근거 편·k/n·명령을 적을 때 이 출력을 인용한다.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/handconst.py <slug> [--src-dir C:/숏템_칼카피/<slug>/src] [--out channel/<slug>/_kal/손상수_실측.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from tools.calcopy.engine import kal_analyze as KA  # noqa: E402

SR = 16000
HOP = 0.02
WIN = 0.15          # checks.pauses_between 과 같은 경계 앞뒤 창
MIN_RUN = 0.04      # 쉼으로 칠 최소 길이(2프레임)
FREE_MIN = 0.4      # 말 없는 구간(자막 없음)으로 칠 최소 길이
ASR_P = 0.4        # 위스퍼 낱말 확률 하한(꼬리 재기)
DUCK_MIN = 3.0      # 이보다 작은 dB 차는 덕킹으로 안 친다(측정 잡음)
_END_RE = re.compile(r"[?!.~…]$")


def audio_db(mp4: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    x = np.frombuffer(raw, np.float32)
    h = int(SR * HOP)
    n = len(x) // h
    fr = x[: n * h].reshape(n, h)
    return 10 * np.log10(np.mean(fr.astype(np.float64) ** 2, axis=1) + 1e-12)


def _idx(t: float, n: int) -> int:
    return max(0, min(n, int(round(t / HOP))))


def _frames(db: np.ndarray, spans) -> np.ndarray:
    m = np.zeros(len(db), bool)
    for a, b in spans:
        m[_idx(a, len(db)):_idx(b, len(db))] = True
    return db[m]


def sentence_end(text: str) -> bool:
    t = (text or "").strip()
    if _END_RE.search(t):
        return True
    e = KA._ending(t)
    return e in KA._ENDINGS


def _pix(l: dict) -> bool:
    """줄 확신도(confidence)에 '픽셀'이 있으면 y 가 픽셀 실측(confidence 꼴은 채널마다 글·사전으로 다르다)."""
    return "픽셀" in json.dumps(l.get("confidence"), ensure_ascii=False)


def p(xs, q):
    return float(np.percentile(xs, q)) if len(xs) else None


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 3) if xs else None


def last_word_end(asr: str | None, dur: float) -> float | None:
    """로컬 위스퍼(asrwords.py 산출) 마지막 낱말 끝 — p ≥ ASR_P 인 낱말만(나레 없는 구간 환각 거름)."""
    if not asr or not Path(asr).exists():
        return None
    ws = [w for w in json.loads(Path(asr).read_text(encoding="utf-8")).get("words") or [] if (w.get("p") or 0) >= ASR_P and str(w.get("w") or "").strip()]
    ws = [w for w in ws if float(w["t1"]) <= dur + 0.05]
    return max(float(w["t1"]) for w in ws) if ws else None


def episode(doc: dict, mp4: str | None, asr: str | None = None) -> dict:
    dur = float(doc.get("dur") or 0)
    lines = [l for l in doc.get("lines") or [] if (l.get("layer") or "채널") != "원본박힘"]
    speech = sorted([l for l in lines if KA._sp(l.get("speaker")) in ("나레", "원음") and l.get("t1") is not None],
                    key=lambda l: float(l["t0"]))
    out = {"id": doc.get("id"), "dur": dur, "n_speech": len(speech)}
    out["tail_caption"] = round(dur - max(float(l["t1"]) for l in speech), 3) if speech else None
    lw = last_word_end(asr, dur)
    out["last_word_t1"] = lw
    out["tail"] = round(max(0.0, dur - lw), 3) if lw is not None else None
    # 경계: 화자 바뀜 또는 앞 조각이 문장 끝
    B = []
    for a, b in zip(speech, speech[1:]):
        sa, sb = KA._sp(a.get("speaker")), KA._sp(b.get("speaker"))
        if sa != sb or sentence_end(a.get("text")):
            B.append({"prev": sa, "next": sb, "t1": float(a["t1"]), "t0": float(b["t0"]), "cap_gap": round(max(0.0, float(b["t0"]) - float(a["t1"])), 3)})
    out["bounds_n"] = len(B)
    if not mp4 or not Path(mp4).exists():
        out["audio"] = None
        out["bounds"] = B
        return out
    db = audio_db(mp4)
    n = len(db)
    sp_frames = _frames(db, [(float(l["t0"]), float(l["t1"])) for l in speech])
    narr = [(float(l["t0"]), float(l["t1"])) for l in speech if KA._sp(l.get("speaker")) == "나레"]
    orig = [(float(l["t0"]), float(l["t1"])) for l in speech if KA._sp(l.get("speaker")) == "원음"]
    lv, fl = p(sp_frames, 50), p(sp_frames, 5)
    thr = (lv + fl) / 2 if lv is not None else None
    pause_db = []
    for x in B:
        a, b = _idx(x["t1"] - WIN, n), _idx(x["t0"] + WIN, n)
        seg = db[a:b] < thr
        best, run, best_end = 0, 0, a
        for i, q in enumerate(seg):
            run = run + 1 if q else 0
            if run > best:
                best, best_end = run, a + i + 1
        x["pause"] = round(best * HOP, 3) if best * HOP >= MIN_RUN else 0.0
        if best * HOP >= MIN_RUN:
            pause_db.extend(db[best_end - best:best_end].tolist())
    # 말 없는 구간(자막 없음) — 0~끝 사이 자막 조각 빈 곳 ≥ FREE_MIN, 끝 0.5초 페이드는 뺀다
    cover = sorted([(float(l["t0"]), float(l["t1"])) for l in lines if l.get("t1") is not None])
    free, cur = [], 0.0
    for a, b in cover:
        if a - cur >= FREE_MIN:
            free.append((cur, a))
        cur = max(cur, b)
    if dur - 0.5 - cur >= FREE_MIN:
        free.append((cur, dur - 0.5))
    free_fr = _frames(db, free)
    # 끝 페이드
    ref = p(db[_idx(dur - 3, n):_idx(dur - 1, n)], 50)
    last = None
    if ref is not None:
        idx = np.where(db[: _idx(dur, n)] >= ref - 6)[0]
        last = float(idx[-1] * HOP + HOP) if len(idx) else None
    out["audio"] = {
        "speech_p50": round(lv, 2) if lv is not None else None, "speech_p5": round(fl, 2) if fl is not None else None,
        "thr": round(thr, 2) if thr is not None else None,
        "pause_floor": round(float(np.median(pause_db)), 2) if pause_db else None, "pause_frames": len(pause_db),
        "free_sec": round(sum(b - a for a, b in free), 2), "free_p10": round(p(free_fr, 10), 2) if len(free_fr) else None,
        "narr_p5": round(p(_frames(db, narr), 5), 2) if narr else None, "orig_p5": round(p(_frames(db, orig), 5), 2) if orig else None,
        "end_ref": round(ref, 2) if ref is not None else None, "fade_out": round(max(0.0, dur - last), 3) if last is not None else None,
    }
    out["bounds"] = B
    return out


def measure(slug: str, src_dir: str | None, asr_dir: str | None = None) -> dict:
    files = sorted(glob.glob(str(REPO / "channel" / slug / "줄판독" / "*.json")))
    docs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    src_dir = src_dir or f"C:/숏템_칼카피/{slug}/src"
    R = KA.rules_of(docs)
    asr_dir = asr_dir or str(Path(src_dir).parent / "work" / "asrw")
    eps = [episode(d, str(Path(src_dir) / f"{d.get('id')}.mp4"), str(Path(asr_dir) / f"{d.get('id')}.json")) for d in docs]
    O = {"slug": slug, "n_docs": len(docs), "src_dir": src_dir, "docs": [Path(f).stem for f in files],
         "made_by": "tools/calcopy/engine/readline_tools/handconst.py", "cells": {}}
    C = O["cells"]
    cps = [e["narr_cps"] for e in R["episodes"] if e.get("narr_cps")]
    C["cps_target"] = {"value": round(statistics.median(cps), 2) if cps else None, "n": len(cps), "per_ep": cps,
                       "method": "kal_analyze.rules_of episodes.narr_cps(나레 글자/자막 초) 편 중앙"}
    durs = sorted(e["dur"] for e in R["episodes"])
    if durs:
        C["length"] = {"min": math.floor(p(durs, 17)), "max": math.ceil(p(durs, 83)), "n": len(durs), "per_ep": durs,
                       "method": "편 길이 p17 내림·p83 올림"}
    C["timing.tail"] = {"value": med([e["tail"] for e in eps]), "n": sum(e["tail"] is not None for e in eps),
                        "per_ep": [e["tail"] for e in eps], "caption_tail": [e["tail_caption"] for e in eps],
                        "method": "편 길이 − 마지막 말 소리 끝(로컬 위스퍼 asrwords 마지막 낱말 t1, p≥0.4), 편 중앙 · 자막 꼬리(편 길이 − 마지막 말 조각 t1)는 참고 — 벤치는 마지막 자막을 끝까지 붙들어 0 이 많다"}
    allb = [(e["id"], b) for e in eps for b in e["bounds"] if "pause" in b]

    def gap_of(f):
        xs = [b["pause"] for _, b in allb if f(b)]
        cg = [b["cap_gap"] for _, b in allb if f(b)]
        return {"value": med(xs), "n": len(xs), "nonzero": sum(1 for x in xs if x > 0), "p25": round(p(xs, 25), 3) if xs else None,
                "p75": round(p(xs, 75), 3) if xs else None, "cap_gap_med": med(cg)}
    C["timing.gap"] = {**gap_of(lambda b: True), "method": "줄 경계(화자 바뀜·앞 조각 문장 끝) 소리 쉼 중앙(경계 ±0.15초 창, 쉼 문턱 (말 p50+p5)/2)"}
    C["timing.gap_after_tts"] = {**gap_of(lambda b: b["prev"] == "나레"), "method": "위 경계 중 앞이 나레"}
    C["timing.gap_after_orig"] = {**gap_of(lambda b: b["prev"] == "원음"), "method": "위 경계 중 앞이 원음(원음→원음 포함)"}
    C["timing.gap_after_orig_x_oo"] = {**gap_of(lambda b: b["prev"] == "원음" and b["next"] != "원음"), "method": "앞 원음·뒤 나레(gap_oo 칸이 있을 때 gap_after_orig)"}
    C["timing.gap_oo"] = {**gap_of(lambda b: b["prev"] == "원음" and b["next"] == "원음"), "method": "원음→원음 문장 경계"}
    # 자막 조각
    norm = [KA._norm_line(l, float(d.get("dur") or 0)) for d in docs for l in d.get("lines") or [] if (l.get("layer") or "채널") != "원본박힘"]
    nc = [x["chars"] for x in norm if x["sp"] == "나레" and x["chars"] > 0]
    who = "나레"
    if len(nc) < KA.MIN_N:
        nc, who = [x["chars"] for x in norm if x["chars"] > 0], "전체"
    C["caption.chunk_max_chars"] = {"value": int(round(p(nc, 90))) if nc else None, "n": len(nc), "who": who,
                                    "p50": p(nc, 50), "max": max(nc) if nc else None, "method": f"{who} 조각 자수 p90"}
    allL = [l for d in docs for l in d.get("lines") or [] if (l.get("layer") or "채널") != "원본박힘"]
    ty = []
    for l in allL:
        if KA.enter_key(l.get("enter")) == "typing":
            c = l.get("type_cps") or (KA._chars(l.get("text")) / (l["enter_ms"] / 1000) if l.get("enter_ms") else None)
            ty.append(round(float(c), 2) if c else None)
    C["caption.typing_cps"] = {"value": med(ty), "k": len(ty), "measured": sum(x is not None for x in ty), "n": len(allL),
                               "method": "타이핑 줄 type_cps(없으면 글자÷enter_ms) 중앙"}
    bl = [l for l in allL if KA._sp(l.get("speaker")) == "나레" and isinstance(l.get("y"), list) and len(l["y"]) == 2 and _pix(l)]
    bwho = "나레"
    if len(bl) < KA.MIN_N:
        bl, bwho = [l for l in allL if isinstance(l.get("y"), list) and len(l["y"]) == 2 and _pix(l)], "전체"
    if bl:
        op = [(l["outline"].get("px") or 0) if isinstance(l.get("outline"), dict) else 0 for l in bl]
        o = statistics.median(op)
        y0, y1 = statistics.median(l["y"][0] for l in bl), statistics.median(l["y"][1] for l in bl)
        C["caption.band"] = {"value": [int(round(y0 + o)), int(round(y1 - o))], "n": len(bl), "who": bwho, "bbox_med": [y0, y1], "outline_med": o,
                             "method": f"{bwho} 픽셀 줄 y 중앙 ± 외곽 px 중앙(채움 잉크)"}
    else:
        C["caption.band"] = {"value": None, "n": 0, "method": "픽셀 줄 y 없음"}
    from collections import Counter
    for key, sp in (("cuts.push_tts", "나레"), ("cuts.push_orig", "원음")):
        mo = Counter(str(l.get("motion")) for l in allL if KA._sp(l.get("speaker")) == sp)
        tot = sum(mo.values())
        zi = mo.get("zoom_in", 0)
        C[key] = {"value": 0.0 if tot and zi / tot < 0.5 else None, "k_zoom_in": zi, "n": tot, "motion": dict(mo.most_common()),
                  "method": f"{sp} 줄 motion 분포 — zoom_in 과반이 아니면 push 0(재료 움직임 그대로), 과반이면 세기 미측정"}
    A = [e["audio"] for e in eps if e.get("audio")]
    lv = [a["speech_p50"] for a in A if a["speech_p50"] is not None]
    pf = [a["pause_floor"] for a in A]
    fr = [a["free_p10"] if a["free_sec"] >= 1.0 else None for a in A]
    below = []
    for a in A:
        base = a["free_p10"] if (a["free_sec"] >= 1.0 and a["free_p10"] is not None) else a["pause_floor"]
        below.append(round(a["speech_p50"] - base, 2) if (base is not None and a["speech_p50"] is not None) else None)
    C["bgm.db_below_voice"] = {"value": med(below), "n": sum(x is not None for x in below), "per_ep": below,
                               "method": "말 p50 − (말 없는 구간 ≥1초면 그 p10, 아니면 줄 경계 쉼 프레임 중앙)"}
    dn = []
    for a in A:
        if a["pause_floor"] is not None and a["free_sec"] >= 1.0 and a["free_p10"] is not None:
            d = a["pause_floor"] - a["free_p10"]
            dn.append(round(d, 2) if d <= -DUCK_MIN else 0.0)
        else:
            dn.append(None)
    C["bgm.duck_narr_db"] = {"value": med(dn) if any(x is not None for x in dn) else 0.0, "n": sum(x is not None for x in dn), "per_ep": dn,
                             "method": "줄 경계 쉼 바닥 − 말 없는 구간 바닥(−3dB 넘게 낮으면 그 차, 아니면 0). 비교 편 0이면 0 = db_below_voice 가 이미 말 사이 바닥 기준"}
    do = []
    for a in A:
        if a["orig_p5"] is None:
            do.append(None)
        elif a["narr_p5"] is None:
            do.append(None)
        else:
            d = a["orig_p5"] - a["narr_p5"]
            do.append(round(d, 2) if d <= -DUCK_MIN else 0.0)
    C["bgm.duck_orig_db"] = {"value": med(do) if any(x is not None for x in do) else 0.0, "n": sum(x is not None for x in do), "per_ep": do,
                             "method": "원음 조각 바닥 p5 − 나레 조각 바닥 p5(−3dB 넘게 낮으면 그 차, 아니면 0). 비교 편 0이면 0(원음·나레 같이 나온 편 없음)"}
    fo = [a["fade_out"] for a in A]
    C["bgm.fade_out"] = {"value": med(fo), "n": sum(x is not None for x in fo), "per_ep": fo,
                         "method": "끝 3~1초 전 p50 −6dB 이상 마지막 프레임 → 끝까지 초, 편 중앙"}
    O["episodes"] = [{k: v for k, v in e.items() if k != "bounds"} | {"bounds": e["bounds"]} for e in eps]
    return O


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--src-dir")
    ap.add_argument("--asr-dir", help="asrwords.py 산출 폴더(기본 <src_dir>/../work/asrw)")
    ap.add_argument("--out")
    ap.add_argument("--brief", action="store_true", help="칸 요약만 출력")
    a = ap.parse_args(argv)
    O = measure(a.slug, a.src_dir, a.asr_dir)
    if a.out:
        Path(a.out).write_text(json.dumps(O, ensure_ascii=False, indent=1), encoding="utf-8")
    view = {k: {kk: vv for kk, vv in v.items() if kk not in ("method",)} for k, v in O["cells"].items()}
    print(json.dumps(view if a.brief else O, ensure_ascii=False, indent=1 if not a.brief else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
