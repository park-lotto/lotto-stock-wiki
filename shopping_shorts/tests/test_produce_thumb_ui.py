"""썸네일 화면 JS — produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다
(test_produce_preview_gate.py와 같은 방식. 재구현이 아니다).

비율 좌표(0~1)가 이 화면의 핵심 계약이다: 프리뷰가 270px든 결과가 1080px든
같은 자리에 찍혀야 한다. 그 계약을 여기서 잠근다.
"""
import json
import pathlib
import shutil
import subprocess
import tempfile

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_START = "// ── 6단계 썸네일"
_END = "// ── 썸네일 끝"


def _slice_source():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i, j = src.index(_START), src.index(_END)
    return src[i:j]


def _run_node(script):
    """★스크립트를 임시파일로 실행한다 — `node -e <script>`로 넘기면 안 된다.
    윈도우 CreateProcess 명령줄 상한이 32,767자인데 이 슬라이스만 이미 31KB라, 화면에 몇 줄만
    더해도 WinError 206으로 죽는다(2026-07-29·08-18 두 번 재발한 시한폭탄). 파일 실행엔 상한이 없다.
    확장자는 .js — .mjs로 두면 ESM 모드가 돼 슬라이스의 최상위 코드가 다르게 해석된다."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "harness.js"
        p.write_text(script, encoding="utf-8")
        # encoding 명시 필수 — 안 주면 윈도우가 cp949로 읽어 한글 오류 메시지에서 죽고,
        # 진짜 실패 원인이 UnicodeDecodeError에 가려진다.
        r = subprocess.run([NODE, str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def test_preset_maps_to_layer_with_ratio_coords():
    script = _slice_source() + """
const layer = thumbPresetToLayer({name:'옐로 팝', font:'BMJUA.ttf', color:'#FFE100',
  size:76, y:12, outline:true, outline_color:'#000000', outline_w:9});
console.log(JSON.stringify(layer));
"""
    layer = json.loads(_run_node(script))
    assert layer["font"] == "BMJUA.ttf"
    assert layer["size"] == 76
    assert layer["color"] == "#FFE100"
    assert layer["y"] == pytest.approx(0.12)   # 프리셋 y(%) → 비율
    assert 0 <= layer["x"] <= 1
    assert layer["outline"]["w"] == 9


def test_draw_uses_ratio_coords_scaled_to_canvas():
    """x=0.5,y=0.25 → 1080x1920에서 (540, 480)에 찍힌다."""
    script = _slice_source() + """
const calls = [];
const ctx = new Proxy({}, {
  get(t, k){
    if (k === 'measureText') return () => ({width: 100});
    if (k === 'save' || k === 'restore' || k === 'translate' || k === 'rotate' ||
        k === 'drawImage' || k === 'strokeText' || k === 'fillRect' || k === 'beginPath' || k === 'clearRect')
      return (...a) => calls.push([k, ...a]);
    if (k === 'fillText') return (...a) => calls.push(['fillText', ...a]);
    return undefined;
  },
  set(){ return true; }
});
drawThumb(ctx, {width:1080, height:1920}, [{text:'A', font:'BMJUA.ttf', size:100,
  color:'#fff', outline:null, box:null, rot:0, x:0.5, y:0.25}], 1080, 1920);
console.log(JSON.stringify(calls.filter(c => c[0]==='translate')));
"""
    calls = json.loads(_run_node(script))
    assert calls, "translate가 안 불렸다 — 좌표 배선이 없다"
    x, y = calls[0][1], calls[0][2]
    assert x == pytest.approx(540)
    assert y == pytest.approx(480)


def test_draw_scales_identically_at_preview_size():
    """같은 레이어를 270x480으로 그리면 좌표가 정확히 1/4 — 비율 계약."""
    script = _slice_source() + """
function trace(W, H){
  const calls = [];
  const ctx = new Proxy({}, {
    get(t, k){
      if (k === 'measureText') return () => ({width: 100});
      if (k === 'translate') return (...a) => calls.push(a);
      if (['save','restore','rotate','drawImage','strokeText','fillText','fillRect','beginPath','clearRect'].includes(k))
        return () => {};
      return undefined;
    }, set(){ return true; }
  });
  drawThumb(ctx, {width:W, height:H}, [{text:'A', font:'BMJUA.ttf', size:100,
    color:'#fff', outline:null, box:null, rot:0, x:0.5, y:0.25}], W, H);
  return calls[0];
}
console.log(JSON.stringify({big: trace(1080,1920), small: trace(270,480)}));
"""
    out = json.loads(_run_node(script))
    assert out["small"][0] == pytest.approx(out["big"][0] / 4)
    assert out["small"][1] == pytest.approx(out["big"][1] / 4)


# ── ✨ 강조 효과(밑줄·형광펜·네온) ────────────────────────────────
# 최종 PNG를 캔버스가 그리므로, 여기서 통과하는 그림이 곧 결과물이다.

_TRACE = """
function trace(fx){
  const calls = [];
  const ctx = new Proxy({}, {
    get(t, k){
      if (k === 'measureText') return () => ({width: 100});
      if (['save','restore','translate','rotate','drawImage','strokeText','fillText',
           'fillRect','beginPath','moveTo','lineTo','stroke','quadraticCurveTo','clearRect'].includes(k))
        return (...a) => calls.push([k, ...a]);
      return undefined;
    }, set(t, k, v){ calls.push(['set:' + k, v]); return true; }
  });
  drawThumb(ctx, {width:1080, height:1920}, [{text:'AB', font:'BMJUA.ttf', size:100,
    color:'#fff', outline:null, box:null, rot:0, x:0.5, y:0.5, fx}], 1080, 1920);
  return calls;
}
"""


def _trace(fx_js):
    return json.loads(_run_node(
        _slice_source() + _TRACE + f"console.log(JSON.stringify(trace({fx_js})));"))


def test_no_fx_draws_nothing_extra():
    """효과가 없으면(구 저장본·구 레이어) 종전 그림 그대로 — 회귀 0."""
    for fx in ("null", "undefined"):
        names = [c[0] for c in _trace(fx)]
        assert "stroke" not in names, "효과가 없는데 획을 그었다"
        assert "fillRect" not in names, "효과가 없는데 형광펜을 깔았다"


def test_underline_draws_a_stroke_below_text():
    calls = _trace("{underline:'line', underline_color:'#FF0000'}")
    assert "stroke" in [c[0] for c in calls], "밑줄이 안 그어졌다"
    ys = [c[2] for c in calls if c[0] == "moveTo"]
    assert ys and all(y > 0 for y in ys), "밑줄이 글자 아래(양수 y)가 아니다"
    assert ["set:strokeStyle", "#FF0000"] in calls, "밑줄 색이 안 먹었다"


def test_brush_underline_uses_a_curve():
    """붓 밑줄은 곡선이라 직선(lineTo)이 아니라 quadraticCurveTo를 쓴다."""
    names = [c[0] for c in _trace("{underline:'brush'}")]
    assert "quadraticCurveTo" in names
    assert "lineTo" not in names


def test_marker_is_drawn_behind_text():
    """형광펜이 글자 뒤에 깔려야 글자를 안 덮는다 — fillRect가 fillText보다 먼저."""
    calls = _trace("{marker:{color:'#FFE100'}}")
    names = [c[0] for c in calls]
    assert "fillRect" in names, "형광펜이 안 깔렸다"
    assert names.index("fillRect") < names.index("fillText")
    assert ["set:globalCompositeOperation", "multiply"] in calls, "곱하기 합성이 아니면 글자를 덮는다"


def test_underline_moves_below_marker_band():
    """형광펜과 같이 켜면 밑줄이 띠 아래로 내려가야 보인다.
    (실측 사고: 띠가 y+0.06~+0.58을 덮는데 밑줄이 +0.46이라 띠 안에 그어져 묻혔다)"""
    band_bottom = 0.06 + 0.52          # _fxMarker의 띠 하단(글자 크기 대비 비율)
    alone = [c[2] for c in _trace("{underline:'line'}") if c[0] == "moveTo"][0]
    withm = [c[2] for c in _trace("{underline:'line', marker:{color:'#FFE100'}}")
             if c[0] == "moveTo"][0]
    assert withm > alone, "형광펜을 켜도 밑줄이 안 내려갔다"
    assert withm >= 100 * band_bottom, "밑줄이 아직 형광펜 띠 안에 있다(size=100 기준)"


def test_glow_sets_colored_shadow():
    calls = _trace("{glow:{color:'#2EE6C5'}}")
    assert ["set:shadowColor", "#2EE6C5"] in calls, "네온 색이 안 먹었다"
    assert len([c for c in calls if c[0] == "fillText"]) > 1, "겹쳐 그리지 않으면 안 빛난다"


def test_fx_survives_preset_change():
    """색 프리셋을 바꿔도 밑줄·형광펜이 사라지면 안 된다(사장님이 준 설정이 우선)."""
    # HC_PRESETS는 슬라이스 밖(자막 꾸미기 쪽)에 선언돼 있다 — 하네스엔 최소 1종만 심는다.
    script = _slice_source() + """
var HC_PRESETS = [{cat:'썸네일', name:'흰→노랑', font:'BMDOHYEON.ttf', color:'#FFFFFF',
                   color2:'#FFD400', size:92, y:14, outline:true, outline_color:'#000000', outline_w:12}];
THUMB_STATE.layers = [{text:'A', font:'BMJUA.ttf', size:76, color:'#fff', outline:null,
                       box:null, rot:0, x:0.4, y:0.7, fx:{underline:'brush'}}];
THUMB_STATE.sel = 0;
renderThumbLayers = () => {}; renderThumbCanvas = () => {};
applyThumbPreset(0);
console.log(JSON.stringify(THUMB_STATE.layers[0].fx));
"""
    assert json.loads(_run_node(script)) == {"underline": "brush"}


def test_toggle_turns_fx_on_and_off():
    """딸깍 = 켜기, 다시 딸깍 = 끄기. 밑줄과 붓밑줄은 서로 배타."""
    script = _slice_source() + """
THUMB_STATE.layers = [{text:'A', font:'BMJUA.ttf', size:76, color:'#fff', outline:null,
                       box:null, rot:0, x:0.5, y:0.5}];
THUMB_STATE.sel = 0;
renderThumbLayers = () => {}; renderThumbCanvas = () => {};
const out = {};
toggleThumbFx(0); out.on = THUMB_STATE.layers[0].fx.underline;
toggleThumbFx(0); out.off = THUMB_STATE.layers[0].fx.underline;
toggleThumbFx(0); toggleThumbFx(1); out.exclusive = THUMB_STATE.layers[0].fx.underline;
toggleThumbFx(2); out.marker = !!THUMB_STATE.layers[0].fx.marker;
toggleThumbFx(2); out.marker_off = THUMB_STATE.layers[0].fx.marker;
console.log(JSON.stringify(out));
"""
    out = json.loads(_run_node(script))
    assert out["on"] == "line"
    assert out["off"] == "none"
    assert out["exclusive"] == "brush", "붓밑줄을 켜면 일반 밑줄은 꺼져야 한다"
    assert out["marker"] is True
    assert out["marker_off"] is None


def test_draw_font_size_scales_with_canvas_ratio():
    """grow-to-fill: 크기는 절대 px이 아니라 캔버스 폭에 비례한다 — 270px 캔버스는 1080px의 1/4.
    (프리뷰 270 == 결과 1080이 같은 비율이라는 핵심 계약. 절대값이 아니라 4배 관계를 잠근다.)"""
    script = _slice_source() + r"""
function fontPxAt(W){
  let seen = null;
  const ctx = new Proxy({}, {
    get(t, k){
      if (k === 'measureText') return () => ({width: 100});
      if (['save','restore','rotate','translate','drawImage','strokeText','fillText','fillRect','beginPath','clearRect'].includes(k))
        return () => {};
      return undefined;
    },
    set(t, k, v){ if (k === 'font') seen = v; return true; }
  });
  drawThumb(ctx, {width:W, height:W*16/9}, [{text:'A', font:'BMJUA.ttf', size:100,
    color:'#fff', outline:null, box:null, rot:0, x:0.5, y:0.25}], W, W*16/9);
  return parseFloat(/(\d+(?:\.\d+)?)px/.exec(seen)[1]);
}
console.log(JSON.stringify({big: fontPxAt(1080), small: fontPxAt(270)}));
"""
    out = json.loads(_run_node(script))
    assert out["big"] > 0 and out["small"] > 0
    assert out["small"] == pytest.approx(out["big"] / 4, rel=1e-3)


def test_draw_applies_rotation():
    script = _slice_source() + """
const calls = [];
const ctx = new Proxy({}, {
  get(t, k){
    if (k === 'measureText') return () => ({width: 100});
    if (k === 'rotate') return (...a) => calls.push(a);
    if (['save','restore','translate','drawImage','strokeText','fillText','fillRect','beginPath','clearRect'].includes(k))
      return () => {};
    return undefined;
  }, set(){ return true; }
});
drawThumb(ctx, {width:1080, height:1920}, [{text:'A', font:'BMJUA.ttf', size:100,
  color:'#fff', outline:null, box:null, rot:90, x:0.5, y:0.25}], 1080, 1920);
console.log(JSON.stringify(calls));
"""
    calls = json.loads(_run_node(script))
    assert calls, "회전이 배선되지 않았다 — drawtext 대신 canvas를 고른 이유가 이것이다"
    assert calls[0][0] == pytest.approx(3.14159265 / 2, rel=1e-4)


def test_draw_renders_every_layer():
    script = _slice_source() + """
let n = 0;
const ctx = new Proxy({}, {
  get(t, k){
    if (k === 'measureText') return () => ({width: 100});
    if (k === 'fillText') return () => { n++; };
    if (['save','restore','rotate','translate','drawImage','strokeText','fillRect','beginPath','clearRect'].includes(k))
      return () => {};
    return undefined;
  }, set(){ return true; }
});
const L = t => ({text:t, font:'BMJUA.ttf', size:100, color:'#fff', outline:null,
                 box:null, rot:0, x:0.5, y:0.25});
drawThumb(ctx, {width:1080, height:1920}, [L('A'), L('B'), L('C')], 1080, 1920);
console.log(n);
"""
    assert int(_run_node(script).strip()) == 3


def test_draw_scales_box_with_canvas_ratio():
    """박스(fillRect)도 좌표·폰트와 같은 캔버스 배율을 타야 한다 — 270px 프리뷰의 박스가
    1080px 결과와 같은 비율이어야 한다. 크기·여백 모두 폭에 비례하므로 박스 높이는 정확히 1/4."""
    script = _slice_source() + """
function boxHeightAt(W){
  const calls = [];
  const ctx = new Proxy({}, {
    get(t, k){
      if (k === 'measureText') return () => ({width: 100});
      if (k === 'fillRect') return (...a) => calls.push(a);
      if (['save','restore','rotate','translate','drawImage','strokeText','fillText','beginPath','clearRect'].includes(k))
        return () => {};
      return undefined;
    }, set(){ return true; }
  });
  drawThumb(ctx, {width:W, height:W*16/9}, [{text:'A', font:'BMJUA.ttf', size:90,
    color:'#fff', outline:null, box:{color:'#000', pad:16, opacity:80}, rot:0, x:0.5, y:0.25}], W, W*16/9);
  return calls[0][3];   // fillRect height (size + pad*1.2), 둘 다 폭에 비례
}
console.log(JSON.stringify({big: boxHeightAt(1080), small: boxHeightAt(270)}));
"""
    out = json.loads(_run_node(script))
    assert out["big"] > 0 and out["small"] > 0
    assert out["small"] == pytest.approx(out["big"] / 4, rel=1e-3)


def test_draw_scales_outline_width_with_canvas():
    """외곽선 두께(lineWidth)도 배율(s)을 타야 한다 —
    안 타면 270px 프리뷰는 얇은 테두리, 1080px 결과는 두꺼운 테두리로 다르게 보인다."""
    script = _slice_source() + """
function lineWidthAt(W){
  let seen = null;
  const ctx = new Proxy({}, {
    get(t, k){
      if (k === 'measureText') return () => ({width: 100});
      if (['save','restore','rotate','translate','drawImage','strokeText','fillText','fillRect','beginPath','clearRect'].includes(k))
        return () => {};
      return undefined;
    },
    set(t, k, v){ if (k === 'lineWidth') seen = v; return true; }
  });
  drawThumb(ctx, {width:W, height:W*16/9}, [{text:'A', font:'BMJUA.ttf', size:100,
    color:'#fff', outline:{color:'#000', w:9}, box:null, rot:0, x:0.5, y:0.25}], W, W*16/9);
  return seen;
}
console.log(JSON.stringify({big: lineWidthAt(1080), small: lineWidthAt(270)}));
"""
    out = json.loads(_run_node(script))
    assert out["small"] == pytest.approx(out["big"] / 4)


def test_draw_uses_color2_for_second_line():
    """2색 룩: color2가 있으면 1줄=color, 2줄부터=color2로 그린다(레퍼런스 흰→노랑)."""
    script = _slice_source() + r"""
const log = [];
const ctx = {
  fillStyle: '', font: '',
  measureText(){ return {width: 100}; },
  save(){}, restore(){}, translate(){}, rotate(){}, drawImage(){},
  clearRect(){}, fillRect(){}, beginPath(){}, strokeText(){},
  fillText(t){ log.push(this.fillStyle); },
};
drawThumb(ctx, {width:1080, height:1920}, [{text:'A\nB', font:'X.ttf', size:80,
  color:'#ffffff', color2:'#ffe100', outline:null, box:null, rot:0, x:0.5, y:0.14}], 1080, 1920);
console.log(JSON.stringify(log));
"""
    out = json.loads(_run_node(script))
    assert out == ["#ffffff", "#ffe100"], "1줄은 color, 2줄은 color2여야 한다"


def test_apply_title_sets_selected_layer_text():
    """AI 추천 제목을 누르면(applyThumbTitle) 선택된 레이어의 text가 그 문구로 바뀐다 —
    줄바꿈(\\n)까지 그대로. renderThumbLayers/Canvas가 화면 갱신을 하도록 외부 의존은 스텁."""
    script = _slice_source() + r"""
globalThis.HC_PRESETS = []; globalThis.HC_FONTS = []; globalThis.esc = s => s;
globalThis.window = {};
globalThis.document = { getElementById: (id) =>
  id === 'thumbCanvas' ? null : { set innerHTML(v){}, get innerHTML(){ return ''; } } };
THUMB_STATE.layers = [{text:'옛문구', font:'X.ttf', size:78, color:'#fff',
                       outline:null, box:null, rot:0, x:0.5, y:0.16}];
THUMB_STATE.sel = 0;
const WANT = '밥솥 빵\n미쳤다';
THUMB_STATE.title_cands = [{text: WANT, why:'반전'}];
applyThumbTitle(0);
const got = THUMB_STATE.layers[0].text;
// stdout은 ASCII만(Windows cp949 디코딩 회피) — 비교는 node 안에서 끝낸다
console.log(JSON.stringify({match: got === WANT, hasNewline: got.includes('\n'), len: got.length}));
"""
    out = json.loads(_run_node(script))
    assert out["match"], "추천 제목이 레이어 text로 안 들어갔다"
    assert out["hasNewline"], "줄바꿈(\\n)이 보존되지 않았다"
    assert out["len"] == 8   # 밥·솥·공백·빵·\n·미·쳤·다 = 8자


def test_draw_restores_rotation_between_layers():
    """save/restore가 1:1로 맞아야 한다 — 하나라도 빠지면 앞 레이어의 회전이
    다음 레이어로 새어나간다. rot:90 레이어 다음 rot:0 레이어의 실효 회전은 0이어야 한다.

    기존 Proxy mock은 상태가 없어 이 누수를 관측 못 한다 — 여기선 회전 스택을
    실제로 들고 있는 가짜 ctx로 save=push/restore=pop을 흉내낸다."""
    script = _slice_source() + """
class FakeCtx {
  constructor(){ this._rot = 0; this._stack = []; this.log = []; }
  save(){ this._stack.push(this._rot); }
  restore(){ if (this._stack.length) this._rot = this._stack.pop(); }
  rotate(a){ this._rot += a; }
  translate(){}
  measureText(){ return {width: 100}; }
  clearRect(){}
  drawImage(){}
  strokeText(){}
  fillRect(){}
  beginPath(){}
  fillText(){ this.log.push(this._rot); }
}
const ctx = new FakeCtx();
const L = (rot) => ({text:'A', font:'BMJUA.ttf', size:100, color:'#fff', outline:null,
                     box:null, rot, x:0.5, y:0.25});
drawThumb(ctx, {width:1080, height:1920}, [L(90), L(0)], 1080, 1920);
console.log(JSON.stringify(ctx.log));
"""
    log = json.loads(_run_node(script))
    assert log[0] == pytest.approx(3.14159265 / 2, rel=1e-4)
    assert log[1] == pytest.approx(0, abs=1e-6), \
        "회전이 앞 레이어에서 새어나왔다 — save/restore 짝이 안 맞는다"
