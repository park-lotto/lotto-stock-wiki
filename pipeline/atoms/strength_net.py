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

def _bullish_hits(atoms):
    hits = [a for a in (atoms or [])
            if (a.get("signal") or "").strip().lower() in _BULLISH_SIGNALS
            or (a.get("signal") or "").strip() in _BULLISH_SIGNALS]
    hits.sort(key=lambda a: a.get("strength_score", 1), reverse=True)
    return hits

def attribute_mover(mover: dict, days: int = 3, query_fn=None, related_fn=None) -> dict:
    """직접 원자 → 없으면 그래프-홉(같은 섹터 관련자산의 호재) → 없으면 미귀속(침묵 금지)."""
    if query_fn is None:
        query_fn = _db.query_atoms
    name = mover.get("name")
    base = {"name": name, "code": mover.get("code"),
            "sector": mover.get("sector"), "rate": mover.get("rate")}
    hits = _bullish_hits(query_fn(asset=name, days=days, active_only=True))
    if hits:
        top = hits[0]
        return {**base, "attributed": True, "issue": top.get("content"),
                "trust": trust_tier(top), "source": top.get("source_name"),
                "atom_ids": [a["id"] for a in hits], "status": "attributed",
                "priority": 1, "flag": None, "via": None}
    # 그래프-홉 폴백: 같은 섹터 관련자산의 호재 원자를 근거로 연계 귀속
    # related_fn은 종목명을 받아 그래프 2홉(종목→큰섹터→관련자산)으로 관련자산을 반환한다.
    if related_fn is not None:
        for rel in related_fn(name) or []:
            if rel == name:
                continue
            r_hits = _bullish_hits(query_fn(asset=rel, days=days, active_only=True))
            if r_hits:
                rt = r_hits[0]
                return {**base, "attributed": True,
                        "issue": f"연계: {rel} — {rt.get('content')}",
                        "trust": "🔵", "source": rt.get("source_name"),
                        "atom_ids": [a["id"] for a in r_hits], "status": "attributed",
                        "priority": 1, "flag": None, "via": rel}
    return {**base, "attributed": False, "issue": None, "trust": None,
            "source": None, "atom_ids": [], "status": "unattributed",
            "priority": 0, "flag": _UNATTR_FLAG, "via": None}

def scan_movers(movers: list, days: int = 3, query_fn=None, related_fn=None) -> list:
    """모든 강세 종목을 귀속 판정. 입력 종목은 하나도 누락하지 않는다(침묵 금지)."""
    return [attribute_mover(m, days=days, query_fn=query_fn, related_fn=related_fn) for m in movers]

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


def movers_from_heatmap(heatmap: dict, min_rate: float = 3.0) -> list:
    """build_heatmap() 반환 dict에서 min_rate 이상 강세 종목만 mover로 추출(순수).

    실제 형태: {"sectors": [{"name", "avg_rate", "stocks": [{"name","code","change_rate","price"}]}]}.
    - price==0(데이터 없음)은 제외.
    - 한 종목이 여러 섹터 타일에 나오면 최고 등락률 1건으로 dedup.
    """
    best = {}  # code -> mover(최고 rate)
    for sector in heatmap.get("sectors") or []:
        sec_name = sector.get("name")
        for st in sector.get("stocks") or []:
            code = st.get("code")
            rate = st.get("change_rate")
            if not code or rate is None or rate < min_rate:
                continue
            if (st.get("price") or 0) == 0:  # 가격 데이터 없음 = 유효 강세 아님
                continue
            prev = best.get(code)
            if prev is None or rate > prev["rate"]:
                best[code] = {"name": st.get("name"), "code": code,
                              "sector": sec_name, "rate": rate}
    return sorted(best.values(), key=lambda m: m["rate"], reverse=True)


def scan_heatmap(top_n: int = 5, days: int = 3, min_rate: float = 3.0) -> dict:
    """라이브 히트맵을 스캔해 랭킹된 미귀속 강세 목록 + 촘촘함 지표를 반환(impure 엔트리)."""
    import sys
    import pathlib
    scripts_dir = str(pathlib.Path(__file__).resolve().parents[2] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import sector_heatmap
    from pipeline.atoms import edges as _edges
    heatmap = sector_heatmap.build_heatmap(top_n=top_n)
    movers = movers_from_heatmap(heatmap, min_rate=min_rate)
    results = rank_results(scan_movers(movers, days=days, related_fn=_edges.related_assets))
    metrics = coverage_metrics(results, input_count=len(movers))
    return {"results": results, "metrics": metrics, "count": len(results),
            "updated_at": heatmap.get("updated_at")}
