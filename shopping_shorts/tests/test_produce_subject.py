"""제작소 pmModal 소재칸(2026-07-16).

즐겨찾기(library.html)엔 소재 자동감지 칸이 있는데 제작소 pmModal엔 없어서
pmRunGen이 subject를 안 보냈다 → 리메이크 모드인데 소재가 고정되지 않았다.
(백엔드 /api/wiki/generate는 subject를 이미 받는다.)

test_produce_category_race.py와 같은 방식 — produce.html의 **실제 소스**를
앵커로 잘라내 Node로 실행한다. 재구현이 아니라 실물 코드를 검증한다.
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# 앵커: 이번 수정으로 안 바뀌는 문자열
START_ANCHOR = "function pmToggleTopic(){"
END_ANCHOR = "function pmRenderDrafts(drafts){"

_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{ contains(){return false;}, add(){}, remove(){} },
           textContent:'', innerHTML:'', disabled:false, value:'', placeholder:'', appendChild(){},
           querySelector(){ return null; }, querySelectorAll(){ return []; } };
}
const _elements = { pmSubject: makeGenericEl(), pmSubjectRow: makeGenericEl(),
                    pmTopic: makeGenericEl(), pmRun: makeGenericEl(),
                    pmResults: makeGenericEl(), pmModal: makeGenericEl() };
let _mode = 'A';                       // 리메이크(A) 기본
let _postBody = null;
const document = {
  getElementById(id){ return _elements[id] || null; },
  querySelector(sel){
    if (sel.indexOf('pmmode') !== -1) return { value: _mode };
    return null;
  },
  querySelectorAll(sel){ return []; },   // pmToggles 요소행 없음 → elemModes {}
  addEventListener(){},
};
function fetch(url, opts){
  if (String(url).indexOf('/api/wiki/subject') !== -1) {
    return Promise.resolve({ json: async () => ({ ok:true, subject:'감자 스낵 만들기' }) });
  }
  if (String(url).indexOf('/api/wiki/generate') !== -1) {
    _postBody = JSON.parse(opts.body);
    return Promise.resolve({ json: async () => ({ ok:true, drafts:[] }) });
  }
  return Promise.reject(new Error('unmocked fetch: ' + url));
}
function esc(s){ return s; }
// pmRenderDrafts는 END_ANCHOR 밖(잘라낸 범위에 없음)인데 pmRunGen이 부른다 → 스텁 필수.
function pmRenderDrafts(){}
let PM_IDX=null, PM_BASE_STRUCT=null, PM_CATEGORY='레시피', PM_URL='', PM_SHORTCODE='ABC123', PM_BASE_SCRIPT='원본 대본';
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스 ----
"""

_SCENARIO_SUBJECT_SENT = r"""
(async () => {
  await pmPrefillSubject('ABC123');
  const el = document.getElementById('pmSubject');
  if (el.value !== '감자 스낵 만들기') {
    console.error('FAIL: 소재 프리필 안 됨 — value=' + JSON.stringify(el.value)); process.exit(1);
  }
  await pmRunGen();
  if (_postBody === null) { console.error('FAIL: generate 호출 안 됨'); process.exit(1); }
  if (_postBody.subject !== '감자 스낵 만들기') {
    console.error('FAIL: subject가 payload에 안 실림 — ' + JSON.stringify(_postBody.subject)); process.exit(1);
  }
  console.log('PASS');
})();
"""

_SCENARIO_TRANSPLANT_NO_SUBJECT = r"""
(async () => {
  document.getElementById('pmSubject').value = '감자 스낵 만들기';
  document.getElementById('pmTopic').value = '무선 가습기';
  _mode = 'B';                       // 이식 모드
  await pmRunGen();
  if (_postBody === null) { console.error('FAIL: generate 호출 안 됨'); process.exit(1); }
  if (_postBody.subject !== '') {
    console.error('FAIL: 이식 모드인데 subject가 실림 — ' + JSON.stringify(_postBody.subject)); process.exit(1);
  }
  if (_postBody.my_topic !== '무선 가습기') {
    console.error('FAIL: my_topic 누락 — ' + JSON.stringify(_postBody.my_topic)); process.exit(1);
  }
  console.log('PASS');
})();
"""


def _extract() -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    start = text.find(START_ANCHOR)
    end = text.find(END_ANCHOR)
    assert start != -1, f"START_ANCHOR 못 찾음(produce.html이 바뀌었나): {START_ANCHOR!r}"
    assert end != -1 and end > start, f"END_ANCHOR 못 찾음: {END_ANCHOR!r}"
    return text[start:end]


def _run(scenario: str, tmp_path) -> subprocess.CompletedProcess:
    src = _HARNESS_PREFIX + _extract() + scenario
    f = tmp_path / "probe.js"
    f.write_text(src, encoding="utf-8")
    return subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_subject_prefilled_and_sent(tmp_path):
    r = _run(_SCENARIO_SUBJECT_SENT, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_transplant_mode_sends_empty_subject(tmp_path):
    r = _run(_SCENARIO_TRANSPLANT_NO_SUBJECT, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


def test_subject_markup_exists():
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    assert 'id="pmSubject"' in text, "소재 입력칸이 없다"
    assert 'id="pmSubjectRow"' in text, "소재 래퍼가 없다"
    assert ".subject-row" in text, "subject-row CSS가 없다(library.html에만 있으면 스타일이 깨진다)"
