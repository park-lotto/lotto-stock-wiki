"""제작소 — 조합 생성(genMix)이 초 선택값 + 선택 대본 본문(sources)을 그대로 실어 보낸다(2026-07-18).

백엔드(Task A)는 이미 인라인 sources를 받도록 완료됨(/api/produce/script/mix, sources 필드).
이 테스트는 프론트 genMix()가 shortcodes 대신 sources를 보내고, mixSeconds select 값을
target_seconds로 넘기는지를 실소스 앵커 슬라이스로 검증한다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_START = "function genMix(){"
_END = "// ── 1단계 제작소: 영상믹스"


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER_TMPL = r"""
(function(){
  // ── DOM/전역 스텁 ──
  global.window = global;
  global.document = {};
  window._mixItems = [
    {shortcode:'sc1', name:'영상A', category:'요리', full_text:'대본A 본문입니다'},
    {shortcode:'sc2', name:'영상B', category:'청소', full_text:'대본B 본문입니다'},
    {shortcode:'sc3', name:'영상C(본문없음)', category:'요리', full_text:''},
  ];
  const CHECKED = %(checked)s;
  const SECONDS = %(seconds)s;
  document.querySelectorAll = (sel) => {
    if(sel === '.mixPick:checked') return CHECKED.map(v => ({value:v}));
    return [];
  };
  document.getElementById = (id) => {
    if(id === 'mixDrafts') return { innerHTML: '' };
    if(id === 'mixSeconds') return SECONDS === null ? null : { value: String(SECONDS) };
    return null;
  };
  let captured = null;
  window.postDrafts = (url, payload, boxId) => { captured = {url, payload, boxId}; };
  postDrafts = window.postDrafts;

  genMix();

  console.log(JSON.stringify({captured}));
})();
"""


def _run(tmp_path, checked, seconds):
    js = tmp_path / "t.js"
    driver = _DRIVER_TMPL % {"checked": json.dumps(checked), "seconds": json.dumps(seconds)}
    js.write_text(_slice() + driver, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])["captured"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_genmix_sends_inline_sources_with_full_text(tmp_path):
    got = _run(tmp_path, ["sc1", "sc2"], 20)
    assert got is not None
    assert got["url"] == "/api/produce/script/mix"
    payload = got["payload"]
    assert "sources" in payload
    codes = [s["shortcode"] for s in payload["sources"]]
    assert codes == ["sc1", "sc2"]
    assert payload["sources"][0]["full_text"] == "대본A 본문입니다"
    assert payload["sources"][1]["full_text"] == "대본B 본문입니다"
    assert "shortcodes" not in payload


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_genmix_target_seconds_follows_select(tmp_path):
    got = _run(tmp_path, ["sc1", "sc2"], 45)
    assert got["payload"]["target_seconds"] == 45


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_genmix_default_seconds_when_select_missing(tmp_path):
    got = _run(tmp_path, ["sc1", "sc2"], None)
    assert got["payload"]["target_seconds"] == 20


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_genmix_excludes_picks_without_full_text(tmp_path):
    got = _run(tmp_path, ["sc1", "sc3"], 20)
    # sc3는 full_text가 비어 있어 sources 부족(1개) → 안내 문구만 뜨고 postDrafts 미호출
    assert got is None
