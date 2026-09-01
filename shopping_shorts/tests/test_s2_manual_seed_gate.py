"""「직접 쓰기」 대본이 생성에서 막히던 것(2026-09-01 사장님 제보).

증상: 대본을 붙여넣어도 "먼저 씨앗 영상을 고르세요 (직접 쓴 대본은 아직 생성 대상이
아닙니다)"가 뜨고 만들기가 안 됐다. 서버(api_wiki_generate)는 원래부터 shortcode 없이
base_script만으로 생성한다 — 막고 있던 건 화면의 판정 한 줄이었다.
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

pytestmark = requires_node


def _gate_src():
    src = PRODUCE.read_text(encoding="utf-8")
    i = src.index("function s2SeedReady(s){")
    j = src.index("}", src.index("return !!(s &&", i)) + 1
    return src[i:j]


def _ready(seed):
    out = run_js(_gate_src() + f"\nconsole.log(JSON.stringify(s2SeedReady({json.dumps(seed)})));\n")
    return json.loads(out)


def test_직접_쓴_대본도_생성할_수_있다():
    assert _ready({"shortcode": "", "text": "안녕하세요 반갑습니다 로켓이에요"}) is True


def test_담긴_영상_씨앗은_종전대로():
    assert _ready({"shortcode": "Cabc123", "text": ""}) is True


def test_아무것도_없으면_막는다():
    assert _ready({"shortcode": "", "text": "   "}) is False
    assert _ready(None) is False


def test_안내문구가_직접쓰기를_가리킨다():
    """'직접 쓴 대본은 생성 대상이 아니다'는 이제 사실이 아니다 — 남아 있으면 안 된다."""
    src = PRODUCE.read_text(encoding="utf-8")
    assert "직접 쓴 대본은 아직 생성 대상이 아닙니다" not in src
    assert "「직접 쓰기」" in src
