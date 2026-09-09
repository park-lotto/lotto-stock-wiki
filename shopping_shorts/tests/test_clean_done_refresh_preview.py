# -*- coding: utf-8 -*-
"""자막제거가 끝나면 **꾸미기(5단계) 미리보기 배경**도 청소본으로 바뀌는가.

2026-09-06 사장님 질문 "자막제거 동안 장면꾸미기를 하면 어떻게 되나 / 새로고침하나".

라이브 실측(job feeb174bf50a, cid 268 정종수):
  같은 job 안에 poster가 **두 판본**으로 저장돼 있었다 —
    poster_s3@0.03.jpg        자막 "다이소가면"·워터마크 "@템캣"·"[광고]" 있음
    poster_s3@0.03_clean.jpg  전부 지워짐
  서버는 청소가 끝나면 _clean_frame_src가 ctag='_clean'을 주므로, **다시 요청만 하면**
  깨끗한 판본을 준다. 그런데 화면이 그 요청을 다시 보내지 않았다:

    pollClean의 clean_status==='ready' 분기는 renderCleanReady(3단계)만 다시 그린다.
    5단계 배경(hcPreviewBg)을 갱신하는 toggleSceneBg()는 **initHeadcopy(5단계 진입)**
    에서만 불린다 → 5단계에 머문 채 청소가 끝나면 자막이 그대로 보인다.

  ★고객은 이것을 "자막제거가 안 됐다"로 읽고 다시 누른다. VMake는 유료 API다 —
    이 job은 clean 작업이 **13번** 실행됐다(06:05~06:29, 큐 qid 11485~11516).

여기서 못 박는 것: 청소 완료 시 5단계 배경·자막정렬이 자동으로 다시 걸린다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "async function pollClean(gen,job){"
_END = "// 자막제거 실패 안내"

# 화면 전체를 흉내내지 않는다 — pollClean이 부르는 것만 스텁으로 세우고
# **무엇을 불렀는지** 기록한다(호출됐나가 판정이지 그림이 아니다).
_HARNESS = r"""
'use strict';
const CALLED = [];
let CLEAN_GEN = 1, MIX_JOB = 'j1', CLEAN_POLL = 1;
let CLEAN_REGIONS = null, CLEAN_SRC_N = 0, CLEAN_SRC_IDX = null, CLEAN_CLIPS_JOB = 'j1';
global.clearInterval = () => { CLEAN_POLL = null; };
global.document = { getElementById: () => null };
global.fetch = async () => ({ json: async () => PAYLOAD });
function renderCleanReady(){ CALLED.push('renderCleanReady'); }
function updateCleanProgress(){ CALLED.push('updateCleanProgress'); }
function cleanFailHtml(){ CALLED.push('cleanFailHtml'); return ''; }
function startCleanPreview(){}
// ★이 둘이 5단계 미리보기를 되살리는 손잡이다
function toggleSceneBg(){ CALLED.push('toggleSceneBg'); }
function ensureCleanRegions(){ CALLED.push('ensureCleanRegions'); }
"""

_DRIVER = r"""
(async () => { await pollClean(1, 'j1');
  console.log(JSON.stringify({called: CALLED, regions: CLEAN_REGIONS})); })();
"""


def _run(tmp_path, payload):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    frag = src[src.index(_START):src.index(_END)]
    js = tmp_path / "t.js"
    js.write_text("const PAYLOAD = " + json.dumps(payload) + ";\n"
                  + _HARNESS + frag + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


_READY = {"clean_status": "ready", "clean_regions": {"primary": {"x_pct": 50, "y_pct": 80}},
          "clean_source_count": 3}


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_청소가_끝나면_꾸미기_배경을_다시_받는다(tmp_path):
    """★이게 없으면 5단계에 머문 고객은 자막이 남은 옛 배경을 계속 본다."""
    got = _run(tmp_path, _READY)
    assert "toggleSceneBg" in got["called"], (
        "청소 완료인데 5단계 배경을 다시 안 받는다 — 고객은 자막이 그대로 보여 "
        f"자막제거를 다시 누른다(유료 API). 호출된 것: {got['called']}")


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_청소가_끝나면_자막_자동정렬도_다시_건다(tmp_path):
    """지워진 자막 자리(clean_regions)에 새 자막을 놓아주는 처리도 같이 걸려야 한다."""
    got = _run(tmp_path, _READY)
    assert "ensureCleanRegions" in got["called"], got["called"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_3단계_화면_갱신은_그대로다(tmp_path):
    """회귀 방지 — 기존 동작(컷 목록 다시 그리기)을 건드리지 않는다."""
    got = _run(tmp_path, _READY)
    assert "renderCleanReady" in got["called"], got["called"]
    assert got["regions"] == _READY["clean_regions"], got["regions"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_아직_도는_중이면_배경을_안_건드린다(tmp_path):
    """★cleaning일 때 배경을 갈면 아직 자막이 남은 그림을 헛되이 다시 받는다.

    진행 표시만 갱신하고 끝나야 한다(불필요한 요청 + 깜빡임 방지).
    """
    got = _run(tmp_path, {"clean_status": "cleaning", "clean_done": 1, "clean_source_count": 3})
    assert "updateCleanProgress" in got["called"], got["called"]
    assert "toggleSceneBg" not in got["called"], f"도는 중엔 배경을 건드리면 안 된다: {got['called']}"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_실패했으면_배경을_안_건드린다(tmp_path):
    """실패인데 배경을 갈면 '되지도 않았는데 뭔가 바뀐' 착시를 준다."""
    got = _run(tmp_path, {"clean_status": "failed", "clean_error_kind": "need_own_key"})
    assert "toggleSceneBg" not in got["called"], got["called"]
