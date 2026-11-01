# -*- coding: utf-8 -*-
"""뜯기 재현성 점검 — 같은 영상의 받아쓰기·소리 구성을 두 번 돌려 같은지 본다(실제 무료 제미나이 호출, pytest 아님).

    PYTHONUTF8=1 py tools/calcopy/engine/check_repeat.py <mp4> [<mp4> …]

비교: 답한 모델 · 소리 구성 사전 값 · 나레 종류 · 구절별 (언어, 종류, 화자). 하나라도 다르면 '다름' + 종료코드 1.
2026-10-16 1판: 503 때 lite·별칭으로 넘어가 같은 영상이 'en source/human' ↔ 'es dialog/tts'로 흔들렸다 → 모델 고정 뒤 이걸로 확인.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.channelkit.bench import probe  # noqa: E402
from tools.calcopy.engine import analyze, gemini_free  # noqa: E402


def sig(path: str) -> tuple:
    a, _ = analyze.audio_and_tone(path, probe.info(path), gemini_free.ask, {})
    tr, c = a.get("transcript") or {}, a.get("composition") or {}
    return (tr.get("model"), c.get("kind"), c.get("narration"),
            tuple((s["lang"], s["kind"], s["speaker"]) for s in tr.get("segments", [])))


def main() -> int:
    bad = 0
    for p in sys.argv[1:]:
        a, b = sig(p), sig(p)
        same = a == b
        bad += not same
        print(Path(p).stem, "같음" if same else "다름", a if same else (a, b))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
