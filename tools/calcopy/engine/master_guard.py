# -*- coding: utf-8 -*-
"""완성본 소리 최고점 지킴이 — 영상+소리 → final.mp4(AAC) 를 만들고, **인코딩 뒤** 진짜 최고점(true peak)이 넘치면 고친다(관제 097, 2026-10-18).

왜: 마스터의 alimiter 는 표본 최고점만 막는다. 날카로운 순간음(TTS 'ㅆ·ㄱ' 끝소리 등)은 AAC 인코딩에서 크게 튄다 —
  10-18 실측 잇썸홈 원샷1_전동칫솔: mix.wav 최고점 −0.9 → final.mp4 +6.3 dBFS(16.25초 '쏙' 한 프레임) · 하이브리드 김가연 −0.8 → +0.4.
고치는 법(실측으로 고름): 4배로 올려(176.4kHz) 리미터 → 되돌리기 = 표본 사이 최고점까지 막는다.
  같은 소리로 비교: 그대로 +6.3 / 4배 리미터 −1.5dB → −1.3 dBFS, LUFS −8.8 그대로 / attack 0.1 + −3dB → +1.1(더 나쁨).
판단 주인: 완성본 인코딩·최고점 판정은 encode_final() 한 곳. preset_make·hybrid render_itssum·render_jaemi 는 이걸 부른다.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

SR_UP = 176400            # 44.1kHz × 4 — 표본 사이 최고점을 보이게
LIMIT_DB = -1.5           # 첫 시도 리미터 한계(dBFS) — 실측 −1.3 dBFS 로 B2(≤ −0.5) 안
STEP_DB = 1.0             # 그래도 넘치면 이만큼 더 내린다
MAX_TRIES = 3


def _run(cmd):
    r = subprocess.run([str(c) for c in cmd], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(f"ffmpeg 실패({r.returncode}): {(r.stderr or '')[-600:]}")
    return r


def loudness(p) -> tuple[float, float]:
    """(통합 LUFS, 진짜 최고점 dBFS) — ebur128 peak=true(preset_make B2 와 같은 자)."""
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def tp_filter(limit_db: float) -> str:
    return f"aresample={SR_UP},alimiter=limit={10 ** (limit_db / 20):.4f}:level=false:attack=1:release=30,aresample=44100"


def _mux(video, audio, final):
    _run(["ffmpeg", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final])


def encode_final(video, mix, final, peak_max_db: float = -0.5, log=print) -> dict:
    """(판단 주인) 영상(소리 없음)+mix.wav → final.mp4. 인코딩 뒤 진짜 최고점 > peak_max_db 면 4배 리미터 판 mix 로 다시(한계를 STEP_DB 씩 내려 최대 MAX_TRIES).
    반환 = 표식 {made_by, tries:[{limit_db, lufs, tp}], mix_used, lufs, tp, ok}. 원래 mix.wav 는 건드리지 않는다."""
    video, mix, final = Path(video), Path(mix), Path(final)
    _mux(video, mix, final)
    I, tp = loudness(final)
    tries, used = [{"limit_db": None, "lufs": I, "tp": tp}], mix
    limit = LIMIT_DB
    while tp > peak_max_db and len(tries) <= MAX_TRIES:
        safe = mix.with_name(mix.stem + f"_tp{abs(limit):.1f}.wav")
        _run(["ffmpeg", "-y", "-i", mix, "-af", tp_filter(limit), "-ar", "44100", safe])
        _mux(video, safe, final)
        I, tp = loudness(final)
        tries.append({"limit_db": limit, "lufs": I, "tp": tp})
        log(f"  [최고점 지킴이] 인코딩 뒤 {tries[-2]['tp']} dBFS > {peak_max_db} → 4배 리미터 {limit} dB → {tp} dBFS · {I} LUFS")
        used, limit = safe, limit - STEP_DB
    return {"made_by": "tools/calcopy/engine/master_guard.encode_final", "tries": tries, "mix_used": str(used), "lufs": I, "tp": tp,
            "ok": tp <= peak_max_db}
