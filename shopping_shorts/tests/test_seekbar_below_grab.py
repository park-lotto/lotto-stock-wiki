# -*- coding: utf-8 -*-
"""재생바는 담기 버튼 바로 아래에 붙는다 (2026-09-02 사장님 "댓글을 못 써서 자리를 옮겨줘").

종전: `bottom:174px` 고정. 인스타는 화면 아래쪽에 **댓글 입력창**을 두므로 창 크기·기기에
따라 재생바가 그 위를 덮어 **댓글을 못 쓰는** 상태가 됐다.

담기 버튼도 bottom 고정이라 둘 사이 간격이 창마다 달라진다 — 두 자리를 따로 적어두면
언젠가 어긋난다(0순위-B). 그래서 담기 버튼의 **실제 화면 좌표를 읽어** 그 아래에 건다.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _place_fn():
    """파일에서 _placeSeekBar 함수만 떼어낸다(브라우저 없이 좌표 계산만 시험)."""
    src = JS.read_text(encoding="utf-8")
    m = re.search(r"function _placeSeekBar\(box\) \{.*?\n  \}", src, re.S)
    assert m, "_placeSeekBar를 못 찾았다 — 이름이 바뀌었으면 이 시험도 같이 고쳐라"
    return m.group(0)


def _run(body):
    code = _place_fn() + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, timeout=20)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    assert r.returncode == 0, out
    return out.strip()


_STUB = """
function mk(rect){
  const box={style:{}};
  global.window={innerWidth:1000};
  global.document={getElementById:(id)=> id==='ss-grab-btn'
     ? (rect? {getBoundingClientRect:()=>rect} : null) : null};
  return box;
}
"""


def test_담기_버튼_아래에_붙는다():
    """담기 버튼이 (right 982, bottom 700)이면 재생바는 그 10px 아래·오른쪽 정렬."""
    out = _run(_STUB + """
const box = mk({width:100,height:34,right:982,bottom:700});
_placeSeekBar(box);
console.log(JSON.stringify(box.style));
""")
    st = eval(out.replace("null", "None"))
    assert st["top"] == "710px", st          # 700 + 10
    assert st["right"] == "18px", st         # 1000 - 982
    assert st["bottom"] == "auto", st        # 옛 bottom 고정을 반드시 푼다


def test_담기_버튼이_없으면_건드리지_않는다():
    """아직 안 그려진 순간에 엉뚱한 자리로 튀면 안 된다 — 다음 주기에 붙는다."""
    out = _run(_STUB + """
const box = mk(null);
_placeSeekBar(box);
console.log(JSON.stringify(box.style));
""")
    assert out == "{}", out


def test_숨어있어_좌표가_0이면_그대로_둔다():
    """display:none 등으로 크기가 0이면 좌표를 믿을 수 없다."""
    out = _run(_STUB + """
const box = mk({width:0,height:0,right:0,bottom:0});
_placeSeekBar(box);
console.log(JSON.stringify(box.style));
""")
    assert out == "{}", out


def test_고정_bottom_174는_더이상_유일한_자리가_아니다():
    """자리 계산이 실제로 코드에 걸려 있어야 한다(주석만 남고 호출이 빠지는 걸 막는다)."""
    src = JS.read_text(encoding="utf-8")
    assert "_placeSeekBar(box);" in src, "syncSeekBar가 자리 함수를 안 부른다"
