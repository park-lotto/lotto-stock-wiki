"""2단계 안내 문구의 '안 개수'가 실제 생성 개수(s2AnCount)와 같은지.

2026-09-02 라이브 실측:
  스타일을 하나도 안 고르면 픽업 1안만 나온다(s2AnCount()=1, drafts=1).
  그런데 안내는 "AI가 스타일까지 골라 **2안**을 만듭니다"로 박혀 있었다.
  생성 뒤 부족 경고도 s2AnCount() 기준이라 경고조차 안 떠서, 고객에겐
  "2안 준다더니 1안만 왔다"만 남았다(0순위-B: 개수를 두 곳에서 따로 셈).

이 테스트는 문구에서 숫자를 뽑아 s2AnCount()와 대조한다.
문구에 숫자를 다시 손으로 박으면 빨개진다.
"""
import json, pathlib, re, shutil, subprocess, pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_HARNESS = r"""
'use strict';
global.S2 = { picked: PICKED, usePickup: USE_PICKUP };
let _hintTxt = '';
global.document = { getElementById: (id) => (id === 's2GenHint')
  ? { set textContent(v){ _hintTxt = v; }, get textContent(){ return _hintTxt; } }
  : null };
"""

# 문구를 쓰는 조각만 떼어 낸다(카드 렌더 전체는 DOM이 필요해 못 돌린다).
_START = "  const hint=document.getElementById('s2GenHint');"
_END = "function s2ClearStyles()"

_DRIVER = r"""
console.log(JSON.stringify({ hint: _hintTxt, want: s2AnCount() }));
"""


def _run(tmp_path, picked, use_pickup):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    frag = src[src.index(_START):src.index(_END)]
    # 조각 끝의 닫는 중괄호(렌더 함수의 것)를 떼고, s2AnCount 정의를 함께 싣는다.
    frag = frag.rstrip().rstrip("}")
    m = re.search(r"^function s2AnCount\(\).*$", src, re.M)
    assert m, "s2AnCount 정의를 못 찾음"
    js = tmp_path / "t.js"
    js.write_text(
        _HARNESS.replace("PICKED", json.dumps(picked)).replace("USE_PICKUP", json.dumps(use_pickup))
        + m.group(0) + "\n" + frag + "\n" + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
@pytest.mark.parametrize("picked,use_pickup", [
    ([], True),            # 스타일 0 + 픽업 → 1안  (라이브에서 "2안"이라 거짓말하던 경우)
    (["a"], True),         # 스타일 1 + 픽업 → 2안
    (["a"], False),        # 스타일 1, 픽업 끔  → 1안
])
def test_hint_number_matches_real_count(tmp_path, picked, use_pickup):
    got = _run(tmp_path, picked, use_pickup)
    nums = [int(x) for x in re.findall(r"(\d+)안", got["hint"])]
    assert nums, f"안내 문구에 '<숫자>안'이 없다: {got['hint']!r}"
    assert nums[-1] == got["want"], (
        f"안내는 {nums[-1]}안인데 실제 생성은 {got['want']}안 — {got['hint']!r}")
