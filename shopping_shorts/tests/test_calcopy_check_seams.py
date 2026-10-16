# -*- coding: utf-8 -*-
"""이음매 검사(되감김) — 실제 완성본으로 잰다(관제 097, 2026-10-17 사장님 '17초 끊김 재발 없게').

벤치(사람 편집본)는 0, 아이템홈 1편 1판은 17.77초 되감김(0.37초), 2판은 0. 파일이 없는 PC에선 건너뛴다.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import check_seams  # noqa: E402

BASE = Path("C:/숏템_칼카피/itemhome")
BENCH = BASE / "원본/MfptnwqlGKs.mp4"
V1 = BASE / "1편_안유진로션/render/final.mp4"
V2 = BASE / "1편_안유진로션/render2/final.mp4"
WIN, MASK = check_seams.from_frame(str(ROOT / "channel/itemhome/frame_MfptnwqlGKs.json"))   # 창·자막 띠 = 틀


def _need(*ps):
    for p in ps:
        if not p.exists():
            pytest.skip(f"표본 없음: {p}")


def test_벤치_사람편집본은_되감김_없음():
    _need(BENCH)
    assert check_seams.check(str(BENCH), WIN, MASK)["되감김"] == []


def test_1판_17초_되감김을_잡는다():
    _need(V1)
    r = check_seams.check(str(V1), WIN, MASK)
    assert not r["ok"]
    hit = [x for x in r["되감김"] if 17.6 <= x["t"] <= 18.1]
    assert hit and all(0.3 <= x["되감김_초"] <= 0.45 for x in hit)


def test_2판은_되감김_없음():
    _need(V2)
    assert check_seams.check(str(V2), WIN, MASK)["ok"]


def test_틀에서_창과_자막띠를_읽는다():
    assert WIN == (0, 480, 1080, 1440)
    assert MASK[0] <= 1180 and MASK[1] >= 1300   # 자막 y1222·줄높이 86


def test_제목띠를_안_가리면_되감김을_놓친다_고정줄_자동가림():
    """전체 화면(창·띠 모름)으로 재도 고정 제목 줄은 자동으로 가려져 17초 되감김을 잡는다(10-17: 가림 전 0건)."""
    _need(V1)
    r = check_seams.check(str(V1), None, MASK)
    assert any(17.6 <= x["t"] <= 18.1 for x in r["되감김"])
