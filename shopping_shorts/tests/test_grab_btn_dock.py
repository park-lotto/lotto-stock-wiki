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
         ancestor=None, rail=None, ancestor_textarea=False):
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
                         querySelector: function () {{ return {'{}' if ancestor_textarea else 'null'}; }},
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
// 자리 판단만 잰다 — 표시 여부(_floatWanted)는 주인 함수 몫이라 '띄운다'로 고정.
var location = {{ host: "www.instagram.com", pathname: "/reel/x/" }};
function _floatWanted() {{ return true; }}
{_dock_src()}
_dockBtns();
var out = {{}};
Object.keys(els).forEach(function (k) {{ out[k] = els[k].style; }});
console.log(JSON.stringify(out));
"""
    return json.loads(run_js(script))


# ★영상 칸은 사이트 **헤더 아래**에서 시작한다(인스타·유튜브 모두 60px 안팎).
#   종전 top:10은 헤더 위라 현실에 없는 배치였고, 그 값에 맞춘 기대값 때문에
#   "헤더를 덮지 마라"는 새 규칙이 회귀처럼 보였다.
RECT = {"width": 500, "height": 880, "top": 100, "bottom": 890, "right": 560, "left": 60}


def test_버튼은_영상칸_오른쪽_위에서부터_쌓인다():
    st = _run(1280, RECT)
    assert st["ss-adopt-btn"]["left"] == "576px"
    assert st["ss-adopt-btn"]["top"] == "108px"      # rect.top + 8
    assert st["ss-lens-btn"]["top"] == "160px"       # +52
    assert st["ss-grab-btn"]["top"] == "264px"
    assert st["ss-adopt-btn"]["bottom"] == "auto"


def test_없는_버튼은_빈칸을_남기지_않는다():
    """⭐레퍼런스 등록은 영상 페이지에서만 뜬다 — 없을 때 첫 칸부터 채워야 한다."""
    st = _run(1280, RECT, present=["ss-lens-btn", "ss-grab-btn"])
    assert st["ss-lens-btn"]["top"] == "108px"
    assert st["ss-grab-btn"]["top"] == "160px"


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


def test_버튼이_사이트_헤더를_덮지_않는다():
    """2026-09-02 사장님 "이거때매 계정 눌러지지가 않는다".

    영상이 화면 위로 올라가면 버튼이 top:8까지 붙어 인스타 헤더의 계정 아이콘을
    덮었다. 헤더(60px 안팎) 아래로만 내려온다.
    """
    up = dict(RECT, top=-200, bottom=680)      # 스크롤로 영상이 위로 밀린 상태
    st = _run(1280, up)
    assert st["ss-adopt-btn"]["top"] == "72px", st["ss-adopt-btn"]


def test_시크바는_담기_버튼_아래_한_칸():
    """2026-09-03: 영상 아래쪽(bottom)이 아니라 담기 버튼 밑(top)이다. bottom은 auto."""
    st = _run(1280, RECT)
    assert st["ss-seek"]["top"] == "316px"           # 264(담기) + 52
    assert st["ss-seek"]["bottom"] == "auto"
    assert st["ss-seek"]["left"] == "576px"


def test_릴_직접주소_화면은_댓글판_바깥_오른쪽으로():
    """/reel/ 직접 주소: dialog·article이 아닌 칸이 영상+댓글판을 감싼다(2026-09-03 사장님 스샷).
    댓글 입력창(textarea)을 품은 칸이면 그 오른쪽 바깥으로 넘긴다."""
    st = _run(1673, RECT, ancestor={"width": 940, "right": 1345, "left": 405}, ancestor_textarea=True)
    assert st["ss-grab-btn"]["left"] == "1361px"     # 1345 + 16


def test_화면_거의_전체를_덮는_칸은_textarea가_있어도_버린다():
    st = _run(1673, RECT, ancestor={"width": 1600, "right": 1650, "left": 50}, ancestor_textarea=True)
    assert st["ss-grab-btn"]["left"] == "576px"


def _run_modal(inner_width, depth=14, panel_left=1079, ta_left=1137):
    """인스타 팝업 새 구조(2026-10-03 라이브 실측, 게시물 CcfWWv2lviz):
    영상 → 영상 폭 칸 14겹 → 화면보다 넓은 칸(자식 = 영상 칸 + 본문 칸) → ARTICLE → dialog.
    본문 칸 안에 댓글 입력창(textarea)이 있다."""
    script = f"""
var window = {{ innerWidth: {inner_width}, innerHeight: 1012 }};
function R(l, r, t, b) {{ return {{ left: l, right: r, width: r - l, top: t, bottom: b, height: b - t }}; }}
function N(rect, parent, ta) {{
  return {{ tagName: "DIV", getAttribute: function () {{ return null; }},
           getBoundingClientRect: function () {{ return rect; }},
           querySelector: function () {{ return ta || null; }}, parentElement: parent }};
}}
var ta = {{ getBoundingClientRect: function () {{ return R({ta_left}, {ta_left} + 393, 953, 971); }} }};
var dialog = N(R(0, {inner_width} - 15, 0, 1012), null, ta);
var wide = N(R(-114, {inner_width} + 99, 24, 988), dialog, ta);
var panel = N(R({panel_left}, {panel_left} + 500, 24, 988), wide, ta);
ta.parentElement = N(R({panel_left} + 2, {panel_left} + 484, 942, 982), panel, ta);
var p = wide;
for (var n = 0; n < {depth}; n++) p = N(R(537, 1079, 24, 988), p, null);
var vid = {{ getBoundingClientRect: function () {{ return R(537, 1079, 24, 988); }}, parentElement: p }};
var els = {{}};
["ss-adopt-btn", "ss-lens-btn", "ss-chadd-btn", "ss-grab-btn", "ss-seek"].forEach(function (id) {{
  els[id] = {{ offsetWidth: 150, style: {{}} }};
}});
var document = {{
  querySelectorAll: function (sel) {{ return sel === "video" ? [vid] : []; }},
  getElementById: function (id) {{ return els[id] || null; }}
}};
var location = {{ host: "www.instagram.com", pathname: "/p/x/" }};
function _floatWanted() {{ return true; }}
{_dock_src()}
_dockBtns();
var out = {{}};
Object.keys(els).forEach(function (k) {{ out[k] = els[k].style; }});
console.log(JSON.stringify(out));
"""
    return json.loads(run_js(script))


def test_인스타_팝업은_본문칸_바깥_오른쪽으로():
    """2026-10-03 사장님 스샷: 버튼·속도창이 본문 글자를 덮었다. 팝업 칸이 15겹째로 깊어졌고
    그 칸은 화면보다 넓어 못 쓴다 — 댓글 입력창이 든 본문 칸의 오른쪽 끝이 기준이다."""
    st = _run_modal(1920)
    for k in ("ss-adopt-btn", "ss-lens-btn", "ss-chadd-btn", "ss-grab-btn", "ss-seek"):
        assert st[k]["left"] == "1595px", (k, st[k])     # 본문 칸 오른쪽(1579) + 16


def test_댓글창이_영상_아래면_본문칸으로_치지_않는다():
    """피드처럼 댓글 입력창이 영상 아래(오른쪽이 아님)에 있으면 종전 자리(영상 오른쪽)다."""
    st = _run_modal(1920, panel_left=537, ta_left=560)
    assert st["ss-grab-btn"]["left"] == "1095px"         # 영상 오른쪽(1079) + 16


def test_팝업_오른쪽_여백이_모자라면_종전_자리로_물러난다():
    st = _run_modal(1700)                                # 1579+16+150+12 > 1700
    assert st["ss-grab-btn"]["right"] == "18px"
