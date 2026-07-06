"""미귀속 강세 스캐너 (Phase 1). 히트맵 강세를 기존 atoms.db로 귀속 판정한다."""
from pipeline.atoms import db as _db

_TIER_BY_SOURCE = {
    "공시": "🟢", "dart": "🟢", "disclosure": "🟢",
    "news": "🟢", "뉴스": "🟢",
    "telegram": "🟡", "텔레그램": "🟡",
    "종토방": "🟠", "naver_board": "🟠",
}

_BULLISH_SIGNALS = {"bullish", "positive", "상승", "호재"}
_UNATTR_FLAG = "⚠️ 원인 미상 강세 — 추적 요망"

def trust_tier(atom: dict) -> str:
    """atom의 source_type을 신뢰등급 이모지로. 미지의 소스는 🔵(추론급)."""
    st = (atom.get("source_type") or "").strip().lower()
    for key, tier in _TIER_BY_SOURCE.items():
        if key.lower() == st:
            return tier
    return "🔵"

def attribute_mover(mover: dict, days: int = 3, query_fn=None) -> dict:
    """한 강세 종목에 대해 기존 atom에서 귀속 이슈를 찾는다. 없으면 미귀속으로 승격."""
    if query_fn is None:
        query_fn = _db.query_atoms
    name = mover.get("name")
    atoms = query_fn(asset=name, days=days, active_only=True) or []
    hits = [a for a in atoms if (a.get("signal") or "").strip().lower() in _BULLISH_SIGNALS
            or (a.get("signal") or "").strip() in _BULLISH_SIGNALS]
    base = {
        "name": name, "code": mover.get("code"),
        "sector": mover.get("sector"), "rate": mover.get("rate"),
    }
    if not hits:
        return {**base, "attributed": False, "issue": None, "trust": None,
                "source": None, "atom_ids": [], "status": "unattributed",
                "priority": 0, "flag": _UNATTR_FLAG}
    hits.sort(key=lambda a: a.get("strength_score", 1), reverse=True)
    top = hits[0]
    return {**base, "attributed": True, "issue": top.get("content"),
            "trust": trust_tier(top), "source": top.get("source_name"),
            "atom_ids": [a["id"] for a in hits], "status": "attributed",
            "priority": 1, "flag": None}

def scan_movers(movers: list, days: int = 3, query_fn=None) -> list:
    """모든 강세 종목을 귀속 판정. 입력 종목은 하나도 누락하지 않는다(침묵 금지)."""
    return [attribute_mover(m, days=days, query_fn=query_fn) for m in movers]

def rank_results(results: list) -> list:
    """정렬 반전: 미귀속(priority 0)을 최상단, 각 그룹 내 rate 내림차순."""
    return sorted(results, key=lambda r: (r.get("priority", 1), -(r.get("rate") or 0)))

def coverage_metrics(results: list, input_count: int = None) -> dict:
    """그물 촘촘함 지표. silent_miss>0 이면 침묵 금지 규칙 위반 신호."""
    total = len(results)
    attributed = sum(1 for r in results if r.get("status") == "attributed")
    unattributed = total - attributed
    n_in = total if input_count is None else input_count
    return {
        "total": total,
        "attributed": attributed,
        "unattributed": unattributed,
        "coverage_rate": (attributed / total) if total else 0.0,
        "silent_miss": max(0, n_in - total),
    }
