"""사이드바 작업 목록 — 숏템 제작소 아래에 내 작업이 뜬다(스펙 §4.4).

sidebar.js는 페이지 6개가 공유한다 — 목록 주입이 다른 페이지를 깨면 안 된다.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile

import pytest

SIDEBAR_JS = pathlib.Path(__file__).resolve().parents[1] / "static" / "sidebar.js"
NODE = shutil.which("node")

_HARNESS = r"""
'use strict';
const _created = [];
function _el(tag){
  const o = { tagName:tag, children:[], _html:'', style:{}, textContent:'',
              classList:{ _s:new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
                          contains(c){return this._s.has(c);} },
              appendChild(c){ this.children.push(c); this._html += (c._html || ''); return c; },
              insertBefore(c, ref){ const i = ref ? this.children.indexOf(ref) : -1;
                if (i < 0) { this.children.push(c); } else { this.children.splice(i, 0, c); } return c; },
              querySelector(){ return null; }, addEventListener(){} };
  Object.defineProperty(o, 'innerHTML', { get(){return o._html;}, set(v){o._html=String(v);} });
  _created.push(o);
  return o;
}
const _byId = {};
const _nav = _el('div');
function _createElement(tag){ return tag === 'aside' ? _nav : _el(tag); }
const document = {
  createElement:_createElement,
  head:_el('head'),
  body:_el('body'),
  getElementById(id){ return _byId[id] || null; },
  querySelector(sel){ return sel === '.ss-nav' ? _nav : null; },
  querySelectorAll(){ return []; },
  addEventListener(ev, fn){ if(ev==='DOMContentLoaded') _domReady.push(fn); },
  readyState:'complete',
};
const _domReady = [];
const location = { pathname:'/produce', search:'', href:'/produce' };
let WORKS_RESPONSE = { ok:true, works:[
  { work_id:'w1', title:'협탁 인테리어 대본', step:1, job_id:'j1', updated_at:'2026-07-17T01:00:00+00:00' },
  { work_id:'w2', title:'감자 레시피', step:3, job_id:'j2', updated_at:'2026-07-16T01:00:00+00:00' },
]};
const FETCHED = [];
async function fetch(url){
  FETCHED.push(url);
  if (WORKS_RESPONSE === 'throw') throw new Error('네트워크');
  return { json: async () => WORKS_RESPONSE };
}
const window = { location };
"""


def _run(body, harness_override=""):
    src = SIDEBAR_JS.read_text(encoding="utf-8")
    js = _HARNESS + harness_override + "\n" + src + "\n"
    js += "(async()=>{ await new Promise(r=>setTimeout(r,0)); \n" + body + "\n})();"
    # node -e 로 인라인하면 js 전체가 명령줄 인자가 돼 Windows 명령줄 길이 한계(~32KB)에 걸린다
    # — sidebar.js가 커지면 WinError 206으로 죽는다(리눅스 서버는 ARG_MAX가 커서 안 터져 게이트가
    # 갈렸다). 임시 .js 파일로 넘겨 길이 제한을 없앤다(단언·동작 동일, 전달 방식만 교체).
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run([NODE, path], capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    finally:
        os.unlink(path)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def test_works_are_fetched_on_produce_page():
    out = _run("console.log(FETCHED.filter(u=>u.indexOf('/api/produce/works')!==-1).length ? 'fetched' : 'no');")
    assert out == "fetched"


def test_work_titles_appear_in_nav():
    out = _run("console.log(_nav.innerHTML.indexOf('협탁 인테리어 대본') !== -1 ? 'shown' : 'missing');")
    assert out == "shown"


def test_work_links_to_restore_url():
    out = _run("console.log(_nav.innerHTML.indexOf('/produce?work=w1') !== -1 ? 'linked' : 'missing');")
    assert out == "linked"


def test_new_work_entry_exists():
    """'+ 새 작업'이 없으면 작업이 하나 생긴 뒤로 새 작업을 시작할 길이 없다."""
    out = _run("console.log(_nav.innerHTML.indexOf('새 작업') !== -1 ? 'ok' : 'missing');")
    assert out == "ok"


def test_current_work_is_marked():
    """어느 게 지금 보고 있는 작업인지 보여야 한다(스펙 §4.4)."""
    out = _run("console.log(_nav.innerHTML.indexOf('ss-work-current') !== -1 ? 'marked' : 'missing');",
               harness_override="")
    # ?work=w1로 들어온 상태를 만든다
    out2 = _run("console.log(_nav.innerHTML.indexOf('ss-work-current') !== -1 ? 'marked' : 'missing');",
                harness_override="location.search='?work=w1'; location.pathname='/produce';")
    assert out2 == "marked"
    assert out == "missing", "아무 작업도 안 열었는데 현재 표시가 붙었다"


def test_works_fetched_on_all_pages():
    """T6(2026-07-19): 작업 목록을 /produce 전용 → 전 페이지 노출로 바꿨다(설계서 §3-3).
    어느 화면에서도 진행 중 작업으로 바로 복귀 — 그래서 /library 같은 다른 페이지에서도 fetch한다.
    (옛 test_no_fetch_on_other_pages를 뒤집은 것: 그땐 /produce에서만 불렀다.)"""
    out = _run("console.log(FETCHED.filter(u=>u.indexOf('/api/produce/works')!==-1).length ? 'fetched' : 'no');",
               harness_override="location.pathname='/library';")
    assert out == "fetched"


def test_empty_list_does_not_break_nav():
    out = _run("console.log(_nav.innerHTML.indexOf('숏템 제작소') !== -1 ? 'nav-ok' : 'nav-broken');",
               harness_override="WORKS_RESPONSE = {ok:true, works:[]};")
    assert out == "nav-ok"


def test_fetch_failure_does_not_break_nav():
    """서버가 죽어도 사이드바는 살아 있어야 한다 — 이건 6개 페이지의 유일한 네비게이션이다."""
    out = _run("console.log(_nav.innerHTML.indexOf('숏템 제작소') !== -1 ? 'nav-ok' : 'nav-broken');",
               harness_override="WORKS_RESPONSE = 'throw';")
    assert out == "nav-ok"


def test_quoted_script_title_does_not_break_markup():
    """★따옴표로 시작하는 대본은 쇼핑 숏폼의 관습이다 — 그것 하나로 사이드바가 깨지면 안 된다.
    esc()는 작은따옴표만 JS-이스케이프하는 함수라 title=" 속성과 텍스트 자리엔 부적합했다."""
    out = _run("console.log(_nav.innerHTML);",
               harness_override='''WORKS_RESPONSE = {ok:true, works:[
                 {work_id:'w1', title:'"이거 실화냐?" 협탁이', step:0, job_id:null, updated_at:'2026-07-17T01:00:00+00:00'}]};''')
    assert 'title=""' not in out, "title 속성이 따옴표에서 끊겼다"
    assert "&quot;" in out or "&#34;" in out, "큰따옴표가 이스케이프되지 않았다"


def test_work_has_delete_button():
    """각 작업에 삭제(✕) 버튼이 있어야 지울 수 있다(2026-07-19 사장님 요청)."""
    out = _run("console.log(JSON.stringify({"
               "del: _nav.innerHTML.indexOf('ss-work-del') !== -1,"
               "fn: _nav.innerHTML.indexOf('__ssDelWork') !== -1,"
               "wid: _nav.innerHTML.indexOf('data-wid=\"w1\"') !== -1}));")
    assert '"del":true' in out and '"fn":true' in out and '"wid":true' in out, out


def test_delete_calls_backend_and_removes_row():
    """✕ 클릭 → 삭제 API 호출. confirm=true 가정."""
    out = _run("""
      window.confirm = function(){ return true; };
      window.alert = function(){};
      const before = FETCHED.length;
      window.__ssDelWork({stopPropagation:function(){}}, 'w1');
      await new Promise(r=>setTimeout(r,20));
      console.log(FETCHED.filter(u=>u.indexOf('/api/produce/works/w1/delete')!==-1).length ? 'called' : 'no');
    """)
    assert out == "called", f"삭제 API가 안 불렸다: {out}"


def test_delete_aborts_when_not_confirmed():
    """confirm=false면 아무것도 안 한다 — 실수 삭제 방지."""
    out = _run("""
      window.confirm = function(){ return false; };
      window.__ssDelWork({stopPropagation:function(){}}, 'w1');
      await new Promise(r=>setTimeout(r,20));
      console.log(FETCHED.filter(u=>u.indexOf('/delete')!==-1).length ? 'called' : 'aborted');
    """)
    assert out == "aborted", f"확인 취소했는데 삭제됐다: {out}"


def test_angle_brackets_in_title_do_not_become_tags():
    """대본에 <>가 있으면 진짜 DOM 태그로 살아나면 안 된다."""
    out = _run("console.log(_nav.innerHTML);",
               harness_override='''WORKS_RESPONSE = {ok:true, works:[
                 {work_id:'w1', title:'감자 레시피 <꿀팁>', step:0, job_id:null, updated_at:'2026-07-17T01:00:00+00:00'}]};''')
    assert "<꿀팁>" not in out, "꺾쇠가 그대로 나가 태그가 된다"
    assert "&lt;" in out
