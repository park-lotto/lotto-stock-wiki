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


def test_card_only_render_error_returns_to_thumb():
    st = {"version": "키치잇판", "tries": {}, "log": []}
    m = {"render": {"error": "썸네일 카드 B: 연예인 얼굴 아님(얼굴 0개 · a.mp4@80.00) — 얼굴이 크게 나온 장면으로 바꾼다"}}
    out = flow.ph_render_got(st, m, {}, None)
    assert out == {"goto": "thumb"}
    assert st["_thumb_bad"][0].startswith("썸네일 카드 B")
    st["tries"]["thumb"] = 2          # 썸네일 기회를 다 쓰면 예전 길(멈춤 쪽)로
    try:
        out2 = flow.ph_render_got(st, m, {}, None)
    except Exception:          # 예전 길 = 재료 고치기 요청(대본 없는 이 시험 st 에선 KeyError) — 썸네일로 안 가면 된다
        out2 = None
    assert out2 != {"goto": "thumb"}


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


def test_card_rejects_after_thumb_tries_render_without_card():
    """⑤ 썸네일 기회를 다 쓴 뒤 카드 반려 = ph_thumb_got 과 같은 규칙(카드 없이 렌더) — 멈추지 않는다."""
    st = {"version": "키치잇판", "tries": {"thumb": 2}, "log": []}
    m = {"render": {"error": "썸네일 카드 A: 연예인 얼굴 아님(얼굴 0개 · a.mp4@80.00) — 얼굴이 크게 나온 장면으로 바꾼다"}}
    out = flow.ph_render_got(st, m, {}, None)
    assert out["then"] == "render" and out["do"][0]["files"] == {"키치잇판/썸네일.json": {"options": []}}
