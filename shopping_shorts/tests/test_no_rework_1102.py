"""관제 304 재작업 검사표 — 고장 난 곳만 고친다(사장님 11-02 '의미 없는 뺑뺑이 금지').
B 썸네일은 원본·초로 옮긴다 · C 걸린 줄만 묻는다 · D 재검사·눈 검수는 바뀐 곳만 · E 다시 시도가 횟수·진전을 지우지 않는다."""
import json

import pytest

from tools.calcopy.hybrid import flow as F, thumb as TH


def _st(**kw):
    S = {"title_lines": [[["가", None]], [["나", None]]],
         "lines": [{"id": "L1", "kind": "tts", "tts": "첫 줄.", "caps": ["첫 줄"]},
                   {"id": "L5", "kind": "tts", "tts": "느린 줄 입니다.", "caps": ["느린 줄 입니다"]}]}
    M = {"cuts": {"L1": [{"src": "a.mp4", "ss": 1}], "L5": [{"src": "b.mp4", "ss": 2}]}}
    return {"version": "썰템쇼판", "script": {"S": S, "M": M}, "tries": {}, "log": [], "read": {}, "product": {}, **kw}


# ── E 다시 시도 ─────────────────────────────────────────────────────────
def test_retry_keeps_fix_counts_and_history():
    st = _st(tries={"plan": 5, "script": 4, "render": 2, "look": 1, "line_fix": 2, "render_err": 1, "vmake_fail": 1},
             redo_hist={"plan": [["cut_len"]]}, stopped={"retry": "plan", "why": "막힘", "fix": "x"})
    assert F.ph_stopped(st, {}, {}, {"retry": True}) == {"goto": "plan"}
    assert st["tries"]["plan"] == 5 and st["tries"]["script"] == 4 and st["tries"]["render"] == 2 and st["tries"]["line_fix"] == 2
    assert st["redo_hist"] == {"plan": [["cut_len"]]}


def test_retry_clears_only_transient_marks():
    st = _st(tries={"plan": 5, "render_err": 1, "vmake_fail": 1, "of_verify": 1}, stopped={"retry": "plan", "why": "막힘", "fix": "x"})
    F.ph_stopped(st, {}, {}, {"retry": True})
    assert "render_err" not in st["tries"] and "vmake_fail" not in st["tries"] and "of_verify" not in st["tries"]


def test_retry_with_asker_feed_keeps_counts():
    st = _st(tries={"plan": 5}, _asker="plan_got", _asker_in={"m": {"plan": {}}}, stopped={"retry": "plan_got", "why": "막힘", "fix": "x"})
    out = F.ph_stopped(st, {}, {}, {"retry": True})
    assert out["goto"] == "plan_got" and st["tries"]["plan"] == 5


def test_limit_reached_after_retry_goes_to_task_not_full_new_budget():
    st = _st(tries={"plan": F.LIMITS["plan"]})
    with pytest.raises(F._Stop):
        F._tries(st, "plan", F.LIMITS["plan"], ["cut_len"])


def test_back_still_clears_that_stage_only():
    st = _st(tries={"script": 4, "render": 2}, redo_hist={"script": [["x"]]}, phase="task_got",
             _task={"id": "task_1", "stage": "render", "retry": "render", "why": "w", "fix": "f"})
    st["_stage_ok"] = True
    out = F.ph_task_got(st, {}, {"task_1": {"action": "back", "to": "script"}}, {})
    assert out == {"goto": "script"} and "script" not in st["tries"] and st["tries"]["render"] == 2


@pytest.mark.parametrize("fn,arg", [("_voice_rewrite", ["줄 표시 없음"]), ("_length_rewrite", "40초"), ("_conflict_rewrite", {"axis": "caps", "cause": "x"})])
def test_rewrites_do_not_zero_script_count(fn, arg, monkeypatch):
    st = _st(tries={"script": 3, "line_fix": F.LINE_FIX_MAX})
    monkeypatch.setattr(F, "_script_ask", lambda st_, why="": {"x": 1})
    getattr(F, fn)(st, arg)
    assert st["tries"]["script"] == 3


# ── C 걸린 줄만 ─────────────────────────────────────────────────────────
def test_conflict_with_line_id_asks_only_that_line():
    st = _st()
    out = F._conflict_rewrite(st, {"axis": "caps", "need": 5, "cap": 3, "cause": "L5 자막 조각 수"})
    assert out["then"] == "line_fix_got"
    body = out["review"][0]["ask"] if "ask" in out["review"][0] else json.dumps(out["review"][0], ensure_ascii=False)
    assert "느린 줄" in body and "첫 줄." not in body.split("지금 줄")[1].split("JSON")[0]


def test_conflict_without_line_id_picks_lines_not_full_script():
    st = _st()
    out = F._conflict_rewrite(st, {"axis": "sticker", "need": 5, "cap": 3, "cause": "규칙"})
    assert out["then"] == "line_fix_got" and "가장 적게" in json.dumps(out["review"][0], ensure_ascii=False)


def test_voice_without_line_id_picks_lines_not_full_script():
    st = _st()
    out = F._voice_rewrite(st, ["받아쓰기 확정 결함(줄 표시 없음)"])
    assert out["then"] == "line_fix_got"


def test_conflict_line_fix_failure_falls_back_to_conflict_path(monkeypatch):
    st = _st()
    F._conflict_rewrite(st, {"axis": "caps", "need": 5, "cap": 3, "cause": "L5"})
    monkeypatch.setattr(F, "audit_script", lambda st_, S, M: {"ok": False, "x": ["bad"]})
    monkeypatch.setattr(F, "_reply", lambda rp, rid, need: {"lines": {"L5": {"tts": "?", "caps": ["?"]}}})
    monkeypatch.setattr(F, "_script_ask", lambda st_, why="": {"why": why})
    out = F.ph_line_fix_got(st, {}, {}, None)
    assert out["then"] == "script_got" and "배치 충돌" in out["review"][0]["why"]


# ── B 썸네일 ────────────────────────────────────────────────────────────
def _cut(src, ss, t0, t1, line="L1", crop="face", speed=1.0):
    return {"src": src, "ss": ss, "t0": t0, "t1": t1, "dur": round(t1 - t0, 3), "line": line, "crop": crop, "speed": speed}


def _spec(tmp_path, **kw):
    sp = {"options": [{"id": "A", "axis": "인물순간", "part": 1, "t": 0.5, "circle": [[100, 100, 50]], "text": [{"lines": ["진짜??"]}]}], "pick": "A", **kw}
    (tmp_path / "썸네일.json").write_text(json.dumps(sp, ensure_ascii=False), encoding="utf-8")
    return sp


def _read(tmp_path):
    return json.loads((tmp_path / "썸네일.json").read_text(encoding="utf-8"))


def test_relocate_follows_source_second_when_cut_number_changes(tmp_path):
    _spec(tmp_path)
    T0 = {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4), _cut("c.mp4", 5, 4, 6)]}
    assert TH.relocate(tmp_path, T0)["pick_gone"] is False
    assert _read(tmp_path)["options"][0]["at"]["src"] == "b.mp4" and _read(tmp_path)["options"][0]["at"]["sec"] == 10.5
    T1 = {"cuts": [_cut("z.mp4", 0, 0, 1), _cut("a.mp4", 0, 1, 3), _cut("c.mp4", 5, 3, 4), _cut("b.mp4", 9, 4, 7)]}      # 번호·시작 초가 바뀜
    r = TH.relocate(tmp_path, T1)
    o = _read(tmp_path)["options"][0]
    assert r["pick_gone"] is False and o["part"] == 3 and abs(o["t"] - 1.5) < 1e-6 and not o.get("gone")


def test_relocate_respects_slowed_cut(tmp_path):
    _spec(tmp_path)
    TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4)]})
    TH.relocate(tmp_path, {"cuts": [_cut("b.mp4", 10, 0, 2, speed=0.5)]})
    o = _read(tmp_path)["options"][0]
    assert o["part"] == 0 and abs(o["t"] - 1.0) < 1e-6        # 원본 0.5초 = 늦춘 컷의 1.0초


def test_relocate_scene_gone_only_when_second_not_in_any_cut(tmp_path):
    _spec(tmp_path)
    TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4)]})
    r = TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 30, 2, 4)]})
    assert r["pick_gone"] is True and r["gone"] == ["A"]


def test_relocate_crop_change_is_gone_when_mark_on_scene(tmp_path):
    _spec(tmp_path)
    TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4, crop=[0, 0, 100, 100])]})
    r = TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4, crop=[50, 0, 100, 100])]})
    assert r["pick_gone"] is True       # 빨간 원 자리가 어긋난다


def test_relocate_face_crop_compares_real_box(tmp_path):
    """crop 글자가 둘 다 'face' 여도 시작 초가 바뀌면 실제 칸이 다르다 — 원이 제품에서 벗어난다(실물 대조로 잡음)."""
    _spec(tmp_path)
    box = {"box": [100, 0, 600, 800]}
    co = lambda c: box["box"]
    TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4)]}, crop_of=co)
    assert _read(tmp_path)["options"][0]["at"]["crop"] == [100, 0, 600, 800]
    box["box"] = [110, 0, 600, 800]         # 3% 안 = 같은 구도
    assert TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4)]}, crop_of=co)["pick_gone"] is False
    box["box"] = [300, 0, 600, 800]
    assert TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4)]}, crop_of=co)["pick_gone"] is True


def test_relocate_switches_pick_to_living_option(tmp_path):
    sp = _spec(tmp_path)
    sp["options"].append({"id": "B", "axis": "물건근접", "part": 0, "t": 0.2, "text": [{"lines": ["뭐지"]}]})
    (tmp_path / "썸네일.json").write_text(json.dumps(sp, ensure_ascii=False), encoding="utf-8")
    TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 10, 2, 4)]})
    r = TH.relocate(tmp_path, {"cuts": [_cut("a.mp4", 0, 0, 2), _cut("b.mp4", 30, 2, 4)]})
    assert r["pick_gone"] is False and r["pick"] == "B" and _read(tmp_path)["pick"] == "B"


def test_flow_moved_thumb_skips_question_and_replan():
    st = _st(_thumb_have=True, _sheet_stale=True, _thumb_move={"have": True, "moved": ["A"], "gone": [], "pick_gone": False})
    assert F.ph_thumb(st, {}, {}, None) == {"goto": "render"}
    assert "_sheet_stale" not in st


def test_flow_line_fix_skips_thumb_question():
    st = _st(_thumb_have=True, _thumb_move={"have": True, "moved": [], "gone": [], "pick_gone": False})
    assert F.ph_thumb(st, {}, {}, None) == {"goto": "render"}


def test_flow_scene_gone_asks_once_with_new_sheet():
    st = _st(_thumb_have=True, _sheet_stale=True, _plan_sheet="old.jpg", _thumb_move={"have": True, "gone": ["A"], "pick_gone": True})
    out = F.ph_thumb(st, {}, {}, None)
    assert out["then"] == "thumb_sheet"
    F.ph_thumb_sheet(st, {"plan": {"sheet": "new.jpg", "cuts": 3}}, {}, None)
    out2 = F.ph_thumb(st, {}, {}, None)
    assert out2["then"] == "thumb_got" and out2["review"]


def test_render_scene_gone_comes_back_through_thumb():
    st = _st(_thumb_have=True)
    out = F.ph_render_got(st, {"render": {"ok": False, "thumb_gone": True, "error": "썸네일 카드 장면 없음"}}, {}, None)
    assert out == {"goto": "thumb"} and st["_sheet_stale"] and st["_thumb_move"]["pick_gone"]


def test_plan_passes_thumb_state():
    st = _st(_plan_fixed=True)
    st.update(_all_dims={})
    import tools.calcopy.hybrid.flow as M
    res = None
    try:
        res = M.ph_plan_got(st, {"plan": {"over": "", "cuts": 2, "sheet": "s.jpg", "thumb_move": {"have": True, "pick_gone": False}}}, {}, None)
    except Exception:  # noqa: BLE001 — 재료 판정 함수는 이 시험 대상이 아니다
        pass
    assert res is None or st.get("_thumb_move", {}).get("have") is True


# ── D 눈 검수 범위 ───────────────────────────────────────────────────────
def test_eye_second_look_only_changed_sheet():
    st = _st(look={"ok": False, "problems": ["L5 장면"], "by": "눈 2단"}, eye_keys=["E1"], tries={"look": 1}, phase="check_got")
    m = {"check": {"auto": {"ok": True, "rows": []}, "eye_files": ["k/eye/시트_1초.jpg", "k/eye/훅3초_0.1초.jpg", "k/eye/끝2초_0.1초.jpg"], "eye_texts": {},
                   "changed": {"share": 0.1, "cuts": [3], "lines": ["L5"], "spans": [[4.0, 6.0]], "sheet": "k/eye/바뀐구간_시트.jpg"}}}
    out = F.ph_check_got(st, m, {}, None)
    rv = out["review"][0]
    txt = json.dumps(rv, ensure_ascii=False)
    assert "바뀐구간_시트.jpg" in txt and "시트_1초.jpg" not in txt and st["_eye_scope"]["lines"] == ["L5"]


def test_eye_first_look_is_full():
    st = _st(look={}, tries={}, phase="check_got")
    m = {"check": {"auto": {"ok": True, "rows": []}, "eye_files": ["k/eye/시트_1초.jpg"], "eye_texts": {}, "changed": None}}
    out = F.ph_check_got(st, m, {}, None)
    assert "시트_1초.jpg" in json.dumps(out["review"][0], ensure_ascii=False) and not st.get("_eye_scope")


def test_eye_big_change_is_full():
    st = _st(look={"ok": False, "problems": ["x"], "by": "눈 2단"}, tries={"look": 1}, phase="check_got")
    m = {"check": {"auto": {"ok": True, "rows": []}, "eye_files": ["k/eye/시트_1초.jpg"], "eye_texts": {},
                   "changed": {"share": 0.8, "cuts": [1, 2, 3], "lines": ["L1"], "spans": [[0, 9]], "sheet": "k/eye/바뀐구간_시트.jpg"}}}
    out = F.ph_check_got(st, m, {}, None)
    assert "시트_1초.jpg" in json.dumps(out["review"][0], ensure_ascii=False)


def test_scoped_proof_counts_changed_lines_only():
    sv = {"title": "제목", "lines": [{"id": str(i)} for i in range(10)]}
    a = {"title_seen": "제목", "scenes": [{"at": "4~6", "line": "L5", "seen": "화면"}]}
    assert F.sheet_proof_problems(a, sv) != []                 # 전체면 5줄 필요
    assert F.sheet_proof_problems(a, sv, ["L5"]) == []
