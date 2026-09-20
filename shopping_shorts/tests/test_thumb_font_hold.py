"""썸네일 제목 크기는 문구 길이가 아니라 사용자가 정한 숫자로 고정된다.

2026-09-19 박세현님 작업에서 같은 글꼴인데 제목 길이에 따라 실제 글자 크기가 달라졌다.
원인은 size가 실제 크기가 아니라 grow-to-fill 결과의 배율이었던 것이다. 이제 같은 size는
문구와 무관하게 같은 크기로 그려야 한다. 이 파일은 produce.html 실제 코드를 실행한다.
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
    """thumbAutoLines부터 고정 크기 계산까지 실제 소스를 실행한다."""
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


def test_same_value_means_same_size_for_every_title():
    """★같은 90이면 한 글자든 긴 문장이든 실제 글자 크기가 같아야 한다."""
    d = _run("""
const ctx = mkCtx();
const out = %s.map(t => Math.round(thumbFit(ctx, {text:t, size:90}, THUMB_W, THUMB_H).size));
console.log(JSON.stringify(out));
""" % json.dumps(_STEPS, ensure_ascii=False))
    assert len(set(d)) == 1, f"문구 길이에 따라 크기가 달라졌다: {d}"


def test_size_85_is_fixed_across_titles():
    """고객이 맞춘 85도 모든 제목에서 같은 실제 크기다."""
    d = _run("""
const ctx = mkCtx();
console.log(JSON.stringify(%s.map(t => thumbFit(ctx, {text:t, size:85}, THUMB_W, THUMB_H).size)));
""" % json.dumps(_STEPS, ensure_ascii=False))
    assert len(set(d)) == 1
    assert d[0] == pytest.approx(1080 * 85 / 500)


def test_preview_and_saved_png_keep_same_ratio():
    """270 미리보기와 1080 저장본은 4배 차이로 같은 모양이어야 한다."""
    d = _run("""
const ctx=mkCtx(), L={text:'세탁기에\\n소주 넣고 충격', size:85};
console.log(JSON.stringify({preview:thumbFit(ctx,L,270,480).size, saved:thumbFit(ctx,L,1080,1920).size}));
""")
    assert d["saved"] == pytest.approx(d["preview"] * 4)


def test_slider_still_works():
    """크기는 사용자가 슬라이더로 직접 정한다."""
    d = _run("""
const L = {text:'얼린고기 보관은 이렇게 하세요', size:90};
const ctx = mkCtx();
const base = thumbFit(ctx, L, THUMB_W, THUMB_H).size;
L.size = 40; const small = thumbFit(ctx, L, THUMB_W, THUMB_H).size;
console.log(JSON.stringify({base: Math.round(base), small: Math.round(small)}));
""")
    assert d["small"] < d["base"], "슬라이더를 내려도 크기가 안 바뀐다"


def test_trailing_enter_is_not_an_extra_line():
    """끝의 Enter 때문에 보이지 않는 세 번째 줄이 생기지 않는다."""
    d = _run("""
console.log(JSON.stringify(thumbAutoLines('세탁기에\\n소주 넣고 충격\\n')));
""")
    assert d == ["세탁기에", "소주 넣고 충격"]


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
