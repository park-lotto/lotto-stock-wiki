"""작업 저장 배선 — 대본만 확정해도 서버에 남는다 + 디바운스(스펙 §4.3).

produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다(test_produce_preview_gate.py와
같은 방식 — 재구현이 아니다).

★2026-07-17 실측: 대본확정 두 경로(useDraft·pmUseDraft)가 모두 호출부마다 HANDOFF 길이를
검사한 뒤에만 saveWork()를 불렀다 — 영상을 안 담은 채 대본만 확정하면 저장이 아예 안 일어났다.
가드를 saveWork() 안으로 옮기는 게 이 태스크의 요지 — 그래서 useDraft/pmUseDraft를 슬라이스에 넣는다.

★복원 쪽 구멍 2개(제작소를 열 때마다 작업 복제 / 대본만 있는 작업이 로컬 복원조차 안 됨)를
같이 잠근다 — _consumeProduceHandoff를 슬라이스에 넣는 js_consume 픽스처.

★비동기는 실제로 굴린다. `_pushWork`가 진짜 `await fetch(...)`를 타므로, `saveWork` → 디바운스
타이머 발동 → `_pushWork` 실행 → `fetch` 응답의 `work_id`가 `WORK_ID`에 반영, 순서가 실제로
돌아야 두 번째 저장이 같은 work_id를 싣는지 확인할 수 있다. 그래서 `tick()`은 타이머를 발동시킨
뒤 마이크로태스크를 여러 번 양보(await Promise.resolve() 반복)해 그 안의 await 체인이 실제로
끝까지 진행되게 하고, 테스트 본문 전체를 async IIFE로 감싸 `await tick(...)`을 쓴다.
"""
import pathlib
import shutil
import subprocess
import tempfile

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# useDraft = 조합초안 확정. saveWork 정의 = 저장의 유일한 문. 둘 다 실제 소스로 돌린다.
_USEDRAFT_START = "function useDraft(i){"
_USEDRAFT_END = "async function postDrafts("
# WORK_ID/_workState/_pushWork 선언이 saveWork() **앞**에 온다 — 앵커를 saveWork()로 잡으면
# 이 선언부를 놓쳐 WORK_ID가 ReferenceError로 죽는다. 그래서 그 앞의 선언부에서 슬라이스를 시작한다.
_SAVE_START = "let WORK_ID = null;"
_SAVE_END = "function _consumeProduceHandoff(){"
_CONSUME_START = "function _consumeProduceHandoff(){"
_CONSUME_END = "// 왼쪽 영상 풀 렌더"

_HARNESS = r"""
'use strict';
let HANDOFF = [];
const STATE = { script:'', script_src_idx:null, script_from_wiki:null };
let cur = 0;
let MIX_JOB = null;
const _store = {};
const sessionStorage = {
  setItem(k,v){ _store[k]=v; }, getItem(k){ return _store[k]||null; }, removeItem(k){ delete _store[k]; },
};
// 가짜 시계 — 디바운스가 "실제로 도는지" 보려면 타이머를 진짜로 굴려야 한다.
let _now = 0, _seq = 0;
const _timers = new Map();
function setTimeout(fn, ms){ const id=++_seq; _timers.set(id,{fn, at:_now+(ms||0)}); return id; }
function clearTimeout(id){ _timers.delete(id); }
async function tick(ms){
  _now += ms;
  for (const [id,t] of [..._timers]) if (t.at <= _now) { _timers.delete(id); t.fn(); }
  // 발동된 콜백(_pushWork 등)이 await fetch(...)를 타면 그 이어지는 마이크로태스크가 실제로
  // 끝까지 돌 시간을 준다 — 스텁으로 건너뛰면 WORK_ID 갱신 같은 부작용이 안 보인다.
  for (let i=0;i<10;i++) await Promise.resolve();
}
// fetch 기록 — POST가 몇 번 나갔나가 이 테스트의 전부다. 진짜 async 체인으로 응답한다(즉시값 아님).
const POSTS = [];
async function fetch(url, opt){
  POSTS.push({url, body: JSON.parse((opt&&opt.body)||'{}')});
  return { json: async () => ({ ok:true, work_id:'w-server-1' }) };
}
function setScriptMode(){}
function refreshFinalPeek(){}
const window = globalThis;   // useDraft가 window._drafts를 읽는다(브라우저 전역)
// _pushWork가 저장 성공 후 URL에 ?work=<id>를 박는다(2026-07-19). 새로고침이 서버 복원 경로를
// 타게 하는 배선 — location/history를 스텁해 그 replaceState 호출을 관찰한다.
const _replaced = [];
const location = { search:'', pathname:'/produce', href:'/produce' };
const history = { replaceState(s, t, url){
  _replaced.push(url);
  location.search = url.indexOf('?') >= 0 ? url.slice(url.indexOf('?')) : '';
} };
"""

_SHIMS = r"""
// 슬라이스 밖 함수들 — 이 테스트의 관심사가 아니다.
"""

# js_consume 전용 하네스 — _consumeProduceHandoff가 부르는 렌더/동기화 함수들을 스텁한다.
_CONSUME_HARNESS = r"""
'use strict';
let HANDOFF = [];
const STATE = { script:'', script_src_idx:null, script_from_wiki:null };
let cur = 0;
let MIX_JOB = null;
const _store = {};
const sessionStorage = {
  setItem(k,v){ _store[k]=v; }, getItem(k){ return _store[k]||null; }, removeItem(k){ delete _store[k]; },
};
let _now = 0, _seq = 0;
const _timers = new Map();
function setTimeout(fn, ms){ const id=++_seq; _timers.set(id,{fn, at:_now+(ms||0)}); return id; }
function clearTimeout(id){ _timers.delete(id); }
async function tick(ms){
  _now += ms;
  for (const [id,t] of [..._timers]) if (t.at <= _now) { _timers.delete(id); t.fn(); }
  for (let i=0;i<10;i++) await Promise.resolve();
}
const POSTS = [];
async function fetch(url, opt){
  POSTS.push({url, body: JSON.parse((opt&&opt.body)||'{}')});
  return { json: async () => ({ ok:true, work_id:'w-server-1' }) };
}
function setScriptMode(){}
function refreshFinalPeek(){}
function renderPool(){}
function syncFootageToMixUrls(){}
const document = { getElementById(){ return null; } };
"""


def _slice(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


@pytest.fixture(scope="module")
def js():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return (_HARNESS
            + _slice(src, _SAVE_START, _SAVE_END)
            + _slice(src, _USEDRAFT_START, _USEDRAFT_END)
            + _SHIMS)


@pytest.fixture(scope="module")
def js_consume():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return (_CONSUME_HARNESS
            + _slice(src, _SAVE_START, _SAVE_END)
            + _slice(src, _CONSUME_START, _CONSUME_END))


def _run(js, body):
    # 본문 전체를 async IIFE로 감싼다 — tick()이 진짜 await 체인을 굴리는 async 함수라
    # 테스트 본문에서 `await tick(...)`을 쓰려면 top-level await가 필요한데, node -e는
    # CommonJS라 top-level await를 못 쓴다. IIFE로 우회한다.
    wrapped = (js + "\n(async () => {\n" + body
               + "\n})().catch(e => { console.error(e && e.stack || String(e)); process.exit(1); });")
    # ★`node -e wrapped`로 넘기지 않는다 — 슬라이스한 JS가 커지면 윈도우 명령줄 상한
    # (32KB)을 넘겨 FileNotFoundError [WinError 206]으로 죽는다(2026-07-29 실측:
    # produce.html에 쿠팡 검색 UI가 붙자 이 파일 3건이 동시에 깨졌다). 파일로 넘기면
    # 길이 제한이 사라진다.
    with tempfile.TemporaryDirectory() as td:
        script = pathlib.Path(td) / "case.js"
        script.write_text(wrapped, encoding="utf-8")
        r = subprocess.run([NODE, str(script)],
                            capture_output=True, text=True, timeout=30,
                            encoding="utf-8",
                            stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def test_script_only_still_saves(js):
    """★영상이 하나도 없어도 대본을 확정하면 저장된다 — 사장님이 잃어버린 구간."""
    out = _run(js, """
      globalThis._drafts = [{script:'감자 레시피 대본'}];
      HANDOFF = [];                 // 영상 안 담음
      useDraft(0);
      await tick(1500);
      console.log(JSON.stringify({posts: POSTS.length, script: (POSTS[0]||{}).body?.state?.script}));
    """)
    d = eval(out.replace("null", "None").replace("true", "True").replace("false", "False"))
    assert d["posts"] == 1, "대본만 확정한 작업이 서버에 안 남는다"
    assert d["script"] == "감자 레시피 대본"


def test_debounce_collapses_bursts(js):
    """saveWork를 10번 불러도 POST는 1번 — 입력마다 서버를 두들기면 안 된다(스펙 §4.3)."""
    out = _run(js, """
      STATE.script = '대본';
      for (let i=0;i<10;i++) saveWork();
      console.log(JSON.stringify({before: POSTS.length}));
      await tick(1500);
      console.log(JSON.stringify({after: POSTS.length}));
    """)
    before, after = out.splitlines()
    assert '"before": 0' in before or '"before":0' in before, "디바운스 전에 POST가 나갔다"
    assert '"after": 1' in after or '"after":1' in after, f"디바운스가 안 돈다: {after}"


def test_sessionstorage_write_is_immediate(js):
    """로컬 복원은 빠른 게 값이다 — sessionStorage는 디바운스하지 않는다."""
    out = _run(js, """
      STATE.script = '즉시';
      saveWork();
      console.log(sessionStorage.getItem('produce_work') ? 'written' : 'missing');
    """)
    assert out == "written"


def test_truly_empty_work_is_not_saved(js):
    """영상도 대본도 없으면 안 쓴다 — 빈 작업이 목록을 더럽히면 안 된다."""
    out = _run(js, """
      HANDOFF = []; STATE.script = '';
      saveWork(); await tick(1500);
      console.log(String(POSTS.length));
    """)
    assert out == "0"


def test_work_id_is_reused_after_first_save(js):
    """서버가 준 work_id를 다음 저장에 실어야 같은 작업이 갱신된다 — 안 그러면 매번 새 작업이 쌓인다."""
    out = _run(js, """
      STATE.script = '첫 저장'; saveWork(); await tick(1500);
      STATE.script = '둘째 저장'; saveWork(); await tick(1500);
      console.log(JSON.stringify({posts: POSTS.length, second: POSTS[1].body.work_id}));
    """)
    assert '"posts": 2' in out or '"posts":2' in out
    assert "w-server-1" in out, "두 번째 POST가 work_id를 안 실었다 — 작업이 중복 생성된다"


def test_step_and_job_ride_along(js):
    """복원이 '단계까지 그대로'가 되려면 step·job_id가 저장에 실려야 한다(스펙 §3)."""
    out = _run(js, """
      STATE.script = '대본'; cur = 1; MIX_JOB = 'job-77';
      saveWork(); await tick(1500);
      console.log(JSON.stringify({step: POSTS[0].body.step, job: POSTS[0].body.job_id}));
    """)
    assert '"step": 1' in out or '"step":1' in out
    assert "job-77" in out


def test_saved_work_pins_work_id_into_url(js):
    """★새로고침이 서버 복원 경로를 타게 URL에 ?work=<id>를 박는다(2026-07-19 사장님 제보:
    상위 단계에서 새로고침하면 1단계로 돌아옴). sessionStorage 경로는 MIX_JOB·단계를 복원하지
    않으니, WORK_ID가 서버에서 확정되는 순간 URL에 박아 refresh가 _restoreWork를 타게 한다."""
    out = _run(js, """
      location.search = '';
      STATE.script = '대본'; saveWork(); await tick(1500);
      console.log(JSON.stringify({replaced:_replaced, search:location.search}));
    """)
    assert "?work=w-server-1" in out, f"저장 후 URL에 ?work=가 안 박혔다: {out}"


def test_url_not_replaced_when_already_on_that_work(js):
    """이미 ?work=<그 id>면 다시 replaceState하지 않는다 — 히스토리를 더럽히지 않는다."""
    out = _run(js, """
      location.search = '?work=w-server-1';
      STATE.script = '대본'; saveWork(); await tick(1500);
      console.log(JSON.stringify({replaced:_replaced}));
    """)
    assert '"replaced": []' in out or '"replaced":[]' in out, (
        f"같은 작업인데 URL을 또 갈아끼웠다: {out}")


def test_no_guard_left_at_call_sites():
    """★가드가 호출부에 남아 있으면 이 기능은 절반만 작동한다 — 소스를 직접 본다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "if(HANDOFF.length) saveWork()" not in src, (
        "호출부에 HANDOFF.length 가드가 남아 있다 — 대본만 확정한 작업이 저장되지 않는다")


def test_reopening_does_not_duplicate_the_work(js_consume):
    """★제작소를 다시 열어도 같은 작업이다 — WORK_ID를 안 되살리면 열 때마다 새 작업이 쌓인다.

    _consumeProduceHandoff는 끝에서 saveWork()를 무조건 부른다. clearWork()는 정의만 되고
    아무도 안 부르므로(호출 0곳) sessionStorage가 영원히 남아 매 로드가 복원+재저장을 탄다."""
    out = _run(js_consume, """
      _store['produce_work'] = JSON.stringify({
        handoff:[{url:'https://x/1'}], script:'대본', script_src_idx:null,
        script_from_wiki:null, step:0, work_id:'w-기존'});
      _consumeProduceHandoff();
      await tick(1500);
      console.log(JSON.stringify({wid: WORK_ID, sent: (POSTS[0]||{}).body?.work_id}));
    """)
    assert "w-기존" in out, "WORK_ID를 안 되살렸다 — 제작소를 열 때마다 작업이 복제된다"


def test_first_save_then_reload_reuses_server_work_id(js_consume):
    """★T6 라이브 실증 C-2: 제작소를 열 때마다 작업이 복제됐다(4번 새로고침 → 같은 제목 4건).

    구멍: `_pushWork`가 `d.work_id`를 받아 전역 `WORK_ID`는 갱신하지만 sessionStorage는
    다시 안 썼다. `saveWork()`가 이미 그 앞에서 WORK_ID=null인 채로 sessionStorage를 써버렸으니,
    새로고침 시 `_consumeProduceHandoff`가 `w.work_id || null` = null을 읽어 다음 저장이
    새 작업을 만들었다.

    ★기존 `test_reopening_does_not_duplicate_the_work`처럼 sessionStorage에 work_id를
    미리 심어놓고 시작하지 않는다 — 그러면 이 구멍(POST 응답 → sessionStorage 재기록 누락)을
    한 번도 안 밟는다. 여기선 진짜 순서를 그대로 밟는다:
    1) WORK_ID=null 상태에서 saveWork() (진짜 첫 저장)
    2) tick → 디바운스 발동 → POST → 응답 work_id 수신
    3) 그 시점에 sessionStorage.produce_work.work_id가 서버값인지 확인(수정 전엔 null)
    4) (새 페이지 로드 흉내) 그 sessionStorage로 _consumeProduceHandoff → WORK_ID 복원
    5) 다시 저장 → 두 번째 POST가 같은 work_id를 싣는지(=새 작업이 안 생긴다)
    """
    out = _run(js_consume, """
      // 1. 진짜 첫 저장 — WORK_ID는 아직 null
      STATE.script = '첫 작업';
      saveWork();
      // 2. 디바운스 발동 → POST 나감 → 응답 {work_id:'w-server-1'}
      await tick(1500);
      // 3. 그 시점에 sessionStorage가 서버 work_id로 다시 써졌는가
      const afterFirstSave = JSON.parse(sessionStorage.getItem('produce_work'));
      // 4. (새 페이지 로드 흉내) 전역을 리셋하고 그 sessionStorage로 복원
      _store['produce_work'] = JSON.stringify(afterFirstSave);
      HANDOFF = []; STATE.script = ''; WORK_ID = null;
      _consumeProduceHandoff();
      await tick(1500);
      const restoredWid = WORK_ID;
      // 5. 다시 저장 — 새 작업이 생기면 안 된다
      STATE.script = '이어서 작업';
      saveWork();
      await tick(1500);
      console.log(JSON.stringify({
        afterFirstSaveWid: afterFirstSave.work_id,
        restoredWid: restoredWid,
        lastPostWid: POSTS[POSTS.length-1].body.work_id,
        postCount: POSTS.length,
      }));
    """)
    d = eval(out.replace("null", "None").replace("true", "True").replace("false", "False"))
    assert d["afterFirstSaveWid"] == "w-server-1", (
        f"POST 응답의 work_id가 sessionStorage에 다시 안 써졌다: {d}")
    assert d["restoredWid"] == "w-server-1", f"새로고침 후 WORK_ID가 안 살아났다: {d}"
    assert d["lastPostWid"] == "w-server-1", (
        f"새로고침 후 저장이 새 작업을 만들었다(제작소를 열 때마다 작업 복제): {d}")


def test_script_only_work_is_restored_locally(js_consume):
    """★영상 없이 대본만 있는 작업도 화면에 돌아온다 — 사장님이 잃어버린 바로 그 구간이다.
    저장(saveWork)만 넓히고 복원을 안 넓히면 '저장은 되는데 안 돌아오는' 비대칭이 된다."""
    out = _run(js_consume, """
      _store['produce_work'] = JSON.stringify({
        handoff:[], script:'영상 없이 대본만', script_src_idx:null,
        script_from_wiki:null, step:0, work_id:'w-대본만'});
      _consumeProduceHandoff();
      console.log(JSON.stringify({script: STATE.script, wid: WORK_ID}));
    """)
    assert "영상 없이 대본만" in out, "대본만 있는 작업이 복원되지 않는다"
    assert "w-대본만" in out
