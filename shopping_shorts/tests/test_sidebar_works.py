"""사이드바 작업 목록 — 숏템 제작소 아래에 내 작업이 뜬다(스펙 §4.4).

sidebar.js는 페이지 6개가 공유한다 — 목록 주입이 다른 페이지를 깨면 안 된다.
"""
import json
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


# ── 목록 다시 그리기(2026-08-06) ────────────────────────────────────────────
# 사장님 제보: "따로 만들기를 누르면 내 작업에 추가가 되야 하는데 안 된다".
# mountWorks는 페이지 로드 때 한 번만 돌아 화면 안에서 생긴 작업이 안 보였다.
# ★.ss-works를 찾아 **갈아끼우는지**를 봐야 하므로 _nav.querySelector를 실제로 동작시킨다
#   (기본 harness는 null만 돌려줘서 '중복 삽입'을 못 잡는다).
_NAV_QS = """
_nav.querySelector = function(sel){
  var cls = sel.replace('.','');
  for (var i=0;i<this.children.length;i++){
    var c = this.children[i];
    if (c.classList && c.classList.contains && c.classList.contains(cls)) return c;
    if (typeof c.className === 'string' && c.className.split(' ').indexOf(cls) !== -1) return c;
  }
  return null;
};
_nav.replaceChild = function(nu, old){
  var i = this.children.indexOf(old);
  if (i >= 0) this.children[i] = nu; else this.children.push(nu);
  this._html = this.children.map(function(c){ return c._html || ''; }).join('');
  return old;
};
"""


def test_refresh_hook_is_exposed():
    """전역 훅이 없으면 화면 안에서 목록을 다시 그릴 방법이 아예 없다."""
    out = _run("console.log(typeof window.__ssRefreshWorks);", harness_override=_NAV_QS)
    assert out == "function", out


def test_refresh_does_not_duplicate_the_list():
    """★다시 그릴 때 기존 .ss-works를 갈아끼워야 한다 — 그냥 삽입하면 '내 작업'이 두 벌 쌓인다."""
    out = _run("""
      window.__ssRefreshWorks();
      await new Promise(r=>setTimeout(r,20));
      console.log(_nav.children.filter(c => c.className === 'ss-group ss-works').length);
    """, harness_override=_NAV_QS)
    assert out == "1", f"목록 블록이 {out}개 — 다시 그리기가 중복 삽입됐다"


def test_refresh_shows_newly_created_work():
    """복제로 생긴 작업이 **새로고침 없이** 목록에 뜬다(이 버그의 본체)."""
    out = _run("""
      WORKS_RESPONSE = { ok:true, works:[
        {work_id:'w1', title:'협탁 인테리어 대본', step:1, job_id:'j1', updated_at:'2026-07-17T01:00:00+00:00'},
        {work_id:'w9', title:'C안 토마토 주스', step:2, job_id:'j9', updated_at:'2026-08-06T01:00:00+00:00'}]};
      window.__ssRefreshWorks('w9');
      await new Promise(r=>setTimeout(r,20));
      const h = _nav.children.filter(c => c.className === 'ss-group ss-works')[0]._html;
      console.log(JSON.stringify({shown: h.indexOf('C안 토마토 주스') !== -1,
                                  cur: h.indexOf('data-wid="w9"') !== -1 && h.indexOf('ss-work-current') !== -1}));
    """, harness_override=_NAV_QS)
    assert '"shown":true' in out, f"새 작업이 목록에 안 떴다: {out}"
    assert '"cur":true' in out, f"새 작업이 '지금 작업'으로 표시 안 됐다: {out}"


def test_refresh_current_id_beats_url():
    """cloneCandidate는 URL을 즉시 안 바꾼다 — 인자로 받은 id가 ?work= 보다 우선해야
    '지금 작업' 표시가 원본 쪽에 잘못 남지 않는다.
    (WORK_ID는 produce.html에서 `let`이라 window에 안 올라간다 → 인자로 넘기는 게 유일한 길.)"""
    out = _run("""
      window.__ssRefreshWorks('w2');
      await new Promise(r=>setTimeout(r,20));
      const h = _nav.children.filter(c => c.className === 'ss-group ss-works')[0]._html;
      const i2 = h.indexOf('data-wid="w2"'), i1 = h.indexOf('data-wid="w1"');
      console.log(h.slice(0, i2).lastIndexOf('ss-work-current') > i1 ? 'w2-current' : 'wrong');
    """, harness_override=_NAV_QS + "location.search='?work=w1';")
    assert out == "w2-current", f"URL의 w1이 인자 w2를 이겼다: {out}"


def test_angle_brackets_in_title_do_not_become_tags():
    """대본에 <>가 있으면 진짜 DOM 태그로 살아나면 안 된다."""
    out = _run("console.log(_nav.innerHTML);",
               harness_override='''WORKS_RESPONSE = {ok:true, works:[
                 {work_id:'w1', title:'감자 레시피 <꿀팁>', step:0, job_id:null, updated_at:'2026-07-17T01:00:00+00:00'}]};''')
    assert "<꿀팁>" not in out, "꺾쇠가 그대로 나가 태그가 된다"
    assert "&lt;" in out


# ── 이름 바꾸기 ✏ (2026-08-17) ─────────────────────────────────────
# 사장님 "내 작업에 작업명 수정할수있게". 목록이 '(제목 없음)' 여러 줄이라 구분이 안 됐다.
# ★문자열 검사로 끝내지 않는다 — 이 파일 주석의 경고대로 "코드에 그 문자열이 있다"가
#   런타임 동작을 보장하지 않는다(슬라이스 섀도잉으로 실제로 한 번 속았다). 핸들러를
#   **직접 불러** 무엇을 POST하고 화면을 어떻게 고치는지 본다.
_RENAME_HS = _NAV_QS + """
// 행(.ss-work[data-wid=..])과 그 안의 이름 칸을 찾아주는 최소 DOM.
var _rows = {};
function _mkRow(wid, label){
  var nameEl = { textContent: '· ' + label };
  var openEl = { title: label };
  var row = { querySelector: function(sel){
    if (sel === '.ss-work-name') return nameEl;
    if (sel === '.ss-work-open') return openEl;
    return null; } };
  row._name = nameEl; row._open = openEl;
  _rows[wid] = row; return row;
}
_mkRow('w1', '협탁 인테리어 대본');
_mkRow('w2', '(제목 없음)');
document.querySelector = function(sel){
  if (sel === '.ss-nav') return _nav;
  var m = /data-wid="([^"]+)"/.exec(sel || '');
  if (m) return _rows[m[1]] || null;
  return null;
};
var PROMPT_ARGS = null, PROMPT_RET = '새 이름';
window.prompt = function(msg, def){ PROMPT_ARGS = {msg: msg, def: def}; return PROMPT_RET; };
window.alert = function(m){ console.log('ALERT:' + m); };
var POSTED = [];
var RENAME_RESPONSE = null;   // null이면 서버가 준 이름을 그대로 되돌려준다
var _origFetch = fetch;
fetch = async function(url, opt){
  if (String(url).indexOf('/rename') !== -1){
    POSTED.push({url: url, opt: opt});
    var body = JSON.parse(opt.body);
    var d = RENAME_RESPONSE || {ok: true, title: body.name || '자동제목'};
    return { json: async () => d };
  }
  return _origFetch(url, opt);
};
"""


def test_rename_button_is_rendered():
    out = _run("console.log(_nav.innerHTML.indexOf('__ssRenWork') !== -1 ? 'has-btn' : 'missing');")
    assert out == "has-btn", "✏ 버튼이 목록에 안 그려졌다 — 이름을 바꿀 손잡이가 없다"


def test_rename_posts_new_name_and_updates_row():
    """✏ → 이름 입력 → 서버에 POST → 화면의 그 행이 즉시 바뀐다(새로고침 없이)."""
    out = _run("""
      PROMPT_RET = '요거트케이크 A안';
      window.__ssRenWork({stopPropagation(){}}, 'w2');
      await new Promise(r=>setTimeout(r,20));
      console.log(JSON.stringify({
        posted: POSTED.length,
        url: POSTED[0] && POSTED[0].url,
        sent: POSTED[0] && JSON.parse(POSTED[0].opt.body).name,
        method: POSTED[0] && POSTED[0].opt.method,
        name: _rows['w2']._name.textContent,
        title: _rows['w2']._open.title,
      }));
    """, harness_override=_RENAME_HS)
    d = json.loads(out)
    assert d["posted"] == 1 and d["method"] == "POST"
    assert d["url"] == "/api/produce/works/w2/rename"
    assert d["sent"] == "요거트케이크 A안"
    assert d["name"] == "· 요거트케이크 A안", f"행 이름이 안 바뀌었다: {d}"
    assert d["title"] == "요거트케이크 A안", "title 속성(툴팁)도 같이 바뀌어야 한다"


def test_rename_cancel_does_not_post():
    """취소(prompt가 null)면 아무 일도 없어야 한다 — 빈 이름으로 지워버리면 안 된다."""
    out = _run("""
      PROMPT_RET = null;
      window.__ssRenWork({stopPropagation(){}}, 'w1');
      await new Promise(r=>setTimeout(r,20));
      console.log(JSON.stringify({posted: POSTED.length, name: _rows['w1']._name.textContent}));
    """, harness_override=_RENAME_HS)
    d = json.loads(out)
    assert d["posted"] == 0, "취소했는데 서버로 보냈다"
    assert d["name"] == "· 협탁 인테리어 대본"


def test_rename_empty_string_is_sent_as_reset():
    """빈 문자열은 취소가 아니라 '자동 제목으로 되돌리기'다 — 서버까지 가야 한다."""
    out = _run("""
      PROMPT_RET = '';
      window.__ssRenWork({stopPropagation(){}}, 'w1');
      await new Promise(r=>setTimeout(r,20));
      console.log(JSON.stringify({posted: POSTED.length,
                                  sent: POSTED[0] && JSON.parse(POSTED[0].opt.body).name}));
    """, harness_override=_RENAME_HS)
    d = json.loads(out)
    assert d["posted"] == 1 and d["sent"] == ""


def test_rename_prefills_current_name_without_bullet():
    """현재 이름이 기본값으로 뜬다. '· '는 화면 장식이라 빼고, '(제목 없음)'은 빈 칸으로."""
    out = _run("""
      window.__ssRenWork({stopPropagation(){}}, 'w1');
      await new Promise(r=>setTimeout(r,20));
      const a = PROMPT_ARGS.def;
      window.__ssRenWork({stopPropagation(){}}, 'w2');
      await new Promise(r=>setTimeout(r,20));
      console.log(JSON.stringify({w1: a, w2: PROMPT_ARGS.def}));
    """, harness_override=_RENAME_HS)
    d = json.loads(out)
    assert d["w1"] == "협탁 인테리어 대본", f"현재 이름이 기본값으로 안 떴다: {d}"
    assert d["w2"] == "", "'(제목 없음)'은 지울 필요 없이 빈 칸이어야 한다"


def test_rename_uses_server_title_not_local_guess():
    """★제목은 서버(store._work_title)가 정한다 — 화면이 따로 계산하면 어긋난다(0순위-B).
    서버가 다른 제목을 주면 화면은 **그 값**을 따라야 한다."""
    out = _run("""
      PROMPT_RET = '';
      RENAME_RESPONSE = {ok:true, title:'서버가 정한 자동제목'};
      window.__ssRenWork({stopPropagation(){}}, 'w1');
      await new Promise(r=>setTimeout(r,20));
      console.log(_rows['w1']._name.textContent);
    """, harness_override=_RENAME_HS)
    assert out == "· 서버가 정한 자동제목"


def test_rename_notifies_producer_page():
    """지금 열려 있는 작업이면 제작소 STATE에도 심어야 한다 — 안 그러면 다음 자동저장이
    이름 없는 state를 덮어써 방금 지은 이름이 조용히 사라진다."""
    out = _run("""
      var GOT = null;
      window.__ssApplyWorkTitle = function(wid, name){ GOT = {wid: wid, name: name}; };
      PROMPT_RET = '내 이름';
      window.__ssRenWork({stopPropagation(){}}, 'w2');
      await new Promise(r=>setTimeout(r,20));
      console.log(JSON.stringify(GOT));
    """, harness_override=_RENAME_HS)
    assert json.loads(out) == {"wid": "w2", "name": "내 이름"}


def test_rename_failure_does_not_change_row():
    """서버가 거절하면 화면을 고치지 않는다 — 바뀐 척하면 새로고침에 되돌아가 혼란만 준다."""
    out = _run("""
      PROMPT_RET = '새 이름';
      RENAME_RESPONSE = {ok:false, error:'작업 없음'};
      window.__ssRenWork({stopPropagation(){}}, 'w1');
      await new Promise(r=>setTimeout(r,20));
      console.log(_rows['w1']._name.textContent);
    """, harness_override=_RENAME_HS)
    assert out.endswith("협탁 인테리어 대본"), f"실패했는데 행이 바뀌었다: {out}"


def test_rename_pencil_has_variation_selector():
    """★맨 ✏(U+270F)는 윈도우 크롬에서 '옆으로 누운 막대'로 그려진다(실측 스크린샷).
    U+FE0F(VS16)를 붙여야 연필 모양이 된다 — 아이콘이 뭔지 모르면 아무도 안 누른다."""
    src = SIDEBAR_JS.read_text(encoding="utf-8")
    assert "\u270f\ufe0f" in src, "✏에 VS16(U+FE0F)이 빠졌다 — 막대기로 보인다"
