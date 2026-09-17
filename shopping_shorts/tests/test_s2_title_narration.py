"""2단계 확정 시 화면 제목이 TTS로 읽히는 회귀를 막는다."""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
pytestmark = requires_node


def _src():
    src = PRODUCE.read_text(encoding="utf-8")
    start = src.index("function s2ScriptLines(dr)")
    end = src.index("function s2Confirm(i)", start)
    return src[start:end]


def _run(tail):
    return run_js(f"""
{_src()}
{tail}
""")


def test_화면제목은_대본에서_빠지고_첫tts후킹부터_시작한다():
    out = _run("""
const dr={beats:[
  {role:'title',text:'독일 개발자도 놀란 기차 케이크',src_seg:'s0-1'},
  {role:'hook',text:'근데 이 케이크는 자르고 나서가 더 놀라워요.',src_seg:'s0-2'},
  {role:'story',text:'장난감 대신 케이크 위 기차가 움직여요.',src_seg:'s0-3'}]};
console.log(JSON.stringify(s2DraftContract(dr)));
""")
    got = json.loads(out)
    assert got["visualTitle"] == "독일 개발자도 놀란 기차 케이크"
    assert got["script"].splitlines() == [
        "근데 이 케이크는 자르고 나서가 더 놀라워요.",
        "장난감 대신 케이크 위 기차가 움직여요.",
    ]
    assert [b["role"] for b in got["narrationBeats"]] == ["hook", "story"]


def test_확정계약은_제목을_헤드카피로_보내고_장면출처도_tts와_맞춘다():
    out = _run("""
const target={headcopy:{font:'Pretendard',subline:'옛 문구'}};
const dr={beats:[
  {role:'title',text:'움직이는 기차 케이크',src_seg:'s0-1'},
  {role:'hook',text:'아이들이 촛불보다 먼저 이것부터 봐요.',src_seg:'s0-2',src_segs:['s0-2']},
  {role:'story',text:'레일을 올리면 기차가 케이크 위를 돌아요.',src_seg:'s0-3'}]};
s2ApplyDraftContract(target,dr);
console.log(JSON.stringify(target));
""")
    got = json.loads(out)
    assert got["headcopy"] == {
        "font": "Pretendard", "text": "움직이는 기차 케이크", "subline": ""}
    assert got["script"].startswith("아이들이 촛불보다")
    assert [b["role"] for b in got["script_beat_sources"]] == ["hook", "story"]


def test_역할없는_옛대본은_그대로_둔다():
    out = _run("console.log(JSON.stringify(s2ScriptLines({script:'첫 줄\\n둘째 줄',beats:[]}))); ")
    assert json.loads(out) == "첫 줄\n둘째 줄"

