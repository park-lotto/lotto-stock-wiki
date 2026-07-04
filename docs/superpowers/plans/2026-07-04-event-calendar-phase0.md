# 이벤트 캘린더 Phase 0 (데이터 파이프라인) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 크롤된 섹터 캘린더를 이벤트 원자로 적재하고, 미래 이벤트를 D-정렬 위키 보드로 투영하는 데이터 파이프라인을 만든다.

**Architecture:** 기존 `atoms.db`(SQLite)에 `event_date` 컬럼 하나만 추가하고, `fetch_sector_calendar.py`가 생산하는 `raw/캘린더/{date}_섹터캘린더.json`(현재 dead-end)을 읽어 이벤트 원자로 변환·적재하는 `calendar_ingest.py`, 그리고 미래 이벤트를 선택해 위키 마크다운 보드를 쓰는 `calendar_build.py`를 추가한다. 신규 스키마 결정은 `event_date` 컬럼 1개뿐이며 나머지 메타는 기존 `structured_fields`(JSON) 컬럼에 담는다.

**Tech Stack:** Python 3, sqlite3, pytest. 기존 모듈: `pipeline/atoms/db.py`, `fetch_sector_calendar.py`.

## Global Constraints

- 모든 테스트는 저장소 루트에서 `python -m pytest <path> -v`로 실행한다 (테스트가 `from pipeline.atoms...` 절대 임포트를 쓰므로 cwd=루트).
- 테스트 격리: `monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")` 후 `init_db()`로 임시 DB를 만든다. 실제 `atoms.db`를 건드리지 않는다.
- 신규 컬럼은 `schema.sql`이 아니라 `migrate_db()`의 `ALTER TABLE`로만 추가한다 (`structured_fields` 방식과 동일). 인덱스 명명: `idx_atoms_<column>`.
- `insert_atom(atom: dict)`은 단일 dict를 받고 named-param으로 INSERT하므로, 새 컬럼은 반드시 `a.setdefault(...)`로 기본값을 넣어야 한다 (기존 호출부 하위호환).
- `structured_fields`는 dict로 넘기면 `insert_atom`이 `json.dumps(ensure_ascii=False)`로 인코딩한다. 읽을 땐 `json.loads`.
- 커밋 메시지 끝에 다음 줄 추가:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 1: `event_date` 컬럼 추가 + insert_atom 배선

**Files:**
- Modify: `pipeline/atoms/db.py` (`_STRUCTURED_COLUMNS` 아래 / `migrate_db` / `insert_atom`)
- Test: `pipeline/atoms/test_event_date.py`

**Interfaces:**
- Consumes: 기존 `insert_atom(atom: dict) -> str`, `init_db()`, `get_conn()`
- Produces: `atoms` 테이블에 `event_date TEXT` 컬럼 + `idx_atoms_event_date` 인덱스. `insert_atom`이 `atom["event_date"]`(없으면 None)를 저장.

- [ ] **Step 1: 실패하는 테스트 작성**

`pipeline/atoms/test_event_date.py`:
```python
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom, get_conn


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _atom(**kw):
    base = dict(id="t1", date="2026-07-04", source_type="calendar",
                signal="catalyst", event_type="event", content="본문")
    base.update(kw)
    return base


def test_insert_atom_stores_event_date():
    insert_atom(_atom(event_date="2026-07-15"))
    conn = get_conn()
    row = conn.execute("SELECT event_date FROM atoms WHERE id=?", ("t1",)).fetchone()
    conn.close()
    assert row["event_date"] == "2026-07-15"


def test_insert_atom_without_event_date_is_null():
    insert_atom(_atom(id="t2"))
    conn = get_conn()
    row = conn.execute("SELECT event_date FROM atoms WHERE id=?", ("t2",)).fetchone()
    conn.close()
    assert row["event_date"] is None


def test_event_date_index_exists():
    conn = get_conn()
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_atoms_event_date'"
    ).fetchone()
    conn.close()
    assert idx is not None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest pipeline/atoms/test_event_date.py -v`
Expected: FAIL — `sqlite3.OperationalError: table atoms has no column named event_date` (insert 시).

- [ ] **Step 3: 최소 구현**

`pipeline/atoms/db.py` — `_STRUCTURED_COLUMNS` 정의 바로 아래에 추가:
```python
_EVENT_COLUMNS = [
    ("event_date", "TEXT"),
]
```

`migrate_db()`의 for 루프 대상에 `_EVENT_COLUMNS`를 더하고, 루프 뒤·commit 앞에 인덱스 생성 추가:
```python
def migrate_db():
    """기존 DB에 텔레그램 필드 멱등 추가 (이미 있으면 무시)."""
    conn = get_conn()
    for name, decl in _TG_COLUMNS + _SYNTH_COLUMNS + _YT_COLUMNS + _STRUCTURED_COLUMNS + _EVENT_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE atoms ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass  # 이미 존재
    conn.execute("CREATE INDEX IF NOT EXISTS idx_atoms_event_date ON atoms(event_date)")
    conn.commit()
    conn.close()
```

`insert_atom()` — 기존 `a.setdefault("deeplink", None)` 다음 줄에 추가:
```python
    a.setdefault("event_date", None)
```
그리고 INSERT 문의 컬럼 리스트 끝(`structured_fields` 뒤)과 VALUES 끝(`:structured_fields` 뒤)에 각각 `event_date` / `:event_date` 추가:
```python
        INSERT OR REPLACE INTO atoms
        (id, date, source_type, source_name, source_trust, raw_file,
         layer, sector, asset, asset_level,
         signal, event_type, magnitude, content_type, strength_score,
         validity_type, validity_until, is_active,
         content, relations, created_at,
         stance_key, mention_channels, mention_count, msg_ts,
         speaker, yt_timestamp, deeplink, structured_fields, event_date)
        VALUES
        (:id, :date, :source_type, :source_name, :source_trust, :raw_file,
         :layer, :sector, :asset, :asset_level,
         :signal, :event_type, :magnitude, :content_type, :strength_score,
         :validity_type, :validity_until, :is_active,
         :content, :relations, :created_at,
         :stance_key, :mention_channels, :mention_count, :msg_ts,
         :speaker, :yt_timestamp, :deeplink, :structured_fields, :event_date)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest pipeline/atoms/test_event_date.py -v`
Expected: 3 passed.

- [ ] **Step 5: 커밋**

```bash
git add pipeline/atoms/db.py pipeline/atoms/test_event_date.py
git commit -m "feat(atoms): add event_date column + index for event calendar"
```

---

### Task 2: 캘린더 이벤트 → 원자 매퍼 (순수 함수)

**Files:**
- Create: `pipeline/atoms/calendar_ingest.py`
- Test: `pipeline/atoms/test_calendar_ingest.py`

**Interfaces:**
- Consumes: 없음 (순수 변환)
- Produces:
  - `event_to_atom(ev: dict, sector: str, gen_date: str) -> dict` — 캘린더 이벤트 1건을 `insert_atom`이 받는 원자 dict로 변환. `structured_fields`는 dict로 담아 반환(인코딩은 insert_atom이 담당).
  - `_confidence(confirmed: bool, mention_count: int, has_date: bool) -> int` (1~4)
  - `_entity_scope(company, ev_type: str) -> str` ('domestic'|'foreign'|'policy')
  - `_map_kind(ev_type: str) -> str`
  - 상수 `FOREIGN_ENTITIES: set[str]`, `POLICY_KINDS: set[str]`

- [ ] **Step 1: 실패하는 테스트 작성**

`pipeline/atoms/test_calendar_ingest.py`:
```python
from pipeline.atoms.calendar_ingest import (
    event_to_atom, _confidence, _entity_scope, _map_kind,
)


def test_confidence_tiers():
    assert _confidence(True, 1, True) == 1        # 확정
    assert _confidence(False, 3, True) == 2       # 여러 소스
    assert _confidence(False, 1, True) == 3        # 단일 소스
    assert _confidence(False, 1, False) == 4       # 날짜 애매


def test_entity_scope():
    assert _entity_scope("삼성전자", "실적발표") == "domestic"
    assert _entity_scope("마이크론", "실적발표") == "foreign"
    assert _entity_scope(None, "금통위") == "policy"


def test_map_kind():
    assert _map_kind("실적발표") == "실적발표"
    assert _map_kind("금통위") == "정책"
    assert _map_kind("기타") == "트리거"


def test_event_to_atom_domestic_stock():
    ev = {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "가이던스 주목",
          "confirmed": True}
    a = event_to_atom(ev, sector="반도체", gen_date="2026-07-04")
    assert a["event_type"] == "event"
    assert a["signal"] == "catalyst"
    assert a["validity_type"] == "date"
    assert a["event_date"] == "2026-07-08"
    assert a["validity_until"] == "2026-07-08"
    assert a["sector"] == "반도체"
    assert a["asset"] == "삼성전자"
    assert a["asset_level"] == "stock"
    sf = a["structured_fields"]
    assert sf["event_kind"] == "실적발표"
    assert sf["entity_scope"] == "domestic"
    assert sf["event_form"] == "point"
    assert sf["affected_stocks"] == ["삼성전자"]
    assert sf["confidence"] == 1
    assert sf["confirmed"] is True


def test_event_to_atom_id_is_deterministic():
    ev = {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}
    a1 = event_to_atom(ev, "반도체", "2026-07-04")
    a2 = event_to_atom(ev, "반도체", "2026-07-04")
    assert a1["id"] == a2["id"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.atoms.calendar_ingest'`.

- [ ] **Step 3: 최소 구현**

`pipeline/atoms/calendar_ingest.py`:
```python
"""섹터 캘린더 JSON → 이벤트 원자 적재."""
import hashlib
import re

FOREIGN_ENTITIES = {
    "마이크론", "인텔", "TSMC", "엔비디아", "AMD", "애플",
    "마이크론테크놀로지", "브로드컴", "퀄컴",
}
POLICY_KINDS = {"정책", "FOMC", "금통위", "수출지표", "MSCI", "경제지표"}
_KIND_MAP = {
    "실적발표": "실적발표", "IR": "IR", "정책": "정책", "전시": "전시", "수주": "수주",
    "FOMC": "정책", "금통위": "정책", "수출지표": "정책", "MSCI": "정책", "경제지표": "정책",
}


def _map_kind(ev_type: str) -> str:
    return _KIND_MAP.get(ev_type, "트리거")


def _entity_scope(company, ev_type: str) -> str:
    if ev_type in POLICY_KINDS:
        return "policy"
    if company and company in FOREIGN_ENTITIES:
        return "foreign"
    return "domestic"


def _confidence(confirmed: bool, mention_count: int, has_date: bool) -> int:
    if not has_date:
        return 4
    if confirmed:
        return 1
    if mention_count >= 2:
        return 2
    return 3


def _evid(event_date: str, event: str, company) -> str:
    raw = f"{event_date}|{event}|{company or ''}"
    norm = re.sub(r"\s+", "", raw)
    return "cal_" + hashlib.md5(norm.encode()).hexdigest()[:12]


def event_to_atom(ev: dict, sector: str, gen_date: str) -> dict:
    company = ev.get("company")
    event = ev.get("event", "")
    event_date = ev.get("date")
    ev_type = ev.get("type", "기타")
    confirmed = bool(ev.get("confirmed", False))
    importance = ev.get("importance", "")
    has_date = bool(event_date)
    kind = _map_kind(ev_type)
    scope = _entity_scope(company, ev_type)
    conf = _confidence(confirmed, 1, has_date)
    affected = [company] if company else []
    return {
        "id": _evid(event_date, event, company),
        "date": gen_date,
        "source_type": "calendar",
        "source_name": "sector_calendar",
        "source_trust": "A" if confirmed else "C",
        "layer": "L5",
        "sector": sector,
        "asset": company or sector,
        "asset_level": "stock" if company else "sector",
        "signal": "catalyst",
        "event_type": "event",
        "magnitude": "major" if "HIGH" in importance else "minor",
        "content_type": "fact",
        "strength_score": 3 if "HIGH" in importance else 1,
        "validity_type": "date",
        "validity_until": event_date,
        "is_active": 1,
        "content": f"{event} — {ev.get('desc', '')}".strip(" —"),
        "event_date": event_date,
        "structured_fields": {
            "event_date": event_date,
            "event_kind": kind,
            "entity": company or sector,
            "entity_scope": scope,
            "event_form": "point",
            "affected_stocks": affected,
            "confidence": conf,
            "confirmed": confirmed,
        },
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_ingest.py -v`
Expected: 5 passed.

- [ ] **Step 5: 커밋**

```bash
git add pipeline/atoms/calendar_ingest.py pipeline/atoms/test_calendar_ingest.py
git commit -m "feat(calendar): map sector-calendar events to event atoms"
```

---

### Task 3: 캘린더 파일 적재 + CLI

**Files:**
- Modify: `pipeline/atoms/calendar_ingest.py`
- Test: `pipeline/atoms/test_calendar_ingest_file.py`

**Interfaces:**
- Consumes: `event_to_atom()` (Task 2), `insert_atom()` (Task 1), `init_db()`
- Produces: `ingest_calendar_file(path: str) -> int` — `{date}_섹터캘린더.json`(`{"generated_at","macro":[...],"sectors":{sector:[...]}}`)을 읽어 원자 적재, 적재 건수 반환. macro 이벤트는 sector="매크로"로.

- [ ] **Step 1: 실패하는 테스트 작성**

`pipeline/atoms/test_calendar_ingest_file.py`:
```python
import json
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, get_conn
from pipeline.atoms.calendar_ingest import ingest_calendar_file


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _write_cal(tmp_path):
    data = {
        "generated_at": "2026-07-04",
        "macro": [
            {"date": "2026-07-18", "event": "금통위", "type": "금통위",
             "importance": "[HIGH]", "desc": "기준금리 결정", "confirmed": True},
        ],
        "sectors": {
            "반도체": [
                {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
                 "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True},
            ],
        },
    }
    p = tmp_path / "20260704_섹터캘린더.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_ingest_calendar_file_inserts_all(tmp_path):
    n = ingest_calendar_file(str(_write_cal(tmp_path)))
    assert n == 2
    conn = get_conn()
    rows = conn.execute(
        "SELECT sector, asset, event_date FROM atoms WHERE event_type='event' ORDER BY event_date"
    ).fetchall()
    conn.close()
    assert [dict(r)["asset"] for r in rows] == ["삼성전자", "금통위"]
    assert dict(rows[1])["sector"] == "매크로"


def test_ingest_is_idempotent(tmp_path):
    p = _write_cal(tmp_path)
    ingest_calendar_file(str(p))
    ingest_calendar_file(str(p))
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM atoms").fetchone()["c"]
    conn.close()
    assert n == 2  # INSERT OR REPLACE → 중복 없음
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_ingest_file.py -v`
Expected: FAIL — `ImportError: cannot import name 'ingest_calendar_file'`.

- [ ] **Step 3: 최소 구현**

`pipeline/atoms/calendar_ingest.py` 상단 import에 추가: `import json`, `import sys`, `from pathlib import Path`, `from pipeline.atoms.db import insert_atom, init_db`.
파일 하단에 추가:
```python
def ingest_calendar_file(path: str) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    gen_date = data.get("generated_at", "")[:10] or "1970-01-01"
    count = 0
    for ev in data.get("macro", []):
        insert_atom(event_to_atom(ev, sector="매크로", gen_date=gen_date))
        count += 1
    for sector, evs in data.get("sectors", {}).items():
        for ev in evs:
            insert_atom(event_to_atom(ev, sector=sector, gen_date=gen_date))
            count += 1
    return count


if __name__ == "__main__":
    init_db()
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not target:
        cal_dir = Path(__file__).parent.parent.parent / "raw" / "캘린더"
        files = sorted(cal_dir.glob("*_섹터캘린더.json"))
        if not files:
            print("섹터캘린더.json 없음 — 먼저 fetch_sector_calendar.py 실행"); sys.exit(1)
        target = str(files[-1])
    n = ingest_calendar_file(target)
    print(f"적재 완료: {n}건 ← {target}")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_ingest_file.py -v`
Expected: 2 passed.

- [ ] **Step 5: 커밋**

```bash
git add pipeline/atoms/calendar_ingest.py pipeline/atoms/test_calendar_ingest_file.py
git commit -m "feat(calendar): ingest sector-calendar json into atoms + CLI"
```

---

### Task 4: 미래 이벤트 선택기

**Files:**
- Create: `pipeline/atoms/calendar_build.py`
- Test: `pipeline/atoms/test_calendar_build.py`

**Interfaces:**
- Consumes: `get_conn()` (Task 1), `event_to_atom`/`ingest_calendar_file`로 적재된 원자
- Produces: `select_future_events(today: str, watchlist: list[str] | None = None, sector: str | None = None) -> list[dict]` — `event_date >= today`, `event_type='event'`, `is_active=1` 원자를 `event_date` 오름차순으로. 각 dict에 `structured_fields`(decode됨)와 `dday`(정수, `today`~`event_date` 일수) 포함. `watchlist` 주면 `affected_stocks`가 교집합인 것만, `sector` 주면 해당 섹터만.

- [ ] **Step 1: 실패하는 테스트 작성**

`pipeline/atoms/test_calendar_build.py`:
```python
import json
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
from pipeline.atoms.calendar_build import select_future_events


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    _seed()
    yield


def _seed():
    evs = [
        ({"date": "2026-07-08", "company": "삼성전자", "event": "2Q 실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}, "반도체"),
        ({"date": "2026-07-25", "company": "HD현대중공업", "event": "2Q 실적",
          "type": "실적발표", "importance": "[MID]", "desc": "", "confirmed": True}, "조선"),
        ({"date": "2026-06-30", "company": "삼성전자", "event": "지난 이벤트",
          "type": "실적발표", "importance": "[LOW]", "desc": "", "confirmed": True}, "반도체"),
    ]
    for ev, sec in evs:
        insert_atom(event_to_atom(ev, sector=sec, gen_date="2026-07-04"))


def test_only_future_sorted():
    out = select_future_events("2026-07-04")
    assert [e["event_date"] for e in out] == ["2026-07-08", "2026-07-25"]  # 06-30 제외


def test_dday_computed():
    out = select_future_events("2026-07-04")
    assert out[0]["dday"] == 4
    assert out[0]["structured_fields"]["event_kind"] == "실적발표"


def test_watchlist_filter():
    out = select_future_events("2026-07-04", watchlist=["삼성전자"])
    assert [e["asset"] for e in out] == ["삼성전자"]


def test_sector_filter():
    out = select_future_events("2026-07-04", sector="조선")
    assert [e["asset"] for e in out] == ["HD현대중공업"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.atoms.calendar_build'`.

- [ ] **Step 3: 최소 구현**

`pipeline/atoms/calendar_build.py`:
```python
"""이벤트 원자 → D-정렬 투영 + 위키 보드."""
import json
from datetime import date as _date
from pipeline.atoms.db import get_conn


def _dday(today: str, event_date: str) -> int:
    y1, m1, d1 = (int(x) for x in today.split("-"))
    y2, m2, d2 = (int(x) for x in event_date.split("-"))
    return (_date(y2, m2, d2) - _date(y1, m1, d1)).days


def select_future_events(today: str, watchlist=None, sector=None) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM atoms WHERE event_type='event' AND is_active=1 "
        "AND event_date IS NOT NULL AND event_date >= ? ORDER BY event_date ASC",
        (today,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["structured_fields"] = json.loads(d["structured_fields"]) if d.get("structured_fields") else {}
        except (json.JSONDecodeError, TypeError):
            d["structured_fields"] = {}
        d["dday"] = _dday(today, d["event_date"])
        affected = d["structured_fields"].get("affected_stocks", [])
        if watchlist and not (set(watchlist) & set(affected)):
            continue
        if sector and d.get("sector") != sector:
            continue
        out.append(d)
    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_build.py -v`
Expected: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add pipeline/atoms/calendar_build.py pipeline/atoms/test_calendar_build.py
git commit -m "feat(calendar): select future events with D-day, watchlist/sector filter"
```

---

### Task 5: 위키 캘린더 보드 생성 + CLI

**Files:**
- Modify: `pipeline/atoms/calendar_build.py`
- Test: `pipeline/atoms/test_calendar_board.py`

**Interfaces:**
- Consumes: `select_future_events()` (Task 4)
- Produces: `build_calendar_board(today: str, out_dir: str) -> str` — `{out_dir}/캘린더_index.md`에 D-정렬 마크다운 표(`| 날짜 | D-N | 종목/섹터 | 이벤트 | 종류 | 확정도 | `)를 쓰고 경로 반환. 확정도는 1→●확정 2→◐높음 3→○관측 4→·추정.

- [ ] **Step 1: 실패하는 테스트 작성**

`pipeline/atoms/test_calendar_board.py`:
```python
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
from pipeline.atoms.calendar_build import build_calendar_board


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    insert_atom(event_to_atom(
        {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
         "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True},
        sector="반도체", gen_date="2026-07-04"))
    yield


def test_board_written(tmp_path):
    path = build_calendar_board("2026-07-04", str(tmp_path))
    text = open(path, encoding="utf-8").read()
    assert "D-4" in text
    assert "삼성전자" in text
    assert "실적발표" in text
    assert "● 확정" in text
    assert path.endswith("캘린더_index.md")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_board.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_calendar_board'`.

- [ ] **Step 3: 최소 구현**

`pipeline/atoms/calendar_build.py` 상단 import에 `import sys`, `from pathlib import Path` 추가. 파일 하단에 추가:
```python
_CONF_LABEL = {1: "● 확정", 2: "◐ 높음", 3: "○ 관측", 4: "· 추정"}


def build_calendar_board(today: str, out_dir: str) -> str:
    events = select_future_events(today)
    lines = [
        f"# 📅 이벤트 캘린더 — {today} 기준",
        "",
        "| 날짜 | D | 종목/섹터 | 이벤트 | 종류 | 확정도 |",
        "|---|---|---|---|---|---|",
    ]
    for e in events:
        sf = e["structured_fields"]
        conf = _CONF_LABEL.get(sf.get("confidence", 4), "· 추정")
        lines.append(
            f"| {e['event_date']} | D-{e['dday']} | {e['asset']} | "
            f"{e['content']} | {sf.get('event_kind','')} | {conf} |"
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "캘린더_index.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    from datetime import datetime
    today = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent.parent.parent / "wiki" / "이벤트캘린더"
    p = build_calendar_board(today, str(out_dir))
    print(f"보드 생성: {p}")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest pipeline/atoms/test_calendar_board.py -v`
Expected: 1 passed.

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python -m pytest pipeline/atoms/test_event_date.py pipeline/atoms/test_calendar_ingest.py pipeline/atoms/test_calendar_ingest_file.py pipeline/atoms/test_calendar_build.py pipeline/atoms/test_calendar_board.py -v`
Expected: 전부 통과.

```bash
git add pipeline/atoms/calendar_build.py pipeline/atoms/test_calendar_board.py
git commit -m "feat(calendar): write D-sorted wiki calendar board + CLI"
```

---

## 통합 검증 (수동, 실데이터)

계획 완료 후 실제 파이프 구동으로 Phase 0 성공 기준 확인 (fablize 그라운딩):
```bash
# 1) 오늘 섹터 캘린더 생성 (기존 스크립트, Gemini 필요)
python fetch_sector_calendar.py --sectors 반도체,조선
# 2) 이벤트 원자 적재
python -m pipeline.atoms.calendar_ingest
# 3) 위키 보드 생성
python -m pipeline.atoms.calendar_build
# 4) 확인
cat "wiki/이벤트캘린더/캘린더_index.md"
```
Expected: `raw/캘린더/{today}_섹터캘린더.json` 생성 → 원자 N건 적재 → `wiki/이벤트캘린더/캘린더_index.md`에 D-정렬 표 출력.

---

## Self-Review (완료)

- **Spec coverage:** 스펙 4.1(event_date 컬럼)=Task1, 4.2 확정일정 공급원(섹터캘린더 적재)=Task2·3, 4.3 확정도=Task2 `_confidence`, 4.6 일일 루프(적재→투영→보드)=Task3·5, 4.7 위키 보드=Task5, 접근용 셀렉터(4.8/API 준비)=Task4. **미포함(의도적, 후속 Phase):** 예상 트리거 추출(atomizer catalyst→event_date, Phase 3), 사가(Phase 3), event_merge 확정도 부스트(Phase 1), 락업/옵션/배당락(Phase 3), UI/API(Phase 1·2). Phase 0 범위는 "확정 일정이 매일 적재되고 보드가 생성됨"으로 한정.
- **Placeholder scan:** 모든 스텝에 실제 코드/명령/기대출력 포함. TBD 없음.
- **Type consistency:** `event_to_atom`/`_confidence`/`_entity_scope`/`_map_kind`(Task2) → `ingest_calendar_file`(Task3) → `select_future_events`(Task4) → `build_calendar_board`(Task5) 시그니처 일관. `structured_fields` dict 저장(Task2) ↔ json.loads 복원(Task4) 일치.
