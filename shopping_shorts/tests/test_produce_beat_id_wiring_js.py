"""produce.html 편집안 — 화면 위치 i ≠ 진짜 칸 번호 beat_idx (2026-09-27).

서버 라우트 /ai_scene·/cutaway·/sfx 는 edit_plan.beats[].beat_idx 로 칸을 찾는다.
칸을 지운 작업은 번호가 빠진다(0,2,3). 화면이 위치 1을 그대로 보내면 서버는 번호 1을 찾다 422,
위치 2를 보내면 번호 2(=화면 위치 1) 칸에 엉뚱하게 붙는다.

이 테스트는 produce.html의 실제 JS 구간을 떼어 node로 돌린다(정적 문자열 검사 아님):
  - 위치 1 버튼 → 세 통로 fetch body 의 beat_idx 가 2
  - _refreshBeatBox(1) 이 번호 2 칸을 다시 그린다
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
_START = "let MIX_REVIEW_SUGGESTIONS = [];"
_END = "// ── [다른 화면으로] 스왑 피커(2026-07-19) ─── SWAP-START"


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    a = src.index(_START)
    return src[a:src.index(_END, a)]


_DRIVER = r"""
(async function(){
  global.window = global;
  global.esc = (s)=>String(s==null?'':s);
  global.ErrorHelp = {html: ()=>'NET'};
  global.MIX_JOB = 'JID';
  global.setInterval = ()=>0;           // pollAiScene 이 프로세스를 붙잡지 않게
  global.clearInterval = ()=>{};
  const boxes = {};
  global.document = { getElementById: (id)=>({
    set innerHTML(v){ boxes[id]=v; }, get innerHTML(){ return boxes[id]||''; } }) };

  // 1번 칸을 지운 편집안: 위치 0,1,2 ↔ 번호 0,2,3
  const beats = [
    {beat_idx:0, role:'훅'},
    {beat_idx:2, role:'본문', cutaway:{asset_id:22, match_type:'manual'},
     sfx:{asset_id:9, match_type:'role', position:'first'}},
    {beat_idx:3, role:'CTA'},
  ];
  globalThis._mixBeats = beats;
  globalThis.MIX_AI_SCENE_ON = true;

  const posts = {};
  global.fetch = async (url, opts)=>{
    if(opts && opts.method==='POST'){
      const k = url.split('/').pop();
      posts[k] = JSON.parse(opts.body);
      return {json: async()=>({ok:true})};
    }
    if(url.indexOf('/api/mix/result/')===0)
      return {json: async()=>({ok:true, beats: beats, asset_suggestions: [], ai_scene_enabled: true})};
    return {json: async()=>({ok:false})};
  };

  const html = renderSceneCutaway(beats[1], 1) + renderSceneSfx(beats[1], 1);
  await startAiScene(1, 'natural');
  await toggleCutaway(1, null);
  await removeSfx(1);
  delete boxes['sceneCutaway1'];
  const refreshed = await _refreshBeatBox(1);
  console.log(JSON.stringify({
    html, posts,
    refreshedIdx: refreshed ? refreshed.beat_idx : null,
    refreshedBox: boxes['sceneCutaway1'] || null,
  }));
})().catch(e=>{ console.error(e && e.stack || e); process.exit(1); });
"""


def _run():
    out = run_js(_slice() + _DRIVER)
    return json.loads(out.splitlines()[-1])


def test_buttons_keep_dom_position_but_send_beat_idx():
    r = _run()
    # 화면(DOM·onclick)은 위치 1 그대로
    assert "startAiScene(1,'natural')" in r["html"]
    assert "toggleCutaway(1,null)" in r["html"]
    assert "removeSfx(1)" in r["html"]
    # 서버로 가는 값은 번호 2 — 세 통로 모두
    assert r["posts"]["ai_scene"]["beat_idx"] == 2
    assert r["posts"]["cutaway"]["beat_idx"] == 2
    assert r["posts"]["sfx"]["beat_idx"] == 2


def test_refresh_beat_box_redraws_by_position():
    r = _run()
    assert r["refreshedIdx"] == 2
    assert r["refreshedBox"] and "자산 #22" in r["refreshedBox"]


# ── 트림·대사 줄이기(TRIM 구간) — 같은 변환 함수를 타는지 ─────────────────
_TRIM_START = "// ── [끝/앞 조용한 부분 자르기] 트림(2026-07-22) ─── TRIM-START"
_TRIM_END = "// ─── TRIM-END"


def _trim_slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    a = src.index("function mixBeatIdAt(")
    conv = src[a:src.index("\n}\n", a) + 3]        # 변환 함수는 원본에서 그대로 떼어 붙인다
    t = src.index(_TRIM_START)
    return conv + src[t:src.index(_TRIM_END, t)]


_TRIM_DRIVER = r"""
(async function(){
  global.window = global;
  global.esc = (s)=>String(s==null?'':s);
  global.ErrorHelp = {html: ()=>'NET'};
  global.MIX_JOB = 'JID';
  global.loadMixReview = ()=>{};
  global.document = { getElementById: ()=>({ innerHTML: '' }) };
  globalThis._mixBeats = [{beat_idx:0}, {beat_idx:2}, {beat_idx:3}];
  const posts = {};
  global.fetch = async (url, opts)=>{
    posts[url.split('/').pop()] = JSON.parse(opts.body);
    return {json: async()=>({ok:true, changed:true, tail_trim:0.3})};
  };
  const html = renderTrimControls({}, 1);
  await doShorten(1);
  await doTrim(1, 'tail', 'nudge');
  console.log(JSON.stringify({html, posts}));
})().catch(e=>{ console.error(e && e.stack || e); process.exit(1); });
"""


def test_trim_and_shorten_send_beat_idx():
    out = run_js(_trim_slice() + _TRIM_DRIVER)
    r = json.loads(out.splitlines()[-1])
    assert "doTrim(1,'tail','auto')" in r["html"]       # 화면(onclick)은 위치 그대로
    assert r["posts"]["shorten"]["beat_idx"] == 2
    assert r["posts"]["trim"]["beat_idx"] == 2
    assert r["posts"]["trim"]["edge"] == "tail" and r["posts"]["trim"]["mode"] == "nudge"
