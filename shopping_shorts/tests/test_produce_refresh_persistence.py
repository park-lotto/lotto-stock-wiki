"""제작소 위저드 — 새로고침 상태유지(2026-07-19, 사장님 제보).

증상: ① 1단계에서 미리보기까지 만들고 새로고침하면 프리뷰가 사라진다.
      ② 2·3단계에서 새로고침하면 1단계로 되돌아온다.

근본원인은 **저장 side**였다: `?work=<id>`를 URL에 박아 새로고침이 서버 복원(_restoreWork)을
타게 해뒀지만, 대본 확정 **이후**의 상태 변화(MIX_JOB 획득·단계 전진)가 `saveWork()`를 안 불러
서버 작업파일이 낡은 채로 남았다 → 복원이 step=0·job_id=null을 읽어 둘 다 사라졌다.

여기서 검증하는 것:
  - jump()/go(): 단계 이동이 saveWork()를 부른다(=step이 서버에 남는다). 게이트는 여전히 막는다.
  - startProduceMix(): MIX_JOB을 잡은 직후 saveWork()를 부른다(=job_id가 서버에 남는다).
  - _restoreWork(): 복원 시 미리보기 <video>와 편집안을 다시 그린다. 단계도 되살린다.
    단, 미리보기 미확인(preview_status!='ready')이면 게이트 재동기가 1단계로 되돌린다(유료 우회 차단).
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _slice(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


def _run(js, body):
    r = subprocess.run([NODE, "-e", js + "\n(async()=>{\n" + body + "\n})();"],
                       capture_output=True, text=True, timeout=30,
                       encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


# ── 저장 side: 단계 이동이 서버에 남는가 ────────────────────────
_NAV_HARNESS = r"""
'use strict';
let cur = 0, MIX_JOB = null, PREVIEW_STATUS = null, _saves = 0;
// Task 2(2026-07-23): jump/go가 오브 표시축(STEP_LABELS)과 실제 패널축(ORB_TO_PANEL)을 나눠
// 쓴다 — 슬라이스에 안 담기는 심볼이라 실제 소스와 같은 값으로 여기서 준다.
const STEP_LABELS = ['대본','화면 붙이기','TTS','꾸미기','썸네일','SEO','최종'];
const ORB_TO_PANEL = [0, 7, 2, 3, 4, 5, 6];
const PANEL_TO_ORB = Object.fromEntries(ORB_TO_PANEL.map((p,o)=>[p,o]));
function orbIndex(){ return PANEL_TO_ORB[cur] ?? 0; }
function canGoNext(){ return PREVIEW_STATUS === 'ready' || PREVIEW_STATUS === 'failed'; }
// T7 게이트(origin/main 병합, 2026-07-20): 0→1 미리보기 게이트를 stepLocked 단일화로 흡수.
// jump/go가 canGoNext 대신 stepLocked를 보므로 소스와 동일 구현을 스텁한다(1단계+ 매칭후·미리보기전 잠금).
// ★Task 6(2026-07-23): 화면 붙이기(매칭, 패널7)는 게이트 예외 — 후보를 고르고 미리보기를
// "만드는" 자리 자체라 여기서 막으면 미리보기를 영영 못 만든다. 소스와 동일하게 스텁한다.
function stepLocked(i){ if(i === 7) return false; return i >= 1 && !!MIX_JOB && !canGoNext(); }
function stepLockMsg(){ return !MIX_JOB ? '먼저 1단계에서 영상을 매칭하세요' : '먼저 1단계에서 미리보기를 확인하세요'; }
function toast(){}
function renderSteps(){}
function showPanel(){}
function saveWork(){ _saves++; }
"""


@pytest.fixture(scope="module")
def js_nav():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    # ★Task 2(2026-07-23): jump(i) → jump(o) — 파라미터명이 오브(표시) 인덱스로 바뀌었다.
    return _NAV_HARNESS + _slice(src, "function jump(o){", "// ── 1단계 대본: 3모드")


def test_step_navigation_persists_and_gate_holds(js_nav):
    """★단계 이동은 saveWork()를 불러야 한다 — 안 부르면 서버 step이 0에 멈춰 새로고침이 1단계로 되돌린다.

    ★Task 6(2026-07-23): 화면 붙이기(매칭, 패널7=오브1)가 게이트 예외가 됐다 — 후보를 고르고
    미리보기를 "만드는" 자리 자체이므로, 여기 들어가는 걸 막으면 미리보기를 영영 못 만든다.
    게이트는 그 다음 단계(음성=오브2)부터 다시 적용된다.

    ① 제작소(0)→화면 붙이기(1=패널7)는 미리보기 여부와 무관하게 항상 열린다 — 저장도 된다.
    ② 화면 붙이기(패널7)에서 그 다음(음성)으로는 미리보기 미확인이면 막힌다(게이트) — 저장 없음.
    ③ 미리보기 ready면 go(1)로 전진하고 **저장한다**.
    ④ jump(앞 단계)도, ⑤ go(-1) 뒤로가기도 저장한다(뒤로 간 자리도 새로고침이 지켜야 한다).
    """
    out = _run(js_nav, """
      const r = {};
      // ① 화면 붙이기(매칭)는 게이트 예외 — 미리보기 없이도 들어간다 + 저장한다
      cur = 0; MIX_JOB = 'j1'; PREVIEW_STATUS = null; _saves = 0;
      go(1); r.matchCur = cur; r.matchSaves = _saves;
      // ② 게이트: 화면 붙이기에서 그 다음(음성)으로는 미리보기 없이 못 간다
      _saves = 0;
      go(1); r.gatedCur = cur; r.gatedSaves = _saves;
      // ③ 미리보기 ready → 전진 + 저장
      PREVIEW_STATUS = 'ready'; _saves = 0;
      go(1); r.fwdCur = cur; r.fwdSaves = _saves;
      // ④ jump 앞으로 → 저장
      _saves = 0; jump(3); r.jumpCur = cur; r.jumpSaves = _saves;
      // ⑤ go(-1) 뒤로 → 저장
      _saves = 0; go(-1); r.backCur = cur; r.backSaves = _saves;
      console.log(JSON.stringify(r));
    """)
    assert '"matchCur":7' in out, f"①화면 붙이기(매칭) 패널이 게이트에 막혔다: {out}"
    assert '"matchSaves":1' in out, f"①전진했는데 saveWork 미호출: {out}"
    assert '"gatedCur":7' in out, f"②게이트가 뚫렸다 — 미리보기 없이 음성 단계로 갔다: {out}"
    assert '"gatedSaves":0' in out, f"②막혔는데 저장했다(return 전에 saveWork): {out}"
    assert '"fwdCur":2' in out, f"③미리보기 ready인데 전진 못 했다: {out}"
    assert '"fwdSaves":1' in out, f"③전진했는데 saveWork 미호출 — 서버 step이 0에 멈춰 새로고침이 1단계로 되돌린다(증상2): {out}"
    assert '"jumpCur":3' in out and '"jumpSaves":1' in out, f"④jump가 저장 안 했다: {out}"
    assert '"backCur":2' in out and '"backSaves":1' in out, f"⑤go(-1)가 저장 안 했다: {out}"


def test_start_mix_persists_job_id():
    """★startProduceMix가 MIX_JOB을 잡은 직후 saveWork()를 불러야 job_id가 서버에 남는다.

    안 남기면 새로고침 시 _restoreWork가 job_id=null을 읽어 미리보기·편집안이 통째로 사라진다(증상1).
    슬라이스 실행 대신 소스에서 순서를 확인한다(startProduceMix는 fetch·DOM·SBLoader 의존이 많다).
    """
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    body = _slice(src, "async function startProduceMix(){", "async function pollMix(){")
    assert "MIX_JOB=d.job_id" in body, "MIX_JOB 대입이 사라졌다 — 테스트 앵커 갱신 필요"
    i = body.index("MIX_JOB=d.job_id")
    assert "saveWork()" in body[i:], (
        "MIX_JOB을 잡은 뒤 saveWork()를 안 부른다 — 새 job이 서버에 안 남아 새로고침이 미리보기를 잃는다(증상1)")


# ── 복원 side: 새로고침이 미리보기 video·편집안·단계를 되살리는가 ──
_RESTORE_HARNESS = r"""
'use strict';
let HANDOFF = [], cur = 0, MIX_JOB = null, WORK_ID = null, PREVIEW_STATUS = null;
let STYLE_TOUCHED = false, PENDING_STYLE_RESTORE = false, MIX_REVIEW_SUGGESTIONS = [];
const STATE = { script:'', script_src_idx:null, script_from_wiki:null,
                subtitleRemoval:false, headcopy:null, captionStyle:null,
                deco:{ extra_texts:[], motion:null } };
const STEP_LABELS = ['대본','화면 붙이기','TTS','꾸미기','썸네일','SEO','최종'];
// Task 6(2026-07-23): cur 바운드는 PANEL_COUNT(물리 패널 수, 지금 8)를 쓴다 — STEP_LABELS.length
// (오브 라벨 수)와는 다른 축이다.
const PANEL_COUNT = 8;
function canGoNext(){ return PREVIEW_STATUS === 'ready' || PREVIEW_STATUS === 'failed'; }
// ★_restoreWork의 게이트 재동기는 stepLocked() 하나만 본다(2026-07-26). 예전엔 복원 쪽이
// canGoNext로 게이트를 **다시 구현**해 패널7 예외를 몰랐고, 매칭 화면에서 새로고침하면
// 1단계로 쫓겨났다(사장님 제보). 소스와 동일 구현을 스텁한다.
function stepLocked(i){ if(i === 7) return false; return i >= 1 && !!MIX_JOB && !canGoNext(); }
function refreshNextBtn(){}
function renderSteps(){}
function showPanel(){}
function renderPool(){}
function syncFootageToMixUrls(){}
function refreshFinalPeek(){}
function setScriptMode(){}
function _consumeProduceHandoff(){}
function renderCoverageSignal(){ return ''; }
function renderSwapButton(){ return ''; }
function renderSceneCutaway(){ return ''; }
function renderSceneSfx(){ return ''; }
function renderTrimControls(){ return ''; }
function esc(s){ return s || ''; }
const _els = {};
function _el(id){ if(!_els[id]) _els[id] = {innerHTML:'', style:{}, disabled:false, textContent:''}; return _els[id]; }
const document = { getElementById: _el };
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


@pytest.fixture(scope="module")
def js_restore():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return _RESTORE_HARNESS + _slice(src, "async function _restoreWork(workId){",
                                     "function _consumeProduceHandoff(){")


def test_restore_renders_preview_and_step_but_gate_relocks(js_restore):
    """★복원 3시나리오를 한 node 프로세스에서:

    ① step0·미리보기 ready: 1단계로 복원 + 미리보기 <video>·편집안 다시 그린다(증상1 해소).
    ② step2·미리보기 ready: 2단계로 복원한다(증상2 해소).
    ③ step2·미리보기 rendering(미확인): 게이트 재동기가 1단계로 되돌린다(유료 자막제거 우회 차단).
    """
    beats = ("[{role:'훅',narration:'n',primary:{video_id:'v',start:0,end:3},"
             "target_seconds:3,fit:5}]")
    out = _run(js_restore, f"""
      function reset(){{ cur=0; MIX_JOB=null; PREVIEW_STATUS=null;
        for(const k of Object.keys(_els)) delete _els[k]; }}
      const r = {{}};
      // ① step0 + ready
      reset();
      RESPONSES = {{ '/api/produce/works/': {{ok:true, step:0, job_id:'job-9',
          state:{{handoff:[{{url:'u'}}], script:'대본'}}, settings:{{}}}},
        '/api/mix/status/': {{ok:true, preview_status:'ready'}},
        '/api/mix/result/': {{ok:true, beats:{beats}, asset_suggestions:[]}} }};
      await _restoreWork('w-1');
      r.s0 = {{cur, video:_el('mixPreview').innerHTML.indexOf('<video')>=0,
               review:_el('mixReview').innerHTML.indexOf('편집안')>=0}};
      // ② step2 + ready
      reset();
      RESPONSES = {{ '/api/produce/works/': {{ok:true, step:2, job_id:'job-9',
          state:{{handoff:[{{url:'u'}}], script:'대본'}}, settings:{{}}}},
        '/api/mix/status/': {{ok:true, preview_status:'ready'}},
        '/api/mix/result/': {{ok:true, beats:{beats}, asset_suggestions:[]}} }};
      await _restoreWork('w-2');
      r.s2 = {{cur}};
      // ③ step2 + rendering(미확인) → 게이트가 1단계로 되돌림
      reset();
      RESPONSES = {{ '/api/produce/works/': {{ok:true, step:2, job_id:'job-9',
          state:{{handoff:[{{url:'u'}}], script:'대본'}}, settings:{{}}}},
        '/api/mix/status/': {{ok:true, preview_status:'rendering'}},
        '/api/mix/result/': {{ok:true, beats:{beats}, asset_suggestions:[]}} }};
      await _restoreWork('w-3');
      r.gate = {{cur}};
      // ④ step7(화면 붙이기=매칭) + rendering(미확인) → 게이트 예외라 그 자리를 지킨다
      reset();
      RESPONSES = {{ '/api/produce/works/': {{ok:true, step:7, job_id:'job-9',
          state:{{handoff:[{{url:'u'}}], script:'대본'}}, settings:{{}}}},
        '/api/mix/status/': {{ok:true, preview_status:'rendering'}},
        '/api/mix/result/': {{ok:true, beats:{beats}, asset_suggestions:[]}} }};
      await _restoreWork('w-4');
      r.match = {{cur}};
      console.log(JSON.stringify(r));
    """)
    assert '"s0":{"cur":0,"video":true,"review":true}' in out, (
        f"①새로고침이 미리보기 <video>/편집안을 못 되살렸다(증상1): {out}")
    assert '"s2":{"cur":2}' in out, f"②2단계 복원 실패 — 1단계로 떨어진다(증상2): {out}"
    assert '"gate":{"cur":0}' in out, (
        f"③미리보기 미확인인데 2단계로 복원됐다 — 유료 자막제거 게이트 우회: {out}")
    assert '"match":{"cur":7}' in out, (
        f"④매칭(화면 붙이기) 화면에서 새로고침했더니 1단계로 쫓겨났다 — 미리보기를 '만드는' "
        f"자리라 게이트 예외인데 복원 쪽이 게이트를 다시 구현해 예외를 몰랐다(2026-07-26 제보): {out}")
