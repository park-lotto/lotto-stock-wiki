"""P1 Task 4 ①: visual_verb 앵커 — 대사가 시각행위를 지목하는 비트는 respine 제외.

대사에 구체적 시각행위("결대로 찢어진다")가 있는 비트는 화면이 반드시 맞아야 하므로
꼬리처럼 앵커로 고정한다(모델이 고른 원 세그먼트 그대로, respined 없음). 나머지 movable
body 비트만 소스 시간순으로 재배치한다.
"""
from shopping_shorts.edit_plan import _chronological_respine


def _beat(narr, start, verb=False, video="A"):
    return {"beat_idx": 0, "role": "x", "narration": narr, "target_seconds": 2.0,
            "primary": {"video_id": video, "seg_id": f"{video}-{start}",
                        "start": float(start), "end": float(start) + 1, "scene_desc": ""},
            "alternates": [], "fit": 3, "visual_verb": verb}


def test_visual_verb_beat_anchored_not_respined():
    # "찢어진다"(visual_verb) 비트는 원래 화면 고정, 나머지 body만 시간순.
    beats = [_beat("훅", 10), _beat("결대로 찢어진다", 2, verb=True),
             _beat("실용", 8), _beat("cta", 6)]
    out = _chronological_respine(beats)
    verb_beat = out[1]
    assert verb_beat["narration"] == "결대로 찢어진다"
    assert verb_beat["primary"]["start"] == 2.0        # 모델이 고른 그대로
    assert verb_beat.get("respined") is not True        # 앵커 = respined 아님
    # 나머지 body(훅·실용)만 시간순 재배치, cta는 꼬리 앵커
    assert out[0]["primary"]["start"] == 8.0 and out[2]["primary"]["start"] == 10.0
    assert out[-1]["primary"]["start"] == 6.0           # 꼬리 앵커 고정


def test_visual_verb_fit_preserved_on_anchor():
    # 앵커 비트는 fit도 모델값 그대로(respine이 건드리지 않는다).
    beats = [_beat("훅", 5), _beat("붓는다", 1, verb=True), _beat("cta", 9)]
    out = _chronological_respine(beats)
    assert out[1]["fit"] == 3 and out[1].get("respined") is not True


def test_missing_visual_verb_key_treated_as_movable():
    # visual_verb 키가 없으면 .get()이 False → movable(기존 respine 계약 유지).
    beats = [{"beat_idx": 0, "role": "x", "narration": "a", "target_seconds": 2.0,
              "primary": {"video_id": "A", "seg_id": "A-9", "start": 9.0, "end": 10.0,
                          "scene_desc": ""}, "alternates": [], "fit": 1},
             {"beat_idx": 0, "role": "x", "narration": "b", "target_seconds": 2.0,
              "primary": {"video_id": "A", "seg_id": "A-2", "start": 2.0, "end": 3.0,
                          "scene_desc": ""}, "alternates": [], "fit": 1},
             {"beat_idx": 0, "role": "x", "narration": "cta", "target_seconds": 2.0,
              "primary": {"video_id": "A", "seg_id": "A-5", "start": 5.0, "end": 6.0,
                          "scene_desc": ""}, "alternates": [], "fit": 1}]
    out = _chronological_respine(beats)
    # body(a,b) 시간순 재배치 → 2.0, 9.0 / cta 앵커 5.0
    assert [b["primary"]["start"] for b in out] == [2.0, 9.0, 5.0]
    assert out[0]["respined"] is True and out[1]["respined"] is True


def test_all_body_visual_verb_only_tail_movable_pool_empty():
    # body 전부 앵커면 재배치 대상이 없다 — 전원 원 화면 고정, respined 없음.
    beats = [_beat("찢는다", 3, verb=True), _beat("붓는다", 1, verb=True),
             _beat("cta", 7)]
    out = _chronological_respine(beats)
    assert [b["primary"]["start"] for b in out] == [3.0, 1.0, 7.0]
    assert all(b.get("respined") is not True for b in out)
