import copy
from shopping_shorts import scene_match


def _plan(*narrations):
    return {"structure": "template",
            "beats": [{"beat_idx": i, "role": "본문", "narration": n, "target_seconds": 2.0,
                       "primary": {"video_id": 0, "seg_id": f"s{i}", "start": 0.0, "end": 2.0},
                       "alternates": [], "effect": "cut", "fit": 0}
                      for i, n in enumerate(narrations)]}


def _asset(aid, subject, origin="짜집기", atype="clip", **kw):
    a = {"id": aid, "asset_type": atype, "source_origin": origin, "subject": subject,
         "scene_desc": subject, "keywords": [subject], "category": "레시피",
         "role": "본문", "duration": 1.5, "media_path": f"/x/{aid}.mp4"}
    a.update(kw)
    return a


def test_high_score_autoplaces_cutaway():
    plan = _plan("감자를 채 썬다")
    assets = [_asset(5, "채 썬 감자")]
    # 스텁: 비트0 → 자산5 점수 0.9
    fake = lambda prompt, schema, **k: {"best_asset_id": 5, "score": 0.9}
    out = scene_match.match_scene_assets(plan, assets, threshold=0.6, vault_call=fake)
    assert out["beats"][0]["cutaway"] == {"asset_id": 5, "score": 0.9}
    assert out.get("asset_suggestions", []) == []


def test_low_score_goes_to_suggestions_not_autoplace():
    plan = _plan("자전거를 탄다")
    assets = [_asset(7, "공유 자전거")]
    fake = lambda prompt, schema, **k: {"best_asset_id": 7, "score": 0.3}
    out = scene_match.match_scene_assets(plan, assets, threshold=0.6, vault_call=fake)
    assert "cutaway" not in out["beats"][0]
    assert out["asset_suggestions"] == [{"beat_idx": 0, "asset_id": 7, "score": 0.3}]


def test_first_filter_excludes_non_clip_and_unknown_origin():
    plan = _plan("무언가")
    assets = [_asset(1, "x", atype="sfx"), _asset(2, "y", origin="모름"),
              _asset(3, "z", origin=None)]
    calls = []
    fake = lambda prompt, schema, **k: calls.append(prompt) or {"best_asset_id": 0, "score": 0.0}
    out = scene_match.match_scene_assets(plan, assets, vault_call=fake)
    # 후보 0 → Gemini 호출조차 안 함, cutaway 없음
    assert calls == []
    assert "cutaway" not in out["beats"][0]


def test_vault_none_fails_quietly():
    plan = _plan("감자")
    assets = [_asset(5, "채 썬 감자")]
    out = scene_match.match_scene_assets(plan, assets, vault_call=lambda *a, **k: None)
    assert "cutaway" not in out["beats"][0]
    assert out["asset_suggestions"] == []


def test_does_not_mutate_input_plan():
    plan = _plan("감자")
    snap = copy.deepcopy(plan)
    scene_match.match_scene_assets(plan, [_asset(5, "채 썬 감자")],
                                   vault_call=lambda *a, **k: {"best_asset_id": 5, "score": 0.9})
    assert plan == snap  # 원본 불변(순수함수)


def test_unknown_best_asset_id_is_ignored():
    plan = _plan("감자")
    assets = [_asset(5, "채 썬 감자")]
    # 모델이 후보에 없는 id를 뱉으면 배치 안 함(방어)
    out = scene_match.match_scene_assets(plan, assets,
                                         vault_call=lambda *a, **k: {"best_asset_id": 999, "score": 0.9})
    assert "cutaway" not in out["beats"][0]
