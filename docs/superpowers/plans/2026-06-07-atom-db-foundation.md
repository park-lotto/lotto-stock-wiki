# Atom DB Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 텍스트/Excel 원천 데이터를 버리지 않고 원자(Atom) 단위로 SQLite에 저장하는 핵심 파이프라인 구축

**Architecture:** 모든 raw 파일(텔레그램/뉴스/리포트/Excel)을 Gemini Flash로 원자화하여 표준 스키마로 SQLite에 저장. 원문 100% 보존, 메타데이터 부착, 유효기간 관리 포함.

**Tech Stack:** Python 3.10+, SQLite (내장), google-generativeai, openpyxl, pandas, pytest

---

## 파일 구조

```
pipeline/atoms/
  __init__.py           빈 패키지 마커
  schema.sql            SQLite 테이블 + 인덱스 정의
  taxonomy.py           택소노미 상수 (signal/event_type 등)
  db.py                 DB 연결, insert/query/expire CRUD
  atomizer.py           텍스트 → 원자 리스트 (Gemini Flash)
  excel_converter.py    Excel 행 → 텍스트 원자 (수급/컨센 등)
  ingest.py             메인 진입점: 파일 1개 → 원자들 → DB

tests/atoms/
  __init__.py
  test_db.py
  test_atomizer.py
  test_excel_converter.py
  test_ingest.py
```

---

## Task 1: 패키지 뼈대 + 택소노미

**Files:**
- Create: `pipeline/atoms/__init__.py`
- Create: `pipeline/atoms/taxonomy.py`
- Create: `tests/atoms/__init__.py`

- [ ] **Step 1: 디렉터리 생성**

```powershell
New-Item -ItemType Directory -Force pipeline\atoms
New-Item -ItemType Directory -Force tests\atoms
```

- [ ] **Step 2: `pipeline/atoms/__init__.py` 생성**

```python
```
(빈 파일)

- [ ] **Step 3: `tests/atoms/__init__.py` 생성**

```python
```
(빈 파일)

- [ ] **Step 4: `pipeline/atoms/taxonomy.py` 작성**

```python
SIGNAL_TYPES = [
    "bullish",   # 상승 재료
    "bearish",   # 하락 재료
    "neutral",   # 현황/팩트 (방향 없음)
    "risk",      # 리스크 (방향 미결)
    "catalyst",  # 트리거 (곧 터질 이벤트)
    "conflict",  # 충돌 (상반된 신호, 둘 다 보존)
    "data",      # 순수 수치
]

EVENT_TYPES = [
    "earnings",   # 실적/어닝/가이던스
    "policy",     # 정책/규제/금리
    "supply",     # 수급 (외국인·기관 매매)
    "demand",     # 제품·서비스 수요
    "consensus",  # 컨센서스·TP 변화
    "momentum",   # 가속화·모멘텀
    "macro",      # 매크로 지표
    "news",       # 뉴스·이슈·공시
    "report",     # 리포트·분석
    "event",      # IR·컨퍼런스·일정
]

ASSET_LEVELS = [
    "stock",   # 개별 종목
    "sector",  # 섹터
    "market",  # 시장 전체
    "macro",   # 매크로 지표
    "theme",   # 사이클·서사
]

CONTENT_TYPES = [
    "fact",      # 검증된 사실 → 그대로 반영
    "data",      # 수치 데이터 → 그대로 반영
    "analysis",  # 공식 분석 → 출처 명시 후 반영
    "opinion",   # 개인 의견 → 교차검증 후 반영
]

SOURCE_TRUST = {
    "A": "증권사 공식 리포트",
    "B": "텔레그램 유료 채널",
    "C": "텔레그램 일반 채널",
    "D": "뉴스·블로그",
    "E": "소셜·미확인",
}

VALIDITY_TYPES = [
    "event",      # 특정 이벤트 기반 만료
    "date",       # 날짜 기반 만료
    "permanent",  # 계속 유효
]

MAGNITUDE_TYPES = ["major", "minor"]

SECTOR_LIST = [
    "반도체", "조선", "로봇", "방산", "바이오",
    "전력", "2차전지", "자동차", "통신", "AI소프트웨어",
    "우주", "소비내수", "미용", "LNG", "신재생", "기타"
]

SOURCE_TRUST_BY_PATH = {
    "wisereport": "A",
    "report": "A",
    "신한": "B",
    "태린이": "B",
    "crawling_bot": "B",
    "telegram": "C",
    "news": "D",
    "blog": "D",
    "market": "D",
}
```

- [ ] **Step 5: taxonomy 테스트 작성**

```python
# tests/atoms/test_taxonomy.py
from pipeline.atoms.taxonomy import (
    SIGNAL_TYPES, EVENT_TYPES, ASSET_LEVELS,
    CONTENT_TYPES, SECTOR_LIST
)

def test_signal_types_complete():
    assert "bullish" in SIGNAL_TYPES
    assert "bearish" in SIGNAL_TYPES
    assert "conflict" in SIGNAL_TYPES

def test_no_duplicates():
    assert len(SIGNAL_TYPES) == len(set(SIGNAL_TYPES))
    assert len(EVENT_TYPES) == len(set(EVENT_TYPES))

def test_sector_list_has_major_sectors():
    for sector in ["반도체", "조선", "로봇", "방산"]:
        assert sector in SECTOR_LIST
```

- [ ] **Step 6: 테스트 실행 — PASS 확인**

```powershell
python -m pytest tests/atoms/test_taxonomy.py -v
```

기대 출력: `3 passed`

- [ ] **Step 7: 커밋**

```powershell
git add pipeline/atoms/__init__.py pipeline/atoms/taxonomy.py tests/atoms/ 
git commit -m "feat(atoms): taxonomy 상수 + 패키지 뼈대"
```

---

## Task 2: SQLite 스키마 + DB CRUD

**Files:**
- Create: `pipeline/atoms/schema.sql`
- Create: `pipeline/atoms/db.py`
- Create: `tests/atoms/test_db.py`

- [ ] **Step 1: `pipeline/atoms/schema.sql` 작성**

```sql
CREATE TABLE IF NOT EXISTS atoms (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,

    -- 소스
    source_type TEXT NOT NULL,
    source_name TEXT,
    source_trust TEXT DEFAULT 'D',
    raw_file TEXT,

    -- 분류
    layer TEXT,
    sector TEXT,
    asset TEXT,
    asset_level TEXT DEFAULT 'sector',

    -- 신호
    signal TEXT NOT NULL DEFAULT 'neutral',
    event_type TEXT DEFAULT 'news',
    magnitude TEXT DEFAULT 'minor',
    content_type TEXT DEFAULT 'fact',
    strength_score INTEGER DEFAULT 1,

    -- 유효기간
    validity_type TEXT DEFAULT 'permanent',
    validity_until TEXT,
    is_active INTEGER DEFAULT 1,

    -- 내용 (원문 보존)
    content TEXT NOT NULL,

    -- 관계 그래프 (JSON: [{type, target_id}])
    relations TEXT DEFAULT '[]',

    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_atoms_date ON atoms(date);
CREATE INDEX IF NOT EXISTS idx_atoms_sector ON atoms(sector);
CREATE INDEX IF NOT EXISTS idx_atoms_signal ON atoms(signal);
CREATE INDEX IF NOT EXISTS idx_atoms_asset ON atoms(asset);
CREATE INDEX IF NOT EXISTS idx_atoms_is_active ON atoms(is_active);
CREATE INDEX IF NOT EXISTS idx_atoms_validity ON atoms(validity_until);
CREATE INDEX IF NOT EXISTS idx_atoms_source_trust ON atoms(source_trust);
```

- [ ] **Step 2: 테스트 먼저 작성**

```python
# tests/atoms/test_db.py
import pytest
from pathlib import Path
from datetime import datetime, date, timedelta
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, insert_atom, query_atoms, expire_atoms, get_atom_count

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_atoms.db")
    init_db()

def _make_atom(overrides=None):
    base = {
        "id": "atom_test_001",
        "date": date.today().isoformat(),
        "source_type": "telegram",
        "source_name": "신한리서치",
        "source_trust": "B",
        "raw_file": "raw/telegram/test.md",
        "layer": "L5",
        "sector": "반도체",
        "asset": "브로드컴",
        "asset_level": "stock",
        "signal": "bearish",
        "event_type": "earnings",
        "magnitude": "major",
        "content_type": "fact",
        "strength_score": 4,
        "validity_type": "permanent",
        "validity_until": None,
        "is_active": 1,
        "content": "브로드컴 AI 가이던스 -11.8% 미달. 시장 예상 하회.",
        "relations": [],
    }
    if overrides:
        base.update(overrides)
    return base

def test_insert_and_retrieve():
    atom = _make_atom()
    insert_atom(atom)
    results = query_atoms(sector="반도체", days=1)
    assert len(results) == 1
    assert results[0]["asset"] == "브로드컴"
    assert results[0]["signal"] == "bearish"

def test_content_preserved_exactly():
    original = "브로드컴 AI 가이던스 -11.8% 미달. 절대 요약 금지."
    insert_atom(_make_atom({"content": original}))
    results = query_atoms(days=1)
    assert results[0]["content"] == original

def test_query_by_signal():
    insert_atom(_make_atom({"id": "atom_001", "signal": "bullish"}))
    insert_atom(_make_atom({"id": "atom_002", "signal": "bearish"}))
    bullish = query_atoms(signal="bullish", days=1)
    assert len(bullish) == 1
    assert bullish[0]["signal"] == "bullish"

def test_query_by_asset():
    insert_atom(_make_atom({"asset": "SK하이닉스"}))
    results = query_atoms(asset="SK하이닉스", days=1)
    assert len(results) == 1

def test_expire_atoms_by_date():
    expired_date = (date.today() - timedelta(days=3)).isoformat()
    atom = _make_atom({
        "id": "atom_expired",
        "date": "2026-01-01",
        "validity_type": "date",
        "validity_until": expired_date,
    })
    insert_atom(atom)
    count = expire_atoms()
    assert count >= 1
    active = query_atoms(days=365, active_only=True)
    assert all(r["id"] != "atom_expired" for r in active)

def test_permanent_atom_not_expired():
    insert_atom(_make_atom({"validity_type": "permanent", "validity_until": None}))
    expire_atoms()
    results = query_atoms(days=1)
    assert len(results) == 1

def test_get_atom_count():
    insert_atom(_make_atom({"id": "atom_a"}))
    insert_atom(_make_atom({"id": "atom_b"}))
    assert get_atom_count() == 2
```

- [ ] **Step 3: 테스트 실행 — FAIL 확인 (db.py 없으니까)**

```powershell
python -m pytest tests/atoms/test_db.py -v 2>&1 | Select-Object -First 5
```

기대 출력: `ImportError` 또는 `ModuleNotFoundError`

- [ ] **Step 4: `pipeline/atoms/db.py` 작성**

```python
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "pipeline" / "atoms" / "atoms.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def insert_atom(atom: dict) -> str:
    a = dict(atom)
    if isinstance(a.get("relations"), list):
        a["relations"] = json.dumps(a["relations"], ensure_ascii=False)
    a.setdefault("created_at", datetime.now().isoformat())
    conn = get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO atoms
        (id, date, source_type, source_name, source_trust, raw_file,
         layer, sector, asset, asset_level,
         signal, event_type, magnitude, content_type, strength_score,
         validity_type, validity_until, is_active,
         content, relations, created_at)
        VALUES
        (:id, :date, :source_type, :source_name, :source_trust, :raw_file,
         :layer, :sector, :asset, :asset_level,
         :signal, :event_type, :magnitude, :content_type, :strength_score,
         :validity_type, :validity_until, :is_active,
         :content, :relations, :created_at)
        """,
        a,
    )
    conn.commit()
    conn.close()
    return a["id"]


def query_atoms(
    sector: Optional[str] = None,
    signal: Optional[str] = None,
    asset: Optional[str] = None,
    layer: Optional[str] = None,
    days: int = 7,
    limit: int = 50,
    active_only: bool = True,
) -> list[dict]:
    conditions = ["date >= date('now', ? || ' days')"]
    params: list = [f"-{days}"]

    if active_only:
        conditions.append("is_active = 1")
    if sector:
        conditions.append("sector = ?")
        params.append(sector)
    if signal:
        conditions.append("signal = ?")
        params.append(signal)
    if asset:
        conditions.append("asset LIKE ?")
        params.append(f"%{asset}%")
    if layer:
        conditions.append("layer = ?")
        params.append(layer)

    sql = (
        f"SELECT * FROM atoms WHERE {' AND '.join(conditions)} "
        f"ORDER BY date DESC, strength_score DESC LIMIT ?"
    )
    params.append(limit)
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def expire_atoms() -> int:
    conn = get_conn()
    conn.execute(
        """
        UPDATE atoms
        SET is_active = 0, updated_at = ?
        WHERE validity_until IS NOT NULL
          AND validity_until < date('now')
          AND is_active = 1
        """,
        [datetime.now().isoformat()],
    )
    count = conn.total_changes
    conn.commit()
    conn.close()
    return count


def get_atom_count(active_only: bool = False) -> int:
    conn = get_conn()
    sql = "SELECT COUNT(*) FROM atoms"
    if active_only:
        sql += " WHERE is_active = 1"
    count = conn.execute(sql).fetchone()[0]
    conn.close()
    return count
```

- [ ] **Step 5: 테스트 실행 — PASS 확인**

```powershell
python -m pytest tests/atoms/test_db.py -v
```

기대 출력: `7 passed`

- [ ] **Step 6: 커밋**

```powershell
git add pipeline/atoms/schema.sql pipeline/atoms/db.py tests/atoms/test_db.py
git commit -m "feat(atoms): SQLite 스키마 + CRUD (insert/query/expire)"
```

---

## Task 3: Atomizer (텍스트 → 원자, Gemini Flash)

**Files:**
- Create: `pipeline/atoms/atomizer.py`
- Create: `tests/atoms/test_atomizer.py`

- [ ] **Step 1: 테스트 먼저 작성**

```python
# tests/atoms/test_atomizer.py
import pytest
from unittest.mock import MagicMock, patch
from pipeline.atoms.atomizer import atomize_text, _make_id, _calc_strength

def test_make_id_deterministic():
    id1 = _make_id("2026-06-07", "신한리서치", 0)
    id2 = _make_id("2026-06-07", "신한리서치", 0)
    assert id1 == id2
    assert id1.startswith("atom_")
    assert len(id1) == 17  # "atom_" + 12자

def test_make_id_unique_per_index():
    id0 = _make_id("2026-06-07", "신한리서치", 0)
    id1 = _make_id("2026-06-07", "신한리서치", 1)
    assert id0 != id1

def test_calc_strength_a_source_major():
    score = _calc_strength({"magnitude": "major"}, "A")
    assert score == 4  # 1 base + 2 trust_A + 1 major

def test_calc_strength_max_five():
    score = _calc_strength({"magnitude": "major"}, "A")
    assert score <= 5

def test_calc_strength_d_source_minor():
    score = _calc_strength({"magnitude": "minor"}, "D")
    assert score == 1  # 1 base only

@patch("pipeline.atoms.atomizer.genai")
def test_atomize_text_returns_atoms(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value.text = '''[
        {
            "content": "브로드컴 AI 가이던스 -11.8% 미달.",
            "sector": "반도체",
            "asset": "브로드컴",
            "asset_level": "stock",
            "signal": "bearish",
            "event_type": "earnings",
            "magnitude": "major",
            "content_type": "fact",
            "validity_type": "permanent",
            "validity_until": null
        }
    ]'''

    atoms = atomize_text(
        text="브로드컴 AI 가이던스 -11.8% 미달.",
        source_type="telegram",
        source_name="신한리서치",
        source_trust="B",
        raw_file="raw/test.md",
        date="2026-06-07",
    )

    assert len(atoms) == 1
    a = atoms[0]
    assert a["signal"] == "bearish"
    assert a["sector"] == "반도체"
    assert a["source_trust"] == "B"
    assert a["content"] == "브로드컴 AI 가이던스 -11.8% 미달."
    assert a["id"].startswith("atom_")

@patch("pipeline.atoms.atomizer.genai")
def test_atomize_text_preserves_content_exactly(mock_genai):
    original = "원문 그대로 보존해야 한다. 절대 요약 금지."
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value.text = f'''[
        {{
            "content": "{original}",
            "sector": "기타", "asset": "테스트",
            "asset_level": "stock", "signal": "neutral",
            "event_type": "news", "magnitude": "minor",
            "content_type": "fact", "validity_type": "permanent",
            "validity_until": null
        }}
    ]'''

    atoms = atomize_text(
        text=original,
        source_type="news",
        source_name="테스트",
        source_trust="D",
        raw_file="raw/test.md",
        date="2026-06-07",
    )
    assert atoms[0]["content"] == original
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```powershell
python -m pytest tests/atoms/test_atomizer.py -v 2>&1 | Select-Object -First 5
```

기대 출력: `ImportError`

- [ ] **Step 3: `pipeline/atoms/atomizer.py` 작성**

```python
import os
import json
import hashlib
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

_PROMPT = """다음 텍스트를 주식 시장 정보 '원자' 단위로 분해하라.

원자 정의: 하나의 명확한 주제(자산/이벤트)에 대한 최소 의미 단위. 3~7문장.
핵심 규칙: 원문을 요약하지 마라. 원문의 해당 부분을 그대로 담아라.

각 원자에 아래 메타데이터를 부여하라:
- sector: 반도체/조선/로봇/방산/바이오/전력/2차전지/자동차/통신/AI소프트웨어/우주/소비내수/기타
- asset: 종목명 또는 섹터명 또는 지표명
- asset_level: stock/sector/market/macro/theme
- signal: bullish/bearish/neutral/risk/catalyst/conflict/data
- event_type: earnings/policy/supply/demand/consensus/momentum/macro/news/report/event
- magnitude: major/minor
- content_type: fact/data/analysis/opinion
- validity_type: permanent/date/event
- validity_until: 만료일 YYYY-MM-DD 형식 또는 null

JSON 배열만 반환하라. 다른 텍스트 없이.

텍스트:
{text}"""


def atomize_text(
    text: str,
    source_type: str,
    source_name: str,
    source_trust: str,
    raw_file: str,
    date: str,
    layer: str = "L5",
) -> list[dict]:
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(
        _PROMPT.format(text=text),
        generation_config={"response_mime_type": "application/json"},
    )
    raw_atoms: list[dict] = json.loads(response.text)

    atoms = []
    for i, a in enumerate(raw_atoms):
        atoms.append(
            {
                "id": _make_id(date, source_name, i),
                "date": date,
                "source_type": source_type,
                "source_name": source_name,
                "source_trust": source_trust,
                "raw_file": raw_file,
                "layer": layer,
                "sector": a.get("sector", "기타"),
                "asset": a.get("asset", ""),
                "asset_level": a.get("asset_level", "sector"),
                "signal": a.get("signal", "neutral"),
                "event_type": a.get("event_type", "news"),
                "magnitude": a.get("magnitude", "minor"),
                "content_type": a.get("content_type", "fact"),
                "strength_score": _calc_strength(a, source_trust),
                "validity_type": a.get("validity_type", "permanent"),
                "validity_until": a.get("validity_until"),
                "is_active": 1,
                "content": a["content"],
                "relations": [],
            }
        )
    return atoms


def _make_id(date: str, source_name: str, index: int) -> str:
    raw = f"{date}_{source_name}_{index}"
    return "atom_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _calc_strength(atom: dict, source_trust: str) -> int:
    score = 1
    score += {"A": 2, "B": 1}.get(source_trust, 0)
    if atom.get("magnitude") == "major":
        score += 1
    return min(score, 5)
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```powershell
python -m pytest tests/atoms/test_atomizer.py -v
```

기대 출력: `6 passed`

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/atomizer.py tests/atoms/test_atomizer.py
git commit -m "feat(atoms): Gemini Flash 원자화 엔진"
```

---

## Task 4: Excel Converter (수급/컨센 → 원자)

**Files:**
- Create: `pipeline/atoms/excel_converter.py`
- Create: `tests/atoms/test_excel_converter.py`

- [ ] **Step 1: 테스트 먼저 작성**

```python
# tests/atoms/test_excel_converter.py
import pytest
import pandas as pd
from pipeline.atoms.excel_converter import oscillator_to_atoms, consensus_to_atoms

@pytest.fixture
def oscillator_excel(tmp_path):
    df = pd.DataFrame({
        "종목명": ["SK하이닉스", "삼성전자", "에코프로"],
        "오실레이터": [73.0, -20.0, 5.0],
    })
    path = tmp_path / "oscillator.xlsx"
    df.to_excel(path, index=False)
    return str(path)

@pytest.fixture
def consensus_excel(tmp_path):
    df = pd.DataFrame({
        "종목명": ["삼성전자", "LG에너지솔루션"],
        "섹터": ["반도체", "2차전지"],
        "컨센변화": ["+15%", "-8%"],
        "TP": ["100000", "450000"],
    })
    path = tmp_path / "consensus.xlsx"
    df.to_excel(path, index=False)
    return str(path)

def test_positive_oscillator_is_bullish(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    sk = next(a for a in atoms if a["asset"] == "SK하이닉스")
    assert sk["signal"] == "bullish"
    assert sk["event_type"] == "supply"
    assert "73" in sk["content"]

def test_negative_oscillator_is_bearish(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    samsung = next(a for a in atoms if a["asset"] == "삼성전자")
    assert samsung["signal"] == "bearish"

def test_oscillator_above_50_is_major(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    sk = next(a for a in atoms if a["asset"] == "SK하이닉스")
    assert sk["magnitude"] == "major"

def test_oscillator_validity_is_one_week(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    assert all(a["validity_until"] == "2026-06-14" for a in atoms)
    assert all(a["validity_type"] == "date" for a in atoms)

def test_oscillator_content_type_is_data(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    assert all(a["content_type"] == "data" for a in atoms)

def test_oscillator_source_trust_is_a(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    assert all(a["source_trust"] == "A" for a in atoms)

def test_consensus_positive_is_bullish(consensus_excel):
    atoms = consensus_to_atoms(consensus_excel, "2026-06-07")
    samsung = next(a for a in atoms if a["asset"] == "삼성전자")
    assert samsung["signal"] == "bullish"
    assert samsung["event_type"] == "consensus"

def test_consensus_negative_is_bearish(consensus_excel):
    atoms = consensus_to_atoms(consensus_excel, "2026-06-07")
    lg = next(a for a in atoms if a["asset"] == "LG에너지솔루션")
    assert lg["signal"] == "bearish"
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```powershell
python -m pytest tests/atoms/test_excel_converter.py -v 2>&1 | Select-Object -First 5
```

- [ ] **Step 3: `pipeline/atoms/excel_converter.py` 작성**

```python
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def _atom_id(date: str, source: str, asset: str) -> str:
    raw = f"{date}_{source}_{asset}"
    return "atom_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _next_week(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=7)).strftime("%Y-%m-%d")


def oscillator_to_atoms(file_path: str, date: str) -> list[dict]:
    """수급 오실레이터 Excel → 원자 리스트."""
    df = pd.read_excel(file_path)
    atoms = []

    osc_col = next(
        (c for c in df.columns if "오실레이터" in str(c) or "값" in str(c)), None
    )
    name_col = next(
        (c for c in df.columns if "종목" in str(c) or "이름" in str(c)), None
    )
    if not osc_col or not name_col:
        return atoms

    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        val = row[osc_col]
        if not name or pd.isna(val):
            continue
        val = float(val)
        signal = "bullish" if val > 0 else "bearish" if val < 0 else "neutral"
        magnitude = "major" if abs(val) > 50 else "minor"
        빈집 = " 수급 빈집 신호 발동." if val > 60 else ""
        direction = (
            "강한 매수 우위" if val > 50
            else "매수 우위" if val > 0
            else "매도 우위" if val > -50
            else "강한 매도 우위"
        )
        content = (
            f"{name} 외국인+기관 수급 오실레이터 {val:+.0f}. "
            f"수급 방향: {direction}.{빈집}"
        )
        atoms.append({
            "id": _atom_id(date, "수급오실레이터", name),
            "date": date,
            "source_type": "excel",
            "source_name": "수급오실레이터",
            "source_trust": "A",
            "raw_file": str(file_path),
            "layer": "L6",
            "sector": "기타",
            "asset": name,
            "asset_level": "stock",
            "signal": signal,
            "event_type": "supply",
            "magnitude": magnitude,
            "content_type": "data",
            "strength_score": 3 if magnitude == "major" else 2,
            "validity_type": "date",
            "validity_until": _next_week(date),
            "is_active": 1,
            "content": content,
            "relations": [],
        })
    return atoms


def consensus_to_atoms(file_path: str, date: str) -> list[dict]:
    """컨센서스 변화 Excel → 원자 리스트."""
    df = pd.read_excel(file_path)
    atoms = []

    name_col = next((c for c in df.columns if "종목" in str(c)), None)
    sector_col = next((c for c in df.columns if "섹터" in str(c)), None)
    change_col = next((c for c in df.columns if "컨센" in str(c) or "변화" in str(c)), None)
    tp_col = next((c for c in df.columns if "TP" in str(c) or "목표" in str(c)), None)

    if not name_col:
        return atoms

    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name == "nan":
            continue

        sector = str(row[sector_col]).strip() if sector_col else "기타"
        change_str = str(row[change_col]).strip() if change_col else ""
        tp_str = str(row[tp_col]).strip() if tp_col else ""

        signal = "neutral"
        if change_str and change_str not in ("nan", ""):
            if "+" in change_str or (
                change_str.replace(".", "").replace("%", "").lstrip("-").isdigit()
                and float(change_str.replace("%", "")) > 0
            ):
                signal = "bullish"
            elif "-" in change_str:
                signal = "bearish"

        content = f"{name} 컨센서스 변화: {change_str}."
        if tp_str and tp_str != "nan":
            content += f" 목표주가 {tp_str}원."

        atoms.append({
            "id": _atom_id(date, "컨센서스", name),
            "date": date,
            "source_type": "excel",
            "source_name": "컨센서스",
            "source_trust": "A",
            "raw_file": str(file_path),
            "layer": "L5",
            "sector": sector,
            "asset": name,
            "asset_level": "stock",
            "signal": signal,
            "event_type": "consensus",
            "magnitude": "minor",
            "content_type": "data",
            "strength_score": 2,
            "validity_type": "date",
            "validity_until": _next_week(date),
            "is_active": 1,
            "content": content,
            "relations": [],
        })
    return atoms
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```powershell
python -m pytest tests/atoms/test_excel_converter.py -v
```

기대 출력: `9 passed`

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/excel_converter.py tests/atoms/test_excel_converter.py
git commit -m "feat(atoms): Excel 수급/컨센서스 → 원자 변환"
```

---

## Task 5: Ingest 메인 진입점

**Files:**
- Create: `pipeline/atoms/ingest.py`
- Create: `tests/atoms/test_ingest.py`

- [ ] **Step 1: 테스트 먼저 작성**

```python
# tests/atoms/test_ingest.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, query_atoms
from pipeline.atoms.ingest import (
    ingest_file,
    _guess_trust,
    _guess_source_type,
    _guess_layer,
)

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()

def test_guess_trust_report_path():
    assert _guess_trust(Path("raw/wisereport/2026-06-07.md")) == "A"

def test_guess_trust_telegram_path():
    assert _guess_trust(Path("raw/telegram/2026-06-07_채널.md")) == "C"

def test_guess_trust_blog_path():
    assert _guess_trust(Path("raw/blog/2026-06-07_post.md")) == "D"

def test_guess_source_type_telegram():
    assert _guess_source_type(Path("raw/telegram/test.md")) == "telegram"

def test_guess_source_type_report():
    assert _guess_source_type(Path("raw/wisereport/test.md")) == "report"

def test_guess_layer_l5():
    assert _guess_layer(Path("raw/L5_섹터/반도체/test.md")) == "L5"

def test_guess_layer_default():
    assert _guess_layer(Path("raw/telegram/test.md")) == "L5"

@patch("pipeline.atoms.ingest.atomize_text")
def test_ingest_markdown_stores_atoms(mock_atomize, tmp_path, monkeypatch):
    test_file = tmp_path / "telegram" / "2026-06-07_신한.md"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("브로드컴 AI 가이던스 미달.", encoding="utf-8")

    mock_atomize.return_value = [{
        "id": "atom_test_001",
        "date": "2026-06-07",
        "source_type": "telegram",
        "source_name": "신한",
        "source_trust": "C",
        "raw_file": str(test_file),
        "layer": "L5",
        "sector": "반도체",
        "asset": "브로드컴",
        "asset_level": "stock",
        "signal": "bearish",
        "event_type": "earnings",
        "magnitude": "major",
        "content_type": "fact",
        "strength_score": 2,
        "validity_type": "permanent",
        "validity_until": None,
        "is_active": 1,
        "content": "브로드컴 AI 가이던스 미달.",
        "relations": [],
    }]

    count = ingest_file(str(test_file), "2026-06-07")
    assert count == 1
    results = query_atoms(sector="반도체", days=1)
    assert len(results) == 1
    assert results[0]["signal"] == "bearish"
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```powershell
python -m pytest tests/atoms/test_ingest.py -v 2>&1 | Select-Object -First 5
```

- [ ] **Step 3: `pipeline/atoms/ingest.py` 작성**

```python
"""
ingest.py — 단일 파일을 원자화하여 Atom DB에 저장.

사용법:
    python -m pipeline.atoms.ingest <파일경로> [날짜 YYYY-MM-DD]

예시:
    python -m pipeline.atoms.ingest raw/telegram/2026-06-07_신한.md 2026-06-07
    python -m pipeline.atoms.ingest raw/supply/oscillator.xlsx 2026-06-07
"""
import sys
from pathlib import Path
from datetime import datetime

from .db import init_db, insert_atom
from .atomizer import atomize_text
from .excel_converter import oscillator_to_atoms, consensus_to_atoms
from .taxonomy import SOURCE_TRUST_BY_PATH

_EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
_TEXT_SUFFIXES = {".md", ".txt"}


def ingest_file(file_path: str, date: str = None, source_trust: str = None) -> int:
    path = Path(file_path)
    date = date or datetime.now().strftime("%Y-%m-%d")

    if path.suffix in _EXCEL_SUFFIXES:
        return _ingest_excel(path, date)

    if path.suffix in _TEXT_SUFFIXES:
        return _ingest_text(path, date, source_trust)

    return 0


def _ingest_excel(path: Path, date: str) -> int:
    name = path.stem.lower()
    atoms: list[dict] = []

    if "오실레이터" in name or "oscillator" in name or "수급" in name:
        atoms = oscillator_to_atoms(str(path), date)
    elif "컨센" in name or "consensus" in name or "이익" in name:
        atoms = consensus_to_atoms(str(path), date)

    for atom in atoms:
        insert_atom(atom)
    return len(atoms)


def _ingest_text(path: Path, date: str, force_trust: str = None) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return 0

    source_name = _extract_source_name(path)
    trust = force_trust or _guess_trust(path)
    source_type = _guess_source_type(path)
    layer = _guess_layer(path)

    atoms = atomize_text(
        text=text,
        source_type=source_type,
        source_name=source_name,
        source_trust=trust,
        raw_file=str(path),
        date=date,
        layer=layer,
    )
    for atom in atoms:
        insert_atom(atom)
    return len(atoms)


def _extract_source_name(path: Path) -> str:
    stem = path.stem
    parts = stem.split("_")
    return parts[-1] if len(parts) > 1 else stem


def _guess_trust(path: Path) -> str:
    name = str(path).lower().replace("\\", "/")
    for key, trust in SOURCE_TRUST_BY_PATH.items():
        if key in name:
            return trust
    return "D"


def _guess_source_type(path: Path) -> str:
    name = str(path).lower().replace("\\", "/")
    if "telegram" in name:
        return "telegram"
    if "report" in name or "wisereport" in name:
        return "report"
    if "news" in name:
        return "news"
    if "blog" in name:
        return "blog"
    if "market" in name:
        return "news"
    return "unknown"


def _guess_layer(path: Path) -> str:
    name = str(path)
    for layer in ["L1", "L2", "L3", "L4", "L5", "L6"]:
        if layer in name:
            return layer
    return "L5"


if __name__ == "__main__":
    init_db()
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.atoms.ingest <file_path> [date]")
        sys.exit(1)
    file_path = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else None
    count = ingest_file(file_path, date)
    print(f"✅ {count}개 원자 저장 완료")
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```powershell
python -m pytest tests/atoms/test_ingest.py -v
```

기대 출력: `8 passed`

- [ ] **Step 5: 커밋**

```powershell
git add pipeline/atoms/ingest.py tests/atoms/test_ingest.py
git commit -m "feat(atoms): ingest 메인 진입점 (텍스트 + Excel 분기)"
```

---

## Task 6: 전체 테스트 + 실제 파일로 통합 검증

**Files:**
- Modify: `pipeline/atoms/db.py` — DB_PATH 환경변수 오버라이드 지원 (이미 완료)

- [ ] **Step 1: 전체 테스트 스위트 실행**

```powershell
python -m pytest tests/atoms/ -v
```

기대 출력: 모든 테스트 `PASSED` (30개 이상)

- [ ] **Step 2: DB 초기화**

```powershell
python -m pipeline.atoms.ingest --init
```

→ `pipeline/atoms/atoms.db` 생성 확인

실제로는:
```powershell
python -c "from pipeline.atoms.db import init_db; init_db(); print('DB 초기화 완료')"
```

- [ ] **Step 3: 실제 텔레그램 파일로 검증**

```powershell
python -m pipeline.atoms.ingest "raw\telegram\2026-06-05_신한리서치.md" 2026-06-05
```

기대 출력: `✅ N개 원자 저장 완료` (N = 10~30)

- [ ] **Step 4: DB 내용 확인**

```powershell
python -c "
from pipeline.atoms.db import query_atoms, get_atom_count
print(f'총 원자 수: {get_atom_count()}')
atoms = query_atoms(days=30, limit=5)
for a in atoms:
    print(f'  [{a[\"signal\"]}] {a[\"sector\"]} | {a[\"asset\"]} | {a[\"content\"][:50]}...')
"
```

기대 출력: 원자들이 signal/sector/asset 메타데이터와 함께 출력

- [ ] **Step 5: Excel 파일로 검증**

```powershell
python -m pipeline.atoms.ingest "raw\외국인기관수급오실레이터0521.xlsm" 2026-05-21
```

기대 출력: `✅ N개 원자 저장 완료` (종목 수만큼)

- [ ] **Step 6: 수급 원자 확인**

```powershell
python -c "
from pipeline.atoms.db import query_atoms
atoms = query_atoms(signal='bullish', days=60, limit=5)
for a in atoms:
    print(f'  {a[\"asset\"]} | {a[\"content\"]}')
"
```

- [ ] **Step 7: 최종 커밋**

```powershell
git add -A
git commit -m "feat(atoms): Atom DB 기반 구현 완료 — Plan 1 완료"
```

---

## 완료 기준

- [ ] `python -m pytest tests/atoms/ -v` → 전부 PASS
- [ ] 실제 텔레그램 파일 1개 → 원자 10개+ 저장됨
- [ ] 실제 Excel 파일 1개 → 원자 N개 저장됨 (종목 수만큼)
- [ ] `query_atoms()` → signal/sector 필터 작동 확인
- [ ] `expire_atoms()` → 만료 원자 비활성화 작동 확인

---

## 다음 계획 (Plan 2)

Plan 1 완료 후: `2026-06-07-vector-db-embedding.md`
- ChromaDB 설치 + 임베딩 파이프라인
- Google Embedding-004 연동
- 벡터 검색 함수 (query_similar)
- 기존 atoms.db → 벡터 일괄 생성
