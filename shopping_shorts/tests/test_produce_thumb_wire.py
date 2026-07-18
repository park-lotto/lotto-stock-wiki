"""썸네일 배선 — fetch를 가짜로 세워 실제 함수를 구동한다.

★test_produce_preview_gate.py의 교훈: fetch를 reject로 스텁하면 함수가 한 줄도
실행되지 않은 채 '통과'한다. 여기선 진짜로 resolve시켜 배선을 구동한다.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _real_deps():
    """썸네일 코드가 기대는 '슬라이스 밖의 진짜 의존물'을 파일에서 그대로 가져온다.

    ★스텁을 새로 짜지 않는다. 하네스가 계약을 발명하면 Critical이 숨는다 — 2026-07-17에
    `global.STATE={job_id:'j1'}`이 정확히 그래서 기능이 0% 동작하는 걸 8건 초록 뒤에 숨겼다.
    esc()는 실브라우저에서 썸네일 코드가 실제로 부르는 것을 확인했다(typeof esc === 'function',
    renderThumbLayers가 &lt;img를 이스케이프하는 것 실측).
    """
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    m = re.search(r"^function esc\(s\)\{.*\}$", src, re.M)
    assert m, "esc() 선언을 못 찾았다 — renderThumbLayers가 이걸 쓴다"
    return m.group(0) + "\n"


def _slice_source():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return _real_deps() + src[src.index("// ── 6단계 썸네일"):src.index("// ── 썸네일 끝")]


def test_thumb_routes_use_a_job_id_variable_that_actually_exists():
    """★2026-07-17 최종 whole-branch 리뷰가 잡은 Critical의 자물쇠.

    썸네일 라우트 3곳이 `STATE.job_id`를 읽었다. 그런데 STATE 선언(:1151)엔 그 키가 없고
    코드 전체에 대입도 0곳이라 실제로는 `undefined`가 나가 frames·save·select가 **전부 404**였다.
    = 이 기능은 단 한 번도 동작한 적이 없다(실브라우저 재현: 화면에 "job 없음", 그리드 0장).

    ★이 자물쇠가 슬라이스가 아니라 **진짜 파일 전체**를 읽는 이유:
    `_slice_source()`는 썸네일 구간만 잘라내므로 STATE·MIX_JOB의 실제 선언이 슬라이스 밖이다.
    그래서 하네스가 `global.STATE={job_id:'j1'}`으로 **없는 계약을 발명**해 넣었고, 자기 스텁을
    자기가 검증하느라 8건이 전부 초록이었다. 슬라이스 테스트는 원리적으로 이 결함을 못 본다.
    """
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "STATE.job_id" not in src, (
        "STATE엔 job_id 키가 없다(:1151 선언, 대입 0곳) — undefined가 나가 라우트가 404난다. "
        "믹스 job id는 MIX_JOB을 써라"
    )
    # MIX_JOB이 '실제로 값이 들어오는' 변수라는 것까지 확인한다 — 이름만 바꾸면 같은 함정이다.
    assert "MIX_JOB=d.job_id" in src.replace(" ", ""), "MIX_JOB에 대입하는 곳이 사라졌다"


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
// ★MIX_JOB이 진짜 계약이다. 여기 STATE={job_id:'j1'}을 심어놨던 게 Critical을 가렸다 —
// 페이지의 STATE(:1151)엔 job_id 키가 없고 대입도 0곳이라 실제로는 undefined가 나가 세 라우트가
// 전부 404였는데, 하네스가 없는 계약을 발명해 자기 스텁을 자기가 검증하고 있었다(2026-07-17 최종리뷰).
// 믹스 job id는 MIX_JOB(:1309 선언, :1716 대입)이고 다른 라우트 호출 7곳도 전부 이걸 쓴다.
global.MIX_JOB = 'j1';
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
    # ★encoding 명시 필수 — Windows 콘솔 기본(cp949)로 두면 Node의 UTF-8 stdout에
    # 한글이 섞였을 때 리더 스레드가 디코드 에러로 죽는다(발견: test_preset_applies_to_selected_layer,
    # '유지될 문구' 로그에서 실측). 베이스라인 결함 — 이 파일이 이번 작업 대상이라 여기서 같이 고친다.
    r = subprocess.run([NODE, "--input-type=module", "-e", script],
                       capture_output=True, text=True, encoding="utf-8",
                       stdin=subprocess.DEVNULL, timeout=30)
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
