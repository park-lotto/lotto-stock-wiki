# -*- coding: utf-8 -*-
"""음성 없는 칸에서 미리보기가 첫 단어에 얼어붙던 것 (2026-08-20 사장님 제보).

증상(스크린샷 실측): hook 칸 대본은 "여러분 다이소 가면 이거 무조건 담아오세요."인데
미리보기 자막칸엔 **"여러분"만** 뜨고(컷 1/2에서 정지), 시간도 0:00에서 안 흐르고,
전체 재생은 다음 칸으로 영영 안 넘어갔다.

★근본 원인(코드 실측) — 미리보기의 '시계'가 **두 벌**이다(CLAUDE.md 0순위-B):
    · 화면(컷 진행)  : seqTimer가 컷 길이만큼 setTimeout으로 진행
    · 자막·시간·전체재생: audio().currentTime / audio.onended
  음성이 있으면 둘이 대충 맞지만, 음성이 없으면(합성 전 404 · 대본 바뀜 409)
  <audio>는 시간이 영영 0이고 ended도 영영 안 온다 →
    자막 = capAt(t=0) = 첫 구절만 / 시간 = 0:00 고정 / 전체재생 = 그 칸에서 정지.
  화면(영상)만 자기 타이머로 계속 돌아 "대본이 적용 안 된 것"처럼 보였다.

계약: 시계 판단은 audioUsable() **한 곳**. 음성을 시계로 못 쓰면(=src 없음·error·
길이 미상) 화면(컷 진행) 시계로 폴백한다 — curT()·tickSub()·전체재생 넘김 전부.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")

# 파일 전체를 그대로 싣는다(조각 추출은 개행 하나에도 깨진다). DOM만 최소로 스텁.
_STUB = r"""
function _mkel(id){
  return { id, style:{}, classList:{add(){},remove(){},contains(){return false}},
    innerHTML:'', textContent:'', value:0,
    appendChild(){}, querySelector(){return null},
    setAttribute(){}, getAttribute(){return null},
    parentNode:{insertBefore(){}},
    pause(){}, play(){ return {catch(){}}; }, load(){}, onended:null };
}
const _els = {};
const document = {
  getElementById(id){ return _els[id] || (_els[id] = _mkel(id)); },
  addEventListener(){}, createElement(t){ return _mkel('new:'+t); },
  querySelectorAll(){ return []; },
  documentElement:{ style:{ setProperty(){} } },
};
const window = { addEventListener(){} };
function esc(t){ return String(t==null?'':t); }
// 죽은 음성(합성 전 404 / 대본 바뀜 409): error 있음, duration 미상, 시간 0에서 영영 안 흐름.
function _deadAudio(){
  const a = _els['bgaudio'] = _mkel('bgaudio');
  a.src='x'; a.error={code:4}; a.duration=NaN;
  a.currentTime=0; a.paused=true; a.ended=false;
  return a;
}
"""


def _run(body):
    code = _STUB + JS.read_text(encoding="utf-8") + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, (r.stderr or r.stdout)
    return r.stdout.strip().splitlines()


def test_음성이_죽어도_시계는_화면을_따라간다():
    """옛 코드: curT()가 무조건 audio().currentTime → 0:00에 고정(사장님 스크린샷)."""
    out = _run("""
_deadAudio();
seqBeat = 0;
seq = [{video_id:'v',start:10,dur:2},{video_id:'v',start:10.5,dur:2}];
seqBounds = [[0,2],[2,4]];
seqI = 1;
curVid = {currentTime:11.0, pause(){}, play(){return{catch(){}}}};
console.log('T=' + curT().toFixed(2));
""")
    assert out[-1] == "T=2.50", f"화면은 2.5초인데 시계가 {out[-1]} — 음성 0초에 얼어붙었다"


def test_음성이_죽어도_자막이_다음_구절로_넘어간다():
    """옛 코드: 자막이 audio 시각(0초)만 봐서 '여러분'에서 영영 멈췄다."""
    out = _run("""
_deadAudio();
DATA = {captions:{'0':[
    {text:'여러분', start:0, end:1.2},
    {text:'다이소 가면 이거 무조건 담아오세요', start:1.2, end:3.7}]},
  beats:[{}]};
seqBeat = 0;
seq = [{video_id:'v',start:10,dur:2},{video_id:'v',start:10.5,dur:2}];
seqBounds = [[0,2],[2,4]];
seqI = 1;                      // 화면은 이미 컷 2
curVid = {currentTime:11.0, pause(){}, play(){return{catch(){}}}};
tickSub();
setTimeout(() => {
  clearInterval(subTimer);
  const html = _els['subbox'].innerHTML;
  console.log(html.indexOf('다이소') >= 0 ? 'SUB=OK' : 'SUB=STUCK ' + JSON.stringify(html));
}, 250);
""")
    assert out[-1] == "SUB=OK", f"자막이 첫 구절에 얼어붙었다: {out[-1]}"


def test_음성이_죽어도_전체재생이_다음_칸으로_넘어간다():
    """옛 코드: 다음 칸 넘김이 audio.onended뿐 → 음성 없는 칸에서 영영 정지."""
    out = _run("""
_deadAudio();
DATA = {captions:{}, beats:[{}]};      // 칸 1개 — 넘어가면 곧장 완주(stopPlay → playKey=null)
playKey = 'all';
seqBeat = 0;
seqLabel = '전체 재생';
seq = [{video_id:'v',start:0,dur:1}];
seqBounds = [[0,1]];
seqI = 1;                              // 이 칸의 컷이 다 끝난 상태
curVid = {currentTime:1.0, pause(){}, play(){return{catch(){}}}};
step();                                // 옛 코드는 여기서 아무것도 안 하고 멈춘다
setTimeout(() => { console.log(playKey === null ? 'ADV=OK' : 'ADV=STUCK'); }, 700);
""")
    assert out[-1] == "ADV=OK", "음성 없는 칸에서 전체 재생이 다음 칸으로 못 넘어간다"


def test_시계판단은_한_곳이다():
    """audioUsable() 없이 a.currentTime을 직접 시계로 쓰면 두 벌이 또 생긴다(0순위-B)."""
    src = JS.read_text(encoding="utf-8")
    assert re.search(r"function audioUsable\(", src), "audioUsable()이 없다 — 시계 판단처 실종"
    m = re.search(r"function tickSub\(\)\{.*?\n\}", src, re.S)
    assert m, "tickSub을 못 찾았다"
    assert "curT()" in m.group(0), "tickSub이 공용 시계(curT)를 안 쓴다 — 자막만 딴 시계"
