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


def test_no_clip_below_min_clip_flicker_guard():
    """★2026-07-29 사장님 '0.몇초마다 두서없이 바뀌어 눈아픔': 라운드로빈이 세그 잔량이 짧아도
    그대로 뱉어 0.5초짜리 깜빡임 컷이 났다(실측 75f41e558957.mp4). min_clip 하한을 강제한다 —
    마지막 클립(shortfall로 연장될 수 있음)을 뺀 모든 컷은 min_clip 이상."""
    # 세그 3개(각 2.5초). max_shot=2.2로 돌리면 재방문 때 잔량 0.3초가 생겨 예전엔 tiny컷이 났다.
    segs = [_seg("s0", 0, 2.5), _seg("s1", 0, 2.5), _seg("s2", 0, 2.5)]
    plan = va._plan_beat_clips(segs, 6.0, min_clip=0.8, src_durs=None, max_shot=2.2)
    assert plan
    # 마지막 클립을 제외한 전 컷이 min_clip 이상(자투리는 마지막으로 흡수)
    for c in plan[:-1]:
        assert c["out_dur"] >= 0.8 - 1e-6, f"깜빡임 컷 {c['out_dur']:.2f}s < 0.8"
    assert round(sum(c["out_dur"] for c in plan), 2) == 6.0   # 길이 채움 유지


def test_min_clip_falls_back_to_shortfall_when_no_segment_qualifies():
    """어느 세그도 min_clip을 못 낼 만큼 잔량이 다 짧으면, tiny컷을 뱉지 말고 루프를 끝내
    shortfall(마지막 클립 실프레임 연장)이 이어받아야 한다 — 되풀이/깜빡임 없음."""
    segs = [_seg("s0", 0, 1.0), _seg("s1", 0, 1.0)]   # 각 1초짜리 짧은 세그
    # src_durs로 실프레임 연장 여지를 준다(릴은 구간보다 길다).
    plan = va._plan_beat_clips(segs, 5.0, min_clip=0.8, src_durs={"s0": 30.0, "s1": 30.0}, max_shot=2.2)
    assert plan
    assert round(sum(c["out_dur"] for c in plan), 2) == 5.0
