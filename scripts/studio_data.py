"""브리핑 데이터 확보 — daily_scenario 산출물(out/scenario_{date}.md)을 파싱해 dict로.

daily_scenario 실제 형식은 이모지 섹션 마커를 쓴다(## 헤더 아님):
  ━━━ {date} 시장 브리핑 ━━━
  📌 오늘 핵심        • 불릿…
  🔴 강세 종목        (표) 종목명  TP·수치  핵심이유
  🔵 리스크 종목
  ⚠️ 리스크
  📅 챙길 일정
  💡 시나리오         강세:/약세:
  🎯 오늘 한 줄        한 줄 요약
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"

# 섹션 시작을 알리는 이모지 마커 → 내부 키
_MARKERS = {
    "📌": "core",        # 오늘 핵심
    "🔴": "strong",      # 강세 종목
    "🔵": "risk_stocks", # 리스크 종목
    "⚠️": "risk",        # 리스크
    "📅": "schedule",    # 챙길 일정
    "💡": "scenario",    # 시나리오
    "🎯": "one_liner",   # 오늘 한 줄
}


def _parse_sections(md: str) -> dict:
    """이모지 마커 기준으로 본문을 섹션별 라인 리스트로 분해."""
    sections: dict[str, list[str]] = {}
    cur = None
    for raw in md.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("━"):  # 타이틀 구분선 → 섹션 리셋
            cur = None
            continue
        hit = next((key for em, key in _MARKERS.items() if s.startswith(em)), None)
        if hit:
            cur = hit
            sections[cur] = []
            continue
        if cur:
            sections[cur].append(s)
    return sections


def _strong_names(rows: list[str]) -> list[str]:
    """🔴 강세 종목 표에서 종목명(첫 토큰)만 추출. 헤더행 제외."""
    names = []
    for row in rows:
        if "종목명" in row:  # 표 헤더행
            continue
        parts = row.split()
        if parts:
            names.append(parts[0])
    return names


def get_briefing_data(date: str) -> dict:
    path = OUT_DIR / f"scenario_{date}.md"
    base = {"date": date, "headline": "", "market_mood": "",
            "lead_sectors": [], "lines": [], "source": ""}
    if not path.exists():
        return base

    md = path.read_text(encoding="utf-8")
    sec = _parse_sections(md)

    core = [ln.lstrip("•").strip() for ln in sec.get("core", [])]
    one_liner = sec.get("one_liner", [])
    scenario = sec.get("scenario", [])
    strong = _strong_names(sec.get("strong", []))

    headline = (one_liner[0] if one_liner else (core[0] if core else ""))
    base.update({
        "headline": headline,
        "market_mood": headline,
        "lead_sectors": strong[:4],          # 강세 종목명을 하이라이트 칩으로
        "lines": (core or scenario)[:5],     # 오늘 핵심 불릿 우선, 없으면 시나리오
        "source": path.name,
    })
    return base
