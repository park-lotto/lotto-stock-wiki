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


def test_body_primaries_reordered_tail_anchored():
    # 머리(훅)·꼬리(마지막)는 앵커로 원래 화면 고정, 그 사이 body만 소스 시간순 재배치.
    beats = [_beat("훅", 10), _beat("전개", 2), _beat("실용", 8), _beat("CTA", 6)]
    out = _chronological_respine(beats)
    # 나레이션 순서(훅→전개→실용→CTA)는 그대로
    assert [b["narration"] for b in out] == ["훅", "전개", "실용", "CTA"]
    # 머리(훅) 원래 10 고정 / body(전개·실용) 시간순 재배치 = 2,8 / 꼬리(CTA) 원래 6 고정
    assert [b["primary"]["start"] for b in out] == [10.0, 2.0, 8.0, 6.0]


def test_segment_count_per_beat_preserved():
    beats = [_beat("a", 10, alt_starts=[1]), _beat("m", 5, alt_starts=[8]),
             _beat("n", 4, alt_starts=[7]), _beat("cta", 3, alt_starts=[0])]
    out = _chronological_respine(beats)
    # 개수 보존: 각 비트 1 primary + 1 alternate
    assert all(len(b["alternates"]) == 1 for b in out)
    # 중간 body(m,n) 시퀀스는 단조 증가 (머리·꼬리 앵커 제외)
    body_seq = []
    for b in out[1:-1]:
        body_seq.append(b["primary"]["start"])
        body_seq += [a["start"] for a in b["alternates"]]
    assert body_seq == sorted(body_seq)
    # 머리(a)는 앵커 — 원래 세그먼트 그대로
    assert out[0]["primary"]["start"] == 10.0 and out[0]["alternates"][0]["start"] == 1.0
    # 꼬리(cta)는 앵커 — 원래 세그먼트 그대로
    assert out[-1]["primary"]["start"] == 3.0 and out[-1]["alternates"][0]["start"] == 0.0


def test_multi_video_body_grouped_by_video_then_time():
    beats = [_beat("a", 5, video="B"), _beat("b", 2, video="A"),
             _beat("c", 9, video="A"), _beat("cta", 1, video="A")]
    out = _chronological_respine(beats)
    keys = [(b["primary"]["video_id"], b["primary"]["start"]) for b in out]
    # 머리(a) 앵커 B-5 고정 / 중간 body(b,c) (video_id,start) 오름차순: A-2, A-9 / 꼬리(cta) 앵커 A-1 고정
    assert keys == [("B", 5.0), ("A", 2.0), ("A", 9.0), ("A", 1.0)]


def test_respined_body_flagged_fit_preserved():
    # ④ fit 정직화: respine은 fit을 덮어쓰지 않고 respined 플래그만 단다.
    beats = [_beat("a", 3), _beat("b", 1), _beat("c", 4), _beat("cta", 5)]  # fit=1로 생성됨(_beat)
    out = _chronological_respine(beats)
    # 중간 body(b,c)는 시간순 재배치됨 → respined 표시, fit은 모델값(1) 보존
    assert out[1]["respined"] is True and out[2]["respined"] is True
    assert out[1]["fit"] == 1 and out[2]["fit"] == 1
    # 머리(a)는 앵커 — respined 아님, fit 보존
    assert out[0].get("respined") is not True
    assert out[0]["fit"] == 1
    # 꼬리(cta)는 앵커 — respined 아님, fit 보존
    assert out[-1].get("respined") is not True
    assert out[-1]["fit"] == 1


def test_tail_beat_anchor_preserved():
    """② 엔딩 딴 영상 버그: 꼬리(CTA/엔딩) 비트의 화면은 모델이 고른 완성/시식 컷 그대로여야
    한다. respine 전역정렬이 (video_id,start)로 소스를 뭉쳐서, CTA 나레이션 위에 딴 소스
    세그먼트를 얹던 버그. 꼬리 비트는 앵커 — body만 시간순 재배치, 꼬리는 고정."""
    beats = [
        _beat("훅", 0, video="A"),
        _beat("조리", 5, video="A"),
        _beat("딴소스 조리컷", 2, video="B"),
        _beat("완성! 댓글 남겨요", 10, video="A"),  # CTA 앵커 = 완성 컷(A-10)
    ]
    out = _chronological_respine(beats)
    assert [b["narration"] for b in out][-1] == "완성! 댓글 남겨요"
    # 꼬리 화면 = 모델이 고른 완성 컷(A-10) 그대로, 딴 소스(B) 아님
    assert out[-1]["primary"]["video_id"] == "A"
    assert out[-1]["primary"]["seg_id"] == "A-10"


def test_single_beat_tail_only_ok():
    out = _chronological_respine([_beat("only", 5)])
    assert len(out) == 1 and out[0]["primary"]["start"] == 5.0


def test_empty_beats_ok():
    assert _chronological_respine([]) == []
