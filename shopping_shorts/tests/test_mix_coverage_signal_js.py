"""produce.html 완성도 신호등 renderCoverageSignal — node 슬라이스 그라운딩.

편집안 맨 위 한 줄이 비트를 fit로 🟢(fit>=4/없음)·🟡(fit==3)·🔴(fit<=2)로 집계하고,
빨강이 있으면 '빨간 N칸' 안내, 없으면 '다 좋아요'를 낸다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "// ── 완성도 신호등(2026-07-19) ─── SIGNAL-START"
_END = "// ─── SIGNAL-END"


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER = r"""
(function(){
  global.window = global;
  // fit: 5,4,null → 🟢(3) / 3 → 🟡(1) / 2 → 🔴(1)
  const mixed = [{fit:5},{fit:4},{fit:null},{fit:3},{fit:2}];
  const allGreen = [{fit:5},{fit:4},{fit:null}];
  console.log(JSON.stringify({
    mixed: renderCoverageSignal(mixed),
    allGreen: renderCoverageSignal(allGreen),
    empty: renderCoverageSignal([]),
  }));
})();
"""


def _run(tmp_path):
    js = tmp_path / "t.js"
    js.write_text(_slice() + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_coverage_signal(tmp_path):
    r = _run(tmp_path)
    # 혼합: 🟢3 🟡1 🔴1 + '빨간 1칸' 안내(fire색)
    assert "🟢 3 · 🟡 1 · 🔴 1" in r["mixed"]
    assert "빨간 1칸" in r["mixed"]
    assert "var(--fire)" in r["mixed"]
    # 전부 초록: 🔴0 + '다 좋아요', fire색 없음
    assert "🟢 3 · 🟡 0 · 🔴 0" in r["allGreen"]
    assert "다 좋아요" in r["allGreen"]
    assert "var(--fire)" not in r["allGreen"]
    # 비트 없음: 빈 문자열
    assert r["empty"] == ""
