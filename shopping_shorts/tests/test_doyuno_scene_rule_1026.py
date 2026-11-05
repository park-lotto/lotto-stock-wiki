# -*- coding: utf-8 -*-
"""10-26 잇썸홈 두유노판 상위 10편 대조 → 규칙 수리 시험.
① material_bank.usable: 제품 없는 '문제 상태' 구간(state problem·product none·act '문제: …')도 재료 · 다른 제품(other)·남의 글자는 계속 아님
② material_bank.story_visible: 판 script.scene_rule — 훅·도입 줄에 문제 상태 조각이 없으면 멈춤 사유
③ script_audit head_connectors·made_candidates: 상위 10편 대조 기계 칸(bench_compare_script_scene.CONNECTORS·MADE_RE)과 같은 자
④ script_audit engine off ['wow']: 두유노판만 와우 줄 머리 연결어 3줄을 끈다 — 다른 판(잇썸홈판)은 그대로."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import material_bank as MB  # noqa: E402
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402


def test_usable_problem_state():
    assert MB.usable({"product": "none", "state": "problem", "act": "문제: 물 고임", "text": False})
    assert not MB.usable({"product": "none", "state": "problem", "act": "물 고임", "text": False})        # 이름 머리 '문제:' 필수
    assert not MB.usable({"product": "other", "state": "problem", "act": "문제: 물 고임", "text": False})  # 다른 제품 보이면 안 됨
    assert not MB.usable({"product": "none", "state": "problem", "act": "문제: 물 고임", "text": True})
    assert not MB.usable({"product": "none", "act": "제품 보여주기", "text": False})
    assert MB.usable({"product": "same", "act": "누르기", "text": False})


def test_story_visible():
    segs = [{"product": "none", "state": "problem", "act": "문제: 물 고임"}, {"product": "same", "act": "누르기"}]
    rule = {"story_slots": ["훅", "도입"], "min_problem_pieces": 1}
    bad = {"lines": [{"slot": "훅", "pieces": [{"text": "업체 부르려다", "act": ["누르기"]}]}]}
    good = {"lines": [{"slot": "훅", "pieces": [{"text": "물이 고여서", "act": ["문제: 물 고임"]}]},
                      {"slot": "효과", "pieces": [{"text": "꾹", "act": ["누르기"]}]}]}
    assert MB.story_visible(bad, segs, rule)
    assert MB.story_visible(good, segs, rule) == []
    assert MB.story_visible(bad, segs, None) == []          # 판에 scene_rule 없으면 안 잰다(다른 판 그대로)


def _d(texts):
    return {"lines": [{"id": f"L{i + 1}", "kind": "tts", "text": t} for i, t in enumerate(texts)]}


def test_head_connectors_and_made():
    ok, why = SA.rule_check({"kind": "head_connectors", "max": 0.0}, _d(["세면대에 물이 고였어요.", "꾹 누르면 닫혀요."]), {})
    assert ok, why
    ok, why = SA.rule_check({"kind": "head_connectors", "max": 0.0}, _d(["세면대에 물이 고였어요. 심지어 냄새도 나요."]), {})
    assert not ok, why                                      # 줄 안 두 번째 문장 머리도 센다(받아쓰기 문장 기준)
    ok, why = SA.rule_check({"kind": "made_candidates", "max": 0}, _d(["해외에서 조회수 2000만 찍었어요."]), {})
    assert not ok, why
    ok, why = SA.rule_check({"kind": "made_candidates", "max": 0}, _d(["머리카락만 거르려고 만든 거름망이었어요."]), {})
    assert ok, why


def test_engine_off_wow_only_this_board():
    lines = [{"text": t} for t in ["세면대에 물이 고여서 업체 부르려다 와이프한테 혼났어요.", "배수구에서 머리카락 뭉치가 나왔어요.",
                                   "머리카락만 거르려고 만든 거름망이었어요.", "볼펜처럼 누르면 닫혀요.", "요즘 자취생들 사이에서 필수템이래요."]]
    on = SA.engine("itssum", {}, lines)
    off = SA.engine("itssum", {}, lines, ("wow",))
    assert any("와우" in w for w in on["points"]["why"])
    assert not any("와우" in w or "강한 연결어" in w for w in off["points"]["why"])
