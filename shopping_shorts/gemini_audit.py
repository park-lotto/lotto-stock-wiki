"""제미니 일일 검열 — 흡수 파이프라인이 '일을 잘하고 있나'를 매일 측정.

세 층위(2026-07-23 설계):
  · 가동 성공률 = 실제 제미니 호출(attempted) 대비 성공(succeeded). 429·에러로 실패한 건이
    지금까지 조용히 버려져 안 보였다 → 명시적으로 센다.
  · 산출 완성도 = 성공한 소스의 structure_json이 hook·spine.beat_chain·부품을 빠짐없이 채웠나.
  · 산출 품질   = 훅 스팸율(참여유도 멘트 비율).

순수함수만 둔다(계산·판정). 저장·조회는 호출부(app._bank_ingest_collected_bg)가 한다."""

# 신호등 임계 — 하나라도 걸리면 그 색. 적신호가 주의를 이긴다.
_SUCCESS_MIN = 0.5       # 미만이면 🔴 (오늘 497→33=7%가 바로 이 케이스)
_COMPLETE_MIN = 0.7      # 미만이면 🟡
_SPAM_MAX = 0.15         # 초과면 🟡
_BEAT_MIN = 3            # beat_chain 유효 최소 길이
_PARTS_MIN = 5           # 부품 버킷 총합 최소


def audit_health(metrics):
    """검열 지표 → {level, reasons}. 지표가 None이면 그 항목은 판정에서 제외."""
    reasons = []
    red = False
    yellow = False

    sr = metrics.get("success_rate")
    if sr is not None and sr < _SUCCESS_MIN:
        red = True
        reasons.append(f"가동 성공률 {round(sr * 100)}% — 쿼터/에러로 대량 실패(키풀 로테이션 점검)")

    cr = metrics.get("completeness_rate")
    if cr is not None and cr < _COMPLETE_MIN:
        yellow = True
        reasons.append(f"산출 완성도 {round(cr * 100)}% — 훅/스토리구조 누락분 있음")

    spam = metrics.get("hook_spam_ratio")
    if spam is not None and spam > _SPAM_MAX:
        yellow = True
        reasons.append(f"훅 스팸율 {round(spam * 100)}% — 참여유도 멘트가 훅으로 섞임")

    level = "🔴" if red else ("🟡" if yellow else "🟢")
    return {"level": level, "reasons": reasons}


def _is_complete(structure):
    """성공한 소스 하나가 통째로 잘 뽑혔나 — hook 있고 beat_chain 길이≥3, 부품 총합≥5."""
    if not isinstance(structure, dict):
        return False
    if not (structure.get("hook") or []):
        return False
    spine = structure.get("spine") or {}
    beat = spine.get("beat_chain") if isinstance(spine, dict) else None
    if not (isinstance(beat, list) and len(beat) >= _BEAT_MIN):
        return False
    parts = 0
    for k, v in structure.items():
        if k == "spine":
            continue
        if isinstance(v, list):
            parts += len([x for x in v if (x or "")])
    return parts >= _PARTS_MIN


def compute_audit(attempted, succeeded, structures, hook_total, hook_bait):
    """계측값 → 검열 지표 묶음(신호등 포함). 0 나눗셈은 None으로 안전 처리.

    attempted: 실제 제미니 호출 수(중복·짧은 것 제외 후).
    succeeded: source_id 생성 성공 수.
    structures: 성공한 소스들의 structure_json(dict) 리스트.
    hook_total: 추출된 훅 총수(차단 전). hook_bait: 그중 스팸으로 차단한 수."""
    success_rate = (succeeded / attempted) if attempted else None
    completeness_rate = (
        sum(1 for s in structures if _is_complete(s)) / len(structures)
        if structures else None
    )
    hook_spam_ratio = (hook_bait / hook_total) if hook_total else None
    metrics = {
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": max(0, attempted - succeeded),
        "success_rate": success_rate,
        "completeness_rate": completeness_rate,
        "hook_total": hook_total,
        "hook_bait": hook_bait,
        "hook_spam_ratio": hook_spam_ratio,
    }
    metrics["health"] = audit_health(metrics)
    return metrics
