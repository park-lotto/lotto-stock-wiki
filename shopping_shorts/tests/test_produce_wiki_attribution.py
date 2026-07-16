"""위키담기 오귀속 차단(2026-07-16).

기존 버그: mix 목록에서 온 대본을 확정하면 script_src_idx가 안 남아
_currentSrcItem()이 HANDOFF[0] 등으로 폴백 → '⭐이 원본 영상 위키에 담기'가
대본과 무관한 영상을 학습 재료로 담았다. 주석의 I-1이 잡으려던 오귀속인데
mix 경로만 안 막혀 있었다.

위키 유래 대본은 이미 위키에 있으니 담을 원본이 없다 → 버튼을 숨긴다.
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

START_ANCHOR = "function refreshFinalPeek(){"
END_ANCHOR = "// 이 \"원본 영상\"(내 리메이크 아님)을 위키(도서관)에 담아"

_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{ contains(){return false;}, add(){}, remove(){} },
           textContent:'', innerHTML:'', disabled:false, value:'', appendChild(){} };
}
const _elements = { finalScriptPeek: makeGenericEl(), saveWikiBtn: makeGenericEl(),
                    finalCategory: makeGenericEl() };
const document = { getElementById(id){ return _elements[id] || null; } };
function esc(s){ return s; }
function lenText(){ return '10자 · 약 2초'; }
function ensureCategoryOptions(){}
const STATE = { script: '', script_src_idx: null, script_from_wiki: null };
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스 ----
"""

_SCENARIO_WIKI_HIDES = r"""
STATE.script = '확정된 대본';
STATE.script_from_wiki = 'ABC123';     // mix 목록(위키)에서 온 대본
refreshFinalPeek();
if (document.getElementById('saveWikiBtn').style.display !== 'none') {
  console.error('FAIL: 위키 유래인데 담기 버튼이 보임 — display=' +
    JSON.stringify(document.getElementById('saveWikiBtn').style.display));
  process.exit(1);
}
console.log('PASS');
"""

_SCENARIO_HANDOFF_SHOWS = r"""
STATE.script = '확정된 대본';
STATE.script_from_wiki = null;         // 왼쪽 뽑기(HANDOFF) 유래 — 담을 원본이 있다
refreshFinalPeek();
if (document.getElementById('saveWikiBtn').style.display !== 'inline-block') {
  console.error('FAIL: 뽑기 유래인데 담기 버튼이 안 보임(회귀) — display=' +
    JSON.stringify(document.getElementById('saveWikiBtn').style.display));
  process.exit(1);
}
console.log('PASS');
"""

_SCENARIO_NO_SCRIPT_HIDES = r"""
STATE.script = '';
STATE.script_from_wiki = null;
refreshFinalPeek();
if (document.getElementById('saveWikiBtn').style.display !== 'none') {
  console.error('FAIL: 대본이 없는데 담기 버튼이 보임'); process.exit(1);
}
console.log('PASS');
"""


def _extract() -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    start = text.find(START_ANCHOR)
    end = text.find(END_ANCHOR)
    assert start != -1, f"START_ANCHOR 못 찾음: {START_ANCHOR!r}"
    assert end != -1 and end > start, f"END_ANCHOR 못 찾음: {END_ANCHOR!r}"
    return text[start:end]


def _run(scenario: str, tmp_path) -> subprocess.CompletedProcess:
    src = _HARNESS_PREFIX + _extract() + scenario
    f = tmp_path / "probe.js"
    f.write_text(src, encoding="utf-8")
    return subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_wiki_sourced_script_hides_save_button(tmp_path):
    r = _run(_SCENARIO_WIKI_HIDES, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_handoff_sourced_script_still_shows_button(tmp_path):
    r = _run(_SCENARIO_HANDOFF_SHOWS, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_no_script_hides_button(tmp_path):
    r = _run(_SCENARIO_NO_SCRIPT_HIDES, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


def test_confirm_points_set_the_flag():
    """확정 경로 넷이 전부 플래그를 명시적으로 세팅하는가(누락 = stale 플래그 버그)."""
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "script_from_wiki: null" in text or "script_from_wiki:null" in text, "STATE 초기값이 없다"
    assert "STATE.script_from_wiki=PM_FROM_WIKI" in text.replace(" ", ""), "pmUseDraft가 플래그를 안 세운다"
    assert text.count("STATE.script_from_wiki") >= 4, "확정 경로 일부가 플래그를 안 세운다"
