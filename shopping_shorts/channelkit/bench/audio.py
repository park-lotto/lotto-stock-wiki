# -*- coding: utf-8 -*-
"""audio — A.*  통합 LUFS·TP·LRA·단기 폭·오프닝 음량(두 자)·8~16k 고역.

자 정의(설계 §1, 볼케이노 규율):
  - I/LRA/TP = ebur128 stderr의 **마지막** `^\\s*I:` / `LRA:` / `Peak:` (re.M) — Summary 값
  - S 폭 = 정렬 인덱스 S[int(n·.9)] − S[int(n·.1)], S > −70만, n < 20 이면 None, 앞부분 버리지 않음
  - 모노 = (L+R)/2 f32 (`-ac 1`은 +3.01dB)
  - 8~16k = kaiser FIR(1001탭, β8.6, 중심 이득 정규화) 통과 후 파일 전체 RMS dBFS
  - 오프닝은 이름을 가른다: A.openvoice(20ms RMS 바닥 대비 p90, 나레 채널) / A.open3s_M(ebur M 중앙값 차, BGM 채널)
"""
from __future__ import annotations

import re

import numpy as np

from . import probe
from .constants import SR, S_FLOOR, S_MIN_N, HF_LO, HF_HI, HF_NTAPS, HF_BETA, WIN_S, OPEN_S


def ebur128(path: str) -> dict:
    """ebur128 요약 + 단기 폭 + 순간(M) 오프닝 대비."""
    log = probe.ffmpeg_log(["-i", path, "-vn", "-af", "ebur128=peak=true:framelog=info", "-f", "null", "-"])
    I = re.findall(r"^\s*I:\s*(-?[\d.]+)\s*LUFS", log, re.M)
    LRA = re.findall(r"^\s*LRA:\s*(-?[\d.]+)\s*LU", log, re.M)
    TP = re.findall(r"^\s*Peak:\s*(-?[\d.]+)\s*dBFS", log, re.M)
    S = sorted(float(x) for x in re.findall(r"S:\s*(-?[\d.]+)", log) if float(x) > S_FLOOR)
    spread = round(S[int(len(S) * .9)] - S[int(len(S) * .1)], 2) if len(S) >= S_MIN_N else None
    M = [(float(t), float(m)) for t, m in re.findall(r"t:\s*([\d.]+)\s+.*?M:\s*(-?[\d.]+)", log)]
    m_open = [m for t, m in M if t <= OPEN_S and m > S_FLOOR]
    m_rest = [m for t, m in M if t > OPEN_S and m > S_FLOOR]
    return {"I": float(I[-1]) if I else None, "LRA": float(LRA[-1]) if LRA else None, "TP": float(TP[-1]) if TP else None,
            "S_spread": spread, "S_n": len(S),
            "open3s_M": round(float(np.median(m_open)), 1) if m_open else None,
            "rest_M": round(float(np.median(m_rest)), 1) if m_rest else None}


def mono(path: str) -> np.ndarray | None:
    """(L+R)/2 f32 모노."""
    st = probe.pcm_stereo(path, SR)
    return None if st is None else (st[:, 0] + st[:, 1]) / 2.0


def band_rms_db(x: np.ndarray, lo: float, hi: float) -> float:
    """kaiser 창 선형위상 FIR 대역통과(중심 이득 정규화) → RMS dBFS."""
    m = np.arange(HF_NTAPS) - (HF_NTAPS - 1) / 2.0
    fl, fh = lo / (SR / 2), hi / (SR / 2)
    h = (fh * np.sinc(fh * m) - fl * np.sinc(fl * m)) * np.kaiser(HF_NTAPS, HF_BETA)
    h /= float(np.sum(h * np.cos(np.pi * m * (fl + fh) / 2)))
    n = x.size + HF_NTAPS - 1
    nf = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nf) * np.fft.rfft(h, nf), nf)[:n][(HF_NTAPS - 1) // 2:(HF_NTAPS - 1) // 2 + x.size]
    return float(10 * np.log10(max(float((y ** 2).mean()), 1e-30)))


def openvoice(x: np.ndarray) -> dict | None:
    """20ms RMS dB: 바닥 = 전체 p10, 오프닝(첫 OPEN_S) p90 − 바닥 / 본편 p90 − 바닥 (볼케이노 A7)."""
    W = int(SR * WIN_S)
    n = x.size // W
    if n < 8:
        return None
    lv = 20 * np.log10(np.sqrt((x[:n * W].reshape(n, W) ** 2).mean(axis=1) + 1e-12))
    floor = float(np.percentile(lv, 10))
    no = int(OPEN_S / WIN_S)
    return {"floor_db": round(floor, 2), "open": round(float(np.percentile(lv[:no], 90)) - floor, 2),
            "body": round(float(np.percentile(lv[no:], 90)) - floor, 2) if n > no else None}


def measure_video(path: str, meta: dict) -> dict:
    if not meta.get("has_audio"):
        return {"has_audio": False}
    res = {"has_audio": True, **ebur128(path)}
    x = mono(path)
    if x is not None:
        res["hf_8k16k_dbfs"] = round(band_rms_db(x, HF_LO, HF_HI), 2)
        res["openvoice"] = openvoice(x)
    return res


def summarize(per_video: dict[str, dict], vids: list[str]) -> dict:
    """소리는 틀과 무관하다 — 받은 영상 전부로 잰다."""
    got = [(v, per_video[v]["audio"]) for v in vids if per_video[v].get("audio", {}).get("has_audio")]
    if not got:
        return {}

    def dist(key, k=1, unit="", method=""):
        a = [(v, x[key]) for v, x in got if x.get(key) is not None]
        vals = [b for _, b in a]
        return {"value": round(float(np.median(vals)), k), "stat": "median", "range": [round(min(vals), k), round(max(vals), k)],
                "n": len(vals), "unit": unit, "per_video": dict(a), "method": method}

    crit = {
        "A.lufs": dist("I", 1, "LUFS", "audio.ebur128"),
        "A.tp": dist("TP", 1, "dBTP", "audio.ebur128"),
        "A.lra": dist("LRA", 1, "LU", "audio.ebur128"),
        "A.s_spread": dist("S_spread", 1, "LU", "audio.ebur128"),
        "A.hf_8k16k": dist("hf_8k16k_dbfs", 2, "dBFS", "audio.band_rms_db"),
    }
    diffs = [(v, round(x["open3s_M"] - x["rest_M"], 1)) for v, x in got if x.get("open3s_M") is not None and x.get("rest_M") is not None]
    if diffs:
        d = [b for _, b in diffs]
        crit["A.open3s_M"] = {"value": round(float(np.median(d)), 1), "stat": "median (open3s M - rest M)", "range": [min(d), max(d)],
                              "quieter_open": sum(1 for x in d if x < 0), "n": len(d), "unit": "LU", "per_video": dict(diffs),
                              "method": "audio.ebur128"}
    ov = [(v, x["openvoice"]["open"]) for v, x in got if x.get("openvoice")]
    if ov:
        o = [b for _, b in ov]
        crit["A.openvoice"] = {"value": round(float(np.median(o)), 2), "stat": "median (open p90 - floor)", "range": [min(o), max(o)],
                               "n": len(o), "unit": "dB", "per_video": dict(ov), "method": "audio.openvoice"}
    return crit
