# -*- coding: utf-8 -*-
"""소스분석 자동분석 래치 · 진행표시 가드 (2026-08-20)

사장님 제보: "들어가서 새로고침을 한번눌러야 대본들이 아래 분석이 뜬다"
            "그동안에 멈춰있는것처럼 안보이려면 뭔가 진행되고있다는걸 보여줘야한다"

원인: `_autoloadTried`가 **페이지 수명 boolean**이라 한 번 켜지면 새로고침 전까지
      안 풀렸다. 영상을 담으면 refreshStep0()이 다시 도는데 그때는 이미 잠겨 있어
      자동분석을 통째로 건너뛰었다 → 카드도 "분석 중"도 안 뜸(분석을 시작조차 안 함).

★이 테스트는 **옛 코드에서 실패해야** 가드다(reference_재발버그_가드없인_되살아난다).
  옛 코드엔 _autoloadKey·_footageKey·_srcAutoloadRunning이 아예 없으므로 전부 FAIL한다.
"""
import pathlib
import re

import pytest

HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
SRC = HTML.read_text(encoding="utf-8")


def test_래치가_묶음지문으로_판정된다():
    """boolean 래치만으로 판정하면 새 영상을 담아도 분석이 안 돈다."""
    assert "function _footageKey()" in SRC, "담긴 영상 묶음의 지문 함수가 없다"
    # 래치 분기가 지문 비교를 쓰는지 — boolean만 보면 이번 버그가 그대로 재발한다.
    assert re.search(r"_autoloadKey\s*!==\s*_fkey", SRC), \
        "자동분석 분기가 묶음 지문(_autoloadKey)으로 판정하지 않는다"


def test_지문은_담긴것만_정렬해_만든다():
    """담기 해제한 영상이 섞이거나 순서만 바뀌어 재분석이 돌면 크레딧이 샌다."""
    m = re.search(r"function _footageKey\(\)\{(.*?)\n\}", SRC, re.S)
    assert m, "_footageKey 본문을 못 찾았다"
    body = m.group(1)
    assert "useFootage" in body, "담긴 영상(useFootage)만 세야 한다"
    assert ".sort()" in body, "순서만 바뀐 것을 다른 묶음으로 보면 안 된다"


def test_담자마자_진행표시를_먼저_올린다():
    """네트워크 왕복 전에 표시가 떠야 '멈춘 것처럼' 안 보인다."""
    m = re.search(r"async function refreshStep0\(\)\{(.*?)\n  try\{", SRC, re.S)
    assert m, "refreshStep0 앞부분을 못 찾았다"
    head = m.group(1)
    # aipick fetch·_pushWork보다 먼저 _SRC_BUSY를 세우고 그려야 한다.
    assert "_SRC_BUSY = pending" in head, "선제 진행표시가 없다(빈 화면 구간이 남는다)"
    assert "renderSourceAnalysis()" in head, "선제 표시를 그리지 않는다"


def test_분석을_건너뛰면_진행표시를_내린다():
    """도는 게 없는데 회전표시가 남으면 빈 화면보다 나쁜 거짓말이 된다."""
    assert "let _srcAutoloadRunning" in SRC, "실제 실행 여부 플래그가 없다"
    assert re.search(r"if\(_SRC_BUSY && !_SRC_QUEUED && !_srcAutoloadRunning\)", SRC), \
        "자동분석 분기를 건너뛴 경로에서 진행표시를 내리지 않는다"


def test_자동분석_실패해도_표시가_풀린다():
    """예외가 나면 회전표시가 영영 남는다 — finally로 반드시 내린다."""
    m = re.search(r"_srcAutoloadRunning = true;(.*?)_SRC_BUSY = 0;", SRC, re.S)
    assert m, "자동분석 실행 구간을 못 찾았다"
    assert "finally" in m.group(1), "autoloadAllFootage를 finally로 감싸지 않았다"


def _refresh_step0_body():
    """refreshStep0 본문을 **중괄호 짝을 세어** 잘라낸다.

    ⚠️ 정규식 `(.*?)\\n\\}`로 자르면 안 된다 — 본문 안 템플릿 리터럴·중첩 블록 때문에
       엉뚱한 곳에서 끊기거나 뒤 함수까지 삼킨다(이 테스트를 처음 쓸 때 실제로 그랬다).
    """
    i = SRC.index("async function refreshStep0()")
    depth, started = 0, False
    for j in range(i, len(SRC)):
        if SRC[j] == "{":
            depth += 1
            started = True
        elif SRC[j] == "}":
            depth -= 1
            if started and depth == 0:
                return SRC[i:j]
    raise AssertionError("refreshStep0 본문의 끝을 못 찾았다")


def test_재귀호출_방지선은_그대로다():
    """2026-07-26 무한루프·크레딧 소진 사고의 방지선을 지운 게 아닌지 확인.

    refreshStep0 안에서 자기 자신을 다시 부르면 그 사고가 재발한다.
    선언부와 주석은 호출이 아니므로 **실제 호출 형태**만 센다.
    """
    body = _refresh_step0_body()
    # 주석 줄을 걷어낸 뒤 호출부만 본다(주석 속 "refreshStep0()를 부르지 마라"는 무해).
    code = "\n".join(
        ln for ln in body.splitlines() if not ln.lstrip().startswith("//")
    )
    calls = re.findall(r"(?<!function )\brefreshStep0\s*\(", code)
    assert not calls, f"refreshStep0이 자기 자신을 다시 부른다(무한루프 위험): {calls}"


# ── 2026-08-20 2차: 레퍼런스 유입 경로 — 저장 레이스로 자동분석이 통째로 안 돌던 버그 ──
#
# 사장님 재제보(시크릿 모드, 9단계 배포 확인된 화면): 랭킹/즐겨찾기에서 영상을 담아
# 제작소로 오면 분석 카드도 진행표시도 없고, **새로고침을 눌러야** 분석이 뜬다.
#
# 실측한 진범(레이스): _consumeProduceHandoff가 유입 저장(_pushWork)을 디바운스
# (_workTimer)를 **우회**해 직접 밀어넣는데, 곧이어 도는 refreshStep0()은 _workTimer만
# 보고 기다려서 그 저장을 못 붙든다 → aipick이 work_id 없이 나감 → 서버
# (_load_work_sources)가 '계정 전체 픽'으로 폴백 → pick_id가 채워져 옴 →
# 자동분석 분기(pick_id==null)를 통째로 건너뜀 → 분석 0회. 새로고침하면 URL이
# ?work=<id>로 바뀌어 있어(저장 성공 후 replaceState) aipick에 work_id가 실리고
# 그제야 분석이 돈다 — "새로고침해야 뜬다"의 정체.
#
# 두 번째 구멍(같은 증상): pick이 이미 있는 작업에 영상을 더 담으면 pick_id!=null이라
# 역시 분기를 건너뛰어 **새 영상은 아무도 분석하지 않는다**.
#
# ★이 가드들은 옛 코드(수정 전)에서 반드시 FAIL한다 — 실제로 되돌려 확인했다.

from shopping_shorts.tests.js_harness import run_js, requires_node


def test_유입저장_약속을_남긴다():
    """_consumeProduceHandoff가 직행 저장의 약속(window._ARRIVAL_PUSH)을 안 남기면
    refreshStep0이 기다릴 방법이 없어 레이스가 그대로 재발한다."""
    assert "window._ARRIVAL_PUSH" in SRC, "유입 저장 약속(_ARRIVAL_PUSH)이 없다"


def test_aipick전에_유입저장을_기다린다():
    """refreshStep0 본문에서 _ARRIVAL_PUSH await가 aipick fetch보다 앞이어야 한다."""
    body = _refresh_step0_body()
    i_wait = body.find("window._ARRIVAL_PUSH")
    i_pick = body.find("/api/produce/aipick")
    assert i_wait != -1, "refreshStep0이 유입 저장을 기다리지 않는다(레이스 재발)"
    assert i_pick != -1, "aipick 호출을 못 찾았다(구조 변경 — 가드를 갱신하라)"
    assert i_wait < i_pick, "유입 저장 대기가 aipick **뒤**에 있다 — 순서가 틀리면 무의미"


def test_pending판정은_한곳에서만():
    """선제 진행표시와 자동분석 재개 판정이 각자 세면 반드시 어긋난다(0순위-B)."""
    assert "function _srcPendingCount()" in SRC, "_srcPendingCount가 없다"
    calls = re.findall(r"(?<!function )_srcPendingCount\(\)", SRC)
    assert len(calls) >= 2, f"호출부가 {len(calls)}곳 — 선제표시·자동분석 둘 다 여기로 세야 한다"


def test_pick있어도_미분석영상_남으면_분기가_열린다():
    """pick_id!=null이어도 담긴 영상 중 미분석이 있으면 자동분석이 돌아야 한다(정적)."""
    body = _refresh_step0_body()
    assert re.search(r"d\.pick_id==null \|\| _srcPendingCount\(\) > 0", body), \
        "자동분석 분기가 pick_id==null만 본다 — 진행 중 작업에 더 담은 영상은 영영 미분석"


# ── 동적 가드: 실제 잘라낸 코드를 node로 돌려 행동을 판정한다 ─────────────────

def _slice_fn(header):
    """컬럼0의 다음 선언(function/let/const)까지 자른다 — 본문 브레이스 파싱 함정 회피.

    없는 함수(옛 코드의 _srcPendingCount)는 빈 문자열로 — 그러면 FAIL이 '슬라이스
    오류'가 아니라 **행동 단언**에서 난다(원인이 보이게).
    """
    i = SRC.find(header)
    if i == -1:
        return ""
    m = re.search(r"\n(?:async function |function |let |const )", SRC[i + 1:])
    chunk = SRC[i:i + 1 + m.start()] if m else SRC[i:]
    lines = chunk.rstrip().splitlines()
    while lines and lines[-1].startswith("//"):
        lines.pop()
    return "\n".join(lines)


_HARNESS_FUNCS = [
    "function _consumeProduceHandoff()",
    "function _mergeHandoffItems(items)",
    "function _pendingHandoffItems()",
    "function _clearHandoffStorage()",
    "function _srcPendingCount()",
    "async function refreshStep0()",
    "async function renderSourceAnalysis()",
    "function _srcCard(it, i)",
    "function _footageKey()",
    "async function autoloadAllFootage()",
    "function renderQueuedState(n)",
    "function renderAutoloadingState(total)",
]

_HARNESS_PRE = r"""
'use strict';
const CALLS = { autoload: 0, aipickUrls: [] };
var window = globalThis;
const _store = {};
var sessionStorage = {
  getItem: k => (k in _store ? _store[k] : null),
  setItem: (k, v) => { _store[k] = String(v); },
  removeItem: k => { delete _store[k]; },
};
const _els = {};
var document = { getElementById: id => (_els[id] = _els[id] || { id, innerHTML: '', style: {} }) };
const sleep = ms => new Promise(r => setTimeout(r, ms));
// aipick: work_id가 실리면 '이 작업의 새 영상들'(pick 없음) — 단 시나리오 B에서는
// 옛 재료의 pick이 살아 있어 work_id가 실려도 pick_id가 차 있다.
var AIPICK_WITH_WORK = { ok: true, pick_id: null, candidates: [] };
var fetch = async (url) => {
  if (url.startsWith('/api/produce/aipick')) {
    CALLS.aipickUrls.push(url);
    await sleep(10);
    return { json: async () => (url.includes('work_id=') ? AIPICK_WITH_WORK
                                                         : { ok: true, pick_id: 'OLD', candidates: [] }) };
  }
  if (url.startsWith('/api/produce/source_brief')) {
    await sleep(5);
    const code = (url.match(/shortcode=([^&]+)/) || [])[1] || '';
    return { json: async () => (code === 'OLD1' ? { ok: true, brief: {}, segments: [] } : { ok: false }) };
  }
  if (url.startsWith('/api/produce/autoload')) {
    CALLS.autoload++;
    await sleep(10);
    return { json: async () => ({ ok: true, added: 2, results: [
      { status: 'added', shortcode: 'AAA' }, { status: 'added', shortcode: 'BBB' } ] }) };
  }
  await sleep(5);
  return { json: async () => ({ ok: true }) };
};
var HANDOFF = [];
var WORK_ID = null;
var _workTimer = null;
var STATE = { script: '' };
var cur = 0;
function esc(s){ return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
const _SRC_BRIEF = {};
const _SRC_INFLIGHT = new Set();
var _SRC_POLL = null;
var _SRC_BUSY = 0;
var _SRC_QUEUED = 0;
const _SRC_CLOSED = new Set();
var _autoloadTried = false;
var _autoloadKey = '';
var _srcAutoloadRunning = false;
function renderPool(){}
function syncFootageToMixUrls(){}
function refreshFinalPeek(){}
function renderAiPick(){}
function renderEmptyState(){}
function renderNoScriptState(){}
function setScriptMode(){}
function saveWork(){}
// 실제 _pushWork처럼 서버 왕복(80ms) **뒤에야** WORK_ID가 채워진다 — 레이스의 재료.
async function _pushWork(){ await sleep(80); WORK_ID = 'W1'; }
"""

_HARNESS_POST = r"""
(async () => {
  const out = {};
  // A) 랭킹 유입(시크릿 = 빈 저장소): 부트 순서 그대로 receiver → refreshStep0
  _store['produce_handoff'] = JSON.stringify([
    { url: 'https://www.instagram.com/reel/AAA/', shortcode: 'AAA', name: '영상A' },
    { url: 'https://www.instagram.com/reel/BBB/', shortcode: 'BBB', name: '영상B' },
  ]);
  _consumeProduceHandoff();
  await refreshStep0();
  out.A = {
    aipickAllHadWorkId: CALLS.aipickUrls.length > 0 && CALLS.aipickUrls.every(u => u.includes('work_id=')),
    autoloadCalls: CALLS.autoload,
    progressShown: /분석/.test((_els['srcAnalysis'] || {}).innerHTML || ''),
  };
  // C) 같은 묶음 재호출 — 자동분석이 더 돌면 크레딧이 샌다(2026-07-26 방지선)
  const c0 = CALLS.autoload;
  await refreshStep0();
  await refreshStep0();
  out.C = { extraAutoload: CALLS.autoload - c0, busyAfter: _SRC_BUSY };
  // B) pick이 있는 작업에 새 영상 추가: pick_id!=null인데 미분석(NEW1)이 남아 있다
  AIPICK_WITH_WORK = { ok: true, pick_id: 'KEEP', candidates: [] };
  HANDOFF = [
    { url: 'https://www.instagram.com/reel/OLD1/', shortcode: 'OLD1', name: '옛영상', useFootage: true },
    { url: 'https://www.instagram.com/reel/NEW1/', shortcode: 'NEW1', name: '새영상', useFootage: true },
  ];
  const b0 = CALLS.autoload;
  await refreshStep0();
  out.B = { autoloadRan: CALLS.autoload - b0 };
  const b1 = CALLS.autoload;
  await refreshStep0();
  out.B.extraAfterLatch = CALLS.autoload - b1;
  console.log(JSON.stringify(out));
  process.exit(0);
})();
"""


@requires_node
def test_실행가드_유입하면_분석이_실제로_돈다():
    """실제 잘라낸 코드로 세 시나리오를 **한 node 프로세스**에서 돌린다(핸들 고갈 회피).

    옛 코드 실측(수정 전): A.aipickAllHadWorkId=false · A.autoloadCalls=0 → FAIL.
    """
    import json as _json
    sliced = "\n".join(_slice_fn(h) for h in _HARNESS_FUNCS)
    out = _json.loads(run_js(_HARNESS_PRE + sliced + _HARNESS_POST, timeout=60))
    # A: 유입 즉시 — 저장을 기다려 aipick에 work_id가 실리고, 자동분석이 실제로 시작된다
    assert out["A"]["aipickAllHadWorkId"], f"aipick이 work_id 없이 나갔다(레이스 재발): {out['A']}"
    assert out["A"]["autoloadCalls"] >= 1, f"유입 경로에서 자동분석이 안 돌았다: {out['A']}"
    assert out["A"]["progressShown"], "진행표시가 안 떴다(멈춘 것처럼 보인다)"
    # C: 같은 묶음이면 다시 안 돈다(무한루프·크레딧 소진 방지선 불변)
    assert out["C"]["extraAutoload"] == 0, f"같은 묶음인데 자동분석이 또 돌았다: {out['C']}"
    assert out["C"]["busyAfter"] == 0, "도는 게 없는데 진행표시가 남아 있다"
    # B: pick이 있어도 미분석 영상이 남으면 돌고, 같은 묶음 재호출엔 안 돈다
    assert out["B"]["autoloadRan"] >= 1, f"pick 있는 작업에 더 담은 영상이 영영 미분석: {out['B']}"
    assert out["B"]["extraAfterLatch"] == 0, f"래치가 안 잠겼다(크레딧 소진 위험): {out['B']}"
