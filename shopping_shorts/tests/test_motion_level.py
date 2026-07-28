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


def test_pick_hook_start_uses_peak_then_override_clamped():
    from shopping_shorts import video_assemble as va
    # 자동: 피크 시각으로 이동하되 끝-min_tail로 클램프
    assert va.pick_hook_start(0.0, 5.0, peak_time=2.0, override=None, min_tail=1.0) == 2.0
    assert va.pick_hook_start(0.0, 5.0, peak_time=4.8, override=None, min_tail=1.0) == 4.0  # 끝 클램프
    # 오버라이드가 피크를 이긴다
    assert va.pick_hook_start(0.0, 5.0, peak_time=2.0, override=3.0, min_tail=1.0) == 3.0
    # 윈도우가 좁으면(≤min_tail) 원위치
    assert va.pick_hook_start(0.0, 0.8, peak_time=0.5, override=None, min_tail=1.0) == 0.0
    # 아무 것도 없으면 원위치
    assert va.pick_hook_start(1.0, 5.0, peak_time=None, override=None) == 1.0
    # 시작보다 앞선 후보는 시작으로 클램프
    assert va.pick_hook_start(2.0, 6.0, peak_time=1.0, override=None, min_tail=1.0) == 2.0


def test_hook_override_reads_state_shapes():
    from shopping_shorts import video_assemble as va
    assert va._hook_override({"hook_inpoint": 2.5}) == 2.5
    assert va._hook_override({"state": {"hook_inpoint": 3.5}}) == 3.5
    assert va._hook_override({}) is None
    assert va._hook_override(None) is None
