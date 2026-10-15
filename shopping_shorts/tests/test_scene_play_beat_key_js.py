# -*- coding: utf-8 -*-
"""장면 편집(scene_play.js·scene_lab.html) — 화면 위치 i ≠ 진짜 칸 번호 beat_idx (2026-09-27).

서버가 주는 DATA.captions·DATA.tts_dur 의 키, 음성 주소 /api/mix/tts/{job}/{n} 은 **번호**다
(app.py _lab_captions 6242·6250, api_mix_tts 7943). 화면은 위치 i로 돈다(lists = DATA.beats.map).
칸을 지운 작업(번호 0,2,3)에서 위치로 읽으면 옆 칸의 자막·길이·음성이 나온다
(라이브 30일 done 1,636 job 중 13 job·40칸 실측).

scene_play.js 전체를 실제로 node로 실행하고, scene_lab.html의 beatIdOf·capSegs는
원본에서 떼어 붙여 같은 스코프에서 부른다(문자열 검사 아님).
"""
import json
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

ROOT = pathlib.Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "scene_play.js"
LAB = ROOT / "static" / "scene_lab.html"

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


def _lab_fn(name):
    src = LAB.read_text(encoding="utf-8")
    a = src.index(f"function {name}(")
    return src[a:src.index("\n}\n", a) + 3]


_CALL = """
const NARR = {};
DATA = {
  // 1번 칸을 지운 편집안: 위치 0,1,2 ↔ 번호 0,2,3
  beats: [{beat_idx:0, tts_ver:4, target_seconds:9, narration:'a'},
          {beat_idx:2, tts_ver:7, target_seconds:9, narration:'b'},
          {beat_idx:3, tts_ver:1, target_seconds:9, narration:'c'}],
  captions: {"0":[{text:"영", start:0, end:1.1}],
             "2":[{text:"둘", start:0, end:2.2}],
             "3":[{text:"셋", start:0, end:3.3}]},
  tts_dur: {"0":1.1, "2":2.2, "3":3.3},
};
SL.server = true; SL.job = 'J';
console.log(JSON.stringify({
  key: beatKeyAt(1),
  caps: capsOf(1).map(c => c.text),
  dur: beatDur(1),
  ver: ttsVer(1),
  url: SL.tts(1, ttsVer(1)),
  labId: beatIdOf(1),
  labSegs: capSegs(1).map(s => s.text),
}));
"""


def _run():
    code = (_STUBS + "\n" + JS.read_text(encoding="utf-8") + "\n"
            + _lab_fn("beatIdOf") + _lab_fn("narrChanged") + _lab_fn("capSegs") + _CALL)
    out = run_js(code, timeout=60)
    return json.loads(out.splitlines()[-1])


def test_position_reads_beat_idx_keys():
    r = _run()
    assert r["key"] == 2
    assert r["caps"] == ["둘"]          # 위치 1 = 번호 2의 자막(위치로 읽으면 없음)
    assert r["dur"] == 2.2              # 번호 2의 음성 길이(위치로 읽으면 target_seconds 9)
    assert r["ver"] == 7                # 그 자리 칸의 음성 버전
    assert r["url"] == "/api/mix/tts/J/2?v=7"


def test_scene_lab_uses_same_rule():
    r = _run()
    assert r["labId"] == 2
    assert r["labSegs"] == ["둘"]
