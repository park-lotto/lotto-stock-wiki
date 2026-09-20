# -*- coding: utf-8 -*-
"""제작소 — 저장된 단계를 알기 전에 1단계를 먼저 그리지 않는가.

2026-09-07 사장님 "3단계 새로고침하면 1단계 화면 보였다가 다시 3단계로 감".
`let cur = 0`(=1단계)이라 서버에서 step을 받기 전에 첫 화면을 그리면 항상 1단계가
번쩍인다. 고객 눈엔 "잘못 열렸나?"로 보인다.

★cur 값이나 저장 순서는 건드리지 않는다 — 2026-08-06에 cur=0이 서버 step을 덮어써
  작업 3개가 1단계로 고정된 사고가 있었다. 미루는 것은 **그리기**뿐이다.

판정은 문자열 세기가 아니라 **실제 실행**이다 — showPanel을 node로 돌려
어떤 패널이 켜졌는지로 본다.
"""
import json
import os

import pytest

from .js_harness import requires_node, run_js

pytestmark = requires_node

_HTML = os.path.join(os.path.dirname(__file__), "..", "static", "produce.html")


def _fn(src, name):
    i = src.index("function %s(" % name)
    depth, j, started = 0, i, False
    while j < len(src):
        if src[j] == "{":
            depth += 1
            started = True
        elif src[j] == "}":
            depth -= 1
            if started and depth == 0:
                return src[i:j + 1]
        j += 1
    raise AssertionError("함수 끝을 못 찾음: %s" % name)


def _run(search, cur, call_ready):
    """?work= 유무와 단계 확정 여부를 바꿔가며 showPanel이 무엇을 켜는지 본다."""
    src = open(_HTML, encoding="utf-8").read()
    # showPanel은 단계별 초기화(refreshSub·loadTtsBeats…)를 부르므로 스텁을 깐다.
    harness = """
const _panels = [0,1,2,3].map(n => ({step:n, on:false,
  classList:{ toggle:function(c,v){ this._p.on = !!v; }, remove:function(){ this._p.on = false; } }}));
_panels.forEach(p => { p.classList._p = p; p.dataset = {step: String(p.step)}; });
let cur = %d;
const _btn = {disabled:false, textContent:''};
const document = {
  querySelectorAll: () => _panels,
  getElementById: () => _btn,
};
const location = { search: %s };
class URLSearchParams { constructor(s){ this.s = s || ''; }
  get(k){ const m = new RegExp('[?&]?' + k + '=([^&]*)').exec(this.s); return m ? m[1] : null; } }
function setTimeout(){}
function refreshNextBtn(){}  function refreshSub(){}   function loadTtsBeats(){}
function initHeadcopy(){}    function initThumb(){}    function initSeo(){}
function loadBuffer(){}      function orbIndex(){ return 0; }
const STEP_LABELS = ['a','b','c','d'];
%s
%s
%s
if (%s) markStepReady();
showPanel();
console.log(JSON.stringify({on: _panels.filter(p=>p.on).map(p=>p.step), ready: _stepReady}));
""" % (cur, json.dumps(search),
       # _stepReady 선언 + markStepReady + showPanel을 원본에서 그대로 떼어 온다
       src[src.index("let _stepReady = true;"):src.index("function markStepReady(")],
       _fn(src, "markStepReady"), _fn(src, "showPanel"),
       "true" if call_ready else "false")
    return json.loads(run_js(harness).strip().splitlines()[-1])


def test_work로_열면_단계를_알기_전엔_아무것도_안_그린다():
    """★깜빡임의 정체 — 여기서 1단계를 그리면 고객이 그걸 본다."""
    r = _run("?work=abc123", cur=0, call_ready=False)
    assert r["ready"] is False
    assert r["on"] == [], "단계를 알기 전에 패널을 그렸다 = 1단계가 번쩍인다"


def test_job으로_열어도_마찬가지():
    r = _run("?job=abc123", cur=0, call_ready=False)
    assert r["on"] == []


def test_단계가_정해지면_그_단계를_그린다():
    r = _run("?work=abc123", cur=2, call_ready=True)
    assert r["ready"] is True
    assert r["on"] == [2], "복원이 끝났는데 안 그리면 화면이 빈다"


def test_새_작업은_기다리지_않고_1단계를_바로_그린다():
    """?work=·?job= 없이 들어오면 1단계가 맞다 — 기다리면 괜히 느려 보인다."""
    r = _run("", cur=0, call_ready=False)
    assert r["ready"] is True
    assert r["on"] == [0]


def test_안전망_타이머가_걸려있다():
    """복원이 실패해도 2.5초 뒤엔 그린다 — 안 그러면 화면이 영영 빈다(깜빡임보다 나쁘다)."""
    src = open(_HTML, encoding="utf-8").read()
    assert "setTimeout(markStepReady, 2500)" in src


def test_호출부에_typeof_가드가_있다():
    """슬라이스 하네스는 함수 부분집합만 돌린다 — 맨몸으로 부르면 ReferenceError로 죽는다
    (실제로 이걸로 15건이 깨졌다)."""
    src = open(_HTML, encoding="utf-8").read()
    assert src.count("if(typeof markStepReady==='function') markStepReady();") == 3
    assert "\n  markStepReady();" not in src
