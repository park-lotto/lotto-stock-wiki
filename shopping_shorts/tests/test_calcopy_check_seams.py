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


def test_2판은_되감김_없지만_점프줌_11곳():
    """2판: 되감김 0, 그러나 같은 장면 확대만 바꾼 컷 11곳(1.67↔2.0배) — 사장님 '19초부터 끊긴다'(19.37·20.13·22.90 포함)."""
    _need(V2)
    r = check_seams.check(str(V2), WIN, MASK)
    assert r["되감김"] == [] and not r["ok"] and r["점프줌_판정"]
    ts = [x["t"] for x in r["점프줌"]]
    assert len(ts) >= 8 and any(19.2 <= t <= 19.5 for t in ts)


MANTEM = sorted(Path("C:/숏템_칼카피/mantem/원본").glob("*.mp4"))


@pytest.mark.parametrize("mp4", MANTEM or [Path("없음.mp4")], ids=lambda p: p.stem)
def test_사람편집_만템은_통과(mp4):
    """만템(사람 편집본)은 멀티캠 각도 전환·가끔 줌을 쓴다 — 이걸 걸면 안 된다(10-17 1차 문턱이 6/8편을 오탐)."""
    _need(mp4)
    w, m = check_seams.from_frame(str(ROOT / "channel/mantem/frame_얜샷템.json"))
    r = check_seams.check(str(mp4), w, m)
    assert r["ok"], (r["되감김"], r["점프줌_판정"])


def test_3판은_통과():
    v3 = BASE / "1편_안유진로션/render3/final.mp4"
    _need(v3)
    assert check_seams.check(str(v3), WIN, MASK)["ok"]


def test_벤치는_점프줌_없음():
    _need(BENCH)
    assert check_seams.check(str(BENCH), WIN, MASK)["점프줌"] == []


def test_틀에서_창과_자막띠를_읽는다():
    assert WIN == (0, 480, 1080, 1440)
    assert MASK[0] <= 1180 and MASK[1] >= 1300   # 자막 y1222·줄높이 86


def test_제목띠를_안_가리면_되감김을_놓친다_고정줄_자동가림():
    """전체 화면(창·띠 모름)으로 재도 고정 제목 줄은 자동으로 가려져 17초 되감김을 잡는다(10-17: 가림 전 0건)."""
    _need(V1)
    r = check_seams.check(str(V1), None, MASK)
    assert any(17.6 <= x["t"] <= 18.1 for x in r["되감김"])
