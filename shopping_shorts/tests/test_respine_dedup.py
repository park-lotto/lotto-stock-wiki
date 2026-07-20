"""P2(장면스파인) ②: 비트 간 중복 제거 + 서브슬라이스 + 얼굴 후순위.

모델이 같은 seg를 여러 비트에 줘도(실측: beat0·beat1 둘 다 s1-0) 걸러지지 않아
같은 장면이 2연속으로 뜨는 버그를 막는다. respine의 flat 풀에서 같은
(video_id,seg_id,start) 중복을 제거하고, 부족분은 가장 긴 세그먼트를 서브슬라이스해 채운다.

리뷰 픽스(2026-07-20): fill이 need 미만으로만 채워질 수 있는데(잔여 세그 전부 1초
미만이면 break) _chronological_respine의 downstream 루프가 그걸 가정 못 하면 뒤쪽
비트에서 IndexError가 난다 — end-to-end로 그 경로를 검증한다.
"""
from shopping_shorts.edit_plan import _is_face_seg, _dedup_and_fill, _chronological_respine


def _beat(v, sid, start, end, narration):
    return {
        "beat_idx": 0, "role": "x", "narration": narration, "target_seconds": 2.0,
        "primary": {"video_id": v, "seg_id": sid, "start": start, "end": end},
        "alternates": [], "fit": 1,
    }


def test_face_seg_detected():
    assert _is_face_seg("진행자가 정면으로 카메라를 보며 설명한다") is True
    assert _is_face_seg("主理人正面讲解") is True
    assert _is_face_seg("반죽을 실리콘매트에 올려 치댄다") is False


def _seg(v, sid, start, end):
    return {"video_id": v, "seg_id": sid, "start": float(start), "end": float(end)}


def test_dedup_removes_identical_and_keeps_order():
    flat = [_seg("A", "A-0", 0, 5), _seg("A", "A-0", 0, 5), _seg("A", "A-2", 35, 60)]
    out = _dedup_and_fill(flat, need=3)
    # 같은 (A-0,0.0) 중복 1개 제거 → 서브슬라이스로 3개 채움, 동일 (seg_id,start) 재등장 없음
    keys = [(s["seg_id"], s["start"]) for s in out]
    assert len(keys) == 3 and len(set(keys)) == 3


def test_subslice_splits_longest_when_short():
    flat = [_seg("A", "A-0", 0, 5), _seg("A", "A-2", 10, 30)]  # 2개인데 3 필요
    out = _dedup_and_fill(flat, need=3)
    assert len(out) == 3
    # 가장 긴 A-2(20초)를 반으로: 앞[10~20], 뒤[20~30]
    a2 = sorted([s for s in out if s["seg_id"].startswith("A-2")], key=lambda s: s["start"])
    assert len(a2) == 2 and a2[0]["end"] == a2[1]["start"]


def test_respine_end_to_end_resolves_duplicate_primary_across_beats():
    """beat0·beat1에 완전히 같은 seg를 주입 — respine 후 두 비트 primary가 서로 달라야
    한다(중복 해소, 서브슬라이스로 채움). 실제 호출 경로(_chronological_respine)로 검증."""
    beats = [
        _beat("A", "A-0", 0.0, 4.0, "beat0"),
        _beat("A", "A-0", 0.0, 4.0, "beat1"),  # beat0과 완전 동일 seg 중복 주입
        _beat("A", "A-9", 9.0, 9.6, "tail"),
    ]
    out = _chronological_respine(beats)
    p0, p1 = out[0]["primary"], out[1]["primary"]
    assert (p0["seg_id"], p0["start"]) != (p1["seg_id"], p1["start"])


def test_respine_fill_shortage_no_indexerror_all_beats_keep_primary():
    """잔여 세그가 전부 1초 미만이면 _dedup_and_fill이 need 미만만 반환한다(fill 실패).
    그래도 _chronological_respine이 IndexError 없이 모든 비트에 primary를 채워야 한다."""
    beats = [
        _beat("A", "A-0", 0.0, 0.5, "beat0"),   # 0.5s <1s
        _beat("A", "A-0", 0.0, 0.5, "beat1"),   # beat0과 완전 동일(중복) — fill 재료 부족 유발
        _beat("A", "A-1", 1.0, 1.3, "beat2"),   # 0.3s <1s — 더 쪼갤 수 없음
        _beat("A", "A-9", 9.0, 9.6, "tail"),
    ]
    out = _chronological_respine(beats)  # 가드 없으면 여기서 IndexError
    assert len(out) == 4
    for b in out:
        assert b.get("primary") is not None
        assert "seg_id" in b["primary"]
