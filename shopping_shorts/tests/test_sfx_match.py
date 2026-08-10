"""효과음(sfx) 역할매칭 순수함수 테스트 (스펙 §3·§8).

클립 역할패스(_role_pass)와 유일한 알고리즘 차이 = **중복 허용**(used 세트 없음).
그 차이를 명시적으로 검증한다(④).
"""
import copy
from shopping_shorts import scene_match


def _plan(*roles, narrations=None):
    beats = []
    for i, r in enumerate(roles):
        narr = (narrations or {}).get(i, f"n{i}")
        beats.append({"beat_idx": i, "role": r, "narration": narr, "target_seconds": 2.0,
                      "primary": {"video_id": 0, "seg_id": f"s{i}", "start": 0, "end": 2},
                      "alternates": [], "effect": "cut", "fit": 0})
    return {"structure": "t", "beats": beats}


def _sfx(aid, role, subject="x", keywords=None):
    return {"id": aid, "asset_type": "sfx", "role": role, "subject": subject,
            "tone": "", "keywords": keywords or [], "media_path": f"/x/{aid}.mp3"}


# ── _sfx_position ──────────────────────────────────────────────

def test_sfx_position_hook_is_first():
    assert scene_match._sfx_position("hook") == "first"


def test_sfx_position_others_are_last():
    for role in ("problem", "info", "cta", "result_wow", "benefit"):
        assert scene_match._sfx_position(role) == "last"


def test_sfx_position_unknown_role_defaults_last():
    assert scene_match._sfx_position("존재안함") == "last"
    assert scene_match._sfx_position(None) == "last"


# ── match_sfx ──────────────────────────────────────────────────

def test_match_sfx_no_candidates_leaves_no_sfx():
    # 후보 역할이 hook 호환("훅","반응")이 아니라 배치될 게 없음
    plan = _plan("hook")
    out = scene_match.match_sfx(plan, [_sfx(1, "본문")])
    assert "sfx" not in out["beats"][0]


def test_match_sfx_role_mismatch_excluded():
    # 비트 role=cta → 호환 자산 역할 "CTA"만. "반응" 자산은 배제.
    plan = _plan("cta")
    out = scene_match.match_sfx(plan, [_sfx(1, "반응")])
    assert "sfx" not in out["beats"][0]


def test_match_sfx_role_outside_vocab_excluded():
    # 통제어휘(_ROLES) 밖 role은 후보에서 원천 배제(§3.2)
    plan = _plan("hook")
    out = scene_match.match_sfx(plan, [_sfx(1, "바나나")])
    assert "sfx" not in out["beats"][0]


def test_match_sfx_places_by_role():
    plan = _plan("hook")
    out = scene_match.match_sfx(plan, [_sfx(7, "훅", subject="빵빠레")])
    sfx = out["beats"][0]["sfx"]
    assert sfx["asset_id"] == 7
    assert sfx["match_type"] == "role"
    assert sfx["position"] == "first"   # hook → first


def test_match_sfx_non_hook_position_last():
    plan = _plan("cta")
    out = scene_match.match_sfx(plan, [_sfx(3, "CTA")])
    assert out["beats"][0]["sfx"]["position"] == "last"


def test_match_sfx_allows_duplicate_across_beats():
    # ★핵심: 같은 asset_id가 서로 다른 두 비트에 배치될 수 있다(중복 허용).
    #   클립 역할패스(_role_pass)라면 used 세트로 둘째 비트를 비웠을 것.
    plan = _plan("hook", "benefit")   # hook→("훅","반응"), benefit→("반응","본문")
    out = scene_match.match_sfx(plan, [_sfx(5, "반응", subject="박수")])
    placed = [b.get("sfx", {}).get("asset_id") for b in out["beats"]]
    assert placed == [5, 5]           # 둘 다 같은 자산 — 중복 허용


def test_match_sfx_prefers_narration_keyword_overlap():
    plan = _plan("hook", narrations={0: "고양이가 등장"})
    assets = [_sfx(1, "반응", subject="강아지", keywords=["강아지"]),
              _sfx(2, "반응", subject="고양이", keywords=["고양이"])]
    out = scene_match.match_sfx(plan, assets)
    assert out["beats"][0]["sfx"]["asset_id"] == 2   # '고양이' 겹침 우선


def test_match_sfx_ignores_non_sfx_assets():
    # asset_type이 sfx가 아니면 후보 아님(_sfx_candidates)
    plan = _plan("hook")
    clip = {"id": 9, "asset_type": "clip", "role": "훅", "subject": "x",
            "keywords": [], "media_path": "/x/9.mp4"}
    out = scene_match.match_sfx(plan, [clip])
    assert "sfx" not in out["beats"][0]


def test_match_sfx_does_not_mutate_input():
    plan = _plan("hook")
    snap = copy.deepcopy(plan)
    scene_match.match_sfx(plan, [_sfx(7, "훅")])
    assert plan == snap
