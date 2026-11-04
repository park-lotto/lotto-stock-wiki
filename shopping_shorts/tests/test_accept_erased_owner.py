"""11-05 사장님 '두더지잡기 그만' — 지우기 결과를 받은 뒤 할 일(구간 더하기·호출 수·보낸 초·흐림 빼기)은 rules.accept_erased 한 곳.
11-04 #5864: 같은 순서가 네 곳(flow 둘·회원 PC 다시 만들기·점검 도구)에 따로 있어 다시 만들기 길만 흐림 빼기가 빠졌다."""
import re
from pathlib import Path

from tools.calcopy.hybrid import rules as RU

ROOT = Path(__file__).resolve().parents[2]


def test_blur_minus_only_inside_owner():
    hits = []
    for p in (ROOT / "tools" / "calcopy").rglob("*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"blur_minus_spans\(", line) and "def blur_minus_spans" not in line and "return blur_minus_spans(M, tf" not in line:
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    assert not hits, f"흐림 빼기를 주인(accept_erased) 밖에서 직접 부른다 — 길마다 따로 적으면 또 어긋난다: {hits}"


def test_take_paths_call_owner():
    src = {p: (ROOT / p).read_text(encoding="utf-8") for p in ("tools/calcopy/hybrid/flow.py", "tools/calcopy/hybrid/runner_ops.py", "tools/calcopy/hybrid/patch_render_check.py")}
    assert src["tools/calcopy/hybrid/flow.py"].count("RU.accept_erased(") >= 3
    assert "RU.accept_erased(M, None, tk)" in src["tools/calcopy/hybrid/runner_ops.py"]
    assert "RU.accept_erased(M, None, r)" in src["tools/calcopy/hybrid/patch_render_check.py"]


def test_owner_counts_calls_even_on_failure_and_removes_blur_on_success():
    M = {"blur": {"a.mp4": [[0, 1500, 1080, 200, 0.0, 10.0]]}}
    tf = {}
    assert RU.accept_erased(M, tf, {"calls": 2, "error": "x"}) == 0 and tf["calls"] == 2 and M["blur"]["a.mp4"] == [[0, 1500, 1080, 200, 0.0, 10.0]]
    n = RU.accept_erased(M, tf, {"calls": 1, "done": {"a.mp4": [[2.0, 6.0]]}, "sec": 4.0})
    assert n == 1 and tf["calls"] == 3 and tf["sec"] == 4.0 and tf["cleaned"] == ["a.mp4"]
    assert [(r[4], r[5]) for r in M["blur"]["a.mp4"]] == [(0.0, 2.0), (6.0, 10.0)]


def test_send_sec_preferred_over_sec():
    tf = {}
    RU.accept_erased({"blur": {}}, tf, {"done": {"a.mp4": [[0, 1]]}, "sec": 9.0, "send_sec": 1.5})
    assert tf["sec"] == 1.5
