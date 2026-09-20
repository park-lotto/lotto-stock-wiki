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


# ── 카드 선택 표시(2026-09-01 2차 제보: "씨앗이 내 대본인데 씨앗을 고르라고 한다") ──
def _seed_on_src():
    src = PRODUCE.read_text(encoding="utf-8")
    i = src.index("function s2SeedOn(i){")
    j = src.index("\n}", i) + 2
    return src[i:j]


def _on(seeds, seed):
    out = run_js(f"""
var S2 = {{seeds: {json.dumps(seeds)}, seed: null}};
S2.seed = {json.dumps(seed)};
{_seed_on_src()}
console.log(JSON.stringify(S2.seeds.map(function(_, i){{ return s2SeedOn(i); }})));
""")
    return json.loads(out)


MANUAL = {"shortcode": "", "text": "화물트럭 케이크 모양 보셨나요", "manual": True}
VIDEOS = [{"shortcode": "A1", "text": "영상1", "pick": True},
          {"shortcode": "B2", "text": "영상2", "pick": False}]


def test_내_대본이_씨앗이면_영상카드는_다_꺼진다():
    """종전엔 대표(AI PICK) 카드가 켜진 것처럼 보여 화면이 거짓말을 했다."""
    assert _on(VIDEOS + [MANUAL], MANUAL) == [False, False, True]


def test_영상을_고르면_내_대본_카드는_꺼진다():
    assert _on(VIDEOS + [MANUAL], VIDEOS[1]) == [False, True, False]


def test_아무것도_안_골랐으면_대표가_켜진다():
    assert _on(VIDEOS, None) == [True, False]


def test_직접_쓴_씨앗은_목록을_다시_그려도_남는다():
    """s2RenderSeeds가 매번 S2.seeds를 새로 만든다 — 다시 얹지 않으면 카드가 사라진다."""
    src = PRODUCE.read_text(encoding="utf-8")
    assert "S2.seeds.push(S2.manualSeed)" in src
