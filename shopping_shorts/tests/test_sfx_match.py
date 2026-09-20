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

def test_sfx_position_hook_is_transition():
    """훅은 **다음 칸으로 넘어가는 순간**이 기본이다(2026-08-21 사장님 "훅에서 다음
    넘어가거나 이럴때"). 종전 기본은 "first"(칸 시작)였는데, 이븐쇼핑류는 장면이
    바뀌는 지점에 효과음을 얹는다 — 그쪽이 사장님이 만들려는 결이다.
    사람이 칸마다 바꿀 수 있으므로 여기 값은 어디까지나 **기본값**이다."""
    assert scene_match._sfx_position("hook") == "transition"


def test_sfx_positions_통제어휘():
    """렌더(video_assemble)가 이 이름들로 실제 초를 계산한다 — 한쪽만 늘리면
    조용히 기본값(last)으로 떨어진다."""
    assert set(scene_match.SFX_POSITIONS) == {"first", "last", "transition"}


def test_사람이_고른_효과음은_재매칭이_안_덮는다():
    """재매칭은 대본이 바뀔 때마다 도는데 덮으면 '바꿨는데 그대로'가 된다."""
    plan = {"beats": [{"beat_idx": 0, "role": "hook", "narration": "훅 문장",
                       "sfx": {"asset_id": 99, "match_type": "manual", "position": "first"}}]}
    out = scene_match.match_sfx(plan, [_sfx(7, "훅")])
    assert out["beats"][0]["sfx"] == {"asset_id": 99, "match_type": "manual",
                                      "position": "first"}


def test_렌더가_전환_타점을_칸_끝으로_계산한다():
    """position 이름을 실제 초로 옮기는 지점.

    ★2026-08-30: 이 계산은 `video_assemble.sfx_events_for` **한 함수**로 빠졌다 —
      캡컷 내보내기도 같은 타점을 써야 하기 때문이다(0순위-B). 소스 grep 대신
      함수를 직접 불러 확인한다(진짜 동작을 본다).
    """
    from shopping_shorts.video_assemble import sfx_events_for
    # 자막이 두 칸으로 갈리는 길이여야 last(=마지막 자막 자리)가 0이 아니다.
    # 한 칸짜리 대사는 last도 0.0이 맞다(칸이 하나뿐이라 앞이 없다).
    _long = "이거 하나면 방충망 먼지가 순식간에 사라지고 다시 붙지도 않아서 정말 편해요"
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": 6.0, "narration": _long},
          {"beat_idx": 1, "t0": 6.0, "dur": 1.5, "narration": "사아자 차카타"}]
    def _at(pos, i=0):
        t = [dict(b) for b in tl]
        t[i]["sfx"] = {"position": pos}
        return sfx_events_for(t, {0: "a.mp3", 1: "b.mp3"})[0][1]
    assert _at("first") == 0.0
    assert _at("transition") == 6.0, "전환 = 칸이 끝나는 순간"
    assert 0.0 < _at("last") < 6.0, "기본(last)은 칸의 마지막 자막 자리"
    # 타점은 **절대시각**이다(비트 t0 + 오프셋) — 자막이 한 칸뿐인 비트면 그 칸 시작.
    assert _at("last", 1) == 6.0, "자막이 한 칸뿐이면 last도 칸 시작이다"


def test_sfx_position_모든역할이_컷경계다():
    """★2026-08-29 실측으로 기본값이 last→transition으로 바뀌었다.
    대세 채널 3편에서 컷 55개 중 52개(95%)에 소리가 붙고, 타점은 컷 경계
    ±12ms였다(역할 무관). 종전 'last'는 검증 안 된 추측이었다."""
    for role in ("hook", "problem", "info", "cta", "result_wow", "benefit"):
        assert scene_match._sfx_position(role) == "transition"


def test_sfx_position_unknown_role도_컷경계():
    assert scene_match._sfx_position("존재안함") == "transition"
    assert scene_match._sfx_position(None) == "transition"


def test_sfx_last는_수동으로_여전히_쓸_수_있다():
    """기본값만 바뀐 것이지 last가 없어진 게 아니다 — 렌더가 계속 받아야 한다."""
    assert "last" in scene_match.SFX_POSITIONS


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
    assert sfx["position"] == "transition"   # hook → 다음 칸으로 넘어가는 순간(2026-08-21)


def test_match_sfx_non_hook도_컷경계():
    plan = _plan("cta")
    out = scene_match.match_sfx(plan, [_sfx(3, "CTA")])
    assert out["beats"][0]["sfx"]["position"] == "transition"


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


def test_미리듣기와_렌더가_같은_타점_규칙을_쓴다():
    """장면편집 미리듣기(scene_play.js)와 렌더(video_assemble)가 어긋나면
    "미리 들은 것과 완성본이 다르다"가 된다 — 두 곳이 같은 규칙을 쓰는지 소스로 못박는다.
    (2026-08-21 사장님 "미리 들어볼 수 있게")"""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "static" / "scene_play.js").read_text(encoding="utf-8")
    assert "function armSfx" in js, "재생 중 효과음 예약 함수가 없다"
    assert "'transition'" in js and "at = dur" in js, "전환 타점이 칸 끝이 아니다"
    assert "'first'" in js, "칸 시작 타점 분기가 없다"
    assert "clearSfxTimers" in js, "정지 시 예약을 끄지 않으면 멈춘 뒤에 울린다"
