"""대본 질문지 = 검사기 기준(10-27 실사고): 두유노판 script_audit engine 이 줄의 point·answer_at·facts 칸을 보는데
flow._script_ask 의 '대본 꼴'에 그 칸이 한 번도 없어 Claude 가 7번 써서 7번 반려(통과 불가능). 검사하는 판마다 질문지에 그 기준이 실려야 한다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402
from tools.calcopy.hybrid import styles as STY  # noqa: E402


def _engine_versions():
    out = []
    for v in STY.names():
        if v.startswith("_"):
            continue
        try:
            if any(r.get("kind") == "engine" for r in (STY.load(v).get("script") or {}).get("audit") or []):
                out.append(v)
        except Exception:  # noqa: BLE001
            pass
    return out


def test_engine_versions_exist():
    assert _engine_versions(), "engine 검사를 쓰는 판이 없다 — 시험이 뜻이 없다"


def test_script_ask_carries_point_fields_for_engine_versions():
    for v in _engine_versions():
        st = {"version": v, "fmt": "쇼핑형", "research_md": "", "log": []}
        ask = F._script_ask(st)["ask"]
        rule = SA.points_rule_for(v)
        assert rule, v
        assert rule in ask, f"{v}: 검사 기준(points_rule)이 대본 질문지에 없다"
        for field in ("answer_at", "facts"):
            assert field in ask, f"{v}: 질문지에 '{field}' 칸 안내가 없다"
