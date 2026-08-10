"""produce.html 장면 우선 토글 + 후보 선택 UI(Task7) — node 슬라이스 그라운딩(test_mix_swap_js 패턴).

백엔드(Task6)는 이미 scene_first 모드에서 추천 후보를 edit_plan으로 자동세팅하므로 이 UI 없이도
동작한다 — 여기서 검증하는 건 (1)"우리 시스템으로 믹스" 시작 payload에 scene_first가 실리는지
(2)후보 카드(renderCandidates)가 추천 배지를 달고 렌더되는지 (3)카드 클릭(pickCandidate)이
/api/mix/candidate를 호출하고 매칭 리뷰를 다시 로드하는지.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "// ── 장면 우선 후보 카드(2026-07-20, Task7) ─── CANDIDATES-START"
_END = "// ─── CANDIDATES-END"


def test_produce_has_scene_first_and_candidates():
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "scene_first" in html
    assert "/api/mix/candidate" in html
    assert "renderCandidates" in html


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER = r"""
(function(){
  global.window = global;
  global.esc = (s)=>String(s==null?'':s);
  global.MIX_JOB = 'JID';
  let captured = {reloaded:false, boxes:{}, fetchCalls:[]};
  global.loadMixReview = ()=>{ captured.reloaded = true; };
  global.fetch = async (url, opts)=>{
    captured.fetchCalls.push({url, body: opts && opts.body ? JSON.parse(opts.body) : null});
    if(url === '/api/mix/candidate') return {json: async()=>({ok:true})};
    return {json: async()=>({ok:false})};
  };
  global.document = { getElementById: (id)=>({ set innerHTML(v){ captured.boxes[id]=v; }, get innerHTML(){ return captured.boxes[id]||''; } }) };

  // 1) 후보 1개 이하 → 고를 게 없어 숨김(빈 문자열)
  renderCandidates([{index:0, score:0.8, recommended:true, hook:'h', story_person:'p'}]);
  const hiddenSingle = captured.boxes['mixCandidates'];

  // 2) 후보 3개, 1개 추천 → 카드 3장 + 추천 배지
  const cands = [
    {index:0, score:0.6, recommended:false, hook:'훅0', story_person:'화자0'},
    {index:1, score:0.9, recommended:true,  hook:'훅1', story_person:'화자1'},
    {index:2, score:0.5, recommended:false, hook:'훅2', story_person:'화자2'},
  ];
  renderCandidates(cands);
  const rendered = captured.boxes['mixCandidates'];

  (async()=>{
    await pickCandidate(1);
    console.log(JSON.stringify({hiddenSingle, rendered, fetchCalls: captured.fetchCalls, reloaded: captured.reloaded}));
  })();
})();
"""


def _run(tmp_path):
    js = tmp_path / "t.js"
    js.write_text(_slice() + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_node_syntax_check():
    """인라인 스크립트 슬라이스 문법 검증 — produce.html 전체가 안 열리는 사고(2026-07-19) 방지."""
    src = _slice()
    out = subprocess.run([NODE, "--check", "-"], input=src, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=30)
    assert out.returncode == 0, out.stderr


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_render_candidates_and_pick(tmp_path):
    r = _run(tmp_path)
    # 후보 1개 이하는 고를 게 없어 카드를 안 그린다
    assert r["hiddenSingle"] == ""
    # 후보 3개: 카드 3장(v6 .cand), hook·story_person 노출, 추천 카드에만 👍 배지 + .on 민트 테두리
    rendered = r["rendered"]
    assert "훅0" in rendered and "훅1" in rendered and "훅2" in rendered
    assert "화자1" in rendered
    assert rendered.count("👍 추천") == 1        # 추천 카드에만 배지(v6 <span class="rec">👍 추천</span>)
    assert 'class="cand on"' in rendered         # 추천 카드는 .on(민트 강조 테두리)
    assert "pickCandidate(1)" in rendered
    # 클릭 → /api/mix/candidate에 job_id/index 전송 → 성공 시 매칭 리뷰 재로드
    calls = [c for c in r["fetchCalls"] if c["url"] == "/api/mix/candidate"]
    assert len(calls) == 1
    assert calls[0]["body"] == {"job_id": "JID", "index": 1}
    assert r["reloaded"] is True


# ── 🎞 따로 만들기 런타임 그라운딩(2026-08-06) ──────────────────────────────
# 사장님 제보: "따로 만들기를 누르면 새로고침되면서 내 작업에 추가가 되야 하는데 안 된다".
# 문자열 검사(test_mix_candidate_clone.test_clone_*)만으론 "정말 서버에 박히나"를 못 본다 —
# 여기서 슬라이스를 실제로 **돌려서** POST와 사이드바 갱신을 눈으로 확인한다.
_CLONE_DRIVER = r"""
(function(){
  global.window = global;
  global.esc = (s)=>String(s==null?'':s);
  global.MIX_JOB = 'JID';
  global.WORK_ID = 'OLD_WORK';
  global.CAND_SEL = 0;
  global.STATE = {script:'원본 대본', script_carryover:true};
  global.PREVIEW_POLL = null; global.PREVIEW_GEN = 0; global.PREVIEW_STATUS = 'ready';
  global._workTimer = null;
  const captured = {fetchCalls:[], pushed:0, saved:0, refreshed:[], boxes:{}};
  global.clearInterval = ()=>{}; global.clearTimeout = ()=>{};
  global.loadMixReview = ()=>{}; global.refreshNextBtn = ()=>{};
  global.confirm = ()=>true; global.alert = (m)=>{ captured.alert = m; };
  global.saveWork = ()=>{ captured.saved++; };
  // 실제 _pushWork는 서버가 준 work_id로 WORK_ID를 채운다 — 그 계약을 그대로 흉내낸다.
  global._pushWork = async ()=>{ captured.pushed++; WORK_ID = 'NEW_WORK'; };
  global.__ssRefreshWorks = (wid)=>{ captured.refreshed.push(wid === undefined ? null : wid); };
  global.fetch = async (url, opts)=>{
    captured.fetchCalls.push({url, body: opts && opts.body ? JSON.parse(opts.body) : null});
    if(url === '/api/mix/candidate/clone') return {json: async()=>({ok:true, job_id:'NEWJOB'})};
    return {json: async()=>({ok:true})};
  };
  global.document = { getElementById: (id)=>({ set innerHTML(v){ captured.boxes[id]=v; },
                                               get innerHTML(){ return captured.boxes[id]||''; } }) };
  // ★CAND_LIST는 슬라이스 안에서 `let`으로 선언돼 global 대입이 안 먹는다(섀도잉).
  //   실제 화면과 똑같이 renderCandidates를 태워 채운다 — 그게 진짜 경로다.
  renderCandidates([
    {index:0, score:0.5, recommended:false, script:'에이 대본 전문', hook:'훅0', story_person:'화자0'},
    {index:1, score:0.9, recommended:true,  script:'씨 대본 전문 토마토 주스', hook:'훅1', story_person:'화자1'},
  ]);
  (async()=>{
    await cloneCandidate(1);
    console.log(JSON.stringify({
      fetchCalls: captured.fetchCalls, pushed: captured.pushed, saved: captured.saved,
      refreshed: captured.refreshed, script: STATE.script, workId: WORK_ID,
      mixJob: MIX_JOB, previewStatus: PREVIEW_STATUS,
    }));
  })();
})();
"""


def _run_clone(tmp_path):
    js = tmp_path / "clone.js"
    js.write_text(_slice() + _CLONE_DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_clone_persists_new_work_and_refreshes_sidebar(tmp_path):
    """★버그의 본체. 복제 후 (1)서버에 **즉시** 새 작업을 박고 (2)사이드바를 다시 그려야
    사장님 눈에 '내 작업'이 하나 더 생긴 게 보인다."""
    r = _run_clone(tmp_path)
    # 복제 API가 고른 후보로 불렸다
    calls = [c for c in r["fetchCalls"] if c["url"] == "/api/mix/candidate/clone"]
    assert len(calls) == 1 and calls[0]["body"] == {"job_id": "JID", "index": 1}
    # 디바운스(saveWork)에만 맡기지 않고 즉시 확정 — 여기가 "추가가 안 된다"의 원인이었다
    assert r["pushed"] == 1, "새 작업이 서버에 즉시 안 박혔다(1초 디바운스에 맡기면 증발한다)"
    # 사이드바를 **새 work_id로** 다시 그린다(_pushWork가 채운 값이어야 한다)
    assert r["refreshed"] == ["NEW_WORK"], f"사이드바 갱신이 잘못됐다: {r['refreshed']}"
    assert r["workId"] == "NEW_WORK"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_clone_carries_chosen_script_for_work_title(tmp_path):
    """작업 제목은 서버가 state.script 앞 20자에서 뽑는다 — 안 실으면 '(제목 없음)'만 쌓인다."""
    r = _run_clone(tmp_path)
    assert r["script"] == "씨 대본 전문 토마토 주스", f"고른 후보 대본이 안 실렸다: {r['script']}"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_clone_switches_job_and_relocks_preview(tmp_path):
    """새 job으로 갈아타면서 옛 미리보기 게이트를 놓아야 유료단계로 안 샌다(기존 계약 유지)."""
    r = _run_clone(tmp_path)
    assert r["mixJob"] == "NEWJOB"
    assert r["previewStatus"] is None
