import copy
from shopping_shorts import scene_match

import pytest


@pytest.fixture(autouse=True)
def _pass_narrow(monkeypatch):
    """1차 좁히기(2026-09-08)를 이 파일에서는 통과시킨다.

    ★좁히기를 끄는 게 아니라 **관심사를 가른다**: 이 파일이 검증하는 것은 소재/역할
      매칭 로직이고, 픽스처의 나레이션은 'n0' 같은 더미라 실제 대본이 아니다. 좁히기
      자체는 test_scene_narrow.py가 실제 서버 데이터 모양으로 따로 검증한다.
      (여기서 좁히기까지 함께 태우면 '무엇이 깨졌는지'가 섞여 진단이 어려워진다)
    """
    monkeypatch.setattr(scene_match, "narrow", lambda assets, plan, **kw: list(assets))



def _plan(*roles):
    return {"structure": "t",
            "beats": [{"beat_idx": i, "role": r, "narration": f"n{i}", "target_seconds": 2.0,
                       "primary": {"video_id": 0, "seg_id": f"s{i}", "start": 0, "end": 2},
                       "alternates": [], "effect": "cut", "fit": 0}
                      for i, r in enumerate(roles)]}


def _asset(aid, role, subject="x", tone="", keywords=None, origin="짜집기", atype="clip"):
    return {"id": aid, "asset_type": atype, "role": role, "subject": subject, "tone": tone,
            "keywords": keywords or [], "category": "레시피", "scene_desc": subject,
            "source_origin": origin, "media_path": f"/x/{aid}.mp4"}


def test_role_map_hook_to_grabbers():
    assert scene_match._ROLE_FALLBACK["hook"] == ("훅", "반응")
    assert "반전" in scene_match._ROLE_FALLBACK["problem_solution"]
    assert scene_match._ROLE_FALLBACK.get("존재안함") is None


def _no_vault(*a, **k):
    return None  # 소재 패스는 전부 실패(빈 비트 만들려고) → 역할 패스만 관찰


def test_role_pass_fills_empty_hook_beat():
    plan = _plan("hook")
    assets = [_asset(7, "반응", subject="귀여운 고양이")]
    out = scene_match.match_scene_assets(plan, assets, vault_call=_no_vault)
    cw = out["beats"][0]["cutaway"]
    assert cw["asset_id"] == 7 and cw["match_type"] == "role"
    assert "score" not in cw or cw["score"] is None


def test_role_pass_skips_beats_already_subject_matched():
    plan = _plan("hook")
    assets = [_asset(5, "훅", subject="감자")]
    # 소재 패스가 배치했다고 가정하는 스텁
    fake = lambda *a, **k: {"best_asset_id": 5, "score": 0.95}
    out = scene_match.match_scene_assets(plan, assets, vault_call=fake)
    cw = out["beats"][0]["cutaway"]
    assert cw["match_type"] == "subject" and cw["score"] == 0.95   # 역할 패스가 안 덮음


def test_role_pass_no_compatible_role_leaves_empty():
    plan = _plan("hook")
    assets = [_asset(9, "본문", subject="배경")]   # 본문은 hook 호환 아님
    out = scene_match.match_scene_assets(plan, assets, vault_call=_no_vault)
    assert "cutaway" not in out["beats"][0]


def test_role_pass_no_repeat_within_video():
    plan = _plan("hook", "benefit")   # 둘 다 반응 호환
    assets = [_asset(3, "반응", subject="강아지")]   # 반응 자산 하나뿐
    out = scene_match.match_scene_assets(plan, assets, vault_call=_no_vault)
    placed = [b["cutaway"]["asset_id"] for b in out["beats"] if b.get("cutaway")]
    assert placed == [3]   # 한 영상에서 같은 asset 한 번만 → 둘째 비트는 빔


def test_role_pass_prefers_keyword_overlap():
    plan = {"structure": "t", "beats": [
        {"beat_idx": 0, "role": "hook", "narration": "고양이가 등장", "target_seconds": 2.0,
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0, "end": 2},
         "alternates": [], "effect": "cut", "fit": 0}]}
    assets = [_asset(1, "반응", subject="강아지", keywords=["강아지"]),
              _asset(2, "반응", subject="고양이", keywords=["고양이"])]
    out = scene_match.match_scene_assets(plan, assets, vault_call=_no_vault)
    assert out["beats"][0]["cutaway"]["asset_id"] == 2   # 나레이션 '고양이'와 겹침


def test_subject_cutaway_gets_match_type():
    plan = _plan("hook")
    assets = [_asset(5, "훅", subject="감자")]
    out = scene_match.match_scene_assets(plan, assets,
                                         vault_call=lambda *a, **k: {"best_asset_id": 5, "score": 0.95})
    assert out["beats"][0]["cutaway"]["match_type"] == "subject"


def test_does_not_mutate_input():
    plan = _plan("hook")
    snap = copy.deepcopy(plan)
    scene_match.match_scene_assets(plan, [_asset(7, "반응")], vault_call=_no_vault)
    assert plan == snap
