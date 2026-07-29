"""P1 — autoloadAllFootage가 4개 초과 소스를 여러 배치로 끝까지 분석하는지(무한루프 없이)."""
import json, pathlib, shutil, subprocess, pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "async function autoloadAllFootage(){"
_END = "// 자동적재가 도는 동안 보여줄 과도 상태"

_HARNESS = r"""
'use strict';
global.HANDOFF = Array.from({length:6}, (_,i)=>({shortcode:'S'+i, url:'https://x/'+i, useFootage:true}));
let _calls = 0;
global._callLog = [];
global.fetch = async (url, opt)=>{
  _calls++;
  const body = JSON.parse(opt.body);
  global._callLog.push(body.items.map(x=>x.shortcode));
  // 1차: 앞 4개 added, 뒤는 서버가 호출당 상한(4)으로 skipped_cap
  // 2차: 남은 2개 added
  if(_calls===1){
    return { json: async ()=>({ added:4, results:[
      {shortcode:'S0',status:'added'},{shortcode:'S1',status:'added'},
      {shortcode:'S2',status:'added'},{shortcode:'S3',status:'added'},
      {shortcode:'S4',status:'skipped_cap'},{shortcode:'S5',status:'skipped_cap'} ]}) };
  }
  return { json: async ()=>({ added:2, results:[
    {shortcode:'S4',status:'added'},{shortcode:'S5',status:'added'} ]}) };
};
"""

_DRIVER = r"""
(async function(){
  const out = await autoloadAllFootage();
  console.log(JSON.stringify({ out, calls: global._callLog.length, log: global._callLog }));
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
def test_autoload_covers_all_via_multiple_batches(tmp_path):
    got = _run(tmp_path)
    assert got["out"]["added"] == 6          # 6개 전부 분석됨(4+2)
    assert got["out"]["analyzed"] is True
    assert 2 <= got["calls"] <= 3            # 여러 배치, 무한루프 아님
