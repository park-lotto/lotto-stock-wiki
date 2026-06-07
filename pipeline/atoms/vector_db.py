"""
vector_db.py — ChromaDB 벡터 인덱스.

SQLite가 단일 진실 소스. ChromaDB는 벡터 검색 인덱스만 담당.
"""
from pathlib import Path
from typing import Optional

import chromadb
from google import genai

from pipeline.atoms.atomizer import _load_gemini_key

_CHROMA_PATH = Path(__file__).parent.parent.parent / "pipeline" / "atoms" / "chroma_db"
_COLLECTION_NAME = "atoms"

_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None
_embed_client: Optional[genai.Client] = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
    return _client


def _get_embed_client() -> genai.Client:
    global _embed_client
    if _embed_client is None:
        _embed_client = genai.Client(api_key=_load_gemini_key())
    return _embed_client


def get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def embed_text(text: str) -> list[float]:
    """텍스트를 gemini-embedding-001로 임베딩 (3072차원)."""
    resp = _get_embed_client().models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )
    return list(resp.embeddings[0].values)


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
    """ChromaDB에 저장된 임베딩 수."""
    return get_collection().count()


def query_similar(
    text: str,
    n_results: int = 10,
    sector: Optional[str] = None,
    signal: Optional[str] = None,
) -> list[dict]:
    """질문 텍스트를 임베딩하여 유사 원자를 반환. (Task 3에서 SQLite 조인 추가 예정)"""
    from pipeline.atoms.db import get_conn

    query_embedding = embed_text(text)

    where: dict = {}
    if sector:
        where["sector"] = sector
    if signal:
        where["signal"] = signal

    col = get_collection()
    count = col.count()
    if count == 0:
        return []

    kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": min(n_results, count),
    }
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)

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
        atom["similarity_score"] = round(1.0 - id_to_dist[atom_id], 4)
        if atom.get("relations"):
            import json as _json
            try:
                atom["relations"] = _json.loads(atom["relations"])
            except Exception:
                atom["relations"] = []
        atoms.append(atom)

    return sorted(atoms, key=lambda a: a["similarity_score"], reverse=True)
