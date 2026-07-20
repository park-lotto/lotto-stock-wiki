"""P2(장면스파인) ②: 비트 간 중복 제거 + 서브슬라이스 + 얼굴 후순위.

모델이 같은 seg를 여러 비트에 줘도(실측: beat0·beat1 둘 다 s1-0) 걸러지지 않아
같은 장면이 2연속으로 뜨는 버그를 막는다. respine의 flat 풀에서 같은
(video_id,seg_id,start) 중복을 제거하고, 부족분은 가장 긴 세그먼트를 서브슬라이스해 채운다.
"""
from shopping_shorts.edit_plan import _is_face_seg, _dedup_and_fill


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
