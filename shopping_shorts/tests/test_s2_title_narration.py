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


def _run(tail, canary=True):
    # 관리자 카나리(window.SS_CANARY)가 켜진 상태가 이 계약의 전제다. 꺼지면(고객) 옛 동작.
    return run_js(f"""
var SS_CANARY={'true' if canary else 'false'};
{_src()}
{tail}
""")


def test_카나리_제목은_첫TTS로_읽고_헤드카피로도_간다():
    out = _run("""
const target={headcopy:{font:'P',subline:'옛 문구'}};
const dr={beats:[
  {role:'title',text:'천재가 왜 게으른지 알 수 있는 제품',src_seg:'s0-1'},
  {role:'story',text:'지금 이 용도를 알 수 없는 물건이',src_seg:'s0-2'}]};
s2ApplyDraftContract(target, dr);
console.log(JSON.stringify(target));
""")
    got = json.loads(out)
    assert got["headcopy"]["text"] == "천재가 왜 게으른지 알 수 있는 제품"
    assert got["headcopy"]["subline"] == ""
    assert got["headcopy"]["font"] == "P"
    assert got["script"].splitlines() == ["천재가 왜 게으른지 알 수 있는 제품", "지금 이 용도를 알 수 없는 물건이"]


def test_카나리_밖_고객은_헤드카피를_건드리지_않는다():
    out = _run("""
const target={headcopy:{text:'원래 제목'}};
const dr={beats:[{role:'title',text:'새 제목'},{role:'story',text:'본문'}]};
s2ApplyDraftContract(target, dr);
console.log(JSON.stringify(target));
""", canary=False)
    got = json.loads(out)
    assert got["headcopy"]["text"] == "원래 제목"
    assert got["script"].splitlines() == ["새 제목", "본문"]
