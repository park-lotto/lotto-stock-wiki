"""2단계 대본 칸 추가·이동(2026-09-30 사장님 "칸을 더 만들고 중간으로 올릴 수도 있고 이동되게", 관제 044).

잠그는 계약:
  · 어느 안이든(AI 안 포함) j번째 **바로 아래**에 빈 칸이 생긴다
  · ▲▼는 칸 객체를 통째로 옮긴다 — 출처 장면(src_seg)이 글과 같이 움직인다
  · 확정 계약: 대본 줄 수 = 장면 출처 개수, 같은 순서(빈 칸이 섞여도).
    종전엔 줄만 빈 칸을 걸러 개수가 어긋났고 3단계 '붙어 온 장면 그대로'가 통째로 빠졌다
  · [바꾸기]가 도는 동안엔 칸 목록을 안 바꾼다(그 함수가 끝나며 옛 배열로 덮는다)
PRODUCE_PATH 환경변수로 다른 produce.html(예: 고치기 전 main)을 같은 검사에 태울 수 있다.
"""
import json
import os
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

PRODUCE = pathlib.Path(os.environ.get("PRODUCE_PATH") or
                       pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html")

pytestmark = requires_node


def _slice(s, a, b):
    i = s.index(a)
    return s[i:s.index(b, i)]


def _src():
    s = PRODUCE.read_text(encoding="utf-8")
    edit = _slice(s, "const S2_MINE_ROLES", "function s2PickDraft(i){")
    contract = _slice(s, "function s2ScriptLines(dr){", "function s2Confirm(i){")
    return edit + "\n" + contract


def _run(setup, tail, busy=False, translating=False):
    return run_js(f"""
var toast = function(){{}}, saveWork = function(){{}}, s2RenderDrafts = function(){{}}, s2CloseBanks = function(){{}};
var SS_CANARY = false;
var document = {{ getElementById: function(id){{ return ({str(translating).lower()} && id.indexOf('s2lang-')===0) ? {{disabled:true}} : null; }},
                  querySelector: function(q){{ return ({str(busy).lower()} && q.indexOf('s2-busy')>=0) ? {{}} : null; }},
                  querySelectorAll: function(){{ return []; }} }};
function s2Beats(dr){{ return (dr.beats && dr.beats.length) ? dr.beats : []; }}
var S2 = {setup};
{_src()}
{tail}
""")


AI = """{drafts: [{style_id: 7, checks:[{name:'x',ok:true}], passed:true, beats: [
  {role:'hook', text:'가', src_seg:'s1-1', src_segs:['s1-1']},
  {role:'problem', text:'나', src_seg:'s1-2', src_segs:['s1-2']},
  {role:'cta', text:'다', src_seg:'s1-3', src_segs:['s1-3']}]}], curDraft: 0}"""


def test_AI_안_가운데에_빈_칸이_생긴다():
    out = _run(AI, "s2AddBeat(0, 0); console.log(JSON.stringify(S2.drafts[0]));")
    dr = json.loads(out)
    assert [b["text"] for b in dr["beats"]] == ["가", "", "나", "다"]
    assert dr["beats"][1]["role"] == ""
    assert dr["checks"] == [] and dr["passed"] is False, "칸 구성이 바뀌면 옛 검사 표시는 지운다"


def test_새_칸을_위로_옮겨_가운데로_올린다_출처는_글과_같이_움직인다():
    out = _run(AI, "s2AddBeat(0, 2); S2.drafts[0].beats[3].text='새 문장'; "
                   "s2MoveBeat(0, 3, -1); s2MoveBeat(0, 2, -1); "
                   "console.log(JSON.stringify(S2.drafts[0].beats));")
    beats = json.loads(out)
    assert [b["text"] for b in beats] == ["가", "새 문장", "나", "다"]
    assert [b.get("src_seg", "") for b in beats] == ["s1-1", "", "s1-2", "s1-3"]


def test_끝에서는_더_못_옮긴다():
    out = _run(AI, "s2MoveBeat(0, 0, -1); s2MoveBeat(0, 2, 1); "
                   "console.log(JSON.stringify(S2.drafts[0].beats.map(b=>b.text)));")
    assert json.loads(out) == ["가", "나", "다"]


def test_바꾸기가_도는_동안엔_칸_목록을_안_바꾼다():
    out = _run(AI, "s2AddBeat(0, 0); s2MoveBeat(0, 0, 1); "
                   "console.log(JSON.stringify(S2.drafts[0].beats.map(b=>b.text)));", busy=True)
    assert json.loads(out) == ["가", "나", "다"]


def test_확정_계약_빈_칸이_섞여도_줄과_출처가_같은_수_같은_순서():
    """★고치기 전 코드에서 실패하는 검사다(빈 칸이 줄에서만 빠졌다)."""
    out = _run(AI, "s2AddBeat(0, 0); var st={}; s2ApplyDraftContract(st, S2.drafts[0]); "
                   "console.log(JSON.stringify(st));")
    st = json.loads(out)
    lines = st["script"].split("\n")
    srcs = st["script_beat_sources"]
    assert lines == ["가", "나", "다"]
    assert len(srcs) == len(lines), (len(srcs), len(lines))
    assert [x["seg"] for x in srcs] == ["s1-1", "s1-2", "s1-3"]


def test_확정_계약_새_칸에_글을_쓰면_그_자리에_출처_없는_줄로_들어간다():
    out = _run(AI, "s2AddBeat(0, 0); S2.drafts[0].beats[1].text='새 문장'; "
                   "var st={}; s2ApplyDraftContract(st, S2.drafts[0]); console.log(JSON.stringify(st));")
    st = json.loads(out)
    assert st["script"].split("\n") == ["가", "새 문장", "나", "다"]
    assert [x["seg"] for x in st["script_beat_sources"]] == ["s1-1", "", "s1-2", "s1-3"]


def test_화면_계약_칸마다_옮기기_추가_버튼과_모든_안의_칸추가():
    src = PRODUCE.read_text(encoding="utf-8")
    assert 'onclick="s2MoveBeat(${i},${j},-1)"' in src
    assert 'onclick="s2MoveBeat(${i},${j},1)"' in src
    assert 'onclick="s2AddBeat(${i},${j})"' in src
    assert "${dr.mine?`<button class=\"btn-ghost\" style=\"min-width:auto\" title=\"칸을 하나 더 만듭니다\"" not in src


def test_영어_변환_중엔_칸_목록을_안_바꾼다():
    """s2ToggleLang도 끝나며 잡아 둔 배열로 dr.beats를 덮는다 — 변환 중(버튼 disabled) 옮기면 사라진다."""
    out = _run(AI, "s2AddBeat(0, 0); s2MoveBeat(0, 0, 1); "
                   "console.log(JSON.stringify(S2.drafts[0].beats.map(b=>b.text)));", translating=True)
    assert json.loads(out) == ["가", "나", "다"]
