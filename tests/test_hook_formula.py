"""두유노홈디노 첫 문장 공식(channel/homedesignnote/대본설명서/hook_formula.json) — 초안 5편은 통과, 공식 아닌 문장은 반려."""
import json
from pathlib import Path

from tools.calcopy.engine import script_frame as SF

ROOT = Path(__file__).resolve().parents[1]
FRAME = ROOT / "channel" / "homedesignnote" / "대본설명서" / "script_frame.json"


def test_examples_pass():
    hf = SF.load_hook_formula(FRAME)
    assert hf and all(SF.hook_formula_check(e, hf)["ok"] for e in hf["examples"])


def test_non_formula_rejected():
    hf = SF.load_hook_formula(FRAME)
    for s in ["저희 와이프가 벽 코너에 이런걸 해놨는데 보는 사람마다 깜짝 놀라더라구요.",
              "이 식기세척기는 싱크대 안에 들어가요.",
              "중국 회사가 싱크대 안에 식기세척기를 숨겨버렸대요.",
              "빡친 엄마가 열받아서 빡쳐서 만들어버렸대요."]:
        assert not SF.hook_formula_check(s, hf)["ok"], s


def test_no_formula_none():
    assert SF.hook_formula_check("아무 문장", None) is None
