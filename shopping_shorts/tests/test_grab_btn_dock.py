"""버튼 자리(영상 칸 옆·위에서부터) 계산을 node로 실제 실행해 확인한다.

2026-09-01 사장님 요청: 버튼은 영상 칸 오른쪽 **위**에서부터, 시크바는 **영상 아래**로.
문법검사로는 못 잡는 층 — 좁은 창 복귀·빈칸 없이 연속으로 쌓기·시크바 자리.
자리 판단은 grab_logic.js `_dockAnchor`/`_dockBtns` 한 곳뿐(0순위-B).
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

LOGIC = pathlib.Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"


def _dock_src():
    src = LOGIC.read_text(encoding="utf-8")
    i = src.index("  var DOCK_IDS")
    j = src.index("function tick()", i)
    return src[i:j]


def _run(inner_width, video_rect, present=None, inner_height=900, btn_width=150,
         ancestor=None, rail=None):
    """present=None이면 버튼 4개 + 시크바 전부 있는 화면."""
    ids = ["ss-adopt-btn", "ss-lens-btn", "ss-chadd-btn", "ss-grab-btn"]
    present = ids + ["ss-seek"] if present is None else present
    script = f"""
var window = {{ innerWidth: {inner_width}, innerHeight: {inner_height} }};
var anc = {json.dumps(ancestor)};
var rail = {json.dumps(rail)};
var vid = {{
  getBoundingClientRect: function () {{ return {json.dumps(video_rect)}; }},
  closest: function () {{ return null; }},
  parentElement: anc ? {{ getBoundingClientRect: function () {{ return anc; }},
                         parentElement: null }} : null
}};
var els = {{}};
{json.dumps(present)}.forEach(function (id) {{
  els[id] = {{ offsetWidth: {btn_width}, style: {{}} }};
}});
var document = {{
  querySelectorAll: function (sel) {{
    if (sel === "video") return {'[vid]' if video_rect else '[]'};
    return rail ? [{{ getBoundingClientRect: function () {{ return rail; }} }}] : [];
  }},
  getElementById: function (id) {{ return els[id] || null; }}
}};
{_dock_src()}
_dockBtns();
var out = {{}};
Object.keys(els).forEach(function (k) {{ out[k] = els[k].style; }});
console.log(JSON.stringify(out));
"""
    return json.loads(run_js(script))


RECT = {"width": 500, "height": 880, "top": 10, "bottom": 890, "right": 560, "left": 60}


def test_버튼은_영상칸_오른쪽_위에서부터_쌓인다():
    st = _run(1280, RECT)
    assert st["ss-adopt-btn"]["left"] == "576px"
    assert st["ss-adopt-btn"]["top"] == "18px"       # rect.top + 8
    assert st["ss-lens-btn"]["top"] == "70px"        # +52
    assert st["ss-grab-btn"]["top"] == "174px"
    assert st["ss-adopt-btn"]["bottom"] == "auto"


def test_없는_버튼은_빈칸을_남기지_않는다():
    """⭐레퍼런스 등록은 영상 페이지에서만 뜬다 — 없을 때 첫 칸부터 채워야 한다."""
    st = _run(1280, RECT, present=["ss-lens-btn", "ss-grab-btn"])
    assert st["ss-lens-btn"]["top"] == "18px"
    assert st["ss-grab-btn"]["top"] == "70px"


def test_시크바는_영상_아래쪽에_붙는다():
    st = _run(1280, RECT)
    assert st["ss-seek"]["bottom"] == "18px"          # innerHeight - rect.bottom + 8
    assert st["ss-seek"]["left"] == "576px"


def test_좁은_창이면_종전_오른쪽_아래_자리로_되돌린다():
    st = _run(700, {"width": 500, "height": 880, "top": 10, "bottom": 890, "right": 620, "left": 120})
    assert st["ss-grab-btn"]["right"] == "18px" and st["ss-grab-btn"]["top"] == ""


def test_영상이_없으면_종전_자리다():
    st = _run(1280, None)
    assert st["ss-grab-btn"]["right"] == "18px"
    assert st["ss-seek"]["bottom"] == "174px"


def test_유튜브_쇼츠_전체폭_조상은_무시한다():
    """실사고(2026-09-01): ytd-reel-video-renderer가 화면 전체 폭이라 버튼이
    브라우저 오른쪽 끝(주소창 밑)까지 날아갔다. 영상보다 지나치게 넓은 칸은 버린다."""
    st = _run(1800, RECT, ancestor={"width": 1800, "right": 1790, "left": 0})
    assert st["ss-grab-btn"]["left"] == "576px"      # 영상 오른쪽 + 16 (조상 무시)


def test_액션열이_형제면_그_오른쪽으로_비켜난다():
    """유튜브 쇼츠의 좋아요·공유 열은 영상 바깥에 있다 — 그 위에 얹히면 안 된다."""
    st = _run(1800, RECT, rail={"left": 570, "right": 660, "width": 90, "height": 400})
    assert st["ss-grab-btn"]["left"] == "676px"      # 액션열 오른쪽 + 16
