"""렌더 입구 탭을 **실제로 돌려서** 확인한다(2026-08-22).

⚠️ 짝인 test_render_entry_js.py는 문자열 검사라 "함수 안에 그 낱말이 있나"만 본다.
   2026-08-21에 **테스트 6건 green인데 기능은 안 먹은** 전례가 있어(문자열만 봤다),
   여기서는 scene_lab.html의 함수들을 잘라내 node에서 진짜 실행한다.

특히 지키려는 것:
  ① 탭을 눌렀을 때 부모 startPreview가 **한 번** 불린다
  ② 두 번 눌러도 두 번 안 돈다(서버 렌더는 20초+ 유료)
  ③ **로더가 도는 중에도** 막힌다(로더 HTML이 들어 있으면 innerHTML이 안 비었다)
  ④ clearConfirm 뒤엔 다시 렌더된다(비웠으니 새로 만드는 게 맞다)
"""
import pathlib
import re

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

_LAB = pathlib.Path(__file__).resolve().parents[1] / "static" / "scene_lab.html"


def _fns():
    """scene_lab.html에서 탭·렌더 입구 함수 묶음만 잘라온다.

    `<script>` 블록 중 pvTab 정의가 든 것 하나를 통째로 쓴다 — 함수만 정규식으로
    골라내면 서로를 부르는 관계가 끊겨 "돌긴 도는데 실제 배선과 다른 것"을 잰다.
    """
    src = _LAB.read_text(encoding="utf-8")
    for block in re.findall(r"<script>(.*?)</script>", src, re.S):
        if "function pvTab(" in block and "function _askRender(" in block:
            return block
    raise AssertionError("pvTab·_askRender가 든 <script> 블록을 못 찾았다")


_STUB = r"""
// ── 최소 DOM 스텁 ────────────────────────────────────────────────
function El(id){
  this.id=id; this.innerHTML=''; this._attrs={}; this.disabled=false; this._cls=[];
  this.classList={ _o:this,
    toggle:function(c,on){ var o=this._o; var i=o._cls.indexOf(c);
      if(on && i<0) o._cls.push(c); if(!on && i>=0) o._cls.splice(i,1); },
    add:function(c){ if(this._o._cls.indexOf(c)<0) this._o._cls.push(c); },
    remove:function(c){ var i=this._o._cls.indexOf(c); if(i>=0) this._o._cls.splice(i,1); } };
}
El.prototype.setAttribute=function(k,v){ this._attrs[k]=v; };
El.prototype.getAttribute=function(k){ return (k in this._attrs)?this._attrs[k]:null; };
El.prototype.querySelectorAll=function(){ return { forEach:function(){} }; };
El.prototype.querySelector=function(sel){ return document.querySelector(sel); };

var _els = { playerhost:new El('playerhost'), confirmBody:new El('confirmBody') };
var _tabDraft = new El('tabDraft'), _tabConfirm = new El('tabConfirm');

var document = {
  getElementById:function(id){ return _els[id] || null; },
  querySelector:function(sel){
    if(sel.indexOf('data-pane="confirm"')>=0 && sel.indexOf('pvTab')>=0) return _tabConfirm;
    if(sel.indexOf('data-pane="draft"')>=0  && sel.indexOf('pvTab')>=0) return _tabDraft;
    if(sel.indexOf('#confirmBody video')>=0) return null;   // 확정 영상 없음
    return null;
  },
  querySelectorAll:function(){ return { forEach:function(){} }; }
};
var RENDERS = 0;
var parentWin = { startPreview:function(){ RENDERS++; } };
var window = { parent:parentWin };
window.parent = parentWin;   // window!==parent 조건 만족(둘은 서로 다른 객체다)
var console = { warn:function(){}, log:function(){}, error:function(){} };
function stopPlay(){}
"""

_TAIL = r"""
var fails = [];
function chk(c,m){ if(!c) fails.push(m); }

// ① 탭을 누르면 렌더가 **한 번** 돈다
pvTab('confirm');
chk(RENDERS === 1, '탭을 눌렀는데 렌더가 안 돌았다(RENDERS=' + RENDERS + ')');

// ③ 로더가 도는 중(=confirmBody에 로더 HTML) 다시 눌러도 안 돈다
_els.confirmBody.innerHTML = '<div class="cfLoad">⏳ 미리보기 만드는 중…</div>';
pvTab('draft'); pvTab('confirm');
chk(RENDERS === 1, '로더가 도는 중에 또 렌더했다(20초+ 유료 이중과금, RENDERS=' + RENDERS + ')');

// ② 결과가 붙은 뒤에도 안 돈다
_els.confirmBody.innerHTML = '<video src="x.mp4"></video>';
pvTab('draft'); pvTab('confirm');
chk(RENDERS === 1, '이미 만든 영상이 있는데 또 렌더했다(RENDERS=' + RENDERS + ')');

// ④ clearConfirm(재매칭) 뒤엔 비었으니 다시 만든다
clearConfirm();
chk(_els.confirmBody.innerHTML === '', 'clearConfirm이 내용을 안 비웠다(옛 영상이 남는다)');
chk(_tabConfirm.disabled === false, 'clearConfirm이 탭을 다시 잠갔다 — 렌더 입구가 막힌다');
pvTab('confirm');
chk(RENDERS === 2, '재매칭 뒤에도 새 렌더가 안 돈다(RENDERS=' + RENDERS + ')');

// 부모가 없을 때(단독으로 scene_lab.html을 연 경우) 조용히 안내만 — 죽지 않는다
RENDERS = 0; _els.confirmBody.innerHTML = ''; window.parent = window;
pvTab('confirm');
chk(RENDERS === 0, '부모가 없는데 렌더를 시도했다');
chk(/제작소 화면에서 열어야/.test(_els.confirmBody.innerHTML), '단독 실행 안내가 안 뜬다');

if (fails.length){ console_err('FAIL: ' + fails.join(' / ')); }
else { process.stdout.write('PASS'); }
function console_err(m){ process.stderr.write(m); process.exit(1); }
"""


def test_탭_렌더입구가_실제로_동작한다():
    out = run_js(_STUB + "\n" + _fns() + "\n" + _TAIL)
    assert out.strip() == "PASS", out
