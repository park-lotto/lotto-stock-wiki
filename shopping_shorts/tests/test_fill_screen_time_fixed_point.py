"""화면 길이 채우기(_fill_beat_screen_time)는 고정점이다 — 같은 편성에 두 번 돌려도 그대로(2026-10-05 관제 126).

★실측(job 2388dd0b9650·89dcb2d6f6b6): 화면 3.5초 = 대사 3.5초인데 소수점 오차로 '모자람'이 되어 저장할 때마다
  **길이 0초 조각**(3.733→3.73)을 하나씩 덧붙였다 — 길이가 안 늘어 다음 저장에도 또 붙었다(상한까지).
  저장 관문이 고정점이 아니라 렌더 도장이 깨졌다(관제 122: 렌더가 완성본을 스스로 버림)."""
import copy

from shopping_shorts import edit_plan as ep


def _seg_map():
    return {
        "s0-0": {"seg_id": "s0-0", "video_id": "s0", "start": 0.0, "end": 1.1666666, "scene_desc": "a"},
        "s0-1": {"seg_id": "s0-1", "video_id": "s0", "start": 1.1666666, "end": 3.5, "scene_desc": "b"},
        "s0-2": {"seg_id": "s0-2", "video_id": "s0", "start": 3.733, "end": 3.73, "scene_desc": "c"},   # 0초(끝<시작)
    }


def _beats():
    # 화면 1.1666666 + 2.3333334 = 3.4999999… < 3.5 (부동소수 오차)
    return [{"beat_idx": 0, "narration": "n", "target_seconds": 3.5,
             "primary": {"seg_id": "s0-0", "video_id": "s0", "start": 0.0, "end": 1.1666666},
             "alternates": [{"seg_id": "s0-1", "video_id": "s0", "start": 1.1666666, "end": 3.4999999}]}]


def test_float_shortfall_adds_nothing():
    b = _beats()
    out = ep._fill_beat_screen_time(copy.deepcopy(b), _seg_map(), max_alts=6)
    assert out[0]["alternates"] == b[0]["alternates"], "소수점 오차만큼 모자란 칸에 조각을 덧붙였다"


def test_zero_length_cut_never_added():
    """정말 모자라도 0초 조각은 채우지 못하니 붙이지 않는다(붙이면 저장마다 또 붙는다)."""
    b = _beats()
    b[0]["target_seconds"] = 5.0
    once = ep._fill_beat_screen_time(copy.deepcopy(b), _seg_map(), max_alts=6)
    ids = [a["seg_id"] for a in once[0]["alternates"]]
    assert "s0-2" not in ids
    twice = ep._fill_beat_screen_time(copy.deepcopy(once), _seg_map(), max_alts=6)
    assert twice[0]["alternates"] == once[0]["alternates"], "두 번째 채우기에서 또 바뀌었다 — 고정점이 아니다"


def test_still_fills_real_shortfall():
    """진짜 모자라면 종전처럼 채운다(회귀 방지)."""
    sm = _seg_map()
    sm["s0-3"] = {"seg_id": "s0-3", "video_id": "s0", "start": 4.0, "end": 6.0, "scene_desc": "d"}
    b = _beats()
    b[0]["target_seconds"] = 5.0
    out = ep._fill_beat_screen_time(copy.deepcopy(b), sm, max_alts=6)
    assert any(a["seg_id"] == "s0-3" for a in out[0]["alternates"])
    assert ep._beat_screen_secs(out[0]) >= 5.0 - ep._FILL_EPS
