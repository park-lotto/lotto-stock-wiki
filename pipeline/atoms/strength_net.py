"""미귀속 강세 스캐너 (Phase 1). 히트맵 강세를 기존 atoms.db로 귀속 판정한다."""

_TIER_BY_SOURCE = {
    "공시": "🟢", "dart": "🟢", "disclosure": "🟢",
    "news": "🟢", "뉴스": "🟢",
    "telegram": "🟡", "텔레그램": "🟡",
    "종토방": "🟠", "naver_board": "🟠",
}

def trust_tier(atom: dict) -> str:
    """atom의 source_type을 신뢰등급 이모지로. 미지의 소스는 🔵(추론급)."""
    st = (atom.get("source_type") or "").strip().lower()
    for key, tier in _TIER_BY_SOURCE.items():
        if key.lower() == st:
            return tier
    return "🔵"
