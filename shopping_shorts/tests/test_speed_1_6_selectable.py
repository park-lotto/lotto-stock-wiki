# -*- coding: utf-8 -*-
"""화면 속도 선택지에 1.6이 있어야 한다 (2026-08-22 사장님 확정).

★왜: 기본 보이스(_DEFAULT_VOICE)가 speed 1.6인데 화면 상한이 1.5였다.
  즉 **실제로 쓰이는 값을 화면에서 고를 수 없었다** — 사용자가 속도 버튼을 한 번
  누르는 순간 1.5로 내려가고, 되돌릴 방법이 없다(조용한 하향).
  무음컷은 목소리와 무관하게 적용되지만(audio_post 후처리 층), 배속은 목소리마다
  고르는 값이라 화면 선택지가 실제 범위를 덮어야 한다.
"""
import re
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _speeds():
    m = re.search(r"const SPEEDS=\[([^\]]+)\]", HTML.read_text(encoding="utf-8"))
    assert m, "SPEEDS 배열을 못 찾았다"
    return [float(x) for x in m.group(1).split(",")]


def test_default_voice_speed_is_selectable():
    """기본 보이스 배속이 화면 선택지 안에 있다 — 없으면 조용히 내려간다."""
    from shopping_shorts import mix_pipeline
    assert mix_pipeline._DEFAULT_VOICE["speed"] in _speeds(), \
        "기본 배속 %s가 화면 선택지에 없다" % mix_pipeline._DEFAULT_VOICE["speed"]


def test_speeds_sorted_and_unique():
    """오름차순·중복 없음 — 버튼 순서가 흐트러지면 누르기 어렵다(주 사용자 60대)."""
    v = _speeds()
    assert v == sorted(v) and len(v) == len(set(v)), "SPEEDS가 정렬 안 됐거나 중복이다: %s" % v
