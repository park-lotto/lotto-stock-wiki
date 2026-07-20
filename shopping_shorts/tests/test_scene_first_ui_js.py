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
    # 후보 3개: 카드 3장, hook·story_person 노출, 추천 카드에만 배지 + accent 테두리
    rendered = r["rendered"]
    assert "훅0" in rendered and "훅1" in rendered and "훅2" in rendered
    assert "화자1" in rendered
    assert rendered.count(">⭐ 추천<") == 1   # 안내문구에도 "⭐ 추천"이 나오므로 배지 마크업만 센다
    assert "pickCandidate(1)" in rendered
    # 클릭 → /api/mix/candidate에 job_id/index 전송 → 성공 시 매칭 리뷰 재로드
    calls = [c for c in r["fetchCalls"] if c["url"] == "/api/mix/candidate"]
    assert len(calls) == 1
    assert calls[0]["body"] == {"job_id": "JID", "index": 1}
    assert r["reloaded"] is True
