"""최종 리뷰 I-1 — openScriptModal의 await 뒤 continuation이 mix 모달을 강탈(2026-07-16).

실패 시나리오(리뷰어가 실제 소스로 재현): 왼쪽 📝뽑기(openScriptModal)를 눌러 대본
추출(/api/produce/extract_from_url, 10~30초)이 진행 중일 때, 사용자가 답답해서 mix
탭으로 넘어가 위키 대본 1개를 골라 ♻️ 생성(openGenFromWiki)한다. openGenFromWiki가
PM_*(PM_CATEGORY·PM_BASE_STRUCT·PM_BASE_SCRIPT·PM_SHORTCODE·PM_FROM_WIKI)를 위키
것으로 채운 뒤, 그제서야 먼저 눌렀던 추출이 도착한다. 가드가 없으면 그 continuation이
"자기가 아직 모달 주인인지 확인하지 않고" PM_*를 핸드오프 영상 것으로 덮어써 —
PM_SHORTCODE(=위키 것)만 남고 재료(structure·script·category)는 전부 남의 영상 것인
채로 pmRunGen이 쏴 무관한 영상의 리메이크가 조용히 나온다. 게다가 설계가 명시적으로
금지한 pmUseRaw 버튼이 mix 모달에 뜬다.

수정: 모달의 "현재 주인" 세대번호 PM_GEN. 두 진입점 모두 시작 시 ++PM_GEN, await 뒤
자기 번호(myGen)가 최신인지 확인 후 아니면 아무것도 건드리지 않고 return한다.

produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다 — 재구현이 아니라 실물
코드를 검증한다(test_produce_mix_regen.py·test_produce_subject.py와 같은 방식).
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# openGenFromWiki 전체 + (PM_GEN 등 전역 선언 + openScriptModal 전체)를 이어붙인다.
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
                    // pmRun: 실제 페이지(produce.html:424)엔 늘 있다. 두 진입점이 재료 유무에 따라
                    // 생성 버튼을 잠그고 푸는 2026-07-16 수정 이후 하네스에도 필요.
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
let _loadedCatCalls = [];
function pmLoadElementOptions(cat){ _loadedCatCalls.push(cat); return Promise.resolve(); }
function pmToggleTopic(){}
let _prefillCalls = [];
function pmPrefillSubject(sc){ _prefillCalls.push(sc); return Promise.resolve(); }
let HANDOFF = [];
globalThis.window = { _mixItems: [
  { shortcode:'WIKI_SC', name:'무관한 위키영상', category:'레시피', full_text:'위키 원본 대본 본문' },
] };

// 추출(/api/produce/extract_from_url) 응답을 밖에서 제어 — 늦게 도착하는 경합을 재현한다.
let _resolveExtract = null;
function fetch(url, opts){
  if (String(url).indexOf('/api/produce/extract_from_url') !== -1) {
    return new Promise(resolve => {
      _resolveExtract = () => resolve({ json: async () => ({
        ok:true, category:'가전', structure:{hook:'핸드오프 훅'}, full_text:'핸드오프 영상에서 추출한 대본'
      }) });
    });
  }
  return Promise.reject(new Error('unmocked fetch: ' + url));
}
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스(openGenFromWiki + openScriptModal) ----
"""

_SCENARIO_MIX_WINS_LATE_EXTRACT = r"""
(async () => {
  HANDOFF = [{ url:'https://handoff/video', shortcode:'', category:'' }];

  // 1) 📝뽑기 클릭 — 추출 await 대기 중(아직 응답 없음)
  const p = openScriptModal(0);

  // 2) 답답해서 mix 탭에서 위키 대본을 골라 재생성 진입 — 모달 주인이 바뀐다
  _checked = ['WIKI_SC'];
  openGenFromWiki();
  const snap = { struct: PM_BASE_STRUCT, script: PM_BASE_SCRIPT, cat: PM_CATEGORY,
                 sc: PM_SHORTCODE, fromWiki: PM_FROM_WIKI, resultsHtml: document.getElementById('pmResults').innerHTML };

  // 3) 그제서야 추출이 도착
  _resolveExtract();
  await p;

  const fails = [];
  if (PM_BASE_SCRIPT !== snap.script) fails.push('PM_BASE_SCRIPT가 핸드오프 추출로 덮임 — ' + JSON.stringify(PM_BASE_SCRIPT));
  if (PM_BASE_STRUCT !== snap.struct) fails.push('PM_BASE_STRUCT가 핸드오프 추출로 덮임 — ' + JSON.stringify(PM_BASE_STRUCT));
  if (PM_CATEGORY !== snap.cat) fails.push('PM_CATEGORY가 핸드오프 추출로 덮임 — ' + JSON.stringify(PM_CATEGORY));
  if (PM_SHORTCODE !== snap.sc) fails.push('PM_SHORTCODE가 바뀜 — ' + JSON.stringify(PM_SHORTCODE));
  if (PM_FROM_WIKI !== 'WIKI_SC') fails.push('PM_FROM_WIKI가 위키유래를 잃음 — ' + JSON.stringify(PM_FROM_WIKI));
  const resultsHtml = document.getElementById('pmResults').innerHTML;
  if (resultsHtml !== snap.resultsHtml) fails.push('mix가 채운 pmResults가 늦은 추출 continuation에 덮임 — ' + JSON.stringify(resultsHtml));
  if (resultsHtml.indexOf('pmUseRaw') !== -1) fails.push('mix 모달에 pmUseRaw 버튼이 새어들어옴(설계가 명시적으로 금지)');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# 회귀 방지: mix가 끼어들지 않으면(정상 단독 흐름) 추출 결과가 그대로 반영돼야 한다.
_SCENARIO_NO_RACE_STILL_APPLIES = r"""
(async () => {
  HANDOFF = [{ url:'https://handoff/video', shortcode:'', category:'' }];
  const p = openScriptModal(0);
  _resolveExtract();
  await p;
  const fails = [];
  if (PM_BASE_SCRIPT !== '핸드오프 영상에서 추출한 대본') fails.push('경합 없을 때 추출 결과가 반영 안 됨(회귀) — ' + JSON.stringify(PM_BASE_SCRIPT));
  if (PM_CATEGORY !== '가전') fails.push('경합 없을 때 카테고리가 반영 안 됨(회귀) — ' + JSON.stringify(PM_CATEGORY));
  if (PM_FROM_WIKI !== null) fails.push('뽑기 유래인데 PM_FROM_WIKI가 null이 아님 — ' + JSON.stringify(PM_FROM_WIKI));
  const resultsHtml = document.getElementById('pmResults').innerHTML;
  if (resultsHtml.indexOf('pmUseRaw') === -1) fails.push('정상 뽑기 흐름인데 pmUseRaw 버튼이 안 뜸(회귀)');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""


def _extract() -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")

    def _span(start, end):
        s = text.find(start)
        e = text.find(end)
        assert s != -1, f"START 못 찾음(produce.html이 바뀌었나): {start!r}"
        assert e != -1 and e > s, f"END 못 찾음: {end!r}"
        return text[s:e]

    return _span(_GENFROMWIKI_START, _GENFROMWIKI_END) + "\n" + _span(_SCRIPTMODAL_START, _SCRIPTMODAL_END)


def _run(scenario: str, tmp_path) -> subprocess.CompletedProcess:
    src = _HARNESS_PREFIX + _extract() + scenario
    f = tmp_path / "probe_pm_gen_race.js"
    f.write_text(src, encoding="utf-8")
    # encoding="utf-8", errors="replace": 기본(cp949) 캡처는 실패메시지의 한글 console.error를
    # 못 읽어 리더 스레드에서 죽는다(stderr=None으로 보임) — M-2와 동일 이유로 처음부터 적용.
    # stdin=DEVNULL: Windows에서 여러 node 하위프로세스가 같은 세션에서 잇달아 뜨면 부모
    # stdin 핸들 복제 경합으로 간헐적 OSError([WinError 50])가 난다(test_produce_category_race.py
    # 기존 조치와 동일 원인·동일 처방 — 2026-07-17, 보이스 트랙 회귀런에서 실측).
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30,
                           stdin=subprocess.DEVNULL)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_late_extract_does_not_hijack_mix_modal(tmp_path):
    r = _run(_SCENARIO_MIX_WINS_LATE_EXTRACT, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_no_race_extract_still_applies_normally(tmp_path):
    r = _run(_SCENARIO_NO_RACE_STILL_APPLIES, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout
