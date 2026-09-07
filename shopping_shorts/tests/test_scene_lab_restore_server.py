# -*- coding: utf-8 -*-
"""3단계(scene_lab) — 로컬 저장본이 없어도 서버 편성으로 되살아나는가.

2026-09-07 고객 다수 제보 "작업하다가 3단계로 가니 작업이 다 없어졌다"의 회귀 방어.
뿌리: 복원 통로가 localStorage 하나뿐이라, 로컬 저장본이 없거나(다른 PC·브라우저 정리)
칸 수가 달라져 버려지면(4단계에서 대본 줄을 고침) initLists가 돌아 **AI 기본 배치로
초기화**됐다. 서버 edit_plan에는 편성(scene_override)이 멀쩡히 남아 있는데도 그랬다
(실측 job 441702e0ec14: 5칸 배정 전부 생존).

판정은 문자열 세기가 아니라 **실제 실행**이다 — 함수를 node로 떼어 돌리고
lists가 무엇이 됐는지로 본다.
"""
import json
import os
import re
import subprocess
import tempfile

import pytest

_HTML = os.path.join(os.path.dirname(__file__), "..", "static", "scene_lab.html")


def _fn(src, name):
    """scene_lab.html에서 함수 하나를 통째로 떼어낸다(중괄호 균형으로 끝을 찾는다)."""
    i = src.index("function %s(" % name)
    depth, j, started = 0, i, False
    while j < len(src):
        if src[j] == "{":
            depth += 1
            started = True
        elif src[j] == "}":
            depth -= 1
            if started and depth == 0:
                return src[i:j + 1]
        j += 1
    raise AssertionError("함수 끝을 못 찾음: %s" % name)


def _run(beats, call):
    src = open(_HTML, encoding="utf-8").read()
    harness = """
const DATA = %s;
let lists = null, mode = 'live';
const FIXLEN = {};
let rendered = 0, said = '';
function render(){ rendered++; }
function nsay(m){ said = m; }
function hydrateFixlen(x){}
function fixlenFromBeats(){ return {}; }
function undoMark(){}
function saveWork(){}
function baseList(b){ return [b.primary, ...(b.alternates || [])].filter(Boolean).map(s => s.seg_id); }
const document = { getElementById: () => null };
%s
%s
%s
const out = %s;
console.log(JSON.stringify({ret: out, lists, mode, rendered, said}));
""" % (
        json.dumps({"beats": beats}, ensure_ascii=False),
        _fn(src, "serverList"),
        _fn(src, "hasServerEdit"),
        _fn(src, "restoreServer"),
        call,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(harness)
        path = f.name
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(path)


# 서버에 편성이 얹혀 있는 잡 — 박세현 님 441702e0ec14의 모양 그대로(칸마다 scene_override).
_BEATS_WITH_SERVER = [
    {"beat_idx": 0,
     "primary": {"seg_id": "ai_a"}, "alternates": [{"seg_id": "ai_b"}],
     "scene_override": [{"seg_id": "film_s8_0.46_2.03"}, {"seg_id": "lens_x-1"}]},
    {"beat_idx": 1,
     "primary": {"seg_id": "ai_c"}, "alternates": [],
     "scene_override": [{"seg_id": "film_s2_11.36_12.45"}]},
]
# 편성이 없는 잡(아직 아무도 안 고친 새 잡)
_BEATS_CLEAN = [
    {"beat_idx": 0, "primary": {"seg_id": "ai_a"}, "alternates": [{"seg_id": "ai_b"}]},
    {"beat_idx": 1, "primary": {"seg_id": "ai_c"}, "alternates": []},
]


def test_서버편성이_있으면_되살아난다():
    """★핵심: 로컬 저장본이 없어도 사람이 고친 편성이 그대로 온다."""
    r = _run(_BEATS_WITH_SERVER, "restoreServer('불러왔어요')")
    assert r["ret"] is True
    assert r["lists"] == [["film_s8_0.46_2.03", "lens_x-1"], ["film_s2_11.36_12.45"]], r["lists"]
    assert r["mode"] == "hand"        # 사람이 정한 배치다
    assert r["rendered"] == 1
    assert r["said"] == "불러왔어요"


def test_AI기본배치로_초기화되지_않는다():
    """되살린 목록이 baseList(AI 원본)와 달라야 한다 — 같으면 초기화된 것."""
    r = _run(_BEATS_WITH_SERVER, "restoreServer('x')")
    assert r["lists"][0] != ["ai_a", "ai_b"]
    assert r["lists"][1] != ["ai_c"]


def test_서버편성이_없으면_false로_비켜준다():
    """fail-open — 되살릴 게 없으면 호출한 쪽이 다음 수단(picks·initLists)으로 넘어가야 한다."""
    r = _run(_BEATS_CLEAN, "restoreServer('x')")
    assert r["ret"] is False
    assert r["lists"] is None          # 손대지 않았다
    assert r["rendered"] == 0
    assert r["mode"] == "live"         # 모드도 안 바꿨다


def test_일부칸만_편성이_있으면_나머지는_AI배치로_채운다():
    beats = [dict(_BEATS_WITH_SERVER[0]), dict(_BEATS_CLEAN[1])]
    r = _run(beats, "restoreServer('x')")
    assert r["ret"] is True
    assert r["lists"] == [["film_s8_0.46_2.03", "lens_x-1"], ["ai_c"]], r["lists"]


def test_초기화_분기에_서버복원_폴백이_있다():
    """loadWork·loadSaved가 모두 실패한 뒤 initLists 앞에 restoreServer가 있어야 한다."""
    src = open(_HTML, encoding="utf-8").read()
    tail = src[src.index("else if (loadWork()) render();"):]
    tail = tail[:tail.index("initLists(); render();")]
    assert "restoreServer(" in tail, "폴백이 사라졌다 — 다시 '작업이 다 없어진다'"
