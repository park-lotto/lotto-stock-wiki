"""작업파일 — 최종 whole-branch 리뷰가 잡은 이음새 2건(C-1·C-2).

★이 파일의 존재 이유: 태스크별 테스트 62건이 **전부 green인데 이 둘이 살아 있었다**.
각 태스크는 각각 옳았고, 결함은 태스크와 태스크 **사이**에만 있었다. 이 트랙에서 최종
whole-branch 리뷰가 개별 리뷰를 뚫고 이음새를 잡은 세 번째 사례다.

C-1: "+ 새 작업"이 새 작업이 아니라 **직전 작업을 덮어쓴다**.
  sidebar.js의 "+ 새 작업"은 `/produce`로 갈 뿐인데(T6 `f4484ede` 시점엔 그게 빈 화면이었다),
  뒤이은 복제버그 수정 `cad0e7b0`이 `_consumeProduceHandoff`에 WORK_ID 복원을 넣으면서
  그 전제를 깼다. → 새 작업을 누르면 작업 A가 열리고 이후 저장이 전부 A를 덮어쓴다.
  **사장님이 제보한 "작업물이 지워진다"를, 그걸 고치려 만든 기능이 그대로 재현한다.**
  ★설계 긴장: 새로고침도 "+ 새 작업"도 **똑같은 /produce**라 신호 없이는 코드가 구분 못 한다.
  → `?new=1`로 가른다. 기존 복제방지(test_reopening_does_not_duplicate_the_work)는 그대로 산다.

C-2: 복원이 **렌더설정을 안 되살려** [렌더]가 서버 꾸미기를 null로 덮고, 자막제거는 몰래 과금된다.
  `_workState()`는 대본 쪽만 저장하는데 `STATE`(produce.html:1117) 주석은 "확정 대본 + 렌더 설정"이다.
  복원 후 `renderFinal`이 `saveHeadcopy()`를 부르면 빈 STATE가 그대로 job에 POST돼
  headcopy·caption_style·deco가 **null로 덮인다**. 그런데 `subtitle_removal`은 job에 True로 남아
  (mix_pipeline이 job에서 읽는다) **유료 VMake가 그대로 도는데 화면은 "꺼짐"이라 표시한다.**
  ★렌더설정의 주인은 작업파일이 아니라 **job**이다 — 작업파일에 복제하면 진실의 원천이 둘이 되어
  새 불일치를 만든다. 그래서 서버가 job에서 읽어 내려주고 복원이 그걸 STATE에 꽂는다.
"""
import pathlib
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
SIDEBAR_JS = pathlib.Path(__file__).resolve().parents[1] / "static" / "sidebar.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _slice(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


def _run(js, body):
    # encoding="utf-8": 기본(cp949) 캡처는 한글 console.log를 못 읽고 죽는다(저장소 전역 함정).
    r = subprocess.run([NODE, "-e", js + "\n(async()=>{\n" + body + "\n})();"],
                       capture_output=True, text=True, timeout=30,
                       encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


# ── C-1: "+ 새 작업" ↔ 새로고침 ────────────────────────────────
_BOOT_START = "function _bootRestore(){"
_BOOT_END = "_bootRestore();"

_BOOT_HARNESS = r"""
'use strict';
// ★실제 페이지와 같이 null로 시작한다(produce.html:1294 `let WORK_ID = null;`).
// 낡은 정체성은 변수가 아니라 **sessionStorage에만** 산다 — 여기에 'w-직전작업'을 미리
// 넣어두면 부팅 시점에 존재할 수 없는 상태를 만들어 하네스가 거짓 실패를 낸다(실제로 겪음).
let WORK_ID = null;
let _cleared = 0, _restoredWith = null, _consumed = 0;
const _store = { produce_work: JSON.stringify({script:'작업 A의 대본', work_id:'w-직전작업'}) };
const sessionStorage = { setItem(k,v){_store[k]=v;}, getItem(k){return _store[k]||null;},
                         removeItem(k){delete _store[k];} };
function clearWork(){ _cleared++; sessionStorage.removeItem('produce_work'); }
function _restoreWork(id){ _restoredWith = id; }
function _consumeProduceHandoff(){
  _consumed++;
  // 실제 코드와 같은 조건: 넘어온 게 없으면 sessionStorage의 이전 작업을 되살린다.
  let w; try{ w=JSON.parse(sessionStorage.getItem('produce_work')||'null'); }catch(e){ w=null; }
  if(w && w.script){ WORK_ID = w.work_id || null; }
}
function renderPool(){}
let _replacedTo = null;
const history = { replaceState(a,b,url){ _replacedTo = url; } };
let location = { search: '' };
"""


@pytest.fixture(scope="module")
def js_boot():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return _BOOT_HARNESS + _slice(src, _BOOT_START, _BOOT_END)


def test_new_work_does_not_hijack_the_previous_work(js_boot):
    """★C-1 본체: "+ 새 작업"(?new=1)은 직전 작업의 WORK_ID를 이어받으면 안 된다.

    이걸 놓치면 새 작업으로 저장하는 순간 작업 A가 통째로 덮어써진다(제목까지 교체).
    """
    out = _run(js_boot, """
      location = { search: '?new=1' };
      _bootRestore();
      console.log(JSON.stringify({wid: WORK_ID, cleared: _cleared,
                                  stored: sessionStorage.getItem('produce_work')}));
    """)
    assert '"wid":null' in out, f"+ 새 작업이 직전 작업의 WORK_ID를 물고 있다 — 저장하면 그 작업이 덮어써진다: {out}"
    assert '"cleared":1' in out, f"clearWork()가 안 불렸다: {out}"
    assert '"stored":null' in out, f"sessionStorage에 직전 작업이 남아 있다 — 다음 로드가 또 되살린다: {out}"


def test_new_work_strips_the_flag_so_refresh_does_not_keep_spawning(js_boot):
    """★?new=1을 URL에 남겨두면 이 화면에서 새로고침할 때마다 새 작업이 또 생긴다.

    그러면 cad0e7b0이 막은 "매 로드마다 작업 복제"가 반대 방향으로 되살아난다.
    """
    out = _run(js_boot, """
      location = { search: '?new=1' };
      _bootRestore();
      console.log(JSON.stringify({to: _replacedTo}));
    """)
    assert '"to":"/produce"' in out, f"URL에서 new를 안 지웠다 — 새로고침마다 새 작업이 생긴다: {out}"


def test_plain_reload_still_resumes_the_same_work(js_boot):
    """★C-1 수정의 반대편: 그냥 새로고침(?new 없음)은 **여전히 같은 작업을 이어야** 한다.

    이걸 같이 잠그지 않으면 C-1을 고치다 cad0e7b0(복제 방지)을 되돌리게 된다.
    """
    out = _run(js_boot, """
      location = { search: '' };
      _bootRestore();
      console.log(JSON.stringify({wid: WORK_ID, cleared: _cleared, consumed: _consumed}));
    """)
    assert '"wid":"w-직전작업"' in out, f"새로고침이 작업을 이어받지 못했다 — 열 때마다 복제된다: {out}"
    assert '"cleared":0' in out, f"새로고침인데 작업을 지웠다: {out}"


def test_work_link_still_restores_from_server(js_boot):
    """?work=<id>는 그대로 서버 복원을 탄다(회귀)."""
    out = _run(js_boot, """
      location = { search: '?work=w-77' };
      _bootRestore();
      console.log(JSON.stringify({restored: _restoredWith}));
    """)
    assert '"restored":"w-77"' in out, out


def test_sidebar_new_work_signals_a_new_work():
    """★sidebar.js가 신호를 안 보내면 produce.html은 새로고침과 구분할 방법이 없다.

    이 둘은 **다른 파일**이라 각각의 태스크 리뷰가 서로를 못 봤다 — 이음새의 정의.
    """
    src = SIDEBAR_JS.read_text(encoding="utf-8")
    assert "+ 새 작업" in src, "사이드바에서 '+ 새 작업'이 사라졌다"
    i = src.index("+ 새 작업")
    line = src[max(0, i - 200):i]
    assert "/produce?new=1" in line, (
        "'+ 새 작업'이 신호 없이 /produce로 간다 — produce.html이 새로고침과 구분 못 해 "
        "직전 작업을 덮어쓴다(C-1)")


# ── C-2: 복원이 렌더설정을 되살린다 ────────────────────────────
_RESTORE_START = "async function _restoreWork(workId){"
_RESTORE_END = "function _consumeProduceHandoff(){"

_RESTORE_HARNESS = r"""
'use strict';
let HANDOFF = [];
const STATE = { script:'', script_src_idx:null, script_from_wiki:null,
                subtitleRemoval:false, headcopy:null, captionStyle:null,
                deco:{ extra_texts:[], motion:null } };
const STEPS = ['대본','자막제거','TTS','꾸미기','최종'];
let cur = 0, MIX_JOB = null, WORK_ID = null, PREVIEW_STATUS = null;
function canGoNext(){ return PREVIEW_STATUS === 'ready' || PREVIEW_STATUS === 'failed'; }
function refreshNextBtn(){}
function renderSteps(){}
function showPanel(){}
function renderPool(){}
function syncFootageToMixUrls(){}
function refreshFinalPeek(){}
function setScriptMode(){}
function _consumeProduceHandoff(){}
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
    return _RESTORE_HARNESS + _slice(src, _RESTORE_START, _RESTORE_END)


def test_restore_brings_back_render_settings_from_the_job(js_restore):
    """★C-2 본체: 복원이 렌더설정을 안 되살리면 [렌더]가 서버 꾸미기를 null로 덮는다.

    renderFinal이 `await saveHeadcopy()`로 STATE를 그대로 job에 POST하기 때문이다.
    """
    out = _run(js_restore, """
      RESPONSES = {
        '/api/produce/works/': {ok:true, step:0, job_id:'job-9',
          state:{handoff:[], script:'대본'},
          settings:{headcopy:{text:'충격! 이 제품'}, caption_style:{preset:'bold-yellow'},
                    deco:{extra_texts:[{text:'한정특가'}], motion:{pack_id:'zoom'}},
                    subtitle_removal:true}},
        '/api/mix/status/': {ok:true, preview_status:'ready'}};
      await _restoreWork('w-1');
      console.log(JSON.stringify({hc:STATE.headcopy, cap:STATE.captionStyle,
                                  deco:STATE.deco, sub:STATE.subtitleRemoval}));
    """)
    assert '"충격! 이 제품"' in out, f"headcopy를 안 되살렸다 — 렌더가 서버 값을 null로 덮는다: {out}"
    assert '"bold-yellow"' in out, f"caption_style을 안 되살렸다: {out}"
    assert '"한정특가"' in out, f"deco를 안 되살렸다 — 꾸미기가 통째로 날아간다: {out}"
    assert '"sub":true' in out, (
        f"subtitleRemoval을 안 되살렸다 — job은 True라 유료 VMake가 도는데 화면은 '꺼짐'이라 "
        f"표시한다(몰래 과금): {out}")


def test_restore_without_settings_leaves_safe_defaults(js_restore):
    """settings가 없으면(job 없는 작업) 안전한 기본값 — deco는 **모양이 있어야** 한다.

    deco를 null로 두면 5단계 꾸미기가 `STATE.deco.extra_texts`에서 터진다.
    """
    out = _run(js_restore, """
      RESPONSES = {'/api/produce/works/': {ok:true, step:0, job_id:null,
        state:{handoff:[], script:'대본'}}};
      await _restoreWork('w-2');
      console.log(JSON.stringify({hc:STATE.headcopy, deco:STATE.deco, sub:STATE.subtitleRemoval}));
    """)
    assert '"hc":null' in out, out
    assert '"extra_texts":[]' in out, f"deco 기본 모양이 깨졌다 — 꾸미기 단계가 터진다: {out}"
    assert '"sub":false' in out, out


# ── 서버: 렌더설정은 job에서 읽어 내려준다 ──────────────────────
@pytest.fixture
def client(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    return TestClient(app_mod.app)


def test_get_one_carries_render_settings_from_the_job(client):
    """★렌더설정의 주인은 job이다 — 작업 조회가 그걸 같이 내려줘야 복원이 되살릴 수 있다.

    작업파일에 복제하지 않는 이유: 진실의 원천이 둘이 되면 새 불일치가 생긴다.
    """
    from shopping_shorts import app as app_mod
    from shopping_shorts.store import Store

    st = Store(app_mod.DB_PATH)
    job_id = "job-테스트"
    st.create_mix_job(job_id, ["https://x/1"], 30, "free")
    st.update_mix_job(job_id, headcopy={"text": "헤드"},
                      caption_style={"preset": "bold"},
                      deco={"extra_texts": [{"text": "특가"}], "motion": None},
                      subtitle_removal=True)
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "s"}, "job_id": job_id}).json()["work_id"]

    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["settings"] is not None, "settings를 안 내려준다 — 복원이 렌더설정을 못 되살린다(C-2)"
    assert d["settings"]["headcopy"] == {"text": "헤드"}
    assert d["settings"]["caption_style"] == {"preset": "bold"}
    assert d["settings"]["deco"]["extra_texts"] == [{"text": "특가"}]
    assert d["settings"]["subtitle_removal"] is True, (
        "subtitle_removal을 안 내려준다 — 화면은 '꺼짐'인데 job은 True라 유료 VMake가 몰래 돈다")


def test_get_one_without_job_has_no_settings(client):
    wid = client.post("/api/produce/works", json={"state": {"script": "s"}}).json()["work_id"]
    assert client.get(f"/api/produce/works/{wid}").json()["settings"] is None


# ── 죽은 테스트 메우기(최종리뷰 M4b) ───────────────────────────
def test_other_customer_cannot_delete_legacy_customer_zero_work(client, monkeypatch):
    """★기존 test_isolation_get_and_delete_are_404_for_other_customer는 **가짜 자물쇠**였다.

    delete 라우트의 `customer_id=_cid(request)`를 통째로 지워도 17/17이 통과했다 —
    인자를 빼면 기본값 0으로 떨어지는데, 그 테스트는 고객 1·2만 쓰므로 `WHERE customer_id=0`이
    아무것도 못 맞혀 **의도한 가드가 아니라 "0은 아무것도 소유 안 함"이라는 엉뚱한 사실에 걸려**
    404가 났다.

    그런데 이 저장소의 **기존 데이터는 전부 고객0(LEGACY)에 귀속**된다(store.py:443) —
    즉 저 가드가 사라지면 로그인한 아무 고객이나 **사장님 본인의 작업을 삭제**할 수 있는데
    스위트는 green이었다. 고객0을 피해자로 세워야만 자물쇠가 진짜가 된다.
    """
    from shopping_shorts import app as app_mod
    from shopping_shorts.store import LEGACY_CUSTOMER_ID

    monkeypatch.setattr(app_mod, "_cid", lambda request: LEGACY_CUSTOMER_ID)
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "사장님 작업"}}).json()["work_id"]

    monkeypatch.setattr(app_mod, "_cid", lambda request: 2)
    assert client.post(f"/api/produce/works/{wid}/delete").status_code == 404, (
        "남이 고객0(사장님)의 작업을 지웠다")
    assert client.get(f"/api/produce/works/{wid}").status_code == 404

    monkeypatch.setattr(app_mod, "_cid", lambda request: LEGACY_CUSTOMER_ID)
    assert client.get(f"/api/produce/works/{wid}").status_code == 200, "작업이 실제로 지워졌다"
