"""버튼 자리(영상 칸 옆) 계산을 node로 실제 실행해 확인한다(2026-09-01 사장님 요청).

문법검사로는 못 잡는 층: 좁은 창에서 종전 자리로 되돌아가는지, 영상이 없으면
손대지 않는지. 자리 판단은 grab_logic.js `_dockAnchorRight`/`_dockBtns` 한 곳뿐.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

LOGIC = pathlib.Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"


def _dock_src():
    src = LOGIC.read_text(encoding="utf-8")
    i = src.index("var DOCK_IDS")
    j = src.index("function tick()", i)
    return src[i:j]


def _run(inner_width, video_rect, btn_width=150):
    if not shutil.which("node"):
        pytest.skip("node 없음")
    rect = json.dumps(video_rect)
    script = f"""
var window = {{ innerWidth: {inner_width} }};
var vid = {{
  getBoundingClientRect: function () {{ return {rect}; }},
  closest: function () {{ return null; }}
}};
var els = {{}};
["ss-grab-btn","ss-chadd-btn","ss-lens-btn","ss-adopt-btn"].forEach(function (id) {{
  els[id] = {{ offsetWidth: {btn_width}, style: {{ left: "", right: "18px" }} }};
}});
var document = {{
  querySelectorAll: function () {{ return {'[vid]' if video_rect else '[]'}; }},
  getElementById: function (id) {{ return els[id] || null; }}
}};
{_dock_src()}
_dockBtns();
console.log(JSON.stringify(els["ss-grab-btn"].style));
"""
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_넓은_화면이면_영상_오른쪽에_붙는다():
    st = _run(1229, {"width": 500, "height": 880, "right": 520})
    assert st["left"] == "536px"          # 영상 오른쪽 끝 + 16
    assert st["right"] == "auto"


def test_좁은_창이면_종전_오른쪽_끝_자리로_되돌린다():
    st = _run(700, {"width": 500, "height": 880, "right": 620})
    assert st["right"] == "18px" and st["left"] == ""


def test_영상이_없으면_손대지_않는다():
    st = _run(1229, None)
    assert st["right"] == "18px" and st["left"] == ""
