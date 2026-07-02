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


def _recent_mentioned_assets(name: str, days: int = 3) -> set:
    """그가 최근 실제 언급/스탠스한 종목명 집합 (검증용)."""
    out = set()
    for a in atoms_for(name, asset_levels=["stock", "stance"], days=days, limit=200):
        for tok in (a.get("asset") or "").replace("/", ",").split(","):
            tok = tok.strip()
            if tok and len(tok) >= 2:
                out.add(tok)
    return out


def _match(a: str, b: str) -> bool:
    return a in b or b in a


def routine_today(name: str) -> dict | None:
    """오늘의 루틴 재구성 — 그의 정적 루틴을 오늘 실제 데이터/발언으로 채움.
    data_key 스텝은 오늘 지표로, 시장판단은 오늘 그의 market/macro 원자로."""
    rt = _routine(name)
    if not rt:
        return None
    from pipeline.people.sortino_data import load_sortino_top
    from pipeline.people import funnel as _f

    sortino = load_sortino_top()
    data = _f._load()
    stocks = data.get("stocks", {})
    n_vac = sum(1 for s in stocks.values()
                if (s.get("osc") or {}).get("pct") is not None
                and s["osc"]["pct"] <= _f.THRESHOLDS["vacuum_pct_max"])
    n_up = sum(1 for s in stocks.values()
               if ((s.get("tp") or {}).get("up_count") or 0)
               > ((s.get("tp") or {}).get("down_count") or 0))
    sectors = ", ".join((sortino.get("sectors") or [])[:6]) or "—"
    metrics = {
        "osc": f"오늘 수급빈집 {n_vac}종목 (osc pct≤{_f.THRESHOLDS['vacuum_pct_max']})",
        "rs": f"오늘 소라티노 주도섹터: {sectors}",
        "consensus": f"오늘 컨센 상향 {n_up}종목",
        "tp": f"오늘 컨센 상향 {n_up}종목",
    }
    # data_key 스텝에 오늘 지표 부착
    for phase in rt["routine"]:
        for step in phase["steps"]:
            dk = [k.strip() for k in (step.get("data_key") or "").split(",") if k.strip()]
            step["today"] = list(dict.fromkeys(metrics[k] for k in dk if k in metrics))

    market = atoms_for(name, asset_levels=["market", "macro"], days=1, limit=20)
    return {
        "date": data.get("date"),
        "philosophy": rt.get("philosophy", []),
        "routine": rt["routine"],
        "market_today": [_slim(a) for a in market],
        "extracted_from": rt.get("extracted_from", ""),
    }


def today_selection(name: str, mention_days: int = 3) -> dict:
    """복사: 그의 규칙을 오늘 데이터에 적용한 종목선정 재현 + 검증(그의 실제 언급 대조).
    데이터 파일(taerini_stock.json 등) 연결된 채널만 가능."""
    cfg = get_person(name)
    if not cfg.get("data_files"):
        return {"available": False,
                "note": "이 채널은 데이터 파일 연결이 없어(발언만) 종목선정 재현 불가"}
    from pipeline.people.funnel import select
    sel = select()

    # 검증 — 퍼널 후보가 그가 실제 최근 언급한 종목과 얼마나 겹치나
    mentioned = _recent_mentioned_assets(name, days=mention_days)
    cand_names = [c["name"] for c in sel["candidates"]]
    for c in sel["candidates"]:
        c["he_mentioned"] = any(_match(c["name"], m) for m in mentioned)
    matched = [n for n in cand_names if any(_match(n, m) for m in mentioned)]
    missed = sorted(m for m in mentioned
                    if not any(_match(m, n) for n in cand_names))
    sel["validation"] = {
        "mention_days": mention_days,
        "mentioned_count": len(mentioned),
        "matched": matched,          # 퍼널이 뽑았고 그도 언급 (일치)
        "missed": missed[:25],       # 그는 언급했으나 퍼널이 놓침 (튜닝 힌트)
        "hit_rate": (round(len(matched) / len(cand_names), 2) if cand_names else None),
    }
    return {"available": True, **sel}


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
