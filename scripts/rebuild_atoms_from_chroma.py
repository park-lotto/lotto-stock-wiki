"""atoms.db 유실 시 chroma 벡터스토어에서 원자를 재구성한다(무료, Gemini 불필요).

배경: 공유 워킹트리에서 동시 세션 git-hygiene가 gitignore된 atoms.db를 날린 적이 있다
(2026-07-06). chroma_db(pipeline/atoms/chroma_db)는 원자 content + 핵심 메타
(date/asset/sector/signal/source_trust)를 보존하므로, 이를 sqlite로 되돌려 즉시 복구한다.

한계(lossy): chroma 메타는 sqlite 스키마의 부분집합이라 source_type·source_name·
strength_score·event_type·relations 등은 기본값으로 채워진다. 데일리 재인제스트가
이후 정교화한다. 완전 복구가 필요하면 raw/에서 전면 재인제스트(atom_pipeline.py).

사용: py scripts/rebuild_atoms_from_chroma.py
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.atoms import db, vector_db


def _atom_from_chroma(aid: str, meta: dict, content: str) -> dict:
    """chroma 레코드 → insert_atom이 요구하는 완전한 dict(모든 컬럼 명시)."""
    meta = meta or {}
    return {
        "id": aid,
        "date": meta.get("date") or "1970-01-01",
        "source_type": meta.get("source_type") or "restore",
        "source_name": meta.get("source_name"),
        "source_trust": meta.get("source_trust") or "D",
        "raw_file": None,
        "layer": meta.get("layer"),
        "sector": meta.get("sector"),
        "asset": meta.get("asset"),
        "asset_level": meta.get("asset_level") or "sector",
        "signal": meta.get("signal") or "neutral",
        "event_type": meta.get("event_type") or "news",
        "magnitude": meta.get("magnitude") or "minor",
        "content_type": meta.get("content_type") or "fact",
        "strength_score": meta.get("strength_score") or 1,
        "validity_type": meta.get("validity_type") or "permanent",
        "validity_until": meta.get("validity_until"),
        "is_active": 1,
        "content": content,
        "relations": [],
    }


def main() -> int:
    db.init_db()
    col = vector_db.get_collection()
    total = col.count()
    got = col.get(include=["metadatas", "documents"])  # ids는 항상 포함
    ids, metas, docs = got["ids"], got["metadatas"], got["documents"]

    restored = skipped = 0
    for i, aid in enumerate(ids):
        content = docs[i] if i < len(docs) else None
        if not content:
            skipped += 1
            continue
        db.insert_atom(_atom_from_chroma(aid, metas[i] if i < len(metas) else {}, content))
        restored += 1

    print(f"chroma atoms: {total} | restored: {restored} | skipped(no content): {skipped}")
    print(f"atoms.db 최종 count: {db.get_atom_count(active_only=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
