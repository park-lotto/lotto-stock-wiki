"""기존 '기타' 원자를 개선된 resolve_sector로 재분류 + ChromaDB 메타 재반영.

asset 자체 정규화 / 종목→섹터 맵 / 외국주 맵을 다시 적용한다.
asset_level이 market/macro/theme이면 섹터 무관이므로 건드리지 않는다.

실행:  python -m pipeline.atoms.backfill_sector            # 실제 반영
       python -m pipeline.atoms.backfill_sector --dry-run  # 미리보기
"""
import argparse
from collections import Counter

from .db import get_conn
from .sector_classify import resolve_sector
from .stock_resolve import _HANGUL


def run(dry_run: bool = False) -> None:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, asset, asset_level, sector FROM atoms "
        "WHERE sector='기타' AND is_active=1 AND asset!='' AND asset IS NOT NULL"
    ).fetchall()

    changes: list[tuple[str, str]] = []  # (id, new_sector)
    dist = Counter()
    for r in rows:
        atom_id, asset, level, _ = r[0], (r[1] or "").strip(), (r[2] or ""), r[3]
        # 시장/매크로/테마 레벨은 섹터 무관 — 스킵
        if level in ("market", "macro", "theme"):
            continue
        is_foreign = not bool(_HANGUL.search(asset))
        secs, src = resolve_sector(asset, None, is_foreign=is_foreign)
        new_sec = secs[0]
        if new_sec != "기타":
            changes.append((atom_id, new_sec))
            dist[f"{new_sec} ({src})"] += 1

    print(f"기타 원자 {len(rows)}개 중 재분류 대상: {len(changes)}개")
    for k, n in dist.most_common():
        print(f"  {k}: {n}개")

    if dry_run:
        print("\n[DRY-RUN] 변경 미반영")
        conn.close()
        return

    # SQLite 갱신
    for atom_id, new_sec in changes:
        conn.execute("UPDATE atoms SET sector=? WHERE id=?", (new_sec, atom_id))
    conn.commit()

    # ChromaDB 메타데이터 갱신
    try:
        from .vector_db import get_collection
        col = get_collection()
        for atom_id, new_sec in changes:
            try:
                col.update(ids=[atom_id], metadatas=[{"sector": new_sec}])
            except Exception:
                pass
    except Exception as e:
        print(f"[WARN] ChromaDB 메타 갱신 일부 실패: {e}")

    conn.close()
    print(f"\n완료: {len(changes)}개 원자 섹터 재분류")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(dry_run=args.dry_run)
