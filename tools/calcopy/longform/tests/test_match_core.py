# match_core.judge_cell / match 시험 — kind 마다 안(in)·밖(out)·못 잼(failed). 쇼츠 kal_analyze.match_table 의 뜻과 같아야 한다.
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
import pytest
from tools.calcopy.engine.match_core import judge_cell, match


@pytest.mark.parametrize("kind,tol,b,o,span,want", [
    ("rel", 15, 100, 110, None, "in"), ("rel", 15, 100, 120, None, "out"), ("rel", 15, 100, 120, (90, 125), "in"),
    ("rel", 15, None, 100, None, "failed"), ("rel", 15, 100, None, None, "failed"), ("rel", 15, 100, "미측정", None, "failed"),
    ("rel0", 30, 0, 0, None, "in"), ("rel0", 30, 0, 1, None, "out"), ("rel0", 30, 10, 12, None, "in"), ("rel0", 30, 10, 14, None, "out"),
    ("rel_slow", 30, 2.0, 2.5, None, "in"), ("rel_slow", 30, 2.0, 1.6, None, "out"), ("rel_slow", 30, 2.0, 1.8, None, "in"),
    ("rel_slow", 30, 2.0, 2.8, (1.5, 3.0), "in"), ("rel_slow", 30, 2.0, 2.8, None, "out"),
    ("db", 1, -14.0, -14.8, None, "in"), ("db", 1, -14.0, -15.5, None, "out"),
    ("pctp", 10, 0.30, 0.38, None, "in"), ("pctp", 10, 0.30, 0.45, None, "out"),
    ("pctp", 10, {"실사": 0.5, "그림": 0.5}, {"실사": 0.45, "그림": 0.55}, None, "in"),
    ("pctp", 10, {"실사": 0.5, "그림": 0.5}, {"실사": 0.2, "그림": 0.8}, None, "out"),
    ("pctp", 10, {"실사": 0.9}, {"실사": 0.85, "지도": 0.15}, None, "out"),      # 한쪽에만 있는 칸은 0 으로
    ("eq", 0, "있음", "있음", None, "in"), ("eq", 0, "있음", "없음", None, "out"),
    ("range", 0, 10, 12, (9, 13), "in"), ("range", 0, 10, 14, (9, 13), "out"), ("range", 0, 10, 12, None, "out"),
])
def test_judge_cell(kind, tol, b, o, span, want):
    assert judge_cell(kind, tol, b, o, span)[0] == want


def test_unknown_kind_raises():
    with pytest.raises(ValueError):
        judge_cell("nope", 1, 1, 1)


def test_match_core_fail_and_failed_not_pass():
    rules = [("len.duration", "rel", 15, True, "길이"), ("cut.median", "rel_slow", 30, True, "컷"),
             ("mix.lufs", "db", 1, False, "참고"), ("caption", "eq", 0, True, "자막")]
    bench = [{"len.duration": 1500, "cut.median": 2.0, "mix.lufs": -14, "caption": "있음"},
             {"len.duration": 1600, "cut.median": 2.2, "mix.lufs": -15, "caption": "있음"}]
    T = match(rules, bench, {"len.duration": 1550, "cut.median": 2.1, "mix.lufs": -20, "caption": "있음"})
    assert T["pass"] is True                       # 참고 칸(mix.lufs) 밖은 통과를 막지 않는다
    T = match(rules, bench, {"len.duration": 1550, "cut.median": None, "mix.lufs": -14.5, "caption": "있음"})
    assert T["pass"] is False and T["core_fail"] == ["cut.median"]   # 못 잰 기준 칸 = 통과 아님
    r = {x["key"]: x for x in T["rows"]}
    assert r["cut.median"]["judge"] == "failed" and r["len.duration"]["bench"] == 1550


def test_match_len_uses_bench_range():
    rules = [("len.duration", "rel", 15, True, "길이")]
    bench = [{"len.duration": 1000}, {"len.duration": 2000}]
    assert match(rules, bench, {"len.duration": 1900})["pass"] is True     # 중앙 1500 ±15% 밖이지만 벤치 범위 안


def test_rel0_count_rule():
    # 원본 n_ok: 벤치 0.051/초 × 28.5초 = 1.45발 → 우리 1발(0.035)은 ±30% 밖이지만 가장 가까운 정수 발 수라 in
    assert judge_cell("rel0", 30, 0.051, 1 / 28.5)[0] == "out"
    assert judge_cell("rel0", 30, 0.051, 1 / 28.5, count_dur=28.5)[0] == "in"
    T = match([("sfx.rate", "rel0", 30, True, "효과음")], [{"sfx.rate": 0.051}], {"sfx.rate": 1 / 28.5, "len.duration": 28.5})
    assert T["pass"] is True


def test_rel_slow_zero_bench_failed():
    assert judge_cell("rel_slow", 30, 0, 1.0)[0] == "failed"


def test_span_pad_range():
    R = [("len.duration", "range", 0, True, "길이", {"span_pad": 0.05})]
    B = [{"len.duration": 1400}, {"len.duration": 2000}]
    assert match(R, B, {"len.duration": 2090})["pass"] is True      # 2000×1.05=2100 안
    assert match(R, B, {"len.duration": 2110})["pass"] is False
    assert match(R, B, {"len.duration": 1335})["pass"] is True      # 1400×0.95=1330 안


def test_same_look_bench():
    R = [("shot_mix", "pctp", 10, True, "샷", {"same_look": True})]
    B = [{"src": "x/A.mp4", "shot_mix": {"글자": 0.5, "사진": 0.5}}, {"src": "x/B.mp4", "shot_mix": {"글자": 0.2, "사진": 0.8}}]
    o = {"shot_mix": {"글자": 0.45, "사진": 0.55}}
    T = match(R, B, o, same_look_bench="A")
    assert T["pass"] is True and [r["key"] for r in T["rows"]] == ["shot_mix", "shot_mix(다른 틀)"]
    assert T["rows"][1]["core"] is False and T["rows"][1]["judge"] == "out"
    assert match(R, B, o, same_look_bench="B")["pass"] is False
    assert match(R, B, o)["rows"][0]["judge"] == "failed"            # 같은 틀 미지정 = 통과 아님
