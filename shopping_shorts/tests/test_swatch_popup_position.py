"""색 팔레트 첫 배치 사고(2026-08-28 사장님 제보) — 회귀 잠금.

## 무엇이 문제였나

`_swOpen`이 `_swReposition()`을 부르는 시점에 **`_swPop` 대입이 아직**이었다
(대입이 리스너 배선 뒤에 있었다). `_swReposition` 첫 줄 가드(`!_swPop`)에 걸려
**처음 열릴 때 배치가 통째로 안 됐고**, 팝업은 CSS 기본 fixed 자리 =
화면 왼쪽 상단 (0,0)에 떴다. 스크롤 이벤트가 와야 그제서야 제자리로 갔다
(실브라우저 실측: 클릭 직후 rect(0,0) → scroll 후 (843,424)).

## 이 테스트가 지키는 것 (텍스트 검사 아님 — 실제로 돌린다)

① 열리는 **그 순간** left/top이 단추 rect 기준으로 박힌다
② 단추가 숨어 rect가 전부 0이면 (0,0)으로 배치하지 말고 **닫는다**
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import run_js, requires_node

pytestmark = requires_node

HTML = pathlib.Path(__file__).resolve().parents[1].joinpath(
    "static", "produce.html").read_text(encoding="utf-8")


def _slice(start_marker, end_marker):
    i = HTML.index(start_marker)
    j = HTML.index(end_marker, i + len(start_marker))
    return HTML[i:j]


def _harness(script):
    src = _slice("const SW_COLORS = [", "let MIX_JOB=null")
    return r"""
// ── 최소 DOM 흉내 ──────────────────────────────────────────────
function mkEl(){
  return {
    className:'', innerHTML:'', dataset:{}, style:{},
    offsetWidth:274, offsetHeight:236,
    _rect:{left:0,top:0,right:0,bottom:0,width:0,height:0},
    getBoundingClientRect(){ return this._rect; },
    addEventListener(){}, remove(){ this._removed = true; },
    appendChild(){}, closest(){ return null; },
  };
}
const BODY = { appendChild(el){ this.last = el; } };
const document = {
  body: BODY, readyState: 'complete',
  createElement(){ return mkEl(); },
  addEventListener(){}, querySelectorAll(){ return []; },
  documentElement: {},
};
function addEventListener(){}
const innerWidth = 1534, innerHeight = 814;
function MutationObserver(){ return {observe(){}}; }
""" + src + "\n" + script


def _run(script):
    out = run_js(_harness(script))
    return json.loads(out.strip().splitlines()[-1])


def test_popup_is_positioned_at_open_time():
    """열리는 순간(스크롤 없이) 단추 아래로 배치돼야 한다 — 안 되면 (0,0)에 뜬다."""
    r = _run(r"""
const input = mkEl();
const btn = mkEl();
btn._rect = {left:843, top:396, right:865, bottom:418, width:22, height:22};
_swOpen(input, btn);
console.log(JSON.stringify({left:_swPop.style.left, top:_swPop.style.top}));
""")
    assert r["left"] == "843px", f"열릴 때 left가 안 잡혔다: {r}"
    assert r["top"] == "424px", f"열릴 때 top이 안 잡혔다: {r}"    # bottom 418 + 6


def test_hidden_button_closes_instead_of_parking_topleft():
    """단추 rect가 전부 0(패널 전환·분리)이면 닫는다 — (8,6)에 세워두면 같은 증상 2호."""
    r = _run(r"""
const input = mkEl();
const btn = mkEl();
btn._rect = {left:843, top:396, right:865, bottom:418, width:22, height:22};
_swOpen(input, btn);
btn._rect = {left:0, top:0, right:0, bottom:0, width:0, height:0};   // 숨김
_swReposition();
console.log(JSON.stringify({closed: _swPop === null}));
""")
    assert r["closed"] is True, "숨은 단추인데 팝업이 안 닫혔다(왼쪽 상단으로 도망간다)"
