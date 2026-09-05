"""✍ 내가 직접 쓰기 — 각색 없이 내 문장이 그대로 대본이 되는 안(2026-09-01 사장님).

"그냥 내 대본을 그대로 하고 싶을 때 빈칸으로 자리를 만들어주고 쓸 수 있게."
AI를 부르지 않는다 = 결과가 사장님이 친 그대로여야 한다. 그 계약을 여기서 잠근다.
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

pytestmark = requires_node


def _src():
    s = PRODUCE.read_text(encoding="utf-8")
    i = s.index("const S2_MINE_ROLES")
    j = s.index("function s2PickDraft(i){", i)
    return s[i:j]


def _run(setup, tail):
    return run_js(f"""
var toast = function(){{}}, saveWork = function(){{}}, s2RenderDrafts = function(){{}};
var document = {{ getElementById: function(){{ return null; }},
                  querySelector: function(){{ return null; }},
                  querySelectorAll: function(){{ return []; }} }};
function s2Beats(dr){{ return (dr.beats && dr.beats.length) ? dr.beats : []; }}
var S2 = {setup};
{_src()}
{tail}
""")


def test_스타일을_안_골랐으면_기본_뼈대로_칸을_만든다():
    out = _run("{drafts: [], curDraft: 0}",
               "s2AddMineDraft(); console.log(JSON.stringify(S2.drafts[0]));")
    dr = json.loads(out)
    assert dr["mine"] is True
    assert [b["role"] for b in dr["beats"]] == ["hook", "problem", "method", "proof", "cta"]
    assert all(b["text"] == "" for b in dr["beats"]), "칸은 비어 있어야 한다(AI가 채우지 않는다)"
    assert dr["script"] == ""


def test_보던_안이_있으면_그_칸_구성을_그대로_따른다():
    out = _run("""{drafts: [{beats: [{role:'title',text:'가'},{role:'story',text:'나'},
                                     {role:'cta',text:'다'}]}], curDraft: 0}""",
               "s2AddMineDraft(); console.log(JSON.stringify(S2.drafts[1].beats.map(b=>b.role)));")
    assert json.loads(out) == ["title", "story", "cta"]


def test_내_대본을_또_눌러도_그_빈칸을_다시_베끼지_않는다():
    """내 대본(빈 칸)을 보던 중에 또 누르면 역할이 빈 칸만 복사돼 이름 없는 칸이 된다."""
    out = _run("{drafts: [], curDraft: 0}",
               "s2AddMineDraft(); s2AddMineDraft(); "
               "console.log(JSON.stringify(S2.drafts[1].beats.map(b=>b.role)));")
    assert json.loads(out) == ["hook", "problem", "method", "proof", "cta"]


def test_칸_추가는_빈_칸을_하나_더_만든다():
    out = _run("{drafts: [], curDraft: 0}",
               "s2AddMineDraft(); s2MineAddRow(0); "
               "console.log(JSON.stringify(S2.drafts[0].beats.length));")
    assert json.loads(out) == 6


def test_남의_안에는_칸을_더하지_않는다():
    """AI가 만든 안은 게이트·역할 계약이 있다 — 여기서 임의로 칸을 늘리지 않는다."""
    out = _run("{drafts: [{beats:[{role:'hook',text:'가'}]}], curDraft: 0}",
               "s2MineAddRow(0); console.log(JSON.stringify(S2.drafts[0].beats.length));")
    assert json.loads(out) == 1


def test_화면_계약_내_대본은_게이트도_다시만들기도_안_붙는다():
    src = PRODUCE.read_text(encoding="utf-8")
    assert "const gate=dr.mine?''" in src
    assert "const fix=(!dr.mine &&" in src
    assert "내 대본으로 확정" in src
    assert ".s2-sent:empty::before" in src      # 빈 칸 안내


def test_내_대본은_빈_칸도_뺄_수_있다():
    """사장님 제보: 한 칸만 쓴 상태에서 나머지 빈 칸이 하나도 안 빠졌다.
    글자 수로 세던 가드가 원인 — 내 대본은 '칸 수'로 센다."""
    src = PRODUCE.read_text(encoding="utf-8")
    assert "const _left = dr.mine ? beats.length" in src
    assert "if(txt && !confirm(" in src, "빈 칸은 확인창 없이 바로 빠져야 한다"
