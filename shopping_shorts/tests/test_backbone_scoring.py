"""백본 자동 채점/선정(2026-07-22): 60대가 메인을 안 골라도 시스템이 coverage(재조합
가능성)+참여도로 최고 백본을 자동 선정. forced는 override."""
from shopping_shorts import backbone


def _seg(sid, action):
    return {"seg_id": sid, "start": 0, "end": 2, "action": action, "scene_desc": ""}


# A: 행위(자르다·붓다)를 B가 전부 커버 → A는 좋은 백본(재조합 잘 됨).
# C: 행위(뒤집다)를 아무도 커버 못 함 → 나쁜 백본.
_SRC = [
    {"video_id": "A", "segments": [_seg("A1", "자르다"), _seg("A2", "붓다")]},
    {"video_id": "B", "segments": [_seg("B1", "자르다"), _seg("B2", "붓다")]},
    {"video_id": "C", "segments": [_seg("C1", "뒤집다")]},
]


def test_score_backbones_ranks_by_coverage():
    scores = {r["video_id"]: r for r in backbone.score_backbones(_SRC)}
    # A는 B가 행위를 커버 → coverage 높음. C는 커버 0.
    assert scores["A"]["coverage"] > scores["C"]["coverage"]
    assert scores["A"]["score"] > scores["C"]["score"]


def test_pick_backbone_auto_by_score_not_comments():
    # C가 댓글수 최다여도, 재조합 안 되는 백본이라 A/B가 뽑혀야 한다(예전엔 댓글수로 C).
    meta = {"A": {"platform": "instagram", "comments": 1},
            "B": {"platform": "instagram", "comments": 1},
            "C": {"platform": "instagram", "comments": 999}}
    picked = backbone.pick_backbone(_SRC, meta=meta)
    assert picked in ("A", "B")
    assert picked != "C"


def test_forced_overrides_score():
    meta = {"A": {"platform": "instagram"}, "B": {"platform": "instagram"},
            "C": {"platform": "instagram"}}
    assert backbone.pick_backbone(_SRC, meta=meta, forced="C") == "C"


def test_engagement_breaks_tie_between_equal_coverage():
    # A와 B는 coverage 동일(서로 커버) → 참여도(댓글) 높은 쪽.
    meta = {"A": {"platform": "instagram", "comments": 100},
            "B": {"platform": "instagram", "comments": 1},
            "C": {"platform": "instagram", "comments": 0}}
    assert backbone.pick_backbone(_SRC, meta=meta) == "A"
