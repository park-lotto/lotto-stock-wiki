"""담긴 대본 전체선택/해제/선택삭제(2026-07-18)."""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_START = "function picksSelectAll("
_END = "// ── 담긴대본 관리 끝 ──"


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_HARNESS = r"""
'use strict';
// 체크박스 2개(tmp1=임시, wiki1=S급) 모킹
const _boxes = [
  {value:'tmp1', checked:true},
  {value:'wiki1', checked:true},
];
global.document = {
  querySelectorAll(sel){ return _boxes; },
};
global.HANDOFF = [
  {shortcode:'tmp1', pickScript:true, script:'임시', useFootage:true},
];
let _toggled = [];
global.fetch = async (url, opts) => {
  _toggled.push(JSON.parse(opts.body).shortcode);
  return { json: async () => ({ok:true}) };
};
global.__toggled = _toggled;
global.loadWikiForMix = async () => {};   // 재렌더 스텁
"""

_DRIVER = r"""
(async () => {
  await picksDeleteSel();
  console.log(JSON.stringify({
    tmpPick: (HANDOFF.find(h=>h.shortcode==='tmp1')||{}).pickScript,
    tmpFoot: (HANDOFF.find(h=>h.shortcode==='tmp1')||{}).useFootage,
    serverToggled: global.__toggled,
  }));
})();
"""


def _run(tmp_path):
    js = tmp_path / "t.js"
    js.write_text(_HARNESS + _slice() + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_delete_removes_temp_script_keeps_footage(tmp_path):
    got = _run(tmp_path)
    assert got["tmpPick"] is False      # 임시 대본은 담긴대본에서 빠진다
    assert got["tmpFoot"] is True       # 영상풀(useFootage)은 남는다


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_delete_toggles_server_pick(tmp_path):
    got = _run(tmp_path)
    assert "wiki1" in got["serverToggled"]   # S급은 서버 picks/toggle로 뺀다
    assert "tmp1" not in got["serverToggled"] # 임시는 서버 안 부른다(HANDOFF만)
