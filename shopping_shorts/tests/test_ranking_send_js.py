"""레퍼런스 랭킹 카드 → 제작소로 보내기(2026-07-18).

index.html의 실제 sendToProduce를 앵커로 잘라 Node로 구동한다(재구현 아님).
"""
import json
import pathlib
import shutil
import subprocess

import pytest

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")

_START = "async function sendToProduce("
_END = "function renderScript("

_HARNESS = r"""
'use strict';
const _store = {};
global.sessionStorage = {
  setItem(k,v){ _store[k]=v; }, getItem(k){ return _store[k]||null; },
  removeItem(k){ delete _store[k]; },
};
global.location = { href:'' };
global.STATE = { items: [
  {shortcode:'sc1', url:'https://x/1', name:'채널A', username:'a',
   thumbnail:'https://t/1.jpg', category:'요리'},
]};
let _fetchCalls = [];
global.fetch = async (url, opts) => {
  _fetchCalls.push(url);
  return { json: async () => ({ ok:true, full_text:'뽑은 대본 본문' }) };
};
global.__fetchCalls = _fetchCalls;
function _btn(){ return { disabled:false, textContent:'' }; }
global.document = { getElementById(){ return _btn(); } };
"""

_DRIVER = r"""
(async () => {
  await sendToProduce('sc1');
  const handoff = JSON.parse(sessionStorage.getItem('produce_handoff'));
  console.log(JSON.stringify({
    handoff, href: location.href,
    extractCalled: global.__fetchCalls.some(u=>u.includes('extract_script')),
  }));
})();
"""


def _run(tmp_path, state_items=None, cached_script=None):
    src = INDEX_HTML.read_text(encoding="utf-8")
    sl = src[src.index(_START):src.index(_END)]
    js = tmp_path / "t.js"
    js.write_text(_HARNESS + sl + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_send_puts_video_and_script_in_handoff(tmp_path):
    got = _run(tmp_path)
    item = got["handoff"][0]
    assert item["shortcode"] == "sc1"
    assert item["useFootage"] is True       # 영상풀 카드로 뜬다
    assert item["pickScript"] is True        # 담긴 대본으로 뜬다
    assert item["script"] == "뽑은 대본 본문"  # 추출한 대본을 실어 나른다
    assert item["thumbnail"] == "https://t/1.jpg"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_send_navigates_to_produce(tmp_path):
    got = _run(tmp_path)
    assert got["href"] == "/produce"
    assert got["extractCalled"] is True
