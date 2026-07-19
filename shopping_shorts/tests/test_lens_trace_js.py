"""index.html traceByUrl — URL 붙여넣기→렌즈 역추적 프런트 배선 node 슬라이스 그라운딩.

/api/lens/trace_url에 {url}을 POST하고, 결과를 합성 shortcode '__trace__'로 LENS_STATE에
넣어 기존 renderLens를 재활용하는지 검증(담기·필터 재사용의 근거).
"""
import json
import pathlib
import shutil
import subprocess

import pytest

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")
_START = "// ── URL 붙여넣기 → 구글렌즈 원본/유사 역추적(2026-07-19) ─── TRACE-START"
_END = "// ─── TRACE-END"


def _slice():
    src = INDEX_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER = r"""
(function(){
  global.window = global;
  global.LENS_PLATFORMS = [{k:'youtube'},{k:'tiktok'},{k:'instagram'}];
  global._lensHash = (u)=>'H'+u.length;
  global.LENS_STATE = {};
  let rendered = null;
  global.renderLens = (sc)=>{ rendered = sc; };
  global.openScript = ()=>{};
  const boxes = {};
  global.document = {
    getElementById: (id)=>{
      if(id==='traceUrl') return { value:'https://youtube.com/shorts/X' };
      return { set innerHTML(v){ boxes[id]=v; }, get innerHTML(){ return boxes[id]||''; } };
    }
  };
  let posted = null;
  global.fetch = async (url, opts)=>{
    if(url==='/api/lens/trace_url'){ posted = JSON.parse(opts.body); return {status:200, json: async()=>({ok:true, items:[
      {platform:'youtube', url:'https://youtu.be/AAA', title:'원본', thumbnail:'t', match:0.9}]})}; }
    if(url==='/api/mix/basket'){ return {json: async()=>({shortcodes:[]})}; }
    return {status:200, json: async()=>({ok:false})};
  };

  traceByUrl().then(()=>{
    const st = LENS_STATE['__trace__'];
    console.log(JSON.stringify({
      posted,
      rendered,
      hasState: !!st,
      itemCount: st ? st.items.length : 0,
      savesc: st ? st.items[0].savesc : null,
    }));
  });
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
def test_trace_by_url_wires_to_lens(tmp_path):
    r = _run(tmp_path)
    assert r["posted"] == {"url": "https://youtube.com/shorts/X"}   # URL을 POST
    assert r["hasState"] is True                                     # 합성 __trace__ 상태 생성
    assert r["itemCount"] == 1
    assert r["savesc"] == "lens_youtube_H20"                         # 담기 키 합성(platform+_lensHash, url길이20)
    assert r["rendered"] == "__trace__"                             # 기존 renderLens 재활용
