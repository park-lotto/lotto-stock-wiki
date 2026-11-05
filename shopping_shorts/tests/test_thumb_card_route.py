"""10-26 이미숙 회원편(관제263) — 렌더 길 썸네일 카드 관문 두 구멍.
① card_scene_frame 이 crop 'face' 글자를 ffmpeg crop 에 그대로 넣어 '프레임 못 뽑음'(칸 주인 render_bench.cut_crop 을 안 부름).
② 카드 반려가 render_fix(재료만 받음)로 가서 회원 AI 가 고친 썸네일이 버려지고 멈춤 → 썸네일 단계로 되돌린다."""
import subprocess
from pathlib import Path

import numpy as np

from tools.calcopy.hybrid import flow, render_bench, thumb


def test_card_frame_face_crop_goes_through_cut_crop(monkeypatch):
    seen = {}
    monkeypatch.setattr(render_bench, "cut_crop", lambda c, src, win: [12, 0, 1080, 1080])

    def fake_run(cmd, **kw):
        seen["vf"] = cmd[cmd.index("-vf") + 1]
        return subprocess.CompletedProcess(cmd, 0, stdout=bytes(8 * 8 * 3))
    monkeypatch.setattr(thumb.subprocess, "run", fake_run)
    T = {"cuts": [{"line": "O2", "src": "a.mp4", "ss": 119, "crop": "face", "dur": 2.0, "kind": "orig"}]}
    im, where = thumb.card_scene_frame({"part": 0, "t": 0.6}, T, Path("."), (8, 8))
    assert "crop=1080:1080:12:0" in seen["vf"]
    assert im is not None and im.shape == (8, 8, 3)


def test_card_only_render_error_auto_picks_not_back_to_thumb():
    """② 카드 반려 → 썸네일 단계로 되돌리지 않고 코드 자동 고르기(thumb_auto) 뒤 곧장 렌더(관제263 10-26 '썸네일 까다로운 것도 문제')."""
    st = {"version": "키치잇판", "tries": {}, "log": []}
    m = {"render": {"error": "썸네일 카드 B: 연예인 얼굴 아님(얼굴 0개 · a.mp4@80.00) — 얼굴이 크게 나온 장면으로 바꾼다"}}
    out = flow.ph_render_got(st, m, {}, None)
    assert out.get("goto") != "thumb"
    assert [d["cmd"] for d in out["do"]] == ["thumb_auto"] and out["then"] == "render"
    assert st["_thumb_auto"] is True


def test_render_fix_nothing_to_fix_renders_again(monkeypatch):
    """③ 검수가 '재료 이상 없음'(ok true, 재료 null)이면 같은 재료로 다시 굽는다 — 예전엔 멈춰서 '다시 시도'가 이 질문만 되풀이했다."""
    st = {"version": "키치잇판", "tries": {"render": 1}, "log": []}
    monkeypatch.setattr(flow, "_reply", lambda rp, rid, need=(): {"ok": True, "problems": [], "재료": None})
    assert flow.ph_render_fix(st, {}, {}, None) == {"goto": "render"}
    st["tries"]["render"] = flow.LIMITS["render"]          # 렌더 기회를 다 쓰면 예전처럼 멈춤
    try:
        flow.ph_render_fix(st, {}, {}, None)
        stopped = False
    except flow._Stop:
        stopped = True
    assert stopped
    monkeypatch.setattr(flow, "_reply", lambda rp, rid, need=(): {"ok": False, "problems": ["x"], "재료": None})
    st["tries"]["render"] = 1                               # 고칠 게 있다면서 재료를 안 주면 멈춤 그대로
    try:
        flow.ph_render_fix(st, {}, {}, None)
        stopped = False
    except flow._Stop:
        stopped = True
    assert stopped


def test_stale_sheet_replans_before_thumb():
    """④ 재료가 계획 시트 뒤에 바뀌면(_sheet_stale) 옛 카드를 비우고 계획을 다시 돌려 새 시트로 썸네일을 묻는다
    (10-26 이미숙: 옛 시트 part 8 = 얼굴 근접, 바뀐 재료에선 앰플 병 → 카드 얼굴 반려 되풀이)."""
    st = {"version": "키치잇판", "tries": {}, "log": [], "_sheet_stale": True, "_plan_sheet": "old.jpg"}
    out = flow.ph_thumb(st, {}, {}, None)
    assert out["then"] == "thumb_sheet"
    assert [d["cmd"] for d in out["do"]] == ["write_doc", "plan"]
    assert out["do"][0]["files"] == {"키치잇판/썸네일.json": {"options": []}}
    out2 = flow.ph_thumb_sheet(st, {"plan": {"sheet": "new.jpg", "cuts": 20}}, {}, None)
    assert out2 == {"goto": "thumb"} and st["_plan_sheet"] == "new.jpg" and "_sheet_stale" not in st
    assert flow.PHASE_STAGE["thumb_sheet"] == "plan"


def test_card_rejects_after_auto_card_render_without_card():
    """⑤ 자동 카드까지 반려면 카드 없이 렌더 — 멈추지도, 되돌아가지도 않는다."""
    st = {"version": "키치잇판", "tries": {}, "log": [], "_thumb_auto": True}
    m = {"render": {"error": "썸네일 카드 A: 연예인 얼굴 아님(얼굴 0개 · a.mp4@80.00) — 얼굴이 크게 나온 장면으로 바꾼다"}}
    out = flow.ph_render_got(st, m, {}, None)
    assert out["then"] == "render" and out["do"][0]["files"] == {"키치잇판/썸네일.json": {"options": []}}


def _ask_ok():
    o = lambda i, ax: {"id": i, "axis": ax, "mood": "wow", "part": 1, "t": 0.5, "circle": [[100, 100, 50]], "text": [{"lines": ["진짜야??"], "xy": [540, 300]}]}
    return {"options": [o("A", "인물순간"), o("B", "물건근접"), o("C", "황당사실")]}


def test_thumb_answer_used_once_else_auto():
    """⑥ AI 답은 한 번만 — 통과면 그대로 저장, 반려·없음이면 되묻지 않고 thumb_auto(반려 안의 쓸 만한 글은 넘긴다)."""
    st = {"version": "키치잇판", "tries": {}, "log": [], "_n_cuts": 5}
    out = flow.ph_thumb_got(st, {}, {"thumb_키치잇판": {"썸네일": _ask_ok()}}, None)
    assert out["do"][0]["cmd"] == "write_doc" and out["then"] == "render"
    bad = _ask_ok(); bad["options"] = bad["options"][:2]          # 2안 = 반려
    st2 = {"version": "키치잇판", "tries": {}, "log": [], "_n_cuts": 5}
    out2 = flow.ph_thumb_got(st2, {}, {"thumb_키치잇판": {"썸네일": bad}}, None)
    assert out2.get("goto") != "thumb" and out2["do"][0]["cmd"] == "thumb_auto" and out2["then"] == "render"
    assert out2["do"][0]["text"] == [{"lines": ["진짜야??"], "xy": [540, 300]}]
    st3 = {"version": "키치잇판", "tries": {}, "log": []}
    out3 = flow.ph_thumb_got(st3, {}, {}, None)                   # 답 없음 = 멈춤 아님
    assert out3["do"][0]["cmd"] == "thumb_auto" and "text" not in out3["do"][0]
    assert "thumb_auto" in __import__("tools.calcopy.hybrid.runner_ops", fromlist=["CMDS"]).CMDS


def test_auto_pick_takes_gate_ok_biggest_face(monkeypatch):
    """⑦ thumb.auto_pick — 관문 자(judge) 통과 프레임 중 score 큰 것. 관문 자 × 인 더 큰 점수는 뒤로. 얼굴 없으면 None(카드 없이)."""
    marks = {}
    keys = [(0, 0.5), (0, 1.0), (1, 0.5), (1, 1.0), (2, 1.0), (2, 2.0)]   # 컷 길이 2·2·4초 × AUTO_AT(0.25, 0.5)
    monkeypatch.setattr(thumb, "AUTO_AT", (0.25, 0.5))
    monkeypatch.setattr(thumb, "_detector", lambda: None)
    monkeypatch.setattr(render_bench, "frame_window", lambda f: (0, 0, 4, 4))
    monkeypatch.setattr(thumb, "card_scene_frame", lambda opt, T, cand, wh: (np.full((4, 4, 3), keys.index((opt["part"], opt["t"])), np.uint8), "x"))
    monkeypatch.setattr(thumb, "faces_of", lambda det, im: [keys[int(im[0, 0, 0])]])
    monkeypatch.setattr(thumb, "judge", lambda fs, W, H, min_frac=0: (marks.get(fs[0], (False, -1.0))[0], "", {"h_frac": 0.3}))
    monkeypatch.setattr(thumb, "score", lambda det, im: (marks.get(keys[int(im[0, 0, 0])], (False, -1.0))[1], {}))
    T = {"cuts": [{"dur": 2.0}, {"dur": 2.0}, {"dur": 4.0}]}
    marks.update({(0, 0.5): (False, 2.0), (1, 0.5): (True, 5.0), (1, 1.0): (True, 7.5), (2, 1.0): (False, 9.0)})
    best = thumb.auto_pick({"frame": {}}, T, Path("."), log=lambda s: None)
    assert (best["part"], best["t"]) == (1, 1.0) and best["auto"] is True
    marks.clear()
    assert thumb.auto_pick({"frame": {}}, T, Path("."), log=lambda s: None) is None
