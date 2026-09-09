# -*- coding: utf-8 -*-
"""꾸미기 미리보기 — 자막은 흘러가는데 장면이 첫 화면에 고정되던 것 (2026-09-01 고객 제보).

제보: work=ef57df4ea9c3(임영미) "자막은 흘러가는데 장면이 첫화면 고정".
실측(서버 /api/produce/mix/beats_preview/017632d42939): 목록은 **컷 단위로 펴져** 있고
(칸1=4컷, 칸2=5컷, 칸3=7컷) 각 컷이 그 칸의 자막 구절 **전체**를 들고 있다.
그런데 _playBeatCaptions는 자막만 돌리고 배경(#hcPreviewBg)은 showBeat이 한 번 깐 뒤
그대로였다 → 자막만 흐르고 화면은 첫 컷에 고정.

계약: 구절이 넘어가면 배경도 그 구절의 컷으로 같이 넘어간다("보는 것 = 나오는 것").
      컷 수 = 구절 수면 1:1, 어긋나면 비례로 고른다.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _slice():
    """호출부 형태 그대로 쓰려고 실제 코드 조각을 잘라 온다(계약을 발명하지 않는다)."""
    a = HTML.index("let CAP_SEQ_TIMER=null;")
    b = HTML.index("function stepBeat(d){", a)
    b = HTML.index("\n}", b) + 2
    return HTML[a:b]


_STUB = r"""
const _bg = {_src:null, style:{display:'none'},
             set src(v){ this._src=v; this.style.display='block'; _SEEN.push(v); },
             get src(){ return this._src; },
             getAttribute(){ return this._src; }};
const _SEEN = [];
const _cnt = {textContent:''};
const document = { getElementById(id){
  return id==='hcPreviewBg' ? _bg : (id==='sceneBg' ? {checked:true} : (id==='beatCount' ? _cnt : null));
}};
let PREVIEW_CAP_TEXT='';
let BEAT_IDX=0;
let BEATS_PREVIEW=[];
function _beatNo(b){ return (b && b.beat_idx!=null) ? b.beat_idx : BEAT_IDX; }
function _beatFrameUrl(b){ return '/f/'+b.beat_idx+'-'+b.cut; }
function updateCaption(){}
function showBeat(i){ BEAT_IDX=i; }
"""


def _run(body):
    code = _STUB + _slice() + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, (r.stderr or r.stdout)
    return r.stdout.strip().splitlines()


_MAKE = """
// 칸1(beat_idx=1) 4컷 · 구절 4개 — 서버 실응답과 같은 모양(컷마다 segs 전체를 들고 있다)
const segs=['가','나','다','라'];
BEATS_PREVIEW=[{beat_idx:0,cut:0,cut_of:1,segs:['훅'],durs:[0.5]}];
for(let c=0;c<4;c++) BEATS_PREVIEW.push({beat_idx:1,cut:c,cut_of:4,segs,durs:[0.5,0.5,0.5,0.5]});
BEATS_PREVIEW.push({beat_idx:2,cut:0,cut_of:1,segs:['끝'],durs:[0.5]});
BEAT_IDX=1;                       // 칸1의 첫 컷
"""


def test_구절이_넘어가면_장면도_같이_넘어간다():
    out = _run(_MAKE + """
_playBeatCaptions(BEATS_PREVIEW[BEAT_IDX]);
setTimeout(()=>{ clearTimeout(CAP_SEQ_TIMER);
  console.log('SEEN=' + JSON.stringify(_SEEN.slice(0,4)));
}, 1700);
""")
    seen = out[-1]
    assert seen == 'SEEN=["/f/1-0","/f/1-1","/f/1-2","/f/1-3"]', \
        f"장면이 첫 컷에 고정됐다(또는 순서가 틀렸다): {seen}"


def test_컷수와_구절수가_다르면_시간으로_고른다():
    """사장님 3단계 대조 지적(2026-09-01): 컷 5개(1.2/0.9/0.9/0.9/0.6)에 구절 4개(0.9씩).
    개수 비례면 구절2가 컷1로 가지만, 시간축으론 구절2 시작 0.9초는 아직 **컷0**(0~1.2초)이다."""
    out = _run("""
const segs=['예측 못 한','반전 기능으로','개떡상한 움직이는','기차 케이크임'];
const durs=[0.9,0.9,0.9,0.6];
const cd=[1.2,0.9,0.9,0.9,0.6];
BEATS_PREVIEW=[];
for(let c=0;c<5;c++) BEATS_PREVIEW.push({beat_idx:1,cut:c,cut_of:5,segs,durs,lead:0,cut_dur:cd[c]});
BEAT_IDX=0;
_playBeatCaptions(BEATS_PREVIEW[0]);
setTimeout(()=>{ clearTimeout(CAP_SEQ_TIMER);
  console.log('SEEN=' + JSON.stringify(_SEEN.slice(0,4)));
}, 3300);
""")
    # 구절 시작 0 / 0.9 / 1.8 / 2.7  ↔  컷 경계 1.2 / 2.1 / 3.0 / 3.9 / 4.5
    assert out[-1] == 'SEEN=["/f/1-0","/f/1-1","/f/1-2"]',         f"3단계 컷 시간축과 안 맞는다: {out[-1]}"


def test_구절보다_컷이_적으면_비례로_고른다():
    """컷 2개 · 구절 4개 — 앞 두 구절은 컷0, 뒤 두 구절은 컷1."""
    out = _run("""
const segs=['가','나','다','라'];
BEATS_PREVIEW=[];
for(let c=0;c<2;c++) BEATS_PREVIEW.push({beat_idx:1,cut:c,cut_of:2,segs,durs:[0.5,0.5,0.5,0.5]});
BEAT_IDX=0;
_playBeatCaptions(BEATS_PREVIEW[0]);
setTimeout(()=>{ clearTimeout(CAP_SEQ_TIMER);
  console.log('SEEN=' + JSON.stringify(_SEEN.slice(0,4)));
}, 1700);
""")
    assert out[-1] == 'SEEN=["/f/1-0","/f/1-1"]', out[-1]


def test_좌우_화살표는_컷_한장씩_넘긴다():
    """2026-09-03 사장님: "1장씩 넘어가야 하는데 단락별로 3~4장씩 넘어간다".
    칸 단위(2026-09-01)로 묶었더니 한 번 누를 때 그 칸의 컷 3~4개를 통째로 건너뛰었다."""
    out = _run(_MAKE + """
clearTimeout(CAP_SEQ_TIMER);
BEAT_IDX=2;                 // 칸1의 두 번째 컷을 보는 중
stepBeat(1);  console.log('NEXT=' + BEAT_IDX);      // 바로 다음 컷
BEAT_IDX=3;
stepBeat(-1); console.log('PREV=' + BEAT_IDX);      // 바로 앞 컷
console.log('SEEN=' + JSON.stringify(_SEEN.slice(-2)));
console.log('PAUSED=' + CAP_PAUSED);                // 수동으로 넘기면 자동흐름은 멈춘다
""")
    assert out[0] == "NEXT=3", out[0]
    assert out[1] == "PREV=2", out[1]
    # 넘긴 그 컷의 그림을 **즉시** 그린다(미리받기를 기다리지 않는다)
    assert out[2] == 'SEEN=["/f/1-2","/f/1-1"]', out[2]
    assert out[3] == "PAUSED=true", out[3]
