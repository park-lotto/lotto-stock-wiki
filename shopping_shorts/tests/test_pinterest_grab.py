"""핀터레스트 원클릭 담기 (2026-09-11 고객 "담기 버튼이 없다").

뿌리: 담기 스크립트가 핀터레스트를 몰랐다(@match·매니페스트·서버 _GRAB_DOMAINS 셋 다 없음).
받기(media_download._download_pinterest)는 이미 있었으니 세 곳을 짝으로 연다.
"""
from pathlib import Path

from shopping_shorts.app import _grab_platform

_ROOT = Path(__file__).resolve().parents[1]


def test_서버가_핀터레스트_주소를_안다():
    assert _grab_platform("https://www.pinterest.com/pin/768074911447008679/") == "pinterest"
    assert _grab_platform("https://kr.pinterest.com/pin/699113542148777443/") == "pinterest"


def test_로더와_확장이_핀터레스트에서_뜬다():
    loader = (_ROOT / "userscript" / "grab.user.js").read_text(encoding="utf-8")
    assert "// @match        https://*.pinterest.com/*" in loader
    assert "@version      2.5.0" in loader, "@match가 바뀌면 버전을 올려야 자동업데이트가 돈다"
    man = (_ROOT / "extension" / "manifest.json").read_text(encoding="utf-8")
    assert '"https://*.pinterest.com/*"' in man


def test_로직에_핀_카드버튼과_플로팅_규칙이_있다():
    logic = (_ROOT / "userscript" / "grab_logic.js").read_text(encoding="utf-8")
    assert "function addPinCardBtns()" in logic and "try{addPinCardBtns();}" in logic
    # 플로팅 표시 판단은 _floatWanted 한 곳(2026-10-03) — 핀터레스트는 핀 상세에서만.
    assert "if (_isPin()) return _pinSingle();" in logic and "function syncPinFloat" not in logic
    import re
    ver = int(re.search(r"var LOGIC_VER = (\d+);", logic).group(1))
    assert ver >= 20260928, "LOGIC_VER를 올려야 옛 로직을 이긴다"


def test_핀터레스트_직접영상주소를_담기에_보낸다():
    logic = (_ROOT / "userscript" / "grab_logic.js").read_text(encoding="utf-8")
    assert '"pinimg.com"' in logic
    assert 'direct.indexOf("pinimg.com") >= 0 ? direct : ""' in logic


def _pin_url(card_js, path="/"):
    import json as _j
    from shopping_shorts.tests.js_harness import run_js
    logic = (_ROOT / "userscript" / "grab_logic.js").read_text(encoding="utf-8")
    i = logic.index("  function _pinCardUrl(c)")
    src = logic[i:logic.index("  function addPinCardBtns()", i)]
    return _j.loads(run_js("var location={origin:'https://kr.pinterest.com',pathname:%s};\n%s\n"
                           "console.log(JSON.stringify(_pinCardUrl(%s)));" % (_j.dumps(path), src, card_js)))


def _card(href, holder_id):
    a = "{href:'https://kr.pinterest.com%s'}" % href if href else "null"
    h = "{getAttribute:function(){return %s;}}" % ("'" + holder_id + "'" if holder_id else "''")
    return "{querySelector:function(){return %s;},closest:function(){return %s;}}" % (a, h)


def test_일반핀은_카드의_핀링크를_쓴다():
    import pytest
    from shopping_shorts.tests.js_harness import NODE
    if NODE is None:
        pytest.skip("node 없음")
    assert _pin_url(_card("/pin/300404237670056222/", "300404237670056222")) ==         "https://kr.pinterest.com/pin/300404237670056222/"


def test_후원핀은_감싼칸의_고유번호로_핀주소를_만든다():
    import pytest
    from shopping_shorts.tests.js_harness import NODE
    if NODE is None:
        pytest.skip("node 없음")
    eid = "AVkrxFMWhAXZcimnAqXlD5fwRtfS6vBNyr69aJCP5dG2qnEBwbkrvR4kODx613meGCRNZhWjiwyYBKdi5rvtyHA"
    assert _pin_url(_card("", eid)) == "https://kr.pinterest.com/pin/%s/" % eid
    assert _pin_url(_card("", "")) == ""
