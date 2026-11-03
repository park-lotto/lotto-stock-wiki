"""#1954 삼현정 — 완성 뒤 회원이 제목을 바꿔 달라고 했는데 줄 고치기(_apply_lines)가 줄(tts·caps)만 받아 title_lines 답을 버렸다.
제목도 대본 칸 — _apply_lines 가 title_lines 도 받는다(검사 audit_script 그대로). 제목은 컷을 정하지 않아 계획 지문(plan_input_sig)에서 빠진다
→ 제목만 바뀐 편은 지난 계획을 다시 쓰고 렌더만 다시."""
import json

from tools.calcopy.hybrid import flow as F
from tools.calcopy.hybrid import render_bench as RB

NEW = [[["새 제목", None]], [["둘째 줄", None]]]


def _st():
    S = {"title_lines": [[["가", None]], [["나", None]]],
         "lines": [{"id": "L1", "kind": "tts", "tts": "첫 줄.", "caps": ["첫 줄"]}]}
    return {"version": "썰템쇼판", "script": {"S": S, "M": {"cuts": {"L1": [{"src": "a.mp4", "ss": 1}]}}}, "tries": {}, "log": [], "read": {}, "product": {}}


def test_member_title_change_is_applied(monkeypatch):
    st = _st()
    st["phase"] = "render_got"
    out = F.step(st, {}, {}, {"revise": "제목을 '새 제목'으로 바꿔 줘"})
    assert "title_lines" in json.dumps(out["review"][0], ensure_ascii=False)       # 질문이 제목 칸을 알려 준다
    monkeypatch.setattr(F, "audit_script", lambda st_, S, M: {"ok": True})
    monkeypatch.setattr(F, "_reply", lambda rp, rid, need: {"lines": {}, "title_lines": NEW})
    done = F.ph_line_fix_got(st, {}, {}, None)
    assert done["then"] == "plan" and st["script"]["S"]["title_lines"] == NEW
    assert done["do"][0]["files"]["썰템쇼판/대본.json"]["title_lines"] == NEW


def test_title_only_keeps_plan_signature(tmp_path):
    S = _st()["script"]["S"]
    M = {"cuts": {}}
    st = {"name": "x"}
    a = RB.plan_input_sig(S, M, st, True, False)
    assert RB.plan_input_sig({**S, "title_lines": NEW}, M, st, True, False) == a
    assert RB.plan_input_sig({**S, "lines": []}, M, st, True, False) != a
