# -*- coding: utf-8 -*-
"""장면 골라 지우기 정본 — 한 칸 안에서 컷 일부만 고른 경우 (2026-09-28 job 52a1ef1723a8).

실사고: 고객이 32컷 중 18컷만 골라 지웠다. 모든 칸에 고른 컷이 하나 이상 있어 skip_beats 는 비었고, 렌더 컷 재생
(_remap_replay)은 칸 단위 skip 만 알아 **안 고른 컷**을 '못 덮은 구간'으로 쳤다 → 10칸 중 7칸 uncovered →
렌더 확인창 "새로 넣은 조각이 있는 장면 7개 … 18.1초 — 약 38크레딧"(고객이 안 지우기로 고른 장면을 돈 내고 지우라는 안내).
판단: 청소본에 없는 틈이 전부 안 고른 컷(cleaned:false) 자리면 원본 그대로 튼다 — clean_base.left_by_choice 한 곳.

곁(같은 꼴, cecc7b884bb0 7번 칸): 0.1초짜리 컷은 SPAN_TOL(0.12)보다 짧아 span_map 이 한 번도 안 돌아 None —
틈 계산은 "빈 곳 없음"인데 재생은 "못 덮음"이라 그 칸이 증분 청소로 갔다.
"""
import copy
import json
from pathlib import Path

from shopping_shorts import clean_base as cb

DATA = Path(__file__).parent / "fixtures" / "clean_base_job7bbb_manual.json"


def _load(tmp_path):
    d = json.loads(DATA.read_text(encoding="utf-8"))
    for bb in d["edit_plan"]["beats"]:
        bb.pop("cut_rhythm", None)
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = d["base"]
    base["path"] = str(tmp_path / "final_clean_x.mp4")
    (tmp_path / cb.BASE_FILE).write_text(json.dumps(base), encoding="utf-8")
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    return d["edit_plan"], cb.load_base(tmp_path), tts, d["src_durs"]


def _partial(base, unselected):
    """cuts 번호 unselected 만 안 고른(cleaned False) 부분 정본 — 모든 칸에 고른 컷이 남게(skip_beats 없음)."""
    b = copy.deepcopy(base)
    b["partial"] = True
    b["sel"] = ["x"]
    b["skip_beats"] = []
    b["cuts"] = [dict(c, cleaned=(i not in unselected)) for i, c in enumerate(b["cuts"])]
    return b


def test_unselected_cut_in_mixed_beat_is_not_recleaned(tmp_path):
    """8번 칸: 컷 13(s2 0.6초~) 안 고름 · 컷 14 고름 → 칸이 uncovered 가 아니고, 컷 13 자리는 **원본 s2 그대로**, 과금 구간 없음."""
    plan, base, tts, sd = _load(tmp_path)
    pb = _partial(base, {13})
    plan2, unc, _ = cb.remap_plan(plan, pb, tts_durs=tts, src_durs=sd)
    assert 8 not in unc and "8" not in plan2["_clean_need"], (unc, plan2["_clean_need"].get("8"))
    b8 = next(b for b in plan2["beats"] if b["beat_idx"] == 8)
    vids = [c["video_id"] for c in b8["manual_cuts"]]
    assert "s2" in vids and "clean" in vids, vids                       # 한 칸 안에 원본 컷 + 지운 컷
    orig = [c for c in b8["manual_cuts"] if c["video_id"] == "s2"]
    assert abs(orig[0]["start"] - 0.6) < 0.05                            # 안 고른 컷 자리 그대로
    assert any(m["video_id"] == "s2" for m in b8["scene_override"])      # 렌더가 원본 소스를 같이 받는 근거(_left)
    for b in plan2["beats"]:                                              # 안 지운 컷을 '지운 조각'으로 빌려 쓰지 않는다
        for c in b.get("manual_cuts") or []:
            if c["video_id"] == "clean":
                assert pb["cuts"][int(c["seg_id"].rsplit("-", 1)[1])]["cleaned"] is not False


def test_partial_base_new_material_still_charged(tmp_path):
    """편성을 바꿔 **어느 컷에도 없던** 원본을 읽게 된 칸은 종전대로 바뀐 장면(증분 청소·동의창) — 1번 칸 s2 5.07~7.70."""
    plan, base, tts, sd = _load(tmp_path)
    pb = _partial(base, {13})
    _plan2, unc, _ = cb.remap_plan(plan, pb, tts_durs=tts, src_durs=sd)
    assert 1 in unc


def test_left_by_choice_only_for_partial_and_only_inside_unselected_cuts(tmp_path):
    _plan, base, _tts, _sd = _load(tmp_path)
    m = {"video_id": "s2", "start": 0.6, "end": 2.5}
    assert cb.left_by_choice(base, m) is False                            # 전체 청소 정본에는 '안 고른 컷'이 없다
    pb = _partial(base, {13})
    assert cb.left_by_choice(pb, m) is True
    assert cb.left_by_choice(pb, {"video_id": "s2", "start": 0.6, "end": 3.5}) is True      # 뒤는 컷 1(지움)이 덮음
    assert cb.left_by_choice(pb, {"video_id": "s2", "start": 5.2, "end": 7.5}) is False     # 어느 컷에도 없던 원본


def test_sub_tolerance_clip_inside_cleaned_cut_is_covered():
    """0.1초 컷(SPAN_TOL 0.12보다 짧음)이 지운 컷 안에 있으면 덮인 것 — cecc7b884bb0 7번 칸 실데이터 좌표."""
    base = {"cuts": [
        {"video_id": "s6", "beat_idx": 7, "src": 22.667, "sdur": 1.201662, "dur": 1.44, "fin": 19.74},
        {"video_id": "s6", "beat_idx": 7, "src": 23.77, "sdur": 0.098662, "dur": 1.0, "fin": 21.18},
    ], "extras": {}}
    clip = {"video_id": "s6", "start": 23.77, "out_dur": 1.0, "src_dur": 0.0987}
    cuts, miss = cb.replay_clips(base, [clip])
    assert miss == [] and len(cuts) == 1 and cuts[0]["video_id"] == cb.CLEAN_VID, (cuts, miss)
    # 긴 컷은 종전과 같다(허용치 SPAN_TOL) — 지운 구간 밖이면 여전히 못 덮음
    cuts, miss = cb.replay_clips(base, [{"video_id": "s6", "start": 24.5, "out_dur": 1.0, "src_dur": 1.0}])
    assert cuts == [] and miss


def test_mostly_unselected_clip_plays_whole_original_not_split():
    """52a1 칸4 컷 s2 7.92~8.76(안 고름): 앞 0.19초가 옆 칸 지운 컷(s2 6.57~8.107) 끝에 걸쳐도 쪼개지 않고 **통째 원본** —
    조립본에서도 그 자리는 원본이었다(쪼개면 자막이 0.19초 사라졌다 나타나고 컷 수가 편집 화면보다 늘어난다)."""
    base = {"partial": True, "sel": ["x"], "skip_beats": [], "extras": {}, "cuts": [
        {"video_id": "s2", "beat_idx": 2, "src": 6.567, "sdur": 1.54, "dur": 1.53, "fin": 7.87, "cleaned": True},
        {"video_id": "s2", "beat_idx": 4, "src": 7.92, "sdur": 0.84, "dur": 0.83, "fin": 16.6, "cleaned": False},
    ]}
    cuts, miss = cb.replay_clips(base, [{"video_id": "s2", "start": 7.92, "out_dur": 0.83, "src_dur": 0.84}])
    assert miss == [] and len(cuts) == 1, (cuts, miss)
    assert cuts[0]["video_id"] == "s2" and abs(cuts[0]["start"] - 7.92) < 1e-3 and abs(cuts[0]["sdur"] - 0.84) < 1e-3
