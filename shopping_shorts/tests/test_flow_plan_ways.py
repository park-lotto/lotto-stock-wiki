"""10-30 숏클 점검표 7·8 — 장면 검수에서 재료로 못 고치는 줄: 멈추지 않고 그 자리에서 ① 그 줄 문장 바꾸기(대본줄) ② 재료만 더 찾기(재료_더찾기).
대본·원본·앞 단계는 그대로(뒤로 가서 처음부터 다시 하지 않는다). 실데이터 재현: 저장된 회원 편 hs_ep3 상태로 단계만 돌려 확인(scratchpad replay_plan_ways.py)."""
import json

from tools.calcopy.hybrid import flow as F


def _st():
    S = {"title_lines": [[["가", None]], [["나", None]]],
         "lines": [{"id": "L1", "kind": "tts", "tts": "첫 줄.", "caps": ["첫 줄"]},
                   {"id": "L3", "kind": "tts", "tts": "장면 없는 줄.", "caps": ["장면 없는 줄"]}]}
    M = {"cuts": {"L1": [{"src": "a.mp4", "ss": 1}], "L3": [{"src": "a.mp4", "ss": 2}]}}
    return {"version": "썰템쇼판", "phase": "plan_look", "script": {"S": S, "M": M}, "tries": {}, "log": [], "read": {}, "product": {"name": "진라면"},
            "bench": {"id": "BENCH"}, "origin": {}, "research": {"exclude": ["모음"]}, "material": {"files": [{"name": "a.mp4"}]},
            "_plan_over": ["L3: 맞는 장면이 재료에 없다"], "_plan_sheet": "plan.jpg"}


def _ans(**kw):
    return {"plan_썰템쇼판": {"ok": False, "problems": ["L3 장면 없음"], "재료": None, **kw}}


def _light(monkeypatch):
    monkeypatch.setattr(F, "_fix_review", lambda st, why, sheet, rid, more=None: {"id": rid, "ask": why, "show": [sheet, *(more or [])], "need": ["ok"]})


def test_more_material_runs_in_place_and_comes_back_to_look(monkeypatch):
    _light(monkeypatch)
    st = _st()
    out = F.step(st, {}, _ans(**{"재료_더찾기": ["진라면 끓이는 영상"]}), {})
    assert st["phase"] == "more_got" and out["do"][0]["cmd"] == "screen" and out["do"][0]["queries"] == ["진라면 끓이는 영상"]
    out = F.step(st, {"screen": {"rows": [{"id": "a"}, {"id": "NEW"}], "sheets": ["screen/a_sheet.jpg", "screen/NEW_sheet.jpg"]}}, {}, {})
    assert out["review"][0]["id"] == "more_pick" and '"a"' not in json.dumps(st["_more_rows"])     # 이미 쓰는 재료는 후보에서 뺀다
    out = F.step(st, {}, {"more_pick": {"chosen": [{"id": "NEW", "why": "끓이는 장면", "sections": [[1, 9]]}]}}, {})
    assert out["do"][0]["cmd"] == "download"
    out = F.step(st, {"dl": {"files": [{"name": "NEW.mp4"}]}}, {}, {})
    assert out["do"][0]["cmd"] == "mat_sheets" and [x["name"] for x in st["material"]["files"]] == ["a.mp4", "NEW.mp4"]
    out = F.step(st, {"msheets": {"sheets": ["_sheet_NEW.jpg"], "list": [{"file": "NEW.mp4"}], "shots": {"NEW.mp4": [[0, 9]]}}}, {}, {})
    rv = out["review"][0]
    assert st["phase"] == "plan_look" and rv["id"] == "plan_썰템쇼판" and "_sheet_NEW.jpg" in rv["show"] and "새 재료 1개" in rv["ask"]
    assert st["script"]["S"]["lines"][1]["tts"] == "장면 없는 줄."      # 대본은 그대로


def test_more_material_limit(monkeypatch):
    _light(monkeypatch)
    st = _st()
    st["tries"]["more_material"] = F.MORE_MATERIAL_MAX
    F.step(st, {}, _ans(**{"재료_더찾기": ["x"]}), {})
    assert st["phase"] != "more_got"


def test_script_line_from_plan_look_keeps_material(monkeypatch):
    _light(monkeypatch)
    monkeypatch.setattr(F, "audit_script", lambda st_, S, M: {"ok": True})
    st = _st()
    M0 = json.dumps(st["script"]["M"])
    out = F.step(st, {}, _ans(**{"대본줄": {"L3": {"tts": "있는 장면에 맞춘 줄.", "caps": ["있는 장면에 맞춘 줄"]}}}), {})
    assert out["do"][0]["id"] == "save_script" and st["phase"] == "plan"
    assert st["script"]["S"]["lines"][1]["tts"] == "있는 장면에 맞춘 줄." and st["script"]["S"]["lines"][0]["tts"] == "첫 줄."
    assert json.dumps(st["script"]["M"]) == M0 and st["_plan_fixed"] is True


def test_no_fix_asks_once_more_before_stopping(monkeypatch):
    _light(monkeypatch)
    st = _st()
    out = F.step(st, {}, _ans(), {})
    assert st["phase"] == "plan_look" and "셋 중 하나는 반드시" in out["review"][0]["ask"]


def _chk():
    return {"check": {"auto": {"ok": True, "rows": []}, "eye_files": ["썰템쇼판/eye/시트_1초.jpg", "썰템쇼판/eye/훅3초_0.1초.jpg", "썰템쇼판/eye/벤치대조_시트.jpg"], "eye_texts": {}}}


def _seen(st, **kw):
    """시트 답 = 화면에서 읽은 제목·줄별 기록 포함(flow.SHEET_NEED)."""
    sv = F.script_view(st)
    return {"title_seen": sv["title"], "scenes": [{"seen": "화면"} for _ in sv["lines"]], **kw}


def test_final_sheet_is_asked_even_when_gate_passes(monkeypatch):
    monkeypatch.setattr(F, "EYE_REVIEW", False)
    """숏클 지침 15-0 — 자동 검사 통과여도 완성 전 1초 시트를 회원 Claude 가 한 번 본다(사장님 PC 제작과 같게)."""
    st = _st()
    st["phase"] = "check_got"
    out = F.step(st, _chk(), {}, {})
    rv = out["review"][0]
    assert rv["id"] == "sheet_썰템쇼판" and st["phase"] == "final_sheet"
    files = [x.get("file") for x in rv["show"] if isinstance(x, dict)]
    assert "썰템쇼판/eye/시트_1초.jpg" in files and "썰템쇼판/eye/벤치대조_시트.jpg" not in files
    out = F.step(st, {}, {"sheet_썰템쇼판": _seen(st, ok=True, problems=[])}, {})
    assert out["do"][0]["cmd"] == "finish"


def test_final_sheet_problem_goes_to_fix_with_line_way(monkeypatch):
    monkeypatch.setattr(F, "EYE_REVIEW", False)
    seen = {}
    monkeypatch.setattr(F, "_fix_review", lambda st, why, sheet, rid, more=None: seen.setdefault(rid, sheet) and {"id": rid, "ask": why, "show": [], "need": ["ok"]} or {"id": rid, "ask": why, "show": [], "need": ["ok"]})
    monkeypatch.setattr(F, "audit_script", lambda st_, S, M: {"ok": True})
    st = _st()
    st["phase"] = "check_got"
    F.step(st, _chk(), {}, {})
    out = F.step(st, {}, {"sheet_썰템쇼판": _seen(st, ok=False, problems=["7초 L3 자막 넘침"])}, {})
    assert out["review"][0]["id"] == "final_fix_썰템쇼판" and seen["final_fix_썰템쇼판"].endswith("시트_1초.jpg")
    out = F.step(st, {}, {"final_fix_썰템쇼판": {"ok": False, "대본줄": {"L3": {"tts": "짧은 줄.", "caps": ["짧은 줄"]}}}}, {})
    assert out["do"][0]["id"] == "save_script" and st["phase"] == "plan"


def test_final_fix_question_offers_line_way_not_more_material():
    assert "대본줄" in F.FINAL_FIX_WAYS and "재료_더찾기" not in F.FINAL_FIX_WAYS and "재료_더찾기" in F.PLAN_LOOK_WAYS


def test_task_material_uses_files_claude_added():
    st = _st()
    st["material"] = {"files": [{"name": "a.mp4"}]}
    st["_task"] = {"id": "task_1", "why": "x"}
    out = F.ph_task_got(st, {}, {"task_1": {"action": "material", "files": ["src/new.mp4"], "note": "직접 받음"}}, {})
    assert out["then"] == "more_sheets" and out["do"][0]["files"] == ["src/new.mp4"]


def test_channel_copy_refuses_bench_sentence():
    from tools.calcopy import bench_distance as BD
    B = BD.bench("banggu")
    txt = next(t for t in B["asr"].values() if len(BD._flat(t)) > 40)
    S = {"lines": [{"tts": txt[:60], "caps": [txt[:60]]}]}
    assert F._channel_copy("썰템홈샷판", S, {}) and not F._channel_copy("다른판", S, {})
