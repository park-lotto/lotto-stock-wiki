# -*- coding: utf-8 -*-
"""대본 제목 줄 글자 수 규칙 title_chars(11-07 썰반장 — 벤치 제목 줄마다 5~7자, 9자 제목이 max_w 에 걸려 150→100px 로 줄었다).
판정 주인 = script_audit.rule_check(title_lines 규칙 옆), 숫자 = 판 script.audit 한 곳. Jev q_title3 통과(뿌리 0.87·근본 0.89·한줄기 0.85·두더지 0.11)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402

R = {"id": "title_chars", "kind": "title_chars", "min": 3, "max": 7}


def _d(*lines):
    return {"title_lines": [[[t, None]] for t in lines], "lines": []}


def test_title_chars_ok_and_too_long():
    ok, why = SA.rule_check(R, _d("이혼 앞둔 여자", "말 건 낯선 남자"), {})
    assert ok, why
    ok, why = SA.rule_check(R, _d("이혼하려던 여자에게", "말 건 낯선 남자"), {})
    assert not ok and "1줄" in why


def test_title_chars_counts_chunks_in_one_line():
    ok, _ = SA.rule_check(R, {"title_lines": [[["사람 ", None], ["좋아한", "#FF0000"]]], "lines": []}, {})
    assert ok


def test_rule_text_mentions_title_chars():
    assert "제목" in SA.rule_text(R, {})


def test_sseolbanjang_pan_has_title_rule():
    from tools.calcopy.hybrid import styles as ST
    assert any(r["kind"] == "title_chars" for r in ST.load("썰반장판")["script"]["audit"])
