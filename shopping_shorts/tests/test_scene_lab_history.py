# -*- coding: utf-8 -*-
"""3단계 편성 판본 보관 — 자동저장이 원본을 덮어써도 되돌릴 수 있는가.

2026-09-07 사장님 "반쪽짜리를 만들어서 나한테 주는 건 뭔데".
같은 날 아침 수리는 '화면이 초기화되는 길'만 막았다. 초기화가 한 번 나면 1.2초 뒤
자동저장(autoApply)이 **서버 편성까지** AI 기본배치로 덮어써 되살릴 방법이 없어진다.
그래서 원인을 하나씩 막는 대신 **결과를 되돌릴 수 있게** 한다.
"""
from shopping_shorts import edit_plan as ep


def _seg_map():
    return {sid: {"video_id": "s0", "seg_id": sid, "start": 0.0, "end": 2.0,
                  "scene_desc": "", "is_key": False, "shot_role": "기타"}
            for sid in ("a", "b", "c", "d")}


def _plan():
    return {"beats": [{"beat_idx": 0, "primary": {"seg_id": "a"}, "alternates": []},
                      {"beat_idx": 1, "primary": {"seg_id": "b"}, "alternates": []}]}


def _apply(plan, lists):
    """화면이 보내는 payload 모양 그대로 — 호출부와 같은 형태로 부른다."""
    beats = [{"beat_idx": i, "list": l} for i, l in enumerate(lists)]
    return ep.apply_scene_lab(plan, _seg_map(), {"beats": beats})


def _override_ids(plan):
    return [[s["seg_id"] for s in (b.get("scene_override") or [])] for b in plan["beats"]]


def test_편성이_바뀌면_직전_판본이_남는다():
    p = _plan()
    _apply(p, [["a", "b"], ["c"]])          # 사람이 고친 편성
    assert not p.get("scene_lab_hist")      # 첫 저장은 남길 이전 것이 없다
    _apply(p, [["a"], ["b"]])               # 자동저장이 덮었다(사고)
    hist = p.get("scene_lab_hist") or []
    assert len(hist) == 1
    assert hist[0]["beats"] == [{"beat_idx": 0, "list": ["a", "b"]},
                                {"beat_idx": 1, "list": ["c"]}]
    # ★배정(scene_override)까지 남아야 되살릴 수 있다 — beats만으론 복원이 안 된다
    assert hist[0]["overrides"]["0"][0]["seg_id"] == "a"
    assert hist[0]["overrides"]["1"][0]["seg_id"] == "c"


def test_같은_편성을_다시_저장하면_안_쌓인다():
    """자동저장은 1.2초마다 온다 — 내용이 같은데 쌓으면 정작 사고 직전 판본이 밀려난다."""
    p = _plan()
    _apply(p, [["a", "b"], ["c"]])
    for _ in range(5):
        _apply(p, [["a", "b"], ["c"]])      # 손 안 대고 자동저장만 반복
    assert not p.get("scene_lab_hist")


def test_사고_직전_판본이_다섯벌_안에_남는다():
    """내용이 같은 자동저장이 밀어내지 않으므로, 사고가 나도 원본이 살아 있다."""
    p = _plan()
    _apply(p, [["a", "b", "c"], ["d"]])     # ← 되살리고 싶은 원본
    for _ in range(20):
        _apply(p, [["a", "b", "c"], ["d"]])
    _apply(p, [["a"], ["b"]])               # 사고(초기화된 화면이 저장됨)
    hist = p["scene_lab_hist"]
    assert hist[0]["beats"][0]["list"] == ["a", "b", "c"]


def test_되돌리면_배정까지_원래대로():
    p = _plan()
    _apply(p, [["a", "b"], ["c"]])
    _apply(p, [["a"], ["b"]])               # 사고
    assert _override_ids(p) == [["a"], ["b"]]
    assert ep.restore_scene_lab_version(p, 0) is True
    assert _override_ids(p) == [["a", "b"], ["c"]]      # ★실제로 되살아났다
    assert p["scene_lab"]["beats"][0]["list"] == ["a", "b"]


def test_되돌린_뒤_다시_돌아올_수_있다():
    """되돌리기가 편도면 잘못 눌렀을 때 갇힌다."""
    p = _plan()
    _apply(p, [["a", "b"], ["c"]])
    _apply(p, [["a"], ["b"]])
    ep.restore_scene_lab_version(p, 0)                  # 원본으로
    assert _override_ids(p) == [["a", "b"], ["c"]]
    assert ep.restore_scene_lab_version(p, 0) is True   # 다시 사고 시점으로
    assert _override_ids(p) == [["a"], ["b"]]


def test_없는_판본은_거절한다():
    p = _plan()
    _apply(p, [["a"], ["b"]])
    assert ep.restore_scene_lab_version(p, 0) is False
    assert ep.restore_scene_lab_version(p, 99) is False


def test_판본은_다섯벌까지만_보관한다():
    p = _plan()
    for i in range(10):
        _apply(p, [["a"], ["b"]] if i % 2 else [["b"], ["a"]])
    assert len(p["scene_lab_hist"]) == ep._LAB_HIST_MAX == 5


def test_오려낸_조각도_판본에_남는다():
    """film_ 조각은 서버 seg_map에 없다 — 판본에 안 실으면 되돌려도 검은 칸이 된다."""
    p = _plan()
    extra = {"film_s0_1.0_2.0": {"video_id": "s0", "start": 1.0, "end": 2.0}}
    beats = [{"beat_idx": 0, "list": ["film_s0_1.0_2.0"]}, {"beat_idx": 1, "list": ["b"]}]
    ep.apply_scene_lab(p, _seg_map(), {"beats": beats, "extra_segs": extra})
    _apply(p, [["a"], ["b"]])               # 사고
    assert "film_s0_1.0_2.0" in p["scene_lab_hist"][0]["extra_segs"]
    ep.restore_scene_lab_version(p, 0)
    assert _override_ids(p)[0] == ["film_s0_1.0_2.0"]


def test_AI배치로_되돌리기도_판본을_남긴다():
    """[↩ AI 배치로 되돌리기]는 편성을 통째로 지운다 — 잘못 눌러도 되살릴 수 있어야 한다."""
    p = _plan()
    _apply(p, [["a", "b"], ["c"]])
    ep.revert_scene_lab(p)
    assert p.get("scene_lab") is None            # 편성은 걷혔고
    assert _override_ids(p) == [[], []]
    hist = p.get("scene_lab_hist") or []
    assert len(hist) == 1                        # 판본은 남았다
    assert ep.restore_scene_lab_version(p, 0) is True
    assert _override_ids(p) == [["a", "b"], ["c"]]   # ★되살아난다
