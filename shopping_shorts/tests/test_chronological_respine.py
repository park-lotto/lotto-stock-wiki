"""P2(장면스파인): 시간순 스파인 — 모델이 고른 시각 세그먼트를 소스 시간순으로 재배치.

핵심(2트랙 모델): 나레이션(비트 순서·내용)은 그대로 두고, 화면만 요리 시간순으로
흐르게 한다. 완성↔붓기 핑퐁 제거. 비트당 세그먼트 개수는 보존(길이 커버리지 유지).
"""
from shopping_shorts.edit_plan import _chronological_respine


def _beat(narration, primary_start, alt_starts=(), video="A"):
    return {
        "beat_idx": 0, "role": "x", "narration": narration, "target_seconds": 2.0,
        "primary": {"video_id": video, "seg_id": f"{video}-{primary_start}",
                    "start": float(primary_start), "end": float(primary_start) + 1.0},
        "alternates": [{"video_id": video, "seg_id": f"{video}-{s}",
                        "start": float(s), "end": float(s) + 1.0} for s in alt_starts],
        "fit": 1,
    }


def test_primaries_reordered_to_source_time_order():
    beats = [_beat("훅", 10), _beat("전개", 2), _beat("CTA", 6)]
    out = _chronological_respine(beats)
    # 나레이션 순서(훅→전개→CTA)는 그대로
    assert [b["narration"] for b in out] == ["훅", "전개", "CTA"]
    # 화면(primary start)은 시간 오름차순으로 재배치
    assert [b["primary"]["start"] for b in out] == [2.0, 6.0, 10.0]


def test_segment_count_per_beat_preserved():
    beats = [_beat("a", 10, alt_starts=[1]), _beat("b", 5, alt_starts=[8])]
    out = _chronological_respine(beats)
    # 개수 보존: 각 비트 1 primary + 1 alternate
    assert all(len(b["alternates"]) == 1 for b in out)
    # 전체 시퀀스(primary,alt,primary,alt)가 단조 증가
    seq = []
    for b in out:
        seq.append(b["primary"]["start"])
        seq += [a["start"] for a in b["alternates"]]
    assert seq == sorted(seq)


def test_multi_video_grouped_by_video_then_time():
    beats = [_beat("a", 5, video="B"), _beat("b", 2, video="A"), _beat("c", 9, video="A")]
    out = _chronological_respine(beats)
    keys = [(b["primary"]["video_id"], b["primary"]["start"]) for b in out]
    # (video_id, start) 오름차순: A-2, A-9, B-5
    assert keys == [("A", 2.0), ("A", 9.0), ("B", 5.0)]


def test_fit_marked_intentional_not_red():
    beats = [_beat("a", 3), _beat("b", 1)]
    out = _chronological_respine(beats)
    # 시간순 배치는 의도된 정상 — 오탐 빨간불(fit 낮음) 방지
    assert all(b["fit"] >= 3 for b in out)


def test_empty_beats_ok():
    assert _chronological_respine([]) == []
