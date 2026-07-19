"""렌즈 CN 후보검색 클릭 상한 순수 헬퍼(2026-07-19) — node 슬라이스."""
import json, pathlib, shutil, subprocess, pytest

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")
_START = "function _lensCnCapReached("
_END = "// ── CN후보 끝 ──"


def _slice():
    src = INDEX_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_cn_click_cap():
    driver = _slice() + r"""
    console.log(JSON.stringify({
      under: _lensCnCapReached({cnClicks:5}),
      at:    _lensCnCapReached({cnClicks:6}),
      over:  _lensCnCapReached({cnClicks:7}),
      zero:  _lensCnCapReached({cnClicks:0}),
    }));
    """
    out = subprocess.run([NODE, "-e", driver], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r == {"under": False, "at": True, "over": True, "zero": False}
