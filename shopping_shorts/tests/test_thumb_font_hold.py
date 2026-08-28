"""썸네일 제목 글자 크기가 타이핑 중에 출렁이던 것(2026-08-27 고객 제보).

제보 원문(사장님이 화면녹화와 함께 전달): "썸네일 글씨가 원래 저렇게 크기가 왔다갔다
하는게 맞아요?"

원인: grow-to-fill(thumbFit)이 **글자 수에 맞춰 매번 폰트를 다시 잰다**. 폭 92%를 채우는
게 목적이라 짧으면 크고 길면 작다 — 결과물은 정상이지만 **치는 과정이 고장난 것처럼 보인다**.
실측(1080 캔버스): "어" 422px → "얼린고기" 248px → "얼린고기 보관은 이렇게 하세요" 135px.

사장님 지시: "1로 해주고 작으면 각자 크기조정으로"
 → 처음 잡은 크기를 그 레이어의 기준으로 **계속 쓴다**. 자동으로 도로 줄이지 않는다.
   작으면 사람이 [크기 미세조정] 슬라이더로 올린다.

이 파일은 produce.html의 **실제 소스를 잘라 Node로 실행**한다(스텁을 발명하지 않는다).
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
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _slice():
    """thumbAutoLines ~ 강조효과 직전까지 = grow-to-fill과 홀드 로직 전부."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index("// 자동 2줄:")
    j = src.index("// ── ✨ 강조 효과")
    head = """
const THUMB_W = 1080, THUMB_H = 1920;
function thumbFontCss(){ return 'X'; }
// 글자 폭 근사(한글 1.0em, 공백 0.35em) — 실제 캔버스가 없으므로 측정만 대신한다.
function mkCtx(){ return {set font(v){this._f=v}, get font(){return this._f},
  measureText(t){ let w=0; for (const ch of String(t)) w += (ch===' '?0.35:1.0); return {width:w*100}; }}; }
const THUMB_STATE = {layers: [], sel: 0};
const document = {getElementById: () => ({getContext: () => mkCtx()})};
"""
    return head + src[i:j]


def _run(script):
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "h.js"
        p.write_text(_slice() + script, encoding="utf-8")
        r = subprocess.run([NODE, str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


_STEPS = ["어", "얼린", "얼린고기", "얼린고기 보관은", "얼린고기 보관은 이렇게 하세요"]


def test_without_hold_size_swings_wildly():
    """★뿌리 재현: 붙잡지 않으면 3배 넘게 출렁인다(고객이 본 그 화면)."""
    d = _run("""
const ctx = mkCtx();
const out = %s.map(t => Math.round(thumbFit(ctx, {text:t, size:90}, THUMB_W, THUMB_H).size));
console.log(JSON.stringify(out));
""" % json.dumps(_STEPS, ensure_ascii=False))
    assert max(d) / min(d) > 2.5, f"뿌리가 재현되지 않는다(설계가 바뀌었나): {d}"


def test_hold_keeps_size_while_typing():
    """★한 번 잡은 기준은 글자를 더 쳐도 유지된다 — 자동으로 도로 줄지 않는다."""
    d = _run("""
const L = {text:'', size:90};
THUMB_STATE.layers = [L]; THUMB_STATE.sel = 0;
const ctx = mkCtx();
const out = [];
for (const t of %s){
  L.text = t;
  thumbHoldSizeWhileTyping();                 // setThumbField('text', ...)가 부르는 것
  out.push(Math.round(thumbFit(ctx, L, THUMB_W, THUMB_H).size));
}
console.log(JSON.stringify(out));
""" % json.dumps(_STEPS, ensure_ascii=False))
    assert max(d) / min(d) < 1.3, f"아직 크게 출렁인다: {d}"
    # 마지막이 처음보다 크게 작아지면 안 된다(손 떼면 확 줄던 증상)
    assert d[-1] >= d[0] * 0.8, f"다 치고 나니 도로 작아졌다: {d}"


def test_hold_not_taken_on_empty_text():
    """빈 칸에서 기준을 잡으면 0에 굳는다 — 글자가 생긴 뒤에 잡는다."""
    d = _run("""
const L = {text:'', size:90};
THUMB_STATE.layers=[L]; THUMB_STATE.sel=0;
thumbHoldSizeWhileTyping();
const held1 = !!THUMB_FIT_HOLD.get(L);
L.text = '어'; thumbHoldSizeWhileTyping();
console.log(JSON.stringify({빈칸에서잡힘: held1, 글자생긴뒤잡힘: !!THUMB_FIT_HOLD.get(L)}));
""")
    assert d["빈칸에서잡힘"] is False
    assert d["글자생긴뒤잡힘"] is True


def test_slider_still_works():
    """작으면 사람이 슬라이더로 올린다 — 홀드가 슬라이더를 막으면 안 된다(사장님 지시)."""
    d = _run("""
const L = {text:'얼린고기 보관은 이렇게 하세요', size:90};
THUMB_STATE.layers=[L]; THUMB_STATE.sel=0;
thumbHoldSizeWhileTyping();
const ctx = mkCtx();
const base = thumbFit(ctx, L, THUMB_W, THUMB_H).size;
L.size = 40; const small = thumbFit(ctx, L, THUMB_W, THUMB_H).size;
console.log(JSON.stringify({base: Math.round(base), small: Math.round(small)}));
""")
    assert d["small"] < d["base"], "슬라이더를 내려도 크기가 안 바뀐다"


def test_badge_and_sticker_not_held():
    """배지·스티커·도형은 대상이 아니다(글자 레이어만)."""
    d = _run("""
const out = {};
for (const kind of ['badge','sticker','shape']){
  const L = {kind, text:'충격', size:5};
  THUMB_STATE.layers=[L]; THUMB_STATE.sel=0;
  thumbHoldSizeWhileTyping();
  out[kind] = !!THUMB_FIT_HOLD.get(L);
}
console.log(JSON.stringify(out));
""")
    assert d == {"badge": False, "sticker": False, "shape": False}, d


def test_release_hold_lets_it_refit():
    """판을 새로 짜면(프리셋 등) 기준을 놓아줄 수 있어야 한다."""
    d = _run("""
const L = {text:'어', size:90};
THUMB_STATE.layers=[L]; THUMB_STATE.sel=0;
thumbHoldSizeWhileTyping();
const before = !!THUMB_FIT_HOLD.get(L);
thumbReleaseFitHold(L);
console.log(JSON.stringify({before, after: !!THUMB_FIT_HOLD.get(L)}));
""")
    assert d["before"] is True and d["after"] is False


# ── 직접 입력칸: 글자를 넣으면 글자로 얹힌다(2026-08-27 고객 제보) ─────────────
# 제보: "이건 글자를 쳐도 적용이 안된다"
# 실측 원인 2개:
#   ① firstGrapheme으로 **첫 글자만** 스티커가 됐다 — "안녕하세요" → '안' 하나만 얹힘
#   ② 안내문이 "안 얹었어요"로 나가 **실패한 것처럼 읽혔다**(하필 첫 글자가 '안')
def _run_input(script):
    """addThumbStickerFromInput 주변 슬라이스를 Node로 돌린다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index("function firstGrapheme")
    j = src.index("function selectThumbLayer")
    head = """
const THUMB_W = 1080, THUMB_H = 1920;
const THUMB_STATE = {layers: [], sel: -1};
const _els = {thumbStickerInput: {value: ''}, thumbStickerInputHint: {textContent: ''}};
const document = {getElementById: id => _els[id] || null};
function addThumbSticker(e){ THUMB_STATE.layers.push({kind:'sticker', emoji:e});
                             THUMB_STATE.sel = THUMB_STATE.layers.length-1; }
function addThumbLayer(){ THUMB_STATE.layers.push({text:'문구를 입력하세요'});
                          THUMB_STATE.sel = THUMB_STATE.layers.length-1; }
function thumbReleaseFitHold(){}
function renderThumbLayers(){}
function renderThumbCanvas(){}
"""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "h.js"
        p.write_text(head + src[i:j] + script, encoding="utf-8")
        r = subprocess.run([NODE, str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_korean_input_becomes_text_layer_not_one_char_sticker():
    """★뿌리: 한글 문장을 넣으면 **문장 전체가 글자 레이어**로 얹혀야 한다."""
    d = _run_input("""
_els.thumbStickerInput.value = '안녕하세요';
addThumbStickerFromInput();
console.log(JSON.stringify({layers: THUMB_STATE.layers, hint: _els.thumbStickerInputHint.textContent}));
""")
    assert len(d["layers"]) == 1
    L = d["layers"][0]
    assert L.get("kind") != "sticker", "글자인데 스티커로 얹혔다"
    assert L.get("text") == "안녕하세요", f"문장 전체가 아니라 일부만 들어갔다: {L}"


def test_hint_is_not_read_as_failure():
    """★안내문이 부정문으로 읽히면 안 된다 — '안 얹었어요'가 그랬다."""
    d = _run_input("""
_els.thumbStickerInput.value = '안녕하세요';
addThumbStickerFromInput();
console.log(JSON.stringify({hint: _els.thumbStickerInputHint.textContent}));
""")
    h = d["hint"]
    assert "얹었어요" in h
    assert not h.startswith("안 "), f"실패로 읽히는 안내문: {h}"
    assert "안녕하세요" in h, f"무엇을 얹었는지 안 보인다: {h}"


def test_emoji_still_becomes_sticker():
    """이모지는 종전대로 스티커(회귀 0)."""
    d = _run_input("""
_els.thumbStickerInput.value = '🔥';
addThumbStickerFromInput();
console.log(JSON.stringify({layers: THUMB_STATE.layers, hint: _els.thumbStickerInputHint.textContent}));
""")
    assert d["layers"] == [{"kind": "sticker", "emoji": "🔥"}]
    assert "🔥" in d["hint"]


def test_blank_input_adds_nothing():
    """빈 칸이면 아무것도 안 얹고 무엇을 하라고 알려준다."""
    d = _run_input("""
_els.thumbStickerInput.value = '   ';
addThumbStickerFromInput();
console.log(JSON.stringify({n: THUMB_STATE.layers.length, hint: _els.thumbStickerInputHint.textContent}));
""")
    assert d["n"] == 0 and "넣고" in d["hint"]


def test_input_is_cleared_after_use():
    """얹은 뒤 입력칸은 비워진다 — 안 비우면 또 눌러 두 번 얹힌다."""
    d = _run_input("""
_els.thumbStickerInput.value = '충격';
addThumbStickerFromInput();
console.log(JSON.stringify({left: _els.thumbStickerInput.value}));
""")
    assert d["left"] == ""
