"""1단계 미리보기 게이트 — 미리보기 전엔 '다음'이 안 열린다(스펙 §5·§7).

사장님 지적: "미리보기를 안 해보고 넘길 수는 있는데 상식적으로 잘 되었는지 뭘 보고
그걸 다음 단계로 넘기겠나. 돈 내고 만드는 사람들인데."
다음 단계(자막제거)가 VMake 유료 API라, 못 본 채 넘어가면 그 돈이 날아간다.

produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다
(test_produce_pm_gen_race.py·test_produce_mix_regen.py와 같은 방식 — 재구현이 아니다).
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_START = "// ── 1단계 미리보기"
_END = "// ── 3단계 자막제거"

_HARNESS = r"""
'use strict';
function el(){ return { style:{}, innerHTML:'', textContent:'', disabled:false, title:'',
                        classList:{add(){},remove(){},toggle(){}} }; }
const _els = { mixPreview: el(), btnNext: el(), mixState: el() };
const document = { getElementById(id){ return _els[id] || null; }, querySelector(){ return null; },
                   querySelectorAll(){ return []; } };
function esc(s){ return s; }
// ⚠️ PREVIEW_STATUS·PREVIEW_POLL은 여기서 선언하지 마라 — 아래 실제 소스가 let으로 선언하므로
// 중복 선언이 되어 SyntaxError로 죽는다. 슬라이스 밖 심볼만 여기서 준다.
var cur = 0;
var MIX_JOB = 'J1';
function fetch(){ return Promise.reject(new Error('이 테스트는 네트워크를 안 탄다')); }
function setInterval(){ return 0; }
function clearInterval(){}
// ---- 여기부터 produce.html 실제 소스 ----
"""

_SCENARIO_GATE = r"""
(() => {
  const fails = [];
  PREVIEW_STATUS = null;
  if (canGoNext() !== false) fails.push('미리보기 전인데 다음이 열려 있다 — 유료 자막제거로 그냥 넘어간다');
  PREVIEW_STATUS = 'rendering';
  if (canGoNext() !== false) fails.push('렌더 중인데 다음이 열려 있다');
  PREVIEW_STATUS = 'ready';
  if (canGoNext() !== true) fails.push('미리보기가 나왔는데도 다음이 잠겨 있다 — 진행 불가');
  PREVIEW_STATUS = 'failed';
  if (canGoNext() !== true) fails.push('렌더 실패인데 탈출구가 없다 — ffmpeg 문제 하나로 갇힌다(스펙 §7.1)');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})();
"""

_SCENARIO_BTN = r"""
(() => {
  const fails = [];
  const b = document.getElementById('btnNext');
  PREVIEW_STATUS = null;  cur = 0;  refreshNextBtn();
  if (b.disabled !== true) fails.push('1단계·미리보기 전인데 btnNext가 안 잠겼다');
  if (!String(b.title || '').trim()) fails.push('왜 잠겼는지 안내(title)가 없다');
  PREVIEW_STATUS = 'ready'; refreshNextBtn();
  if (b.disabled !== false) fails.push('미리보기 후에도 btnNext가 잠겨 있다');
  // 다른 단계에선 이 게이트가 끼어들면 안 된다
  PREVIEW_STATUS = null; cur = 2; refreshNextBtn();
  if (b.disabled !== false) fails.push('3단계인데 1단계 게이트가 다음을 잠갔다');
  if (fails.length) { console.error('FAIL: ' + fails.join(' / ')); process.exit(1); }
  console.log('PASS');
})();
"""


def _src():
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    s, e = text.find(_START), text.find(_END)
    assert s != -1, f"START 못 찾음(produce.html이 바뀌었나): {_START!r}"
    assert e != -1 and e > s, f"END 못 찾음: {_END!r}"
    return text[s:e]


def _run(scenario, tmp_path):
    f = tmp_path / "probe_preview_gate.js"
    f.write_text(_HARNESS + _src() + scenario, encoding="utf-8")
    return subprocess.run([NODE, str(f)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=30)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_next_gated_until_preview_ready(tmp_path):
    r = _run(_SCENARIO_GATE, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 하네스 스킵")
def test_next_button_disabled_state(tmp_path):
    r = _run(_SCENARIO_BTN, tmp_path)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "PASS" in r.stdout


def test_preview_video_is_muted_by_default():
    """★사장님 지시: 음소거가 기본값. 열면 조용하고, 원하면 켠다(스펙 §4.2)."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    i = html.find("mix/preview/")
    assert i != -1, "미리보기 <video>가 없다"
    tag = html[max(0, i - 300): i + 100]
    assert "muted" in tag, f"미리보기 video에 muted가 없다 — 열자마자 소리가 난다: {tag[-160:]!r}"
    assert "controls" in tag, "controls가 없다 — 음소거 해제·탐색을 못 한다"


def test_preview_url_has_cache_buster():
    """대본을 고쳐 재매칭하면 같은 URL에 다른 영상이 온다 — 캐시버스터가 없으면 옛 걸 본다."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    i = html.find("mix/preview/")
    tag = html[i: i + 200]
    assert "?t=" in tag, f"미리보기 URL에 캐시버스터가 없다 — 브라우저가 옛 영상을 재사용한다: {tag[:120]!r}"


def test_go_has_gate_guard():
    """disabled만으론 부족 — go(1)이 다른 경로로 불릴 수 있다(방어 두 겹)."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    i = html.find("function go(d){")
    assert i != -1, "go() 못 찾음"
    body = html[i: i + 320]
    assert "canGoNext()" in body, f"go()에 게이트 가드가 없다: {body[:180]!r}"


def test_stale_review_hint_is_gone():
    """옛 안내문이 남아 있으면 화면이 거짓말을 한다(스펙 §7)."""
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "마지막에 렌더합니다" not in html, \
        "'마지막에 렌더합니다' 안내가 남아 있다 — 이제 1단계에서 미리보기를 렌더한다"
