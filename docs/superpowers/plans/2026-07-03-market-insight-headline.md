# 시장 인사이트 헤드라인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실시간 브리핑 피드(5번째 칸) 최상단에, 오늘 지수가 왜 이렇게 움직였는지 설명하는 2~4문장 내러티브 코멘트 + 특징종목(이유 포함)을 눈에 띄게 고정 표시한다.

**Architecture:** 기존 브리핑 3층(감지/수집/종합) 인프라를 재사용한다. 지수 bars에서 시가/저점/고점/현재가를 계산(`compute_index_shape`), market_flow의 순위 데이터에서 특징종목을 뽑아 news_feed/atoms.db로 이유를 매칭(`pick_notable_movers`+`recent_atoms_for_stock`), Gemini로 내러티브 종합(`build_insight_prompt`), `market_briefing.json`에 별도 `insight` 필드로 저장, 15분마다 독립 타이머로 갱신.

**Tech Stack:** Python(dashboard/server.py 기존 패턴), 순수 JS(market.html 기존 패턴)

## Global Constraints

- 주도섹터 나열은 하지 않는다(사용자 명시적 요청 — 다른 카드에 이미 있음)
- 이유는 반드시 실제 데이터(뉴스 또는 atoms.db 원자) 근거만 — 근거 없으면 "~로 보임"으로 명시(추측 표기), 지어내지 않음
- 갱신 주기: 900초(15분) 고정 타이머 — 기존 브리핑 피드의 12분(720초) 타이머와는 독립
- Gemini 키/모델: 기존 `_briefing_keys()`, `GEMINI_TEXT_MODELS` 재사용(신규 키 불필요)
- `market_briefing.json`의 기존 `items` 배열 구조는 건드리지 않는다(순수 추가: `insight` 필드만 신설)
- bars가 2개 미만이면(장 초반) 이번 주기는 건너뛴다(재료 부족, 다음 15분 때 재시도)

---

### Task 1: 지수 흐름 계산 순수함수

**Files:**
- Modify: `dashboard/briefing_detect.py`
- Test: `tests/test_briefing_detect.py`

**Interfaces:**
- Produces: `compute_index_shape(bars: list[dict]) -> dict | None` — `bars`는
  `[{"t":"HHMMSS","price":float}]` 형식(기존 market_flow의 `curr["J_bars"]`와 동일
  shape). 2개 미만이면 `None`. 반환:
  `{"open": float, "low": float, "low_t": "HH:MM", "high": float, "high_t": "HH:MM", "current": float}`
  (`t`의 `HHMMSS`를 `HH:MM`으로 변환해서 담는다)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_detect.py`에 추가:

```python
from briefing_detect import compute_index_shape


def test_compute_index_shape_returns_none_for_insufficient_bars():
    assert compute_index_shape([]) is None
    assert compute_index_shape([{"t": "090000", "price": 100.0}]) is None


def test_compute_index_shape_finds_open_low_high_current():
    bars = [
        {"t": "090000", "price": 100.0},
        {"t": "093000", "price": 90.0},
        {"t": "103000", "price": 85.0},
        {"t": "113000", "price": 105.0},
        {"t": "120000", "price": 98.0},
    ]
    shape = compute_index_shape(bars)
    assert shape["open"] == 100.0
    assert shape["low"] == 85.0 and shape["low_t"] == "10:30"
    assert shape["high"] == 105.0 and shape["high_t"] == "11:30"
    assert shape["current"] == 98.0


def test_compute_index_shape_handles_flat_series():
    bars = [{"t": "090000", "price": 100.0}, {"t": "093000", "price": 100.0}]
    shape = compute_index_shape(bars)
    assert shape["open"] == shape["low"] == shape["high"] == shape["current"] == 100.0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_detect.py -v -k compute_index_shape`
Expected: FAIL — `ImportError: cannot import name 'compute_index_shape'`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_detect.py` 맨 끝에 추가:

```python
def compute_index_shape(bars: list[dict]) -> dict | None:
    """지수 15분봉에서 시가/저점/고점/현재가를 계산 — Gemini에게 넘길 실측 재료.
    AI가 차트를 직접 해석하게 두지 않고, 계산된 사실만 근거로 쓰게 해서 환각을 막는다."""
    if not bars or len(bars) < 2:
        return None

    def _fmt(t: str) -> str:
        t = str(t or "").zfill(6)
        return f"{t[:2]}:{t[2:4]}"

    open_bar = bars[0]
    current_bar = bars[-1]
    low_bar = min(bars, key=lambda b: b["price"])
    high_bar = max(bars, key=lambda b: b["price"])
    return {
        "open": open_bar["price"],
        "low": low_bar["price"], "low_t": _fmt(low_bar["t"]),
        "high": high_bar["price"], "high_t": _fmt(high_bar["t"]),
        "current": current_bar["price"],
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_detect.py -v`
Expected: 전체 통과(기존 7개 + 신규 3개 = 10 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_detect.py tests/test_briefing_detect.py
git commit -m "feat(insight): 지수 흐름(시가/저점/고점/현재가) 계산 순수함수"
```

---

### Task 2: 특징종목 선정 + 종목별 원자 매칭

**Files:**
- Modify: `dashboard/briefing_collect.py`
- Test: `tests/test_briefing_collect.py`

**Interfaces:**
- Produces:
  - `pick_notable_movers(rank_pop: list, rank_amt: list, news_feed_data: dict | None, n: int = 4) -> list[dict]`
    — `rank_pop`/`rank_amt`는 `[{"code","name","price","change_rate"}]` 형식(기존
    market_flow의 `curr["RANK_POP"]`/`curr["RANK_AMT"]`와 동일). 두 리스트를 종목명
    기준으로 합쳐 중복 제거 후 `abs(change_rate)` 내림차순 상위 n개. 각 항목에
    `news_feed_data`(`recent_news_headlines`가 받는 것과 동일 shape)에서 같은
    이름의 종목 뉴스 제목이 있으면 붙인다. 반환:
    `[{"name": str, "change_rate": float, "news_reason": str | None}]`
  - `recent_atoms_for_stock(db_path: str, stock_name: str, limit: int = 1) -> list[str]`
    — `recent_market_atoms`와 같은 연결관리 패턴(try/finally close), `WHERE date=?
    AND asset=?`로 특정 종목명 오늘자 원자 매칭, `content` 컬럼만 반환.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_collect.py`에 추가:

```python
from briefing_collect import pick_notable_movers, recent_atoms_for_stock


def test_pick_notable_movers_sorts_by_abs_change_rate():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    rank_amt = [{"code": "000660", "name": "SK하이닉스", "price": 200000, "change_rate": -4.7},
                {"code": "005380", "name": "현대차", "price": 200000, "change_rate": 0.5}]
    out = pick_notable_movers(rank_pop, rank_amt, None, n=4)
    assert [m["name"] for m in out] == ["삼성전자", "SK하이닉스", "현대차"]


def test_pick_notable_movers_dedups_by_name():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    rank_amt = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    out = pick_notable_movers(rank_pop, rank_amt, None, n=4)
    assert len(out) == 1


def test_pick_notable_movers_respects_limit_n():
    rank_pop = [{"code": str(i), "name": f"종목{i}", "price": 1000, "change_rate": float(i)}
                for i in range(10)]
    out = pick_notable_movers(rank_pop, [], None, n=3)
    assert len(out) == 3


def test_pick_notable_movers_attaches_matching_news_reason():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    news_feed_data = {"sectors": [{"news": [], "stocks": [
        {"code": "005930", "name": "삼성전자", "news": [{"title": "메모리 가격 반등 소식"}]}]}]}
    out = pick_notable_movers(rank_pop, [], news_feed_data, n=4)
    assert out[0]["news_reason"] == "메모리 가격 반등 소식"


def test_pick_notable_movers_no_match_leaves_reason_none():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    out = pick_notable_movers(rank_pop, [], None, n=4)
    assert out[0]["news_reason"] is None


def test_recent_atoms_for_stock_filters_by_asset_name(tmp_path):
    import sqlite3
    from datetime import datetime
    db_path = str(tmp_path / "atoms.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE atoms (
        id TEXT PRIMARY KEY, date TEXT, asset TEXT, content TEXT, created_at TEXT)""")
    today = datetime.now().strftime("%Y-%m-%d")
    conn.executemany("INSERT INTO atoms VALUES (?,?,?,?,?)", [
        ("a1", today, "삼성전자", "메모리 가격 반등", "2026-07-03T09:10:00"),
        ("a2", today, "SK하이닉스", "무관한 원자", "2026-07-03T09:11:00"),
        ("a3", "2020-01-01", "삼성전자", "옛날 원자", "2020-01-01T09:00:00"),
    ])
    conn.commit(); conn.close()

    out = recent_atoms_for_stock(db_path, "삼성전자", limit=5)
    assert out == ["메모리 가격 반등"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_collect.py -v -k "notable_movers or recent_atoms_for_stock"`
Expected: 6개 FAIL — `ImportError`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_collect.py` 맨 끝에 추가:

```python
def pick_notable_movers(rank_pop: list, rank_amt: list, news_feed_data: dict | None,
                          n: int = 4) -> list[dict]:
    """market_flow 순위 데이터에서 오늘 특징적으로 움직인 종목 상위 n개.
    news_feed_data가 있으면 같은 종목명의 뉴스 제목을 이유로 붙인다(없으면 None —
    종합층 프롬프트가 이유 없다고 명시하거나 수급 관점으로 설명하게 됨)."""
    stock_news: dict[str, str] = {}
    if news_feed_data:
        for sector in news_feed_data.get("sectors") or []:
            for stock in sector.get("stocks") or []:
                name = stock.get("name")
                news_list = stock.get("news") or []
                if name and news_list and news_list[0].get("title"):
                    stock_news[name] = news_list[0]["title"]

    seen: dict[str, dict] = {}
    for item in (rank_pop or []) + (rank_amt or []):
        name = item.get("name")
        if not name or name in seen:
            continue
        seen[name] = {
            "name": name,
            "change_rate": item.get("change_rate", 0.0),
            "news_reason": stock_news.get(name),
        }

    ranked = sorted(seen.values(), key=lambda m: abs(m["change_rate"]), reverse=True)
    return ranked[:n]


def recent_atoms_for_stock(db_path: str, stock_name: str, limit: int = 1) -> list[str]:
    """특정 종목명을 오늘자 원자(asset 컬럼)에서 매칭 — 텔레그램/리포트/유튜브에서
    그 종목을 언급한 최신 원자. recent_market_atoms와 같은 연결관리 패턴."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(db_path)
    except Exception:
        return []
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT content FROM atoms
               WHERE date = ? AND asset = ?
               ORDER BY created_at DESC LIMIT ?""",
            (today, stock_name, limit),
        ).fetchall()
        return [r["content"] for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_collect.py -v`
Expected: 전체 통과(기존 6개 + 신규 6개 = 12 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_collect.py tests/test_briefing_collect.py
git commit -m "feat(insight): 특징종목 선정(순위+뉴스매칭) + 종목별 원자 매칭"
```

---

### Task 3: 인사이트 프롬프트 빌더 + 응답 파서

**Files:**
- Modify: `dashboard/briefing_synth.py`
- Test: `tests/test_briefing_synth.py`

**Interfaces:**
- Consumes: `compute_index_shape`(Task1)의 반환 shape, `pick_notable_movers`(Task2)의
  반환 shape
- Produces:
  - `build_insight_prompt(index_shape: dict | None, movers: list[dict], market_atoms: list[str]) -> str | None`
    — `index_shape`가 `None`이면 `None`(재료 없으면 생성 안 함).
  - `parse_insight_response(text: str) -> dict | None` — `"코멘트:"`/`"특징종목:"`
    두 마커 파싱. 반환 `{"comment": str, "movers": str}`. 마커 없으면 `None`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_synth.py`에 추가:

```python
from briefing_synth import build_insight_prompt, parse_insight_response


def test_build_insight_prompt_returns_none_without_index_shape():
    assert build_insight_prompt(None, [], []) is None


def test_build_insight_prompt_includes_shape_and_movers():
    shape = {"open": 7650.0, "low": 7550.0, "low_t": "10:30",
              "high": 7890.0, "high_t": "11:50", "current": 7877.0}
    movers = [{"name": "삼성전자", "change_rate": 6.8, "news_reason": "메모리 가격 반등"},
              {"name": "SK하이닉스", "change_rate": 4.7, "news_reason": None}]
    prompt = build_insight_prompt(shape, movers, ["오늘 시장 코멘트"])
    assert "7550.0" in prompt and "10:30" in prompt
    assert "삼성전자" in prompt and "메모리 가격 반등" in prompt
    assert "SK하이닉스" in prompt and "이유 데이터 없음" in prompt
    assert "오늘 시장 코멘트" in prompt


def test_parse_insight_response_valid():
    text = "코멘트: 오늘 코스피가 급락 후 반도체 대형주 중심으로 반등했습니다.\n특징종목: 삼성전자, SK하이닉스"
    d = parse_insight_response(text)
    assert "급락 후" in d["comment"]
    assert d["movers"] == "삼성전자, SK하이닉스"


def test_parse_insight_response_missing_marker_returns_none():
    assert parse_insight_response("그냥 아무말") is None


def test_parse_insight_response_empty_returns_none():
    assert parse_insight_response("") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_synth.py -v -k insight`
Expected: 5개 FAIL — `ImportError`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_synth.py` 맨 끝에 추가:

```python
_INSIGHT_PROMPT_TEMPLATE = """너는 오늘 시장 상황을 한눈에 설명하는 헤드라인
작성자다.

철칙:
- 전문용어 최소화, 쉬운 말투
- 아래 재료에 있는 사실만 써라. 이유 데이터가 없으면 "~로 보임"이라고 명시하며
  수급 관점으로 설명해라(지어내지 마라)
- 섹터 나열은 하지 마라 — 지수 흐름과 특징종목 이유에만 집중해라

## 오늘 지수 흐름 (실측)
시가 {open}, 저점 {low}({low_t}), 고점 {high}({high_t}), 현재 {current}

## 오늘 특징종목
{movers_text}

## 오늘 시장 관련 코멘트(텔레그램/리포트)
{atoms_text}

## 출력 형식 (정확히 이렇게)
코멘트: <오늘 지수가 왜 이렇게 움직였는지 2~4문장>
특징종목: <종목명을 쉼표로 나열>
"""


def build_insight_prompt(index_shape: dict | None, movers: list[dict],
                           market_atoms: list[str]) -> str | None:
    if not index_shape:
        return None
    movers_text = "\n".join(
        f"- {m['name']} {m['change_rate']}%: {m['news_reason'] or '이유 데이터 없음'}"
        for m in movers) or "(없음)"
    atoms_text = "\n".join(f"- {c}" for c in market_atoms) or "(없음)"
    return _INSIGHT_PROMPT_TEMPLATE.format(
        open=index_shape["open"], low=index_shape["low"], low_t=index_shape["low_t"],
        high=index_shape["high"], high_t=index_shape["high_t"], current=index_shape["current"],
        movers_text=movers_text, atoms_text=atoms_text)


def parse_insight_response(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    comment, movers = None, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("코멘트:"):
            comment = line.split("코멘트:", 1)[1].strip()
        elif line.startswith("특징종목:"):
            movers = line.split("특징종목:", 1)[1].strip()
    if not comment or not movers:
        return None
    return {"comment": comment, "movers": movers}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_synth.py -v`
Expected: 전체 통과(기존 6개 + 신규 5개 = 11 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_synth.py tests/test_briefing_synth.py
git commit -m "feat(insight): 인사이트 프롬프트 빌더+응답 파서(순수함수)"
```

---

### Task 4: 저장소 — `insight` 필드 확장

**Files:**
- Modify: `dashboard/briefing_store.py`
- Test: `tests/test_briefing_store.py`

**Interfaces:**
- Produces:
  - `load_briefing`(기존 함수 수정) — 반환 dict에 `insight` 키를 항상 포함(없으면
    `None`). 기존 `items`만 있는 파일을 읽어도 안 깨짐(하위호환).
  - `set_insight(path: str, insight_obj: dict) -> dict` — `items`는 안 건드리고
    `insight` 필드만 갱신, 원자적 쓰기(기존 `append_briefing_item`과 같은
    tmp→replace 패턴), 저장된 전체 dict 반환.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_store.py`에 추가:

```python
from briefing_store import set_insight


def test_load_briefing_missing_file_includes_null_insight(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    d = load_briefing(p)
    assert d["insight"] is None


def test_load_briefing_backward_compat_with_items_only_file(tmp_path):
    """기존(이번 태스크 전) 파일은 insight 키가 아예 없다 — 읽을 때 None으로 채워져야 함."""
    p = tmp_path / "market_briefing.json"
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    p.write_text(json.dumps({"date": today, "items": [
        {"ts": "09:00", "severity": "gray", "headline": "테스트", "body": None, "kind": "raw_alert"}
    ]}), encoding="utf-8")
    d = load_briefing(str(p))
    assert d["insight"] is None
    assert len(d["items"]) == 1


def test_set_insight_writes_without_touching_items(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    append_briefing_item(p, {"ts": "09:00", "severity": "gray",
                              "headline": "속보", "body": None, "kind": "raw_alert"})
    insight_obj = {"ts": "11:50", "comment": "오늘 코스피 급락 후 반등",
                   "movers": "삼성전자, SK하이닉스"}
    d = set_insight(p, insight_obj)
    assert d["insight"] == insight_obj
    assert len(d["items"]) == 1
    with open(p, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["insight"] == insight_obj
    assert len(on_disk["items"]) == 1


def test_set_insight_resets_on_new_day_like_items(tmp_path):
    p = tmp_path / "market_briefing.json"
    stale = {"date": "2020-01-01", "insight": {"ts": "09:00", "comment": "옛날", "movers": "x"},
             "items": [{"ts": "09:00", "severity": "gray", "headline": "옛날꺼",
                        "body": None, "kind": "raw_alert"}]}
    p.write_text(json.dumps(stale), encoding="utf-8")
    d = set_insight(str(p), {"ts": "09:00", "comment": "오늘", "movers": "y"})
    assert d["insight"]["comment"] == "오늘"
    assert d["items"] == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_store.py -v -k insight`
Expected: FAIL — `ImportError: cannot import name 'set_insight'` (첫 2개는
`load_briefing`이 아직 `insight` 키를 안 넣으므로 `KeyError`)

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_store.py`의 `load_briefing` 함수를 다음으로 교체:

```python
def load_briefing(path: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today:
            data.setdefault("insight", None)
            return data
    except Exception:
        pass
    return {"date": today, "items": [], "insight": None}
```

같은 파일 맨 끝에 추가:

```python
def set_insight(path: str, insight_obj: dict) -> dict:
    """items는 그대로 두고 insight 필드만 갱신. append_briefing_item과 같은
    원자적 쓰기 패턴(tmp→os.replace)."""
    data = load_briefing(path)
    data["insight"] = insight_obj
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass
    return data
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_store.py -v`
Expected: 전체 통과(기존 4개 + 신규 4개 = 8 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_store.py tests/test_briefing_store.py
git commit -m "feat(insight): 저장소에 insight 필드 추가(하위호환+원자적쓰기)"
```

---

### Task 5: 백그라운드 갱신 — server.py 연결

**Files:**
- Modify: `dashboard/server.py`
- Test: `tests/test_briefing_api.py`

**Interfaces:**
- Consumes: `briefing_detect.compute_index_shape`(Task1),
  `briefing_collect.pick_notable_movers`/`recent_atoms_for_stock`(Task2),
  `briefing_synth.build_insight_prompt`/`parse_insight_response`(Task3),
  `briefing_store.set_insight`(Task4), 기존 `_briefing_keys`, `GEMINI_TEXT_MODELS`,
  `_gemini_text`, `_prewarm_cache`, `_NEWS_FEED`, `BRIEFING_PATH`
- Produces: `/api/market_briefing` 응답에 `insight` 필드가 자연히 포함됨(저장
  구조에 추가됐으므로 API 코드 자체는 안 건드림)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_api.py`에 추가:

```python
def test_api_market_briefing_includes_insight_field(tmp_path, monkeypatch):
    p = tmp_path / "market_briefing.json"
    from datetime import datetime
    p.write_text(json.dumps({"date": datetime.now().strftime("%Y-%m-%d"),
                              "items": [], "insight": {"ts": "11:50",
                              "comment": "테스트 코멘트", "movers": "삼성전자"}}),
                 encoding="utf-8")
    monkeypatch.setattr(server, "BRIEFING_PATH", str(p))
    c = TestClient(server.app)
    r = c.get("/api/market_briefing").json()
    assert r["insight"]["comment"] == "테스트 코멘트"


def test_insight_run_synthesis_calls_gemini_with_built_prompt(tmp_path, monkeypatch):
    p = tmp_path / "market_briefing.json"
    from datetime import datetime
    p.write_text(json.dumps({"date": datetime.now().strftime("%Y-%m-%d"),
                              "items": [], "insight": None}), encoding="utf-8")
    monkeypatch.setattr(server, "BRIEFING_PATH", str(p))
    monkeypatch.setattr(server, "_NEWS_FEED", {"data": None})

    fake_curr = {
        "J_bars": [{"t": "090000", "price": 100.0}, {"t": "093000", "price": 90.0}],
        "RANK_POP": [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}],
        "RANK_AMT": [],
    }

    captured = {}
    def _fake_gemini_text(prompt, keys=None, models=None):
        captured["prompt"] = prompt
        return {"ok": True, "analysis": "코멘트: 테스트 설명입니다.\n특징종목: 삼성전자"}
    monkeypatch.setattr(server, "_gemini_text", _fake_gemini_text)

    server._insight_run_synthesis(fake_curr)

    assert "prompt" in captured, "Gemini가 호출되지 않음"
    assert "100.0" in captured["prompt"] and "삼성전자" in captured["prompt"]
    d = server._briefing_load(str(p))
    assert d["insight"]["comment"] == "테스트 설명입니다."


def test_insight_run_synthesis_skips_when_bars_insufficient(tmp_path, monkeypatch):
    p = tmp_path / "market_briefing.json"
    from datetime import datetime
    p.write_text(json.dumps({"date": datetime.now().strftime("%Y-%m-%d"),
                              "items": [], "insight": None}), encoding="utf-8")
    monkeypatch.setattr(server, "BRIEFING_PATH", str(p))
    monkeypatch.setattr(server, "_NEWS_FEED", {"data": None})

    called = {"n": 0}
    def _fake_gemini_text(prompt, keys=None, models=None):
        called["n"] += 1
        return {"ok": True, "analysis": ""}
    monkeypatch.setattr(server, "_gemini_text", _fake_gemini_text)

    server._insight_run_synthesis({"J_bars": [], "RANK_POP": [], "RANK_AMT": []})

    assert called["n"] == 0, "bars 부족한데 Gemini가 호출됨"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_api.py -v -k insight`
Expected: FAIL — `AttributeError: module 'server' has no attribute '_insight_run_synthesis'`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/server.py`에서 `from briefing_synth import build_briefing_prompt as
_briefing_build_prompt, parse_briefing_response as _briefing_parse` 줄 바로 아래
(임포트 블록)에 추가:

```python
from briefing_detect import compute_index_shape as _compute_index_shape
from briefing_collect import pick_notable_movers as _pick_notable_movers, recent_atoms_for_stock as _recent_atoms_for_stock
from briefing_synth import build_insight_prompt as _build_insight_prompt, parse_insight_response as _parse_insight_response
from briefing_store import set_insight as _briefing_set_insight
```

`_briefing_last_ai_call = {"ts": 0.0}` 줄 바로 아래에 추가:

```python
_insight_last_run = {"ts": 0.0}   # 마지막 인사이트 갱신 시각(15분 독립 타이머)
```

`def api_market_briefing():` 함수 바로 위(파일 맨 끝)에 추가:

```python
def _insight_run_synthesis(curr: dict) -> None:
    """지수 흐름+특징종목 종합 — 15분 독립 타이머로 _poll_briefing에서 호출."""
    try:
        bars = curr.get("J_bars") or curr.get("Q_bars") or []
        shape = _compute_index_shape(bars)
        if not shape:
            return
        news_data = _NEWS_FEED.get("data")
        movers = _pick_notable_movers(curr.get("RANK_POP") or [], curr.get("RANK_AMT") or [],
                                       news_data, n=4)
        atoms_db_path = os.path.join(ROOT, "pipeline", "atoms", "atoms.db")
        for m in movers:
            if not m.get("news_reason"):
                found = _recent_atoms_for_stock(atoms_db_path, m["name"], limit=1)
                if found:
                    m["news_reason"] = found[0]
        market_atoms = _briefing_atoms(atoms_db_path, limit=5)
        prompt = _build_insight_prompt(shape, movers, market_atoms)
        if not prompt:
            return
        res = _gemini_text(prompt, keys=_briefing_keys(), models=GEMINI_TEXT_MODELS)
        if not res.get("ok"):
            return
        parsed = _parse_insight_response(res.get("analysis", ""))
        if not parsed:
            return
        _briefing_set_insight(BRIEFING_PATH, {
            "ts": datetime.now().strftime("%H:%M"),
            "comment": parsed["comment"], "movers": parsed["movers"]})
    except Exception:
        pass
```

`_poll_briefing()` 함수 안, `elif time.time() - _last_fixed_synth >= 720:` 블록 바로
다음 줄(`_briefing_run_synthesis([])` 다음)에 추가:

```python
                if time.time() - _insight_last_run["ts"] >= 900:
                    _insight_last_run["ts"] = time.time()
                    _insight_run_synthesis(curr)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_api.py -v`
Expected: 전체 통과(기존 6개 + 신규 3개 = 9 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/server.py tests/test_briefing_api.py
git commit -m "feat(insight): 15분 독립타이머로 인사이트 종합 실행 + _poll_briefing 연결"
```

---

### Task 6: 프론트엔드 — 최상단 고정 인사이트 블록

**Files:**
- Modify: `dashboard/market.html`

**Interfaces:**
- Consumes: `GET /api/market_briefing`의 `insight` 필드(Task5)
- Produces: 없음(최종 UI 태스크)

- [ ] **Step 1: CSS 추가**

`dashboard/market.html`의 `.briefing-feed{...}` 규칙 바로 위에 추가:

```css
.mkt-insight{padding:10px 12px;margin-bottom:8px;border-radius:6px;
  background:linear-gradient(135deg,#2a2410,#1a1a1a);border:1px solid #d4af37;}
.mkt-insight .mi-comment{font-size:13px;font-weight:700;color:#f0d97a;line-height:1.5;margin-bottom:6px;}
.mkt-insight .mi-movers{font-size:11px;color:#ccc;}
```

- [ ] **Step 2: `_briefingItems` 변수 옆에 `_marketInsight` 상태 변수 추가**

`dashboard/market.html`에서 `let _briefingItems=[];` 줄 바로 아래에 추가:

```javascript
let _marketInsight=null;
```

- [ ] **Step 3: `loadMarketBriefing()`가 insight도 함께 저장하도록 수정**

`dashboard/market.html`의 `loadMarketBriefing` 함수 안,
`if(Array.isArray(d.items)){` 줄을 다음으로 교체:

```javascript
    if(Array.isArray(d.items)){
      _briefingItems=d.items;
      _marketInsight=d.insight||null;
```

(기존에 `_briefingItems=d.items;` 한 줄이었던 것을 위와 같이 `_marketInsight` 대입
줄까지 포함해서 2줄로 만든다 — `if` 블록의 닫는 중괄호는 그대로 유지)

- [ ] **Step 4: briefing 렌더 분기에 인사이트 블록 삽입**

`dashboard/market.html`에서 `if(code==="briefing"){` 분기 안,
`const items=_briefingItems||[];` 줄 바로 위에 추가:

```javascript
        const insightHtml=_marketInsight
          ?`<div class="mkt-insight">
              <div class="mi-comment">${esc(_marketInsight.comment)}</div>
              <div class="mi-movers">📌 ${esc(_marketInsight.movers)}</div>
            </div>`
          :"";
```

같은 분기 안, `return \`<div class="mkt-card" style="flex:1;min-width:0;">` 로
시작하는 반환문에서 `<div style="font-size:13px;color:#ccc;margin-bottom:6px;">📡
실시간 브리핑</div>` 줄 바로 아래에 `${insightHtml}`를 삽입:

```javascript
        return `<div class="mkt-card" style="flex:1;min-width:0;">
          <div style="font-size:13px;color:#ccc;margin-bottom:6px;">📡 실시간 브리핑</div>
          ${insightHtml}
          <div class="briefing-feed">${rows}</div>
        </div>`;
```

- [ ] **Step 5: 브라우저에서 직접 확인**

로컬 서버(`python.exe dashboard/server.py`) 실행 후 `http://127.0.0.1:8090/market`
접속. 개발자도구 콘솔에서 다음을 실행해 인사이트 블록이 실제로 렌더링되는지 확인
(초기엔 `insight`가 `null`이라 블록이 안 보이는 게 정상 — 아래처럼 강제로
`_marketInsight`를 채우고 다시 그려서 렌더 로직 자체를 검증):

```javascript
_marketInsight = {ts:"12:00", comment:"오늘 코스피가 급락 후 반도체 대형주 중심으로 반등한 모습입니다.", movers:"삼성전자, SK하이닉스"};
loadMarketFlow();
```

몇 초 뒤:
```javascript
document.querySelector(".mkt-insight .mi-comment")?.textContent
document.querySelector(".mkt-insight .mi-movers")?.textContent
```

Expected: 위 두 값이 각각 방금 넣은 comment/movers 문자열과 일치. (fablize
검증-그라운딩 원칙: 렌더 산출물은 실제 브라우저 구동 확인 없이 완료 처리 금지 —
이 스텝을 건너뛰지 말 것)

- [ ] **Step 6: 커밋**

```bash
git add dashboard/market.html
git commit -m "feat(insight): 브리핑 피드 최상단 고정 인사이트 블록 렌더링"
```
