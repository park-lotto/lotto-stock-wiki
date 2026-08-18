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
      // 그라데이션은 도형이 쓴다 — 스텁이 없으면 '색이 안 먹는다'가 아니라 통째로 죽는다.
      if (k === 'createLinearGradient') return () => ({addColorStop(){}});
      if (['save','restore','translate','rotate','drawImage','strokeText','fillText',
           'fillRect','beginPath','moveTo','lineTo','stroke','quadraticCurveTo','clearRect',
           'fill','closePath','arc','arcTo','ellipse','bezierCurveTo'].includes(k))
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


# ── 😀 이모지 스티커 레이어 ────────────────────────────────

def _sticker_trace(layers_js):
    script = _slice_source() + """
function trace(layers){
  const calls = [];
  const ctx = new Proxy({}, {
    get(t, k){
      if (k === 'measureText') return () => ({width: 100});
      // 도형은 그라데이션을 쓴다 — 스텁이 없으면 '색이 안 먹는다'가 아니라 통째로 죽는다.
      if (k === 'createLinearGradient') return () => ({addColorStop(){}});
      if (['save','restore','translate','rotate','drawImage','strokeText','fillText',
           'fillRect','beginPath','moveTo','lineTo','stroke','quadraticCurveTo','clearRect',
           'fill','closePath','arc','arcTo','ellipse','bezierCurveTo'].includes(k))
        return (...a) => calls.push([k, ...a]);
      return undefined;
    }, set(t, k, v){ calls.push(['set:' + k, v]); return true; }
  });
  drawThumb(ctx, null, layers, 1080, 1920);
  return calls;
}
console.log(JSON.stringify(trace(%s)));
""" % layers_js
    return json.loads(_run_node(script))


def test_sticker_draws_emoji_at_ratio_position():
    """스티커도 비율 좌표 계약을 따른다 — x=0.25,y=0.75 → (270, 1440)."""
    calls = _sticker_trace(
        "[{kind:'sticker', emoji:'🔥', size:20, x:0.25, y:0.75, rot:0}]")
    tr = [c for c in calls if c[0] == "translate"]
    assert tr, "스티커가 안 그려졌다"
    assert tr[0][1] == pytest.approx(270)
    assert tr[0][2] == pytest.approx(1440)
    assert ["fillText", "🔥", 0, 0] in calls


def test_sticker_size_is_percent_of_width():
    """size=20 → 캔버스 폭의 20%(1080*0.2=216px). 프리뷰든 결과든 같은 비율."""
    calls = _sticker_trace("[{kind:'sticker', emoji:'⭐', size:20, x:0.5, y:0.5, rot:0}]")
    font = [c[1] for c in calls if c[0] == "set:font"][0]
    assert font.startswith("216px"), font


def test_sticker_skips_text_pipeline():
    """★스티커는 자동 줄나눔·폭맞춤을 타면 안 된다(글자 레이어에 이모지를 넣으면 공백에서
    줄이 쪼개져 흩어진다 — 그래서 레이어를 나눈 것). 외곽선·형광펜도 안 그린다."""
    calls = _sticker_trace("[{kind:'sticker', emoji:'😱', size:18, x:0.5, y:0.5, rot:0}]")
    names = [c[0] for c in calls]
    assert "strokeText" not in names, "컬러 이모지엔 외곽선이 안 먹는데 그렸다"
    assert len([c for c in calls if c[0] == "fillText"]) == 1, "한 번만 그려야 한다"


def test_empty_sticker_draws_nothing():
    calls = _sticker_trace("[{kind:'sticker', emoji:'', size:18, x:0.5, y:0.5, rot:0}]")
    assert not [c for c in calls if c[0] == "fillText"]


def test_sticker_and_text_layers_coexist():
    """글자 레이어와 스티커가 한 캔버스에 같이 그려진다(실사용 모양)."""
    calls = _sticker_trace(
        "[{text:'대박', font:'BMJUA.ttf', size:100, color:'#fff', outline:null, box:null,"
        " rot:0, x:0.5, y:0.3},"
        " {kind:'sticker', emoji:'🔥', size:18, x:0.2, y:0.8, rot:-15}]")
    drawn = [c[1] for c in calls if c[0] == "fillText"]
    assert "대박" in drawn and "🔥" in drawn


def test_add_sticker_appends_selected_layer():
    script = _slice_source() + """
THUMB_STATE.layers = []; THUMB_STATE.sel = 0;
renderThumbLayers = () => {}; renderThumbCanvas = () => {};
addThumbSticker('🔥');
console.log(JSON.stringify({n: THUMB_STATE.layers.length, sel: THUMB_STATE.sel,
                            L: THUMB_STATE.layers[0]}));
"""
    out = json.loads(_run_node(script))
    assert out["n"] == 1
    assert out["sel"] == 0, "새로 얹은 스티커가 선택돼야 바로 크기·위치를 조절한다"
    assert out["L"]["kind"] == "sticker" and out["L"]["emoji"] == "🔥"
    assert 0 <= out["L"]["x"] <= 1 and 0 <= out["L"]["y"] <= 1


_STICKER_SEL = """
var HC_PRESETS = [{cat:'썸네일', name:'흰→노랑', font:'BMDOHYEON.ttf', color:'#FFFFFF',
                   color2:'#FFD400', size:92, y:14, outline:true, outline_color:'#000000', outline_w:12}];
renderThumbLayers = () => {}; renderThumbCanvas = () => {};
"""


# ── 🎨 고급 도형 스티커(곡선 화살표 등) ────────────────────────────────

def test_every_listed_shape_has_a_drawer():
    """목록에 있는데 그리는 함수가 없으면 눌러도 아무 일도 안 난다(조용한 실패)."""
    out = json.loads(_run_node(_slice_source() + """
console.log(JSON.stringify({list: THUMB_SHAPE_LIST.map(s => s.key),
                            drawers: Object.keys(THUMB_SHAPES)}));"""))
    missing = [k for k in out["list"] if k not in out["drawers"]]
    assert not missing, f"그리는 함수가 없는 도형: {missing}"


def test_shape_draws_and_respects_ratio_position():
    calls = _sticker_trace(
        "[{kind:'shape', shape:'arrow_curve', size:20, x:0.25, y:0.75, rot:0, color:'#FF3B30'}]")
    tr = [c for c in calls if c[0] == "translate"]
    assert tr, "도형이 안 그려졌다"
    assert tr[0][1] == pytest.approx(270)
    assert tr[0][2] == pytest.approx(1440)


def test_curved_arrow_head_follows_curve_end():
    """★촉을 곡선 끝의 접선에 맞춰 붙인다 — 손으로 좌표를 찍으면 촉이 몸통에서 떨어져
    엉뚱한 곳을 가리킨다(실측으로 한 번 그렇게 나왔다)."""
    calls = _sticker_trace(
        "[{kind:'shape', shape:'arrow_curve', size:20, x:0.5, y:0.5, rot:0, color:'#FF3B30'}]")
    names = [c[0] for c in calls]
    assert "quadraticCurveTo" in names, "곡선이 아니다"
    # 곡선을 그은 뒤 촉을 붙이려면 끝점으로 translate + 접선만큼 rotate 해야 한다
    assert names.count("translate") >= 2, "촉을 곡선 끝으로 옮기지 않았다"
    assert "rotate" in names, "촉을 접선 방향으로 돌리지 않았다"


def test_shape_color_is_applied():
    """도형은 이모지와 달리 색이 먹어야 한다(벡터로 직접 그리므로)."""
    calls = _sticker_trace(
        "[{kind:'shape', shape:'check', size:20, x:0.5, y:0.5, rot:0, color:'#2FD873'}]")
    assert any(c[0] in ("set:strokeStyle", "set:fillStyle") for c in calls)


def test_unknown_shape_draws_nothing():
    """옛 저장본에 없는 도형 이름이 들어와도 죽지 않는다."""
    calls = _sticker_trace("[{kind:'shape', shape:'없는도형', size:20, x:0.5, y:0.5, rot:0}]")
    assert not [c for c in calls if c[0] in ("stroke", "fill", "fillText")]


def test_add_shape_uses_list_default_color():
    script = _slice_source() + """
THUMB_STATE.layers = []; THUMB_STATE.sel = 0;
renderThumbLayers = () => {}; renderThumbCanvas = () => {};
addThumbShape('check');
console.log(JSON.stringify(THUMB_STATE.layers[0]));
"""
    L = json.loads(_run_node(script))
    assert L["kind"] == "shape" and L["shape"] == "check"
    assert L["color"] == "#2FD873", "목록의 기본색으로 시작해야 바로 쓸 만하다"


def test_preset_does_not_destroy_selected_shape():
    """스티커와 같은 함정 — 도형을 고른 채 색 프리셋을 눌러도 사라지면 안 된다."""
    script = _slice_source() + _STICKER_SEL + """
THUMB_STATE.layers = [{kind:'shape', shape:'arrow_curve', size:20, x:0.3, y:0.7, rot:0, color:'#FF3B30'}];
THUMB_STATE.sel = 0;
applyThumbPreset(0);
console.log(JSON.stringify(THUMB_STATE.layers[0]));
"""
    assert json.loads(_run_node(script))["kind"] == "shape"


def test_title_click_skips_shape_layer():
    script = _slice_source() + _STICKER_SEL + """
THUMB_STATE.layers = [{text:'', font:'BMJUA.ttf', size:92, color:'#fff', outline:null,
                       box:null, rot:0, x:0.5, y:0.3},
                      {kind:'shape', shape:'check', size:20, x:0.3, y:0.7, rot:0, color:'#2FD873'}];
THUMB_STATE.sel = 1;
THUMB_STATE.title_cands = [{text:'제목', why:'w'}];
applyThumbTitle(0);
console.log(JSON.stringify({t: THUMB_STATE.layers[0].text, k: THUMB_STATE.layers[1].kind}));
"""
    out = json.loads(_run_node(script))
    assert out["t"] == "제목" and out["k"] == "shape"


def _grapheme(js_literal):
    return json.loads(_run_node(
        _slice_source() + f"console.log(JSON.stringify(firstGrapheme({js_literal})));"))


def test_direct_input_keeps_multibyte_emoji_intact():
    """★이모지는 서로게이트 쌍(2칸)이라 charAt/slice로 자르면 깨진 글자가 된다.
    사람이 보는 '한 글자'가 통째로 나와야 한다."""
    assert _grapheme("'🔥'") == "🔥"
    assert _grapheme("'😱😱'") == "😱", "여러 개를 넣으면 첫 하나만"
    assert _grapheme("'  ⭐  '") == "⭐", "앞뒤 공백은 무시"


def test_direct_input_keeps_zwj_family_emoji_whole():
    """👨‍👩‍👧 같은 ZWJ 결합 이모지는 7칸이 넘는다 — 쪼개면 사람 셋으로 흩어진다."""
    assert _grapheme("'👨‍👩‍👧'") == "👨‍👩‍👧"


def test_direct_input_rejects_empty():
    assert _grapheme("''") == ""
    assert _grapheme("'   '") == ""


def test_direct_input_adds_sticker_and_clears_box():
    """직접 입력칸에서 얹으면 스티커가 생기고 입력칸은 비워진다(연속 입력 대비)."""
    script = _slice_source() + """
THUMB_STATE.layers = []; THUMB_STATE.sel = 0;
renderThumbLayers = () => {}; renderThumbCanvas = () => {};
const box = {value: '🥲'}, hint = {textContent: ''};
document = {getElementById: id => id === 'thumbStickerInput' ? box
                              : id === 'thumbStickerInputHint' ? hint : null};
addThumbStickerFromInput();
console.log(JSON.stringify({emoji: THUMB_STATE.layers[0].emoji, left: box.value}));
"""
    out = json.loads(_run_node(script))
    assert out["emoji"] == "🥲", "목록에 없는 이모지도 얹혀야 한다"
    assert out["left"] == "", "입력칸이 안 비워지면 다음 것을 또 치기 번거롭다"


def test_preset_does_not_destroy_selected_sticker():
    """★스티커를 고른 채 색 프리셋을 누르면 빈 글자 레이어로 바뀌어 조용히 사라졌다."""
    script = _slice_source() + _STICKER_SEL + """
THUMB_STATE.layers = [{kind:'sticker', emoji:'🔥', size:18, x:0.3, y:0.7, rot:0}];
THUMB_STATE.sel = 0;
applyThumbPreset(0);
console.log(JSON.stringify(THUMB_STATE.layers[0]));
"""
    L = json.loads(_run_node(script))
    assert L["kind"] == "sticker" and L["emoji"] == "🔥", "스티커가 글자 레이어로 덮였다"


def test_title_click_targets_text_layer_not_sticker():
    """★스티커를 고른 채 추천 제목을 누르면 스티커에 문구가 박혀 그림이 사라졌다.
    제목은 글자 레이어로 가야 한다."""
    script = _slice_source() + _STICKER_SEL + """
THUMB_STATE.layers = [{text:'', font:'BMJUA.ttf', size:92, color:'#fff', outline:null,
                       box:null, rot:0, x:0.5, y:0.3},
                      {kind:'sticker', emoji:'🔥', size:18, x:0.3, y:0.7, rot:0}];
THUMB_STATE.sel = 1;                       // 스티커를 고른 상태
THUMB_STATE.title_cands = [{text:'속옷 빨래\\n이제 안 해요', why:'타깃'}];
applyThumbTitle(0);
console.log(JSON.stringify({text: THUMB_STATE.layers[0].text,
                            sticker: THUMB_STATE.layers[1]}));
"""
    out = json.loads(_run_node(script))
    assert out["text"] == "속옷 빨래\n이제 안 해요", "제목이 글자 레이어에 안 얹혔다"
    assert out["sticker"]["emoji"] == "🔥", "스티커가 문구로 덮였다"


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


# ── 🖐 손잡이(2026-08-18 사장님: "삭제 간단히 / 끝부분 잡고 크기·방향") ──────────
# 손잡이는 **캔버스가 아니라 그 위 DOM**이다. 캔버스에 그리면 generateThumb의 toBlob이
# 손잡이까지 PNG에 구워버린다 — 그 계약을 여기서 잠근다.

def _handles_html(layer, sel=0):
    script = _slice_source() + r"""
globalThis.HC_PRESETS = []; globalThis.HC_FONTS = []; globalThis.esc = s => s;
globalThis.window = {};
let HTML = '';
globalThis.document = { getElementById: (id) => id === 'thumbHandles'
  ? { set innerHTML(v){ HTML = v; }, get innerHTML(){ return HTML; } } : null };
THUMB_STATE.layers = [__LAYER__];
THUMB_STATE.sel = __SEL__;
renderThumbHandles();
console.log(JSON.stringify({html: HTML}));
""".replace("__LAYER__", json.dumps(layer)).replace("__SEL__", str(sel))
    return json.loads(_run_node(script))["html"]


def test_handles_show_for_sticker_with_delete_size_rotate():
    """스티커를 고르면 ✕삭제·↔크기·↻방향 세 손잡이가 뜬다."""
    html = _handles_html({"kind": "sticker", "emoji": "F", "size": 20,
                          "x": 0.5, "y": 0.5, "rot": 0})
    for h in ("del", "size", "rot"):
        assert f'data-h="{h}"' in html, f"{h} 손잡이가 없다"


def test_handles_hidden_for_text_layer():
    """글자 레이어엔 손잡이를 안 띄운다 — 글자는 편집창에서 다룬다(범위 고정)."""
    html = _handles_html({"text": "A", "font": "X.ttf", "size": 78, "color": "#fff",
                          "outline": None, "box": None, "rot": 0, "x": 0.5, "y": 0.2})
    assert html == "", "글자 레이어에 손잡이가 떴다"


def test_handle_positions_follow_size():
    """손잡이는 도형 반각(size/200)만큼 떨어져 붙는다 — 키우면 같이 벌어져야
    '끝부분을 잡는' 느낌이 유지된다. size=20 → 반각 10%p."""
    import re
    html = _handles_html({"kind": "shape", "shape": "arrow_bold", "size": 20,
                          "color": "#FF3B30", "x": 0.5, "y": 0.5, "rot": 0})
    m = re.search(r'data-h="del"[^>]*?left:([\d.]+)%;top:([\d.]+)%', html, re.S)
    assert m, "삭제 손잡이 좌표를 못 읽었다"
    assert float(m.group(1)) == pytest.approx(60.0, abs=0.1)     # x + 10%p
    # y 반각은 캔버스 비율(1080/1920)만큼 작다 → 0.5 - 0.1*0.5625 = 0.44375
    assert float(m.group(2)) == pytest.approx(44.38, abs=0.1)
