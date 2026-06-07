# Vector DB + Embedding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 각 원자(Atom)에 벡터 임베딩을 부여하여 "반도체 지금 어때?" 같은 자유 질문으로 관련 원자를 의미 검색할 수 있게 한다.

**Architecture:** ChromaDB(로컬 영구저장) + gemini-embedding-001(3072차원)으로 원자 콘텐츠를 임베딩한다. SQLite는 여전히 구조화 데이터의 단일 진실 소스이고, ChromaDB는 벡터 인덱스 역할만 한다. 인제스트 시 SQLite 저장과 동시에 ChromaDB에도 임베딩을 저장한다. 기존 원자는 `embed_all.py`로 일괄 처리한다.

**Tech Stack:** ChromaDB 1.5.9, google-genai 2.6.0 (gemini-embedding-001, 3072차원), Python 3.10+, pytest

---

## 파일 구조

```
pipeline/atoms/
  vector_db.py      ← ChromaDB 연결·embed·query·delete (신규)
  embed_all.py      ← 기존 atoms 일괄 임베딩 CLI (신규)
  query.py          ← 검색 CLI: 질문 → 원자 목록 (신규)
  ingest.py         ← 인제스트 후 자동 임베딩 추가 (수정)

tests/atoms/
  test_vector_db.py ← 벡터 DB 단위 테스트 (신규)
```

---

## 전제 조건

- `pipeline/atoms/db.py` 및 `pipeline/atoms/atomizer.py` 이미 완성됨 (Plan 1)
- ChromaDB 1.5.9: `pip install chromadb` (이미 설치됨)
- google-genai 2.6.0: 이미 설치됨
- `.env`에 `GEMINI_API_KEY=...` 존재

---

## Task 1: vector_db.py — ChromaDB 기본 구조

**Files:**
- Create: `pipeline/atoms/vector_db.py`
- Create: `tests/atoms/test_vector_db.py`

- [ ] **Step 1: 테스트 먼저 작성**

```python
# tests/atoms/test_vector_db.py
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
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
python -m pytest tests/atoms/test_vector_db.py -v
```

Expected: `ImportError: cannot import name 'get_collection' from 'pipeline.atoms.vector_db'`

- [ ] **Step 3: `pipeline/atoms/vector_db.py` 구현**

```python
"""
vector_db.py — ChromaDB 벡터 인덱스.

SQLite가 단일 진실 소스. ChromaDB는 벡터 검색 인덱스만 담당.
"""
import os
from pathlib import Path
from typing import Optional

import chromadb

_CHROMA_PATH = Path(__file__).parent.parent.parent / "pipeline" / "atoms" / "chroma_db"
_COLLECTION_NAME = "atoms"
_EMBEDDING_DIM = 3072

_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _CHROMA_PATH.mkdir(parents=True, exist_ok=True)
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


def embed_text(text: str) -> list[float]:
    """텍스트를 gemini-embedding-001로 임베딩."""
    raise NotImplementedError("Task 2에서 구현")
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
python -m pytest tests/atoms/test_vector_db.py -v
```

Expected: 4 passed (embed_text는 mock으로 대체되므로 NotImplementedError 발생 안 함)

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/vector_db.py tests/atoms/test_vector_db.py
git commit -m "feat(vector): vector_db.py 기본 구조 + ChromaDB upsert/delete"
```

---

## Task 2: embed_text — gemini-embedding-001 연동

**Files:**
- Modify: `pipeline/atoms/vector_db.py` — `embed_text()` 구현

- [ ] **Step 1: 테스트 먼저 작성**

`tests/atoms/test_vector_db.py` 아래에 추가:

```python
from unittest.mock import patch, MagicMock

def test_embed_text_returns_3072_floats(monkeypatch):
    """실제 API를 mock하여 반환 형식 검증."""
    mock_resp = MagicMock()
    mock_resp.embeddings = [MagicMock(values=[0.1] * 3072)]

    with patch("pipeline.atoms.vector_db._embed_client") as mock_client:
        mock_client.models.embed_content.return_value = mock_resp
        result = vdb_module.embed_text("테스트 텍스트")

    assert len(result) == 3072
    assert isinstance(result[0], float)


def test_embed_text_calls_correct_model(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.embeddings = [MagicMock(values=[0.0] * 3072)]

    with patch("pipeline.atoms.vector_db._embed_client") as mock_client:
        mock_client.models.embed_content.return_value = mock_resp
        vdb_module.embed_text("hello")
        mock_client.models.embed_content.assert_called_once_with(
            model="gemini-embedding-001",
            contents="hello",
        )
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
python -m pytest tests/atoms/test_vector_db.py::test_embed_text_returns_3072_floats -v
```

Expected: `AttributeError: module 'pipeline.atoms.vector_db' has no attribute '_embed_client'`

- [ ] **Step 3: `embed_text` 구현 — `vector_db.py` 상단에 추가**

기존 `embed_text` NotImplementedError 구현을 교체하고 `_embed_client` 추가:

```python
# vector_db.py 상단 imports 다음에 추가:
from pipeline.atoms.atomizer import _load_gemini_key
from google import genai

_embed_client: Optional[genai.Client] = None

def _get_embed_client() -> genai.Client:
    global _embed_client
    if _embed_client is None:
        _embed_client = genai.Client(api_key=_load_gemini_key())
    return _embed_client


def embed_text(text: str) -> list[float]:
    """텍스트를 gemini-embedding-001로 임베딩 (3072차원)."""
    resp = _get_embed_client().models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )
    return list(resp.embeddings[0].values)
```

`_embed_client = None` 전역 변수를 파일 상단에 추가하고, 기존 `embed_text` 함수의 `raise NotImplementedError` 줄을 위 내용으로 교체한다.

전체 `vector_db.py`:

```python
"""
vector_db.py — ChromaDB 벡터 인덱스.

SQLite가 단일 진실 소스. ChromaDB는 벡터 검색 인덱스만 담당.
"""
import os
from pathlib import Path
from typing import Optional

import chromadb
from google import genai

from pipeline.atoms.atomizer import _load_gemini_key

_CHROMA_PATH = Path(__file__).parent.parent.parent / "pipeline" / "atoms" / "chroma_db"
_COLLECTION_NAME = "atoms"
_EMBEDDING_DIM = 3072

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
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```powershell
python -m pytest tests/atoms/test_vector_db.py -v
```

Expected: 6 passed

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/vector_db.py tests/atoms/test_vector_db.py
git commit -m "feat(vector): gemini-embedding-001 embed_text 구현"
```

---

## Task 3: query_similar — 의미 검색 함수

**Files:**
- Modify: `pipeline/atoms/vector_db.py` — `query_similar()` 추가
- Modify: `tests/atoms/test_vector_db.py` — 검색 테스트 추가

- [ ] **Step 1: 테스트 먼저 작성**

`tests/atoms/test_vector_db.py`에 추가:

```python
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.vector_db import query_similar


@pytest.fixture
def db_with_atom(tmp_path, monkeypatch):
    """SQLite + ChromaDB 동시 초기화."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def test_query_similar_returns_atoms(isolated_chroma, db_with_atom, monkeypatch):
    """임베딩 저장 후 유사 검색 시 원자 반환."""
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: FAKE_EMBEDDING)

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

    results = query_similar("반도체 실적 가이던스", n_results=5)
    assert len(results) == 1
    assert results[0]["id"] == "atom_semi_001"
    assert "similarity_score" in results[0]


def test_query_similar_filter_by_sector(isolated_chroma, db_with_atom, monkeypatch):
    """sector 필터가 작동하는지 확인."""
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: FAKE_EMBEDDING)

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
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
python -m pytest tests/atoms/test_vector_db.py::test_query_similar_returns_atoms -v
```

Expected: `ImportError: cannot import name 'query_similar'`

- [ ] **Step 3: `query_similar` 구현 — `vector_db.py`에 추가**

```python
from pipeline.atoms.db import get_conn


def query_similar(
    text: str,
    n_results: int = 10,
    sector: Optional[str] = None,
    signal: Optional[str] = None,
    days: int = 30,
) -> list[dict]:
    """
    질문 텍스트를 임베딩하여 유사 원자를 반환.

    SQLite에서 전체 원자 데이터를 가져오고 similarity_score 필드를 추가.
    """
    query_embedding = embed_text(text)

    where: dict = {}
    if sector:
        where["sector"] = sector
    if signal:
        where["signal"] = signal

    col = get_collection()
    kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": min(n_results, col.count()) if col.count() > 0 else 1,
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
        atom = id_to_row[atom_id]
        atom["similarity_score"] = round(1.0 - id_to_dist[atom_id], 4)
        if atom.get("relations"):
            import json as _json
            try:
                atom["relations"] = _json.loads(atom["relations"])
            except Exception:
                atom["relations"] = []
        atoms.append(atom)

    return sorted(atoms, key=lambda a: a["similarity_score"], reverse=True)
```

`from pipeline.atoms.db import get_conn` import를 `vector_db.py` 상단에 추가한다.

- [ ] **Step 4: 테스트 통과 확인**

```powershell
python -m pytest tests/atoms/test_vector_db.py -v
```

Expected: 8 passed

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/vector_db.py tests/atoms/test_vector_db.py
git commit -m "feat(vector): query_similar — 의미 검색 + 섹터 필터"
```

---

## Task 4: ingest.py 통합 — 인제스트 시 자동 임베딩

**Files:**
- Modify: `pipeline/atoms/ingest.py` — `insert_atom` 후 `embed_and_store` 호출
- Modify: `tests/atoms/test_ingest.py` — 임베딩 통합 테스트 추가

- [ ] **Step 1: 테스트 먼저 작성**

`tests/atoms/test_ingest.py`에 추가:

```python
import chromadb
import pipeline.atoms.vector_db as vdb_module
from pipeline.atoms.vector_db import get_embedding_count


@pytest.fixture(autouse=True)
def isolated_chroma_for_ingest(monkeypatch):
    """ingest 테스트용 격리 ChromaDB."""
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(vdb_module, "_client", client)
    monkeypatch.setattr(vdb_module, "_collection", None)
    monkeypatch.setattr(vdb_module, "embed_text", lambda t: [0.1] * 3072)


@patch("pipeline.atoms.ingest.atomize_text")
def test_ingest_also_embeds_atoms(mock_atomize, tmp_path, monkeypatch):
    """ingest 후 ChromaDB에도 원자가 저장되는지 확인."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()

    test_file = tmp_path / "telegram" / "2026-06-07_신한.md"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("테스트 내용.", encoding="utf-8")

    mock_atomize.return_value = [{
        "id": "atom_embed_test",
        "date": "2026-06-07",
        "source_type": "telegram", "source_name": "신한",
        "source_trust": "C", "raw_file": str(test_file),
        "layer": "L5", "sector": "반도체", "asset": "브로드컴",
        "asset_level": "stock", "signal": "bearish",
        "event_type": "earnings", "magnitude": "major",
        "content_type": "fact", "strength_score": 2,
        "validity_type": "permanent", "validity_until": None,
        "is_active": 1, "content": "테스트 내용.", "relations": [],
    }]

    count = ingest_file(str(test_file), "2026-06-07")
    assert count == 1
    assert get_embedding_count() == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
python -m pytest tests/atoms/test_ingest.py::test_ingest_also_embeds_atoms -v
```

Expected: FAIL (get_embedding_count() == 0, 임베딩 연결 안 됨)

- [ ] **Step 3: `ingest.py` 수정 — embed_and_store 통합**

`ingest.py` 상단 import에 추가:

```python
from .vector_db import embed_and_store
```

`ingest.py`의 `_ingest_text`, `_ingest_excel`, `_ingest_json` 함수에서 `insert_atom(atom)` 다음 줄에 `embed_and_store(atom)` 추가.

수정 전:
```python
    for atom in atoms:
        insert_atom(atom)
    return len(atoms)
```

수정 후 (3곳 모두):
```python
    for atom in atoms:
        insert_atom(atom)
        embed_and_store(atom)
    return len(atoms)
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
python -m pytest tests/atoms/ -v
```

Expected: 전체 PASS (기존 39개 + 신규 1개 = 40개)

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/ingest.py tests/atoms/test_ingest.py
git commit -m "feat(vector): ingest 시 자동 임베딩 통합"
```

---

## Task 5: embed_all.py — 기존 atoms 일괄 임베딩

**Files:**
- Create: `pipeline/atoms/embed_all.py`

- [ ] **Step 1: 구현 (이 모듈은 CLI 스크립트이므로 테스트 대신 실제 실행으로 검증)**

```python
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

    # force가 아닌 경우 이미 임베딩된 원자 건너뜀
    if not force:
        existing_ids = set(get_collection().get()["ids"])
    else:
        existing_ids = set()

    count = 0
    for i, row in enumerate(rows):
        atom = dict(row)
        if atom["id"] in existing_ids:
            continue

        try:
            embed_and_store(atom)
            count += 1
        except Exception as e:
            print(f"[WARN] {atom['id']} 임베딩 실패: {e}")
            continue

        if (i + 1) % 10 == 0:
            print(f"  진행: {i+1}/{total} (임베딩 완료: {count})")

        # API 레이트 리밋 방지
        time.sleep(0.1)

    print(f"[OK] {count}개 원자 임베딩 완료 (전체 DB: {get_embedding_count()}개)")
    return count


if __name__ == "__main__":
    force = "--force" in sys.argv
    embed_all(force=force)
```

- [ ] **Step 2: 실제 실행으로 검증**

```powershell
python -m pipeline.atoms.embed_all
```

기대 출력:
```
  진행: 10/75 (임베딩 완료: 10)
  진행: 20/75 (임베딩 완료: 20)
  ...
[OK] 75개 원자 임베딩 완료 (전체 DB: 75개)
```

- [ ] **Step 3: 커밋**

```powershell
git add pipeline/atoms/embed_all.py
git commit -m "feat(vector): embed_all.py — 기존 atoms 일괄 임베딩 CLI"
```

---

## Task 6: query.py — 검색 CLI + 실제 테스트

**Files:**
- Create: `pipeline/atoms/query.py`

- [ ] **Step 1: 구현**

```python
"""
query.py — 자유 질문으로 관련 원자를 검색하고 결과를 출력.

사용법:
    python -m pipeline.atoms.query "반도체 지금 어때?"
    python -m pipeline.atoms.query "수급 빈집 종목" --sector 반도체
    python -m pipeline.atoms.query "오늘 리스크" --signal bearish --n 20
"""
import sys
import argparse

from .db import init_db
from .vector_db import query_similar


def _fmt_atom(a: dict, rank: int) -> str:
    score = a.get("similarity_score", 0)
    date = a.get("date", "")
    sector = a.get("sector", "")
    asset = a.get("asset", "")
    signal = a.get("signal", "")
    trust = a.get("source_trust", "")
    content = a.get("content", "")
    return (
        f"\n[{rank}] {score:.3f} | {date} | {sector}/{asset} | "
        f"{signal}[{trust}]\n    {content[:120]}{'...' if len(content) > 120 else ''}"
    )


def run_query(
    question: str,
    n: int = 10,
    sector: str = None,
    signal: str = None,
) -> list[dict]:
    init_db()
    atoms = query_similar(question, n_results=n, sector=sector, signal=signal)
    if not atoms:
        print("[결과 없음] 관련 원자를 찾지 못했습니다.")
        return []

    print(f"\n질문: {question}")
    print(f"관련 원자 {len(atoms)}개 발견:\n{'='*60}")
    for i, a in enumerate(atoms, 1):
        print(_fmt_atom(a, i))
    print("=" * 60)
    return atoms


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="원자 의미 검색")
    parser.add_argument("question", help="검색 질문")
    parser.add_argument("--n", type=int, default=10, help="결과 수 (기본 10)")
    parser.add_argument("--sector", default=None, help="섹터 필터")
    parser.add_argument("--signal", default=None, help="신호 필터 (bullish/bearish 등)")
    args = parser.parse_args()
    run_query(args.question, args.n, args.sector, args.signal)
```

- [ ] **Step 2: 실제 검색 테스트 1 — 자유 질문**

```powershell
python -m pipeline.atoms.query "반도체 지금 어때?"
```

기대: 반도체 관련 원자 10개 내외 출력 (similarity_score 높은 순)

- [ ] **Step 3: 실제 검색 테스트 2 — 섹터 필터**

```powershell
python -m pipeline.atoms.query "수급 빈집 종목" --sector 기타 --n 5
```

기대: 수급오실레이터 빈집 원자들 출력

- [ ] **Step 4: 실제 검색 테스트 3 — 신호 필터**

```powershell
python -m pipeline.atoms.query "리스크 요인" --signal bearish
```

기대: bearish 신호 원자들 출력

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/query.py
git commit -m "feat(vector): query.py — 자유 질문 의미 검색 CLI"
```

---

## 완료 기준

- [ ] `python -m pytest tests/atoms/ -v` → 전체 PASS (40개+)
- [ ] `python -m pipeline.atoms.embed_all` → atoms.db의 모든 원자 임베딩 완료
- [ ] `python -m pipeline.atoms.query "반도체 지금 어때?"` → 관련 원자 출력
- [ ] `python -m pipeline.atoms.query "수급 빈집 종목" --n 5` → 빈집 원자 출력
- [ ] 신규 ingest 시 자동으로 ChromaDB에도 저장됨

---

## 다음 계획 (Plan 3)

Plan 2 완료 후: `2026-06-07-market-brain-generation.md`
- `wiki/MARKET_BRAIN.md` 자동 생성
- `wiki/state/{섹터}_state.md` 자동 업데이트
- `wiki/threads/` 서사 감지 + 생성
- 매일 아침 스케줄러 연동
