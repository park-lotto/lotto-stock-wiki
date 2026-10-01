"""유튜브 검색 결과(/results)에서 쇼츠 카드마다 📥 (2026-10-01 사장님, 관제 060).

렌즈 키워드 검색이 유튜브 검색 결과로 보내는데, 09-02 '쇼츠에서만' 규칙(_ytOff)이
/results를 통째로 꺼서 담기가 하나도 안 떴다. 검색 화면은 플로팅 없이 쇼츠 카드 버튼만.
실크롬 실측: 수정 전 카드 0개 → 수정 후 15·20개, 클릭 시 /api/grab?url=.../shorts/ID.
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

LOGIC = pathlib.Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"


def _fn(name, nxt):
    s = LOGIC.read_text(encoding="utf-8")
    i = s.index("  function %s()" % name)
    return s[i:s.index(nxt, i)]


def _judge(host, pathname, duration=0):
    src = _fn("_ytResults", "  // 유튜브 비대상 화면")
    script = f"""
var location = {{host: {json.dumps(host)}, pathname: {json.dumps(pathname)}}};
var document = {{querySelector: function () {{ return {{duration: {duration}}}; }}}};
{src}
console.log(JSON.stringify({{results: _ytResults(), off: _ytOff()}}));
"""
    return json.loads(run_js(script))


def test_검색결과는_켜지고_카드모드다():
    assert _judge("www.youtube.com", "/results") == {"results": True, "off": False}


def test_메인과_롱폼은_여전히_꺼진다():
    assert _judge("www.youtube.com", "/")["off"] is True
    assert _judge("www.youtube.com", "/watch", duration=600)["off"] is True


def test_쇼츠는_종전대로_켜지고_카드모드가_아니다():
    assert _judge("www.youtube.com", "/shorts/abc") == {"results": False, "off": False}


def test_검색결과에서는_쇼츠링크만_잡고_플로팅을_걷는다():
    s = LOGIC.read_text(encoding="utf-8")
    assert "_ytResults() ? 'a[href*=\"/shorts/\"]'" in s
    assert "if (_ytResults()) { _ytResultsTick(); return; }" in s
