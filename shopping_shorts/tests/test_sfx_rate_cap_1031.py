"""배치가 넣은 효과음을 B14 가 떨어뜨리지 않는다 — 실제 해외신기템 벤치 줄판독·길이(10-31 라이브 2시간 되풀이)."""
import json
from pathlib import Path

from tools.calcopy.hybrid.placement import ROOT, _sfx_rate_n
from tools.calcopy.hybrid.quality_gate import sfx_excess

STYLE = json.loads((ROOT / "tools/calcopy/hybrid/styles/숏템리폿판.json").read_text(encoding="utf-8"))
DOCS = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / STYLE["bench"]["line_reads"]).glob("*.json"))]


def test_라이브에서_걸린_길이마다_배치가_검사를_통과한다():
    for dur, want in ((25.7, 1), (33.47, 1), (34.2, 2)):
        n = _sfx_rate_n([{"t1": dur}], STYLE, 2, [])
        assert n == want, dur
        assert sfx_excess(n, dur, DOCS)[0] is True


def test_고치기_전_2발은_검사에_걸린다():
    assert sfx_excess(2, 33.5, DOCS)[0] is False


def test_상한_안이면_줄이지_않는다():
    assert _sfx_rate_n([{"t1": 60.0}], STYLE, 2, []) == 2


def test_벤치_줄판독이_없으면_그대로다():
    assert _sfx_rate_n([{"t1": 20.0}], {"bench": {}}, 2, []) == 2
