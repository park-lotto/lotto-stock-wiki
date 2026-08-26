"""새로고침하면 매칭 화면이 1단계로 떨어지고 대본이 옛것으로 되돌아간다(2026-08-06).

사장님 제보: "이미 영상도 한 개 만들고 새로고침하니 없어지고, 3개로 나눈 것들 모두
이 화면(1단계)으로 고정됨."

서버 DB 실측(라이브 reference.db)이 원인을 정확히 가리켰다:
  - 클론 job 3개는 **정상**이었다(각자 다른 edit_plan = A/B/C안, 각자 job_id).
  - 그런데 produce_works 3행이 전부 step=0 · title=원본 대본이었고,
    저장 시각(15:49:4x)이 클론 시각(15:29:5x)보다 **20분 늦었다**.
    = 클릭 시점이 아니라 **새로고침 뒤에** 덮어써진 것이다.

뿌리: 그냥 `/produce`로 새로고침하면 `_bootAccountLatestOrLocal`이
`_consumeProduceHandoff()`(sessionStorage 경로)로 로컬 복원을 한다. 그런데 이 경로는
**`cur`(단계)도 `MIX_JOB`도 복원하지 않는다** — 되살리는 건 handoff·script·work_id뿐.
그 상태로 함수 끝에서 `saveWork()`를 부르니 `step:cur`=0과 옛 script가 서버 레코드를
덮어썼다. 서버엔 step·job_id가 멀쩡히 있는데(그래서 `?work=<id>`로 열면 잘 복원된다)
로컬 경로가 그걸 안 보고 0으로 되감은 것이다.

여기서 못 박는 것:
1. 로컬에 work_id가 있으면 **서버 레코드를 이어받는다**(step·job_id 포함).
2. 그 복원이 저장을 덮어쓰지 않는다(step=0으로 되감기 금지).
3. 게이트는 그대로 — 유료 단계(2~6)는 미리보기 전이면 여전히 잠긴다.
"""
import pathlib
import shutil
import subprocess
import tempfile
import os

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")

_HARNESS = r"""
'use strict';
const _ss = {};
global.sessionStorage = {
  setItem:(k,v)=>_ss[k]=v, getItem:k=>(k in _ss?_ss[k]:null), removeItem:k=>delete _ss[k],
};
global.location = { search:'' };
global.history  = { replaceState:()=>{} };
global.HANDOFF = [];
global.WORK_ID = null;
global.MIX_JOB = null;
global.cur = 0;
global.PREVIEW_STATUS = null;
// 전체재생 완주 플래그(2026-08-17) — _restoreWork가 PREVIEW_STATUS와 짝으로 되돌린다.
global.WATCHED_ALL = false;
global.PANEL_COUNT = 8;
global.STATE = { script:'', script_src_idx:null, script_from_wiki:null,
                 deco:{extra_texts:[],motion:null} };
global.PENDING_STYLE_RESTORE = false;
global.canGoNext = ()=> PREVIEW_STATUS==='ready' || PREVIEW_STATUS==='failed' || WATCHED_ALL;
global.stepLocked = (i)=>{ if(i===7) return false; return i>=1 && !!MIX_JOB && !canGoNext(); };
// 저장 호출을 관찰한다 — "복원이 도로 덮어쓰는가"가 이 버그의 핵심이라 payload를 남긴다.
global.SAVED = [];
global._workState = ()=>({handoff:HANDOFF, script:STATE.script||'', step:cur, work_id:WORK_ID});
global.saveWork = ()=>{ SAVED.push(_workState()); };
global.clearWork = ()=>{ delete _ss['produce_work']; };
global._seedSaveBaseline = ()=>{};
global.renderSteps=()=>{}; global.showPanel=()=>{}; global.refreshNextBtn=()=>{};
global.renderPool=()=>{}; global.syncFootageToMixUrls=()=>{}; global.refreshFinalPeek=()=>{};
global.setScriptMode=()=>{}; global.refreshStep0=()=>{}; global.renderCandidates=()=>{};
global._renderMixReviewBody=()=>{}; global._renderPreviewVideo=()=>{};
global._restoreMixContext = async ()=>{};
global.document = { getElementById:()=>({ style:{}, innerHTML:'', textContent:'' }) };
global.URLSearchParams = URLSearchParams;
let RESPONSES = {};
global.setResponses = (r)=>{ RESPONSES = r; };
global.fetch = async (url)=>{
  for (const k of Object.keys(RESPONSES)) if (url.indexOf(k) !== -1) {
    const r = RESPONSES[k];
    if (r === 'throw') throw new Error('네트워크');
    return { json: async () => r };
  }
  throw new Error('스텁 없음: ' + url);
};
"""


def _slice(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i)]


@pytest.fixture(scope="module")
def js():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    # 실제 함수 3개를 그대로 잘라 쓴다(재구현 금지 — 재구현하면 소스가 바뀌어도 안 깨진다).
    restore = _slice(src, "async function _restoreWork(workId){", "// ── 새로고침 복원 렌더 헬퍼")
    consume = _slice(src, "function _consumeProduceHandoff(){", "// 왼쪽 영상 풀 렌더")
    boot = _slice(src, "async function _bootAccountLatestOrLocal(){", "_bootRestore();")
    return _HARNESS + restore + "\n" + consume + "\n" + boot + "\n"


def _run(js, body):
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(js + "\n(async()=>{\n" + body + "\n})();")
        r = subprocess.run([NODE, path], capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    finally:
        os.unlink(path)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_local_restore_recovers_step_and_job_from_server():
    """★버그의 본체. 로컬(sessionStorage)에 work_id가 있으면 서버 레코드를 이어받아
    **단계(step=7 매칭화면)와 job_id**까지 되살려야 한다. 로컬 경로만 타면 cur=0으로
    떨어져 '3개로 나눈 것들이 전부 1단계로 고정'된다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    restore = _slice(src, "async function _restoreWork(workId){", "// ── 새로고침 복원 렌더 헬퍼")
    consume = _slice(src, "function _consumeProduceHandoff(){", "// 왼쪽 영상 풀 렌더")
    boot = _slice(src, "async function _bootAccountLatestOrLocal(){", "_bootRestore();")
    out = _run(_HARNESS + restore + "\n" + consume + "\n" + boot, """
      // 직전 세션이 남긴 로컬 스냅샷 — 단계도 job도 안 들어 있다(이게 정상. 서버가 안다).
      sessionStorage.setItem('produce_work', JSON.stringify(
        {handoff:[{url:'u'}], script:'C안 대본', work_id:'w-clone'}));
      setResponses({
        '/api/produce/works/w-clone': {ok:true, step:7, job_id:'job-clone',
          state:{handoff:[{url:'u'}], script:'C안 대본'}, settings:{}},
        '/api/mix/status/': {ok:true, preview_status:null},
        '/api/mix/result/': {ok:true, beats:[], asset_suggestions:[]},
        '/api/produce/works': {ok:true, works:[{work_id:'w-clone'}]} });
      await _bootAccountLatestOrLocal();
      console.log(JSON.stringify({cur, job:MIX_JOB, wid:WORK_ID}));
    """)
    assert '"cur":7' in out.replace(" ", ""), f"매칭 화면(7)으로 안 돌아왔다 — 1단계 고정 재발: {out}"
    assert '"job":"job-clone"' in out.replace(" ", ""), f"job_id를 못 되살렸다: {out}"


def test_local_restore_does_not_overwrite_step_with_zero():
    """★두 번째 증상('대본이 옛것으로 되돌아감')의 뿌리. 복원 경로가 끝에서 saveWork()를
    부르는데 cur=0·옛 script인 채로 부르면 서버의 멀쩡한 레코드를 덮어쓴다.
    실측: 클론 20분 뒤 step=0·title=원본대본으로 3행이 전부 덮여 있었다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    restore = _slice(src, "async function _restoreWork(workId){", "// ── 새로고침 복원 렌더 헬퍼")
    consume = _slice(src, "function _consumeProduceHandoff(){", "// 왼쪽 영상 풀 렌더")
    boot = _slice(src, "async function _bootAccountLatestOrLocal(){", "_bootRestore();")
    out = _run(_HARNESS + restore + "\n" + consume + "\n" + boot, """
      sessionStorage.setItem('produce_work', JSON.stringify(
        {handoff:[{url:'u'}], script:'C안 대본', work_id:'w-clone'}));
      setResponses({
        '/api/produce/works/w-clone': {ok:true, step:7, job_id:'job-clone',
          state:{handoff:[{url:'u'}], script:'C안 대본'}, settings:{}},
        '/api/mix/status/': {ok:true, preview_status:null},
        '/api/mix/result/': {ok:true, beats:[], asset_suggestions:[]},
        '/api/produce/works': {ok:true, works:[{work_id:'w-clone'}]} });
      await _bootAccountLatestOrLocal();
      console.log(JSON.stringify({bad: SAVED.filter(s=>s.step===0).length, saved:SAVED}));
    """)
    assert '"bad":0' in out.replace(" ", ""), (
        f"복원이 step=0으로 서버 레코드를 덮어썼다(사장님 작업이 1단계로 되감김): {out}")
