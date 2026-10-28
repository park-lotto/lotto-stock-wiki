# -*- coding: utf-8 -*-
"""재수출 — 주인은 tools/calcopy/engine/gemini_server.py (2026-10-18 엔진으로 옮김, 0순위-B: 서버 제미나이 창구는 한 벌).
hybrid 안의 `from tools.calcopy.hybrid import gemini_server as G` 는 그대로 돈다.
스크립트로도 돈다: PYTHONUTF8=1 py tools/calcopy/hybrid/gemini_server.py asr … (10-18 손태영: sys.path 없이 import 해 ModuleNotFoundError: tools)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine.gemini_server import *  # noqa: E402,F401,F403
from tools.calcopy.engine.gemini_server import ASR_PROMPT, FALLBACK_MODELS, MODELS, MAX_INLINE, REQ_TIMEOUT_SEC, WORKERS, ask_files, ask_raw, asr, texts, main  # noqa: E402,F401

if __name__ == "__main__":
    main()
