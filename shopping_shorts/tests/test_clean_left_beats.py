# -*- coding: utf-8 -*-
"""mix_pipeline.clean_left_beats — 자막제거 job에서 원본 재료(자막 있음)로 나갈 칸 분류(2026-09-28).

관문 구멍: 영상 비교는 원본을 틀어 장면이 같게 나와 "청소본이 있어야 할 칸인데 원본"을 못 본다(52a1ef1723a8 7칸 통과).
  자막 남음(결함) = 편성은 청소 때 그대로인데 못 덮음 · 덮인 칸의 원본 조각이 고객이 안 고른 컷 자리가 아님
  증분 대기 = 청소 뒤 편성이 바뀐 칸(렌더 때 동의창) · 고른 원본 = 고객이 안 지우기로 고른 칸/컷 · 원인 미상 = 스냅샷 없음
"""
import copy
import json
from pathlib import Path

from shopping_shorts import clean_base as cb
from shopping_shorts import mix_pipeline as mp

DATA = Path(__file__).parent / "fixtures" / "clean_base_job7bbb_manual.json"


def _setup(tmp_path, *, partial_unselected=None, snapshot="same"):
    d = json.loads(DATA.read_text(encoding="utf-8"))
    plan = d["edit_plan"]
    for bb in plan["beats"]:
        bb.pop("cut_rhythm", None)
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = d["base"]
    base["path"] = str(tmp_path / "final_clean_x.mp4")
    (tmp_path / cb.BASE_FILE).write_text(json.dumps(base), encoding="utf-8")
    base = cb.load_base(tmp_path)
    if partial_unselected is not None:
        base = copy.deepcopy(base)
        base.update(partial=True, sel=["x"], skip_beats=[])
        base["cuts"] = [dict(c, cleaned=(i not in partial_unselected)) for i, c in enumerate(base["cuts"])]
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    if snapshot is not None:
        snap = copy.deepcopy(plan)
        if snapshot == "beat1_changed":
            b1 = next(b for b in snap["beats"] if b["beat_idx"] == 1)
            for c in b1.get("manual_cuts") or []:
                c["dur"] = round(float(c["dur"]) * 0.5, 3)      # 청소 때는 컷 길이가 달랐다 → 렌더 컷 계획이 다르다
        mp._clean_plan_snapshot_path(tmp_path, base["sig"]).write_text(json.dumps(snap), encoding="utf-8")
    plan2, unc, ext = cb.remap_plan(plan, base, tts_durs=tts, src_durs=d["src_durs"])
    judged = {"base": base, "plan2": plan2, "uncovered": unc, "extend": ext, "tts_durs": tts,
              "src_durs": d["src_durs"], "tier_upgrade": False}
    return {"edit_plan": plan, "subtitle_removal": True}, judged, unc


def test_uncovered_with_unchanged_plan_is_left(tmp_path):
    """스냅샷 편성 = 지금 편성인데 못 덮은 칸 = 자막 남음(결함). 픽스처 1·2·3·6·7번 칸."""
    job, judged, unc = _setup(tmp_path)
    r = mp.clean_left_beats(None, job, tmp_path, judged=judged)
    assert unc and sorted(r["left"]) == sorted(unc), r
    assert r["pending"] == [] and r["unknown"] == []


def test_changed_since_clean_is_pending_not_left(tmp_path):
    """청소 뒤 그 칸의 렌더 컷 계획이 바뀌었으면 증분 대기(렌더 때 동의창) — 결함으로 세지 않는다."""
    job, judged, _unc = _setup(tmp_path, snapshot="beat1_changed")
    r = mp.clean_left_beats(None, job, tmp_path, judged=judged)
    assert 1 in r["pending"] and 1 not in r["left"], r


def test_no_snapshot_is_unknown(tmp_path):
    job, judged, unc = _setup(tmp_path, snapshot=None)
    r = mp.clean_left_beats(None, job, tmp_path, judged=judged)
    assert sorted(r["unknown"]) == sorted(unc) and r["left"] == [], r


def test_unselected_cut_played_original_is_chosen(tmp_path):
    """부분 정본에서 안 고른 컷(컷 13)을 원본으로 튼 8번 칸 = 고른 원본(결함 아님)."""
    job, judged, _unc = _setup(tmp_path, partial_unselected={13})
    r = mp.clean_left_beats(None, job, tmp_path, judged=judged)
    assert 8 in r["chosen"] and 8 not in r["left"], r


def test_old_bug_52a1_is_caught_as_left(tmp_path, monkeypatch):
    """52a1 결함 재현: 안 고른 컷 판단(left_by_choice)이 없던 코드는 8번 칸을 못 덮음으로 본다 — 편성은 그대로라 **자막 남음**.
    (종전 관문은 영상 비교가 원본을 틀어 장면이 같아 이걸 통과시켰다)"""
    monkeypatch.setattr(cb, "left_by_choice", lambda base, m: False)
    job, judged, unc = _setup(tmp_path, partial_unselected={13})
    assert 8 in unc
    r = mp.clean_left_beats(None, job, tmp_path, judged=judged)
    assert 8 in r["left"], r


def test_covered_beat_with_raw_material_not_by_choice_is_left(tmp_path):
    """덮였다는 칸인데 원본 재료가 남았고 그게 안 고른 컷 자리가 아니면 결함(자막 남음) — 전체 청소 정본."""
    job, judged, unc = _setup(tmp_path)
    b0 = next(b for b in judged["plan2"]["beats"] if b["beat_idx"] == 0)
    assert 0 not in unc
    b0["manual_cuts"] = [dict(c, video_id="s1", start=0.0, sdur=c.get("sdur") or c["dur"]) for c in b0["manual_cuts"]]
    r = mp.clean_left_beats(None, job, tmp_path, judged=judged)
    assert 0 in r["left"], r


def test_not_applicable_when_judge_none(tmp_path, monkeypatch):
    monkeypatch.setattr(mp, "clean_base_judge", lambda *a, **k: None)
    assert mp.clean_left_beats(None, {"edit_plan": {}}, tmp_path) is None
