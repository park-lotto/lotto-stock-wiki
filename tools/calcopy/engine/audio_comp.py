# -*- coding: utf-8 -*-
"""소리 구성(audio.composition) — 화자·나레 종류·원음 유무·덕킹·자막=나레·효과음 솟음 (사장님 2026-10-16).

사전: 나레 1명 / 나레+역할 2명 / 역할극만 / 해외 원음+한국어 나레+자막 / 원음만+자막 / 나레 없음.
재료: 받아쓰기(제미나이: 구절별 speaker·lang·kind + 화자별 gender·voice) + bench audio.mono(전체 섞인 소리 — 분리 금지,
      메모리 `분리검출이_효과음을_목소리로_가져간다`).
문턱은 전부 이름과 이유로 여기 있다. **실측 검증 전 문턱**(피치·솟음)은 결과에 method 로 '미검증'을 같이 적는다.
"""
from __future__ import annotations

import difflib
import re
import statistics as st

import numpy as np

from shopping_shorts.channelkit.bench import audio as baudio
from shopping_shorts.channelkit.bench.constants import SR

WIN = 0.020             # 20ms RMS 창(bench WIN_S 와 같은 크기)
SPIKE_DB = 10.0         # 솟음 = 1.5초 이동 중앙값보다 10dB 이상 (미검증 문턱)
SPIKE_MED_S = 1.5
SPIKE_LEN = (0.05, 1.5)  # 효과음 솟음 길이(초) — 사장님 지정
PITCH_SR = 16000
PITCH_RANGE = (70.0, 400.0)
VOICED_R = 0.5          # 자기상관 최고점 > 0.5 = 유성음 프레임

COMPOSITIONS = ["나레 1명", "나레+역할 2명", "역할극만", "해외 원음+한국어 나레+자막", "원음만+자막", "나레 없음"]


def _levels(x: np.ndarray) -> np.ndarray:
    W = int(SR * WIN)
    n = x.size // W
    return 20 * np.log10(np.sqrt((x[:n * W].reshape(n, W) ** 2).mean(axis=1)) + 1e-9)


def _mask(segs: list[dict], n: int) -> np.ndarray:
    m = np.zeros(n, bool)
    for s in segs:
        m[int(s["start"] / WIN):int(s["end"] / WIN) + 1] = True
    return m


def spikes(lv: np.ndarray) -> list[tuple[float, float]]:
    """솟음 = 이동 중앙값 + SPIKE_DB 를 넘는 구간 중 길이 SPIKE_LEN 안. [(시작초, 길이초)]."""
    k = int(SPIKE_MED_S / WIN)
    pad = np.pad(lv, (k // 2, k // 2), mode="edge")
    med = np.array([np.median(pad[i:i + k]) for i in range(0, lv.size)])
    hot = lv > med + SPIKE_DB
    out, i = [], 0
    while i < hot.size:
        if hot[i]:
            j = i
            while j < hot.size and hot[j]:
                j += 1
            d = (j - i) * WIN
            if SPIKE_LEN[0] <= d <= SPIKE_LEN[1]:
                out.append((round(i * WIN, 2), round(d, 2)))
            i = j
        else:
            i += 1
    return out


def pitch_stats(x: np.ndarray, segs: list[dict]) -> dict | None:
    """나레 구간 유성음 피치(자기상관) 반음 표준편차 — TTS 는 좁고 사람은 넓다는 가설용 지표(문턱 미검증)."""
    y = x[::SR // PITCH_SR] if SR % PITCH_SR == 0 else x
    fl, hop = int(0.04 * PITCH_SR), int(0.02 * PITCH_SR)
    lo, hi = int(PITCH_SR / PITCH_RANGE[1]), int(PITCH_SR / PITCH_RANGE[0])
    f0 = []
    for s in segs:
        a, b = int(s["start"] * PITCH_SR), int(s["end"] * PITCH_SR)
        for i in range(a, max(a, b - fl), hop):
            fr = y[i:i + fl]
            if fr.size < fl or fr.std() < 1e-4:
                continue
            fr = fr - fr.mean()
            ac = np.correlate(fr, fr, "full")[fl - 1:]
            ac = ac / (ac[0] + 1e-12)
            lag = lo + int(np.argmax(ac[lo:hi]))
            if ac[lag] > VOICED_R:
                f0.append(PITCH_SR / lag)
    if len(f0) < 20:
        return None
    semi = 12 * np.log2(np.array(f0) / np.median(f0))
    return {"voiced_frames": len(f0), "f0_median_hz": round(float(np.median(f0)), 1),
            "semitone_std": round(float(semi.std()), 2)}


def _norm(t: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t)


def composition(path: str, meta: dict, asr: dict, ocr_texts: list[str]) -> dict:
    """asr = 제미나이 받아쓰기 원본 dict(speakers·segments·ambient). 항목마다 못 재면 failed:이유."""
    segs = asr.get("segments") or []
    spk = {str(s.get("id")): s for s in (asr.get("speakers") or []) if isinstance(s, dict)}
    out: dict = {"method": "받아쓰기(제미나이 speaker·lang·kind) + bench audio.mono 20ms RMS(분리 없음)", "dict": COMPOSITIONS}
    dur = meta["duration"] or 1.0
    # (1) 화자
    secs: dict[str, float] = {}
    for s in segs:
        secs[s["speaker"]] = secs.get(s["speaker"], 0.0) + max(0.0, s["end"] - s["start"])
    tot = sum(secs.values())
    out["speakers"] = [{"n": k, "gender": (spk.get(k) or {}).get("gender", "unknown"),
                        "voice_guess": (spk.get(k) or {}).get("voice", "unknown"),
                        "share": round(v / tot, 3) if tot else 0.0,
                        "kinds": sorted({s["kind"] for s in segs if s["speaker"] == k}),
                        "langs": sorted({s["lang"] for s in segs if s["speaker"] == k})}
                       for k, v in sorted(secs.items(), key=lambda kv: -kv[1])]
    narr = [s for s in segs if s["kind"] == "narration" and s["lang"] == "ko"]
    dialog = [s for s in segs if s["kind"] == "dialog" and s["lang"] == "ko"]
    src = [s for s in segs if s["kind"] == "source" or s["lang"] not in ("ko", "")]
    x = baudio.mono(path)
    lv = _levels(x) if x is not None else None
    # (2) 나레 종류
    if not narr:
        out["narration"] = "none"
    else:
        guesses = {(spk.get(s["speaker"]) or {}).get("voice", "unknown") for s in narr}
        out["narration"] = guesses.pop() if len(guesses) == 1 and list(guesses)[0] in ("tts", "human") else "unknown"
        ps = pitch_stats(x, narr) if x is not None else None
        gaps = [b["start"] - a["end"] for a, b in zip(narr, narr[1:]) if b["start"] - a["end"] > 0.05]
        out["narration_metrics"] = {"pitch": ps or {"failed": "유성음 프레임 20개 미만"},
                                    "pause_cv": round(st.pstdev(gaps) / st.mean(gaps), 2) if len(gaps) >= 3 else None,
                                    "method": "narration = 제미나이 귀 추정(tts/human). 피치 반음 표준편차·쉼 변동계수는 참고 지표(문턱 미검증)"}
    # (3) 원음 + 덕킹
    amb = str(asr.get("ambient") or "").strip()
    # 배경음악만 있는 것은 원음이 아니다(2026-10-16 핫템 H9: BGM 만 있어도 True) — 현장음 설명에서 음악 낱말만 있으면 뺀다
    amb_src = bool(amb) and not re.fullmatch(r"[\s,./·]*(배경\s*음악|음악|BGM|bgm|music|노래)[\s,./·]*", amb)
    out["source_audio_kept"] = bool(src or amb_src)
    out["source_evidence"] = {"foreign_or_source_segments": len(src), "ambient": asr.get("ambient") or ""}
    if lv is None:
        out["duck_db"] = {"failed": "소리 없음"}
    elif not narr:
        out["duck_db"] = {"failed": "한국어 나레 구간 없음"}
    else:
        nm = _mask(narr, lv.size)
        rest = ~_mask(segs, lv.size)
        if rest.sum() < 25:
            out["duck_db"] = {"failed": "말 없는 구간 0.5초 미만"}
        else:
            out["duck_db"] = round(float(np.median(lv[nm]) - np.median(lv[rest])), 2)
            out["duck_method"] = "나레 구간 RMS 중앙값 − 말 없는 구간 RMS 중앙값(dB). 원음이 나레 밑에서 얼마나 눌렸는지의 근사(분리 없음)"
    # (4) 자막 = 나레
    o = _norm("".join(ocr_texts))
    n_txt = _norm("".join(s["text"] for s in narr + dialog))
    if not o:
        out["caption_eq_narration"] = {"failed": "자막 글자(OCR) 없음"}
    elif not n_txt:
        out["caption_eq_narration"] = 0.0
    else:
        m = sum(b.size for b in difflib.SequenceMatcher(None, o, n_txt, autojunk=False).get_matching_blocks())
        out["caption_eq_narration"] = round(m / len(o), 3)
        out["caption_eq_method"] = "자막 글자(공백·부호 뺌) 중 한국어 말소리 글자와 겹치는 비율(difflib 일치 블록)"
    # (5) 효과음 솟음
    if lv is None:
        out["sfx_per_sec"] = {"failed": "소리 없음"}
    else:
        sp = spikes(lv)
        speech = _mask(segs, lv.size)
        outside = [s for s in sp if not speech[min(lv.size - 1, int(s[0] / WIN))]]
        out["sfx_per_sec"] = round(len(sp) / dur, 3)
        out["sfx"] = {"count": len(sp), "outside_speech": len(outside), "outside_per_sec": round(len(outside) / dur, 3),
                      "times": sp, "method": f"20ms RMS가 {SPIKE_MED_S}s 이동중앙값+{SPIKE_DB}dB 넘고 길이 {SPIKE_LEN}s (문턱 미검증, 말소리 음절도 섞일 수 있음)"}
    # 사전 분류
    has_narr, has_dialog = bool(narr), bool(dialog)
    nspk_ko = len({s["speaker"] for s in narr + dialog})
    if has_narr and src:
        kind = "해외 원음+한국어 나레+자막"
    elif has_narr and has_dialog:
        kind = "나레+역할 2명" if nspk_ko >= 2 else "나레 1명"
    elif has_narr:
        kind = "나레 1명"
    elif has_dialog:
        kind = "역할극만"
    elif src or out["source_audio_kept"]:
        kind = "원음만+자막"
    else:
        kind = "나레 없음"
    out["kind"] = kind
    return out
