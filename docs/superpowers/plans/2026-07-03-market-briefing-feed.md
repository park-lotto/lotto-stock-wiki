# 실시간 시장 브리핑 피드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 딸깍 대시보드(`market.html`) 최상단에 5번째 칸으로 실시간 시장 브리핑 피드를 추가한다 — 지수/수급 임계치 감지 + 기존 뉴스/원자 수집 + Gemini 종합으로 일반인도 이해할 수 있는 짧은 브리핑 카드를 시간순으로 쌓는다.

**Architecture:** `dashboard/server.py`에 독립된 백그라운드 스레드(`_poll_briefing`, 30초 주기, 기존 `_poll_flow` 패턴과 동일)를 추가한다. 이 스레드는 (1) `_prewarm_cache["market_flow"]`를 읽어 임계치 감지, (2) `news_feed`/`atoms.db`에서 최근 항목 수집, (3) 감지·수집 결과를 Gemini로 종합해 브리핑 카드 생성, (4) `output/market_briefing.json`에 일별 append 저장한다. 새 API `/api/market_briefing`가 오늘자 항목을 서빙하고, `market.html`은 기존 `renderMarketFlow`의 카드 배열에 `"briefing"`을 추가해 5번째 칸을 그린다.

**Tech Stack:** Python(FastAPI, 기존 `dashboard/server.py`), SQLite(`pipeline/atoms/atoms.db`), Gemini(`_gemini_text`), 순수 JS(기존 `market.html` 패턴)

## Global Constraints

- 감지층 임계치(설계 확정값): 지수 등락률 직전 체크 대비 **1%p 이상** 변동 / 외국인·기관 순매수 부호 전환 / 프로그램 순매수 직전 체크 대비 **500억원(=50000, 백만원 단위) 이상** 변동
- 서버 재시작 직후 첫 비교 사이클은 기준선이 없으므로 **알림을 발생시키지 않고 값만 저장**(오탐 방지)
- 종합층 AI 호출 쿨다운: 직전 호출로부터 **60초 이내면 스킵**
- 종합층 고정 주기: **12분**(720초)마다 1회 + 감지층 이벤트 발생 시 즉시 추가 1회(쿨다운 공유)
- 저장 리셋: 그날 첫 폴링 사이클에서 저장된 `date`가 오늘과 다르면 `items`를 비움(자정 고정 아님, 기존 `_flow_day` 규칙과 동일)
- 하루 최대 저장 항목 수: **200개** 캡
- Gemini 모델: 기존 `GEMINI_TEXT_MODELS`(`["gemini-3-flash-preview", "gemini-2.5-flash"]`), 키는 기존 `_summary_keys()` 재사용 — 신규 API 키 불필요
- 새로 쓸 게 없으면(감지 이벤트도 없고 수집된 뉴스/원자도 없으면) 종합층은 카드를 생성하지 않는다

---

### Task 1: 임계치 감지 순수함수

**Files:**
- Create: `dashboard/briefing_detect.py`
- Test: `tests/test_briefing_detect.py`

**Interfaces:**
- Produces: `detect_alerts(prev: dict | None, curr: dict) -> list[dict]` — `curr`는
  `{"J_price": {"price":..,"change_rate":..}, "Q_price": {...}, "J_investor": {"외인":..,"기관":..,"개인":..}, "Q_investor": {...}, "J_prog": {"차익":..,"비차익":..,"합계":..}, "Q_prog": {...}}`
  형태(기존 `_prewarm_cache["market_flow"]["data"]`와 동일 shape). `prev`가 `None`이면
  빈 리스트 반환(재시작 직후 오탐 방지). 반환값 각 항목:
  `{"ts": "HH:MM", "metric": str, "from": float, "to": float, "label": str}`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_detect.py` 새로 생성:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_detect import detect_alerts


def _mk(j_rate=0.0, q_rate=0.0, j_foreign=0, j_org=0, j_prog=0):
    return {
        "J_price": {"price": 7500, "change_rate": j_rate},
        "Q_price": {"price": 830, "change_rate": q_rate},
        "J_investor": {"외인": j_foreign, "기관": j_org, "개인": 0},
        "Q_investor": {"외인": 0, "기관": 0, "개인": 0},
        "J_prog": {"차익": 0, "비차익": 0, "합계": j_prog},
        "Q_prog": {"차익": 0, "비차익": 0, "합계": 0},
    }


def test_no_baseline_returns_empty():
    """서버 재시작 직후(prev=None)는 알림을 만들지 않는다 — 오탐 방지."""
    assert detect_alerts(None, _mk(j_rate=5.0)) == []


def test_index_change_over_1pp_triggers_alert():
    prev = _mk(j_rate=0.5)
    curr = _mk(j_rate=1.8)   # 1.3%p 변동 > 1%p 임계치
    alerts = detect_alerts(prev, curr)
    assert len(alerts) == 1
    assert alerts[0]["metric"] == "J_change_rate"
    assert alerts[0]["from"] == 0.5 and alerts[0]["to"] == 1.8


def test_index_change_under_1pp_no_alert():
    prev = _mk(j_rate=0.5)
    curr = _mk(j_rate=1.2)   # 0.7%p 변동 < 1%p
    assert detect_alerts(prev, curr) == []


def test_foreign_sign_flip_triggers_alert():
    prev = _mk(j_foreign=-500)
    curr = _mk(j_foreign=300)   # 매도(-)→매수(+) 전환
    alerts = detect_alerts(prev, curr)
    assert any(a["metric"] == "J_investor_외인" for a in alerts)


def test_foreign_same_sign_no_alert():
    prev = _mk(j_foreign=-500)
    curr = _mk(j_foreign=-900)   # 계속 매도, 부호 안 바뀜
    assert not any(a["metric"] == "J_investor_외인" for a in [
        x for x in detect_alerts(prev, curr) if x["metric"] == "J_investor_외인"])


def test_program_trade_over_500eok_triggers_alert():
    prev = _mk(j_prog=0)
    curr = _mk(j_prog=60000)   # 600억(백만원 단위 60000) 변동 > 500억
    alerts = detect_alerts(prev, curr)
    assert any(a["metric"] == "J_prog_합계" for a in alerts)


def test_program_trade_under_500eok_no_alert():
    prev = _mk(j_prog=0)
    curr = _mk(j_prog=30000)   # 300억 < 500억
    assert not any(a["metric"] == "J_prog_합계" for a in detect_alerts(prev, curr))
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_detect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'briefing_detect'`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_detect.py` 새로 생성:

```python
"""market_flow 임계치 감지 — AI 호출 없이 숫자 비교만으로 속보 이벤트 생성.
서버 재시작 직후(prev=None)는 기준선이 없어 오탐이 나므로 값만 저장하고 알림은 안 낸다."""
from datetime import datetime

_INDEX_THRESHOLD_PP = 1.0        # 지수 등락률 %p
_PROG_THRESHOLD = 50000          # 프로그램 순매수 변동(백만원 단위, 500억)

_LABELS = {
    "J_change_rate": "코스피 등락률",
    "Q_change_rate": "코스닥 등락률",
    "J_investor_외인": "코스피 외국인 수급",
    "J_investor_기관": "코스피 기관 수급",
    "Q_investor_외인": "코스닥 외국인 수급",
    "Q_investor_기관": "코스닥 기관 수급",
    "J_prog_합계": "코스피 프로그램 순매수",
    "Q_prog_합계": "코스닥 프로그램 순매수",
}


def detect_alerts(prev: dict | None, curr: dict) -> list[dict]:
    if prev is None:
        return []
    ts = datetime.now().strftime("%H:%M")
    out = []

    for mkt in ("J", "Q"):
        p_rate = (prev.get(f"{mkt}_price") or {}).get("change_rate")
        c_rate = (curr.get(f"{mkt}_price") or {}).get("change_rate")
        if p_rate is not None and c_rate is not None and abs(c_rate - p_rate) >= _INDEX_THRESHOLD_PP:
            metric = f"{mkt}_change_rate"
            out.append({"ts": ts, "metric": metric, "from": p_rate, "to": c_rate,
                        "label": _LABELS[metric]})

        for who in ("외인", "기관"):
            p_v = (prev.get(f"{mkt}_investor") or {}).get(who)
            c_v = (curr.get(f"{mkt}_investor") or {}).get(who)
            if p_v is not None and c_v is not None and p_v != 0 and c_v != 0:
                if (p_v > 0) != (c_v > 0):
                    metric = f"{mkt}_investor_{who}"
                    out.append({"ts": ts, "metric": metric, "from": p_v, "to": c_v,
                                "label": _LABELS[metric]})

        p_prog = (prev.get(f"{mkt}_prog") or {}).get("합계")
        c_prog = (curr.get(f"{mkt}_prog") or {}).get("합계")
        if p_prog is not None and c_prog is not None and abs(c_prog - p_prog) >= _PROG_THRESHOLD:
            metric = f"{mkt}_prog_합계"
            out.append({"ts": ts, "metric": metric, "from": p_prog, "to": c_prog,
                        "label": _LABELS[metric]})

    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_detect.py -v`
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_detect.py tests/test_briefing_detect.py
git commit -m "feat(briefing): market_flow 임계치 감지 순수함수"
```

---

### Task 2: 저장소 — 일별 브리핑 피드 로드/저장/리셋

**Files:**
- Create: `dashboard/briefing_store.py`
- Test: `tests/test_briefing_store.py`

**Interfaces:**
- Produces:
  - `load_briefing(path: str) -> dict` — `{"date": "YYYY-MM-DD", "items": [...]}` 반환.
    파일 없으면 오늘 날짜의 빈 items.
  - `append_briefing_item(path: str, item: dict) -> dict` — 오늘 날짜가 아니면(날짜가
    바뀌었으면) items를 비우고 새로 시작한 뒤 item을 맨 앞에 추가, 200개 캡, 디스크에
    원자적 저장(tmp파일→os.replace), 저장된 전체 dict 반환.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_store.py` 새로 생성:

```python
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_store import load_briefing, append_briefing_item


def test_load_briefing_missing_file_returns_empty_today(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    from datetime import datetime
    d = load_briefing(p)
    assert d["date"] == datetime.now().strftime("%Y-%m-%d")
    assert d["items"] == []


def test_append_briefing_item_writes_and_prepends(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    item1 = {"ts": "09:00", "severity": "gray", "headline": "첫 항목", "body": None, "kind": "raw_alert"}
    item2 = {"ts": "09:05", "severity": "red", "headline": "두번째", "body": "설명", "kind": "ai_brief"}
    append_briefing_item(p, item1)
    d = append_briefing_item(p, item2)
    assert [x["headline"] for x in d["items"]] == ["두번째", "첫 항목"]
    with open(p, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert [x["headline"] for x in on_disk["items"]] == ["두번째", "첫 항목"]


def test_append_briefing_item_caps_at_200(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    for i in range(205):
        d = append_briefing_item(p, {"ts": "09:00", "severity": "gray",
                                      "headline": f"item{i}", "body": None, "kind": "raw_alert"})
    assert len(d["items"]) == 200
    assert d["items"][0]["headline"] == "item204"   # 최신이 맨 앞


def test_append_briefing_item_resets_on_new_day(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    stale = {"date": "2020-01-01", "items": [
        {"ts": "09:00", "severity": "gray", "headline": "옛날꺼", "body": None, "kind": "raw_alert"}]}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(stale, f, ensure_ascii=False)
    d = append_briefing_item(p, {"ts": "09:00", "severity": "gray",
                                  "headline": "오늘꺼", "body": None, "kind": "raw_alert"})
    assert len(d["items"]) == 1
    assert d["items"][0]["headline"] == "오늘꺼"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'briefing_store'`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_store.py` 새로 생성:

```python
"""브리핑 피드 일별 저장소 — output/flow_history.json과 같은 원자적 append 패턴.
리셋은 자정이 아니라 '날짜가 바뀐 뒤 첫 호출 시점'에 일어난다(_flow_day 규칙과 동일)."""
import json
import os
from datetime import datetime

_MAX_ITEMS = 200


def load_briefing(path: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today:
            return data
    except Exception:
        pass
    return {"date": today, "items": []}


def append_briefing_item(path: str, item: dict) -> dict:
    data = load_briefing(path)
    data["items"] = [item] + data["items"]
    data["items"] = data["items"][:_MAX_ITEMS]
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
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_store.py tests/test_briefing_store.py
git commit -m "feat(briefing): 일별 브리핑 피드 저장소(로드/append/200캡/날짜리셋)"
```

---

### Task 3: 수집층 — 최근 뉴스/원자 수집 헬퍼

**Files:**
- Create: `dashboard/briefing_collect.py`
- Test: `tests/test_briefing_collect.py`

**Interfaces:**
- Consumes: `pipeline.atoms.db.get_conn()` (기존, Task1의 원자추출 재설계 세션에서
  확인된 스키마: `atoms` 테이블에 `date, signal, asset_level, content, source_name,
  created_at` 컬럼 존재)
- Produces:
  - `recent_news_headlines(news_feed_data: dict | None, limit: int = 5) -> list[str]` —
    `news_feed_data`(`_NEWS_FEED["data"]`와 동일 shape: `{"sectors":[{"news":[{"title":...}],
    "stocks":[{"news":[{"title":...}]}]}]}`)에서 섹터뉴스+종목뉴스 제목만 평탄화해
    최대 `limit`개 반환. `None`이면 빈 리스트.
  - `recent_market_atoms(db_path: str, limit: int = 5) -> list[str]` — 오늘 날짜,
    `signal IN ('bullish','bearish','catalyst','risk')` 또는 `asset_level='market'`인
    원자를 `created_at DESC`로 최대 `limit`개, `content` 컬럼만 리스트로 반환.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_collect.py` 새로 생성:

```python
import sys, sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_collect import recent_news_headlines, recent_market_atoms


def test_recent_news_headlines_none_returns_empty():
    assert recent_news_headlines(None) == []


def test_recent_news_headlines_flattens_sector_and_stock_news():
    data = {"sectors": [
        {"news": [{"title": "반도체 훈풍"}, {"title": "메모리 가격 상승"}],
         "stocks": [{"news": [{"title": "삼성전자 목표가 상향"}]}]},
        {"news": [{"title": "2차전지 조정"}], "stocks": []},
    ]}
    out = recent_news_headlines(data, limit=10)
    assert "반도체 훈풍" in out
    assert "삼성전자 목표가 상향" in out
    assert "2차전지 조정" in out


def test_recent_news_headlines_respects_limit():
    data = {"sectors": [{"news": [{"title": f"뉴스{i}"} for i in range(20)], "stocks": []}]}
    assert len(recent_news_headlines(data, limit=3)) == 3


def _mk_atoms_db(tmp_path):
    db_path = str(tmp_path / "atoms.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE atoms (
        id TEXT PRIMARY KEY, date TEXT, signal TEXT, asset_level TEXT,
        content TEXT, source_name TEXT, created_at TEXT)""")
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [
        ("a1", today, "bullish", "sector", "반도체 강세 지속", "src", "2026-07-03T09:10:00"),
        ("a2", today, "neutral", "stock", "무관한 잡담", "src", "2026-07-03T09:11:00"),
        ("a3", today, "risk", "market", "코스닥 급락 위험", "src", "2026-07-03T09:12:00"),
        ("a4", "2020-01-01", "bullish", "market", "옛날 원자", "src", "2020-01-01T09:00:00"),
    ]
    conn.executemany("INSERT INTO atoms VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return db_path


def test_recent_market_atoms_filters_signal_and_date(tmp_path):
    db_path = _mk_atoms_db(tmp_path)
    out = recent_market_atoms(db_path, limit=10)
    assert "반도체 강세 지속" in out
    assert "코스닥 급락 위험" in out
    assert "무관한 잡담" not in out
    assert "옛날 원자" not in out


def test_recent_market_atoms_respects_limit(tmp_path):
    db_path = _mk_atoms_db(tmp_path)
    out = recent_market_atoms(db_path, limit=1)
    assert len(out) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_collect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'briefing_collect'`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_collect.py` 새로 생성:

```python
"""브리핑 종합층 입력 재료 수집 — 기존 news_feed/atoms.db를 읽기만, 신규 크롤링 없음."""
import sqlite3
from datetime import datetime


def recent_news_headlines(news_feed_data: dict | None, limit: int = 5) -> list[str]:
    if not news_feed_data:
        return []
    out = []
    for sector in news_feed_data.get("sectors") or []:
        for n in sector.get("news") or []:
            if n.get("title"):
                out.append(n["title"])
        for stock in sector.get("stocks") or []:
            for n in stock.get("news") or []:
                if n.get("title"):
                    out.append(n["title"])
    return out[:limit]


def recent_market_atoms(db_path: str, limit: int = 5) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT content FROM atoms
               WHERE date = ? AND (signal IN ('bullish','bearish','catalyst','risk')
                                    OR asset_level = 'market')
               ORDER BY created_at DESC LIMIT ?""",
            (today, limit),
        ).fetchall()
        conn.close()
        return [r["content"] for r in rows]
    except Exception:
        return []
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_collect.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_collect.py tests/test_briefing_collect.py
git commit -m "feat(briefing): news_feed/atoms.db 수집 헬퍼(신규 크롤링 없음, 읽기전용)"
```

---

### Task 4: 종합층 — Gemini 프롬프트 빌더 + 응답 파서

**Files:**
- Create: `dashboard/briefing_synth.py`
- Test: `tests/test_briefing_synth.py`

**Interfaces:**
- Consumes: 없음(순수 함수) — Task5에서 `_gemini_text`와 함께 조립
- Produces:
  - `build_briefing_prompt(alerts: list[dict], headlines: list[str], atoms_content: list[str], prior_headlines: list[str]) -> str | None`
    — 넷 다 비어있으면 `None`(쓸 게 없으면 프롬프트 자체를 안 만듦). 아니면 완성된
    프롬프트 문자열 반환.
  - `parse_briefing_response(text: str) -> dict | None` — Gemini가 `헤드라인: ...\n본문: ...`
    형식으로 답하도록 프롬프트에서 강제(JSON 대신 단순 텍스트 파싱 — 실패 케이스를
    최소화하기 위해 구조를 최대한 단순하게 유지). 파싱 실패하거나 "브리핑 없음"이면
    `None`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_synth.py` 새로 생성:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_synth import build_briefing_prompt, parse_briefing_response


def test_build_prompt_returns_none_when_nothing_to_report():
    assert build_briefing_prompt([], [], [], []) is None


def test_build_prompt_includes_alert_and_headline():
    alerts = [{"ts": "09:47", "metric": "J_change_rate", "from": -0.5, "to": -1.8,
               "label": "코스피 등락률"}]
    prompt = build_briefing_prompt(alerts, ["반도체 훈풍"], ["코스닥 급락 위험"], [])
    assert "코스피 등락률" in prompt
    assert "반도체 훈풍" in prompt
    assert "코스닥 급락 위험" in prompt


def test_build_prompt_includes_prior_headlines_for_context():
    prompt = build_briefing_prompt(
        [{"ts": "09:47", "metric": "x", "from": 0, "to": 1, "label": "y"}],
        [], [], ["직전 브리핑: 외국인 매도 전환"])
    assert "직전 브리핑: 외국인 매도 전환" in prompt


def test_parse_valid_response():
    text = "헤드라인: 코스닥 급락 전환\n본문: 코스닥이 오전 내내 완만하다가 갑자기 -4%대로 밀렸습니다."
    d = parse_briefing_response(text)
    assert d["headline"] == "코스닥 급락 전환"
    assert "완만하다가" in d["body"]


def test_parse_no_briefing_marker_returns_none():
    assert parse_briefing_response("브리핑 없음") is None


def test_parse_malformed_response_returns_none():
    assert parse_briefing_response("그냥 아무말") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_synth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'briefing_synth'`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/briefing_synth.py` 새로 생성:

```python
"""브리핑 종합층 — Gemini 프롬프트 조립 + 응답 파싱. 실제 API 호출은 Task5에서
기존 _gemini_text()로 수행(이 파일은 순수 함수만, API 의존성 없음)."""

_PROMPT_TEMPLATE = """너는 일반 투자자 구독자에게 지금 시장 상황을 쉽게 설명하는
브리핑 작성자다. 아래 재료를 보고, 지금 알려줄 만한 게 있으면 딱 1개만 써라.

철칙:
- 전문용어 최소화, 쉬운 말투("외국인이 오전 내내 팔다가 정오부터 매수로 돌아섬" 처럼)
- 아래 재료에 있는 사실만 써라. 추측이면 "~로 보임"이라고 명시해라.
- 알려줄 만큼 중요한 게 없으면 정확히 "브리핑 없음"이라고만 답해라.
- 있으면 정확히 이 형식으로: "헤드라인: <15자 내외 한 줄>\\n본문: <1~2문장>"

## 지수/수급 변동
{alerts_text}

## 최근 뉴스 제목
{headlines_text}

## 최근 시장 코멘트(텔레그램/리포트)
{atoms_text}

## 직전 브리핑(같은 얘기 반복하지 마라)
{prior_text}
"""


def build_briefing_prompt(alerts: list[dict], headlines: list[str],
                            atoms_content: list[str], prior_headlines: list[str]) -> str | None:
    if not alerts and not headlines and not atoms_content:
        return None
    alerts_text = "\n".join(
        f"- {a['label']}: {a['from']} → {a['to']} ({a['ts']})" for a in alerts) or "(없음)"
    headlines_text = "\n".join(f"- {h}" for h in headlines) or "(없음)"
    atoms_text = "\n".join(f"- {c}" for c in atoms_content) or "(없음)"
    prior_text = "\n".join(f"- {p}" for p in prior_headlines) or "(없음)"
    return _PROMPT_TEMPLATE.format(
        alerts_text=alerts_text, headlines_text=headlines_text,
        atoms_text=atoms_text, prior_text=prior_text)


def parse_briefing_response(text: str) -> dict | None:
    text = (text or "").strip()
    if not text or "브리핑 없음" in text:
        return None
    headline, body = None, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("헤드라인:"):
            headline = line.split("헤드라인:", 1)[1].strip()
        elif line.startswith("본문:"):
            body = line.split("본문:", 1)[1].strip()
    if not headline or not body:
        return None
    return {"headline": headline, "body": body}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_synth.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add dashboard/briefing_synth.py tests/test_briefing_synth.py
git commit -m "feat(briefing): Gemini 프롬프트 빌더+응답 파서(순수함수, API의존성 없음)"
```

---

### Task 5: 백그라운드 루프 + API 엔드포인트

**Files:**
- Modify: `dashboard/server.py`
- Test: `tests/test_briefing_api.py`

**Interfaces:**
- Consumes: `briefing_detect.detect_alerts`(Task1), `briefing_store.load_briefing`/
  `append_briefing_item`(Task2), `briefing_collect.recent_news_headlines`/
  `recent_market_atoms`(Task3), `briefing_synth.build_briefing_prompt`/
  `parse_briefing_response`(Task4), 기존 `_gemini_text`, `_summary_keys`,
  `GEMINI_TEXT_MODELS`, `_prewarm_cache`, `_NEWS_FEED`
- Produces: `GET /api/market_briefing` — 오늘자 `{"date":..., "items":[...]}` 반환

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_briefing_api.py` 새로 생성:

```python
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

import server
from fastapi.testclient import TestClient


def test_api_market_briefing_returns_stored_items(tmp_path, monkeypatch):
    p = tmp_path / "market_briefing.json"
    from datetime import datetime
    p.write_text(json.dumps({"date": datetime.now().strftime("%Y-%m-%d"),
                              "items": [{"ts": "09:47", "severity": "red",
                                         "headline": "테스트", "body": "본문",
                                         "kind": "ai_brief"}]}), encoding="utf-8")
    monkeypatch.setattr(server, "BRIEFING_PATH", str(p))

    c = TestClient(server.app)
    r = c.get("/api/market_briefing").json()
    assert r["items"][0]["headline"] == "테스트"


def test_api_market_briefing_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "BRIEFING_PATH", str(tmp_path / "missing.json"))
    c = TestClient(server.app)
    r = c.get("/api/market_briefing").json()
    assert r["items"] == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_api.py -v`
Expected: FAIL — `AttributeError: module 'server' has no attribute 'BRIEFING_PATH'`

- [ ] **Step 3: 최소 구현 작성**

`dashboard/server.py`에서 `_flow_day = {"date": None}` 줄(약 379번째 줄) 바로 위에
추가:

```python
from briefing_detect import detect_alerts as _briefing_detect_alerts
from briefing_store import load_briefing as _briefing_load, append_briefing_item as _briefing_append
from briefing_collect import recent_news_headlines as _briefing_news, recent_market_atoms as _briefing_atoms
from briefing_synth import build_briefing_prompt as _briefing_build_prompt, parse_briefing_response as _briefing_parse

BRIEFING_PATH = os.path.join(ROOT, "output", "market_briefing.json")
_briefing_last_metrics = {"data": None}   # 직전 폴링의 market_flow 스냅샷 (임계치 비교 기준선)
_briefing_last_ai_call = {"ts": 0.0}      # 마지막 Gemini 호출 시각 (쿨다운용)
```

같은 파일에서 `threading.Thread(target=_prewarm_worker, daemon=True).start()` 줄
바로 아래(약 2698번째 줄 근처, `_prewarm_worker` 정의부 이후)에 추가:

```python
def _briefing_run_synthesis(alerts: list) -> None:
    """쿨다운 체크 후 종합층 실행 — 성공하면 ai_brief 항목 저장, 실패/생성없음이면 아무것도 안 함."""
    if time.time() - _briefing_last_ai_call["ts"] < 60:
        return
    _briefing_last_ai_call["ts"] = time.time()
    try:
        news_data = _NEWS_FEED.get("data")
        headlines = _briefing_news(news_data, limit=5)
        atoms_db_path = os.path.join(ROOT, "pipeline", "atoms", "atoms.db")
        atoms_content = _briefing_atoms(atoms_db_path, limit=5)
        stored = _briefing_load(BRIEFING_PATH)
        prior_headlines = [f"{it['headline']}" for it in (stored.get("items") or [])[:2]
                           if it.get("kind") == "ai_brief"]
        prompt = _briefing_build_prompt(alerts, headlines, atoms_content, prior_headlines)
        if not prompt:
            return
        res = _gemini_text(prompt, keys=_summary_keys(), models=GEMINI_TEXT_MODELS)
        if not res.get("ok"):
            return
        parsed = _briefing_parse(res.get("analysis", ""))
        if not parsed:
            return
        severity = "red" if alerts else "yellow"
        _briefing_append(BRIEFING_PATH, {
            "ts": datetime.now().strftime("%H:%M"), "severity": severity,
            "headline": parsed["headline"], "body": parsed["body"], "kind": "ai_brief"})
    except Exception:
        pass


def _poll_briefing():
    """30초 주기 — market_flow 임계치 감지 + 12분 고정주기 종합. 감지 즉시 종합도 트리거."""
    _last_fixed_synth = 0.0
    while True:
        try:
            mf_cached = _prewarm_cache.get("market_flow") or {}
            curr = mf_cached.get("data")
            if curr:
                prev = _briefing_last_metrics["data"]
                alerts = _briefing_detect_alerts(prev, curr)
                _briefing_last_metrics["data"] = curr
                for a in alerts:
                    _briefing_append(BRIEFING_PATH, {
                        "ts": a["ts"], "severity": "gray",
                        "headline": f"{a['label']} 변동", "body": None, "kind": "raw_alert"})
                if alerts:
                    _briefing_run_synthesis(alerts)
                elif time.time() - _last_fixed_synth >= 720:
                    _last_fixed_synth = time.time()
                    _briefing_run_synthesis([])
        except Exception:
            pass
        time.sleep(30)

threading.Thread(target=_poll_briefing, daemon=True).start()


@app.get("/api/market_briefing")
def api_market_briefing():
    return JSONResponse(content=_briefing_load(BRIEFING_PATH))
```

`dashboard/server.py`의 import 블록 중 `sys.path.insert(0, os.path.join(ROOT,
"scripts"))` 줄(약 189번째 줄) 바로 아래에 atoms 모듈 경로 확보를 위한 코드는
불필요 — `_PROJ_ROOT`(13번째 줄)가 이미 sys.path에 있어 `pipeline.atoms.db`를 바로
import 가능하지만, 이번 태스크의 `_briefing_atoms`(Task3)는 `db_path`를 직접 받는
설계라 `pipeline.atoms` import조차 필요 없다(스키마 결합도를 낮추기 위해 의도적으로
sqlite3만 사용).

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_briefing_api.py -v`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add dashboard/server.py tests/test_briefing_api.py
git commit -m "feat(briefing): 백그라운드 폴링루프(감지+종합) + /api/market_briefing"
```

---

### Task 6: 프론트엔드 — 5번째 칸 렌더링

**Files:**
- Modify: `dashboard/market.html`

**Interfaces:**
- Consumes: `GET /api/market_briefing` (Task5)
- Produces: 없음(최종 UI 태스크)

- [ ] **Step 1: CSS 추가**

`dashboard/market.html`의 `.mkt-card` 관련 스타일 블록 근처(예: 164번째 줄
`.grid{display:grid...}` 위)에 추가:

```css
.briefing-feed{max-height:520px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;}
.briefing-item{padding:8px 10px;border-radius:6px;background:#1a1a1a;border-left:3px solid #444;}
.briefing-item.sev-red{border-left-color:#e05252;}
.briefing-item.sev-yellow{border-left-color:#d4af37;}
.briefing-item.sev-gray{border-left-color:#555;opacity:0.7;}
.briefing-item .bi-ts{font-size:10px;color:#888;}
.briefing-item .bi-headline{font-size:13px;font-weight:700;margin:2px 0;}
.briefing-item .bi-body{font-size:11px;color:#aaa;line-height:1.4;}
```

- [ ] **Step 2: `renderMarketFlow`의 카드 배열에 `"briefing"` 추가**

`dashboard/market.html`에서 `panel.innerHTML=["0001","1001","global","rank_popular"].map(code=>{`
줄(약 1538번째 줄)을 다음으로 교체:

```javascript
    panel.innerHTML=["0001","1001","global","rank_popular","briefing"].map(code=>{
      const m=d[code]; if(code!=="briefing" && !m)return"";
```

같은 map 함수 안, `if(code==="global"){` 분기 바로 앞(글로벌 카드 분기 시작 지점)에
새 분기를 추가:

```javascript
      // ── 실시간 시장 브리핑 카드 ──
      if(code==="briefing"){
        const items=_briefingItems||[];
        const rows=items.length
          ?items.map(it=>{
            const sev=it.severity==="red"?"sev-red":it.severity==="yellow"?"sev-yellow":"sev-gray";
            const icon=it.severity==="red"?"🔴":it.severity==="yellow"?"🟡":"⚪";
            const body=it.body?`<div class="bi-body">${it.body}</div>`:"";
            return `<div class="briefing-item ${sev}">
              <div class="bi-ts">${icon} ${it.ts}</div>
              <div class="bi-headline">${it.headline}</div>
              ${body}
            </div>`;
          }).join("")
          :`<div style="color:#666;font-size:12px;padding:8px;">아직 브리핑 없음</div>`;
        return `<div class="mkt-card" style="flex:1;min-width:0;">
          <div style="font-size:13px;color:#ccc;margin-bottom:6px;">📡 실시간 브리핑</div>
          <div class="briefing-feed">${rows}</div>
        </div>`;
      }
```

- [ ] **Step 3: `_briefingItems` 상태 변수 + `loadMarketBriefing()` 추가**

`dashboard/market.html`에서 `const _MF_CACHE_KEY="mf_cache_v2";` 줄(약 1404번째 줄)
바로 위에 추가:

```javascript
let _briefingItems=[];

async function loadMarketBriefing(){
  try{
    const r=await fetch("/api/market_briefing");
    const d=await r.json();
    if(Array.isArray(d.items)){
      _briefingItems=d.items;
    }
  }catch(e){console.error("market_briefing 오류",e);}
}
```

- [ ] **Step 4: 폴링 등록**

`dashboard/market.html`에서 `setInterval(loadMarketFlow, 30000);` 줄(약 3411번째
줄) 바로 아래에 추가:

```javascript
loadMarketBriefing();
setInterval(loadMarketBriefing, 30000);
```

`_briefingItems`가 갱신된 뒤 화면에 반영되려면 `renderMarketFlow`가 다시 호출돼야
한다 — 이미 `loadMarketFlow`가 30초마다 `renderMarketFlow`를 호출하고 있으므로
(Step 2에서 그 map 배열에 `"briefing"`을 추가했음), 브리핑 갱신 후 최대 30초 이내에
화면에 반영된다. 두 폴링 함수가 서로 다른 타이밍에 돌아도 문제없다 — `_briefingItems`는
전역 변수라 `renderMarketFlow`가 호출되는 시점의 최신값을 항상 읽는다.

- [ ] **Step 5: 브라우저에서 직접 확인**

로컬 서버(`python.exe dashboard/server.py`) 실행 후 `http://127.0.0.1:8090/market`
접속. 개발자도구 콘솔에서 다음을 실행해 5번째 칸이 실제로 렌더링됐는지 확인:

```javascript
document.querySelectorAll("#mkt-panel > .mkt-card").length   // 5여야 함(코스피/코스닥/글로벌/순위/브리핑)
document.querySelector(".briefing-feed").textContent          // "아직 브리핑 없음" 또는 실제 항목
```

Expected: `.mkt-card` 5개, `.briefing-feed`가 존재하고 텍스트가 비어있지 않음.
(fablize 검증-그라운딩 원칙: 렌더 산출물은 실제 브라우저 구동 확인 없이 완료 처리
금지 — 이 스텝을 건너뛰지 말 것)

- [ ] **Step 6: 커밋**

```bash
git add dashboard/market.html
git commit -m "feat(briefing): 5번째 칸(실시간 브리핑 피드) 프론트 렌더링"
```

