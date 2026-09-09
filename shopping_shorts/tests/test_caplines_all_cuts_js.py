"""★자막 줄나누기가 **같은 자막의 모든 컷 칸**에 반영되는지 (2026-09-09 사장님 제보).

증상: "줄바꿈을 해도 되돌아간다 / 반영이 안 된다".
뿌리: 화면은 **컷마다 한 칸**이다(beats_preview는 비트 하나가 컷 4개면 칸 4개를 준다).
      저장 성공 뒤 `b.segs=d.lines`가 **지금 보던 칸 하나만** 갈아끼워서, ◀▶로 같은
      자막의 다른 컷으로 넘어가면 그 칸은 옛 줄을 들고 있었다. 거기서 다시 저장하면
      **옛 줄이 방금 저장한 줄을 덮어쓴다**.
      (화면 안내문은 이미 "자막 손질은 그 컷 전부에 같이 적용돼요"라고 말하고 있었다.)
"""
import pathlib
import re

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _fn(name):
    """produce.html에서 함수 하나의 소스를 뽑는다(중괄호 균형)."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index("function %s(" % name)
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    raise AssertionError("%s 함수 끝을 못 찾음" % name)


def test_caplines_result_applies_to_every_cut_of_the_beat():
    js = "\n".join([
        _fn("_beatNo"),
        _fn("_capApplyToBeat"),
        # 비트 2번이 컷 3개로 갈린 화면 — 렌더 서버가 주는 모양 그대로
        "var BEATS_PREVIEW=[{beat_idx:1,segs:['가']},"
        " {beat_idx:2,cut:0,segs:['옛1','옛2']},"
        " {beat_idx:2,cut:1,segs:['옛1','옛2']},"
        " {beat_idx:2,cut:2,segs:['옛1','옛2']}];",
        "var BEAT_IDX=1;",
        "_capApplyToBeat(BEATS_PREVIEW[1], {segs:['새1'], durs:null});",
        "console.log(JSON.stringify(BEATS_PREVIEW.map(function(b){return b.segs.join('|');})));",
    ])
    out = run_js(js)
    assert out == '["가","새1","새1","새1"]', out


def test_save_and_reset_use_the_beatwide_helper():
    """저장·되돌리기 경로가 헬퍼를 거치는지 — 한 칸만 고치는 옛 코드로 되돌아가지 않게."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    assert not re.search(r"\bb\.segs\s*=\s*d\.lines", src), \
        "저장 결과를 칸 하나에만 꽂고 있다 — _capApplyToBeat를 써라"
    assert src.count("_capApplyToBeat(") >= 3, "저장·되돌리기·자리 세 경로가 헬퍼를 거쳐야 한다"
