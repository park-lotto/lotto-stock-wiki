"""뽑기 대기 중 '초안 생성'이 눌려 엉뚱한 안내가 뜨던 결함(2026-07-16 사장님 제보).

실패 시나리오(라이브 재현 완료): 왼쪽 📝뽑기를 누르면 openScriptModal이 모달을 **먼저 열고**
PM_BASE_STRUCT=null·PM_BASE_SCRIPT=''로 초기화한 뒤 /api/produce/extract_from_url을 await한다
(콜드 10~70초, 실측 70초 관측). 그 대기창 내내 '✨ 초안 생성' 버튼이 활성이라 누르면 pmRunGen이
structure:null·base_script:''를 그대로 실어 보내고, 백엔드 api_wiki_generate가 위키에서
shortcode(직행 URL)를 못 찾아 404 "위키에 없는 항목 — 먼저 S급으로 저장하세요"로 답한다.

→ 사용자는 "추출이 아직/실패했다"는 진짜 원인 대신 **"위키에 저장하라"는 정반대 지시**를 받는다.
   뽑기는 위키 저장 없이 되는 게 설계다(2026-07-15 bcd32029 폴백). 라이브 실측으로 문구 일치 확인.
   (그날 추출 실패의 근인은 Gemini 503 UNAVAILABLE = 우리 코드 아님. 하지만 실패했든 대기 중이든
    버튼이 열려 있는 것 자체가 결함이고, 그게 오해를 부르는 안내를 만들었다.)

mix 진입(openGenFromWiki)엔 이 문제가 없다 — 재료를 **동기로** 채우고 열며 내용이 비면 아예 안 연다.
즉 두 진입점의 비대칭이 원인이다.

수정: 뽑기는 재료가 오기 전까지 pmRun을 disabled. 추출이 와도 **백엔드 폴백 조건과 같은 식**
(structure가 dict이거나 base_script가 비지 않음)을 만족할 때만 푼다. mix는 진입 시 명시적으로 푼다
(뽑기가 잠가둔 채 모달을 가져갈 수 있으므로).

produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다(test_produce_pm_gen_race.py와 동일 방식).
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# 2026-07-23 Task4: genMix()가 믹스탭과 함께 제거돼 END 앵커를 그 자리에 남은
# 마커(`// ── openGenFromWiki 끝 ──`)로 옮겼다(produce.html 참조).
_GENFROMWIKI_START = "function openGenFromWiki(){"
_GENFROMWIKI_END = "// ── openGenFromWiki 끝 ──"
_SCRIPTMODAL_START = "let PM_IDX=null, PM_BASE_STRUCT=null, PM_CATEGORY='', PM_URL='', PM_SHORTCODE='', PM_BASE_SCRIPT='';"
_SCRIPTMODAL_END = "function pmUseRaw(){"

_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{ _on:false, contains(){return this._on;},
           add(){this._on=true;}, remove(){this._on=false;} },
           textContent:'', innerHTML:'', disabled:false, value:'', placeholder:'', appendChild(){} };
}
const _elements = { pmModal: makeGenericEl(), pmResults: makeGenericEl(), mixDrafts: makeGenericEl(),
                    pmSubject: makeGenericEl(), pmSubjectRow: makeGenericEl(), pmTopic: makeGenericEl(),
                    pmRun: makeGenericEl() };
let _checked = [];
const document = {
  getElementById(id){ return _elements[id] || null; },
  querySelectorAll(sel){ if (sel === '.mixPick:checked') return _checked.map(v => ({ value: v })); return []; },
  querySelector(){ return null; },
};
function esc(s){ return s; }
function renderPool(){}
function saveWork(){}
function pmLoadElementOptions(cat){ return Promise.resolve(); }
function pmToggleTopic(){}
function pmPrefillSubject(sc){ return Promise.resolve(); }
let HANDOFF = [];
globalThis.window = { _mixItems: [
  { shortcode:'WIKI_SC', name:'위키영상', category:'레시피', full_text:'위키 원본 대본 본문' },
] };

// 추출 응답을 밖에서 제어 — 대기창(버튼이 열려 있던 구간)을 재현한다.
let _resolveExtract = null, _extractReply = null;
function fetch(url, opts){
  if (String(url).indexOf('/api/produce/extract_from_url') !== -1) {
    return new Promise(resolve => {
      _resolveExtract = () => resolve({ json: async () => _extractReply });
    });
  }
  return Promise.reject(new Error('unmocked fetch: ' + url));
}
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스 ----
"""

# ★핵심: 추출이 도착하기 전(=사장님이 실제로 누른 그 순간) 버튼이 잠겨 있어야 한다.
_SCENARIO_LOCKED_WHILE_EXTRACTING = r"""
(async () => {
  HANDOFF = [{ url:'https://www.instagram.com/p/Dat2RByz-DM/', shortcode:'', category:'' }];
  _extractReply = { ok:true, category:'홈템', structure:{hook:'훅'}, full_text:'추출된 대본' };

  const p = openScriptModal(0);          // 뽑기 — 추출 await 중
  const fails = [];
  // 이 순간 사장님이 '초안 생성'을 눌렀다. 재료는 아직 null/''.
  if (PM_BASE_STRUCT !== null || PM_BASE_SCRIPT !== '') fails.push('전제 어긋남: 대기 중 재료가 비어있지 않음');
  if (document.getElementById('pmRun').disabled !== true) {
    fails.push('추출 대기 중인데 초안 생성 버튼이 열려 있음 — 재료 없이 요청이 나가 404 "먼저 S급으로 저장하세요"가 뜬다');
  }
  _resolveExtract(); await p;
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# 추출이 정상 도착하면 버튼이 풀려야 한다(안 풀리면 뽑기가 통째로 죽는다).
_SCENARIO_UNLOCKED_AFTER_EXTRACT = r"""
(async () => {
  HANDOFF = [{ url:'https://handoff/video', shortcode:'', category:'' }];
  _extractReply = { ok:true, category:'홈템', structure:{hook:'훅'}, full_text:'추출된 대본' };
  const p = openScriptModal(0);
  _resolveExtract(); await p;
  const fails = [];
  if (document.getElementById('pmRun').disabled !== false) fails.push('추출이 왔는데 버튼이 안 풀림 — 뽑기가 통째로 막힌다(회귀)');
  if (document.getElementById('pmResults').innerHTML.indexOf('pmUseRaw') === -1) fails.push('정상 흐름인데 pmUseRaw가 안 뜸(회귀)');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# 추출이 ok:true인데 재료가 텅 빈 경우 — 열어주면 백엔드가 그대로 404를 뱉는다.
# 백엔드 폴백 조건(structure가 dict이거나 base_script가 비지 않음)과 같은 식이어야 한다.
_SCENARIO_EMPTY_MATERIAL_STAYS_LOCKED = r"""
(async () => {
  HANDOFF = [{ url:'https://handoff/video', shortcode:'', category:'' }];
  _extractReply = { ok:true, category:'홈템', structure:null, full_text:'   ' };   // 구조 없음 + 공백뿐
  const p = openScriptModal(0);
  _resolveExtract(); await p;
  const fails = [];
  if (document.getElementById('pmRun').disabled !== true) {
    fails.push('재료가 텅 비었는데 버튼이 열림 — 누르면 백엔드가 404 "먼저 S급으로 저장하세요"를 그대로 뱉는다');
  }
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# 추출 실패(ok:false, 예: Gemini 503)면 잠긴 채로 남고 진짜 원인이 보여야 한다.
_SCENARIO_EXTRACT_FAILURE_STAYS_LOCKED = r"""
(async () => {
  HANDOFF = [{ url:'https://handoff/video', shortcode:'', category:'' }];
  _extractReply = { ok:false, error:'대본 추출 실패 — 잠시 후 재시도' };
  const p = openScriptModal(0);
  _resolveExtract(); await p;
  const fails = [];
  if (document.getElementById('pmRun').disabled !== true) fails.push('추출 실패인데 버튼이 열림');
  const html = document.getElementById('pmResults').innerHTML;
  if (html.indexOf('추출 실패') === -1) fails.push('추출 실패의 진짜 원인이 안 보임 — ' + JSON.stringify(html));
  if (html.indexOf('S급') !== -1) fails.push('추출 실패인데 위키 저장하라는 엉뚱한 안내가 뜸');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# 뽑기가 잠가둔 채 mix가 모달을 가져가면 mix는 재료가 있으므로 풀어야 한다.
_SCENARIO_MIX_UNLOCKS_AFTER_PICK_LOCKED = r"""
(async () => {
  HANDOFF = [{ url:'https://handoff/video', shortcode:'', category:'' }];
  _extractReply = { ok:true, category:'홈템', structure:{hook:'훅'}, full_text:'추출된 대본' };
  const p = openScriptModal(0);                       // 뽑기 — 버튼 잠김
  if (document.getElementById('pmRun').disabled !== true) { console.error('FAIL: 전제 어긋남(대기 중 안 잠김)'); process.exit(1); }
  _checked = ['WIKI_SC']; openGenFromWiki();          // mix가 모달을 가져간다
  const fails = [];
  if (document.getElementById('pmRun').disabled !== false) {
    fails.push('mix로 넘어왔는데 버튼이 뽑기가 잠가둔 채로 남음 — 재료가 있는데도 생성 불가');
  }
  _resolveExtract(); await p;                          // 늦은 추출이 도착해도(PM_GEN 가드)
  if (document.getElementById('pmRun').disabled !== false) fails.push('늦은 추출 continuation이 mix의 버튼을 도로 잠금');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""


def _extract_src() -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")

    def _span(start, end):
        s = text.find(start)
        e = text.find(end)
        assert s != -1, f"START 못 찾음(produce.html이 바뀌었나): {start!r}"
        assert e != -1 and e > s, f"END 못 찾음: {end!r}"
        return text[s:e]

    return _span(_GENFROMWIKI_START, _GENFROMWIKI_END) + "\n" + _span(_SCRIPTMODAL_START, _SCRIPTMODAL_END)


def _run(scenario: str, tmp_path) -> subprocess.CompletedProcess:
    src = _HARNESS_PREFIX + _extract_src() + scenario
    f = tmp_path / "probe_gen_button_gate.js"
    f.write_text(src, encoding="utf-8")
    # stdin=DEVNULL: Windows에서 여러 node 하위프로세스가 같은 세션에서 잇달아 뜨면 부모
    # stdin 핸들 복제 경합으로 간헐적 OSError([WinError 50])가 난다(test_produce_category_race.py
    # 기존 조치와 동일 원인·동일 처방 — 2026-07-17, 보이스 트랙 회귀런에서 실측).
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=30,
                          stdin=subprocess.DEVNULL)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_gen_button_locked_while_extracting(tmp_path):
    r = _run(_SCENARIO_LOCKED_WHILE_EXTRACTING, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_gen_button_unlocked_after_extract(tmp_path):
    r = _run(_SCENARIO_UNLOCKED_AFTER_EXTRACT, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_gen_button_stays_locked_when_material_empty(tmp_path):
    r = _run(_SCENARIO_EMPTY_MATERIAL_STAYS_LOCKED, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_gen_button_stays_locked_on_extract_failure(tmp_path):
    r = _run(_SCENARIO_EXTRACT_FAILURE_STAYS_LOCKED, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_mix_unlocks_button_taken_from_waiting_pick(tmp_path):
    r = _run(_SCENARIO_MIX_UNLOCKS_AFTER_PICK_LOCKED, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout
