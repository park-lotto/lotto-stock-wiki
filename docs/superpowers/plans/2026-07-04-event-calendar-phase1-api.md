# 이벤트 캘린더 Phase 1-a (촉매 투영 API) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Phase 0의 이벤트 원자를 프론트가 바인딩할 수 있는 `/api/catalysts` HTTP 엔드포인트로 노출한다 (기존 관심종목 watchlist를 "내 종목" 필터로 재사용).

**Architecture:** `calendar_build.select_future_events`에 D-호라이즌(`days`) 필터와 프론트용 셰이핑 헬퍼 `to_api_dict`를 더하고, `dashboard/server.py`에 sync GET `/api/catalysts`를 추가한다. 이미 있는 `_load_watchlist_codes()`(`pipeline/watchlist.json`)로 내 종목을 읽어 필터한다. 신규 watchlist 파일/엔드포인트는 만들지 않는다.

**Tech Stack:** FastAPI(포트 8090, JSONResponse), sqlite3, pytest + FastAPI TestClient.

## Global Constraints

- 테스트는 저장소 루트에서 `py -m pytest <path> -q` (Windows `py` 런처, `python`은 스텁이라 안 됨).
- DB 격리: `monkeypatch.setattr(dbmod, "DB_PATH", tmp_path/"t.db")` 후 `init_db()`.
- 엔드포인트는 FastAPI 관례 준수: 쿼리파라미터=기본값 있는 타입인자, 반환=`JSONResponse(content=...)`, 순수 sync 작업은 `def`(async 아님). 무거운 의존은 **핸들러 안에서 lazy import**.
- server.py는 이미 루트를 sys.path에 넣음(13–18). 새 상태파일 만들지 말 것 — `_load_watchlist_codes()` 재사용.
- 커밋 전 `git branch --show-current`로 `feat/briefing-engine` 확인(공유 워킹트리). `git add`는 파일 지정, `-A` 금지.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 1: select_future_events `days` 호라이즌 + `to_api_dict` 셰이퍼

**Files:**
- Modify: `pipeline/atoms/calendar_build.py`
- Test: `pipeline/atoms/test_calendar_api_shape.py`

**Interfaces:**
- Consumes: 기존 `select_future_events(today, watchlist=None, sector=None)` (Phase 0)
- Produces:
  - `select_future_events(today, watchlist=None, sector=None, days=None)` — `days`가 정수면 `dday > days`인 이벤트 제외 (기본 None=무제한, 하위호환)
  - `to_api_dict(e: dict) -> dict` — 프론트용 평면 dict: `event_date, dday, asset, sector, content, event_kind, entity_scope, confidence, confirmed, affected_stocks`

- [ ] **Step 1: 실패하는 테스트 작성**

`pipeline/atoms/test_calendar_api_shape.py`:
```python
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
from pipeline.atoms.calendar_build import select_future_events, to_api_dict


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    for ev, sec in [
        ({"date": "2026-07-08", "company": "삼성전자", "event": "2Q 실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}, "반도체"),
        ({"date": "2026-08-20", "company": "HD현대중공업", "event": "먼 이벤트",
          "type": "실적발표", "importance": "[MID]", "desc": "", "confirmed": True}, "조선"),
    ]:
        insert_atom(event_to_atom(ev, sector=sec, gen_date="2026-07-04"))
    yield


def test_days_horizon_excludes_far_events():
    out = select_future_events("2026-07-04", days=30)   # 08-20은 D-47 → 제외
    assert [e["asset"] for e in out] == ["삼성전자"]


def test_days_none_returns_all():
    out = select_future_events("2026-07-04")
    assert len(out) == 2


def test_to_api_dict_shape():
    e = select_future_events("2026-07-04", days=30)[0]
    d = to_api_dict(e)
    assert d == {
        "event_date": "2026-07-08", "dday": 4, "asset": "삼성전자",
        "sector": "반도체", "content": "2Q 실적", "event_kind": "실적발표",
        "entity_scope": "domestic", "confidence": 1, "confirmed": True,
        "affected_stocks": ["삼성전자"],
    }
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest pipeline/atoms/test_calendar_api_shape.py -q`
Expected: FAIL — `TypeError: select_future_events() got an unexpected keyword argument 'days'` / `ImportError: to_api_dict`.

- [ ] **Step 3: 최소 구현**

`pipeline/atoms/calendar_build.py` — `select_future_events` 시그니처와 필터 추가:
```python
def select_future_events(today: str, watchlist=None, sector=None, days=None) -> list[dict]:
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
        if days is not None and d["dday"] > days:
            continue
        affected = d["structured_fields"].get("affected_stocks", [])
        if watchlist and not (set(watchlist) & set(affected)):
            continue
        if sector and d.get("sector") != sector:
            continue
        out.append(d)
    return out
```
파일 하단(`build_calendar_board` 아래, `if __name__` 위)에 셰이퍼 추가:
```python
def to_api_dict(e: dict) -> dict:
    sf = e.get("structured_fields", {})
    return {
        "event_date": e.get("event_date"),
        "dday": e.get("dday"),
        "asset": e.get("asset"),
        "sector": e.get("sector"),
        "content": e.get("content"),
        "event_kind": sf.get("event_kind"),
        "entity_scope": sf.get("entity_scope"),
        "confidence": sf.get("confidence"),
        "confirmed": sf.get("confirmed"),
        "affected_stocks": sf.get("affected_stocks", []),
    }
```

- [ ] **Step 4: 통과 확인 + 회귀**

Run: `py -m pytest pipeline/atoms/test_calendar_api_shape.py pipeline/atoms/test_calendar_build.py pipeline/atoms/test_calendar_board.py -q`
Expected: 전부 통과 (기존 Phase 0 테스트 포함).

- [ ] **Step 5: 커밋**

```bash
git add pipeline/atoms/calendar_build.py pipeline/atoms/test_calendar_api_shape.py
git commit -m "feat(calendar): days horizon + to_api_dict shaper for API

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `/api/catalysts` 엔드포인트

**Files:**
- Modify: `dashboard/server.py` (기존 `/api/watchlist` 근처, server.py:2422 영역 뒤)
- Test: `tests/test_catalysts_api.py`

**Interfaces:**
- Consumes: `select_future_events`, `to_api_dict` (Task 1); 기존 `server._load_watchlist_codes()`
- Produces: `GET /api/catalysts?sector=&days=30&mine=1&today=` → `JSONResponse({"today", "count", "events":[to_api_dict...]})`. `mine=1`이고 watchlist 종목명이 있으면 그 종목 촉매만; 없으면 전체. `today` 비면 오늘.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_catalysts_api.py`:
```python
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dashboard"))

import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.db import init_db, insert_atom
from pipeline.atoms.calendar_ingest import event_to_atom
import server
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    init_db()
    for ev, sec in [
        ({"date": "2026-07-08", "company": "삼성전자", "event": "2Q 실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}, "반도체"),
        ({"date": "2026-07-25", "company": "HD현대중공업", "event": "2Q 실적",
          "type": "실적발표", "importance": "[MID]", "desc": "", "confirmed": True}, "조선"),
    ]:
        insert_atom(event_to_atom(ev, sector=sec, gen_date="2026-07-04"))
    wl = tmp_path / "watchlist.json"
    wl.write_text(json.dumps({"codes": [{"code": "005930", "name": "삼성전자"}]}), encoding="utf-8")
    monkeypatch.setattr(server, "WATCHLIST_PATH", str(wl))
    yield


def _client():
    return TestClient(server.app)


def test_catalysts_all():
    r = _client().get("/api/catalysts?mine=0&today=2026-07-04").json()
    assert r["count"] == 2
    assert r["events"][0]["asset"] == "삼성전자"
    assert r["events"][0]["dday"] == 4


def test_catalysts_mine_filters_by_watchlist():
    r = _client().get("/api/catalysts?mine=1&today=2026-07-04").json()
    assert [e["asset"] for e in r["events"]] == ["삼성전자"]


def test_catalysts_sector_filter():
    r = _client().get("/api/catalysts?mine=0&sector=조선&today=2026-07-04").json()
    assert [e["asset"] for e in r["events"]] == ["HD현대중공업"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest tests/test_catalysts_api.py -q`
Expected: FAIL — 404 (엔드포인트 없음) → `r["count"]` KeyError.

- [ ] **Step 3: 최소 구현**

`dashboard/server.py`의 `api_watchlist_get`(2435 영역) 정의 뒤에 추가:
```python
@app.get("/api/catalysts")
def api_catalysts(sector: str = "", days: int = 30, mine: int = 1, today: str = ""):
    """다가오는 촉매(이벤트 원자) — 내 종목/섹터 필터. 프론트 바인딩용."""
    from datetime import datetime
    from pipeline.atoms.calendar_build import select_future_events, to_api_dict
    day = (today or "").strip() or datetime.now().strftime("%Y-%m-%d")
    watch = None
    if mine:
        names = [c.get("name") for c in _load_watchlist_codes()
                 if isinstance(c, dict) and c.get("name")]
        watch = names or None
    events = select_future_events(day, watchlist=watch,
                                  sector=(sector.strip() or None), days=days)
    return JSONResponse(content={
        "today": day, "count": len(events),
        "events": [to_api_dict(e) for e in events],
    })
```

- [ ] **Step 4: 통과 확인**

Run: `py -m pytest tests/test_catalysts_api.py -q`
Expected: 3 passed.

- [ ] **Step 5: 커밋**

```bash
git add dashboard/server.py tests/test_catalysts_api.py
git commit -m "feat(api): GET /api/catalysts projecting event atoms with watchlist/sector filter

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 통합 검증 (수동)

```bash
python dashboard/server.py   # 8090
curl "http://localhost:8090/api/catalysts?mine=0&days=30"
```
Expected: `{"today":..., "count":N, "events":[...]}` (실데이터 없으면 count 0). 서버 기동 후 `/api/catalysts` 200.

## Self-Review (완료)
- **Spec coverage:** 스펙 6절 ⑦(/api/catalysts)=Task2, ④ select_future_events 확장(days)=Task1. ⑧ watchlist=기존 재사용(신규 불필요). 
- **미포함(의도적):** UI 이식(⑨⑩)=Phase 1-b 별도 계획(비주얼 그라운딩 필요). 사가/트리거=Phase 3.
- **Placeholder scan:** 실제 코드/명령/기대값만. 없음.
- **Type consistency:** `select_future_events(...,days=None)`·`to_api_dict`(Task1) ↔ 엔드포인트 호출(Task2) 일치. `_load_watchlist_codes()`/`WATCHLIST_PATH`는 기존 server.py 심볼.
