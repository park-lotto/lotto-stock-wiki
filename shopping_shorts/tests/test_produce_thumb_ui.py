"""썸네일 화면 JS — produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다
(test_produce_preview_gate.py와 같은 방식. 재구현이 아니다).

비율 좌표(0~1)가 이 화면의 핵심 계약이다: 프리뷰가 270px든 결과가 1080px든
같은 자리에 찍혀야 한다. 그 계약을 여기서 잠근다.
"""
import json
import pathlib
import shutil
import subprocess

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
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True,
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


def test_draw_scales_font_size_with_canvas():
    """size는 1080 기준 px — 270px 캔버스에선 1/4로 줄어야 한다."""
    script = _slice_source() + """
function fontAt(W){
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
  return seen;
}
console.log(JSON.stringify({big: fontAt(1080), small: fontAt(270)}));
"""
    out = json.loads(_run_node(script))
    assert "100px" in out["big"]
    assert "25px" in out["small"]


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


def test_draw_scales_box_padding_with_canvas():
    """박스 padding도 좌표·폰트와 같은 배율(s)을 타야 한다 —
    안 타면 270px 프리뷰의 박스 여백이 1080px 결과와 다른 비율로 보인다."""
    script = _slice_source() + """
function padAt(W){
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
  // size:0 → fillRect의 4번째 인자(height)는 pad*1.2만 남는다 (pad를 순수 격리)
  drawThumb(ctx, {width:W, height:W*16/9}, [{text:'A', font:'BMJUA.ttf', size:0,
    color:'#fff', outline:null, box:{color:'#000', pad:16, opacity:80}, rot:0, x:0.5, y:0.25}], W, W*16/9);
  const height = calls[0][3];
  return height / 1.2;
}
console.log(JSON.stringify({big: padAt(1080), small: padAt(270)}));
"""
    out = json.loads(_run_node(script))
    assert out["small"] == pytest.approx(out["big"] / 4)


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
