"""⭐ 내 프리셋 · 🧰 재료 탭 · 🖼 인트로 체크 기억 (2026-09-01 사장님 3건).

서버(설정 저장)와 화면(JS)을 각각 실제로 돌려 확인한다 — 문자열 검사만으로는
"저장은 되는데 적용이 안 된다"를 못 잡는다.
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

pytestmark = requires_node


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index("// ── 6단계 썸네일"):src.index("// ── 썸네일 끝")]


def test_스타일만_뽑는다_문구와_위치는_안_담는다():
    """프리셋에 문구·좌표가 섞이면 남의 썸네일 글자가 튀어나온다."""
    out = run_js(_slice() + """
console.log(JSON.stringify(thumbLayerStyle({
  text:'진짜 이거 대박', font:'BMJUA.ttf', size:80, color:'#fff', color2:'#FFD400',
  outline:{color:'#000',w:12}, box:null, x:0.3, y:0.7, rot:5, fx:'underline'})));
""")
    st = json.loads(out)
    assert st["font"] == "BMJUA.ttf" and st["color2"] == "#FFD400"
    assert st["outline"]["w"] == 12
    for k in ("text", "x", "y", "rot", "fx"):
        assert k not in st, f"{k}는 프리셋에 담기면 안 된다"


def test_내_프리셋_적용은_문구와_위치를_지키지_않는다():
    """색·폰트만 바뀌고 사장님이 잡은 문구·자리는 그대로여야 한다."""
    out = run_js(_slice() + """
THUMB_STATE.sel = 0;            // const라 통째로 바꿀 수 없다 — 안을 갈아끼운다
THUMB_STATE.layers = [{kind:'text', text:'원래 문구', font:'A.ttf', size:50,
  color:'#000', x:0.31, y:0.72, rot:7}];
MY_THUMB_PRESETS = [{name:'내꺼', style:{font:'BMJUA.ttf', size:90, color:'#fff',
  color2:'#FFD400', outline:{color:'#000',w:10}, box:null}}];
renderThumbLayers = function(){}; renderThumbCanvas = function(){};
applyMyThumbPreset(0);
console.log(JSON.stringify(THUMB_STATE.layers[0]));
""")
    L = json.loads(out)
    assert L["font"] == "BMJUA.ttf" and L["size"] == 90 and L["color2"] == "#FFD400"
    assert L["text"] == "원래 문구"
    assert L["x"] == 0.31 and L["y"] == 0.72 and L["rot"] == 7


def test_스티커_도형_배지엔_글자스타일을_얹지_않는다():
    """기존 색 프리셋과 같은 경계 — 얹으면 스티커가 빈 글자로 바뀌어 사라진다."""
    out = run_js(_slice() + """
THUMB_STATE.sel = 0;
THUMB_STATE.layers = [{kind:'sticker', text:'🔥', size:120}];
MY_THUMB_PRESETS = [{name:'내꺼', style:{font:'BMJUA.ttf', size:90, color:'#fff'}}];
renderThumbLayers = function(){}; renderThumbCanvas = function(){};
applyMyThumbPreset(0);
console.log(JSON.stringify(THUMB_STATE.layers[0]));
""")
    L = json.loads(out)
    assert L["kind"] == "sticker" and L["size"] == 120 and "font" not in L


def test_재료탭은_한_번에_하나만_보인다():
    out = run_js(_slice() + """
var panes = {sticker:{hidden:false}, shape:{hidden:false}, badge:{hidden:false}};
var document = { getElementById: function(id){
  var m = /^thKit_(\w+)$/.exec(id); if (m) return panes[m[1]];
  return null;   // 탭 버튼은 없다(하네스) — 그래도 죽지 않아야 한다
}};
showThumbKit('badge');
console.log(JSON.stringify({s:panes.sticker.hidden, h:panes.shape.hidden, b:panes.badge.hidden}));
""")
    r = json.loads(out)
    assert r == {"s": True, "h": True, "b": False}


def test_모르는_탭_이름은_무시한다():
    out = run_js(_slice() + """
var panes = {sticker:{hidden:false}, shape:{hidden:true}, badge:{hidden:true}};
var document = { getElementById: function(id){
  var m = /^thKit_(\w+)$/.exec(id); return m ? panes[m[1]] : null; }};
showThumbKit('없는탭');
console.log(JSON.stringify({s:panes.sticker.hidden}));
""")
    assert json.loads(out)["s"] is False       # 아무것도 안 건드린다


# ── 서버: 개인 기본값·내 프리셋 저장 ────────────────────────────────────────
def test_설정_키는_고객마다_다르다():
    from shopping_shorts import app as A
    assert A._thumb_presets_key(7) != A._thumb_presets_key(8)
    assert A._thumb_intro_key(7) != A._thumb_intro_key(8)


def test_깨진_값이_와도_빈_목록으로_넘어간다(monkeypatch):
    """설정값이 깨져도 편집 화면이 통째로 막히면 안 된다."""
    from shopping_shorts import app as A

    class _S:
        def get_setting(self, k, d=None):
            return "{이건 JSON이 아니다"

    monkeypatch.setattr(A, "Store", lambda *_a, **_k: _S())
    assert A._load_my_thumb_presets(1) == []
