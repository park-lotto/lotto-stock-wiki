"""유튜브 검색 → 쇼츠로 가면 📥 담기가 사라지던 것 + 미리보기가 카드 📥를 덮던 것 (2026-10-07 사장님, 관제 150).

① 유튜브는 검색 화면을 지우지 않고 숨긴다 → 숨은 카드 📥가 남아 _floatWanted가 '그리드'로 오판.
   실크롬 실측: 수정 전 ss-grab-btn display:none(숨은 카드 22개) → 수정 후 보임.
② 카드에 마우스를 올리면 미리보기 영상(ytd-app #video-preview)이 카드 📥 위를 덮는다.
   실측: 수정 전 버튼 자리 맨 위 = video-stream → 수정 후 미리보기 안 📥(클릭 → /api/grab 쇼츠 주소).
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

LOGIC = pathlib.Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"


def _float_wanted(pathname, cards):
    """cards: 각 카드 📥가 화면에 그려졌나(True) 숨었나(False)."""
    s = LOGIC.read_text(encoding="utf-8")
    i = s.index("  function _floatWanted()")
    src = s[i:s.index("  // 검색·탐색 '그리드' 페이지에서만", i)]
    bs = ",".join("{getClientRects:function(){return %s;}}" % ("[1]" if c else "[]") for c in cards)
    script = f"""
var location = {{host: "www.youtube.com", pathname: {json.dumps(pathname)}}};
var _bs = [{bs}];
var document = {{
  querySelector: function (q) {{ return q === ".ss-card-grab" ? (_bs[0] || null) : null; }},
  querySelectorAll: function (q) {{ return q === ".ss-card-grab" ? _bs : []; }}
}};
function _isPin() {{ return false; }}
{src}
console.log(JSON.stringify(_floatWanted()));
"""
    return json.loads(run_js(script))


def test_숨은_검색카드가_남아도_쇼츠화면_담기는_보인다():
    assert _float_wanted("/shorts/abc", [False] * 22) is True


def test_화면에_보이는_카드가_있으면_종전대로_숨긴다():
    assert _float_wanted("/explore", [False, True]) is False


def test_미리보기_담기는_카드와_같은_영상만_집는다():
    s = LOGIC.read_text(encoding="utf-8")
    i = s.index("  function _ytVid(")
    src = s[i:s.index("  function _ytPreviewBtn()", i)]
    script = src + """
function A(h){return {getAttribute:function(){return h;}};}
var cards=[A("/shorts/AAAAAAA"), A("/watch?v=BBBBBBB&pp=x")];
var document={querySelectorAll:function(){return cards;}};
function pv(h){return {querySelector:function(){return h?A(h):null;}};}
console.log(JSON.stringify([
  _ytPreviewCard(pv("/shorts/AAAAAAA"))===cards[0],
  _ytPreviewCard(pv("/watch?v=BBBBBBB"))===cards[1],
  _ytPreviewCard(pv("/watch?v=CCCCCCC")),
  _ytPreviewCard(pv(null))]));
"""
    assert json.loads(run_js(script)) == [True, True, None, None]


def test_검색화면_tick이_미리보기_담기를_돈다():
    s = LOGIC.read_text(encoding="utf-8")
    i = s.index("  function _ytResultsTick()")
    assert "_ytPreviewBtn()" in s[i:s.index("  function tick()", i)]
