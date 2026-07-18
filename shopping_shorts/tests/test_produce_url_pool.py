"""URL 영상풀 — 확정(카드로 담기)·삭제(2026-07-18 사장님 요청).

사장님: "url을 몇개 넣은뒤 추가이후 저장이나 확정버튼을 만들어줘" + "링크 넣었다가 삭제할때
기능없음" + 이미지로 왼쪽 영상풀(빈 박스)에 카드로 '잘 보이게'.

★설계: 카드(HANDOFF useFootage)가 진실의 원천. #mixUrls는 '새 URL 타이핑' 전용이고,
믹스는 collectMixUrls()로 카드+입력칸을 합쳐 읽는다(이중표시 제거). 확정=입력칸 URL을
useFootage:true 카드로 올려 바로 믹스 가능하게 한다.

DOM-heavy 함수(innerHTML 렌더)는 라이브 브라우저로 검증하고, 여기선 데이터 계약을 잠근다.
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")

_START = "function removeFootage(i){"
_END = "// 📝뽑기: 영상 i의 대본을 확보"
_COLLECT_START = "function collectMixUrls(){"
_COLLECT_END = "// 📝뽑기: 영상 i의 대본을 확보"


def _slice(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


# 실제 소스의 removeFootage/confirmMixUrls/removeMixUrlRow + collectMixUrls를 잘라 온다.
def _funcs():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return _slice(src, _START, _END) + "\n" + _slice(src, _COLLECT_START, _COLLECT_END)


_HARNESS = r"""
'use strict';
let HANDOFF = [];
function esc(s){ return String(s); }
function renderPool(){}
function refreshFinalPeek(){}
function saveWork(){}
// #mixUrls DOM 스텁: 입력칸 값 배열을 흉내낸다.
let _typedRows = [];   // [{value}]
let _statusText = '';
const _mixUrlsEl = {
  querySelectorAll(sel){ return _typedRows; },   // '.mixUrl'
  set innerHTML(v){ _typedRows = [{value:''}]; },   // 확정 후 빈 칸 하나로
  querySelector(){ return _typedRows[0]; },
};
const document = {
  getElementById(id){
    if(id === 'mixUrls') return _mixUrlsEl;
    if(id === 'footageList') return {textContent:''};
    if(id === 'mixStatus') return {set textContent(v){ _statusText = v; }, get textContent(){ return _statusText; }};
    return null;
  },
  querySelectorAll(sel){ return _typedRows; },   // collectMixUrls의 .mixUrl
};
function syncFootageToMixUrls(){}
"""


def _run(body):
    js = _HARNESS + _funcs() + "\n(async()=>{\n" + body + "\n})();"
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30,
                       encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_confirm_delete_collect_all_scenarios():
    """확정·삭제·믹스소스 4시나리오를 **한 node 프로세스**에서(윈도우 subprocess 핸들 고갈 회피 —
    격리는 통과인데 전체 실행에서 WinError로 무더기 실패하던 것):

    ① 확정: 입력칸 URL들이 영상풀 카드(useFootage:true)로 올라가고 입력칸은 비워진다(이미지 핵심).
    ② 확정 중복제거: 이미 풀에 있는 URL은 또 안 담는다.
    ③ 삭제: removeFootage(i)가 그 카드를 뺀다('삭제 기능없음' 제보 해소).
    ④ 믹스 소스 = 담긴 카드 + 입력칸에 남은 것, 중복 제거(collectMixUrls). 담기 안 한 카드는 제외.
    """
    out = _run("""
      function reset(){ HANDOFF=[]; _typedRows=[]; }
      const r = {};
      // ① 확정
      reset(); _typedRows=[{value:'https://a/1'},{value:'https://b/2'}]; confirmMixUrls();
      r.confirm = {n:HANDOFF.length, urls:HANDOFF.map(h=>h.url),
                   allFootage:HANDOFF.every(h=>h.useFootage===true), typed:_typedRows.map(x=>x.value)};
      // ② 확정 중복제거
      reset(); HANDOFF=[{url:'https://a/1', useFootage:true}]; _typedRows=[{value:'https://a/1'},{value:'https://c/3'}];
      confirmMixUrls(); r.dedupe = {n:HANDOFF.length, urls:HANDOFF.map(h=>h.url)};
      // ③ 삭제
      reset(); HANDOFF=[{url:'https://a/1',useFootage:true},{url:'https://b/2',useFootage:true}];
      removeFootage(0); r.del = {n:HANDOFF.length, left:HANDOFF.map(h=>h.url)};
      // ④ collectMixUrls
      reset(); HANDOFF=[{url:'https://a/1',useFootage:true},{url:'https://x/9',useFootage:false}];
      _typedRows=[{value:'https://b/2'},{value:'https://a/1'}];
      r.collect = collectMixUrls();
      console.log(JSON.stringify(r));
    """)
    import json
    r = json.loads(out)
    # ①
    assert r["confirm"]["n"] == 2, f"①확정 카드 2개 아님: {out}"
    assert set(r["confirm"]["urls"]) == {"https://a/1", "https://b/2"}, out
    assert r["confirm"]["allFootage"] is True, f"①확정 URL이 useFootage:true 아님 — 바로 믹스 못 함: {out}"
    assert r["confirm"]["typed"] == [""], f"①확정 후 입력칸 안 비워짐: {out}"
    # ②
    assert r["dedupe"]["n"] == 2 and "https://c/3" in r["dedupe"]["urls"], f"②중복 URL 또 담김: {out}"
    # ③
    assert r["del"]["n"] == 1 and r["del"]["left"] == ["https://b/2"], f"③삭제가 엉뚱: {out}"
    # ④
    assert "https://a/1" in r["collect"] and "https://b/2" in r["collect"], f"④입력칸 URL 누락: {out}"
    assert "https://x/9" not in r["collect"], f"④담기 안 한 카드가 믹스에 섞임: {out}"
    assert r["collect"].count("https://a/1") == 1, f"④중복 제거 안 됨: {out}"
