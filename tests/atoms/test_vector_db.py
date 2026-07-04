import pytest
import time
import chromadb
from unittest.mock import patch, MagicMock
import pipeline.atoms.vector_db as vdb_module
import pipeline.atoms.db as db_module
from pipeline.atoms.vector_db import (
    get_collection,
    embed_and_store,
    delete_atom,
    get_embedding_count,
)
from pipeline.atoms.db import init_db, insert_atom

FAKE_EMBEDDING = [0.1] * 3072


@pytest.fixture(autouse=True)
def isolated_chroma(tmp_path, monkeypatch):
    """격리된 ChromaDB 클라이언트 (인메모리)."""
    client = chromadb.EphemeralClient()
    # 이전 테스트 잔여 컬렉션 제거 (EphemeralClient는 프로세스 내 공유)
    try:
        client.delete_collection("atoms")
    except Exception:
        pass
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


# ---------------------------------------------------------------------------
# embed_text 테스트
# ---------------------------------------------------------------------------

def test_embed_text_returns_3072_floats():
    """실제 API를 mock하여 반환 형식 검증."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.embeddings = [MagicMock(values=[0.1] * 3072)]
    mock_client.models.embed_content.return_value = mock_resp

    with patch("pipeline.atoms.vector_db.key_vault.get_live_keys", return_value=["fake-key"]), \
         patch("pipeline.atoms.vector_db.key_vault.get_client_for_key", return_value=mock_client):
        result = vdb_module.embed_text("테스트 텍스트")

    assert len(result) == 3072
    assert isinstance(result[0], float)


def test_embed_text_calls_correct_model():
    """gemini-embedding-001 모델로 호출되는지 확인."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.embeddings = [MagicMock(values=[0.0] * 3072)]
    mock_client.models.embed_content.return_value = mock_resp

    with patch("pipeline.atoms.vector_db.key_vault.get_live_keys", return_value=["fake-key"]), \
         patch("pipeline.atoms.vector_db.key_vault.get_client_for_key", return_value=mock_client):
        vdb_module.embed_text("hello")
        mock_client.models.embed_content.assert_called_once_with(
            model="gemini-embedding-001",
            contents="hello",
        )


def test_embed_text_marks_key_exhausted_on_daily_limit_and_tries_next(monkeypatch):
    """일일 한도(429+PerDay) 키는 mark_exhausted 후 다음 키로 넘어간다."""
    daily_exceeded = Exception("429 RESOURCE_EXHAUSTED PerDay limit: 500")
    ok_client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.embeddings = [MagicMock(values=[0.2] * 3072)]
    ok_client.models.embed_content.return_value = ok_resp
    bad_client = MagicMock()
    bad_client.models.embed_content.side_effect = daily_exceeded

    marked = []
    monkeypatch.setattr(vdb_module.key_vault, "get_live_keys", lambda g: ["bad-key", "ok-key"])
    monkeypatch.setattr(vdb_module.key_vault, "mark_exhausted", lambda g, k: marked.append((g, k)))
    monkeypatch.setattr(
        vdb_module.key_vault, "get_client_for_key",
        lambda k: bad_client if k == "bad-key" else ok_client,
    )

    result = vdb_module.embed_text("hello")
    assert len(result) == 3072
    assert marked == [("embed", "bad-key")]


def test_embed_text_raises_after_both_attempts_fail(monkeypatch):
    """RPM성 429가 두 번의 전체 순회(20초 간격) 후에도 실패하면 명확한 예외를 낸다."""
    rpm_exceeded = Exception("429 RESOURCE_EXHAUSTED PerMinute limit: 15")
    bad_client = MagicMock()
    bad_client.models.embed_content.side_effect = rpm_exceeded

    monkeypatch.setattr(vdb_module.key_vault, "get_live_keys", lambda g: ["k1"])
    monkeypatch.setattr(vdb_module.key_vault, "get_client_for_key", lambda k: bad_client)
    monkeypatch.setattr(vdb_module.key_vault, "mark_exhausted", lambda g, k: None)
    monkeypatch.setattr(vdb_module.key_vault, "_tg_alert", lambda text: None)
    monkeypatch.setattr(vdb_module.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="RPM"):
        vdb_module.embed_text("hello")


# ---------------------------------------------------------------------------
# query_similar 테스트
# ---------------------------------------------------------------------------

def test_query_similar_returns_atoms(tmp_path, monkeypatch):
    """임베딩 저장 후 유사 검색 시 원자 반환."""
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(vdb_module, "_client", client)
    monkeypatch.setattr(vdb_module, "_collection", None)
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: FAKE_EMBEDDING)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()

    atom = {
        "id": "atom_semi_001",
        "date": "2026-06-07",
        "source_type": "telegram",
        "source_name": "신한",
        "source_trust": "B",
        "raw_file": "raw/test.md",
        "layer": "L5",
        "sector": "반도체",
        "asset": "브로드컴",
        "asset_level": "stock",
        "signal": "bearish",
        "event_type": "earnings",
        "magnitude": "major",
        "content_type": "fact",
        "strength_score": 3,
        "validity_type": "permanent",
        "validity_until": None,
        "is_active": 1,
        "content": "브로드컴 AI 가이던스 -11.8% 미달.",
        "relations": [],
    }
    insert_atom(atom)
    embed_and_store(atom)

    from pipeline.atoms.vector_db import query_similar
    results = query_similar("반도체 실적 가이던스", n_results=5)
    assert len(results) == 1
    assert results[0]["id"] == "atom_semi_001"
    assert "similarity_score" in results[0]


def test_query_similar_filter_by_sector(tmp_path, monkeypatch):
    """sector 필터가 작동하는지 확인."""
    from pipeline.atoms.vector_db import query_similar

    client = chromadb.EphemeralClient()
    monkeypatch.setattr(vdb_module, "_client", client)
    monkeypatch.setattr(vdb_module, "_collection", None)
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: FAKE_EMBEDDING)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()

    for sector, atom_id in [("반도체", "atom_001"), ("조선", "atom_002")]:
        atom = {
            "id": atom_id, "date": "2026-06-07",
            "source_type": "telegram", "source_name": "test",
            "source_trust": "C", "raw_file": "raw/test.md",
            "layer": "L5", "sector": sector, "asset": sector,
            "asset_level": "sector", "signal": "bullish",
            "event_type": "news", "magnitude": "minor",
            "content_type": "fact", "strength_score": 1,
            "validity_type": "permanent", "validity_until": None,
            "is_active": 1, "content": f"{sector} 관련 내용.", "relations": [],
        }
        insert_atom(atom)
        embed_and_store(atom)

    results = query_similar("업황", n_results=5, sector="반도체")
    assert len(results) == 1
    assert results[0]["sector"] == "반도체"
