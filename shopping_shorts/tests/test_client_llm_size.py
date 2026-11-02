# -*- coding: utf-8 -*-
"""회원 PC AI 질문 길이 한도(client_llm.PROMPT_MAX) — 넘으면 기다리지 않고 바로 이유를 돌려준다(10-21 원본 후보 제목 4.2만 자로 40분 멈춤)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_too_long_prompt_fails_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(tmp_path))
    from tools.calcopy.engine import client_llm
    t0 = time.time()
    r, why = client_llm.ask([], "가" * (client_llm.PROMPT_MAX + 1), "origin_titles")
    assert r is None and why.startswith("prompt_too_long") and time.time() - t0 < 5
    assert not list(tmp_path.glob("*/request.json"))      # 회원 Claude 에게 넘기지 않는다
