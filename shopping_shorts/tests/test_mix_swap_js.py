"""produce.html 스왑 피커 JS — node 슬라이스 그라운딩(test_produce_mix_seconds_js 패턴)."""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "// ── [다른 화면으로] 스왑 피커(2026-07-19) ─── SWAP-START"
_END = "// ─── SWAP-END"


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER = r"""
(function(){
  global.window = global;
  global.esc = (s)=>String(s==null?'':s);
  global.MIX_JOB = 'JID';
  let captured = {reloaded:false, boxes:{}};
  global.loadMixReview = ()=>{ captured.reloaded = true; };
  const seg = {ok:true, segments:[
    {seg_id:'s0-0', scene_desc:'감자', dur:2.0, thumb_url:'/api/mix/seg_thumb/JID/s0-0', used:true},
    {seg_id:'s0-1', scene_desc:'접시', dur:3.0, thumb_url:'/api/mix/seg_thumb/JID/s0-1', used:false},
  ]};
  let adjustBody = null;
  global.fetch = async (url, opts)=>{
    if(url.indexOf('/api/mix/segments/')===0) return {json: async()=>seg};
    if(url==='/api/mix/adjust'){ adjustBody = JSON.parse(opts.body); return {json: async()=>({ok:true})}; }
    return {json: async()=>({ok:false})};
  };
  global.document = { getElementById: (id)=>({ set innerHTML(v){ captured.boxes[id]=v; }, get innerHTML(){ return captured.boxes[id]||''; } }) };

  // 1) fit<=2 → 강조 버튼
  const btnWeak = renderSwapButton({fit:2}, 0);
  const btnOk = renderSwapButton({fit:5}, 1);

  (async()=>{
    await openSwapPicker(0);
    const picker = captured.boxes['sceneSwap0'];   // doSwap이 같은 박스를 로딩문구로 곧장 덮어쓰므로 여기서 스냅샷
    await doSwap(0, 's0-1');
    console.log(JSON.stringify({btnWeak, btnOk, picker, adjustBody, reloaded: captured.reloaded}));
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
def test_swap_button_and_flow(tmp_path):
    r = _run(tmp_path)
    # fit<=2 버튼은 강조(fire 테두리), 정상 비트는 아님
    assert "var(--fire)" in r["btnWeak"]
    assert "var(--fire)" not in r["btnOk"]
    assert "openSwapPicker(0)" in r["btnWeak"]
    # 피커: 두 썸네일 + used 표기 + 클릭 핸들러
    assert "seg_thumb/JID/s0-1" in r["picker"]
    assert "doSwap(0,'s0-1')" in r["picker"]
    assert "사용중" in r["picker"]              # used seg 표기
    # 스왑: adjust에 job_id/beat_idx/seg_id 정확히 전송 + 전체 재로드
    assert r["adjustBody"] == {"job_id": "JID", "beat_idx": 0, "seg_id": "s0-1"}
    assert r["reloaded"] is True
