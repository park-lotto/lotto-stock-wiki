import pytest
import chromadb
import pipeline.atoms.vector_db as vdb_module
from pipeline.atoms.vector_db import (
    get_collection,
    embed_and_store,
    delete_atom,
    get_embedding_count,
)

FAKE_EMBEDDING = [0.1] * 3072


@pytest.fixture(autouse=True)
def isolated_chroma(tmp_path, monkeypatch):
    """격리된 ChromaDB 클라이언트 (인메모리)."""
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(vdb_module, "_client", client)
    monkeypatch.setattr(vdb_module, "_collection", None)


@pytest.fixture
def sample_atom():
    return {
        "id": "atom_test_001",
        "date": "2026-06-07",
        "sector": "반도체",
        "signal": "bearish",
        "asset": "브로드컴",
        "source_trust": "B",
        "content": "브로드컴 AI 가이던스 -11.8% 미달. 시장 예상 하회.",
    }


def test_get_collection_returns_collection(isolated_chroma):
    col = get_collection()
    assert col is not None
    assert col.name == "atoms"


def test_embed_and_store_increases_count(isolated_chroma, sample_atom, monkeypatch):
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: FAKE_EMBEDDING)
    assert get_embedding_count() == 0
    embed_and_store(sample_atom)
    assert get_embedding_count() == 1


def test_embed_and_store_is_idempotent(isolated_chroma, sample_atom, monkeypatch):
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: FAKE_EMBEDDING)
    embed_and_store(sample_atom)
    embed_and_store(sample_atom)  # 중복 저장해도 1개
    assert get_embedding_count() == 1


def test_delete_atom_removes_from_chroma(isolated_chroma, sample_atom, monkeypatch):
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: FAKE_EMBEDDING)
    embed_and_store(sample_atom)
    assert get_embedding_count() == 1
    delete_atom("atom_test_001")
    assert get_embedding_count() == 0
