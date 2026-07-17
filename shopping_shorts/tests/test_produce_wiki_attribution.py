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
    # encoding="utf-8", errors="replace": 기본(cp949) 캡처는 실패메시지의 한글 console.error를
    # 못 읽어 리더 스레드에서 죽는다(stderr=None으로 보임) — test_produce_subject.py의 _run_race와 동일 수정.
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)


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


def test_state_initial_value_has_the_flag():
    """STATE 초기값에 script_from_wiki가 있는가(최소한의 정적 체크 — 나머지는 아래 행동 테스트가 커버)."""
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "script_from_wiki: null" in text or "script_from_wiki:null" in text, "STATE 초기값이 없다"


# ============================================================================
# 아래는 리뷰(Important) 수정: 기존 test_confirm_points_set_the_flag는 파일 전체
# 문자열 카운트(text.count("STATE.script_from_wiki") >= 4)였다. 리뷰어가
# pmUseDraft의 대입줄을 주석 처리("// STATE.script_from_wiki=PM_FROM_WIKI; // disabled")
# 해서 기능을 완전히 죽였는데도 문자열이 주석 안에 남아 있어 4개 테스트가 전부 통과했다.
# 원인: 기존 START_ANCHOR("function refreshFinalPeek(){")가 그보다 앞(약 1090~1385줄)에
# 있는 pmUseDraft/pmUseRaw/useDraft를 하네스에 안 실었다 — 즉 이 세 함수가 "호출됐을 때"
# 플래그를 세우는지는 아무 테스트도 확인하지 않았다.
#
# 여기서는 세 함수를 별도 앵커로 정확히 잘라내 실제로 호출하고, STATE가 바뀌었는지
# 직접 확인한다(문자열 존재 여부가 아니라 실행 결과). 주석처리 뮤테이션이 죽는지가
# 이 테스트들의 존재 이유다.
# ============================================================================

_CONFIRM_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{ contains(){return false;}, add(){}, remove(){} },
           textContent:'', innerHTML:'', disabled:false, value:'', appendChild(){} };
}
const _elements = {};
const document = { getElementById(id){ return _elements[id] || null; } };
const window = { _drafts: [] };
let HANDOFF = [];
let _saveWorkCalls = 0;
function saveWork(){ _saveWorkCalls++; }
function setScriptMode(){}
function refreshFinalPeek(){}
function pmClose(){}
async function setFinalCategoryValue(){}
let PM_IDX=null, PM_CATEGORY='', PM_BASE_SCRIPT='';
let PM_FROM_WIKI=null;
const STATE = { script:'SENTINEL_UNSET', script_src_idx:'SENTINEL_UNSET', script_from_wiki:'SENTINEL_UNSET' };
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 함수 ----
"""

_USE_DRAFT_START = "function useDraft(i){"
_USE_DRAFT_END = "async function postDrafts"

_PM_USE_DRAFT_START = "function pmUseDraft(btn){"
_PM_USE_DRAFT_END = "async function pmOnDraftEdit"

_PM_USE_RAW_START = "function pmUseRaw(){"
_PM_USE_RAW_END = "function pmClose(){"


def _extract_span(start: str, end: str) -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    s = text.find(start)
    e = text.find(end)
    assert s != -1, f"START 못 찾음: {start!r}"
    assert e != -1 and e > s, f"END 못 찾음: {end!r}"
    return text[s:e]


def _run_confirm(start: str, end: str, scenario: str, tmp_path) -> subprocess.CompletedProcess:
    src = _CONFIRM_HARNESS_PREFIX + _extract_span(start, end) + scenario
    f = tmp_path / "probe_confirm.js"
    f.write_text(src, encoding="utf-8")
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)


_SCENARIO_USE_DRAFT_SETS_FLAG = r"""
window._drafts = [{script:'조합된 대본', hook:'훅'}];
useDraft(0);
if (STATE.script_from_wiki !== 'mix') {
  console.error('FAIL: useDraft가 script_from_wiki를 mix로 세팅 안 함 — ' + JSON.stringify(STATE.script_from_wiki));
  process.exit(1);
}
if (STATE.script !== '조합된 대본') {
  console.error('FAIL: useDraft가 대본 자체를 안 세팅함'); process.exit(1);
}
console.log('PASS');
"""

_SCENARIO_PM_USE_DRAFT_SETS_FLAG_WIKI = r"""
PM_IDX = 4; PM_FROM_WIKI = 'SHORTCODE123'; PM_CATEGORY = '뷰티';
const fakeBtn = { closest(){ return { querySelector(){ return { value: '편집된 초안' }; } }; } };
pmUseDraft(fakeBtn);
if (STATE.script_from_wiki !== 'SHORTCODE123') {
  console.error('FAIL: pmUseDraft가 위키유래 플래그를 안 세움 — ' + JSON.stringify(STATE.script_from_wiki));
  process.exit(1);
}
if (STATE.script_src_idx !== 4) { console.error('FAIL: script_src_idx 안 세팅'); process.exit(1); }
if (STATE.script !== '편집된 초안') { console.error('FAIL: 대본 텍스트 안 세팅'); process.exit(1); }
console.log('PASS');
"""

_SCENARIO_PM_USE_DRAFT_SETS_FLAG_HANDOFF = r"""
PM_IDX = 0; PM_FROM_WIKI = null; PM_CATEGORY = '생활';
const fakeBtn = { closest(){ return { querySelector(){ return { value: '뽑기 유래 대본' }; } }; } };
pmUseDraft(fakeBtn);
if (STATE.script_from_wiki !== null) {
  console.error('FAIL: pmUseDraft가 뽑기유래인데 null이 아님 — ' + JSON.stringify(STATE.script_from_wiki));
  process.exit(1);
}
console.log('PASS');
"""

_SCENARIO_PM_USE_RAW_SETS_FLAG = r"""
PM_IDX = 2; PM_FROM_WIKI = 'RAWSHORT'; PM_BASE_SCRIPT = '원본 그대로 대본'; PM_CATEGORY='패션';
pmUseRaw();
if (STATE.script_from_wiki !== 'RAWSHORT') {
  console.error('FAIL: pmUseRaw가 플래그를 안 세움 — ' + JSON.stringify(STATE.script_from_wiki));
  process.exit(1);
}
if (STATE.script !== '원본 그대로 대본') { console.error('FAIL: 대본 안 세팅'); process.exit(1); }
console.log('PASS');
"""


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_use_draft_actually_sets_flag_when_called(tmp_path):
    r = _run_confirm(_USE_DRAFT_START, _USE_DRAFT_END, _SCENARIO_USE_DRAFT_SETS_FLAG, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_pm_use_draft_actually_sets_flag_wiki_sourced(tmp_path):
    r = _run_confirm(_PM_USE_DRAFT_START, _PM_USE_DRAFT_END, _SCENARIO_PM_USE_DRAFT_SETS_FLAG_WIKI, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_pm_use_draft_actually_sets_flag_handoff_sourced(tmp_path):
    r = _run_confirm(_PM_USE_DRAFT_START, _PM_USE_DRAFT_END, _SCENARIO_PM_USE_DRAFT_SETS_FLAG_HANDOFF, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_pm_use_raw_actually_sets_flag(tmp_path):
    r = _run_confirm(_PM_USE_RAW_START, _PM_USE_RAW_END, _SCENARIO_PM_USE_RAW_SETS_FLAG, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


# ============================================================================
# Critical 수정: 세션 복원(_consumeProduceHandoff)이 saveWork가 저장한
# script_from_wiki를 실제로 복원하는가. 예전엔 saveWork()의 페이로드에
# script_from_wiki가 없어서, 새로고침 후 STATE가 재선언되며 script_from_wiki만
# null로 리셋되고 script_src_idx는 복원돼 — 버튼이 다시 뜨고 누르면 stale
# script_src_idx로 무관한 HANDOFF 영상이 담기는 버그가 되살아났다.
# ============================================================================

# 2026-07-17(대본믹스통합 T3): WORK_ID/_workState/_pushWork가 saveWork() **앞**에 선언되도록
# 소스가 바뀌었다 — 앵커를 saveWork()로 잡으면 그 선언부를 놓쳐 ReferenceError가 난다.
_RESTORE_START = "let WORK_ID = null;"
_RESTORE_END = "function renderPool(){"

_RESTORE_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{ contains(){return false;}, add(){}, remove(){} },
           textContent:'', innerHTML:'', disabled:false, value:'', appendChild(){} };
}
const _elements = { finalScriptPeek: makeGenericEl(), saveWikiBtn: makeGenericEl(),
                    finalCategory: makeGenericEl(), handoffBanner: makeGenericEl() };
const document = { getElementById(id){ return _elements[id] || null; } };
function esc(s){ return s; }
function lenText(){ return '10자 · 약 2초'; }
function ensureCategoryOptions(){}
function renderPool(){}
function syncFootageToMixUrls(){}
function setScriptMode(){}
let HANDOFF = [];
let cur = 0;      // saveWork()가 저장하는 step (2026-07-17 T3)
let MIX_JOB = null;
const STATE = { script:'', script_src_idx:null, script_from_wiki:null };

const _store = {};
const sessionStorage = {
  getItem(k){ return Object.prototype.hasOwnProperty.call(_store, k) ? _store[k] : null; },
  setItem(k, v){ _store[k]=String(v); },
  removeItem(k){ delete _store[k]; },
};
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 함수(saveWork/_consumeProduceHandoff + refreshFinalPeek) ----
"""


def _extract_restore_and_peek() -> str:
    return _extract_span(_RESTORE_START, _RESTORE_END) + "\n" + _extract()


def _run_restore(scenario: str, tmp_path) -> subprocess.CompletedProcess:
    src = _RESTORE_HARNESS_PREFIX + _extract_restore_and_peek() + scenario
    f = tmp_path / "probe_restore.js"
    f.write_text(src, encoding="utf-8")
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)


_SCENARIO_SAVE_THEN_RESTORE_KEEPS_FLAG = r"""
STATE.script = '위키에서 뽑은 대본';
STATE.script_from_wiki = 'ABC123';
STATE.script_src_idx = 2;
HANDOFF = [{url:'u1'},{url:'u2'},{url:'u3'}];
saveWork();

// "새로고침" 시뮬레이션 — STATE·HANDOFF를 초기값으로 리셋, sessionStorage는 그대로 유지.
HANDOFF = [];
STATE.script=''; STATE.script_src_idx=null; STATE.script_from_wiki=null;

_consumeProduceHandoff();   // produce_handoff/produce_mix_urls 없음 → produce_work 복원 분기

if (STATE.script_from_wiki !== 'ABC123') {
  console.error('FAIL: 복원 후 script_from_wiki 유실 — ' + JSON.stringify(STATE.script_from_wiki));
  process.exit(1);
}
if (STATE.script_src_idx !== 2) {
  console.error('FAIL: 복원 후 script_src_idx 유실 — ' + JSON.stringify(STATE.script_src_idx));
  process.exit(1);
}

refreshFinalPeek();
const btn = document.getElementById('saveWikiBtn');
if (btn.style.display !== 'none') {
  console.error('FAIL: 위키유래 복원 후에도 담기 버튼이 보임(회귀) — display=' + JSON.stringify(btn.style.display));
  process.exit(1);
}
console.log('PASS');
"""

_SCENARIO_LEGACY_PAYLOAD_DEFAULTS_TO_NULL = r"""
// 구버전 페이로드(script_from_wiki 키 자체가 없음)를 직접 주입 — 하위호환 확인.
sessionStorage.setItem('produce_work', JSON.stringify({
  handoff: [{url:'u1'}], script: '뽑기에서 나온 대본', script_src_idx: 0
}));
HANDOFF = [];
STATE.script=''; STATE.script_src_idx=null; STATE.script_from_wiki=null;

_consumeProduceHandoff();

if (STATE.script_from_wiki !== null) {
  console.error('FAIL: 구페이로드 복원인데 script_from_wiki가 null이 아님(undefined 유출) — ' +
    JSON.stringify(STATE.script_from_wiki));
  process.exit(1);
}
refreshFinalPeek();
const btn = document.getElementById('saveWikiBtn');
if (btn.style.display !== 'inline-block') {
  console.error('FAIL: 구페이로드 복원(뽑기유래 취급=안전 기본값)인데 버튼이 안 보임 — display=' +
    JSON.stringify(btn.style.display));
  process.exit(1);
}
console.log('PASS');
"""


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_save_then_restore_keeps_wiki_flag_and_button_hidden(tmp_path):
    r = _run_restore(_SCENARIO_SAVE_THEN_RESTORE_KEEPS_FLAG, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_legacy_payload_without_flag_restores_to_null_and_shows_button(tmp_path):
    r = _run_restore(_SCENARIO_LEGACY_PAYLOAD_DEFAULTS_TO_NULL, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


# ============================================================================
# 최종 리뷰 I-2: saveScriptToWiki(Task 4)는 위키 유래 대본의 오귀속을 막았지만
# onFinalCategoryChange는 무방비였다 — mix 확정 후에도 #finalCategory가 계속
# 보이고(refreshFinalPeek는 STATE.script만 봄), 사용자가 카테고리를 교정하면
# _currentSrcItem()이 HANDOFF로 폴백해 무관한 영상의 category를 HANDOFF에 쓰고
# /api/produce/category로 DB(script_extracts.category)에도 영속 기록해버린다.
# refreshFinalPeek과 같은 STATE.script_from_wiki 가드를 여기서도 검증한다.
# ============================================================================

_CATCHANGE_START = "function _currentSrcItem(){"
_CATCHANGE_END = "function refreshFinalPeek(){"

_CATCHANGE_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{ contains(){return false;}, add(){}, remove(){} },
           textContent:'', innerHTML:'', disabled:false, value:'', appendChild(){} };
}
const _elements = { pmModal: makeGenericEl() };
const document = { getElementById(id){ return _elements[id] || null; } };
let _fetchCalls = [];
function fetch(url, opts){
  _fetchCalls.push({ url: String(url), body: opts && opts.body ? JSON.parse(opts.body) : null });
  return Promise.resolve({ json: async () => ({ ok:true }) });
}
let _saveWorkCalls = 0;
function saveWork(){ _saveWorkCalls++; }
let _loadedCatCalls = [];
function pmLoadElementOptions(cat){ _loadedCatCalls.push(cat); }
let HANDOFF = [];
let PM_CATEGORY = '';
const STATE = { script:'대본', script_src_idx:null, script_from_wiki:null };
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스(_currentSrcItem + onFinalCategoryChange) ----
"""

_SCENARIO_WIKI_SOURCED_DOES_NOT_WRITE = r"""
STATE.script_from_wiki = 'WIKI_SC';   // mix 유래 — 담을 원본이 없다
HANDOFF = [{ url:'https://other/video', shortcode:'OTHER_SC', category:'가전' }];
onFinalCategoryChange({ value: '레시피' });
const fails = [];
if (HANDOFF[0].category !== '가전') fails.push('위키 유래인데 무관한 HANDOFF 영상 category가 바뀜 — ' + JSON.stringify(HANDOFF[0].category));
if (_fetchCalls.length !== 0) fails.push('위키 유래인데 /api/produce/category POST가 나감 — ' + JSON.stringify(_fetchCalls));
if (PM_CATEGORY !== '레시피') fails.push('PM_CATEGORY는 위키 유래여도 갱신돼야(생성에 씀) — ' + JSON.stringify(PM_CATEGORY));
if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
console.log('PASS');
"""

_SCENARIO_HANDOFF_SOURCED_STILL_WRITES = r"""
STATE.script_from_wiki = null;   // 뽑기(HANDOFF) 유래 — 담을 원본이 있다
HANDOFF = [{ url:'https://mine/video', shortcode:'MY_SC', category:'가전', pickScript:true }];
onFinalCategoryChange({ value: '뷰티' });
const fails = [];
if (HANDOFF[0].category !== '뷰티') fails.push('뽑기 유래인데 category 교정이 HANDOFF에 반영 안 됨(회귀) — ' + JSON.stringify(HANDOFF[0].category));
if (_fetchCalls.length !== 1) fails.push('뽑기 유래인데 /api/produce/category POST가 안 나감(회귀) — count=' + _fetchCalls.length);
else {
  const body = _fetchCalls[0].body;
  if (body.shortcode !== 'MY_SC' || body.category !== '뷰티') fails.push('POST 페이로드 불일치 — ' + JSON.stringify(body));
}
if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
console.log('PASS');
"""


def _run_catchange(scenario: str, tmp_path) -> subprocess.CompletedProcess:
    src = _CATCHANGE_HARNESS_PREFIX + _extract_span(_CATCHANGE_START, _CATCHANGE_END) + scenario
    f = tmp_path / "probe_catchange.js"
    f.write_text(src, encoding="utf-8")
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_wiki_sourced_category_change_does_not_write_to_unrelated_handoff(tmp_path):
    r = _run_catchange(_SCENARIO_WIKI_SOURCED_DOES_NOT_WRITE, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_handoff_sourced_category_change_still_writes(tmp_path):
    r = _run_catchange(_SCENARIO_HANDOFF_SOURCED_STILL_WRITES, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout
