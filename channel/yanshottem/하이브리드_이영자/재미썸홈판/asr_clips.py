# -*- coding: utf-8 -*-
"""원음·완성본 구간 단독 받아쓰기(무료 제미나이 gemini_free.ask) — 클립마다 따로 한 요청에, 모델 2개로 2회.
    PYTHONUTF8=1 py asr_clips.py <wav|mp4> a-b [a-b ...]
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine.gemini_free import ask  # noqa: E402

MODELS = [("gemini-3-flash-preview",), ("gemini-flash-latest", "gemini-flash-lite-latest")]
import os
if os.environ.get("ASR_MODELS"):   # 무료 한도(quota) 걸린 날: ASR_MODELS=gemini-2.5-pro,gemini-2.5-pro 처럼 바꿔 부른다
    MODELS = [(m,) for m in os.environ["ASR_MODELS"].split(",")]


def main():
    src, spans = sys.argv[1], [tuple(map(float, s.split("-"))) for s in sys.argv[2:]]
    parts = []
    with tempfile.TemporaryDirectory() as td:
        for k, (a, b) in enumerate(spans):
            mp3 = Path(td) / f"c{k}.mp3"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                            "-b:a", "64k", str(mp3)], check=True)
            parts += [f"클립 {k}:", (mp3.read_bytes(), "audio/mp3")]
        prompt = ('위 클립마다 한국어 말소리를 들리는 그대로 받아써라(배경음악·효과음 빼고, 고치거나 보태지 마라). 말하는 사람 수도 세라.\n'
                  'JSON만: {"clips":[{"i":0,"text":"","speakers":1}]}')
        out = []
        for m in MODELS:
            d, why = ask(parts, prompt, tag="yj_asr", models=m)
            out.append({"model": (d or {}).get("_model"), "why": why, "clips": (d or {}).get("clips")})
    print(json.dumps({"spans": spans, "runs": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
