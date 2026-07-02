"""people_query.py — 사람별 원자 조회 (source_name IN sources).

CLI:
    python -m pipeline.people.people_query 태린이아빠
    python -m pipeline.people.people_query 태린이아빠 --content-type method --days 60
"""
import sys
import io
import json
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pipeline.atoms.db import get_conn
from pipeline.people.registry import source_names


def atoms_for(person, content_type=None, days=30, limit=50, active_only=True,
              stance_only=False, asset_levels=None, asset=None):
    sources = source_names(person)
    if not sources:
        return []
    conds = ["date >= date('now', ? || ' days')"]
    params = [f"-{days}"]
    placeholders = ",".join("?" * len(sources))
    conds.append(f"source_name IN ({placeholders})")
    params.extend(sources)
    if active_only:
        conds.append("is_active = 1")
    if content_type:
        conds.append("content_type = ?")
        params.append(content_type)
    if stance_only:
        conds.append("stance_key IS NOT NULL")
    if asset_levels:
        ph = ",".join("?" * len(asset_levels))
        conds.append(f"asset_level IN ({ph})")
        params.extend(asset_levels)
    if asset:
        conds.append("(asset LIKE ? OR sector LIKE ? OR content LIKE ?)")
        params.extend([f"%{asset}%", f"%{asset}%", f"%{asset}%"])
    sql = (
        f"SELECT * FROM atoms WHERE {' AND '.join(conds)} "
        f"ORDER BY date DESC, strength_score DESC LIMIT ?"
    )
    params.append(limit)
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("relations"):
            try:
                d["relations"] = json.loads(d["relations"])
            except (json.JSONDecodeError, TypeError):
                d["relations"] = []
        else:
            d["relations"] = []
        result.append(d)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="사람별 원자 조회")
    ap.add_argument("person")
    ap.add_argument("--content-type", default=None, help="fact|stance|method")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    atoms = atoms_for(args.person, content_type=args.content_type,
                      days=args.days, limit=args.limit)
    print(f"[{args.person}] 원자 {len(atoms)}개 (최근 {args.days}일)")
    for a in atoms:
        print(f"  {a['date']} [{a.get('content_type','')}] {a['source_name']} | "
              f"{a.get('sector','')}/{a.get('asset','')} | {a['content'][:80]}")
