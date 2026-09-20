# -*- coding: utf-8 -*-
"""없는 조각이 '0-0 · 0.0'으로 조용히 그려지지 않는가 (2026-09-05).

사장님 캡처의 지문이 정확히 이것이었다 — 띠는 '장면 없음'인데 아래엔 배지 `0-0`,
길이 `0.0`짜리 '안 나옴' 카드. `srcNo()`·`segNo()`는 `DATA.segments[sid]`가 없을 때만
0을 주므로(scene_lab.html), `0-0`은 **조각이 통째로 없다**는 뜻이다.

★문자열 검색이 아니라 **그 자리 JS를 실제로 실행해서** 판정한다 — 마크업 테스트를
  문자열로 하면 리팩터링에 조용히 빈 단언이 된다(메모리: 마크업테스트_문자열검색_무용지물).
  이 하네스는 사보타주(gone=false, 옛 동작)로 **빨개지는 것을 확인**하고 넣었다.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_HTML = Path(__file__).resolve().parents[1] / "static" / "scene_lab.html"

_HARNESS = r"""
const fs=require('fs');
const slice=fs.readFileSync(process.argv[2],'utf8');
const DATA={segments:{'s0-1':{video_id:'s0',start:2,end:4.5,label:'x'}}};
const lists=[['s0-1','film_s0_7.20_9.80']];   // 두 번째 = 서버가 모르는 조각
const i=0, clips=[];
const isPicked=()=>false, tooShort=()=>false;
const effLen=(id)=>{const s=DATA.segments[id];return s?s.end-s.start:0;};
const srcNo=(id)=>DATA.segments[id]?1:0, segNo=(id)=>DATA.segments[id]?1:0;
const segMark=(id)=>srcNo(id)+'-'+segNo(id);
const SL={thumb:(id)=>'/t/'+id};
let unusedCuts;
eval(slice.replace('const unusedCuts','unusedCuts'));
console.log(JSON.stringify({
  cards:(unusedCuts.match(/class="tbcut unused/g)||[]).length,
  zeroBadge:/class="n">0-0</.test(unusedCuts),
  zeroLen:/class="s">0\.0</.test(unusedCuts),
  saysGone:/조각 없음/.test(unusedCuts),
}));
"""


def _slice_src():
    s = _HTML.read_text(encoding="utf-8")
    i = s.find("const usedIds = new Set(")
    j = s.find("}).join('');", i)
    assert i > 0 and j > i, "renderBand의 '안 나옴' 구간을 못 찾았다 — 코드가 옮겨졌나?"
    return s[i:j + len("}).join('');")]


def _run(tmp_path, src):
    # ★node -e 로 넘기지 않는다 — 윈도우 명령줄 상한(32,767자)에 걸린다(전례 있음).
    js = tmp_path / "slice.js"
    js.write_text(src, encoding="utf-8")
    h = tmp_path / "h.js"
    h.write_text(_HARNESS, encoding="utf-8")
    r = subprocess.run([shutil.which("node") or "node", str(h), str(js)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, f"하네스 실행 실패: {r.stderr[:400]}"
    import json
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_missing_seg_not_drawn_as_zero_zero(tmp_path):
    """없는 조각은 '0-0 · 0.0'이 아니라 이유를 말해야 한다."""
    got = _run(tmp_path, _slice_src())
    assert got["cards"] == 2, got
    assert not got["zeroBadge"], "배지가 '0-0' — 없는 조각이 정상 카드처럼 그려진다"
    assert not got["zeroLen"], "길이가 '0.0' — 없는 조각이 정상 카드처럼 그려진다"
    assert got["saysGone"], "없어진 조각인데 화면이 그 사실을 안 알린다"


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_harness_catches_old_behavior(tmp_path):
    """★사보타주: 옛 동작(gone 판정 없음)이면 반드시 빨개져야 한다.

    이게 실패하면 위 테스트는 **아무것도 안 지키는 빈 단언**이다.
    """
    old = _slice_src().replace("const gone = !DATA.segments[id];", "const gone = false;")
    assert "const gone = false;" in old, "사보타주 지점을 못 찾았다 — 테스트가 무력화됐다"
    got = _run(tmp_path, old)
    assert got["zeroBadge"] and got["zeroLen"], (
        "옛 동작인데도 0-0이 안 나온다 — 하네스가 증상을 못 잡는다(가짜 green)")
