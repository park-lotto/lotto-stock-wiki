# -*- coding: utf-8 -*-
"""두유노판 대본 검사 = 사장님 첫 문장 공식(불편 → '~해버렸대요') — 10-28 '아직도 저장이 안 되어 있나'.
공식은 hook_formula.json·script_engine 에만 있고 회원 흐름 판 검사(script_audit)엔 없어 tv3·hdn2 첫 줄이 공식 밖으로 나갔다."""
import json
from pathlib import Path

from tools.calcopy.hybrid import script_audit as A


def _doc(first: str) -> dict:
    rest = ["게임기 패드랑 리모컨까지 아래 선반에 다 올라가더라고요.", "티비를 건 채로 손끝 하나로 쓱쓱 굴러가더라고요.",
            "침실로 밀어 놓으니 방마다 티비가 생긴 것 같아요.", "써 보니까 오히려 벽걸이보다 편하더라고요."]
    return {"lines": [{"id": f"l{i}", "kind": "tts", "tts": t, "caps": [t[:10]]} for i, t in enumerate([first] + rest)]}


def _hook(tmp_path: Path, first: str) -> dict:
    p = tmp_path / "대본.json"
    p.write_text(json.dumps(_doc(first), ensure_ascii=False), encoding="utf-8")
    return next(r for r in A.audit(p, "두유노판")["rules"] if r["kind"] == "hook_formula")


def test_old_tv3_first_line_rejected(tmp_path):
    assert not _hook(tmp_path, "벽에 구멍 하나 못 뚫는 우리 전셋집 티비가 방마다 돌아다녀요.")["ok"]


def test_formula_first_line_passes(tmp_path):
    assert _hook(tmp_path, "전셋집이라 벽에 구멍 하나 못 뚫어서 답답했던 한 부부가 아예 티비에 바퀴를 달아버렸대요.")["ok"]


def test_rule_in_question_text():
    assert "첫 문장 공식" in A.rules_text("두유노판")
