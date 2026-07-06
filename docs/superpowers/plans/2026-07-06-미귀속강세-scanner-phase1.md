# 미귀속 강세 스캐너 (Phase 1 · MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 히트맵 상위 강세 종목을 스캔해, 기존 `atoms.db`에서 귀속 이슈를 찾고, **이유를 못 찾은 강세를 침묵시키지 않고 최상단에 고정**한 랭킹 목록 + 촘촘함 지표를 만든다. 신규 크롤러 없이 기존 데이터만 사용.

**Architecture:** 순수 함수 3개(귀속판정·랭킹·지표)를 먼저 TDD로 만들고, 그 위에 히트맵/atoms를 엮는 얇은 통합 어댑터와 FastAPI 엔드포인트를 얹는다. 순수 함수는 `query_fn` 주입으로 네트워크 없이 테스트한다. 이후 Phase 2(관계그래프)·3(캐스케이드)·4(지표 대시보드)의 토대.

**Tech Stack:** Python 3.14, SQLite(`pipeline/atoms/db.py`), FastAPI(`dashboard/server.py`), pytest(`py -m pytest`). LLM 없음(Phase 1).

## Global Constraints

- 테스트 실행은 반드시 `py -m pytest` (Windows `py` 런처). `python` 아님.
- 새 순수 함수는 네트워크/DB 직접 접근 없이 인자 주입으로 테스트 가능해야 함(`query_fn` 파라미터).
- 신규 코드의 LLM 호출 표준은 `key_vault.get_client(group)` + `google.genai` (Phase 1은 LLM 미사용).
- **침묵 금지 규칙:** 입력된 강세 종목은 하나도 결과에서 누락되면 안 됨(귀속 실패 = 상단 경보로 승격, 삭제 아님).
- 원자 신뢰등급 라벨은 이모지 세트 고정: 🟢 확정/사실, 🟡 미확인·속보, 🟠 루머·심리, 🔵 추론.
- 임포트는 절대경로(`import pipeline.atoms.db`)로 — 루트 `conftest.py`가 sys.path에 root+dashboard를 넣음.

---

## File Structure

- Create: `pipeline/atoms/strength_net.py` — Phase 1 핵심 모듈(순수 함수 + 얇은 통합 어댑터).
- Create: `pipeline/atoms/test_strength_net.py` — 콜로케이트 테스트(기존 `pipeline/atoms/test_*.py` 패턴).
- Modify: `dashboard/server.py` — `GET /api/net/unattributed` 엔드포인트 1개 추가.
- Create: `tests/test_net_unattributed_api.py` — 엔드포인트 델리게이트 테스트.

**strength_net.py 책임 분해:**
- `trust_tier(atom) -> str` — atom의 source_type/source_trust → 신뢰등급 이모지.
- `attribute_mover(mover, days, query_fn) -> dict` — 한 종목에 귀속 이슈 판정(순수).
- `scan_movers(movers, days, query_fn) -> list[dict]` — 여러 종목 스캔(순수).
- `rank_results(results) -> list[dict]` — 정렬 반전(미귀속 상단 고정, 순수).
- `coverage_metrics(results) -> dict` — 귀속률·미귀속수·침묵누락 지표(순수).
- `scan_heatmap(top_n, days) -> dict` — 라이브 히트맵→movers→위 파이프 실행(통합, 유일한 impure).

---

## Data Model

**mover (입력):** `{"name": str, "code": str, "sector": str, "rate": float}`
**result (출력, attribute_mover 반환):**
```python
{
  "name": str, "code": str, "sector": str, "rate": float,
  "attributed": bool,
  "issue": str | None,          # 귀속된 atom의 content(요약), 없으면 None
  "trust": str | None,          # 신뢰등급 이모지, 미귀속이면 None
  "source": str | None,         # atom source_name, 미귀속이면 None
  "atom_ids": list[str],        # 근거 atom id들
  "status": str,                # "attributed" | "unattributed"
  "priority": int,              # 0 = 미귀속(상단), 1 = 귀속
  "flag": str | None,           # "⚠️ 원인 미상 강세 — 추적 요망" | None
}
```

---

### Task 1: `trust_tier()` — 원자 신뢰등급 매핑

**Files:**
- Create: `pipeline/atoms/strength_net.py`
- Test: `pipeline/atoms/test_strength_net.py`

**Interfaces:**
- Consumes: atom dict(`pipeline.atoms.db.query_atoms` 반환 형태) — 키 `source_type`, `source_trust`, `certainty` 사용.
- Produces: `trust_tier(atom: dict) -> str` (이모지 문자열).

- [ ] **Step 1: Write the failing test**

```python
# pipeline/atoms/test_strength_net.py
import pipeline.atoms.strength_net as sn

def test_trust_tier_disclosure_is_green():
    assert sn.trust_tier({"source_type": "공시", "source_trust": "A"}) == "🟢"

def test_trust_tier_news_is_green():
    assert sn.trust_tier({"source_type": "news", "source_trust": "B"}) == "🟢"

def test_trust_tier_telegram_is_yellow():
    assert sn.trust_tier({"source_type": "telegram", "source_trust": "C"}) == "🟡"

def test_trust_tier_unknown_source_defaults_blue():
    assert sn.trust_tier({"source_type": "misc", "source_trust": "D"}) == "🔵"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.atoms.strength_net'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/atoms/strength_net.py
"""미귀속 강세 스캐너 (Phase 1). 히트맵 강세를 기존 atoms.db로 귀속 판정한다."""

_TIER_BY_SOURCE = {
    "공시": "🟢", "dart": "🟢", "disclosure": "🟢",
    "news": "🟢", "뉴스": "🟢",
    "telegram": "🟡", "텔레그램": "🟡",
    "종토방": "🟠", "naver_board": "🟠",
}

def trust_tier(atom: dict) -> str:
    """atom의 source_type을 신뢰등급 이모지로. 미지의 소스는 🔵(추론급)."""
    st = (atom.get("source_type") or "").strip().lower()
    for key, tier in _TIER_BY_SOURCE.items():
        if key.lower() == st:
            return tier
    return "🔵"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/strength_net.py pipeline/atoms/test_strength_net.py
git commit -m "feat(net): trust_tier — atom source_type을 신뢰등급으로 매핑"
```

---

### Task 2: `attribute_mover()` — 한 종목 귀속 판정

**Files:**
- Modify: `pipeline/atoms/strength_net.py`
- Test: `pipeline/atoms/test_strength_net.py`

**Interfaces:**
- Consumes: `query_fn(asset=..., days=..., active_only=True) -> list[dict]` (기본값은 `pipeline.atoms.db.query_atoms`). atom 키: `id`, `content`, `signal`, `source_name`, `source_trust`, `strength_score`, `source_type`.
- Produces: `attribute_mover(mover: dict, days: int = 3, query_fn=None) -> dict` (위 Data Model의 result dict).

- [ ] **Step 1: Write the failing test**

```python
# append to pipeline/atoms/test_strength_net.py

def _fake_query(atoms_by_asset):
    def q(asset=None, days=None, active_only=True):
        return atoms_by_asset.get(asset, [])
    return q

def test_attribute_mover_finds_bullish_atom():
    mover = {"name": "가온칩스", "code": "399720", "sector": "반도체", "rate": 12.3}
    atoms = {"가온칩스": [
        {"id": "a1", "content": "296억 ASIC 계약 공시", "signal": "bullish",
         "source_type": "공시", "source_name": "DART", "source_trust": "A", "strength_score": 5},
    ]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms))
    assert r["attributed"] is True
    assert r["status"] == "attributed"
    assert r["priority"] == 1
    assert r["trust"] == "🟢"
    assert r["atom_ids"] == ["a1"]
    assert r["flag"] is None

def test_attribute_mover_unattributed_when_no_atom():
    mover = {"name": "무이슈주", "code": "000000", "sector": "기타", "rate": 9.9}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query({}))
    assert r["attributed"] is False
    assert r["status"] == "unattributed"
    assert r["priority"] == 0
    assert r["issue"] is None
    assert r["flag"] == "⚠️ 원인 미상 강세 — 추적 요망"

def test_attribute_mover_ignores_neutral_atoms():
    mover = {"name": "보합주", "code": "111111", "sector": "기타", "rate": 8.0}
    atoms = {"보합주": [
        {"id": "n1", "content": "정기 IR", "signal": "neutral",
         "source_type": "news", "source_name": "X", "source_trust": "C", "strength_score": 1},
    ]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms))
    assert r["attributed"] is False

def test_attribute_mover_picks_highest_strength_atom():
    mover = {"name": "다중주", "code": "222222", "sector": "기타", "rate": 7.0}
    atoms = {"다중주": [
        {"id": "w", "content": "약한 뉴스", "signal": "bullish",
         "source_type": "news", "source_name": "N", "source_trust": "C", "strength_score": 2},
        {"id": "s", "content": "강한 공시", "signal": "bullish",
         "source_type": "공시", "source_name": "DART", "source_trust": "A", "strength_score": 5},
    ]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms))
    assert r["issue"] == "강한 공시"
    assert r["atom_ids"][0] == "s"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'attribute_mover'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to pipeline/atoms/strength_net.py
from pipeline.atoms import db as _db

_BULLISH_SIGNALS = {"bullish", "positive", "상승", "호재"}
_UNATTR_FLAG = "⚠️ 원인 미상 강세 — 추적 요망"

def attribute_mover(mover: dict, days: int = 3, query_fn=None) -> dict:
    """한 강세 종목에 대해 기존 atom에서 귀속 이슈를 찾는다. 없으면 미귀속으로 승격."""
    if query_fn is None:
        query_fn = _db.query_atoms
    name = mover.get("name")
    atoms = query_fn(asset=name, days=days, active_only=True) or []
    hits = [a for a in atoms if (a.get("signal") or "").strip().lower() in _BULLISH_SIGNALS
            or (a.get("signal") or "").strip() in _BULLISH_SIGNALS]
    base = {
        "name": name, "code": mover.get("code"),
        "sector": mover.get("sector"), "rate": mover.get("rate"),
    }
    if not hits:
        return {**base, "attributed": False, "issue": None, "trust": None,
                "source": None, "atom_ids": [], "status": "unattributed",
                "priority": 0, "flag": _UNATTR_FLAG}
    hits.sort(key=lambda a: a.get("strength_score", 1), reverse=True)
    top = hits[0]
    return {**base, "attributed": True, "issue": top.get("content"),
            "trust": trust_tier(top), "source": top.get("source_name"),
            "atom_ids": [a["id"] for a in hits], "status": "attributed",
            "priority": 1, "flag": None}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/strength_net.py pipeline/atoms/test_strength_net.py
git commit -m "feat(net): attribute_mover — atom 귀속 판정 + 미귀속 승격"
```

---

### Task 3: `scan_movers()` + `rank_results()` — 정렬 반전(침묵 금지)

**Files:**
- Modify: `pipeline/atoms/strength_net.py`
- Test: `pipeline/atoms/test_strength_net.py`

**Interfaces:**
- Consumes: `attribute_mover` (Task 2).
- Produces:
  - `scan_movers(movers: list[dict], days: int = 3, query_fn=None) -> list[dict]`
  - `rank_results(results: list[dict]) -> list[dict]` — priority 0(미귀속) 먼저, 각 그룹 내 rate 내림차순.

- [ ] **Step 1: Write the failing test**

```python
# append to pipeline/atoms/test_strength_net.py

def test_scan_movers_never_drops_any_mover():
    movers = [
        {"name": "A", "code": "1", "sector": "s", "rate": 5.0},
        {"name": "B", "code": "2", "sector": "s", "rate": 9.0},
    ]
    results = sn.scan_movers(movers, days=3, query_fn=_fake_query({}))
    assert len(results) == len(movers)  # 침묵 금지: 하나도 누락 안 됨

def test_rank_results_unattributed_pinned_to_top():
    results = [
        {"name": "attr", "rate": 20.0, "priority": 1},
        {"name": "miss1", "rate": 6.0, "priority": 0},
        {"name": "miss2", "rate": 15.0, "priority": 0},
    ]
    ranked = sn.rank_results(results)
    assert [r["name"] for r in ranked] == ["miss2", "miss1", "attr"]
    # 미귀속이 등락률 낮아도 귀속보다 위. 미귀속 내부는 rate 내림차순.
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest pipeline/atoms/test_strength_net.py::test_rank_results_unattributed_pinned_to_top -v`
Expected: FAIL — `AttributeError: ... 'rank_results'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to pipeline/atoms/strength_net.py
def scan_movers(movers: list, days: int = 3, query_fn=None) -> list:
    """모든 강세 종목을 귀속 판정. 입력 종목은 하나도 누락하지 않는다(침묵 금지)."""
    return [attribute_mover(m, days=days, query_fn=query_fn) for m in movers]

def rank_results(results: list) -> list:
    """정렬 반전: 미귀속(priority 0)을 최상단, 각 그룹 내 rate 내림차순."""
    return sorted(results, key=lambda r: (r.get("priority", 1), -(r.get("rate") or 0)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/strength_net.py pipeline/atoms/test_strength_net.py
git commit -m "feat(net): scan_movers + rank_results — 정렬 반전, 침묵 금지"
```

---

### Task 4: `coverage_metrics()` — 촘촘함 지표

**Files:**
- Modify: `pipeline/atoms/strength_net.py`
- Test: `pipeline/atoms/test_strength_net.py`

**Interfaces:**
- Consumes: `scan_movers` 결과 리스트.
- Produces: `coverage_metrics(results: list[dict], input_count: int | None = None) -> dict`
  반환: `{"total","attributed","unattributed","coverage_rate","silent_miss"}`.

- [ ] **Step 1: Write the failing test**

```python
# append to pipeline/atoms/test_strength_net.py

def test_coverage_metrics_basic():
    results = [
        {"status": "attributed"}, {"status": "attributed"},
        {"status": "unattributed"},
    ]
    m = sn.coverage_metrics(results, input_count=3)
    assert m["total"] == 3
    assert m["attributed"] == 2
    assert m["unattributed"] == 1
    assert abs(m["coverage_rate"] - (2/3)) < 1e-9
    assert m["silent_miss"] == 0  # 입력=출력이면 침묵 누락 0

def test_coverage_metrics_detects_silent_miss():
    results = [{"status": "attributed"}]  # 입력 2개인데 결과 1개 = 누락 발생
    m = sn.coverage_metrics(results, input_count=2)
    assert m["silent_miss"] == 1  # 규칙 위반 감지
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: FAIL — `AttributeError: ... 'coverage_metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to pipeline/atoms/strength_net.py
def coverage_metrics(results: list, input_count: int = None) -> dict:
    """그물 촘촘함 지표. silent_miss>0 이면 침묵 금지 규칙 위반 신호."""
    total = len(results)
    attributed = sum(1 for r in results if r.get("status") == "attributed")
    unattributed = total - attributed
    n_in = total if input_count is None else input_count
    return {
        "total": total,
        "attributed": attributed,
        "unattributed": unattributed,
        "coverage_rate": (attributed / total) if total else 0.0,
        "silent_miss": max(0, n_in - total),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/strength_net.py pipeline/atoms/test_strength_net.py
git commit -m "feat(net): coverage_metrics — 귀속률·침묵누락 지표"
```

---

### Task 5: `scan_heatmap()` — 라이브 히트맵 통합 어댑터

**Files:**
- Modify: `pipeline/atoms/strength_net.py`
- Test: `pipeline/atoms/test_strength_net.py` (movers 추출 로직만 단위 테스트; 라이브 호출은 스모크)

**Interfaces:**
- Consumes: `sector_heatmap.build_heatmap(top_n, mode)` (scripts/, conftest가 scripts를 path에 안 넣으므로 아래 임포트 주의). 반환 dict의 실제 형태는 구현 시작 시 확인.
- Produces:
  - `movers_from_heatmap(heatmap: dict, min_rate: float = 3.0) -> list[dict]` (순수, 테스트 대상)
  - `scan_heatmap(top_n: int = 5, days: int = 3, min_rate: float = 3.0) -> dict` (impure 엔트리; `{"generated_at","results","metrics"}` 반환)

- [ ] **Step 1: 실제 히트맵 반환 형태 확인 (discovery — 코드로 하지 말고 읽기)**

`scripts/sector_heatmap.py`의 `build_heatmap()`(line 562)과 `build_heatmap_tab()`(line 368) 반환 dict 구조를 Read로 확인한다. 특히 각 종목 타일이 `name`/`code`/`change_rate`/`sector`를 어떤 키로 담는지 확정한다. `movers_from_heatmap`은 이 실제 키에 맞춰 작성한다. (아래 테스트의 fixture는 확인된 실제 키로 교체할 것.)

- [ ] **Step 2: Write the failing test (movers 추출만)**

```python
# append to pipeline/atoms/test_strength_net.py
# NOTE: 아래 fixture 키(name/code/sector/change_rate)는 Step 1에서 확인한 실제 키로 맞출 것.

def test_movers_from_heatmap_filters_by_min_rate():
    heatmap = {"tiles": [
        {"name": "강세주", "code": "1", "sector": "반도체", "change_rate": 8.0},
        {"name": "약세주", "code": "2", "sector": "반도체", "change_rate": -1.0},
        {"name": "미미주", "code": "3", "sector": "2차전지", "change_rate": 1.0},
    ]}
    movers = sn.movers_from_heatmap(heatmap, min_rate=3.0)
    names = [m["name"] for m in movers]
    assert names == ["강세주"]
    assert movers[0]["rate"] == 8.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -m pytest pipeline/atoms/test_strength_net.py::test_movers_from_heatmap_filters_by_min_rate -v`
Expected: FAIL — `AttributeError: ... 'movers_from_heatmap'`

- [ ] **Step 4: Write minimal implementation**

```python
# add to pipeline/atoms/strength_net.py — 실제 히트맵 키에 맞춰 _extract 조정
def movers_from_heatmap(heatmap: dict, min_rate: float = 3.0) -> list:
    """히트맵 dict에서 min_rate 이상 강세 종목만 mover로 추출(순수)."""
    tiles = heatmap.get("tiles") or []   # Step 1에서 실제 키 확인 후 조정
    out = []
    for t in tiles:
        rate = t.get("change_rate")      # Step 1에서 실제 키 확인 후 조정
        if rate is None or rate < min_rate:
            continue
        out.append({"name": t.get("name"), "code": t.get("code"),
                    "sector": t.get("sector"), "rate": rate})
    return out

def scan_heatmap(top_n: int = 5, days: int = 3, min_rate: float = 3.0) -> dict:
    """라이브 히트맵을 스캔해 랭킹된 미귀속 강세 목록 + 지표를 반환."""
    import sector_heatmap  # scripts/; conftest가 root를 path에 넣지만 scripts는 아님 → 필요시 sys.path 조정
    heatmap = sector_heatmap.build_heatmap(top_n=top_n)
    movers = movers_from_heatmap(heatmap, min_rate=min_rate)
    results = rank_results(scan_movers(movers, days=days))
    metrics = coverage_metrics(results, input_count=len(movers))
    return {"results": results, "metrics": metrics, "count": len(results)}
```

Note: `import sector_heatmap` 가 실패하면(scripts가 sys.path에 없음) 모듈 상단에서
`import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))`
로 scripts 경로를 추가한다(기존 `server.py`가 sector_heatmap을 import하는 방식 참고: `server.py:257`).

- [ ] **Step 5: Run test to verify it passes**

Run: `py -m pytest pipeline/atoms/test_strength_net.py -v`
Expected: PASS (all)

- [ ] **Step 6: 라이브 스모크 (수동, 장중에)**

Run: `py -c "from pipeline.atoms import strength_net as sn; import json; print(json.dumps(sn.scan_heatmap(), ensure_ascii=False, indent=2)[:1500])"`
Expected: `results`/`metrics` 가 실제 종목으로 채워짐. `metrics.silent_miss == 0` 확인. (장 마감 후엔 결과가 빌 수 있음 — 에러 없이 도는지만 확인.)

- [ ] **Step 7: Commit**

```bash
git add pipeline/atoms/strength_net.py pipeline/atoms/test_strength_net.py
git commit -m "feat(net): scan_heatmap — 라이브 히트맵 통합 어댑터"
```

---

### Task 6: `GET /api/net/unattributed` 엔드포인트

**Files:**
- Modify: `dashboard/server.py` (라우트 1개 추가; import 블록 근처 `from pipeline.atoms import strength_net`)
- Test: `tests/test_net_unattributed_api.py`

**Interfaces:**
- Consumes: `strength_net.scan_heatmap(top_n, days, min_rate)` (Task 5).
- Produces: HTTP `GET /api/net/unattributed?top_n=5&days=3&min_rate=3.0` → `scan_heatmap` 반환 JSON.

- [ ] **Step 1: Write the failing test (델리게이트 검증, 네트워크 없이)**

```python
# tests/test_net_unattributed_api.py
import pipeline.atoms.strength_net as sn

def test_scan_heatmap_shape_contract(monkeypatch):
    # scan_heatmap 이 엔드포인트가 기대하는 계약(results/metrics/count)을 지키는지 고정.
    monkeypatch.setattr(sn, "movers_from_heatmap", lambda h, min_rate=3.0: [
        {"name": "X", "code": "1", "sector": "s", "rate": 10.0}])
    import sector_heatmap  # noqa
    monkeypatch.setattr(sn, "scan_movers", lambda movers, days=3, query_fn=None: [
        {"name": "X", "rate": 10.0, "priority": 0, "status": "unattributed"}])
    # build_heatmap 은 호출되지만 movers_from_heatmap 이 대체되므로 반환값 무관
    monkeypatch.setattr("sector_heatmap.build_heatmap", lambda top_n=5, mode="regular": {})
    out = sn.scan_heatmap(top_n=5, days=3)
    assert set(out.keys()) == {"results", "metrics", "count"}
    assert out["metrics"]["silent_miss"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_net_unattributed_api.py -v`
Expected: FAIL (import 또는 계약 불일치) — 우선 실패 확인.

- [ ] **Step 3: 엔드포인트 추가**

`dashboard/server.py`의 다른 `@app.get("/api/...")` 근처(예: `/api/heatmap` 정의 부근 line 2319)에 추가:

```python
from pipeline.atoms import strength_net as _strength_net  # import 블록에 1회

@app.get("/api/net/unattributed")
def api_net_unattributed(top_n: int = 5, days: int = 3, min_rate: float = 3.0):
    """미귀속 강세 스캔 결과(랭킹 반전 + 촘촘함 지표)."""
    return _strength_net.scan_heatmap(top_n=top_n, days=days, min_rate=min_rate)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_net_unattributed_api.py -v`
Expected: PASS

- [ ] **Step 5: 라이브 스모크 (수동)**

서버 기동 후(터미널1): `GET http://localhost:<port>/api/net/unattributed` 호출 → JSON에 `results`(미귀속 상단), `metrics.coverage_rate`, `metrics.silent_miss==0` 확인.

- [ ] **Step 6: Commit**

```bash
git add dashboard/server.py tests/test_net_unattributed_api.py
git commit -m "feat(net): GET /api/net/unattributed 엔드포인트"
```

---

## Self-Review (완료)

- **Spec coverage (Phase 1 범위):** 미귀속=최우선/침묵 금지(Task 2·3), 정렬 반전(Task 3), 신뢰등급 라벨(Task 1·2), 촘촘함 지표=귀속률·미귀속놓침0(Task 4), 라이브 스캔(Task 5), 표면화(Task 6). ✅
- **Phase 1 비범위(후속 계획):** 관계그래프/예측망(Phase 2), 캐스케이드+종토방 인제스트+텔레그램+LLM추론(Phase 3), 지표 대시보드 패널+튜닝(Phase 4). 설계 문서의 나머지 섹션은 여기서 의도적으로 제외.
- **Placeholder scan:** 없음. Task 5 Step 1은 "실제 키 확인" 실행 단계(플레이스홀더 아님).
- **Type consistency:** `attribute_mover`→`scan_movers`→`rank_results`→`coverage_metrics`→`scan_heatmap` 반환 키 일관(priority/status/rate). `trust_tier` 반환 이모지 세트 고정.

## 후속 로드맵 (별도 계획으로 작성 예정)

- **Phase 2 — 관계그래프/예측망:** atoms에서 "A→B 관계 원자" 추출·저장, 사건→수혜종목 점화. 귀속률↑.
- **Phase 3 — 원인 추적 캐스케이드:** 종토방→atoms 인제스터 신규(`scripts/naver_crawl.py` 재사용), 텔레그램·공시·뉴스·LLM추론 병렬 팬아웃(Gemini/Haiku 대군, key_vault 로테이션), 신뢰등급 라벨.
- **Phase 4 — 촘촘함 대시보드:** 지표 시계열 수집·표시, 스캔 주기 크론, 정밀도 사후검증 루프.
