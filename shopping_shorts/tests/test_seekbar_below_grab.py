# -*- coding: utf-8 -*-
"""재생바는 담기 버튼(도킹 줄 맨 아래) 바로 밑에 붙고, 검은 판으로 늘어나지 않는다.

2026-09-02~03 사장님 스샷 3장: 재생바 밑으로 시커먼 판이 영상 바닥까지 깔렸다.
뿌리 = 자리를 **두 함수**(_placeSeekBar: top+right / _dockBtns: left+bottom)가 같은 tick에서
따로 정해 top·bottom·left·right가 넷 다 걸린 것. 고정 배치에서 top과 bottom이 같이 걸리면
그 사이만큼 상자가 늘어난다. 처방 = 자리 결정을 _dockBtns 한 곳으로(0순위-B).

이 시험은 **버튼 도킹과 시크바 배치를 실제 순서대로 함께 돌린 뒤** 최종 스타일을 본다 —
좌표 함수 하나만 떼어 돌리면 두 함수가 싸우는 걸 못 잡는다(어제 그렇게 놓쳤다).
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

LOGIC = pathlib.Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"
RECT = {"width": 500, "height": 880, "top": 100, "bottom": 890, "right": 560, "left": 60}


def _dock_src():
    src = LOGIC.read_text(encoding="utf-8")
    i = src.index("  var DOCK_IDS")
    j = src.index("function tick()", i)
    return src[i:j]


def _run(present, video_rect=RECT, inner_width=1280, seek_init=None):
    script = f"""
var window = {{ innerWidth: {inner_width}, innerHeight: 900 }};
var vid = {{ getBoundingClientRect: function () {{ return {json.dumps(video_rect)}; }},
            parentElement: null }};
var els = {{}};
{json.dumps(present)}.forEach(function (id) {{ els[id] = {{ offsetWidth: 150, style: {{}} }}; }});
if (els["ss-seek"]) Object.assign(els["ss-seek"].style, {json.dumps(seek_init or {})});
var document = {{
  querySelectorAll: function (sel) {{ return sel === "video" && {'true' if video_rect else 'false'} ? [vid] : []; }},
  getElementById: function (id) {{ return els[id] || null; }}
}};
{_dock_src()}
_dockBtns();
var out = {{}};
Object.keys(els).forEach(function (k) {{ out[k] = els[k].style; }});
console.log(JSON.stringify(out));
"""
    return json.loads(run_js(script))


def test_담기_버튼_바로_아래_한_칸():
    st = _run(["ss-lens-btn", "ss-chadd-btn", "ss-grab-btn", "ss-seek"])
    assert st["ss-grab-btn"]["top"] == "212px"       # 108 + 2*52
    assert st["ss-seek"]["top"] == "264px"           # 담기 한 칸(52px) 아래
    assert st["ss-seek"]["left"] == st["ss-grab-btn"]["left"]


def test_top과_bottom이_동시에_걸리지_않는다():
    """첫 그림 초기값(bottom:174px)이 남아 있어도 도킹 뒤엔 반드시 풀려야 한다."""
    st = _run(["ss-grab-btn", "ss-seek"], seek_init={"bottom": "174px", "right": "18px"})
    sk = st["ss-seek"]
    assert sk["top"].endswith("px") and sk["bottom"] == "auto", sk
    assert sk["left"].endswith("px") and sk["right"] == "auto", sk
    assert sk["height"] == "auto" and sk["maxHeight"] == "none", sk


def test_영상이_없으면_종전_자리로_되돌리며_top은_푼다():
    st = _run(["ss-grab-btn", "ss-seek"], video_rect=None, seek_init={"top": "300px", "left": "500px"})
    sk = st["ss-seek"]
    assert sk["bottom"] == "174px" and sk["right"] == "18px", sk
    assert sk["top"] == "" and sk["left"] == "", sk


def test_자리를_정하는_함수는_하나뿐():
    """_placeSeekBar 같은 두 번째 자리 함수가 다시 생기면 검은 판이 재발한다."""
    src = LOGIC.read_text(encoding="utf-8")
    assert "function _placeSeekBar" not in src
    a = src.index("  function syncSeekBar()")
    b = src.index(chr(10) + "  function ", a + 10)
    body = src[a:b]
    for k in ("style.top", "style.bottom", "style.left", "style.right", "setProperty"):
        assert k not in body, "syncSeekBar가 자리를 건드린다: " + k
