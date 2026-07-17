"""mix 탭 1개 선택 → 재생성 배선(2026-07-16).

기존 useSingleScript()는 고른 대본을 그대로 복사해 확정했다 = 원본 영상에
원본 대본을 얹는 재업로드라 무의미. 이제 이미 이식돼 있던 pmModal(즐겨찾기
생성패널)을 열어 재생성한다. 위키 대본이라 추출 단계는 건너뛴다.

produce.html의 실제 소스를 앵커로 잘라내 Node로 실행한다.
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

START_ANCHOR = "function openGenFromWiki(){"
END_ANCHOR = "function genMix(){"

_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{ _on:false, contains(){return this._on;},
           add(){this._on=true;}, remove(){this._on=false;} },
           textContent:'', innerHTML:'', disabled:false, value:'', placeholder:'', appendChild(){} };
}
const _elements = { pmModal: makeGenericEl(), pmResults: makeGenericEl(),
                    mixDrafts: makeGenericEl(), pmSubject: makeGenericEl(),
                    pmSubjectRow: makeGenericEl(), pmTopic: makeGenericEl(),
                    // pmRun: 실제 페이지(produce.html:424)엔 늘 있다. 재료 유무로 생성 버튼을
                    // 잠그고 푸는 2026-07-16 수정 이후 하네스에도 필요.
                    pmRun: makeGenericEl() };
let _checked = [];                    // 체크된 shortcode 목록
const document = {
  getElementById(id){ return _elements[id] || null; },
  querySelectorAll(sel){
    if (sel === '.mixPick:checked') return _checked.map(v => ({ value: v }));
    return [];
  },
  querySelector(){ return null; },
};
let _prefilled = null, _loadedCat = null;
function pmPrefillSubject(sc){ _prefilled = sc; return Promise.resolve(); }
function pmLoadElementOptions(cat){ _loadedCat = cat; return Promise.resolve(); }
function pmToggleTopic(){}
function esc(s){ return s; }
let PM_IDX='기존값', PM_BASE_STRUCT='기존값', PM_CATEGORY='', PM_URL='기존값',
    PM_SHORTCODE='', PM_BASE_SCRIPT='', PM_FROM_WIKI=null;
let PM_GEN=0;   // 최종 리뷰 I-1: openGenFromWiki가 모달을 가져갈 때 ++PM_GEN 해야 한다
// Node엔 window가 없다. 'use strict'라 선언 없이 대입하면 ReferenceError → globalThis에 붙인다.
globalThis.window = { _mixItems: [
  { shortcode:'ABC123', name:'감자스낵', category:'레시피', full_text:'원본 대본 본문' },
  { shortcode:'DEF456', name:'가습기',   category:'가전',   full_text:'' },
] };
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스 ----
"""

_SCENARIO_OPENS_MODAL = r"""
const genBefore = PM_GEN;
_checked = ['ABC123'];
openGenFromWiki();
const fails = [];
if (PM_GEN !== genBefore + 1) fails.push('PM_GEN이 증가 안 함(모달을 가져가는 신호가 없음) — before=' + genBefore + ' after=' + PM_GEN);
if (!document.getElementById('pmModal').classList.contains()) fails.push('모달이 안 열림');
if (PM_SHORTCODE !== 'ABC123') fails.push('PM_SHORTCODE=' + JSON.stringify(PM_SHORTCODE));
if (PM_CATEGORY !== '레시피') fails.push('PM_CATEGORY=' + JSON.stringify(PM_CATEGORY));
if (PM_BASE_SCRIPT !== '원본 대본 본문') fails.push('PM_BASE_SCRIPT=' + JSON.stringify(PM_BASE_SCRIPT));
if (PM_BASE_STRUCT !== null) fails.push('PM_BASE_STRUCT는 null이어야(백엔드가 위키에서 읽음)=' + JSON.stringify(PM_BASE_STRUCT));
if (PM_IDX !== null) fails.push('PM_IDX는 null이어야(HANDOFF 유래 아님)=' + JSON.stringify(PM_IDX));
if (PM_FROM_WIKI !== 'ABC123') fails.push('PM_FROM_WIKI=' + JSON.stringify(PM_FROM_WIKI));
if (_prefilled !== 'ABC123') fails.push('소재 프리필 안 부름=' + JSON.stringify(_prefilled));
if (_loadedCat !== '레시피') fails.push('요소옵션 로드 카테고리=' + JSON.stringify(_loadedCat));
if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
console.log('PASS');
"""

_SCENARIO_REJECTS_TWO = r"""
_checked = ['ABC123', 'DEF456'];
openGenFromWiki();
if (document.getElementById('pmModal').classList.contains()) {
  console.error('FAIL: 2개 선택인데 모달이 열림'); process.exit(1);
}
if (document.getElementById('mixDrafts').innerHTML.indexOf('1개만') === -1) {
  console.error('FAIL: 안내문 없음 — ' + document.getElementById('mixDrafts').innerHTML); process.exit(1);
}
console.log('PASS');
"""

_SCENARIO_REJECTS_EMPTY_SCRIPT = r"""
_checked = ['DEF456'];                 // full_text 빈 항목
openGenFromWiki();
if (document.getElementById('pmModal').classList.contains()) {
  console.error('FAIL: 대본 없는 항목인데 모달이 열림'); process.exit(1);
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
    # encoding="utf-8", errors="replace": 기본(cp949) 캡처는 실패메시지의 한글 console.error를
    # 못 읽어 리더 스레드에서 죽는다(stderr=None으로 보임) — test_produce_subject.py의 _run_race와 동일 수정.
    # stdin=DEVNULL: Windows에서 여러 node 하위프로세스가 같은 세션에서 잇달아 뜨면 부모
    # stdin 핸들 복제 경합으로 간헐적 OSError([WinError 50])가 난다(test_produce_category_race.py
    # 기존 조치와 동일 원인·동일 처방 — 2026-07-17, 보이스 트랙 회귀런에서 실측).
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30,
                           stdin=subprocess.DEVNULL)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_one_pick_opens_modal_with_wiki_item(tmp_path):
    r = _run(_SCENARIO_OPENS_MODAL, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_two_picks_rejected(tmp_path):
    r = _run(_SCENARIO_REJECTS_TWO, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_empty_script_rejected(tmp_path):
    r = _run(_SCENARIO_REJECTS_EMPTY_SCRIPT, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


def test_use_single_script_is_gone():
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "useSingleScript" not in text, "그대로 쓰기(useSingleScript)가 남아 있다"
    assert "그대로 쓰기" not in text, "'그대로 쓰기' 버튼 문구가 남아 있다"


def test_mix_combine_survives():
    """범위 밖 — 2개+ 조합은 그대로여야 한다."""
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "function genMix(){" in text
    assert "/api/produce/script/mix" in text
