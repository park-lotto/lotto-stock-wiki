# -*- coding: utf-8 -*-
"""가로형(롱폼)은 1단계에서 막는다 (2026-09-03 사장님 "매칭에서 막으니까 돌아오게 되니까").

종전: 1단계는 배지만 붙이고, 3단계 믹스(_block_landscape)에서야 실패 → 분석·다운로드 다 치르고
1단계로 되돌아와야 했다. 이제 분석 결과(landscape:true)가 오는 순간 재료에서 빼고 다시 못 고른다.
판정은 서버 값 그대로(0순위-B) — 화면은 w/h를 다시 재지 않는다. null(못 잼)은 막지 않는다.
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node
HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _src():
    s = HTML.read_text(encoding="utf-8")
    a = s.index("function _applyLandscapeGate(code, d){")
    b = s.index("// ✕ = 이 영상을 재료에서", a)
    return s[a:b]


def _run(handoff, brief, then=""):
    script = f"""
var HANDOFF = {json.dumps(handoff)};
var toasts = [], renders = 0, saves = 0;
function toast(m){{ toasts.push(m); }}
function renderPool(){{ renders++; }}
function saveWork(){{ saves++; }}
{_src()}
var changed = _applyLandscapeGate("abc", {json.dumps(brief)});
{then}
console.log(JSON.stringify({{HANDOFF: HANDOFF, toasts: toasts, renders: renders, saves: saves, changed: changed}}));
"""
    return json.loads(run_js(script))


def test_가로형이면_담김과_메인을_풀고_표식을_남긴다():
    st = _run([{"shortcode": "abc", "useFootage": True, "bbMain": True},
               {"shortcode": "xyz", "useFootage": True}],
              {"ok": True, "landscape": True, "video_w": 1920, "video_h": 1080})
    h = st["HANDOFF"][0]
    assert h["landscape"] is True and h["useFootage"] is False and h["bbMain"] is False
    assert st["HANDOFF"][1]["useFootage"] is True          # 다른 영상은 그대로
    assert st["changed"] and st["renders"] == 1 and st["saves"] == 1
    assert "1920x1080" in st["toasts"][0]


def test_세로형이나_못잰것은_건드리지_않는다():
    for brief in ({"ok": True, "landscape": False}, {"ok": True, "landscape": None}, None):
        st = _run([{"shortcode": "abc", "useFootage": True}], brief)
        assert st["HANDOFF"][0]["useFootage"] is True and not st["changed"], brief
        assert st["toasts"] == []


def test_가로형은_다시_골라도_담기지_않는다():
    st = _run([{"shortcode": "abc", "useFootage": True}],
              {"ok": True, "landscape": True},
              then="pickFootage(0);")
    h = st["HANDOFF"][0]
    assert h["useFootage"] is False and not h.get("bbMain")
    assert len(st["toasts"]) == 2 and "못 씁니다" in st["toasts"][1]


def test_호출부가_실제로_걸려_있다():
    s = HTML.read_text(encoding="utf-8")
    assert "_applyLandscapeGate(code, d);" in s, "source_brief 적재 뒤에 게이트를 안 부른다"
    assert "it.landscape?' lscape'" in s, "카드에 가로형 표식이 없다"
