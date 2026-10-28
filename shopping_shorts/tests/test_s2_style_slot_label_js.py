# -*- coding: utf-8 -*-
"""고른 스타일 카드의 '안' 뱃지는 **실제로 나오는 자리**를 가리켜야 한다 (2026-09-23 사장님
"두 개를 선택했는데 한 개는 씨앗으로 자동 가고 한 개는 어떤 게 선택되는 건가").

이야기 작가(story_writer)가 켜지면 서버 make_drafts가 **씨앗 자동안을 늘 A칸에** 만들고
고른 스타일은 `spines[:1]` 한 개만 쓴다. 그런데 화면은 고른 순서만 세어 첫 카드에 'A안'을
붙였다 — 실제 A안은 씨앗이라 어느 카드가 만들어진 건지 알 수 없었고, 'B안' 뱃지가 붙은
두 번째 카드는 **아무것도 안 만들었다**(조용히 버려짐).
여기서는 뱃지 계산식과 상한(s2AnCount)을 뽑아 돌려 자리와 상한을 함께 검사한다."""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

HTML = Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _run(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(js)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8",
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, (r.stderr or r.stdout)
    return json.loads(r.stdout.strip())


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_씨앗자동이_A칸이면_첫_고른_카드는_B안():
    src = HTML.read_text(encoding="utf-8")
    off = re.search(r"^\s*const _slotOff=.*$", src, re.M)
    nth = re.search(r"^\s*const nth=on\?.*$", src, re.M)
    cnt = re.search(r"^function s2AnCount\(\).*$", src, re.M)
    assert off and nth and cnt, "뱃지 자리 계산식을 못 찾음"
    pre = """
let S2={picked:[71,73], usePickup:false};
function _s2SeedAuto(){ return SEED_AUTO; }
"""
    body = ("var SEED_AUTO=true;\n" + pre + cnt.group(0) + """
function label(id){ const st={id}; const on=S2.picked.indexOf(st.id)>=0;
""" + off.group(0) + "\n" + nth.group(0) + """
  return nth; }
const out={first:label(71), second:label(73), want:s2AnCount()};
S2.picked=[71];
out.oneWant=s2AnCount();
console.log(JSON.stringify(out));
""")
    d = _run(body)
    assert d["first"].endswith("B안"), "씨앗이 A칸이니 첫 고른 카드는 B안이어야 한다(실제 결과와 같은 자리)"
    assert d["oneWant"] == 2, "씨앗 자동 1안 + 고른 1개 = 2안"
    assert d["want"] >= 3, "2개를 고르면 상한(2안)을 넘는다 — s2ToggleStyle이 막아야 한다"


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_씨앗자동_꺼지면_종전대로_A안():
    src = HTML.read_text(encoding="utf-8")
    off = re.search(r"^\s*const _slotOff=.*$", src, re.M)
    nth = re.search(r"^\s*const nth=on\?.*$", src, re.M)
    body = ("var SEED_AUTO=false;\nlet S2={picked:[71,73], usePickup:false};\n"
            "function _s2SeedAuto(){ return SEED_AUTO; }\n"
            "function label(id){ const st={id}; const on=S2.picked.indexOf(st.id)>=0;\n"
            + off.group(0) + "\n" + nth.group(0) + "\n  return nth; }\n"
            "console.log(JSON.stringify({first:label(71), second:label(73)}));")
    d = _run(body)
    assert d["first"].endswith("A안") and d["second"].endswith("B안"), "스위치가 꺼지면 종전 그대로"
