"""제목 글자 색·테두리 배선(2026-08-28 사장님 "폰트쪽 꾸미는것 추가") — 동작 검사.

지키는 계약 3개:
① 색 칸은 **만졌을 때만** 값이 된다(FR_TOUCHED) — 안 만지면 ''로 남아 서버가 자동을 쓴다.
② ↩ 자동(frTtDecoReset)은 제목 꾸미기만 물린다 — 틀 색(bar 등)은 안 건드린다.
③ 저장된 작업을 다시 열면(frFill) 값이 있는 것만 '만진 것'으로 되살아난다.

텍스트 검사가 아니라 **함수를 실제로 돌린다**(syncFrameHandles 사고와 같은 이유 —
"코드에 있다"는 "돈다"가 아니다).
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import run_js, requires_node

pytestmark = requires_node

HTML = pathlib.Path(__file__).resolve().parents[1].joinpath(
    "static", "produce.html").read_text(encoding="utf-8")


def _slice(start_marker, end_marker):
    i = HTML.index(start_marker)
    j = HTML.index(end_marker, i + len(start_marker))
    return HTML[i:j]


def _harness(script):
    src = (_slice("let FR_PRESETS=[];", "function frResetCustom(")
           + _slice("function frameUrl(", "async function loadFramePresets(")
           + _slice("function frFill(", "function frPick(")
           + _slice("function frUpdate(", "function frBar("))
    return r"""
const NODES = {};
function mkNode(id){
  return { id, value:'', textContent:'', checked:false, style:{}, innerHTML:'' };
}
['frChannel','frTitle','frViews','frComments','frAd','frIcons','frBar','frBottom',
 'frBarVal','frBottomVal','frChFont','frChSize','frChSizeV','frChX','frChXV',
 'frTtFont','frTtSize','frTtSizeV','frTtX','frTtXV',
 'frTtColor','frTtOlC','frTtOlW','frTtOlWV',
 'frBarColor','frOnBarColor','frSubBg','frSubText',
 'frLeftIcon','frRightIcon','frCenter',
 'frAdSize','frAdSizeV','frAdAlpha','frAdAlphaV','frAdX','frAdY','adBadgeTune'
].forEach(id => NODES[id] = mkNode(id));
const document = { getElementById: id => NODES[id] || null };
const STATE = {deco:{template:{span:'full', frame:{preset:'news_coral', bar_h:190}}}};
function renderTemplatePreview(){}
function saveHeadcopy(){}
function frHcLabel(){}
function fillFrameFontSelects(){}
function syncAdBadge(){}
function renderFrTemplates(){}
""" + src + "\n" + script


def _run(script):
    out = run_js(_harness(script))
    return json.loads(out.strip().splitlines()[-1])


def test_untouched_color_stays_auto():
    """색 칸에 값이 차 있어도(#RRGGBB는 빈값이 없다) 안 만졌으면 ''로 보낸다."""
    r = _run(r"""
NODES['frTtColor'].value = '#141414';   // 칸의 기본값 — 만진 게 아니다
frUpdate();
const f = STATE.deco.template.frame;
console.log(JSON.stringify({color: f.title_color, olc: f.title_ol_c,
                            olw: f.title_ol_w,
                            url: frameUrl(f).includes('title_color=&')}));
""")
    assert r["color"] == "" and r["olc"] == "" and r["olw"] == 0
    assert r["url"] is True    # URL에도 빈값으로 실려 서버가 자동을 쓴다


def test_touch_sends_color_and_width_label_updates():
    r = _run(r"""
NODES['frTtColor'].value = '#ff0000'; frTouch('ttcolor');
NODES['frTtOlC'].value = '#00ff00'; frTouch('ttol');
NODES['frTtOlW'].value = '6'; frUpdate();
const f = STATE.deco.template.frame;
console.log(JSON.stringify({color: f.title_color, olc: f.title_ol_c, olw: f.title_ol_w,
  label: NODES['frTtOlWV'].textContent,
  url: frameUrl(f)}));
""")
    assert r["color"] == "#ff0000" and r["olc"] == "#00ff00" and r["olw"] == 6
    assert r["label"] == "6px"
    assert "title_color=%23ff0000" in r["url"] and "title_ol_w=6" in r["url"]


def test_reset_clears_title_deco_only():
    """↩ 자동은 제목 꾸미기만 물린다 — 만져둔 띠 색(bar_color)은 그대로 남는다."""
    r = _run(r"""
NODES['frBarColor'].value = '#123456'; frTouch('bar');
NODES['frTtColor'].value = '#ff0000'; frTouch('ttcolor');
NODES['frTtOlW'].value = '6'; frUpdate();
frTtDecoReset();
const f = STATE.deco.template.frame;
console.log(JSON.stringify({color: f.title_color, olw: f.title_ol_w,
  label: NODES['frTtOlWV'].textContent, bar: f.bar_color}));
""")
    assert r["color"] == "" and r["olw"] == 0 and r["label"] == "없음"
    assert r["bar"] == "#123456"   # 틀 색은 안 물러났다


def test_reopen_restores_touched_flags():
    """저장된 작업을 다시 열면(frFill) 값 있는 것만 '만진 것'으로 살아난다 —
    안 살리면 다음 frUpdate가 ''로 밀어 그림이 튄다(bar_color와 같은 규약)."""
    r = _run(r"""
const f = STATE.deco.template.frame;
f.title_color = '#ff0000'; f.title_ol_c = ''; f.title_ol_w = 4;
frFill(f);
frUpdate();     // 다시 읽어도 저장값이 유지되는가
console.log(JSON.stringify({t: FR_TOUCHED.ttcolor, o: FR_TOUCHED.ttol,
  color: f.title_color, olw: f.title_ol_w,
  input: NODES['frTtColor'].value, wlabel: NODES['frTtOlWV'].textContent}));
""")
    assert r["t"] is True and r["o"] is False
    assert r["color"] == "#ff0000" and r["olw"] == 4
    assert r["input"] == "#ff0000" and r["wlabel"] == "4px"
