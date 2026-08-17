# -*- coding: utf-8 -*-
"""합친 조각이 재생될 때 3장이 다 나오게 한다(2026-08-17 사장님 제보).

증상: 3장을 합쳐 훅 칸에 넣었는데 맨 앞장만 재생됐다.
원인: mergeSpan이 합치기를 **한 개의 긴 구간**으로 만들고(길이·트림 판단을 한 벌로
두려는 의도), planClips는 구간이 하나면 앞에서부터 칸 길이만큼만 쓴다 → 8초를 합쳐
5초 칸에 넣으면 첫 조각만 보인다.
처방: 재생 계획에 넘기기 전에 멤버 경계로 되가른다. 나누는 규칙(planClips)은 안 건드린다.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _harness(body):
    src = JS.read_text(encoding="utf-8")
    keep = []
    for name in ("const EPS", "const TRIMS", "const MERGES", "function mergeSpan",
                 "function mergeParts", "function splitByMembers", "function trimPieces"):
        m = re.search(re.escape(name) + r".*?(?=\n(?:const |let |function |//))", src, re.S)
        if m:
            keep.append(m.group(0))
    pre = "const EPS=0.05; const DATA={segments:{}};\n"
    code = pre + "\n".join(k for k in keep if not k.startswith("const EPS")) + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True)
    assert r.returncode == 0, (r.stderr or r.stdout)
    return r.stdout.strip()


def test_합친_3장이_3조각으로_갈라진다():
    """한 덩어리로 두면 planClips가 앞부분만 쓴다 — 이게 '맨 앞장만 재생'의 정체다."""
    out = _harness("""
DATA.segments = {a:{start:2.0,end:6.4}, b:{start:6.4,end:8.9}, c:{start:8.9,end:10.0}};
MERGES['a'] = ['b','c'];
const p = trimPieces('a');
console.log(JSON.stringify(p.map(x=>[x.start,x.end])));
""")
    assert out == "[[2,6.4],[6.4,8.9],[8.9,10]]"


def test_안_합친_것은_예전_그대로_한_조각():
    out = _harness("""
DATA.segments = {a:{start:1.0,end:3.0}};
console.log(JSON.stringify(trimPieces('a').map(x=>[x.start,x.end])));
""")
    assert out == "[[1,3]]"


def test_합친_전체_길이는_그대로다():
    """가른다고 총량이 줄면 '가진 시간' 계산이 어긋난다."""
    out = _harness("""
DATA.segments = {a:{start:0,end:4}, b:{start:4,end:6}};
MERGES['a']=['b'];
const tot = trimPieces('a').reduce((s,x)=>s+(x.end-x.start),0);
console.log(tot);
""")
    assert out == "6"


def test_멤버_사이_공백은_빠진다():
    """예전엔 end만 늘려 사이의 남의 화면까지 통째로 포함됐다."""
    out = _harness("""
DATA.segments = {a:{start:0,end:2}, b:{start:5,end:7}};
MERGES['a']=['b'];
console.log(JSON.stringify(trimPieces('a').map(x=>[x.start,x.end])));
""")
    assert out == "[[0,2],[5,7]]"


def test_트림이_걸려도_멤버로_갈린다():
    """트림(앞뒤 잘라내기)과 합치기가 같이 쓰여도 둘 다 살아야 한다."""
    out = _harness("""
DATA.segments = {a:{start:0,end:4}, b:{start:4,end:8}};
MERGES['a']=['b'];
TRIMS['a']=[1,2];          // 장면 시작 기준 1~2초 구간을 도려낸다
console.log(JSON.stringify(trimPieces('a').map(x=>[x.start,x.end])));
""")
    # 앞토막 [0~1] + 뒤토막 [2~8] 이고, 뒤토막은 멤버 경계 4에서 갈린다
    assert out == "[[0,1],[2,4],[4,8]]"
