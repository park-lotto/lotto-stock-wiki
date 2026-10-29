"""10-30 사장님 '목소리·길이 걸림을 왜 대본까지 거슬러 가서 장면을 처음부터 다시 맞추냐' —
flow._voice_rewrite·_length_rewrite 가 먼저 그 자리 줄 고치기(_line_fix): 걸린 줄만 묻고 재료(컷)는 그대로 → 대본만 저장하고 계획부터."""
import json

from tools.calcopy.hybrid import flow as F


def _st():
    S = {"title_lines": [[["가", None]], [["나", None]]],
         "lines": [{"id": "L1", "kind": "tts", "tts": "첫 줄.", "caps": ["첫 줄"]},
                   {"id": "L5", "kind": "tts", "tts": "느린 줄 입니다.", "caps": ["느린 줄 입니다"]}]}
    M = {"cuts": {"L1": [{"src": "a.mp4", "ss": 1}], "L5": [{"src": "b.mp4", "ss": 2}]}}
    return {"version": "썰템쇼판", "script": {"S": S, "M": M}, "tries": {}, "log": [], "read": {}, "product": {}}


def test_voice_problem_asks_only_that_line():
    st = _st()
    out = F._voice_rewrite(st, ["줄별 말속도 L5:6.1 너무 느림"])
    assert out["then"] == "line_fix_got"
    q = out["review"][0]
    text = json.dumps(q, ensure_ascii=False)
    assert "L5" in text and "첫 줄" not in text.split("지금 줄")[1].split("JSON")[0]      # 걸린 줄만 실린다


def test_line_fix_keeps_material_and_goes_to_plan(monkeypatch):
    st = _st()
    F._voice_rewrite(st, ["L5 말속도"])
    M0 = json.dumps(st["script"]["M"])
    monkeypatch.setattr(F, "audit_script", lambda st_, S, M: {"ok": True})
    monkeypatch.setattr(F, "_reply", lambda rp, rid, need: {"lines": {"L5": {"tts": "느린 줄.", "caps": ["느린 줄"]}}})
    out = F.ph_line_fix_got(st, {}, {}, None)
    assert out["then"] == "plan" and json.dumps(st["script"]["M"]) == M0
    assert st["script"]["S"]["lines"][1]["tts"] == "느린 줄." and st["script"]["S"]["lines"][0]["tts"] == "첫 줄."
    assert st["_plan_fixed"] is True


def test_failed_line_fix_falls_back_to_full_rewrite(monkeypatch):
    st = _st()
    F._voice_rewrite(st, ["L5 말속도"])
    monkeypatch.setattr(F, "audit_script", lambda st_, S, M: {"ok": False, "x": ["bad"]})
    monkeypatch.setattr(F, "_reply", lambda rp, rid, need: {"lines": {"L5": {"tts": "?", "caps": ["?"]}}})
    called = {}
    monkeypatch.setattr(F, "_script_ask", lambda st_, why="": called.setdefault("full", why) or {"x": 1})
    out = F.ph_line_fix_got(st, {}, {}, None)
    assert "full" in called and out["then"] == "script_got"


def test_no_line_id_uses_old_path(monkeypatch):
    st = _st()
    called = {}
    monkeypatch.setattr(F, "_script_ask", lambda st_, why="": called.setdefault("full", why) or {"x": 1})
    F._voice_rewrite(st, ["받아쓰기 확정 결함(줄 표시 없음)"])
    assert "full" in called
