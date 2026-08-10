"""작업 전환 시 대본 유실 방지 — node 슬라이스 그라운딩(2026-08-07).

실사고(사장님 제보): 사이드바 '내 작업'에서 다른 작업을 클릭하면 "대본 뽑은 게 다시 다 리셋"됐다.
전환은 SPA가 아니라 **location.href = 전체 페이지 리로드**(sidebar.js)인데, 서버 저장은 1초
디바운스(saveWork)라 그 1초 안에 클릭하면 저장이 영영 안 나갔다. 겹친 문제 셋을 여기서 못 박는다:

  ① 이탈 플러시   — pagehide에 대기 중 저장을 sendBeacon으로 확정(fetch는 언로드 중 취소된다)
  ② step 강등보호 — 게이트가 깎은 cur=0을 서버에 되쓰면 진행단계가 영구 파괴된다(왕복할수록 1단계 고착)
  ③ job_id 즉시확정 — 매칭 직후 job_id는 디바운스를 태우면 안 된다. 안 붙으면 work.job_id가
                     NULL로 남아 _restoreMixContext가 안 돌고 **대본 후보·미리보기가 통째로 안 뜬다**

test_work_save_job_guard_js.py와 같은 결(실제 produce.html을 잘라 node로 돌린다) — 주석이
아니라 실행으로 계약을 고정한다.
"""
import json
import pathlib
import shutil
import subprocess
import tempfile

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"

# 저장 슬라이스 앵커. 바뀌면 여기도 같이 옮길 것(테스트가 조용히 빈 채로 통과하지 않도록 assert한다).
_START = "let _workTimer = null;"
_END = "    window.addEventListener('beforeunload', flushWork);\n  }\n}catch(e){}"

# 슬라이스가 기대하는 브라우저 환경 스텁. sendBeacon/fetch로 나간 것을 각각 모은다.
_HARNESS = """
let POSTS = [], BEACONS = [];
let HANDOFF = [{url:'u1'}];
let cur = 0;
let MIX_JOB = null;
let WORK_ID = 'W1';
const STATE = { script: '대본입니다' };
const document = { getElementById: () => null };
const sessionStorage = { setItem(){}, getItem(){ return null; }, removeItem(){} };
const location = { search: '' };
const history = { replaceState(){} };
class URLSearchParams { constructor(){} get(){ return null; } }
class Blob { constructor(parts){ this._text = parts.join(''); } }
const navigator = { sendBeacon(url, blob){ BEACONS.push(JSON.parse(blob._text)); return true; } };
async function fetch(url, opt){
  POSTS.push(JSON.parse(opt.body));
  return { json: async () => ({ok: true, work_id: 'W1'}) };
}
const window = { addEventListener(ev, fn){ window['_'+ev] = fn; } };
"""


def _slice():
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    a, b = html.find(_START), html.find(_END)
    assert a >= 0, "저장 슬라이스 START 앵커를 못 찾음 — produce.html이 바뀌었으면 테스트도 옮길 것"
    assert b >= 0, "저장 슬라이스 END 앵커를 못 찾음 — pagehide 등록부가 바뀌었나"
    return html[a:b + len(_END)]


def _run(body):
    node = shutil.which("node")
    if not node:
        pytest.skip("node 없음")
    # ★_serverStep은 슬라이스가 `let`으로 선언한다 = 바깥 대입이 그 바인딩에 안 닿는다
    #   (MIX_JOB/WORK_ID에서 이미 두 번 밟은 렉시컬 바인딩 함정). 설정자를 슬라이스 스코프에 심는다.
    script = (_HARNESS + _slice()
              + "\n; var _setServerStep = (v) => { _serverStep = v; };\n"
              + "(async () => {\n" + body
              + "\n})().catch(e => { console.error(e && e.stack || String(e)); process.exit(1); });")
    # 명령줄 32KB 상한(WinError 206)을 피해 파일로 넘긴다 — 옆 테스트들과 같은 이유.
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "case.js"
        p.write_text(script, encoding="utf-8")
        out = subprocess.run([node, str(p)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30,
                             stdin=subprocess.DEVNULL)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_pending_save_is_flushed_on_pagehide():
    """★핵심 회귀: 디바운스 대기 중 페이지를 떠나도 대본이 서버에 확정된다."""
    r = _run("""
      saveWork();                       // 1초 디바운스만 걸린 상태(아직 서버 미전송)
      const before = POSTS.length;
      window._pagehide();               // 사이드바에서 다른 작업 클릭 = 이탈
      console.log(JSON.stringify({before, beacons: BEACONS.length,
                                  script: (BEACONS[0]||{}).state?.script}));
    """)
    assert r["before"] == 0, "디바운스 중인데 벌써 서버로 나갔다 — 저장이 매 입력마다 두들긴다"
    assert r["beacons"] == 1, "이탈 시 저장이 플러시되지 않았다 — 대본이 유실된다(원래 버그)"
    assert r["script"] == "대본입니다"


def test_flush_is_noop_without_pending_save():
    """대기 중인 저장이 없으면 이탈이 중복 POST를 만들지 않는다."""
    r = _run("""
      window._pagehide();
      console.log(JSON.stringify({beacons: BEACONS.length}));
    """)
    assert r["beacons"] == 0


def test_demoted_step_is_not_written_back():
    """게이트가 깎은 cur=0은 서버로 안 간다 — 되쓰면 진행단계가 영구 파괴된다."""
    r = _run("""
      _setServerStep(4); cur = 0;       // 복원 시 stepLocked가 강등한 상태
      await _pushWork();
      console.log(JSON.stringify({hasStep: 'step' in POSTS[0]}));
    """)
    assert r["hasStep"] is False, "강등된 0을 서버에 되썼다 — 작업이 1단계에 고착된다"


def test_user_navigation_still_saves_step():
    """사용자가 스스로 옮긴 단계는 정상 저장된다(강등 보호가 저장을 막으면 안 된다)."""
    r = _run("""
      _setServerStep(4); cur = 0;
      _syncServerStep();                // jump()가 부르는 것 = 진짜 이동
      await _pushWork();
      const back = POSTS[0].step;
      cur = 3; _syncServerStep(); POSTS.length = 0;
      await _pushWork();
      console.log(JSON.stringify({back, fwd: POSTS[0].step}));
    """)
    assert r["back"] == 0, "사용자가 0단계로 돌아간 것이 저장되지 않았다"
    assert r["fwd"] == 3, "진행 중 단계가 저장되지 않았다"


def test_job_id_is_committed_immediately():
    """매칭 직후 job_id는 디바운스를 안 탄다 — 안 붙으면 대본 후보가 복원되지 않는다."""
    r = _run("""
      MIX_JOB = 'JOB99';
      saveWork();                       // 디바운스만
      const pending = POSTS.length;
      await _pushWorkNow();             // startProduceMix가 부르는 것
      console.log(JSON.stringify({pending, posts: POSTS.length, job: POSTS[0].job_id}));
    """)
    assert r["pending"] == 0
    assert r["posts"] == 1 and r["job"] == "JOB99", "job_id가 즉시 확정되지 않았다"


def test_push_now_still_omits_unknown_job_id():
    """job을 모를 땐 즉시확정도 job_id를 안 보낸다 — 서버의 기존 연결 보존(2026-08-03 계약)."""
    r = _run("""
      await _pushWorkNow();
      console.log(JSON.stringify({hasJob: 'job_id' in POSTS[0]}));
    """)
    assert r["hasJob"] is False
