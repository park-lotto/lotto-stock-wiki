# -*- coding: utf-8 -*-
"""채널 효과음 팩 — 원본에서 **잡음(목소리·배경음악)이 안 섞인 효과음만** 잘라 채널별 독립 팩으로 모은다.
(사장님 2026-10-15: "내부 효과음에 합치지 말고 잡음 안 섞인 것만 따로 모아 팩")

    PYTHONUTF8=1 py tools/calcopy/sfx_pack.py C:/숏템_칼카피/sseolpulda

후보 = judge/<id>.json 의 sfx(시각·설명) — 제미니가 들은 자리. 판정은 숫자로 다시 한다:
  ① 말 겹침 0: asr/<id>.json 단어 구간이 [t-0.15, t+LEN] 와 겹치면 버림
  ② 솟음: 후보 창 안 최고 RMS - 직전 0.4초 바닥 RMS ≥ MIN_RISE_DB (배경음악에 묻힌 건 버림)
  ③ 바닥 조용: 직전 바닥 ≤ MAX_FLOOR_DBFS (배경음악이 크게 깔린 자리는 섞여 나온다)
남은 것만 sfx_pack/<번호>_<설명>.wav + index.json(출처 id·시각·수치). 판정 수치는 index 에 남겨 다시 잴 수 있게.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
PRE = 0.15          # 효과음 시작이 판독 시각보다 이를 수 있다
LEN = 1.2           # 자르는 길이(초)
FLOOR_WIN = 0.4
MIN_RISE_DB = 15.0
MAX_FLOOR_DBFS = -38.0


def _pcm(mp4: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def _db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)) if len(x) else -120.0


def _peak_rms_db(x: np.ndarray, win: int = 1024) -> float:
    if len(x) < win:
        return _db(x)
    frames = x[: len(x) // win * win].reshape(-1, win)
    return float(20 * np.log10(np.sqrt((frames ** 2).mean(1)).max() + 1e-9))


def _words(asr: Path) -> list[tuple[float, float]]:
    if not asr.exists():
        return []
    r = json.loads(asr.read_text(encoding="utf-8"))
    return [(w["start_time"], w["end_time"]) for w in r.get("results", []) if w.get("type") == "word"]


def build(base: Path) -> dict:
    out = base / "sfx_pack"
    out.mkdir(exist_ok=True)
    kept, dropped, n = [], {"no_asr": 0, "voice": 0, "buried": 0, "loud_floor": 0}, 0
    for j in sorted((base / "judge").glob("*.json")):
        vid = j.stem
        sfx = json.loads(j.read_text(encoding="utf-8")).get("sfx") or []
        if not sfx:
            continue
        asr = base / "asr" / f"{vid}.json"
        if not asr.exists():
            dropped["no_asr"] += len(sfx)
            continue
        words = _words(asr)
        x = _pcm(base / "mp4" / f"{vid}.mp4")
        for s in sfx:
            t = float(s.get("t") or 0)
            a, b = max(0.0, t - PRE), t + LEN
            if any(ws < b and we > a for ws, we in words):
                dropped["voice"] += 1
                continue
            seg = x[int(a * SR): int(b * SR)]
            floor = _db(x[int(max(0, a - FLOOR_WIN) * SR): int(a * SR)])
            rise = _peak_rms_db(seg) - floor
            if floor > MAX_FLOOR_DBFS:
                dropped["loud_floor"] += 1
                continue
            if rise < MIN_RISE_DB:
                dropped["buried"] += 1
                continue
            n += 1
            name = re.sub(r"[^\w가-힣]+", "_", str(s.get("desc") or "sfx"))[:24].strip("_")
            wav = out / f"{n:03d}_{name}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{LEN + PRE:.3f}",
                            "-i", str(base / "mp4" / f"{vid}.mp4"), "-vn", "-ac", "1", "-ar", str(SR),
                            "-af", "afade=t=out:st=1.2:d=0.15", str(wav)], check=True)
            kept.append({"file": wav.name, "src": vid, "t": t, "desc": s.get("desc"),
                         "floor_dbfs": round(floor, 1), "rise_db": round(rise, 1)})
    idx = {"rule": {"MIN_RISE_DB": MIN_RISE_DB, "MAX_FLOOR_DBFS": MAX_FLOOR_DBFS, "LEN": LEN, "PRE": PRE},
           "kept": kept, "dropped": dropped}
    (out / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"남김 {len(kept)} · 버림 {dropped}")
    return idx


if __name__ == "__main__":
    build(Path(sys.argv[1]))
