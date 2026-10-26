"""E 관문·검사 칸 정리(사장님 10-26 "검수 관문은 뺄 수 있거나 너무 빡빡한 건 줄여라. 품질에 영향 없는 것").
기준: 벤치 원본을 같은 자로 재서 벤치 편이 못 넘는 문턱 = 너무 빡빡 → 벤치 편별 실측 범위로 넓힌다. 빠른 쪽(컷 더 빨리)은 넓히지 않는다(사장님 '휙휙 지나가 집중 안 됨').
주인: 재현일치도 = kal_analyze.match_table(_bench_span) · 판 리듬 합격 범위 = styles.rhythm_bounds(렌더 전 rhythm_gate·품질 관문 판 리듬 행이 같이 읽음).
옛 코드: 벤치 편을 우리로 놓으면 homedesignnote chunk.chars 0/6 · 두유노 벤치 가장 느린 편(1.8초)이 rhythm_gate 에 걸림 — 이 시험에서 실패한다.
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import kal_analyze as K  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import styles as STY  # noqa: E402


def _docs(ch):
    out = []
    for f in sorted(glob.glob(str(ROOT / f"channel/{ch}/줄판독/*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("lines") and d.get("dur"):
            out.append(d)
    return out


def _loo(ch, key):
    docs = _docs(ch)
    res = [r["judge"] for i, d in enumerate(docs) for r in K.match_table(docs[:i] + docs[i + 1:], d, None, None)["rows"] if r["key"] == key]
    return sum(j == "in" for j in res), len(res)


def test_bench_episode_passes_its_own_channel_ruler():
    """벤치 한 편을 우리로 놓고 나머지 벤치와 같은 자 — 옛 ±15% 는 homedesignnote 0/6(벤치가 자기 자를 못 넘음)."""
    ok, n = _loo("homedesignnote", "chunk.chars")
    assert n == 6 and ok >= 4
    ok, n = _loo("ititemlog", "sfx.rate")
    assert ok >= 4


def test_span_is_bench_range_and_fast_side_not_widened():
    B = [{"x": 1.0}, {"x": 1.5}, {"x": 2.0}]
    assert K._bench_span("x", B, {}) == (1.0, 2.0)
    assert K._bench_span("x", B[:2], {}) is None                      # 벤치 편이 적으면 안 넓힘
    # 컷 중앙: 벤치 편별 0.6·1.0·2.0 → 중앙 1.0. 1.9초(느림)는 벤치 범위라 같다 · 0.7초(빠름, −30%)는 그대로 미달
    t = K.match_table([{"lines": [], "dur": 10}] * 3, {"lines": [], "dur": 10}, {"cut_median": 1.9}, {"cut_median": [0.6, 1.0, 2.0]})
    assert next(r for r in t["rows"] if r["key"] == "cut.median")["judge"] == "in"
    t = K.match_table([{"lines": [], "dur": 10}] * 3, {"lines": [], "dur": 10}, {"cut_median": 0.7}, {"cut_median": [0.6, 1.0, 2.0]})
    assert next(r for r in t["rows"] if r["key"] == "cut.median")["judge"] == "out"


def test_rhythm_bounds_from_bench_range():
    k = STY.rhythm_bounds(STY.load("키치잇판"))
    assert k["cut_median"] == (0.805, 1.97) and k["hook_min"] == 1 and k["plain"] == (0.0, 0.5)
    assert not (k["cut_median"][0] <= 3.33 <= k["cut_median"][1])      # 박정수 컷 중앙 3.33(#105)은 그대로 걸린다
    d = STY.rhythm_bounds(STY.load("두유노판"))
    assert d["hook_min"] == 1 and d["cut_median"][1] == 1.8


def test_rhythm_gate_lets_slowest_bench_pace_through():
    """두유노 벤치 가장 느린 편 iiBU 1.8초 컷 중앙 — 옛 ×1.3(1.39) 이면 멈췄다. 3초면 그대로 멈춘다."""
    st = STY.load("두유노판")

    def T(step):
        cuts = [{"src": f"s{i}.mp4", "ss": 0.0, "t0": round(i * step, 3), "line": "L1"} for i in range(10)]
        return {"cuts": cuts, "end": round(10 * step, 3)}
    assert not [x for x in RB.rhythm_gate(T(1.8), st, None) if "컷 중앙" in x]
    assert [x for x in RB.rhythm_gate(T(3.0), st, None) if "컷 중앙" in x]


def test_transition_strength_row_is_reference():
    """전환 세기(zoomblur drop) = 참고 행 — 벤치 자기 경계 5개 중 ±30% 안 2개뿐(벤치가 못 넘는 자)."""
    src = (ROOT / "tools/calcopy/hybrid/quality_gate.py").read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if "전환 세기(zoomblur drop 중앙 ±30%" in l and "row(" in l)
    assert "ref=True" in line
    drops = [-0.192, 0.175, 0.136, 0.337, 0.24]
    import statistics
    m = statistics.median(drops)
    assert sum(abs(x - m) <= 0.3 * abs(m) for x in drops) == 2
