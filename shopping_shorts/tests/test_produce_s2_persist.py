"""2단계 결과 대본 보존 — 새로고침·재방문해도 만든 안이 그대로 돌아온다.

★사장님 제보(2026-08-17): "영상대본 믹스까지 했는데 2단계로 다시 오면 그 대본이 없어져있다"

원인(실측): `S2`는 순수 메모리 객체고 `_workState()`가 담는 건 `STATE.script`(확정한
**1편의 텍스트**)뿐이었다. A안·B안·역할 칸(beats)·게이트 결과·고른 스타일은 어디에도
안 남아, 새로고침하면 `S2.drafts.length===0` → `s2RenderDrafts`가 ③밴드를 통째로
`display:none` 처리한다(= 화면에서 대본이 사라진다).

이 테스트가 잠그는 것:
  1. 만든 초안이 저장 payload(`state.s2`)에 실린다
  2. 그 payload를 되살리면(`_s2Hydrate`) 안·선택·역할 칸이 그대로 돌아온다
  3. **만들자마자** 저장이 나간다 — 확정(s2Confirm) 전에 새로고침해도 안 날아간다
  4. s2가 없는 옛 payload로 복원하면 **깨끗이 비운다**(옛 작업 대본이 새 작업에 눌어붙지
     않는다 — 2026-07-25 캐리오버 사고와 같은 모양을 안 만든다)

produce.html의 **실제 소스**를 앵커로 잘라 Node로 돌린다(test_produce_work_save.py와 같은
방식 — 재구현이 아니다. 재구현하면 소스가 바뀌어도 테스트는 계속 통과한다).
"""
import pathlib
import shutil
import subprocess
import tempfile

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# 저장의 유일한 문. WORK_ID/_workState/_pushWork 선언이 saveWork() 앞에 오므로 그 선언부부터 자른다
# (test_produce_work_save.py와 같은 앵커 — 앵커를 saveWork로 잡으면 WORK_ID가 ReferenceError).
_SAVE_START = "let WORK_ID = null;"
_SAVE_END = "function _consumeProduceHandoff(){"
# 스냅샷/하이드레이트 한 쌍 + S2 선언.
_S2_START = "const S2 = { seed:null"
_S2_END = "// 역할 라벨 — 내부값(beat_roles)"

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
// 가짜 시계 — saveWork는 1초 디바운스라 타이머를 진짜로 굴려야 POST가 나간다.
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
// s2RenderDrafts는 DOM을 만진다 — 이 테스트의 관심사는 **상태**라 호출 여부만 센다.
let RENDERS = 0;
function s2RenderDrafts(){ RENDERS++; }
const document = { getElementById(){ return null; }, querySelectorAll(){ return []; } };
const window = globalThis;
const _replaced = [];
const location = { search:'', pathname:'/produce', href:'/produce' };
const history = { replaceState(s, t, url){
  _replaced.push(url);
  location.search = url.indexOf('?') >= 0 ? url.slice(url.indexOf('?')) : '';
} };
// 초안 2개 — A안(역할 칸 있음, 게이트 통과) / B안(게이트 실패). 실제 응답 모양 그대로.
function mkDrafts(){
  return [
    {style_id:54, style_name:'물건 발견형', passed:true, checks:[{name:'hook', ok:true}],
     tries:[{chars:254, fails:[]}], hook:'이거 진짜 미친 물건이에요',
     beats:[{role:'hook', text:'이거 진짜 미친 물건이에요'},
            {role:'reveal', text:'써보니까 손목이 편해요'},
            {role:'cta', text:'궁금하면 댓글 남겨주세요'}],
     script:'이거 진짜 미친 물건이에요\n써보니까 손목이 편해요\n궁금하면 댓글 남겨주세요'},
    {style_id:53, style_name:'단정 명령형', passed:false, checks:[{name:'hook', ok:false}],
     tries:[{chars:240, fails:['hook']}], hook:'무조건 이거 사세요',
     beats:[{role:'hook', text:'무조건 이거 사세요'}],
     script:'무조건 이거 사세요'},
  ];
}
"""


def _slice(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


@pytest.fixture(scope="module")
def js():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return (_HARNESS
            + _slice(src, _S2_START, _S2_END)
            + _slice(src, _SAVE_START, _SAVE_END))


def _run(js, body):
    wrapped = (js + "\n(async () => {\n" + body
               + "\n})().catch(e => { console.error(e && e.stack || String(e)); process.exit(1); });")
    # node -e 로 넘기지 않는다 — 슬라이스가 커지면 윈도우 명령줄 상한(32KB)에 걸린다.
    with tempfile.TemporaryDirectory() as td:
        script = pathlib.Path(td) / "case.js"
        script.write_text(wrapped, encoding="utf-8")
        r = subprocess.run([NODE, str(script)],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def test_snapshot_carries_drafts(js):
    """만든 초안이 저장 payload에 실린다 — 안 실리면 새로고침에 통째로 날아간다."""
    out = _run(js, """
      S2.drafts = mkDrafts(); S2.curDraft = 1; S2.picked = [54, 53];
      S2.materials = {sources:[{chars:224, head:'치아바타를 샀는데'}], scene_points:7};
      const st = _workState();
      console.log(JSON.stringify({
        has: !!st.s2, n: st.s2 ? st.s2.drafts.length : 0,
        cur: st.s2 ? st.s2.curDraft : null,
        picked: st.s2 ? st.s2.picked : null,
        beats: st.s2 ? st.s2.drafts[0].beats.length : 0,
        mat: st.s2 ? !!st.s2.materials : false,
      }));
    """)
    import json
    d = json.loads(out)
    assert d["has"], "초안이 저장 state에 안 실린다 — 새로고침하면 사라진다"
    assert d["n"] == 2, "A안·B안 둘 다 실려야 한다"
    assert d["cur"] == 1, "보던 안(탭)도 같이 실려야 한다"
    assert d["picked"] == [54, 53], "고른 스타일도 실려야 한다"
    assert d["beats"] == 3, "역할 칸(beats)이 실려야 역할 행을 되살린다"
    assert d["mat"], "재료 표시(materials)도 실려야 '무슨 영상인지'가 남는다"


def test_snapshot_omits_key_when_empty(js):
    """만든 게 없으면 키 자체를 안 만든다 — 빈 값으로 서버의 기존 값을 덮지 않는다."""
    out = _run(js, """
      S2.drafts = [];
      const st = _workState();
      console.log(JSON.stringify({has: Object.prototype.hasOwnProperty.call(st, 's2')}));
    """)
    import json
    assert json.loads(out)["has"] is False, "빈 s2를 실으면 서버에 남아 있는 초안을 지운다"


def test_roundtrip_restores_everything(js):
    """저장 → 복원 왕복. 사장님이 실제로 겪는 경로(새로고침)를 그대로 재현한다."""
    out = _run(js, """
      S2.drafts = mkDrafts(); S2.curDraft = 1; S2.picked = [54, 53];
      S2.materials = {sources:[{chars:224, head:'치아바타를 샀는데'}]};
      const saved = JSON.parse(JSON.stringify(_workState()));   // 서버를 왕복한 셈(JSON 직렬화)
      // ── 새로고침: 메모리가 통째로 초기화된다 ──
      S2.drafts = []; S2.curDraft = 0; S2.picked = []; S2.materials = null;
      _s2Hydrate(saved);
      console.log(JSON.stringify({
        n: S2.drafts.length, cur: S2.curDraft, picked: S2.picked,
        hook: S2.drafts[0].beats[0].text,
        role: S2.drafts[0].beats[0].role,
        passed0: S2.drafts[0].passed, passed1: S2.drafts[1].passed,
        name: S2.drafts[1].style_name,
        mat: !!S2.materials,
      }));
    """)
    import json
    d = json.loads(out)
    assert d["n"] == 2, "복원 후 안이 그대로 2개여야 한다"
    assert d["cur"] == 1, "보던 안으로 돌아와야 한다"
    assert d["picked"] == [54, 53]
    assert d["hook"] == "이거 진짜 미친 물건이에요", "문장이 그대로 살아야 한다"
    assert d["role"] == "hook", "역할이 살아야 역할 행으로 그린다"
    assert d["passed0"] is True and d["passed1"] is False, "게이트 판정이 그대로여야 한다"
    assert d["name"] == "단정 명령형", "스타일 이름(탭 라벨)이 살아야 한다"
    assert d["mat"], "재료 표시가 살아야 한다"


def test_hydrate_clears_when_absent(js):
    """★대본이 아예 없는 작업으로 갈아타면 **비운다**. 앞 작업 대본이 눌어붙으면 안 된다.

    ⚠️ payload에 script가 있으면 그건 '옛 작업 구제'가 도는 정상 경로다
    (test_old_work_recovers_confirmed_script). 여기서 잠그는 건 **아무것도 없는 작업**이
    앞 작업의 초안을 물려받지 않는가다.
    """
    out = _run(js, """
      S2.drafts = mkDrafts(); S2.curDraft = 1; S2.picked = [54];
      S2.materials = {sources:[]};
      _s2Hydrate({handoff:[]});                 // s2도 script도 없는 작업
      console.log(JSON.stringify({n:S2.drafts.length, cur:S2.curDraft,
                                  picked:S2.picked.length, mat:!!S2.materials}));
    """)
    import json
    d = json.loads(out)
    assert d["n"] == 0, "다른 작업으로 갈아탔는데 앞 작업 대본이 남아 있다(캐리오버 사고와 같은 모양)"
    assert d["cur"] == 0 and d["picked"] == 0
    assert d["mat"] is False, "앞 작업의 재료 표시가 남으면 '무슨 영상인지'가 거짓말이 된다"


def test_hydrate_clamps_bad_curdraft(js):
    """저장된 curDraft가 범위를 벗어나면 0으로 — 안 그러면 S2.drafts[cur]가 undefined다."""
    out = _run(js, """
      _s2Hydrate({s2:{drafts:mkDrafts(), curDraft:9}});
      const a = S2.curDraft;
      _s2Hydrate({s2:{drafts:mkDrafts(), curDraft:-1}});
      console.log(JSON.stringify({a:a, b:S2.curDraft}));
    """)
    import json
    d = json.loads(out)
    assert d["a"] == 0 and d["b"] == 0, "범위 밖 인덱스를 그대로 쓰면 확정 버튼이 undefined를 집는다"


def test_saves_before_confirm_with_empty_pool(js):
    """★사장님이 실제로 겪은 경로: 대본만 뽑고(확정 전) 새로고침 → 살아 있어야 한다.

    확정 전이라 STATE.script는 ''이다. 영상풀까지 비어 있으면 saveWork/_pushWork의
    `!HANDOFF.length && !st.script` 가드가 저장을 통째로 걸러 초안이 날아갔다.
    """
    out = _run(js, """
      HANDOFF = [];             // 영상 안 담김
      STATE.script = '';        // 아직 확정 안 함
      S2.drafts = mkDrafts(); S2.curDraft = 0;
      saveWork();
      await tick(1500);
      const local = JSON.parse(sessionStorage.getItem('produce_work')||'null');
      console.log(JSON.stringify({
        posts: POSTS.length,
        localN: local && local.s2 ? local.s2.drafts.length : 0,
        serverN: POSTS.length ? POSTS[0].body.state.s2.drafts.length : 0,
      }));
    """)
    import json
    d = json.loads(out)
    assert d["localN"] == 2, "확정 전 초안이 로컬(sessionStorage)에 안 남는다 — 새로고침에 사라진다"
    assert d["posts"] == 1, "확정 전 초안이 서버로 안 올라간다 — 다른 기기·재방문에서 사라진다"
    assert d["serverN"] == 2, "서버 payload에 초안이 실려야 한다"


def test_old_work_recovers_confirmed_script(js):
    """★이 배포 **전에** 만든 작업 구제 — 후보는 못 되살려도 '확정한 대본'은 보여준다.

    사장님 제보: "확정 대본도 안 보인다". s2 스냅샷이 없는 옛 작업이라도 `w.script`
    (확정본)는 예전부터 저장돼 있었다 — 없는 걸 지어내는 게 아니라 있는 걸 보여준다.
    """
    out = _run(js, """
      S2.drafts = [];
      _s2Hydrate({script:'이거 진짜 미친 물건이에요\\n손목이 편해집니다', handoff:[]});
      const d = S2.drafts[0] || {};
      console.log(JSON.stringify({
        n: S2.drafts.length, cur: S2.curDraft,
        script: d.script, hook: d.hook, name: d.style_name,
        checks: (d.checks||[]).length,      // 게이트 결과는 모른다 → 뱃지 안 뜬다
        beats: (d.beats||[]).length,        // 역할도 모른다 → 비운다(s2Beats가 문장으로 나눔)
      }));
    """)
    import json
    d = json.loads(out)
    assert d["n"] == 1, "확정한 대본이 있는데 ③가 비어 있다 — 사장님이 보신 화면"
    assert d["script"].startswith("이거 진짜 미친 물건이에요")
    assert d["hook"] == "이거 진짜 미친 물건이에요", "첫 줄이 훅으로 잡혀야 탭·요약이 산다"
    assert d["name"] == "확정한 대본", "옛 안인지 새 안인지 라벨로 구분돼야 한다"
    assert d["checks"] == 0, "모르는 게이트 결과를 ✅/⚠️로 지어내면 안 된다"
    assert d["beats"] == 0, "모르는 역할을 붙이면 안 된다(모르면 비운다)"


def test_old_work_recovery_uses_payload_not_global(js):
    """★구제가 캐리오버를 만들면 안 된다 — 반드시 그 작업의 저장값(w.script)만 쓴다.

    STATE.script(전역, 앞 작업 잔재일 수 있음)를 보고 만들면 다른 작업으로 갈아탔을 때
    앞 작업 대본이 딸려온다(2026-07-25 사고와 같은 모양).
    """
    out = _run(js, """
      STATE.script = '앞 작업의 확정 대본';     // 전역엔 앞 작업 잔재가 남아 있다
      S2.drafts = mkDrafts();
      _s2Hydrate({handoff:[]});                 // 새 작업: script도 s2도 없다
      console.log(JSON.stringify({n:S2.drafts.length, first:(S2.drafts[0]||{}).script||null}));
    """)
    import json
    d = json.loads(out)
    assert d["n"] == 0, "대본 없는 작업에 앞 작업 대본이 딸려왔다(캐리오버)"
    assert d["first"] is None


def test_new_snapshot_wins_over_recovery(js):
    """s2 스냅샷이 있으면 그게 이긴다 — 구제는 **없을 때만** 도는 폴백이다."""
    out = _run(js, """
      _s2Hydrate({s2:{drafts:mkDrafts(), curDraft:1}, script:'확정본 텍스트'});
      console.log(JSON.stringify({n:S2.drafts.length, cur:S2.curDraft,
                                  name:S2.drafts[0].style_name}));
    """)
    import json
    d = json.loads(out)
    assert d["n"] == 2 and d["cur"] == 1, "스냅샷이 있는데 폴백이 덮어썼다"
    assert d["name"] == "물건 발견형", "실제 스타일 이름이 '확정한 대본'으로 뭉개지면 안 된다"


def test_hydrate_survives_empty_drafts_array(js):
    """drafts:[] 인 s2도 '없음'으로 친다(밴드가 빈 채로 켜지면 화면이 깨진다)."""
    out = _run(js, """
      S2.drafts = mkDrafts();
      _s2Hydrate({s2:{drafts:[], curDraft:0}});
      console.log(JSON.stringify({n:S2.drafts.length}));
    """)
    import json
    assert json.loads(out)["n"] == 0
