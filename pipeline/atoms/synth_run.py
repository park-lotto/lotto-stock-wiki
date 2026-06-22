"""오케스트레이터: 반도체 1섹터 종합 실행. 설계 §3."""
import argparse, json
from datetime import date, timedelta
from pathlib import Path

from .db import get_conn, init_db
from .synth_qc import dedupe, route
from .verify_gate import grade
from .synth_engine import synth_stock, synth_sector
from .synth_rollup import build_index

_ROOT = Path(__file__).parent.parent.parent
_STAGING = Path(__file__).parent / "staging"


def _load_atoms(sector: str, days: int) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conn = get_conn()
    rows = conn.execute(
        "SELECT date,content,asset,asset_level,raw_file,source_trust,certainty "
        "FROM atoms WHERE sector=? AND is_active=1 AND date>=?", (sector, cutoff)).fetchall()
    conn.close()
    return [dict(r) for r in rows]  # get_conn은 row_factory=sqlite3.Row 사용


def _find_stock_page(sector: str, name: str) -> Path | None:
    p = _ROOT / "wiki" / "L5_섹터" / sector / "stock" / f"stock_{name}.md"
    return p if p.exists() else None


def run_sector(sector: str = "반도체", *, days: int = 14, dry_run: bool = False):
    init_db()
    atoms = dedupe(_load_atoms(sector, days))
    for a in atoms:  # 검증등급 부여
        a["verdict"] = grade(a)
    routed = route(atoms)
    _STAGING.mkdir(exist_ok=True)

    # 종목 종합 (auto만 페이지로, staging은 적재)
    for name, items in routed["stock"].items():
        page = _find_stock_page(sector, name)
        if not page:
            continue
        autos = [a for a in items if a["verdict"]["route"] == "auto"]
        staged = [a for a in items if a["verdict"]["route"] == "staging"]
        if autos:
            synth_stock(page, autos, dry_run=dry_run)
        if staged:
            (_STAGING / f"{name}.json").write_text(
                json.dumps(staged, ensure_ascii=False, indent=2), encoding="utf-8")

    # 섹터 종합
    sector_page = _ROOT / "wiki" / "L5_섹터" / sector / f"sector_{sector}.md"
    sec_autos = [a for a in routed["sector"] if a["verdict"]["route"] == "auto"]
    if sector_page.exists() and sec_autos:
        synth_sector(sector_page, sec_autos, dry_run=dry_run)

    # 롤업
    index = build_index(_ROOT / "wiki" / "L5_섹터" / sector)
    if not dry_run:
        (_ROOT / "wiki" / "L5_섹터" / sector / "index_auto.md").write_text(index, encoding="utf-8")
    print(f"[synth] {sector}: 종목 {len(routed['stock'])} / 섹터원자 {len(routed['sector'])} / staging {len(list(_STAGING.glob('*.json')))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector", default="반도체")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_sector(args.sector, days=args.days, dry_run=args.dry_run)
