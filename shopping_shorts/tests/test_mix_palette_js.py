"""produce.html 조각 전체 보기 JS(2026-07-21) — node 슬라이스 그라운딩(test_mix_swap_js 패턴).

사장님: "이거 자른거 볼수있게 띄워봐". 믹스가 소스를 몇 조각으로 나눠 이 영상에 몇 컷 썼는지
썸네일로 보여주는 패널. 집계는 순수함수 paletteStats(primary+alternates seg_id)로 하고,
openPaletteView가 /api/mix/segments(팔레트 전체)를 그려 쓴 컷에 ✅ 표시.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "// ── 조각 전체 보기(2026-07-21 사장님: \"이거 자른거 볼수있게 띄워봐\") ─── PALETTE-START"
_END = "// ─── PALETTE-END"


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER = r"""
(function(){
  global.window = global;
  global.esc = (s)=>String(s==null?'':s).replace(/</g,'&lt;');
  global.MIX_JOB = 'JID';
  // 실제 쓴 컷: 비트0 primary s0-0 + alt s0-2 / 비트1 primary s1-0 (총 3컷, 소스 2개)
  global.window._mixBeats = [
    {primary:{seg_id:'s0-0', video_id:'s0'}, alternates:[{seg_id:'s0-2', video_id:'s0'}]},
    {primary:{seg_id:'s1-0', video_id:'s1'}, alternates:[]},
  ];
  const seg = {ok:true, segments:[
    {seg_id:'s0-0', scene_desc:'감자 썰기', dur:2.0, thumb_url:'/api/mix/seg_thumb/JID/s0-0'},
    {seg_id:'s0-1', scene_desc:'접시', dur:3.0, thumb_url:'/api/mix/seg_thumb/JID/s0-1'},
    {seg_id:'s0-2', scene_desc:'담기', dur:1.5, thumb_url:'/api/mix/seg_thumb/JID/s0-2'},
    {seg_id:'s1-0', scene_desc:'완성', dur:2.5, thumb_url:'/api/mix/seg_thumb/JID/s1-0'},
  ]};
  global.fetch = async (url)=>{
    if(url.indexOf('/api/mix/segments/')===0) return {json: async()=>seg};
    return {json: async()=>({ok:false})};
  };
  const boxes = {};
  global.document = { getElementById: (id)=>{
    if(!boxes[id]) boxes[id] = {_html:'', dataset:{}, set innerHTML(v){ this._html=v; }, get innerHTML(){ return this._html; }};
    return boxes[id];
  }};

  const stats = paletteStats(global.window._mixBeats);
  const summary = paletteSummaryText(global.window._mixBeats, 4);
  (async()=>{
    await openPaletteView();                       // 1) 펼치기
    const box = document.getElementById('paletteBox');
    const opened = box.innerHTML; const openFlag = box.dataset.open;
    await openPaletteView();                        // 2) 다시 누르면 토글 닫기
    console.log(JSON.stringify({
      placed: stats.placed, distinct: stats.distinct, sources: stats.sources, beats: stats.beats,
      summary: summary, opened: opened, openFlag: openFlag,
      closedHtml: box.innerHTML, closedFlag: box.dataset.open
    }));
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
def test_palette_stats_and_view(tmp_path):
    r = _run(tmp_path)
    # 집계: primary+alternates = 3컷 배치, 3종, 소스 2개, 2문장
    assert r["placed"] == 3, f"쓴 컷 수 오집계: {r['placed']}"
    assert r["distinct"] == 3
    assert r["sources"] == 2, f"소스 수 오집계: {r['sources']}"
    assert r["beats"] == 2
    # 요약 문구: 소스/문장/컷/총조각 숫자가 정확히
    assert "소스 <b>2개</b>" in r["summary"]
    assert "2문장" in r["summary"] and "3컷" in r["summary"]
    assert "총 <b>4조각</b>" in r["summary"]
    # 펼친 패널: 요약 + 팔레트 4조각 전부 + 쓴 컷 ✅ + 안 쓴 조각도 표시
    assert "seg_thumb/JID/s0-1" in r["opened"], "안 쓴 조각(s0-1)도 팔레트에 보여야 함"
    assert "seg_thumb/JID/s0-0" in r["opened"]
    assert "✅" in r["opened"], "쓴 컷 표시가 없음"
    assert r["openFlag"] == "1"
    # 토글 닫기: 다시 누르면 비워지고 플래그 0
    assert r["closedHtml"] == "" and r["closedFlag"] == "0", "토글 닫기가 동작 안 함"
