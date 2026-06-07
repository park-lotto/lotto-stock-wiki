"""
embed_all.py — atoms.db의 모든 활성 원자를 ChromaDB에 일괄 임베딩.

사용법:
    python -m pipeline.atoms.embed_all           # 미임베딩 원자만 처리
    python -m pipeline.atoms.embed_all --force   # 전체 재임베딩
"""
import sys
import time
from pathlib import Path

from .db import init_db, get_conn
from .vector_db import embed_and_store, get_embedding_count, get_collection


def embed_all(force: bool = False) -> int:
    init_db()
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, date, sector, asset, signal, source_trust, content "
        "FROM atoms WHERE is_active = 1"
    ).fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        print("[OK] 저장된 원자 없음")
        return 0

    if not force:
        try:
            existing_ids = set(get_collection().get()["ids"])
        except Exception:
            existing_ids = set()
    else:
        existing_ids = set()

    pending = [dict(r) for r in rows if dict(r)["id"] not in existing_ids]
    if not pending:
        print(f"[OK] 모든 원자 이미 임베딩됨 (총 {get_embedding_count()}개)")
        return 0

    print(f"[INFO] {len(pending)}개 원자 임베딩 시작 (전체 {total}개 중 미처리 {len(pending)}개)")

    count = 0
    for i, atom in enumerate(pending):
        try:
            embed_and_store(atom)
            count += 1
        except Exception as e:
            print(f"[WARN] {atom['id']} 임베딩 실패: {e}")
            continue

        if (i + 1) % 10 == 0 or (i + 1) == len(pending):
            print(f"  진행: {i+1}/{len(pending)} (완료: {count})")

        time.sleep(0.1)

    print(f"[OK] {count}개 원자 임베딩 완료 (전체 DB: {get_embedding_count()}개)")
    return count


if __name__ == "__main__":
    force = "--force" in sys.argv
    embed_all(force=force)
