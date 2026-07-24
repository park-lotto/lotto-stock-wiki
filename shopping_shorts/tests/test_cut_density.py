"""컷 밀도(2026-07-22 벤치마크): 긴 정지(7초 홀드) 대신 max_shot으로 distinct 세그먼트를
번갈아 재생해 컷을 만든다. 포인트 비트는 홀드(라운드로빈 안 함)."""
from shopping_shorts import video_assemble as va


def _seg(vid, start, end):
    return {"video_id": vid, "start": start, "end": end}


def test_no_shot_longer_than_max():
    # 세그 2개(각 4초)로 7초 채우기 — max_shot=2 → 어떤 컷도 2초 초과 없음.
    segs = [_seg("s0", 0, 4), _seg("s1", 0, 4)]
    plan = va._plan_beat_clips(segs, 7.0, max_shot=2.0)
    assert plan, "클립 계획 비면 안 됨"
    assert all(c["src_dur"] <= 2.0 + 1e-6 for c in plan)     # 정지 없음
    assert round(sum(c["out_dur"] for c in plan), 2) == 7.0   # 길이 채움


def test_round_robin_alternates_sources():
    # 컷이 세그먼트를 번갈아(s0→s1→s0…) → distinct 앵글로 컷.
    segs = [_seg("s0", 0, 4), _seg("s1", 0, 4)]
    plan = va._plan_beat_clips(segs, 6.0, max_shot=2.0)
    vids = [c["video_id"] for c in plan]
    assert vids[0] != vids[1]                                 # 첫 두 컷이 다른 소스
    # 같은 세그 재방문 시 창이 앞으로 밀림(정지 아님).
    s0_starts = [c["start"] for c in plan if c["video_id"] == "s0"]
    assert s0_starts == sorted(s0_starts) and len(set(s0_starts)) == len(s0_starts)


def test_max_shot_off_is_legacy():
    # max_shot None → 옛 동작(세그 통째 재생).
    segs = [_seg("s0", 0, 4), _seg("s1", 0, 4)]
    plan = va._plan_beat_clips(segs, 6.0, max_shot=None)
    assert plan[0]["src_dur"] == 4.0                          # 첫 세그 통째


def test_single_segment_no_roundrobin():
    # 세그 1개면 라운드로빈 안 함(옛 경로) — 회귀 안전.
    segs = [_seg("s0", 0, 5)]
    plan = va._plan_beat_clips(segs, 3.0, max_shot=2.0)
    assert plan[0]["src_dur"] == 3.0
