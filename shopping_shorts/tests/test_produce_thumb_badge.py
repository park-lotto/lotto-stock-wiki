"""썸네일 🏷 배지 레이어 — produce.html의 실제 소스를 잘라 Node로 실행한다.

배지는 참조 이미지(어그로 썸네일)의 좌상단 빨간 알약 "진짜 봐야할 것"이다.
글자 레이어와 다른 점: **알약 배경이 글자를 감싼다**(자동 줄바꿈·grow-to-fill을 안 탄다).
도형 레이어와 다른 점: **글자를 품는다**.

★2026-08-18 메모리(reference_썸네일_스티커도형레이어 ③)가 경고한 함정을 여기서 잠근다:
   새 kind를 넣으면 기존 '글자 가정' 경로가 그것을 조용히 파괴한다.
"""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_START = "// ── 6단계 썸네일"
_END = "// ── 썸네일 끝"


def _real_deps():
    """슬라이스 밖의 **진짜** 의존물을 파일에서 그대로 가져온다.

    ★스텁을 발명하지 않는다 — 하네스가 계약을 지어내면 진짜 버그가 초록 뒤에 숨는다
    (2026-07-17 사고: 발명한 STATE가 Critical 8건을 은폐). applyThumbPreset이
    HC_PRESETS를 읽는데 슬라이스 밖이라, 없으면 ReferenceError로 죽는다.
    """
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    m = re.search(r"^const HC_PRESETS=\[.*?^\];", src, re.M | re.S)
    assert m, "HC_PRESETS 선언을 못 찾았다 — applyThumbPreset이 이걸 쓴다"
    return m.group(0) + chr(10)


def _slice_source():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i, j = src.index(_START), src.index(_END)
    return _real_deps() + src[i:j]


def _run_node(script):
    """★`node -e`로 넘기지 마라 — 윈도우 명령줄 상한 32,767자(WinError 206, 3회 재발)."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "harness.js"
        p.write_text(script, encoding="utf-8")
        r = subprocess.run([NODE, str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


# ── 그리기용 가짜 캔버스 — 무엇을 호출했는지 기록만 한다(픽셀은 안 본다)
_FAKE_CTX = """
function mkCtx(){
  const calls = [];
  const rec = n => (...a) => { calls.push([n, ...a]); };
  return {calls,
    save: rec('save'), restore: rec('restore'), beginPath: rec('beginPath'),
    closePath: rec('closePath'), moveTo: rec('moveTo'), lineTo: rec('lineTo'),
    arc: rec('arc'), arcTo: rec('arcTo'), quadraticCurveTo: rec('quadraticCurveTo'),
    bezierCurveTo: rec('bezierCurveTo'), ellipse: rec('ellipse'),
    fill: rec('fill'), stroke: rec('stroke'), rect: rec('rect'),
    roundRect: rec('roundRect'), fillRect: rec('fillRect'),
    clearRect: rec('clearRect'), drawImage: rec('drawImage'),
    translate: rec('translate'), rotate: rec('rotate'), scale: rec('scale'),
    fillText: rec('fillText'), strokeText: rec('strokeText'),
    setTransform: rec('setTransform'), clip: rec('clip'),
    measureText: t => ({width: String(t).length * 40}),
    set font(v){ this._font = v; }, get font(){ return this._font || ''; },
    fillStyle: '', strokeStyle: '', lineWidth: 0, lineJoin: '', lineCap: '',
    textAlign: '', textBaseline: '', globalAlpha: 1,
    shadowColor: '', shadowBlur: 0, shadowOffsetY: 0, shadowOffsetX: 0,
  };
}
"""


def test_badge_list_exists_with_aggro_labels():
    """배지 목록이 있고, 참조 이미지의 '진짜 봐야할 것'을 포함한다."""
    script = _slice_source() + """
console.log(JSON.stringify(THUMB_BADGE_LIST));
"""
    lst = json.loads(_run_node(script))
    assert len(lst) >= 6, "배지가 너무 적다 — 고를 맛이 없다"
    labels = [b["label"] for b in lst]
    assert "진짜 봐야할 것" in labels
    for b in lst:
        assert b["label"].strip(), "빈 배지는 화면에서 안 보인다"
        assert b["color"].startswith("#"), "배지 색은 hex여야 한다"


def test_add_badge_makes_badge_layer_with_ratio_coords():
    """배지를 얹으면 kind:'badge' 레이어가 되고 좌표는 비율(0~1)이다."""
    script = _slice_source() + """
renderThumbLayers = () => {}; renderThumbCanvas = () => {}; renderThumbHandles = () => {};
THUMB_STATE.layers = [];
THUMB_STATE.sel = -1;
addThumbBadge('진짜 봐야할 것');
console.log(JSON.stringify(THUMB_STATE.layers));
"""
    layers = json.loads(_run_node(script))
    assert len(layers) == 1
    L = layers[0]
    assert L["kind"] == "badge"
    assert L["text"] == "진짜 봐야할 것"
    assert 0 <= L["x"] <= 1 and 0 <= L["y"] <= 1, "비율 좌표여야 프리뷰=결과"
    # 참조 이미지처럼 좌상단에서 시작한다
    assert L["y"] < 0.25, "배지는 위쪽에 놓인다"
    assert L["color"].startswith("#")


def test_badge_draws_pill_and_text():
    """배지는 알약(채워진 도형)과 글자를 둘 다 그린다."""
    script = _slice_source() + _FAKE_CTX + """
const ctx = mkCtx();
drawThumb(ctx, null, [{kind:'badge', text:'진짜 봐야할 것', x:0.3, y:0.08,
                       size:5, color:'#FF3B30', text_color:'#FFFFFF'}], 1080, 1920);
const names = ctx.calls.map(c => c[0]);
console.log(JSON.stringify({
  filled: names.includes('fill'),
  texted: names.includes('fillText'),
  text: (ctx.calls.find(c => c[0] === 'fillText') || [])[1] || ''
}));
"""
    d = json.loads(_run_node(script))
    assert d["filled"], "알약 배경이 안 그려졌다"
    assert d["texted"], "배지 글자가 안 그려졌다"
    assert d["text"] == "진짜 봐야할 것"


def test_badge_text_does_not_wrap_into_two_lines():
    """★배지는 글자 레이어와 달리 자동 두 줄로 쪼개지면 안 된다(알약이 깨진다)."""
    script = _slice_source() + _FAKE_CTX + """
const ctx = mkCtx();
drawThumb(ctx, null, [{kind:'badge', text:'진짜 봐야할 것', x:0.3, y:0.08,
                       size:5, color:'#FF3B30'}], 1080, 1920);
console.log(JSON.stringify(ctx.calls.filter(c => c[0] === 'fillText').length));
"""
    assert json.loads(_run_node(script)) == 1, "배지 글자가 여러 줄로 쪼개졌다"


def test_badge_survives_color_preset_click():
    """★함정①: 배지를 고른 채 색 프리셋을 누르면 빈 글자 레이어로 갈아치워지면 안 된다."""
    script = _slice_source() + """
renderThumbLayers = () => {}; renderThumbCanvas = () => {}; renderThumbHandles = () => {};
THUMB_STATE.layers = [];
addThumbBadge('충격');
const before = JSON.stringify(THUMB_STATE.layers[THUMB_STATE.sel]);
applyThumbPreset(0);
console.log(JSON.stringify({before, after: JSON.stringify(THUMB_STATE.layers[THUMB_STATE.sel])}));
"""
    d = json.loads(_run_node(script))
    assert d["before"] == d["after"], "색 프리셋이 배지를 갈아치웠다"


def test_badge_survives_title_suggestion_click():
    """★함정②: 배지를 고른 채 추천 제목을 누르면 배지에 제목이 박히면 안 된다."""
    script = _slice_source() + """
renderThumbLayers = () => {}; renderThumbCanvas = () => {}; renderThumbHandles = () => {};
THUMB_STATE.layers = [];
addThumbBadge('충격');
THUMB_STATE.title_cands = [{text:'세탁기에 소주를 넣어보세요'}];
applyThumbTitle(0);
const badge = THUMB_STATE.layers.find(L => L.kind === 'badge');
const text  = THUMB_STATE.layers.find(L => L.kind !== 'badge' && L.text);
console.log(JSON.stringify({badge_text: badge && badge.text, title_landed: !!text}));
"""
    d = json.loads(_run_node(script))
    assert d["badge_text"] == "충격", "추천 제목이 배지 문구를 덮어썼다"
    assert d["title_landed"], "제목이 글자 레이어에 안 얹혔다"


def test_deselect_does_not_pick_badge_as_text_layer():
    """★함정③: 선택 해제는 '글자 레이어'로 돌아가야 한다 — 배지를 글자로 착각하면 안 된다."""
    script = _slice_source() + """
renderThumbLayers = () => {}; renderThumbCanvas = () => {}; renderThumbHandles = () => {};
THUMB_STATE.layers = [];
addThumbBadge('충격');          // 배지만 있는 상태
deselectThumbLayer();
console.log(JSON.stringify({sel: THUMB_STATE.sel}));
"""
    assert json.loads(_run_node(script))["sel"] == -1, "배지가 글자 레이어로 취급됐다"


def test_old_saved_thumbnails_unchanged():
    """구 저장본 회귀 0 — badge가 없으면 아무것도 안 그린다."""
    script = _slice_source() + _FAKE_CTX + """
const a = mkCtx(), b = mkCtx();
const layers = [{text:'옛 제목', x:0.5, y:0.2, size:80, color:'#fff'}];
drawThumb(a, null, layers, 1080, 1920);
drawThumb(b, null, JSON.parse(JSON.stringify(layers)), 1080, 1920);
console.log(JSON.stringify({same: JSON.stringify(a.calls) === JSON.stringify(b.calls),
                            drew: a.calls.some(c => c[0] === 'fillText')}));
"""
    d = json.loads(_run_node(script))
    assert d["drew"] and d["same"]


def test_badge_dot_toggle_off_removes_circle():
    """왼쪽 동그라미를 끄면 원을 안 그린다(체크박스가 진짜 먹는지)."""
    script = _slice_source() + _FAKE_CTX + """
function arcs(dot){
  const ctx = mkCtx();
  drawThumb(ctx, null, [{kind:'badge', text:'충격', x:0.3, y:0.08, size:5,
                         color:'#FF2D2D', dot}], 1080, 1920);
  return ctx.calls.filter(c => c[0] === 'arc').length;
}
console.log(JSON.stringify({on: arcs(true), off: arcs(false)}));
"""
    d = json.loads(_run_node(script))
    assert d["on"] == 1, "동그라미가 안 그려졌다"
    assert d["off"] == 0, "동그라미를 껐는데도 그려졌다"


def test_badge_field_edit_is_boolean_not_string():
    """★`dot`을 문자열 'false'로 저장하면 꺼도 켜진 것으로 읽힌다(자바스크립트 진리값 함정)."""
    script = _slice_source() + """
renderThumbLayers = () => {}; renderThumbCanvas = () => {}; renderThumbHandles = () => {};
THUMB_STATE.layers = [];
addThumbBadge('충격');
setThumbField('dot', false);
const L = THUMB_STATE.layers[THUMB_STATE.sel];
console.log(JSON.stringify({dot: L.dot, type: typeof L.dot}));
"""
    d = json.loads(_run_node(script))
    assert d["type"] == "boolean" and d["dot"] is False


def test_badge_pill_grows_with_text_length():
    """알약은 글자 길이에 따라 넓어진다 — 긴 문구가 알약 밖으로 삐져나오면 안 된다."""
    script = _slice_source() + _FAKE_CTX + """
function pillWidth(text){
  const ctx = mkCtx();
  drawThumb(ctx, null, [{kind:'badge', text, x:0.5, y:0.08, size:5}], 1080, 1920);
  const xs = ctx.calls.filter(c => c[0] === 'lineTo' || c[0] === 'moveTo').map(c => c[1]);
  return Math.max(...xs) - Math.min(...xs);
}
console.log(JSON.stringify({short: pillWidth('충격'), long: pillWidth('진짜 봐야할 것')}));
"""
    d = json.loads(_run_node(script))
    assert d["long"] > d["short"], "긴 문구인데 알약이 안 넓어졌다"
