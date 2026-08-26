# -*- coding: utf-8 -*-
"""칸 길이 표기(`담은재료/자막`)가 두 화면에서 같은 값을 내는지 지킨다.

배경(2026-08-17 사장님 "4.9/5로 표시되나?"):
  종전엔 칸 헤더에 `5.1초` 하나만 떴다. 그런데 그 숫자는 planClips가 부족분을 이미
  0으로 만든 **뒤**의 합계라, 자막 길이와 언제나 같다(토글 OFF=마지막 컷에 몰기 /
  ON=전 컷 비례배분). 즉 `sec/need`로 짝을 지으면 늘 `5.0/5.0`이라 정보가 없다.
  → 왼쪽을 **늘리기 전 진짜 재료**(effLen 합)로 두어야 "늘려서 때우는 중"이 드러난다.

이 파일이 지키는 것:
  1) 보정 뒤 합계는 언제나 need와 같다 — 그래서 짝표기의 왼쪽으로 쓰면 안 된다(회귀 방지)
  2) 재료 계산 기준은 okIds(tooShort 제외) 한 가지뿐이다 — 두 화면이 갈리면 안 된다
  3) 컷이 0장이면 planClips가 보정을 건너뛴다 → '늘려 채움'이라 말하면 거짓말이다
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"
JS = STATIC / "scene_play.js"
LAB = STATIC / "scene_lab.html"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _harness(body):
    """scene_play.js의 진짜 계산 + scene_lab.html의 진짜 beatFill을 그대로 끌어다 돌린다.

    복사본을 만들지 않는다 — 복사하면 원본이 바뀌어도 테스트는 옛 규칙을 계속 통과한다.
    """
    src = JS.read_text(encoding="utf-8")
    keep = []
    for name in ("function trimPieces", "function effLen", "function planClips",
                 "function beatDur"):
        m = re.search(re.escape(name) + r".*?(?=\n(?:const |let |var |function |//))", src, re.S)
        assert m, f"{name} 를 scene_play.js에서 못 찾았다 — 이름이 바뀌었나?"
        keep.append(m.group(0))

    lab = LAB.read_text(encoding="utf-8")
    mf = re.search(r"function beatFill\(i, clips\)\{.*?\n\}", lab, re.S)
    assert mf, "beatFill 을 scene_lab.html에서 못 찾았다 — 계산이 다시 흩어졌나?"

    pre = """
const EPS=0.05, MIN_CLIP=0.6, MAX_SHOT=2.2; let onePerSeg=false; const TRIMS={};
let DATA={segments:{}, tts_dur:{}, beats:[{}]};
let lists=[[]], STRETCH={};
function mergeSpan(id){ const s=DATA.segments[id]; return s?{...s,video_id:id}:null; }
function splitByMembers(id, sp){ return [sp]; }
function tooShort(id){ const s=DATA.segments[id]; return !s || (s.end-s.start) < 0.8; }
function fill(segs, tts, on){
  DATA.segments=segs; DATA.tts_dur={'0':tts}; lists=[Object.keys(segs)]; STRETCH={0:on};
  const clips = planClips(lists[0], beatDur(0), on);
  return {f: beatFill(0, clips), sec: clips.reduce((a,c)=>a+c.dur,0)};
}
"""
    code = pre + "\n".join(keep) + "\n" + mf.group(0) + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True)
    assert r.returncode == 0, (r.stderr or r.stdout)
    return r.stdout.strip()


def test_보정후_합계는_언제나_자막길이와_같다():
    """`sec/need` 짝표기가 무의미한 이유 — 이게 깨지면 표기 설계를 다시 봐야 한다."""
    out = _harness("""
const cases = [
  [{a:{start:0,end:1.5}, b:{start:0,end:1.0}}, 5.0],   // 재료 부족
  [{a:{start:0,end:2.5}, b:{start:0,end:2.5}}, 5.0],   // 딱 맞음
  [{a:{start:0,end:4.0}, b:{start:0,end:4.0}}, 5.0],   // 재료 남음
];
const out = [];
for (const [segs, tts] of cases)
  for (const on of [false, true])
    out.push(Math.abs(fill(segs, tts, on).sec - tts) < 0.01);
console.log(out.every(Boolean) ? 'ALL_EQUAL' : 'DIFFERS:' + JSON.stringify(out));
""")
    assert out == "ALL_EQUAL", f"보정 뒤 합계가 자막 길이와 달라졌다: {out}"


def test_재료계산은_tooShort를_뺀_한가지_기준뿐():
    """0.6~0.8초 장면이 두 기준을 가르는 유일한 틈이다(실측 2026-08-17: 위2.70 아래2.00).

    beatFill이 okIds 기준을 쓰므로 그 틈의 장면은 재료에서 빠져야 한다.
    """
    out = _harness("""
const {f} = fill({a:{start:0,end:2.0}, m:{start:0,end:0.7}}, 5.0, false);
console.log(JSON.stringify({have:+f.have.toFixed(2), tiny:f.tinyN}));
""")
    assert out == '{"have":2,"tiny":1}', (
        f"0.7초 장면이 재료에 섞였다 — 담아도 화면에 안 나오는 길이다: {out}")


def test_컷이_0장이면_늘려채움이_아니다():
    """planClips가 clips.length 검사로 보정을 건너뛴다 → 실제로는 무음 화면이다."""
    out = _harness("""
const on  = fill({}, 5.0, true).f;
const off = fill({}, 5.0, false).f;
console.log(JSON.stringify({on:on.stretching, off:off.stretching,
                            empty:on.empty, lack:+on.lack.toFixed(1)}));
""")
    assert out == '{"on":false,"off":false,"empty":true,"lack":5}', (
        f"장면이 없는데 '늘려 채우는 중'이라고 말하고 있다: {out}")


def test_늘려채움은_컷이_있을때만_참():
    """정상 상태에서는 토글이 그대로 반영돼야 한다(위 테스트가 과잉 차단하지 않았나)."""
    out = _harness("""
const on = fill({a:{start:0,end:1.5}, b:{start:0,end:1.0}}, 5.0, true).f;
console.log(JSON.stringify({stretching:on.stretching, empty:on.empty,
                            lack:+on.lack.toFixed(1)}));
""")
    assert out == '{"stretching":true,"empty":false,"lack":2.5}', out
