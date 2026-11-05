# -*- coding: utf-8 -*-
"""구간마다 따로 한 요청 받아쓰기(무료 제미나이) — asr_clips.py 의 여러 클립 한 요청이 2.5-pro 에서 빈 답일 때 씀(10-17 무료 한도 날).
    ASR_MODEL=gemini-2.5-pro PYTHONUTF8=1 py asr_one.py <wav|mp4> a-b [a-b ...]
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine.gemini_free import ask  # noqa: E402

M = os.environ.get("ASR_MODEL", "gemini-2.5-pro")
src = sys.argv[1]
for s in sys.argv[2:]:
    a, b = map(float, s.split("-"))
    with tempfile.TemporaryDirectory() as td:
        mp3 = Path(td) / "c.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(mp3)], check=True)
        d, why = ask(["클립:", (mp3.read_bytes(), "audio/mp3")],
                     '한국어 말소리를 들리는 그대로 받아써라(배경음악·효과음 빼고, 고치거나 보태지 마라). 말하는 사람 수도 세라. JSON만: {"text":"","speakers":1}',
                     tag="cegname_one", models=(M,))
    print(f"{s}\t{why}\t{(d or {}).get('speakers')}\t{(d or {}).get('text')}")
