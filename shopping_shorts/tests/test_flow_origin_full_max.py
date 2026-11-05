# -*- coding: utf-8 -*-
"""11-05 얜샷템 회원 편 0e227a6917c6: flow 의 통째 상한(1800)과 받는 쪽 yt_fetch.FULL_MAX_SEC(600, 사장님 11-02)이 따로 있어
21분 원본(PC 04편 원본 8Vhy53eDdS8)에 통째를 지시 → 거절 → 매칭 시각을 알고도 원본을 잃었다. 상한은 받는 쪽 한 곳, 넘으면 구간."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import yt_fetch as YF  # noqa: E402
from tools.calcopy.hybrid import flow as F  # noqa: E402


def _pick(dur):
    st = {"scored": [{"id": "8Vhy53eDdS8", "dur": dur, "matched": [{"origin_t": 378.4}]}], "log": []}
    rp = {"origin_pick": {"origin_id": "8Vhy53eDdS8", "self_spoken": True, "matched": [{"bench": "x", "origin_t": 365.4}, {"bench": "y", "origin_t": 387.2}]}}
    return st, F.ph_pick_got(st, {}, rp, None)["do"][0]


def test_one_owner():
    assert F.full_max() == YF.FULL_MAX_SEC


def test_long_origin_gets_sections_around_match():
    st, d = _pick(1260)                                   # 21분
    assert d["full"] is False and d["a"] <= 365.4 and d["b"] >= 387.2 and d["b"] - d["a"] < 400
    assert st["origin"]["window"] == [d["a"], d["b"]]


def test_short_origin_still_whole():
    _, d = _pick(300)
    assert d["full"] is True


def test_sb_pick_long_origin_is_sections():
    st = {"sb": {"L": 1}, "src_mixed": [{"id": "L", "dur": 1260}], "log": []}
    d = F.ph_sb_pick(st, {}, {"origin_sb": {"origin_id": "L", "origin_t": [400.0], "why": "w"}}, None)["do"][0]
    assert d["full"] is False and d["a"] <= 400 <= d["b"] and d["ts"] == [400.0]
