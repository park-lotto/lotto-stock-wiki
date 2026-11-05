# -*- coding: utf-8 -*-
"""#1567 김미향 — 재료에 사진 컷(prod_*.jpg)을 max 와 함께 적으면 계획 넘침 셈(measure_over)이 c['ss'] 를 읽다 KeyError 'ss'.
주인 render_bench.still_cut — 사진에는 원본 초·샷 길이가 없으니 시간표 입구에서 ss·max 칸을 버린다(뒤 함수는 'ss 없음 = 사진')."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402


def _S():
    return {"voice": {"voice_id": "tc_x"}, "cps_target": 8.6,
            "lines": [{"id": "N1", "kind": "tts", "tts": "가나다라마바사아자차카타파하.", "caps": [{"text": "가나다"}]}]}


def test_photo_cut_with_max_plans():
    M = {"cuts": {"N1": [{"src": "prod_1.jpg", "at": 0.0, "max": 2.0, "ss": 0.0, "crop": "face"}]}}
    T = RB.timeline(_S(), M, ST.load("잇템로그판"), None, None)
    c = T["cuts"][0]
    assert c["src"] == "prod_1.jpg" and "ss" not in c and c["over"] == 0.0


def test_still_cut_keeps_video_cut():
    v = {"src": "a.mp4", "ss": 1.5, "max": 2.0}
    assert RB.still_cut(v) is v
    assert RB.still_cut({"src": "p.PNG", "ss": 0, "max": 1, "crop": "face", "at": 0.2}) == {"src": "p.PNG", "crop": "face", "at": 0.2}
