"""삭제한 자리가 **없는 진짜 페이지**에서 아무것도 안 죽는가 (2026-08-24).

강조 단어 칸·프리셋 줄을 뺐다(사장님 "이건 삭제해도 되고"). 위험한 건 삭제 자체가 아니라
**그 자리를 그리던 함수가 던지는 것**이다 — 던지면 뒤에 이어 붙은 호출이 통째로 죽어
화면이 비는 사고가 된다(reference_render죽으면_전화면공백).

그래서 마크업에 실제로 있는 id만 존재하는 세계를 만들어 페이지 스크립트를 통째로 돌린다.
정적 검사(node --check)는 이걸 못 잡는다 — 런타임 오류라서 문법은 유효하다.

⚠️ 테스트 데이터는 반드시 json.dumps로 넣는다(파이썬 문자열로 조립하면 이스케이프가
   무너져 하네스가 죽는다 — 2026-08-24에 세 번 밟았다).
⚠️ node는 이 PC에서 파일을 cp949로 읽는다 → 하네스는 utf-8-sig(BOM)로 쓴다.
"""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

HTML_PATH = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
HTML = HTML_PATH.read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")

_STUB = """
globalThis.window=globalThis;
globalThis.addEventListener=function(){};globalThis.removeEventListener=function(){};
globalThis.dispatchEvent=function(){return true};
globalThis.setInterval=()=>0;globalThis.clearInterval=()=>{};
const mk=()=>{const e={style:{},dataset:{},
 classList:{add(){},remove(){},contains(){return false},toggle(){}},
 addEventListener(){},removeEventListener(){},appendChild(){},prepend(){},
 querySelectorAll(){return []},querySelector(){return null},
 getBoundingClientRect(){return{width:100,height:100,top:0,left:0,right:0,bottom:0}},
 setAttribute(){},getAttribute(){return null},removeAttribute(){},remove(){},
 insertAdjacentHTML(){},focus(){},blur(){},click(){},scrollIntoView(){},
 innerHTML:'',outerHTML:'',value:'',textContent:'',checked:false,disabled:false,
 options:[],children:[],files:[],selectedIndex:0};e.parentElement=null;e.parentNode=null;return e};
const REAL=new Set(__IDS__);
const _c={};
globalThis.document={
 getElementById:(id)=> REAL.has(id)?(_c[id]||(_c[id]=mk())):null,
 querySelector:()=>mk(),querySelectorAll:()=>[],createElement:mk,
 addEventListener(){},removeEventListener(){},body:mk(),documentElement:mk(),
 head:mk(),cookie:'',readyState:'complete',scripts:[]};
globalThis.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
globalThis.sessionStorage=globalThis.localStorage;
globalThis.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({}),text:()=>Promise.resolve('')});
globalThis.location={href:'http://x/produce',search:'',hash:'',pathname:'/produce'};
globalThis.navigator={userAgent:'node',clipboard:{writeText(){}}};
globalThis.alert=()=>{};globalThis.confirm=()=>true;globalThis.prompt=()=>null;
globalThis.requestAnimationFrame=cb=>setTimeout(cb,0);
globalThis.matchMedia=()=>({matches:false,addEventListener(){},addListener(){}});
globalThis.EventSource=function(){this.addEventListener=()=>{};this.close=()=>{}};
globalThis.Image=function(){};globalThis.FormData=function(){};
globalThis.MutationObserver=function(){this.observe=()=>{};this.disconnect=()=>{}};
const TWO_LINE_TEXT=__TWOLINE__;
const HC_SET=__HCSET__;
"""

_TAIL = """
const out={};
out.highlightRuleList_exists=!!document.getElementById('highlightRuleList');
out.hcPresets_exists=!!document.getElementById('hcPresets');
try{ renderHighlightRules(); out.rhr='ok'; }catch(e){ out.rhr='THREW: '+e.message; }
try{ renderPresets(); out.rp='ok'; }catch(e){ out.rp='THREW: '+e.message; }
try{
  STATE.deco=STATE.deco||{};
  document.getElementById('hcText').value=TWO_LINE_TEXT;
  applyHeadcopySet(HC_SET);
  out.rules=(STATE.deco.highlight_rules||[]).map(x=>({k:x.keyword,c:x.color,f:!!x._fromFrame}));
}catch(e){ out.twotone='THREW: '+e.message; }
try{
  document.getElementById('hcColor').value='#111111';
  window._hcCopies=[{label:'x',text:TWO_LINE_TEXT,why:'w'}];
  useHeadcopyColor(0,'#FF00AA');
  out.color_after=document.getElementById('hcColor').value;
  out.text_after=document.getElementById('hcText').value;
}catch(e){ out.colorfn='THREW: '+e.message; }
console.log('RESULT'+JSON.stringify(out));
"""

_ID_RE = re.compile(r'id="([A-Za-z0-9_\-]+)"')
_SCRIPT_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.S)

_TWO_LINE = "AAA\nBBB"
_HC_SET = {"font": "BMDOHYEON.ttf", "color": "#FFFFFF", "color2": "#FFD400",
           "weight": 900, "size": 92, "y": 14, "outline": True,
           "outline_color": "#000000", "outline_w": 12}


def _boot():
    js = "\n".join(_SCRIPT_RE.findall(HTML))
    ids = sorted(set(_ID_RE.findall(HTML)))
    stub = (_STUB.replace("__IDS__", json.dumps(ids))
                 .replace("__TWOLINE__", json.dumps(_TWO_LINE))
                 .replace("__HCSET__", json.dumps(_HC_SET)))
    f = pathlib.Path(tempfile.gettempdir()) / "hc_removed_ui_test.js"
    f.write_text(stub + js + _TAIL, encoding="utf-8-sig")
    r = subprocess.run(["node", str(f)], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[:900]
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith("RESULT"):
            return json.loads(line[6:])
    raise AssertionError("하네스가 결과를 못 냈다")


def test_page_boots_without_the_removed_slots():
    """★페이지 스크립트가 통째로 돈다 — 부팅 중 던지면 화면이 통째로 빈다."""
    out = _boot()
    assert out["highlightRuleList_exists"] is False
    assert out["hcPresets_exists"] is False


def test_removed_slot_renderers_do_not_throw():
    out = _boot()
    assert out["rhr"] == "ok", out["rhr"]
    assert out["rp"] == "ok", out["rp"]


def test_two_tone_still_works_after_ui_removal():
    """★'흰→노랑' 투톤은 highlight_rules를 타고 산다 — UI를 뺐어도 살아야 한다.

    틀이 2줄째(BBB)를 color2로 칠하는 규칙을 넣는다. 이게 죽으면 20종 틀의 투톤이
    통째로 밋밋해진다.
    """
    out = _boot()
    assert "twotone" not in out, out.get("twotone")
    assert out["rules"] == [{"k": "BBB", "c": "#FFD400", "f": True}], out["rules"]


def test_card_color_picker_sets_color_and_text():
    """카드 색 고르개 = 글자색(hcColor) + 그 문구가 함께 들어간다."""
    out = _boot()
    assert "colorfn" not in out, out.get("colorfn")
    assert out["color_after"] == "#FF00AA"
    assert out["text_after"] == _TWO_LINE
