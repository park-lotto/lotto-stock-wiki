"""작업 복원 — 단계까지 그대로, 단 **게이트는 우회하지 않는다**(스펙 §4.5·§6).

★이 파일의 존재 이유: 복원의 `cur = d.step`이 jump()/go()를 안 거쳐 미리보기 게이트를
건너뛴다. 그러면 미리보기를 한 번도 안 본 채 유료 자막제거(VMake)로 넘어간다 — 게이트를
만든 이유가 통째로 무효가 된다. C-1/C-3와 같은 종류의 구멍이 될 자리다.
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_RESTORE_START = "async function _restoreWork(workId){"
_RESTORE_END = "function _consumeProduceHandoff(){"

_HARNESS = r"""
'use strict';
let HANDOFF = [];
const STATE = { script:'', script_src_idx:null, script_from_wiki:null };
const STEP_LABELS = ['대본','화면 붙이기','TTS','꾸미기','최종'];
// ★Task 6(2026-07-23): cur(패널 인덱스) 범위 체크는 STEP_LABELS.length(오브 라벨 수)가 아니라
// PANEL_COUNT(물리 패널 수)를 쓴다 — 신규 매칭 패널(data-step=7)이 생겨 둘이 갈라졌다(7 vs 8).
const PANEL_COUNT = 8;
let cur = 0, MIX_JOB = null, WORK_ID = null, PREVIEW_STATUS = null;
let STYLE_TOUCHED = false, PENDING_STYLE_RESTORE = false;   // 꾸미기 스타일 복원 플래그(C-2 잔여)
function canGoNext(){ return PREVIEW_STATUS === 'ready' || PREVIEW_STATUS === 'failed'; }
// _restoreWork의 게이트 재동기는 stepLocked() 하나만 본다(2026-07-26) — 소스와 동일 스텁.
// 패널7(화면 붙이기=매칭)은 미리보기를 '만드는' 자리라 게이트 예외다.
function stepLocked(i){ if(i === 7) return false; return i >= 1 && !!MIX_JOB && !canGoNext(); }
let NEXT_DISABLED = null;
// !!(...): 실제 코드의 `b.disabled = gated`는 DOM boolean IDL 프로퍼티라 대입 시 ToBoolean으로
// 강제변환된다(null → false). 이 스텁은 DOM이 아닌 평범한 변수라 그 강제변환을 흉내낸다 —
// 안 하면 MIX_JOB이 null일 때 단락평가로 NEXT_DISABLED가 null이 되어 실제 브라우저 동작과 어긋난다.
function refreshNextBtn(){ NEXT_DISABLED = !!(cur === 0 && MIX_JOB && !canGoNext()); }
let _refreshCalls = 0;
const _realRefresh = refreshNextBtn;
refreshNextBtn = function(){ _refreshCalls++; _realRefresh(); };
function renderSteps(){}
function showPanel(){}
function renderPool(){}
function syncFootageToMixUrls(){}
function refreshFinalPeek(){}
function setScriptMode(){}
let _consumeCalls = 0;
function _consumeProduceHandoff(){ _consumeCalls++; }
const _store = {};
const sessionStorage = { setItem(k,v){_store[k]=v;}, getItem(k){return _store[k]||null;},
                         removeItem(k){delete _store[k];} };
// 서버 응답은 테스트마다 갈아끼운다.
let RESPONSES = {};
async function fetch(url){
  for (const k of Object.keys(RESPONSES)) if (url.indexOf(k) !== -1) {
    const r = RESPONSES[k];
    if (r === 'throw') throw new Error('네트워크');
    return { json: async () => r };
  }
  throw new Error('스텁 없음: ' + url);
}
"""


def _slice(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


@pytest.fixture(scope="module")
def js():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return _HARNESS + _slice(src, _RESTORE_START, _RESTORE_END)


def _run(js, body):
    # encoding="utf-8", errors="replace": 기본(cp949) 캡처는 한글 console.log를 못 읽어 죽는다
    # (test_produce_preview_gate.py와 같은 저장소 전역 함정, 336번 줄 참고).
    r = subprocess.run([NODE, "-e", js + "\n(async()=>{\n" + body + "\n})();"],
                       capture_output=True, text=True, timeout=30,
                       encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def test_restores_script_and_handoff(js):
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:0, job_id:null,
        state:{handoff:[{url:'https://x/1'}], script:'복원된 대본', script_src_idx:2,
               script_from_wiki:'ABC'}}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({script:STATE.script, n:HANDOFF.length,
                                  idx:STATE.script_src_idx, wiki:STATE.script_from_wiki,
                                  wid:WORK_ID}));
    """)
    assert "복원된 대본" in out and '"n": 1' in out.replace('"n":1', '"n": 1')
    assert '"idx": 2' in out.replace('"idx":2', '"idx": 2')
    assert "ABC" in out and "w-1" in out


def test_restores_step_when_preview_was_seen(js):
    """미리보기를 봤던 작업(preview_status=ready)은 그 단계로 돌아간다 — '단계까지 그대로'."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:2, job_id:'job-9', state:{script:'대본'}},
                   '/api/mix/status/': {ok:true, preview_status:'ready'}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur, preview:PREVIEW_STATUS, job:MIX_JOB}));
    """)
    assert '"cur": 2' in out.replace('"cur":2', '"cur": 2')
    assert "ready" in out and "job-9" in out


def test_restore_does_not_bypass_the_gate(js):
    """★핵심. 미리보기를 안 본 작업이 2단계로 저장돼 있어도 1단계로 되돌린다.

    안 그러면 미리보기를 한 번도 안 본 채 유료 자막제거(VMake)로 넘어간다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:2, job_id:'job-9', state:{script:'대본'}},
                   '/api/mix/status/': {ok:true, preview_status:null}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur, disabled:NEXT_DISABLED, refreshed:_refreshCalls>0}));
    """)
    assert '"cur": 0' in out.replace('"cur":0', '"cur": 0'), "게이트를 우회해 2단계로 복원됐다"
    assert '"disabled": true' in out.replace('"disabled":true', '"disabled": true'), \
        "다음 버튼이 안 잠겼다"
    assert "true" in out


def test_failed_preview_still_lets_you_through(js):
    """렌더가 고장난 작업까지 가둘 순 없다 — 'failed'는 탈출구다(1단계 미리보기 스펙 §7.1)."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:2, job_id:'job-9', state:{script:'대본'}},
                   '/api/mix/status/': {ok:true, preview_status:'failed'}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur}));
    """)
    assert '"cur": 2' in out.replace('"cur":2', '"cur": 2')


def test_no_job_means_no_gate(js):
    """매칭 전 작업(job 없음)은 게이트 대상이 아니다 — 미리보기할 게 애초에 없다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:0, job_id:null, state:{script:'대본'}}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur, job:MIX_JOB, disabled:NEXT_DISABLED}));
    """)
    assert '"cur": 0' in out.replace('"cur":0', '"cur": 0')
    assert '"disabled": false' in out.replace('"disabled":false', '"disabled": false')


def test_bogus_step_does_not_escape_the_wizard(js):
    """서버가 이상한 step을 줘도 STEPS 범위를 벗어나면 안 된다 — showPanel이 죽는다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:99, job_id:null, state:{script:'대본'}}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur}));
    """)
    assert '"cur": 0' in out.replace('"cur":0', '"cur": 0')


def test_restores_step_7_matching_panel(js):
    """★Task 6: 신규 매칭 패널(data-step=7)이 생겨 물리 패널 수가 8이 됐다 — 이건 오브 라벨 수
    (STEP_LABELS.length=7과는 다른 축이다. cur 복원 바운드가 STEP_LABELS.length에 그대로 걸리면
    7단계(화면 붙이기)는 범위 밖으로 오판돼 0으로 튕긴다(Task2 리뷰 Minor②) — PANEL_COUNT(8)를
    써야 한다. 매칭 전(job_id 없음)이라 게이트 재동기에도 안 걸린다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:7, job_id:null, state:{script:'대본'}}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur}));
    """)
    assert '"cur": 7' in out.replace('"cur":7', '"cur": 7'), (
        "매칭 패널(step:7)로 복원되지 않았다 — PANEL_COUNT 바운드 확인: " + out)


def test_restores_matching_panel_even_before_preview(js):
    """★2026-08-06 사장님 제보: "3개로 나눈 것들 모두 이 화면(1단계)으로 고정됨".

    '따로 만들기'로 갈라진 작업은 **job은 있는데 미리보기는 아직 안 본** 상태로 저장된다
    (preview_status=null). 그 조합에서 복원이 `stepLocked(cur)`에 걸려 7(매칭 화면)을
    0으로 되감았다 — 대본 후보 A/B/C를 고르는 자리가 바로 그 화면인데 거기서 쫓겨나니
    3편을 따로 만들 방법이 사라진다.

    stepLocked() 자신은 패널7을 예외로 둔다(`if(i===7) return false`) — 즉 이 되감기는
    게이트의 뜻이 아니었다. 기존 test_restores_step_7_matching_panel은 job_id:null이라
    게이트 자체를 안 태워서 이 조합을 못 잡았다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:7, job_id:'job-9', state:{script:'대본'}},
                   '/api/mix/status/': {ok:true, preview_status:null}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur}));
    """)
    assert '"cur": 7' in out.replace('"cur":7', '"cur": 7'), (
        "미리보기 전이라고 매칭 화면에서 1단계로 쫓겨났다 — 후보를 고를 자리가 없어진다: " + out)


def test_gate_still_holds_for_paid_steps_after_the_panel7_fix(js):
    """★위 수정이 게이트를 뚫으면 안 된다 — 패널7만 예외고 2~6단계(유료 자막제거 등)는 그대로 잠근다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:2, job_id:'job-9', state:{script:'대본'}},
                   '/api/mix/status/': {ok:true, preview_status:null}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur}));
    """)
    assert '"cur": 0' in out.replace('"cur":0', '"cur": 0'), "유료 단계 게이트가 뚫렸다: " + out


def test_missing_work_falls_back_to_old_path(js):
    """지워진 작업의 링크를 눌러도 빈 화면이 되면 안 된다 — 기존 복원 경로로 떨어진다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:false, error:'작업 없음'}};
      await _restoreWork('없는id');
      console.log(String(_consumeCalls));
    """)
    assert out == "1"


def test_network_error_falls_back_too(js):
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': 'throw'};
      await _restoreWork('w-1');
      console.log(String(_consumeCalls));
    """)
    assert out == "1"


def test_status_error_does_not_open_the_gate(js):
    """미리보기 상태를 못 읽으면 **잠근 채로** 둔다 — 모르면 안전한 쪽이다."""
    out = _run(js, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:2, job_id:'job-9', state:{script:'대본'}},
                   '/api/mix/status/': 'throw'};
      await _restoreWork('w-1');
      console.log(JSON.stringify({cur, preview:PREVIEW_STATUS}));
    """)
    assert '"cur": 0' in out.replace('"cur":0', '"cur": 0'), "상태를 못 읽었는데 게이트가 열렸다"
    assert '"preview": null' in out.replace('"preview":null', '"preview": null')
