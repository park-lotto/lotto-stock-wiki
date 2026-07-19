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


# ── 동시 전송(2026-07-19 버그) ─────────────────────────────────────────
# 랭킹에서 두 카드의 "제작소로 보내기"를 거의 동시에 누르면, sendToProduce가
# 대본추출을 await(10~30초)라 두 전송이 함께 진행된다. 예전엔 매 전송이 handoff를
# [item] 한 개로 통째 교체 + 즉시 이동해서 하나가 사라졌다. 이제는 (1)기존 배열에
# 누적하고 (2)마지막 전송이 끝날 때만 이동한다.
_HARNESS_CONC = r"""
'use strict';
const _store = {};
global.sessionStorage = {
  setItem(k,v){ _store[k]=v; }, getItem(k){ return _store[k]||null; },
  removeItem(k){ delete _store[k]; },
};
let _hrefSets = 0;
global.location = {}; Object.defineProperty(global.location, 'href', {
  get(){ return this._h||''; }, set(v){ this._h=v; _hrefSets++; },
});
global.__hrefSets = () => _hrefSets;
global.STATE = { items: [
  {shortcode:'sc1', url:'https://x/1', name:'채널A', thumbnail:'https://t/1.jpg', category:'요리'},
  {shortcode:'sc2', url:'https://x/2', name:'채널B', thumbnail:'https://t/2.jpg', category:'요리'},
]};
// fetch: shortcode별로 지연을 달리 줘서 sc1이 먼저, sc2가 나중에 끝나게 한다.
global.fetch = (url) => {
  const sc = new URL('http://x'+ (url.startsWith('/')?url:'/'+url)).searchParams.get('shortcode');
  const delay = sc === 'sc1' ? 5 : 25;   // sc1 먼저 끝난다
  return new Promise(res => setTimeout(() => res({
    json: async () => ({ ok:true, full_text:'대본:'+sc }),
  }), delay));
};
global.document = { getElementById(){ return { disabled:false, textContent:'' }; } };
"""

_DRIVER_CONC = r"""
(async () => {
  const p1 = sendToProduce('sc1');   // await하지 않고
  const p2 = sendToProduce('sc2');   // 곧바로 두 번째도 시작(동시 클릭 재현)
  await Promise.all([p1, p2]);
  const handoff = JSON.parse(sessionStorage.getItem('produce_handoff'));
  console.log(JSON.stringify({
    shortcodes: handoff.map(i=>i.shortcode),
    scripts: handoff.map(i=>i.script),
    href: location.href,
    hrefSets: global.__hrefSets(),
  }));
})();
"""


def _run_conc(tmp_path):
    src = INDEX_HTML.read_text(encoding="utf-8")
    sl = src[src.index(_START):src.index(_END)]
    js = tmp_path / "tc.js"
    js.write_text(_HARNESS_CONC + sl + _DRIVER_CONC, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_concurrent_send_keeps_both(tmp_path):
    got = _run_conc(tmp_path)
    # 둘 다 남는다(예전엔 나중에 끝난 sc2만 남았다)
    assert sorted(got["shortcodes"]) == ["sc1", "sc2"], got
    assert sorted(got["scripts"]) == ["대본:sc1", "대본:sc2"], got


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_concurrent_send_navigates_once_after_both(tmp_path):
    got = _run_conc(tmp_path)
    assert got["href"] == "/produce"
    # 먼저 끝난 sc1이 곧바로 이동하지 않고, 마지막(sc2)이 끝난 뒤 한 번만 이동한다
    assert got["hrefSets"] == 1, got
