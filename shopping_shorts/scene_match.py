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

# 비트 역할 → 호환 자산 역할(순위). 결정적 — Gemini 안 씀(과배치 원천차단).
# 자산 역할 통제어휘: 훅·반전·CTA·비법공개·반응·전환·본문(scene_assets._ROLES).
_ROLE_FALLBACK = {
    "hook": ("훅", "반응"),                       # 시선 잡기: 귀여운 리액션·만족짤
    "problem": ("반전",),                          # 페인포인트: 눈물 양파·요리 실패
    "problem_solution": ("반전",),
    "easy_process": ("비법공개", "전환"),          # "이렇게 쉽게": 만족 슬라이스
    "process_step1": ("비법공개", "전환"),
    "process_step2": ("비법공개", "전환"),
    "process": ("비법공개", "전환"),
    "result_wow": ("반응", "본문"),                # 와우 모먼트: ASMR 먹방
    "benefit": ("반응", "본문"),
    "cta": ("CTA",),
}

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
        "너는 영상 편집자다. 아래 나레이션 위에 b-roll(컷어웨이)로 얹을 짤을 후보 중에서 고른다.\n"
        f"나레이션: \"{narration}\"\n"
        f"후보(각 짤이 화면에 실제로 보여주는 것):\n{joined}\n\n"
        "판정 규칙(엄격히):\n"
        "- 짤이 나레이션이 말하는 **바로 그 사물이나 동작을 실제로 화면에 보여줄 때만** 높은 점수를 준다.\n"
        "- '주제가 비슷하다', '분위기가 맞다', '요리다', '살림이다' 같은 느슨한 연상은 **오배치**다 — b-roll은 말과 화면이 어긋나면 시청자가 즉시 이상함을 느낀다.\n"
        "- 후보 중 나레이션의 구체적 소재를 실제로 보여주는 게 없으면, 가장 가까운 것을 고르되 **score를 0.3 이하**로 줘라. 억지로 고신뢰를 매기지 마라.\n"
        "- 예: 나레이션이 '마법 가루를 넣는다'인데 후보가 '채 썬 오이'뿐이면 → 오이는 마법 가루가 아니다 → score 0.1~0.2.\n"
        "  나레이션이 '감자를 썬다'인데 후보에 '채 썬 감자'가 있으면 → 화면과 말이 일치 → score 0.9.\n"
        "가장 가까운 후보의 id와, 위 규칙에 따른 정직한 적합도(0~1)를 반환하라. 애매하면 낮게."
    )


def match_scene_assets(plan, assets, *, threshold=0.9, vault_call=None):
    # 임계 0.9 — 실 재료 grounding(2026-07-18)에서 확정. 자산과 무관한 주제의 대본에
    # Gemini가 억지 매칭을 딱 0.80~0.85로 뱉는 걸 관측했다(프롬프트에 반례를 넣어도 살아남음).
    # 진짜 일치(화면과 말이 같음)는 0.9~0.95로 갈리므로, 0.9+만 자동배치하고 그 아래는 전부
    # 제안으로 돌린다 = '저신뢰 자동배치 금지'의 보수적 못박기. 오배치 손해가 비대칭(엉뚱한
    # 짤이 라이브 영상에 박히는 것 > 짤 안 쓰는 것)이라 이쪽이 안전하다. 최종 안전망=검수판(사람).
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
                beat["cutaway"] = {"asset_id": aid, "score": score, "match_type": "subject"}
            else:
                suggestions.append({"beat_idx": beat["beat_idx"], "asset_id": aid, "score": score})
    _role_pass(plan, cands)
    plan["asset_suggestions"] = suggestions
    return plan


def _role_pass(plan, cands):
    """소재 패스가 못 채운 빈 비트에, 비트 역할에 맞는 요소짤을 결정적으로 배치한다.
    Gemini 안 씀 — 역할 호환표로만. plan을 제자리 수정. 한 영상 내 반복 금지."""
    used = {b["cutaway"]["asset_id"] for b in plan["beats"] if b.get("cutaway")}
    by_role = {}
    for a in cands:
        by_role.setdefault(a.get("role") or "", []).append(a)
    for beat in plan["beats"]:
        if beat.get("cutaway"):
            continue  # 소재 패스가 이미 배치 — 안 건드림
        compatible = _ROLE_FALLBACK.get(beat.get("role") or "")
        if not compatible:
            continue  # 이 비트 역할은 요소짤 자리가 아님 → 빈 채로
        pool = [a for role in compatible for a in by_role.get(role, [])
                if a["id"] not in used]
        if not pool:
            continue
        chosen = _pick_role_asset(pool, beat.get("narration") or "")
        beat["cutaway"] = {"asset_id": chosen["id"], "match_type": "role"}
        used.add(chosen["id"])


def _pick_role_asset(pool, narration):
    """역할 호환 후보 중 1개. 나레이션과 keyword/subject 겹치면 우선(Gemini 없음),
    없으면 결정적 순서(최근 담은 것 = id 큰 것 우선)."""
    def overlap(a):
        text = (a.get("subject") or "") + " " + " ".join(a.get("keywords") or [])
        return sum(1 for w in text.split() if w and w in narration)
    return sorted(pool, key=lambda a: (-overlap(a), -a["id"]))[0]
