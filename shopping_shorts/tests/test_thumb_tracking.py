"""썸네일 자간(letter-spacing)과 글자 레이어 손잡이(2026-08-28 사장님 요청).

사장님: "썸네일 자간 설정 이런거는 어려울까요? 그리고 전체잡고 늘려서 글씨 크게 작게
하는 기능 좋을 거 같은뎅"

여기서 못박는 것:
  ① 자간은 **재는 곳(thumbFit)과 그리는 곳에 같은 값**이 걸려야 한다. 한쪽만 걸면
     자동 줄맞춤이 좁게 재고 넓게 그려 글자가 캔버스를 넘친다.
  ② 자간은 px가 아니라 **글자 크기 대비 %**로 담는다 — 미리보기(270)와 저장(1080)이
     같은 그림이어야 하는 썸네일 전체의 계약(배율이 다른 두 캔버스).
  ③ tracking이 없는 옛 저장본은 그림이 **하나도 안 바뀐다**(회귀 0).
  ④ 글자 레이어도 캔버스 손잡이를 받는다 — 손잡이는 2026-08-18부터 있었는데 kind 필터가
     글자만 빼놓아 슬라이더로만 조절할 수 있었다.

★produce.html의 **실제 소스를 잘라 Node로 실행**한다(스텁을 발명하지 않는다).
  ctx 모형은 Chrome처럼 letterSpacing을 measureText에 반영한다 — 반영하지 않는 모형을
  쓰면 자간이 0% 동작해도 초록이 뜬다(하네스가 계약을 발명하면 안 된다).
"""
import json
import pathlib
import shutil
import subprocess
import tempfile

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")

_HEAD = """
const THUMB_W = 1080, THUMB_H = 1920;
function thumbFontCss(){ return 'X'; }
// Chrome의 CanvasRenderingContext2D를 흉내낸다 — letterSpacing이 measureText에 반영된다.
// (반영 안 하는 모형을 쓰면 자간이 안 걸려도 테스트가 통과한다)
function mkCtx(){
  return {
    letterSpacing: '0px',
    set font(v){ this._f = v; }, get font(){ return this._f; },
    measureText(t){
      const s = String(t);
      let w = 0;
      for (const ch of s) w += (ch === ' ' ? 0.35 : 1.0);
      const ls = parseFloat(this.letterSpacing) || 0;
      return {width: w * 100 + ls * s.length};   // 글자마다 자간이 더 붙는다
    },
  };
}
const THUMB_STATE = {layers: [], sel: 0};
const document = {getElementById: () => ({getContext: () => mkCtx()})};
"""


def _slice():
    """실제 소스 두 토막 — grow-to-fill(thumbFit)과 새 레이어 자리 고르기(_freeThumbY)."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index("// 자동 2줄:")
    j = src.index("// ── ✨ 강조 효과")
    a = src.index("const THUMB_SLOT_Y")
    b = src.index("function addThumbLayer()")
    return _HEAD + src[i:j] + src[a:b]


def _run(script):
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "h.js"
        p.write_text(_slice() + script, encoding="utf-8")
        r = subprocess.run([NODE, str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_자간이_없으면_그림이_종전과_같다():
    """옛 저장본(tracking 없음)은 한 픽셀도 안 달라져야 한다."""
    d = _run("""
const ctx = mkCtx();
const a = thumbFit(ctx, {text:'얼린고기 보관법', size:90}, THUMB_W, THUMB_H);
const b = thumbFit(ctx, {text:'얼린고기 보관법', size:90, tracking:0}, THUMB_W, THUMB_H);
console.log(JSON.stringify({a:a.size, b:b.size}));
""")
    assert abs(d["a"] - d["b"]) < 1e-9, f"tracking 0이 그림을 바꿨다: {d}"


def test_자간을_벌리면_자동크기가_줄어든다():
    """★①의 본체 — 자간이 재는 곳에 걸려야 넘치지 않는다.

    폭 92%를 채우는 게 목표이므로, 글자 사이를 벌리면 그만큼 글자는 작아져야 한다.
    자간이 measureText에 안 걸리면 크기가 그대로다 = 캔버스를 넘치게 그린다.
    """
    d = _run("""
const ctx = mkCtx();
const out = [0, 10, 30].map(t =>
  thumbFit(ctx, {text:'얼린고기 보관법', size:90, tracking:t}, THUMB_W, THUMB_H).size);
console.log(JSON.stringify(out));
""")
    assert d[0] > d[1] > d[2], f"자간을 벌려도 크기가 안 줄었다(측정에 안 걸린다): {d}"


def test_자간은_캔버스_배율에_비례한다():
    """★②의 본체 — 미리보기(270)와 저장(1080)이 같은 그림이어야 한다.

    자간을 px로 담으면 작은 캔버스에서만 크게 벌어져 두 그림이 어긋난다.
    글자 크기 대비 %로 담으므로, 크기가 2배면 자간 px도 2배여야 한다.
    """
    d = _run("""
const L = {tracking: 20};
console.log(JSON.stringify({s100: _thumbTrackCss(L, 100), s200: _thumbTrackCss(L, 200)}));
""")
    assert d["s100"] == "20.00px" and d["s200"] == "40.00px", d


def test_letterSpacing_없는_브라우저에서도_안_죽는다():
    """구형 브라우저(letterSpacing 미지원)에서는 종전 그림 — 예외로 렌더가 통째로 죽으면 안 된다."""
    d = _run("""
const ctx = {set font(v){this._f=v}, get font(){return this._f},
             measureText(t){ return {width: String(t).length * 100}; }};
const f = thumbFit(ctx, {text:'가나다', size:90, tracking:30}, THUMB_W, THUMB_H);
console.log(JSON.stringify({ok: f.size > 0}));
""")
    assert d["ok"]


def test_자간_한칸_계산이_트래킹에_비례한다():
    """가운데 정렬 보정의 재료 — Chrome은 마지막 글자 뒤에도 자간을 붙인다(실측).

    실브라우저 실측(2026-08-28): '가나다' 100px, letterSpacing 40px → 폭 276 → 396.
    +120 = **3칸**(글자 수)이지 2칸이 아니다. 그래서 center 정렬이 자간 절반만큼
    왼쪽으로 밀린다(실측: 자간 81.4px일 때 잉크 중심이 캔버스 중심에서 41px 왼쪽).
    """
    d = _run("""
const ctx = mkCtx();
console.log(JSON.stringify({
  off: _trackPx(ctx, {tracking: 0}, 100),
  on:  _trackPx(ctx, {tracking: 30}, 100),
}));
""")
    assert d["off"] == 0 and abs(d["on"] - 30) < 1e-6, d


def test_letterSpacing_없으면_보정도_0이다():
    """구형 브라우저는 자간이 안 걸리니 보정도 하면 안 된다(하면 오히려 밀린다)."""
    d = _run("""
const ctx = {set font(v){this._f=v}, get font(){return this._f},
             measureText(t){ return {width: String(t).length * 100}; }};
console.log(JSON.stringify({px: _trackPx(ctx, {tracking: 30}, 100)}));
""")
    assert d["px"] == 0


class Test화면배선:
    SRC = PRODUCE_HTML.read_text(encoding="utf-8")

    def test_자간_슬라이더가_편집칸에_있다(self):
        assert "setThumbField('tracking'" in self.SRC
        assert "자간" in self.SRC

    def test_그리는_곳에도_자간이_걸린다(self):
        """★재는 곳만 걸고 그리는 곳을 빼먹는 게 이 기능의 전형적 반쪽 구현이다."""
        i = self.SRC.index("const {lines, size, family} = thumbFit(ctx, L, W, H)")
        j = self.SRC.index("ctx.textAlign = 'center'", i)
        assert "_setTrack(ctx, L, size)" in self.SRC[i:j], \
            "캔버스에 그릴 때 자간을 안 걸면 미리보기와 저장본이 어긋난다"

    def test_가운데_정렬_보정이_그리는_곳에_걸린다(self):
        """★실브라우저 실측(2026-08-28): 보정 없이 자간 30을 주면 글자가 41px 왼쪽으로
        밀린다(자간 81.4px의 절반). 채우기·외곽선·네온이 전부 같은 x를 써야 한다."""
        i = self.SRC.index("const tx = ls / 2;")
        j = self.SRC.index("_fxUnderline(ctx, line, y, size, L.fx, _fill, ls)", i)
        block = self.SRC[i:j]
        assert "ctx.fillText(line, tx, y)" in block, "채우기가 보정을 안 쓴다"
        assert "ctx.strokeText(line, tx, y)" in block, "외곽선이 보정을 안 쓴다"
        assert "ctx.measureText(line).width - ls" in block, "배경 박스 폭에서 자간 한 칸을 안 뺐다"

    def test_글자_레이어도_손잡이를_받는다(self):
        """kind 필터가 글자만 빼놓던 것(produce.html) — 그 회귀를 막는다."""
        i = self.SRC.index("function renderThumbHandles()")
        j = self.SRC.index("function initThumbHandleDrag()")
        block = self.SRC[i:j]
        assert "isText" in block, "글자 레이어가 다시 손잡이에서 빠졌다"
        assert "['sticker', 'shape', 'badge'].includes(L.kind)" in block


class Test새글자_얹기:
    """스티커 직접입력 칸 — 사장님 "고쳐"(2026-08-28).

    라이브 실측으로 확인한 두 가지:
      · maxlength=8 → 썸네일 문구가 통째로 잘렸다
      · 새 글자 레이어가 늘 y=0.14(맨 위)에 생겨 **기존 제목과 포개졌다**
        → 화면이 안 바뀐 것처럼 보여 "얹어도 반영이 안 된다"로 읽혔다
    """
    SRC = PRODUCE_HTML.read_text(encoding="utf-8")

    def test_입력칸_길이제한이_문구를_안_자른다(self):
        i = self.SRC.index('id="thumbStickerInput"')
        seg = self.SRC[i:i + 200]
        assert 'maxlength="8"' not in seg, "8글자 제한이 아직 있다 — 썸네일 문구가 잘린다"
        import re
        m = re.search(r'maxlength="(\d+)"', seg)
        assert m and int(m.group(1)) >= 30, f"제한이 여전히 짧다: {seg[:80]}"

    def test_새_글자는_기존_글자와_겹치지_않는_자리에_생긴다(self):
        d = _run("""
THUMB_STATE.layers = [{text:'아이 생일 엄마들', y:0.14}];
const a = _freeThumbY(0.14);
THUMB_STATE.layers.push({text:'둘째 줄', y:a});
const b = _freeThumbY(0.14);
console.log(JSON.stringify({a, b}));
""")
        assert abs(d["a"] - 0.14) > 0.05, f"기존 제목과 같은 자리에 또 놓았다: {d}"
        assert abs(d["b"] - d["a"]) > 0.05 and abs(d["b"] - 0.14) > 0.05, \
            f"세 번째도 앞의 것들을 피해야 한다: {d}"

    def test_처음_얹는_글자는_원래_자리_그대로(self):
        """빈 판에서는 프리셋 위치를 그대로 쓴다 — 회귀 0."""
        d = _run("""
THUMB_STATE.layers = [];
console.log(JSON.stringify({y: _freeThumbY(0.14)}));
""")
        assert d["y"] == 0.14

    def test_빈_문구_레이어는_자리를_차지하지_않는다(self):
        """문구가 비어 있으면 화면에 아무것도 안 그려진다 — 피할 이유가 없다."""
        d = _run("""
THUMB_STATE.layers = [{text:'   ', y:0.14}, {kind:'sticker', emoji:'F', y:0.14}];
console.log(JSON.stringify({y: _freeThumbY(0.14)}));
""")
        assert d["y"] == 0.14
