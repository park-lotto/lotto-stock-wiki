"""1단계 미리보기 게이트 — 미리보기 전엔 '다음'이 안 열린다(스펙 §5·§7).

사장님 지적: "미리보기를 안 해보고 넘길 수는 있는데 상식적으로 잘 되었는지 뭘 보고
그걸 다음 단계로 넘기겠나. 돈 내고 만드는 사람들인데."
다음 단계(자막제거)가 VMake 유료 API라, 못 본 채 넘어가면 그 돈이 날아간다.

produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다
(test_produce_pm_gen_race.py·test_produce_mix_regen.py와 같은 방식 — 재구현이 아니다).

★2026-07-17 최종리뷰 후 확장: 이 파일의 옛 판은 fetch를 reject로, setInterval/clearInterval을
no-op으로 스텁해 **startPreview·pollPreview가 한 줄도 실행되지 않았다**. 그래서 뮤테이션 3종을
다 통과하고도 C-2(고아 인터벌로 미리보기를 볼 수 없다)가 살아 있었다. 이제 **가짜 시계**로
비동기 배선을 실제로 구동한다.
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# jump()·go() = 게이트를 통과시키는 두 경로. jump는 상단 스텝칩(renderSteps)이 모든 단계에
# onclick으로 달아둔다 — 슬라이스에 반드시 포함해야 한다(옛 판은 여기가 빠져 C-1을 못 봤다).
_JUMP_START = "function jump(i){"
_JUMP_END = "// ── 1단계 대본: 3모드"
# loadMixReview(재매칭 시 폴러 정리)부터 미리보기 전체까지.
_PREVIEW_START = "async function loadMixReview(){"
_PREVIEW_END = "// ── 3단계 자막제거"
# ★startProduceMix = 재매칭의 **시작**. MIX_JOB을 바꾸는 유일한 곳(초기화 제외)이다.
# 재리뷰 C-3: 이게 슬라이스에 없어서 34건이 다 green인데도 "재매칭 중 게이트가 열려 있다"가 살아 있었다.
_MIX_START = "async function startProduceMix(){"
_MIX_END = "async function pollMix(){"

_HARNESS = r"""
'use strict';
function el(){
  const o = { style:{}, textContent:'', disabled:false, title:'',
              classList:{add(){},remove(){},toggle(){}} };
  let _html = '';
  o._videoWrites = 0;
  Object.defineProperty(o, 'innerHTML', {
    get(){ return _html; },
    // <video>가 몇 번 "다시 그려졌나"를 센다. 2번 이상이면 노드가 파괴·재생성돼 재생이 0초로
    // 리셋되고 mp4를 매번 재다운로드한다 = 사장님이 미리보기를 못 본다.
    set(v){ _html = String(v); if (_html.indexOf('<video') !== -1) o._videoWrites++; },
  });
  return o;
}
const _els = { mixPreview: el(), btnNext: el(), mixState: el(), mixReview: el(), btnPreview: el(),
               mixStatus: el() };
const document = { getElementById(id){ return _els[id] || null; }, querySelector(){ return null; },
                   // startProduceMix가 소스 URL을 읽는다 — 1개는 있어야 진행된다.
                   querySelectorAll(sel){ return sel === '.mixUrl' ? [{value:'https://x/1'}] : []; } };
function esc(s){ return s; }
// ⚠️ PREVIEW_STATUS·PREVIEW_POLL·PREVIEW_GEN은 여기서 선언하지 마라 — 아래 실제 소스가 let으로
// 선언하므로 중복 선언이 되어 SyntaxError로 죽는다. 슬라이스 밖 심볼만 여기서 준다.
var cur = 0;
var MIX_JOB = 'J1';
var MIX_POLL = null;
var STATE = { script: '확정된 대본' };     // startProduceMix가 없으면 alert하고 빠진다
var STEPS = ["제작소","자막제거","TTS","꾸미기","썸네일","SEO","최종검수"];
function renderSteps(){}
function showPanel(){ refreshNextBtn(); }
function alert(){}
function pollMix(){}                        // 슬라이스 밖 — 이 테스트는 미리보기 게이트만 본다

// ── 가짜 시계: setInterval을 진짜로 등록하고 수동으로 tick한다 ──
let _timerSeq = 0;
const _timers = new Map();
function setInterval(fn, ms){ const id = ++_timerSeq; _timers.set(id, fn); return id; }
function clearInterval(id){ if (id !== null && id !== undefined) _timers.delete(id); }
async function _drain(){ for (let i = 0; i < 8; i++) await Promise.resolve(); }
async function _tick(){ for (const fn of Array.from(_timers.values())) await fn(); await _drain(); }

// ── 가짜 네트워크 ──
let _postResponse = { ok:true, status:'rendering' };
let _postMixStart = { ok:true, job_id:'J2' };   // startProduceMix(재매칭)가 받는 새 job
let _statusResponse = { ok:true, preview_status:'rendering' };
let _resultResponse = { ok:true, beats:[] };
let _holdStatus = false;      // true면 상태 응답을 붙잡아 둔다(늦게 도착하는 경합 재현)
let _releaseStatus = null;
function fetch(url, opts){
  const u = String(url);
  if (u.indexOf('/api/produce/mix/preview') !== -1 && opts && opts.method === 'POST')
    return Promise.resolve({ json: async () => _postResponse });
  if (u.indexOf('/api/produce/mix/start') !== -1)
    return Promise.resolve({ json: async () => _postMixStart });
  if (u.indexOf('/api/mix/status/') !== -1) {
    if (_holdStatus) return new Promise(res => { _releaseStatus = r => res({ json: async () => r }); });
    return Promise.resolve({ json: async () => _statusResponse });
  }
  if (u.indexOf('/api/mix/result/') !== -1)
    return Promise.resolve({ json: async () => _resultResponse });
  return Promise.reject(new Error('unmocked fetch: ' + u));
}
// ---- 여기부터 produce.html 실제 소스 ----
"""

_SCENARIO_GATE = r"""
(() => {
  const fails = [];
  PREVIEW_STATUS = null;
  if (canGoNext() !== false) fails.push('미리보기 전인데 다음이 열려 있다 — 유료 자막제거로 그냥 넘어간다');
  PREVIEW_STATUS = 'rendering';
  if (canGoNext() !== false) fails.push('렌더 중인데 다음이 열려 있다');
  PREVIEW_STATUS = 'ready';
  if (canGoNext() !== true) fails.push('미리보기가 나왔는데도 다음이 잠겨 있다 — 진행 불가');
  PREVIEW_STATUS = 'failed';
  if (canGoNext() !== true) fails.push('렌더 실패인데 탈출구가 없다 — ffmpeg 문제 하나로 갇힌다(스펙 §7.1)');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})();
"""

_SCENARIO_BTN = r"""
(() => {
  const fails = [];
  const b = document.getElementById('btnNext');
  PREVIEW_STATUS = null;  cur = 0;  refreshNextBtn();
  if (b.disabled !== true) fails.push('1단계·미리보기 전인데 btnNext가 안 잠겼다');
  if (!String(b.title || '').trim()) fails.push('왜 잠겼는지 안내(title)가 없다');
  PREVIEW_STATUS = 'ready'; refreshNextBtn();
  if (b.disabled !== false) fails.push('미리보기 후에도 btnNext가 잠겨 있다');
  // 다른 단계에선 이 게이트가 끼어들면 안 된다
  PREVIEW_STATUS = null; cur = 2; refreshNextBtn();
  if (b.disabled !== false) fails.push('3단계인데 1단계 게이트가 다음을 잠갔다');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})();
"""

# ★C-1: 상단 스텝칩이 모든 단계에 onclick="jump(i)"를 달고 있다. jump에 가드가 없으면
# "자막제거" 칩 한 번 클릭으로 게이트가 통째로 우회된다 — 게다가 그 뒤 refreshNextBtn()은
# cur=1이라 gated=false로 계산해 버튼까지 도로 열어준다(우회 흔적도 안 남는다).
_SCENARIO_JUMP = r"""
(() => {
  const fails = [];
  MIX_JOB = 'J1';

  PREVIEW_STATUS = null; cur = 0;
  jump(1);
  if (cur !== 0) fails.push('스텝칩 클릭(jump)이 게이트를 우회했다 — cur=' + cur + ' → 미리보기 못 본 채 유료 VMake가 돈다');
  jump(6);
  if (cur !== 0) fails.push('마지막 단계로 점프해 게이트를 우회했다 — cur=' + cur);

  PREVIEW_STATUS = 'ready'; cur = 0;
  jump(1);
  if (cur !== 1) fails.push('미리보기를 봤는데도 스텝칩 점프가 막혔다 — 진행 불가');

  // 뒤로 가는 건 막지 않는다(앞으로만 막는다)
  PREVIEW_STATUS = null; cur = 3;
  jump(0);
  if (cur !== 0) fails.push('뒤로 가기가 막혔다 — 1단계로 못 돌아간다');

  // 매칭 전(MIX_JOB 없음)이면 게이트가 걸리면 안 된다 — go()와 같은 조건
  MIX_JOB = null; PREVIEW_STATUS = null; cur = 0;
  jump(1);
  if (cur !== 1) fails.push('매칭도 안 했는데 게이트가 걸렸다');

  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})();
"""

# ★C-2 본체: 더블클릭 → 고아 인터벌 → <video> 재생성 반복.
# 서버는 중복예약을 막지만(app.py) **클라이언트 타이머는 별개다**.
_SCENARIO_DOUBLE_CLICK = r"""
(async () => {
  const fails = [];
  MIX_JOB = 'J1'; cur = 0;
  _statusResponse = { ok:true, preview_status:'rendering' };

  const p1 = startPreview();
  const p2 = startPreview();          // 더블클릭(렌더는 20초+ 걸린다 — 충분히 일어난다)
  await p1; await p2; await _drain();

  if (_timers.size !== 1)
    fails.push('더블클릭 후 살아있는 폴러가 ' + _timers.size + '개 — 고아 인터벌이 생겼다(PREVIEW_POLL을 덮어써 옛 핸들을 잃었다)');

  const box = document.getElementById('mixPreview');
  _statusResponse = { ok:true, preview_status:'ready' };   // 렌더 완료
  await _tick(); await _tick(); await _tick();             // 시계를 여러 번 돌린다

  if (box.innerHTML.indexOf('<video') === -1) fails.push('ready인데 <video>가 안 그려졌다');
  if (box._videoWrites !== 1)
    fails.push('<video>가 ' + box._videoWrites + '번 그려졌다 — 매 tick마다 노드가 파괴·재생성돼 재생이 0초로 리셋되고 5MB mp4를 2.5초마다 재다운로드한다(사장님이 못 본다 = 기능의 존재이유가 무너진다)');
  if (_timers.size !== 0)
    fails.push('ready 뒤에도 폴러가 ' + _timers.size + '개 살아있다 — 영원히 폴링한다');
  if (PREVIEW_STATUS !== 'ready') fails.push('PREVIEW_STATUS가 ready가 아니다 — ' + PREVIEW_STATUS);

  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# ★C-2 같은 계열: 재매칭(loadMixReview)은 정상 흐름이고 새 job_id가 잡힌다.
# 옛 폴러를 안 죽이면 그놈이 새 MIX_JOB을 폴링해 **옛 렌더의 결과로 게이트를 연다**.
_SCENARIO_REMATCH_KILLS_STALE_POLLER = r"""
(async () => {
  const fails = [];
  MIX_JOB = 'J1'; cur = 0;
  _statusResponse = { ok:true, preview_status:'rendering' };
  await startPreview(); await _drain();
  if (_timers.size !== 1) { console.error('FAIL(전제): 폴러가 안 떴다'); process.exit(1); }

  // 옛 폴러가 tick해서 상태를 물어보는 중(응답 아직 도착 전)
  _holdStatus = true;
  const pending = Array.from(_timers.values())[0]();
  await _drain();

  // 그 사이 사장님이 대본을 고쳐 재매칭 → 새 job
  MIX_JOB = 'J2';
  _holdStatus = false;
  await loadMixReview(); await _drain();

  if (_timers.size !== 0)
    fails.push('재매칭 후에도 옛 폴러가 ' + _timers.size + '개 살아있다 — 새 MIX_JOB을 폴링한다');
  if (PREVIEW_STATUS !== null)
    fails.push('재매칭했는데 PREVIEW_STATUS가 초기화 안 됐다 — ' + PREVIEW_STATUS);

  // 이제 옛 요청의 응답이 도착한다 — 주인이 바뀌었으니 아무것도 건드리면 안 된다
  const box = document.getElementById('mixPreview');
  const writesBefore = box._videoWrites;
  _releaseStatus({ ok:true, preview_status:'ready' });
  await pending; await _drain();

  if (PREVIEW_STATUS === 'ready')
    fails.push('옛 job(J1)의 늦은 응답이 새 job(J2)의 게이트를 열었다 — 사장님은 J2 미리보기를 본 적이 없다');
  if (box._videoWrites !== writesBefore)
    fails.push('옛 job의 늦은 응답이 새 화면에 <video>를 그렸다 — 옛 영상을 보고 OK하게 된다');

  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# 렌더 중 버튼 잠금 — 재클릭 자체를 막는 1차 방어(위 세대토큰은 2차).
_SCENARIO_BTN_DISABLED_WHILE_RENDERING = r"""
(async () => {
  const fails = [];
  MIX_JOB = 'J1'; cur = 0;
  _statusResponse = { ok:true, preview_status:'rendering' };
  const b = document.getElementById('btnPreview');
  b.disabled = false;
  await startPreview(); await _drain();
  if (b.disabled !== true) fails.push('렌더 중(20초+)인데 미리보기 버튼이 안 잠겼다 — 재클릭이 그대로 들어온다');

  _statusResponse = { ok:true, preview_status:'ready' };
  await _tick();
  if (b.disabled !== false) fails.push('렌더가 끝났는데 버튼이 잠긴 채다 — 다시 만들 수 없다');

  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""

# 렌더 실패도 탈출구가 열려야 한다(스펙 §7.1) — 폴러도 같이 죽는다.
_SCENARIO_FAILED_OPENS_ESCAPE = r"""
(async () => {
  const fails = [];
  MIX_JOB = 'J1'; cur = 0;
  _statusResponse = { ok:true, preview_status:'rendering' };
  await startPreview(); await _drain();
  _statusResponse = { ok:true, preview_status:'failed', preview_error:'ffmpeg 죽음' };
  await _tick(); await _tick();
  if (PREVIEW_STATUS !== 'failed') fails.push('failed가 반영 안 됨 — ' + PREVIEW_STATUS);
  if (canGoNext() !== true) fails.push('렌더 실패인데 탈출구가 안 열렸다(스펙 §7.1)');
  if (_timers.size !== 0) fails.push('failed 뒤에도 폴러가 살아있다 — ' + _timers.size + '개');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""


# ★C-3(재리뷰): 재매칭 = 새 job. 옛 job의 'ready'를 물고 있으면 canGoNext()가 그걸 보고
# **한 번도 본 적 없는 새 영상으로 다음을 열어준다**. 매칭은 수십 초~수 분 걸리므로 창이 넓다.
# 화면이 "대본을 살짝 바꾸거나 소스 영상을 추가하세요"라고 권하는 **정상 흐름**이다.
# 앞선 수정은 재매칭의 '끝'(loadMixReview)만 봉인하고 '시작'(startProduceMix)을 놓쳤다.
_SCENARIO_REMATCH_RELOCKS_GATE = r"""
(async () => {
  const fails = [];
  const btn = document.getElementById('btnNext');

  // 1) J1을 미리보기까지 봤다 — 게이트 열림
  MIX_JOB = 'J1'; cur = 0;
  _statusResponse = { ok:true, preview_status:'ready' };
  await startPreview(); await _drain(); await _tick();
  if (PREVIEW_STATUS !== 'ready') { console.error('FAIL(전제): J1 미리보기가 ready가 아니다 — ' + PREVIEW_STATUS); process.exit(1); }
  if (canGoNext() !== true) { console.error('FAIL(전제): J1을 봤는데 게이트가 잠겼다'); process.exit(1); }

  // 2) 대본을 고쳐 재매칭 — 새 job J2가 잡힌다(매칭은 수십 초~수 분 걸린다)
  _postMixStart = { ok:true, job_id:'J2' };
  await startProduceMix(); await _drain();

  if (MIX_JOB !== 'J2') { console.error('FAIL(전제): 재매칭이 안 됐다 — MIX_JOB=' + MIX_JOB); process.exit(1); }

  // 3) ★J2는 한 번도 미리보기를 만든 적이 없다 — 게이트가 **다시 잠겨야** 한다
  if (PREVIEW_STATUS !== null)
    fails.push('재매칭했는데 옛 job의 미리보기 상태가 남았다(' + PREVIEW_STATUS + ') — 새 영상을 못 본 채 게이트가 열린다');
  if (canGoNext() !== false)
    fails.push('재매칭 중인데 canGoNext()가 true — [다음]을 누르면 J2를 한 번도 못 본 채 유료 자막제거로 넘어간다');
  if (btn.disabled !== true)
    fails.push('재매칭 중인데 btnNext가 열려 있다');

  // 4) 옛 **미리보기** 폴러가 죽어야 한다(안 죽이면 옛 job을 2.5초마다 계속 두드린다).
  //    ⚠️ _timers 전체를 세면 안 된다 — startProduceMix가 MIX_POLL(매칭 폴러)을 **정당하게** 만든다.
  if (PREVIEW_POLL !== null)
    fails.push('재매칭 후에도 옛 미리보기 폴러가 살아있다(PREVIEW_POLL=' + PREVIEW_POLL + ')');

  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""


def _src():
    text = PRODUCE_HTML.read_text(encoding="utf-8")

    def _span(start, end):
        s, e = text.find(start), text.find(end)
        assert s != -1, f"START 못 찾음(produce.html이 바뀌었나): {start!r}"
        assert e != -1 and e > s, f"END 못 찾음: {end!r}"
        return text[s:e]

    return (_span(_JUMP_START, _JUMP_END) + "\n"
            + _span(_MIX_START, _MIX_END) + "\n"
            + _span(_PREVIEW_START, _PREVIEW_END))


def _run(scenario, tmp_path):
    f = tmp_path / "probe_preview_gate.js"
    f.write_text(_HARNESS + _src() + scenario, encoding="utf-8")
    # encoding="utf-8", errors="replace": 기본(cp949) 캡처는 한글 console.error를 못 읽어 죽는다.
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=30)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
# id를 명시한다 — 안 그러면 시나리오 소스 전체가 테스트 이름이 돼 실패 보고를 못 읽는다.
@pytest.mark.parametrize("name,scenario", [
    pytest.param("canGoNext_상태표", _SCENARIO_GATE, id="canGoNext_상태표"),
    pytest.param("C3_재매칭이_게이트를_다시_잠그나", _SCENARIO_REMATCH_RELOCKS_GATE, id="C3_rematch_relocks_gate"),
    pytest.param("btnNext_disabled", _SCENARIO_BTN, id="btnNext_disabled"),
    pytest.param("C1_jump가_게이트를_지키나", _SCENARIO_JUMP, id="C1_jump_guard"),
    pytest.param("C2_더블클릭_고아인터벌", _SCENARIO_DOUBLE_CLICK, id="C2_double_click_orphan_poller"),
    pytest.param("C2_재매칭이_옛폴러를_죽이나", _SCENARIO_REMATCH_KILLS_STALE_POLLER, id="C2_rematch_kills_stale_poller"),
    pytest.param("C2_렌더중_버튼잠금", _SCENARIO_BTN_DISABLED_WHILE_RENDERING, id="C2_btn_disabled_while_rendering"),
    pytest.param("failed_탈출구", _SCENARIO_FAILED_OPENS_ESCAPE, id="failed_opens_escape"),
])
def test_preview_gate_scenarios(name, scenario, tmp_path):
    r = _run(scenario, tmp_path)
    assert r.returncode == 0, f"[{name}] stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


def test_preview_video_is_muted_by_default():
    """★사장님 지시: 음소거가 기본값. 열면 조용하고, 원하면 켠다(스펙 §4.2)."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    i = html.find("mix/preview/")
    assert i != -1, "미리보기 <video>가 없다"
    tag = html[max(0, i - 300): i + 100]
    assert "muted" in tag, f"미리보기 video에 muted가 없다 — 열자마자 소리가 난다: {tag[-160:]!r}"
    assert "controls" in tag, "controls가 없다 — 음소거 해제·탐색을 못 한다"


def test_preview_url_has_cache_buster():
    """대본을 고쳐 재매칭하면 같은 URL에 다른 영상이 온다 — 캐시버스터가 없으면 옛 걸 본다."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    i = html.find("mix/preview/")
    tag = html[i: i + 200]
    assert "?t=" in tag, f"미리보기 URL에 캐시버스터가 없다 — 브라우저가 옛 영상을 재사용한다: {tag[:120]!r}"


def test_go_has_gate_guard():
    """disabled만으론 부족 — go(1)이 다른 경로로 불릴 수 있다(방어 두 겹)."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    i = html.find("function go(d){")
    assert i != -1, "go() 못 찾음"
    body = html[i: i + 320]
    assert "canGoNext()" in body, f"go()에 게이트 가드가 없다: {body[:180]!r}"


def test_stale_review_hint_is_gone():
    """옛 안내문이 남아 있으면 화면이 거짓말을 한다(스펙 §7)."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "마지막에 렌더합니다" not in html, \
        "'마지막에 렌더합니다' 안내가 남아 있다 — 이제 1단계에서 미리보기를 렌더한다"
