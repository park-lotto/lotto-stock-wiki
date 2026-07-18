"""제작소 — 랭킹에서 여러 번 보낸 영상이 누적된다(2026-07-18 라이브 버그).

사장님 제보: "레퍼런스에서 대본으로 보내기를 두 개 하면 제작소에 한 개만 넘어오고,
다른 걸 누르면 (첫 번째가) 지워진다." 원인: _consumeProduceHandoff가 신규 핸드오프가
있으면 진행 중 작업(produce_work)을 무시하고 HANDOFF를 통째 대체했다.
→ 진행 중 작업을 먼저 복원하고 신규 핸드오프를 거기에 누적(중복 제거)한다.

produce.html의 실제 _consumeProduceHandoff를 앵커로 잘라 Node로 구동한다(재구현 아님).
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_START = "function _consumeProduceHandoff(){"
_END = "// 왼쪽 영상 풀 렌더"

_HARNESS = r"""
'use strict';
const _ss = {};
global.sessionStorage = {
  setItem:(k,v)=>_ss[k]=v, getItem:k=>(k in _ss?_ss[k]:null), removeItem:k=>delete _ss[k],
};
global.HANDOFF = [];
global.WORK_ID = null;
global.STATE = {};
global.document = { getElementById:()=>({ style:{}, innerHTML:'' }) };
global.setScriptMode = ()=>{};
global.renderPool = ()=>{};
global.syncFootageToMixUrls = ()=>{};
global.refreshFinalPeek = ()=>{};
global.saveWork = ()=>{ _ss['produce_work'] = JSON.stringify({handoff:global.HANDOFF, work_id:global.WORK_ID}); };
"""

_DRIVER = r"""
(function(){
  // 1) 진행 중 작업: 영상 A가 이미 담겨 저장돼 있다(뽑기까지 함)
  global.HANDOFF = [{shortcode:'A', url:'https://x/A', name:'영상A', thumbnail:'ta',
                     pickScript:true, useFootage:true, script:'A대본'}];
  global.WORK_ID = 'w1';
  saveWork();                                    // produce_work에 [A] 저장
  global.HANDOFF = [];                           // 새로고침/재진입처럼 메모리 초기화

  // 2) 랭킹에서 영상 B를 '제작소로 보내기' → produce_handoff에 [B]
  sessionStorage.setItem('produce_handoff', JSON.stringify([
    {shortcode:'B', url:'https://x/B', name:'영상B', thumbnail:'tb',
     pickScript:true, useFootage:true, script:'B대본'}]));

  // 3) 제작소 소비
  _consumeProduceHandoff();
  const codes = global.HANDOFF.map(x=>x.shortcode);
  const scripts = global.HANDOFF.map(x=>x.script);

  // 4) 다시 B를 또 보내면(같은 영상) 중복으로 안 쌓인다
  global.HANDOFF = [];
  sessionStorage.setItem('produce_handoff', JSON.stringify([
    {shortcode:'B', url:'https://x/B', name:'영상B', thumbnail:'tb',
     pickScript:true, useFootage:true, script:'B대본'}]));
  _consumeProduceHandoff();
  const codesDup = global.HANDOFF.map(x=>x.shortcode);

  console.log(JSON.stringify({
    누적_codes: codes, 누적_scripts: scripts,
    A유지: codes.includes('A'), B추가: codes.includes('B'),
    work_id유지: global.WORK_ID,
    중복안쌓임: codesDup.filter(c=>c==='B').length,
    중복후_codes: codesDup,
  }));
})();
"""


def _run(tmp_path):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    sl = src[src.index(_START):src.index(_END)]
    js = tmp_path / "t.js"
    js.write_text(_HARNESS + sl + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_second_send_accumulates_not_replaces(tmp_path):
    """★두 번째 보내기가 첫 번째를 지우지 않고 누적된다(라이브 버그의 핵심)."""
    got = _run(tmp_path)
    assert got["A유지"] is True          # 진행 중이던 영상 A가 살아있다
    assert got["B추가"] is True          # 새로 보낸 B도 들어왔다
    assert got["누적_codes"] == ["A", "B"]
    assert got["work_id유지"] == "w1"    # 같은 작업에 누적(새 작업 안 만듦)


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_scripts_ride_along_on_accumulate(tmp_path):
    """누적돼도 각 영상의 대본(script)이 딸려 유지된다."""
    got = _run(tmp_path)
    assert "A대본" in got["누적_scripts"]
    assert "B대본" in got["누적_scripts"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_same_video_not_duplicated(tmp_path):
    """같은 영상을 또 보내면 중복으로 안 쌓인다(shortcode 기준)."""
    got = _run(tmp_path)
    assert got["중복안쌓임"] == 1        # B가 딱 한 번만
