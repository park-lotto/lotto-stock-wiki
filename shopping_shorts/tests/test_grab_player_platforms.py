"""시크바·렌즈가 도는 플랫폼 판정 — 유튜브·쓰레드까지(2026-09-01 사장님 요청).

"유튜브도 렌즈랑 재생속도 등 추가하고 위치·기능 다 인스타랑 같게."
종전엔 `_snsHost()`(인스타·틱톡)로 막혀 유튜브 쇼츠엔 🔍렌즈·시크바가 아예 안 떴다.
판정은 `_playerPlat()`/`_pageKey()` 한 곳뿐 — 여기가 바뀌면 두 기능이 함께 바뀐다.
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

LOGIC = pathlib.Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"


def _src():
    s = LOGIC.read_text(encoding="utf-8")
    i = s.index("  function _playerPlat()")
    j = s.index("  function _ttProfile()", i)
    return s[i:j]


def _run(host, pathname, search=""):
    script = f"""
var location = {{ host: {json.dumps(host)}, pathname: {json.dumps(pathname)},
                 search: {json.dumps(search)} }};
{_src()}
console.log(JSON.stringify({{plat: _playerPlat(), key: _pageKey()}}));
"""
    return json.loads(run_js(script))


def test_유튜브_쇼츠():
    r = _run("www.youtube.com", "/shorts/abc123")
    assert r["plat"] == "youtube" and r["key"] == "/shorts/abc123"


def test_유튜브_watch는_v파라미터로_키를_만든다():
    r = _run("www.youtube.com", "/watch", "?v=dQw4w9WgXcQ&t=3")
    assert r["plat"] == "youtube" and r["key"] == "/watch/dQw4w9WgXcQ"


def test_쓰레드_게시물():
    r = _run("www.threads.com", "/@someone/post/XYZ_1")
    assert r["plat"] == "threads" and r["key"] == "/@someone/post/XYZ_1"


def test_인스타_릴스는_종전대로():
    r = _run("www.instagram.com", "/reel/CxYz123/")
    assert r["plat"] == "instagram" and r["key"] == "/reel/CxYz123"


def test_틱톡_영상():
    r = _run("www.tiktok.com", "/@u/video/7300000000000000000")
    assert r["plat"] == "tiktok" and r["key"].startswith("/video/")


def test_모르는_사이트는_안_붙인다():
    r = _run("example.com", "/watch", "?v=abc")
    assert r["plat"] == "" and r["key"] == ""


def test_재생속도_버튼이_시크바에_있다():
    """버튼이 빠지면 속도 조절이 통째로 사라진다 — 존재 자체가 계약."""
    src = LOGIC.read_text(encoding="utf-8")
    assert "id='ss-seek-x'" in src
    assert "vv.playbackRate = SPEEDS[" in src
