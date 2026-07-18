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
// 체크박스 3개(tmp1=순수임시, wiki1=순수S급, dup=겹침) 모킹
const _boxes = [
  {value:'tmp1', checked:true},
  {value:'wiki1', checked:true},
  {value:'dup', checked:true},
];
global.document = {
  querySelectorAll(sel){ return _boxes; },
};
global.HANDOFF = [
  {shortcode:'tmp1', pickScript:true, script:'임시', useFootage:true},
  {shortcode:'dup', pickScript:true, script:'임시', useFootage:true},
];
// dup은 HANDOFF(임시)와 서버 picks 양쪽에 다 있는 겹침 케이스.
global._serverPickCodes = new Set(['wiki1', 'dup']);
let _toggled = [];
global.fetch = async (url, opts) => {
  _toggled.push(JSON.parse(opts.body).shortcode);
  return { json: async () => ({ok:true}) };
};
global.__toggled = _toggled;
global.window = global;             // picksDeleteSel은 window._serverPickCodes를 읽는다
global.loadWikiForMix = async () => {};   // 재렌더 스텁
"""

_DRIVER = r"""
(async () => {
  await picksDeleteSel();
  console.log(JSON.stringify({
    tmpPick: (HANDOFF.find(h=>h.shortcode==='tmp1')||{}).pickScript,
    tmpFoot: (HANDOFF.find(h=>h.shortcode==='tmp1')||{}).useFootage,
    dupPick: (HANDOFF.find(h=>h.shortcode==='dup')||{}).pickScript,
    dupFoot: (HANDOFF.find(h=>h.shortcode==='dup')||{}).useFootage,
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
    assert "tmp1" not in got["serverToggled"] # 순수 임시는 서버 안 부른다(HANDOFF만)


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_delete_overlap_hits_both_handoff_and_server(tmp_path):
    """겹침(HANDOFF 임시 + 서버 S급 동시)은 두 곳에서 독립적으로 다 빠져야 한다.
    안 그러면 mergePicks가 서버 우선이라 재로드 시 삭제가 무효로 보인다(2026-07-18 리뷰 #2)."""
    got = _run(tmp_path)
    assert got["dupPick"] is False       # HANDOFF에서도 빠진다
    assert got["dupFoot"] is True        # useFootage는 절대 안 건드린다
    assert "dup" in got["serverToggled"] # 서버 toggle도 반드시 불린다
