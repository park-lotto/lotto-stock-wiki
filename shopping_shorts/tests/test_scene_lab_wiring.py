# -*- coding: utf-8 -*-
"""장면실험실 → 라이브 렌더 배선(2026-08-15) 회귀 테스트.

핵심 계약:
  ① scene_override/stretch_fill/scene_lab을 **모르는 기존 잡은 결과 불변** —
     _beat_material은 override 없으면 [primary]+alternates 그대로,
     _spread_stretch는 플래그 게이트 뒤에 있어 호출도 안 된다.
  ② 트림(✂ 가운데 잘라내기)은 재료를 '구멍 뺀 두 토막'으로 바꿀 뿐 —
     _plan_beat_clips 계산 규칙은 안 건드린다.
  ③ 예산(beat_screen_budget)은 override(=트림 반영 구간)로 계산 —
     안 그러면 없는 화면만큼 대본을 길게 뽑는다(_conform_beats 전제 붕괴).
"""
from shopping_shorts import edit_plan as ep
from shopping_shorts import mix_pipeline as mp
from shopping_shorts.video_assemble import (_MAX_SLOWMO, _beat_material, _plan_beat_clips,
                                            _spread_stretch)


def _beat(**kw):
    b = {"beat_idx": 0, "role": "hook", "narration": "멘트",
         "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 1.0, "end": 3.0},
         "alternates": [{"video_id": "s0", "seg_id": "s0-2", "start": 5.0, "end": 7.5}]}
    b.update(kw)
    return b


# ── ① 기존 잡 불변 ────────────────────────────────────────────────────────────

def test_material_default_is_primary_plus_alternates():
    b = _beat()
    segs = _beat_material(b)
    assert [s["seg_id"] for s in segs] == ["s0-1", "s0-2"]
    assert [(s["start"], s["end"]) for s in segs] == [(1.0, 3.0), (5.0, 7.5)]


def test_material_none_alternates_and_missing_keys():
    b = _beat(alternates=None)
    assert [s["seg_id"] for s in _beat_material(b)] == ["s0-1"]
    assert _beat_material({"beat_idx": 0}) == []          # primary조차 없어도 죽지 않는다


def test_budget_matches_old_formula_without_override():
    b = _beat()
    old = (2.0 + 2.5) * _MAX_SLOWMO                        # 종전 식 그대로
    assert abs(mp.beat_screen_budget(b) - old) < 1e-9


def test_spread_noop_without_deficit():
    plan = [{"video_id": "s0", "start": 0.0, "src_dur": 2.0, "out_dur": 2.0},
            {"video_id": "s0", "start": 2.0, "src_dur": 1.5, "out_dur": 1.5}]
    before = [dict(c) for c in plan]
    assert _spread_stretch(plan) == before                 # 부족분 없으면 그대로


# ── ② override·트림이 '재료'로만 작동 ─────────────────────────────────────────

def test_material_uses_override_when_present():
    over = [{"video_id": "s1", "seg_id": "s1-9", "start": 0.0, "end": 1.2},
            {"video_id": "s1", "seg_id": "s1-9", "start": 1.8, "end": 4.0}]
    b = _beat(scene_override=over)
    segs = _beat_material(b)
    assert [(s["start"], s["end"]) for s in segs] == [(0.0, 1.2), (1.8, 4.0)]
    # 반환은 사본 — 렌더가 만져도 edit_plan 원본이 안 더러워진다
    segs[0]["start"] = 99.0
    assert b["scene_override"][0]["start"] == 0.0


def test_trim_pieces_split_and_edges():
    seg = {"video_id": "s1", "seg_id": "s1-9", "start": 10.0, "end": 14.0}
    # 가운데 [1.2, 1.8] 구멍 → 앞토막 10.0~11.2 + 뒤토막 11.8~14.0
    p = ep._lab_trim_pieces(seg, [1.2, 1.8])
    assert [(x["start"], x["end"]) for x in p] == [(10.0, 11.2), (11.8, 14.0)]
    # 구멍이 앞끝에 붙으면 뒤토막만 / 뒤끝에 붙으면 앞토막만
    assert [(x["start"], x["end"]) for x in ep._lab_trim_pieces(seg, [0.0, 1.0])] == [(11.0, 14.0)]
    assert [(x["start"], x["end"]) for x in ep._lab_trim_pieces(seg, [3.0, 4.0])] == [(10.0, 13.0)]
    # 전부 잘려 나가면 원본 그대로(실험실 trimPieces와 같은 폴백)
    assert [(x["start"], x["end"]) for x in ep._lab_trim_pieces(seg, [0.0, 4.0])] == [(10.0, 14.0)]
    assert [(x["start"], x["end"]) for x in ep._lab_trim_pieces(seg, None)] == [(10.0, 14.0)]


def test_apply_and_revert_scene_lab_roundtrip():
    plan = {"beats": [_beat(), _beat(beat_idx=1)]}
    seg_map = {"s1-9": {"video_id": "s1", "seg_id": "s1-9", "start": 10.0, "end": 14.0,
                        "scene_desc": "컵", "is_key": True, "shot_role": "완성"},
               "s1-3": {"video_id": "s1", "seg_id": "s1-3", "start": 0.0, "end": 2.0,
                        "scene_desc": "뒤집기"}}
    orig_primary = dict(plan["beats"][0]["primary"])
    edits = {"beats": [{"beat_idx": 0, "list": ["s1-9", "s1-3", "유령seg"], "stretch": True},
                       {"beat_idx": 1, "list": [], "stretch": False}],   # 빈 칸은 안 건드림
             "trims": {"s1-9": [1.2, 1.8]}}
    ep.apply_scene_lab(plan, seg_map, edits)
    b0, b1 = plan["beats"]
    # 트림 두 토막 + 트림 없는 s1-3, 유령 seg는 걸러짐
    assert [(s["seg_id"], s["start"], s["end"]) for s in b0["scene_override"]] == \
        [("s1-9", 10.0, 11.2), ("s1-9", 11.8, 14.0), ("s1-3", 0.0, 2.0)]
    assert b0["stretch_fill"] is True
    assert b0["primary"] == orig_primary                   # 원본은 그대로(얹기만)
    assert "scene_override" not in b1 and "stretch_fill" not in b1
    assert plan["scene_lab"]["applied"] == 1
    # 예산이 트림 구멍을 뺀 재료로 바뀐다: (1.2 + 2.2 + 2.0) × 상한
    assert abs(mp.beat_screen_budget(b0) - (1.2 + 2.2 + 2.0) * _MAX_SLOWMO) < 1e-6
    # 되돌리면 100% 원상 — 렌더·예산 모두 종전과 동일
    ep.revert_scene_lab(plan)
    assert "scene_override" not in b0 and "stretch_fill" not in b0 and "scene_lab" not in plan
    assert [s["seg_id"] for s in _beat_material(b0)] == ["s0-1", "s0-2"]
    assert abs(mp.beat_screen_budget(b0) - (2.0 + 2.5) * _MAX_SLOWMO) < 1e-9


def test_planner_unchanged_with_trimmed_material():
    """트림 토막을 넣어도 _plan_beat_clips 규칙(라운드로빈·min_clip)은 그대로 돈다."""
    pieces = [{"video_id": "s1", "start": 10.0, "end": 11.2},
              {"video_id": "s1", "start": 11.8, "end": 14.0}]
    plan = _plan_beat_clips(pieces, 3.0, max_shot=2.2)
    assert sum(c["out_dur"] for c in plan) > 2.99          # 멘트 길이만큼 채운다
    for c in plan:                                         # 어떤 컷도 구멍(11.2~11.8)을 안 밟는다
        s, e = c["start"], c["start"] + c["src_dur"]
        in_piece1 = s >= 10.0 - 1e-6 and e <= 11.2 + 1e-6
        in_piece2 = s >= 11.8 - 1e-6 and e <= 14.0 + 1e-6
        assert in_piece1 or in_piece2, (s, e)


# ── ③ 늘려 채우기 재배분 ─────────────────────────────────────────────────────

def test_spread_stretch_distributes_deficit_evenly():
    # 재료 5.2초로 6.1초 멘트: 종전엔 마지막 컷이 부족분 0.9를 통째로 짊어졌다
    plan = [{"video_id": "s0", "start": 0.0, "src_dur": 1.6, "out_dur": 1.6},
            {"video_id": "s0", "start": 2.0, "src_dur": 2.2, "out_dur": 2.2},
            {"video_id": "s0", "start": 5.0, "src_dur": 1.4, "out_dur": 2.3}]
    _spread_stretch(plan)
    outs = [round(c["out_dur"], 2) for c in plan]
    assert outs == [1.88, 2.58, 1.64]                      # 실험실 실측과 같은 비례(6.1/5.2)
    assert abs(sum(c["out_dur"] for c in plan) - 6.1) < 1e-6   # 총 길이 불변(싱크 보존)


def test_spread_stretch_single_clip_untouched():
    plan = [{"video_id": "s0", "start": 0.0, "src_dur": 1.0, "out_dur": 3.0}]
    before = [dict(c) for c in plan]
    assert _spread_stretch(plan) == before                 # 1컷은 나눌 곳이 없다
