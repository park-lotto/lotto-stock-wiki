"""
vector_db.py — ChromaDB 벡터 인덱스.

SQLite가 단일 진실 소스. ChromaDB는 벡터 검색 인덱스만 담당.
"""
import time
from pathlib import Path
from typing import Optional

import chromadb

from pipeline.atoms import key_vault

_CHROMA_PATH = Path(__file__).parent.parent.parent / "pipeline" / "atoms" / "chroma_db"
_COLLECTION_NAME = "atoms"

_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None


def _heal_hnsw_if_corrupt() -> None:
    """ChromaDB HNSW 인덱스 부패 감지 및 자동 수복.

    증상: index_metadata.pickle 존재 + HNSW max_seq_id > 0 → 반쪽 컴팩션 상태.
    처치: pickle 삭제 + HNSW 세그먼트 max_seq_id를 0으로 리셋 → 새 세션에서 클린 백필.
    """
    import sqlite3 as _sqlite3
    import os as _os

    # Delete stale index_metadata.pickle files
    for p in _CHROMA_PATH.glob("*/index_metadata.pickle"):
        _os.remove(p)

    # Reset HNSW segment max_seq_id to 0
    chroma_sqlite = _CHROMA_PATH / "chroma.sqlite3"
    if not chroma_sqlite.exists():
        return
    conn = _sqlite3.connect(str(chroma_sqlite))
    try:
        segs = conn.execute("SELECT id, type FROM segments").fetchall()
        for seg_id, seg_type in segs:
            if "hnsw" in seg_type.lower():
                conn.execute(
                    "UPDATE max_seq_id SET seq_id = 0 WHERE segment_id = ?",
                    (seg_id,),
                )
        conn.commit()
    finally:
        conn.close()


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        # Auto-heal HNSW corruption before opening client
        _heal_hnsw_if_corrupt()
        _client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
    return _client


def get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def embed_text(text: str) -> list[float]:
    """텍스트를 gemini-embedding-001로 임베딩 (3072차원).
    429는 대부분 분당 요청수(RPM) 제한이라 짧으면 1분 내 회복된다 — 일일 소진이 아니다.
    embed 전용 키 풀(key_vault 'embed' 그룹)을 한 바퀴 돌고,
    그래도 다 막히면 20초 대기 후 한 번 더 전체를 재시도한다."""
    for attempt in range(2):
        keys = key_vault.get_live_keys("embed")
        for key in keys:
            try:
                resp = key_vault.get_client_for_key(key).models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                )
                return list(resp.embeddings[0].values)
            except Exception as e:
                if key_vault.is_daily_exhausted_error(e):
                    key_vault.mark_exhausted("embed", key)
                    continue
                if key_vault.is_quota_error(e):
                    continue
                raise
        if attempt == 0:
            time.sleep(20)
    key_vault._tg_alert("🚨 <b>[embed] Gemini 임베딩 키 전체 소진(RPM)</b> — 20초 재시도 후에도 실패")
    raise RuntimeError("모든 Gemini 임베딩 키 한도 초과(RPM) — 20초 재시도 후에도 실패")


def embed_and_store(atom: dict) -> None:
    """원자 콘텐츠를 임베딩하여 ChromaDB에 upsert."""
    col = get_collection()
    embedding = embed_text(atom["content"])
    col.upsert(
        ids=[atom["id"]],
        embeddings=[embedding],
        metadatas=[{
            "date": atom.get("date", ""),
            "sector": atom.get("sector", "기타"),
            "signal": atom.get("signal", "neutral"),
            "asset": atom.get("asset", ""),
            "source_trust": atom.get("source_trust", "D"),
        }],
        documents=[atom["content"]],
    )


def delete_atom(atom_id: str) -> None:
    """ChromaDB에서 원자 삭제."""
    get_collection().delete(ids=[atom_id])


def get_embedding_count() -> int:
    """ChromaDB에 저장된 임베딩 수.

    ChromaDB Rust HNSW reader 오류 시 chroma.sqlite3에서 직접 카운트.
    """
    try:
        return get_collection().count()
    except Exception:
        import sqlite3 as _sqlite3
        chroma_sqlite = _CHROMA_PATH / "chroma.sqlite3"
        if not chroma_sqlite.exists():
            return 0
        conn = _sqlite3.connect(str(chroma_sqlite))
        try:
            return conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        finally:
            conn.close()


def query_similar(
    text: str,
    n_results: int = 10,
    sector: Optional[str] = None,
    signal: Optional[str] = None,
) -> list[dict]:
    """질문 텍스트를 임베딩하여 유사 원자를 반환.

    sector/signal 필터는 ChromaDB where 대신 Python 후처리로 적용.
    (ChromaDB Rust 레이어 where 필터가 세그먼트 누락 시 InternalError 발생하는 문제 우회)
    """
    from pipeline.atoms.db import get_conn

    query_embedding = embed_text(text)
    col = get_collection()
    count = col.count()
    if count == 0:
        return []

    # 필터가 있으면 여유분 확보, Python에서 후처리
    fetch_n = min(n_results * 5 if (sector or signal) else n_results, count)

    results = col.query(
        query_embeddings=[query_embedding],
        n_results=fetch_n,
    )

    ids = results["ids"][0]
    distances = results["distances"][0]

    if not ids:
        return []

    conn = get_conn()
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT * FROM atoms WHERE id IN ({placeholders})", ids
    ).fetchall()
    conn.close()

    id_to_row = {dict(r)["id"]: dict(r) for r in rows}
    id_to_dist = dict(zip(ids, distances))

    atoms = []
    for atom_id in ids:
        if atom_id not in id_to_row:
            continue
        atom = dict(id_to_row[atom_id])
        # Python 레벨 필터
        if sector and atom.get("sector", "") != sector:
            continue
        if signal and atom.get("signal", "") != signal:
            continue
        atom["similarity_score"] = round(1.0 - id_to_dist[atom_id], 4)
        if atom.get("relations"):
            import json as _json
            try:
                atom["relations"] = _json.loads(atom["relations"])
            except Exception:
                atom["relations"] = []
        atoms.append(atom)

    atoms = sorted(atoms, key=lambda a: a["similarity_score"], reverse=True)
    return atoms[:n_results]
