"""캡컷·ZIP 의 원본 재료 이름 바꾸기(`<vid>_raw`) 뒤에도 화면 컷을 그대로 쓰는지(2026-09-27).

왜 (9차 관문, dacd163229e5 칸2 컷0): 부분 정본 job 에서 캡컷·ZIP 은 원본 재료 칸의 video_id 를 `s4_raw` 로 바꾼 사본을 계획한다
  (mix_pipeline._plan_on_source_files). 칸 내용 키가 달라져 화면 컷을 못 찾고 파이썬 예비 계산으로 떨어져, 렌더(화면 컷: 잔상 가드로
  시작 0.066·1.15배 느리게)와 캡컷(0.0·1배속)이 한 컷에서 start·read·speed 가 갈렸다.
"""
from shopping_shorts import mix_pipeline as mp
from shopping_shorts import screen_clips as sc
from shopping_shorts import video_assemble as va


def _beat():
    return {"beat_idx": 2, "phrase_sync": None, "narration": "가 나",
            "primary": {"video_id": "s4", "seg_id": "a", "start": 0.0, "end": 3.0}, "alternates": []}


def test_renamed_copy_uses_same_screen_cut(monkeypatch):
    b = _beat()
    k = sc.beat_key(b)
    monkeypatch.setitem(sc._CACHE, k, {"t": 0.3667, "c": [{"v": "s4", "s": 0.066, "d": 0.3667, "sd": 0.304, "fit": 0}]})
    plan, moved, unmoved = mp._plan_on_source_files({"beats": [b]}, {"s4": {"path": "x"}}, [], {"s4"})
    rb = plan["beats"][0]
    assert rb["primary"]["video_id"] == "s4_raw"
    assert rb["_screen_key"] == k and rb["_screen_vid"] == {"s4": "s4_raw"}
    assert sc.beat_key(rb) != k                                   # 바꾼 사본의 내용 키는 다르다 — 그래서 대응을 단다
    got = va.plan_beat_clips_for(rb, 0.3667, {"s4_raw": 30.0})
    assert [(c["video_id"], c["start"], round(c["src_dur"], 3)) for c in got] == [("s4_raw", 0.066, 0.304)], got
    assert sc.has(rb)


def test_without_mapping_falls_back_old_behavior(monkeypatch):
    """대응이 없으면(종전) 키가 달라 화면 컷을 못 찾는다 — 이 테스트가 재현하는 결함이 실제로 있었는지."""
    b = _beat()
    monkeypatch.setitem(sc._CACHE, sc.beat_key(b), {"t": 0.3667, "c": [{"v": "s4", "s": 0.066, "d": 0.3667, "sd": 0.304, "fit": 0}]})
    rb = dict(b, primary=dict(b["primary"], video_id="s4_raw"))
    assert not sc.has(rb)
