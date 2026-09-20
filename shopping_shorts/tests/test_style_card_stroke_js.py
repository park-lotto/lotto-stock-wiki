"""6단계 스타일 카드(축소 썸네일)의 테두리가 미리보기·렌더와 같은 규칙인지.

배경: 2026-08-31 `handoff/자막렌더불일치.md`가 자막·헤드카피 미리보기를 stroke로 통일하고
서버 `_outline_parts(zero_ok=True)`를 고쳤지만, **스타일 카드는 ⏭로 남겨뒀다**
("썸네일 스타일카드(styleCardHTML)는 아직 대각 4방향 + Math.max(1,…). 같은 함정이다").

카드에 남아 있던 두 가지:
  ① `hc.outline_w || 6` — 두께 **0이 falsy**라 6으로 되살아난다.
     서버가 고친 `_ui_px` 0무시 버그와 같은 모양(0은 '없음'이 아니라 0이다).
  ② 대각 4방향 text-shadow — 두꺼워지면 검은 사본이 글자 위로 올라와 획을 메운다.

즉 **카드가 보여주는 그림과 실제 결과가 달랐다**. 스타일을 고르는 화면이 거짓말하면
사장님은 고른 뒤에야 다르다는 걸 안다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "function _cardStrokeCss(s, scale){"
_END = "function updateCaption(){"

_DRIVER = r"""
const out = CASES.map(c => _cardStrokeCss(c.style, c.scale));
console.log(JSON.stringify(out));
"""


def _run(tmp_path, cases):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    frag = src[src.index(_START):src.index(_END)]
    js = tmp_path / "t.js"
    js.write_text("const CASES = " + json.dumps(cases) + ";\n" + frag + _DRIVER,
                  encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_zero_width_draws_nothing(tmp_path):
    """★두께 0이면 테두리를 아예 안 그린다 — 서버 _outline_parts(zero_ok=True)와 같은 판단."""
    got = _run(tmp_path, [
        {"style": {"outline": True, "outline_w": 0}, "scale": 92 / 720},
        {"style": {"outline": False, "outline_w": 6}, "scale": 92 / 720},
    ])
    assert got[0] == "", f"두께 0인데 테두리가 그려진다(falsy 함정 부활): {got[0]!r}"
    assert got[1] == "", f"외곽선 OFF인데 그려진다: {got[1]!r}"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_uses_stroke_not_diagonal_shadow(tmp_path):
    """대각 4방향 그림자를 쓰면 두꺼울 때 획이 메워진다 — stroke여야 한다."""
    got = _run(tmp_path, [{"style": {"outline": True, "outline_w": 8,
                                     "outline_color": "#112233"}, "scale": 92 / 720}])
    css = got[0]
    assert "-webkit-text-stroke" in css, f"stroke가 아니다: {css!r}"
    assert "paint-order" in css, "paint-order가 없으면 획이 글자를 덮는다"
    assert "text-shadow" not in css, f"옛 대각 그림자가 남아 있다: {css!r}"
    assert "#112233" in css, "지정한 테두리 색을 안 쓴다"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_thin_outline_not_rounded_up(tmp_path):
    """Math.max(1,round(..))로 반올림하면 얇은 테두리가 4배로 뻥튀기된다.

    실측: outline_w=2, 카드 스케일 92/720 → 진짜 0.26px인데 옛 코드는 1px로 그렸다.
    """
    got = _run(tmp_path, [{"style": {"outline": True, "outline_w": 2}, "scale": 92 / 720}])
    css = got[0]
    assert css, "얇아도 테두리는 있어야 한다"
    import re
    m = re.search(r"-webkit-text-stroke:([\d.]+)px", css)
    assert m, css
    assert float(m.group(1)) < 0.5, f"0.26px여야 하는데 {m.group(1)}px로 뻥튀기됐다"


def test_style_card_calls_shared_helper():
    """카드가 공용 함수를 쓰는지 — 옛 인라인 계산이 남아 있으면 또 어긋난다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    card = src[src.index("function styleCardHTML("):]
    card = card[:card.index("function ", 40)]
    assert "_cardStrokeCss(" in card, "스타일 카드가 공용 테두리 함수를 안 쓴다"
    # 주석은 빼고 **코드 줄만** 본다 — 설명에 쓴 `hc.outline_w || 6`까지 잡으면 오탐이다
    # (실제로 이 테스트가 내 주석을 잡았다).
    code = "\n".join(l for l in card.splitlines() if not l.strip().startswith("//"))
    assert "outline_w||6" not in code.replace(" ", ""), "falsy 기본값(||6)이 코드에 남아 있다"
    assert "text-shadow:${ow}" not in code, "옛 대각 그림자 인라인 계산이 남아 있다"
