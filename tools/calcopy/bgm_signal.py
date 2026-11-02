# -*- coding: utf-8 -*-
"""벤치 원본의 배경음악 유무를 소리 신호로 재서 줄판독 sound.bgm 에 적는다(preset_card 의 bgm 칸 근거, 관제 샤크탱크 프리셋 11-02).

판정: 20ms 창 RMS 의 바닥(p10)이 무음 기준(-40dB)보다 높고, 전체 시간의 95% 이상 소리가 이어지면 '깔림'.
말 사이 쉼까지 소리가 안 꺼지는지를 보는 것이라 곡 이름은 모른다(confidence=신호).

    PYTHONUTF8=1 py tools/calcopy/bgm_signal.py <채널 slug> <원본 mp4 폴더> [--write]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SILENCE_DB = -40.0
WIN_SEC = 0.02
SR = 16000


def measure(mp4: Path) -> dict:
    """mp4 하나의 바닥·중앙 dB 와 깔림 판정."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                       capture_output=True, stdin=subprocess.DEVNULL, check=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float64) / 32768.0
    n = int(SR * WIN_SEC)
    m = len(x) // n
    if m == 0:
        raise ValueError(f"소리가 없다: {mp4}")
    rms = np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-7))
    floor = float(np.percentile(db, 10))
    on_rate = float((db >= SILENCE_DB).mean())
    return {"present": bool(floor > SILENCE_DB and on_rate >= 0.95), "on_rate": round(on_rate, 3),
            "floor_db": round(floor, 1), "med_db": round(float(np.percentile(db, 50)), 1), "confidence": "신호",
            "how": f"원본 mp4 20ms 창 RMS — 바닥 p10 > {SILENCE_DB}dB 이고 소리 이어짐 95% 이상(tools/calcopy/bgm_signal.py)"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("src")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    bad = 0
    for f in sorted((ROOT / "channel" / a.slug / "줄판독").glob("*.json")):
        mp4 = Path(a.src) / f"{f.stem}.mp4"
        if not mp4.is_file():
            print("원본 없음", f.stem)
            bad += 1
            continue
        res = measure(mp4)
        print(f.stem, res["present"], res["floor_db"], res["med_db"], res["on_rate"])
        if a.write:
            d = json.loads(f.read_text(encoding="utf-8"))
            d.setdefault("sound", {})["bgm"] = res
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
