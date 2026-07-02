"""brain_view.py — 대시보드 '브레인' 탭용 데이터 레이어.

여러 채널(사람)을 목록으로 보여주고, 각 사람의 브레인(사고 골격 + 라이브 스탠스 +
발언 로그)을 조립한다. 스탠스·발언은 atoms.db에서 실시간 조회(항상 최신),
골격(§0~4)은 wiki/people/{사람}.md의 첫 AUTO 마커 이전 텍스트에서 읽는다.

CLI:
    python -m pipeline.people.brain_view              # 사람 목록
    python -m pipeline.people.brain_view 태린이아빠   # 개인 뷰 요약
"""
import sys
import io
import json
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pipeline.people.registry import load_registry, get_person
from pipeline.people.people_query import atoms_for

_ROOT = Path(__file__).parent.parent.parent
_ROUTINE_DIR = Path(__file__).parent / "routines"

# 뷰로 내보낼 원자 필드(원문 보존, 노이즈 제거)
_ATOM_FIELDS = ("date", "sector", "asset", "signal", "content_type",
                "content", "source_name", "stance_key")


def _slim(atom: dict) -> dict:
    return {k: atom.get(k) for k in _ATOM_FIELDS}


def _skeleton_md(person_cfg: dict) -> str:
    """브레인 페이지에서 첫 AUTO 마커 이전(=§0~4 수동 골격) 원문을 반환. 없으면 ''."""
    rel = person_cfg.get("brain_page")
    if not rel:
        return ""
    path = _ROOT / rel
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    marker = text.find("<!-- AUTO:")
    return text[:marker].rstrip() if marker != -1 else text.rstrip()


def _routine(name: str) -> dict | None:
    """사람의 일일 사고 루틴(있으면). routines/{name}.json."""
    path = _ROUTINE_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_people() -> list[dict]:
    """추적 중인 모든 사람 요약 카드용 목록."""
    out = []
    for name, cfg in load_registry().items():
        stances = atoms_for(name, stance_only=True, days=60, limit=200)
        recent = atoms_for(name, days=30, limit=1)
        out.append({
            "name": name,
            "display": cfg.get("display", name),
            "trust": cfg.get("trust", ""),
            "tracking_since": cfg.get("tracking_since", ""),
            "stance_count": len(stances),
            "latest_date": recent[0]["date"] if recent else None,
            "has_skeleton": bool(_skeleton_md(cfg)),
            "has_routine": _routine(name) is not None,
        })
    # 최근 발언 있는 사람 우선, 그다음 이름순
    out.sort(key=lambda p: (p["latest_date"] or "", p["name"]), reverse=True)
    return out


# ── 3버킷 (사용자 정의: 시장인사이트 · 종목선정방법 · 섹터종목재료) ──
def market_insight(name: str, days: int = 30, limit: int = 40) -> list[dict]:
    """1. 시장 생각 인사이트 — market/macro 레벨 원자 타임라인."""
    return [_slim(a) for a in atoms_for(
        name, asset_levels=["market", "macro"], days=days, limit=limit)]


def methods(name: str, days: int = 120, limit: int = 60) -> list[dict]:
    """2. 종목선정·매매 방법론 — method 레벨 원자."""
    return [_slim(a) for a in atoms_for(
        name, asset_levels=["method"], days=days, limit=limit)]


def materials(name: str, query: str = None, days: int = 90, limit: int = 60) -> list[dict]:
    """3. 섹터·종목 재료 — stock/sector 레벨 원자. query로 종목/섹터 검색(꺼내쓰기)."""
    return [_slim(a) for a in atoms_for(
        name, asset_levels=["stock", "sector"], asset=query, days=days, limit=limit)]


def today_selection(name: str) -> dict:
    """복사: 그의 규칙을 오늘 데이터에 적용한 종목선정 재현.
    데이터 파일(taerini_stock.json 등) 연결된 채널만 가능."""
    cfg = get_person(name)
    if not cfg.get("data_files"):
        return {"available": False,
                "note": "이 채널은 데이터 파일 연결이 없어(발언만) 종목선정 재현 불가"}
    from pipeline.people.funnel import select
    return {"available": True, **select()}


def person_view(name: str) -> dict:
    """한 사람의 브레인 전체 뷰."""
    cfg = get_person(name)  # 없으면 KeyError
    return {
        "name": name,
        "display": cfg.get("display", name),
        "trust": cfg.get("trust", ""),
        "tracking_since": cfg.get("tracking_since", ""),
        "sources": cfg.get("sources", []),
        "routine": _routine(name),
        "skeleton_md": _skeleton_md(cfg),
        "live_stance": [_slim(a) for a in
                        atoms_for(name, stance_only=True, days=60, limit=60)],
        "market_insight": market_insight(name),   # 1. 시장 인사이트
        "methods": methods(name),                 # 2. 종목선정 방법
        "materials": materials(name, limit=40),    # 3. 섹터·종목 재료 (기본)
        "speech_log": [_slim(a) for a in
                       atoms_for(name, days=14, limit=50)],
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(person_view(sys.argv[1]), ensure_ascii=False, indent=2))
    else:
        for p in list_people():
            print(f"{p['display']:12s} 스탠스 {p['stance_count']:3d}개 · "
                  f"최근 {p['latest_date']} · 골격 {'O' if p['has_skeleton'] else 'X'}")
