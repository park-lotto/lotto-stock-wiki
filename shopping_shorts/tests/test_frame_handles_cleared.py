"""틀을 지우면 띠·[광고] 손잡이도 같이 사라져야 한다 (2026-08-24 사장님 제보).

## 무엇이 문제였나

사장님: *"템플릿 했다가 삭제했는데 가운데 높이조절하는건 안지워짐"*

`syncFrameHandles()`는 틀이 없으면 손잡이 3개를 숨기도록 **이미 제대로 짜여
있었다**. 문제는 그 함수가 **삭제 경로에서 아예 안 불렸다**는 것:

    function renderTemplatePreview(){
      ...
      if(!t||(!t.id&&!t.frame)){ if(el) el.style.display='none'; return; }  ← 여기서 나간다
      ...
      syncFrameHandles();     ← 그래서 여기까지 못 온다

틀 그림(`#tplPreview`)만 숨기고 손잡이는 손대지 않은 채 return → 흰 막대가
미리보기 한가운데 남았다. 손잡이는 `position:absolute`로 **미리보기에 직접
붙어 있어**(pv.appendChild) 틀 그림을 숨겨도 같이 안 사라진다.

## 이 테스트가 지키는 것

함수를 **실제로 돌려서** 손잡이 3개(frHandleTop/frHandleBottom/frHandleAd)가
전부 display:none이 되는지 본다. 텍스트 검사가 아니라 동작 검사다 —
"syncFrameHandles가 코드에 있다"는 건 위 사고를 못 잡는다(있었는데 안 불렸다).
"""
import os
import pathlib
import re

import pytest

from shopping_shorts.tests.js_harness import run_js, requires_node

pytestmark = requires_node

HTML = pathlib.Path(__file__).resolve().parents[1].joinpath(
    "static", "produce.html").read_text(encoding="utf-8")


def _slice(start_marker, end_marker):
    """produce.html에서 함수 하나를 이름으로 잘라낸다."""
    i = HTML.index(start_marker)
    j = HTML.index(end_marker, i + len(start_marker))
    return HTML[i:j]


def _harness(state_js):
    """DOM을 최소한만 흉내내고, 함수 3개를 실제로 돌린 뒤 손잡이 상태를 찍는다.

    ★`window.x=` 맨몸 대입을 쓰지 않는다 — produce.html의 `let` 선언과 부딪혀
      ReferenceError로 죽는 함정이 있다(reference_슬라이스하네스_window금지).
    """
    src = (_slice("const FR_MAX_BAR=", "function syncFrameHandles(")
           + _slice("function syncFrameHandles(", "// ── 🖱 [광고] 위치 드래그")
           + _slice("const FR_AD_DEF_X =", "function frAdReset(")
           + _slice("function syncAdHandle(", "function bindAdHandle(")
           + _slice("function renderTemplatePreview(", "// 🗂 탭 전환"))
    return r"""
// ── 최소 DOM 흉내 ──────────────────────────────────────────────
const NODES = {};
function mkNode(id){
  return {
    id: id,
    style: new Proxy({cssText:''}, {set:(o,k,v)=>{o[k]=v; return true;}}),
    innerHTML: '', title: '', src: '',
    children: [],
    appendChild(c){ this.children.push(c); if(c.id) NODES[c.id]=c; return c; },
    addEventListener(){},
    getBoundingClientRect(){ return {width:270, height:480, left:0, top:0}; },
  };
}
NODES['hcPreview'] = mkNode('hcPreview');
const document = {
  getElementById: (id) => NODES[id] || null,
  createElement: () => mkNode(''),
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener(){}, removeEventListener(){},
};
// 손잡이가 만들어질 때 id가 나중에 붙으므로, appendChild 시점에 등록되게 보강
NODES['hcPreview'].appendChild = function(c){
  this.children.push(c);
  // id는 appendChild 직전에 대입된다 — 여기서 잡는다
  if(c.id) NODES[c.id] = c;
  return c;
};
const STATE = {deco: null, headcopy: {}};
function frameUrl(){ return 'about:blank'; }
function saveHeadcopy(){}
const TPL_LIST = [];
// 드래그 배선은 이 검사의 관심사가 아니다(손잡이가 생기고 사라지는지만 본다)
function bindFrameHandle(){}
function bindAdHandle(){}
function frUpdate(){}

""" + src + r"""

// ── 실행 ───────────────────────────────────────────────────────
// ① 먼저 틀을 골라 손잡이 3개를 실제로 만든다
STATE.deco = {template:{span:'full', frame:{preset:'news_coral', bar_h:190,
              bottom_h:120, ad_badge:true, icons:true}}};
renderTemplatePreview();
const made = ['frHandleTop','frHandleBottom','frHandleAd'].filter(id => NODES[id]);

// ② 그리고 삭제한다(frPick('') / pickTemplate('')가 하는 일)
""" + state_js + r"""
renderTemplatePreview();

const after = {};
['frHandleTop','frHandleBottom','frHandleAd'].forEach(id => {
  after[id] = NODES[id] ? (NODES[id].style.display || '') : 'MISSING';
});
console.log(JSON.stringify({made: made, after: after}));
"""


def _run(state_js):
    out = run_js(_harness(state_js))
    import json
    return json.loads(out.strip().splitlines()[-1])


def test_handles_are_created_when_a_frame_is_picked():
    """전제 확인 — 손잡이 3개가 실제로 만들어진다(안 만들어지면 아래 검사가 무의미)."""
    r = _run("STATE.deco.template = null;")
    assert r["made"] == ["frHandleTop", "frHandleBottom", "frHandleAd"], \
        f"손잡이가 안 만들어졌다: {r['made']}"


def test_deleting_the_frame_hides_every_handle():
    """★본 건 — 틀을 지우면 손잡이 3개가 전부 숨는다."""
    r = _run("STATE.deco.template = null;")
    for hid, disp in r["after"].items():
        assert disp == "none", f"{hid}이 안 지워졌다(display={disp!r})"


def test_deleting_via_empty_template_object_also_hides_handles():
    """색띠 템플릿을 지운 모양(id·frame 둘 다 없음)에서도 같아야 한다."""
    r = _run("STATE.deco.template = {span:'full'};")
    for hid, disp in r["after"].items():
        assert disp == "none", f"{hid}이 안 지워졌다(display={disp!r})"


def test_switching_from_frame_to_color_band_hides_frame_handles():
    """틀 → 색띠 템플릿으로 갈아타도 띠 손잡이는 남으면 안 된다."""
    r = _run("STATE.deco.template = {id:'band_navy', span:'full'};")
    for hid, disp in r["after"].items():
        assert disp == "none", f"{hid}이 안 지워졌다(display={disp!r})"


def test_early_return_still_syncs_handles():
    """되돌림 방지 — '틀 없음' 분기가 syncFrameHandles 없이 return하면 안 된다."""
    seg = _slice("function renderTemplatePreview(", "// 🗂 탭 전환")
    m = re.search(r"if\(!t\|\|\(!t\.id&&!t\.frame\)\)\{([^}]*)\}", seg)
    assert m, "'틀 없음' 분기를 못 찾았다 — 검사가 낡았다"
    assert "syncFrameHandles" in m.group(1), \
        "틀이 없을 때 syncFrameHandles()를 안 부른다 — 손잡이가 남는다"
