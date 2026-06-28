"""브리핑 데이터 확보 — daily_scenario 산출물(out/scenario_{date}.md)을 파싱해 dict로."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"


def _section(md: str, title: str) -> list[str]:
    """## {title} 섹션의 본문 라인들(불릿 '-' 제거)을 반환."""
    lines = md.splitlines()
    out, capture = [], False
    for ln in lines:
        if ln.strip().startswith("## "):
            capture = title in ln
            continue
        if capture and ln.strip():
            out.append(ln.strip().lstrip("-").strip())
    return out


def get_briefing_data(date: str) -> dict:
    path = OUT_DIR / f"scenario_{date}.md"
    base = {"date": date, "headline": "", "market_mood": "",
            "lead_sectors": [], "lines": [], "source": ""}
    if not path.exists():
        return base
    md = path.read_text(encoding="utf-8")
    one_liner = _section(md, "오늘의 한 줄")
    sectors = _section(md, "주도 섹터")
    scenario = _section(md, "시나리오")
    base.update({
        "headline": one_liner[0] if one_liner else "",
        "market_mood": one_liner[0] if one_liner else "",
        "lead_sectors": sectors,
        "lines": scenario or one_liner,
        "source": path.name,
    })
    return base
