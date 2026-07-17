"""썸네일 배선 — fetch를 가짜로 세워 실제 함수를 구동한다.

★test_produce_preview_gate.py의 교훈: fetch를 reject로 스텁하면 함수가 한 줄도
실행되지 않은 채 '통과'한다. 여기선 진짜로 resolve시켜 배선을 구동한다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _slice_source():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index("// ── 6단계 썸네일"):src.index("// ── 썸네일 끝")]


_HARNESS = """
const els = {};
function mkEl(){ return {innerHTML:'', style:{}, value:'', checked:false, children:[],
  addEventListener(){}, getBoundingClientRect(){ return {left:0, top:0, width:270, height:480}; },
  getContext(){ return new Proxy({}, {get(t,k){ if(k==='measureText') return ()=>({width:10});
    return ()=>{}; }, set(){ return true; }}); },
  toBlob(cb){ cb(new Blob(['png'])); } }; }
global.document = { getElementById(id){ return els[id] || (els[id] = mkEl()); },
                    createElement(){ return mkEl(); } };
global.Image = class { set src(v){ this._src = v; if (this.onload) this.onload(); } };
global.Blob = class { constructor(p){ this.parts = p; } };
global.FormData = class { constructor(){ this.d = {}; } append(k, v){ this.d[k] = v; } };
global.STATE = { job_id: 'j1' };
global.HC_FONTS = [{name:'주아', file:'BMJUA.ttf', css:'HCJua'}];
global.HC_PRESETS = [{cat:'썸네일', name:'옐로 팝', font:'BMJUA.ttf', color:'#FFE100',
                      size:76, y:12, outline:true, outline_color:'#000', outline_w:9}];
const FETCHES = [];
global.__fetches = FETCHES;
global.fetch = async (url, opt) => {
  FETCHES.push({url, opt});
  if (url.includes('/thumb/frames'))
    return {ok:true, json: async () => ({ok:true, frames:[{url:'/f/0.jpg', ts:1.2},
                                                          {url:'/f/1.jpg', ts:3.5}]})};
  if (url.includes('/thumb/save'))
    return {ok:true, json: async () => ({ok:true, name:'thumb_1.png', url:'/f/thumb_1.png'})};
  return {ok:true, json: async () => ({ok:true})};
};
"""


def _run(script):
    r = subprocess.run([NODE, "--input-type=module", "-e", script],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_load_frames_calls_api_with_job_id():
    out = _run(_HARNESS + _slice_source() + """
await loadThumbFrames();
console.log(JSON.stringify(__fetches.map(f => f.url)));
""")
    urls = json.loads(out)
    assert any("/api/produce/thumb/frames" in u for u in urls)


def test_load_frames_renders_grid_with_seconds():
    out = _run(_HARNESS + _slice_source() + """
await loadThumbFrames();
console.log(document.getElementById('thumbFrames').innerHTML);
""")
    assert "1.2" in out and "3.5" in out   # 초 배지 — 등분 추출의 이점


def test_generate_uploads_png_and_appends_gallery():
    out = _run(_HARNESS + _slice_source() + """
await loadThumbFrames();
addThumbLayer();
THUMB_STATE.layers[0].text = '강남언니';
await generateThumb();
const saves = __fetches.filter(f => f.url.includes('/thumb/save'));
console.log(JSON.stringify({saves: saves.length,
  gallery: document.getElementById('thumbGallery').innerHTML.includes('thumb_1.png')}));
""")
    res = json.loads(out)
    assert res["saves"] == 1
    assert res["gallery"] is True


def test_generate_sends_meta_with_ratio_coords():
    out = _run(_HARNESS + _slice_source() + """
await loadThumbFrames();
addThumbLayer();
THUMB_STATE.layers[0].text = 'A';
await generateThumb();
const f = __fetches.find(x => x.url.includes('/thumb/save'));
console.log(JSON.stringify(JSON.parse(f.opt.body.d.meta)));
""")
    meta = json.loads(out)
    assert 0 <= meta["layers"][0]["x"] <= 1
    assert 0 <= meta["layers"][0]["y"] <= 1
    assert "frame_ts" in meta


def test_preset_applies_to_selected_layer():
    out = _run(_HARNESS + _slice_source() + """
addThumbLayer();
THUMB_STATE.layers[0].text = '유지될 문구';
applyThumbPreset(0);
console.log(JSON.stringify(THUMB_STATE.layers[0]));
""")
    layer = json.loads(out)
    assert layer["color"] == "#FFE100"
    assert layer["text"] == "유지될 문구", "프리셋이 문구를 지우면 안 된다 — 스타일만 바꾼다"


def test_select_result_calls_select_api():
    out = _run(_HARNESS + _slice_source() + """
await selectThumbResult('thumb_1.png');
const f = __fetches.find(x => x.url.includes('/thumb/select'));
console.log(JSON.stringify(JSON.parse(f.opt.body)));
""")
    body = json.loads(out)
    assert body["name"] == "thumb_1.png"
    assert body["job_id"] == "j1"
