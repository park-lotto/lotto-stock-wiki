"""첫 비트(훅)는 respine 대상에서 제외 — 모델이 훅에 고정한 화면이 시간순 재배치에 안 밀린다."""
from shopping_shorts import edit_plan


def _beat(sid, vid, start, txt="t"):
    seg = {"seg_id": sid, "video_id": vid, "start": start, "end": start + 2,
           "scene_desc": txt, "text": txt}
    return {"primary": seg, "alternates": [], "text": txt, "fit": 4}


def test_first_beat_not_respined():
    beats = [_beat("a-9", "a", 9.0, "훅"), _beat("b-1", "b", 1.0),
             _beat("a-1", "a", 1.0), _beat("b-9", "b", 9.0)]
    out = edit_plan._chronological_respine(beats)
    # 첫 비트 primary는 원본 그대로(seg_id a-9 유지), respined 플래그 없음
    assert out[0]["primary"]["seg_id"] == "a-9"
    assert not out[0].get("respined")
