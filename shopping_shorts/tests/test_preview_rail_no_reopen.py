"""꺼둔 좌측 미리보기 레일이 되살아나던 것(2026-08-28 사장님 제보).

제보: "저 미리보기는 없던 건데 완성을 만든 뒤 다른 페이지 갔다가 다시 돌아오면
저 자리에 남아있다. 생기지 말아야 할 버그" + "가만히 두면 점점 더 아래로 내려가면서
확인 버튼이 내려간다"

원인: `_PV_LAB_WAITED[job]`는 **job당 타이머를 하나만** 두려는 장치였는데,
두 번째 호출이 그 플래그만 보고 곧바로 `_renderPreviewVideoFallback`으로 떨어졌다.
'fallback'은 `_RAIL_OFF`를 뚫는 **유일한 값**이라 꺼둔 레일이 되살아났고,
그 레일은 `align-self:stretch`라 자리를 크게 먹어 [다음] 버튼을 아래로 민다.
"""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _run(script):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index("function _pvOpen()")
    j = src.index("// 옛 좌측 레일에 그리는")
    head = """
const _calls = [];
const _lab = {ready: false};
const _els = {};
function _mkEl(id){ return _els[id] || (_els[id] = {id, style:{display:'none'}, innerHTML:'', disabled:false}); }
const document = {getElementById: id => {
  if (id === 'sceneLabFrame') return _lab.exists ? {contentWindow: _lab.win} : null;
  return _mkEl(id);
}};
// ★console을 통째로 덮지 마라 — console.log가 죽어 stdout이 비고, 테스트가
//   "출력 파싱 실패"로만 보여 진짜 원인을 못 짚는다(2026-08-28 실측으로 잡음).
let _timers = [];
function setInterval(fn, ms){ const t={fn, ms, id:_timers.length}; _timers.push(t); return t; }
function clearInterval(t){ if (t) t.dead = true; }
function _tick(n){ for (let k=0;k<n;k++) for (const t of _timers) if (!t.dead) t.fn(); }
// ★호출부 형태 그대로 받는다 — _renderPreviewVideo는 job **객체**를 넘긴다.
//   'j1' 문자열을 기대하면 하네스가 계약을 발명하는 셈이라 초록이 거짓이 된다.
// ★호출부 형태 그대로 — _renderPreviewVideo(job)의 job은 **문자열 job_id**다.
//   객체를 넘기면 _PV_LAB_WAITED[job] 키가 "[object Object]"가 돼 모든 job이 한 칸을
//   공유한다(실측 2026-08-28: 브라우저에서 그 키가 실제로 생겨 있었다).
function _renderPreviewVideoFallback(job, src){
  _calls.push({fallback: true, job});
  _mkEl('mixPreviewRail').style.display=''; _mkEl('mixPreviewPanel').style.display='';
}
const MIX_JOB = 'j1';
const encodeURIComponent = s => String(s);
const Date = {now: () => 1};
"""
    tail = """
// ★반드시 boolean으로 — undefined를 돌려주면 JSON.stringify가 그 키를 통째로 빼서
//   테스트가 KeyError로 죽는다(실패 원인이 안 보인다).
function _railOpen(){ return !!(_els.mixPreviewRail && _els.mixPreviewRail.style.display === ''); }
"""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "h.js"
        p.write_text(head + src[i:j] + tail + script, encoding="utf-8")
        r = subprocess.run([NODE, str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_second_visit_does_not_reopen_rail():
    """★뿌리: 같은 job으로 두 번째 들어와도 **레일이 열리면 안 된다**.

    (다른 페이지 갔다가 돌아오는 상황 — 사장님이 본 그 화면)
    """
    d = _run("""
_lab.exists = true;
_lab.win = {};                       // iframe은 있지만 아직 함수가 없다(로딩 중)
_renderPreviewVideo('j1');     // 첫 진입 → 기다리기 시작
_lab.win.showConfirmVideo = () => {};            // 곧 준비됨
_tick(1);                                        // 타이머가 한 번 돌아 제자리에 넣는다
const afterFirst = _railOpen();
// ★다른 페이지 갔다 돌아오면 iframe이 **다시 뜨는 중**이다 — 함수가 아직 없다.
//   이 상태를 안 만들면 ①에서 곧장 성공해버려 **폴백 분기에 닿지도 않는다**
//   (실측 2026-08-28: 그래서 옛 동작으로 되돌려도 테스트가 초록이었다 —
//    하네스가 계약을 발명하면 0% 동작도 통과한다).
_lab.win = {};
_renderPreviewVideo('j1');     // 다른 페이지 갔다 돌아옴
console.log(JSON.stringify({afterFirst, afterSecond: _railOpen(), calls: _calls}));
""")
    assert d["afterFirst"] is False, "첫 진입에서 이미 레일이 열렸다"
    assert d["afterSecond"] is False, "두 번째 진입에서 꺼둔 레일이 되살아났다"
    assert not any(c.get("fallback") for c in d["calls"]), f"폴백으로 샜다: {d['calls']}"


def test_ready_iframe_goes_straight_in():
    """iframe이 이미 떠 있으면 기다리지 않고 곧장 제자리에 넣는다."""
    d = _run("""
_lab.exists = true;
_lab.win = {showConfirmVideo: () => {}};
_renderPreviewVideo('j1');
console.log(JSON.stringify({rail: _railOpen(), calls: _calls,
                            btn: _els.btnPreview ? _els.btnPreview.disabled : null}));
""")
    assert d["rail"] is False and d["calls"] == [], d


def test_real_failure_still_falls_back():
    """★2초를 다 기다려도 안 뜨면 **폴백은 살아 있어야 한다** — 결과를 아예 못 보면 더 나쁘다."""
    d = _run("""
_lab.exists = true;
_lab.win = {};                        // 끝까지 준비 안 됨
_renderPreviewVideo('j1');
_tick(25);                            // 20회 넘게 돌린다
console.log(JSON.stringify({calls: _calls, rail: _railOpen()}));
""")
    assert any(c.get("fallback") for c in d["calls"]), "진짜 실패인데 폴백도 안 한다"
    assert d["rail"] is True


def test_no_iframe_at_all_falls_back_immediately():
    """iframe이 아예 없는 화면(구형·스텁)에선 종전대로 바로 폴백."""
    d = _run("""
_lab.exists = false;
_renderPreviewVideo('j1');
console.log(JSON.stringify({calls: _calls}));
""")
    assert any(c.get("fallback") for c in d["calls"]), d


def test_restore_closes_rail_first():
    """★안전벨트: 복원(_restoreMixContext)은 **시작하자마자** 폴백 레일을 닫는다.

    레일을 여는 입구는 3곳(_pvFail · _renderPreviewVideoFallback · 렌더 로더)인데
    닫는 보장은 '제자리에 정상으로 들어갔을 때'뿐이었다. 어느 입구로든 한 번 열리면
    다른 페이지 갔다 돌아와도 그대로 남는다 — 사장님이 본 그 화면이다.

    _restoreMixContext는 fetch를 쓰는 async 함수라 node 하네스로 통째로 돌리기 어렵다.
    그래서 **소스에서 그 한 줄이 함수 맨 앞에 있는지**를 지킨다(누가 지우면 잡힌다).
    실제 동작은 브라우저에서 확인했다(레일 열림 → 복원 호출 → 닫힘).
    """
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index("async function _restoreMixContext(){")
    head = src[i:i + 1200]                      # 함수 앞부분
    assert "_pvClose()" in head, "복원이 폴백 레일을 안 닫는다(안전벨트가 사라졌다)"
    # 다른 무거운 작업(fetch)보다 **먼저** 닫아야 한다 — 늦게 닫으면 그 사이 화면에 남는다
    assert head.index("_pvClose()") < head.index("fetch("), \
        "_pvClose가 fetch보다 뒤에 있다 — 복원 중에 레일이 그대로 보인다"


def test_rail_open_entrances_are_known():
    """★레일을 여는 입구가 늘어나면 알아차린다.

    'fallback'은 _RAIL_OFF를 뚫는 유일한 값이다. 입구가 새로 생기면 닫는 경로도
    같이 만들어야 하는데, 조용히 늘면 이 버그가 그대로 재발한다.
    """
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    # ★주석 줄은 빼고 센다 — 주석 속 호출 표기까지 세면 문구만 고쳐도 깨진다.
    code = chr(10).join(ln for ln in src.splitlines() if not ln.lstrip().startswith("//"))
    opens = re.findall(r"_pvShow\('fallback'\)", code)
    closes = re.findall(r"_pvClose\(\)", code)
    assert len(opens) == 3, (
        f"레일을 여는 입구가 {len(opens)}곳이 됐다(알던 건 3곳). "
        "새 입구를 만들었으면 닫는 경로도 함께 넣고 이 숫자를 갱신하라")
    assert len(closes) >= 4, f"닫는 곳이 {len(closes)}곳뿐이다 — 안전벨트가 빠졌는지 확인하라"
