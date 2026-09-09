# -*- coding: utf-8 -*-
"""★scene_play.js를 **실제로 실행**해 본다 — 문자열 검색으로는 못 잡는 런타임 오류용.

2026-09-06 라이브 장애: planClips 안에서 `const bounds = [0];`로 선언한 값을
아래에서 `bounds = pickSplitBounds(...)`로 재대입해 브라우저가 통째로 죽었다.

    TypeError: Assignment to constant variable.
      at planClips → renderBand → render → boot

boot이 죽으니 컷 목록이 하나도 안 그려져 **사장님·고객 전원이 빈 화면**을 봤다.
(미리보기 영상은 별 코드라 재생돼서 "데이터는 있는데 목록만 빈" 모양이었다)

왜 기존 검사가 못 잡았나:
  · `node --check`는 **문법만** 본다 — const 재대입은 문법상 합법이고 실행할 때 터진다
  · test_cut_count_wired는 "planClips 본문에 pickSplitBounds라는 글자가 있나"만 본다
그래서 여기서는 **함수를 진짜로 호출**한다(메모리 '마크업테스트 문자열검색은 무용지물').
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "scene_play.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")

# 브라우저 전역 최소 흉내 — 파일 상단이 document·window를 만지므로 없으면 로드가 막힌다.
_STUBS = """
const _noop = () => {};
const _el = () => ({
  addEventListener: _noop, removeEventListener: _noop, appendChild: _noop, remove: _noop,
  querySelector: () => null, querySelectorAll: () => [], setAttribute: _noop,
  style: { setProperty: _noop, removeProperty: _noop },
  classList: { add: _noop, remove: _noop, toggle: _noop, contains: () => false },
  dataset: {}, getContext: () => null,
});
global.document = Object.assign(_el(), {
  getElementById: () => null, createElement: _el, body: _el(), documentElement: _el(),
});
global.window = global;
global.addEventListener = _noop;
global.removeEventListener = _noop;
global.location = { search: "", href: "" };
global.localStorage = { getItem: () => null, setItem: _noop, removeItem: _noop };
global.fetch = () => Promise.reject(new Error("no fetch in test"));
global.requestAnimationFrame = _noop;
global.matchMedia = () => ({ matches: false, addEventListener: _noop });
"""

# planClips가 읽는 전역을 라이브와 같은 모양으로 최소한만 채우고 실제로 부른다.
# ★scene_play.js의 `let DATA`와 **같은 스코프**여야 하므로 파일 뒤에 이어 붙인다.
_CALL = """
DATA = {
  segments: { "s0-0": {video_id:"s0", start:0, end:5},
              "s0-1": {video_id:"s0", start:5, end:10},
              "s0-2": {video_id:"s0", start:10, end:15} },
  beats: [{primary:{seg_id:"s0-0"}, alternates:[]}],
  captions: {}, tts_dur: {0: 4.8}, src_duration: {s0: 20},
};
// ★구절 맞춤 경로를 타게 만든다 — 2026-09-06에 죽은 그 길.
//   capsOf는 scene_lab.html에 있고 scene_play.js엔 없다(여기서 정의해야 조건을 통과한다).
//   phraseSyncOn·getFix는 파일 안에 있으므로 **덮어쓰지 않는다** — PHRASE_SYNC/FIXLEN을
//   비워두면 기본이 '구절맞춤 켬 · 수동길이 없음'이라 그대로 그 경로로 들어간다.
capsOf = () => ([{start:0.0},{start:1.2},{start:2.4},{start:3.6}]);
try {
  // ★planClips는 **seg_id 문자열 배열**을 받는다(객체를 넘기면 조용히 []가 되어
  //   버그 지점에 도달조차 못 한다 — 이 테스트를 처음 쓸 때 그렇게 가짜가 됐다).
  const clips = planClips(["s0-0", "s0-1", "s0-2"], 4.8, false, 0);
  console.log("OK:" + (Array.isArray(clips) ? clips.length : "not-array"));
} catch (e) {
  console.log("RUN_FAIL:" + e.message);
}
"""


def _run_scene_play():
    """scene_play.js + 호출 코드를 한 파일로 붙여 node로 돌린다. 출력 문자열 반환."""
    src = JS.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "harness.js"
        f.write_text(_STUBS + "\n" + src + "\n" + _CALL, encoding="utf-8")
        r = subprocess.run(["node", str(f)], capture_output=True, text=True, timeout=90)
    return (r.stdout or "") + (r.stderr or "")


def test_planClips가_구절맞춤_경로에서_실제로_돈다():
    """★이 테스트가 잡으려는 것: planClips 안의 런타임 오류(const 재대입 등).

    되돌려 확인: `let bounds = [0];`를 `const`로 바꾸면 이 테스트가 빨개진다."""
    out = _run_scene_play()
    assert "RUN_FAIL" not in out, "planClips가 실행 중 죽는다 — " + out.strip()[:400]
    assert "OK:" in out, "planClips를 부르지 못했다 — " + out.strip()[:400]
