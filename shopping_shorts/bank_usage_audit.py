"""생성 순응 검열 — 빼쓰기(생성) 시 은행이 대본을 실제로 형성했나를 결정적으로 측정.

순수함수만(계산·판정). 저장·조회·Gemini는 호출부(mix_pipeline)가 한다.
기존 gemini_audit.py(넣기 쪽 검열)의 빼기 쪽 대응."""

_PARTS_MIN = 5
_BEAT_MIN = 5
# 신호등 임계 — 하나라도 걸리면 그 색(적신호가 주의를 이긴다).
_BANK_USED_MIN = 0.5
_CONFORMANCE_MIN = 0.7
_PLAGIARISM_MAX = 0.1
_ARC_MIN = 2.5   # 5점 만점


def _opener_ok(narration):
    """beats[0]이 강한 오프너인가 — edit_plan의 토큰 재사용."""
    from shopping_shorts.edit_plan import _STRONG_OPENER_TOKENS
    head = (narration or "").lstrip()[:14]
    return any(t.strip() and t.strip() in head for t in _STRONG_OPENER_TOKENS)


def structural_conformance(chosen_plan, snapshot, story):
    """선택 후보가 아크가 규정하는 '모양'을 가졌나 — LLM 없이."""
    beats = (chosen_plan or {}).get("beats") or []
    need = max((snapshot or {}).get("spine_beats") or 0, _BEAT_MIN)
    beat_ok = len(beats) >= need
    opener_ok = bool(beats) and _opener_ok(beats[0].get("narration"))
    cta_ok = bool(((story or {}).get("cta_line") or "").strip())
    plagiarism_hits = len((chosen_plan or {}).get("plagiarism_flags") or [])
    conformant = beat_ok and opener_ok and cta_ok and plagiarism_hits == 0
    return {"beat_ok": beat_ok, "opener_ok": opener_ok, "cta_ok": cta_ok,
            "plagiarism_hits": plagiarism_hits, "conformant": conformant}


def judge_snapshot(candidates):
    """심사위원(candidate_judge) 결과를 그대로 기록 — 추가 계산 없음."""
    cands = candidates or []
    rec = next((c for c in cands if c.get("recommended")), cands[0] if cands else None)
    jr = (rec or {}).get("judge") if rec else None
    scores = sorted((c.get("score") or 0.0) for c in cands)
    best_gap = round(scores[-1] - scores[-2], 3) if len(scores) >= 2 else None
    if not jr:
        return {"judged": False, "total": None, "axes": None, "best_gap": best_gap}
    return {"judged": True, "total": jr.get("total"),
            "axes": {k: jr.get(k) for k in ("script_quality", "scene_sync", "storyline")},
            "best_gap": best_gap}


def usage_health(agg):
    """집계 지표 → {level, reasons}. 지표가 None이면 그 항목은 판정 제외."""
    reasons = []
    red = yellow = False
    bur = agg.get("bank_used_rate")
    if bur is not None and bur < _BANK_USED_MIN:
        red = True
        reasons.append(f"은행 사용률 {round(bur * 100)}% — 절반+ job에서 은행 무용(승인 부품·스파인 부족)")
    cpr = agg.get("conformance_pass_rate")
    if cpr is not None and cpr < _CONFORMANCE_MIN:
        yellow = True
        reasons.append(f"구조 순응 {round(cpr * 100)}% — 훅/CTA/비트 누락분")
    pr = agg.get("plagiarism_rate")
    if pr is not None and pr > _PLAGIARISM_MAX:
        yellow = True
        reasons.append(f"표절율 {round(pr * 100)}% — 은행을 그대로 베낀 조각 섞임")
    comp = agg.get("compliance")
    if comp and comp.get("arc_avg") is not None and comp["arc_avg"] < _ARC_MIN:
        yellow = True
        reasons.append(f"순응샘플 아크 {comp['arc_avg']}/5 — 제미니가 주입 아크 무시 경향")
    level = "🔴" if red else ("🟡" if yellow else "🟢")
    return {"level": level, "reasons": reasons}


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def compute_usage_audit(recent):
    """job 레코드 리스트 → 집계 지표 + 신호등. 빈 리스트도 None-safe."""
    recent = recent or []
    n = len(recent)

    def rate(pred):
        return round(sum(1 for r in recent if pred(r)) / n, 3) if n else None

    snaps = [r.get("snapshot") or {} for r in recent]
    confs = [r.get("conformance") or {} for r in recent]
    judged = [r.get("judge") for r in recent if (r.get("judge") or {}).get("judged")]
    comps = [r.get("compliance") for r in recent if r.get("compliance")]
    compliance = None
    if comps:
        compliance = {
            "arc_avg": _mean([c.get("arc_follow") for c in comps]),
            "flavor_avg": _mean([c.get("flavor_follow") for c in comps]),
            "verbatim_rate": round(sum(1 for c in comps if c.get("verbatim_copy")) / len(comps), 3),
            "n": len(comps),
        }
    agg = {
        "n": n,
        "bank_used_rate": round(sum(1 for s in snaps if not s.get("empty")) / n, 3) if n else None,
        "spine_present_rate": round(sum(1 for s in snaps if s.get("spine_present")) / n, 3) if n else None,
        "parts_avg": _mean([s.get("parts_total") for s in snaps]),
        "conformance_pass_rate": round(sum(1 for c in confs if c.get("conformant")) / n, 3) if n else None,
        "plagiarism_rate": rate(lambda r: (r.get("conformance") or {}).get("plagiarism_hits", 0) > 0),
        "judge_avg": _mean([j.get("total") for j in judged]),
        "compliance": compliance,
    }
    agg["health"] = usage_health(agg)
    return agg
