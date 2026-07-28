"""P1 모션레벨 순수함수 회귀(2026-07-28). ffmpeg 불필요 — 합성값으로 검증."""
from shopping_shorts import scene_cut as sc


def test_motion_thresholds_and_level():
    vals = list(range(0, 100))  # 0..99
    lo, hi = sc.motion_thresholds(vals, lo_q=0.5, hi_q=0.85)
    assert 48 <= lo <= 51          # 중앙값 근처
    assert 82 <= hi <= 86          # 85분위 근처
    assert sc.level_of(10, lo, hi) == "LOW"
    assert sc.level_of(60, lo, hi) == "MED"
    assert sc.level_of(95, lo, hi) == "PEAK"


def test_cut_motion_labels_and_peak():
    # 3컷: 저모션 / 고모션(피크) / 중간
    motion = {0: 1.0, 1: 2.0,          # 컷A [0,2): 낮음
              2: 90.0, 3: 99.0,        # 컷B [2,4): 피크(최대=99 @ frame3)
              4: 40.0, 5: 45.0}        # 컷C [4,6): 중간
    cuts = [(0, 2), (2, 4), (4, 6)]
    res = sc.cut_motion(cuts, motion)
    assert res[0]["level"] == "LOW"
    assert res[1]["level"] == "PEAK" and res[1]["peak_frame"] == 3
    assert res[2]["level"] == "MED"


def test_cut_motion_empty_cut_is_low_energy_zero():
    motion = {0: 5.0, 1: 6.0}
    res = sc.cut_motion([(10, 20)], motion)   # 이 컷엔 프레임 없음
    assert res[0]["energy"] == 0.0 and res[0]["peak_frame"] == 10


def test_pick_hook_start_peak_plus_delta_clamped():
    from shopping_shorts import video_assemble as va
    # 자동: 피크로 이동(delta 0)
    assert va.pick_hook_start(0.0, 5.0, base_time=2.0, delta=0.0, min_tail=1.0) == 2.0
    # 미세조정: 피크 + delta
    assert va.pick_hook_start(0.0, 5.0, base_time=2.0, delta=0.4, min_tail=1.0) == 2.4
    assert abs(va.pick_hook_start(0.0, 5.0, base_time=2.0, delta=-0.6, min_tail=1.0) - 1.4) < 1e-9
    # 끝-min_tail로 클램프
    assert va.pick_hook_start(0.0, 5.0, base_time=2.0, delta=5.0, min_tail=1.0) == 4.0
    # 시작으로 클램프(뒤로 너무 당김)
    assert va.pick_hook_start(2.0, 6.0, base_time=2.0, delta=-5.0, min_tail=1.0) == 2.0
    # 윈도우 좁으면 원위치
    assert va.pick_hook_start(0.0, 0.8, base_time=0.5, delta=0.0, min_tail=1.0) == 0.0
    # base None이면 시작 기준
    assert va.pick_hook_start(1.0, 5.0, base_time=None, delta=0.0) == 1.0


def test_hook_delta_reads_state_shapes():
    from shopping_shorts import video_assemble as va
    assert va._hook_delta({"hook_inpoint_delta": 0.4}) == 0.4
    assert va._hook_delta({"state": {"hook_inpoint_delta": -0.2}}) == -0.2
    assert va._hook_delta({}) == 0.0
    assert va._hook_delta(None) == 0.0
