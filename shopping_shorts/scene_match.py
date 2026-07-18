"""대본 비트 ↔ 라이브러리 자산 매칭(순수함수).

1차 필터(무료·기계적): asset_type=clip 且 source_origin ∈ {짜집기,촬영원본}.
  (비트에 category가 없으므로 category 축은 안 쓴다 — 설계 §9 해소.)
2차 판정(Gemini _vault_call 캐스케이드): 비트 나레이션 + 후보 다축 태그 →
  {best_asset_id, score}. 점수 ≥ 임계 → 자동배치(cutaway), < 임계 → 제안만.

저신뢰 자동배치 금지: 오배치 손해가 비대칭(엉뚱한 짤이 라이브 영상에 박히는 것 >
짤 안 쓰는 것). 캐스케이드가 None(키 소진) → 조용한 실패(자동배치 없음, 예외 없음).
"""
import copy

from . import edit_plan

_ALLOWED_ORIGIN = ("짜집기", "촬영원본")

_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "best_asset_id": {"type": "integer"},
        "score": {"type": "number"},
    },
    "required": ["best_asset_id", "score"],
}


def _candidates(assets):
    return [a for a in assets
            if a.get("asset_type") == "clip" and a.get("source_origin") in _ALLOWED_ORIGIN]


def _prompt(narration, cands):
    lines = [f"- id={a['id']}: 소재={a.get('subject')}, 장면={a.get('scene_desc')}, "
             f"키워드={','.join(a.get('keywords') or [])}" for a in cands]
    joined = "\n".join(lines)
    return (
        "다음 나레이션에 화면으로 곁들일 b-roll 짤을 후보 중에서 고른다.\n"
        f"나레이션: \"{narration}\"\n"
        f"후보:\n{joined}\n"
        "나레이션이 말하는 사물·동작과 가장 잘 맞는 후보의 id와 적합도(0~1)를 반환하라. "
        "맞는 게 없으면 score를 낮게. 보이는 것만 근거로, 억지로 고르지 마라."
    )


def match_scene_assets(plan, assets, *, threshold=0.6, vault_call=None):
    vault_call = vault_call or edit_plan._vault_call
    plan = copy.deepcopy(plan)
    cands = _candidates(assets)
    by_id = {a["id"]: a for a in cands}
    suggestions = []
    if cands:
        for beat in plan["beats"]:
            res = vault_call(_prompt(beat["narration"], cands), _MATCH_SCHEMA)
            if not res:
                continue  # 키 소진 등 → 조용한 실패
            aid = res.get("best_asset_id")
            score = float(res.get("score") or 0.0)
            if aid not in by_id:
                continue  # 모델이 후보 밖 id를 뱉음 → 방어
            if score >= threshold:
                beat["cutaway"] = {"asset_id": aid, "score": score}
            else:
                suggestions.append({"beat_idx": beat["beat_idx"], "asset_id": aid, "score": score})
    plan["asset_suggestions"] = suggestions
    return plan
