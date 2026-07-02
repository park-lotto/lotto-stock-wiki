# 크롤·인제스트 텔레그램 헬스리포트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/slot_ingest.py`가 매 슬롯(하루 7회, 기존 Task Scheduler 트리거) 실행
후 텔레그램에 "오늘 누적(+이번 슬롯 신규)" 표를 보내고, 원자 0건/급감/API에러를
자동 감지해 1회 재시도한 뒤 결과를 표시하도록 확장한다.

**Architecture:** 새 파일 없이 `scripts/slot_ingest.py` 내부에 순수 함수(패딩/정규식
파싱/판정)와 DB 헬퍼를 추가하고, `main()`의 `send_report()` 호출을 새 진단 파이프라인
(`ingest_cat` → `diagnose` → `build_report` → `_send_ops_tg`)으로 교체한다.

**Tech Stack:** Python 표준 라이브러리(`re`, `subprocess`, `unicodedata`, `urllib`),
`pipeline.atoms.db.get_conn()`(기존 sqlite3 연결 헬퍼), pytest.

## Global Constraints

- 발송 빈도는 기존 그대로 하루 7회(Task Scheduler 트리거 변경 없음)
- 표시값은 "오늘누적(+이번슬롯신규)" 형식 (예: `45(+12)`)
- 재시도는 카테고리당 슬롯당 최대 1회
- 문제 판정: `에러 시그니처 발견` 또는 `원본 있음(pending>0)인데 신규원자 0건` → 재시도
- 급감 판정: `신규원자>0` AND `최근 7일 평균>0` AND `신규원자 < 평균*0.3` → ⚠️(재시도 없음)
- 발송 채널: `.env`의 `OPS_BOT_TOKEN`/`OPS_CHAT_ID` (이미 설정 완료, t.me/parklotto13bot)
  — 기존 `BOT_TOKEN`/`CHAT_ID`(`_send_tg`)는 건드리지 않음
- 대상 카테고리는 `--cats`로 들어온 것만(telegram/youtube/blog/report). `news`는 범위 밖.
- 스펙 문서: `docs/superpowers/specs/2026-07-02-crawl-ingest-health-report-design.md`

---

### Task 1: 표시 폭 계산 + 패딩 헬퍼

**Files:**
- Modify: `scripts/slot_ingest.py` (파일 상단 import 아래에 헬퍼 추가)
- Test: `tests/test_slot_ingest_report.py` (신규)

**Interfaces:**
- Produces: `_disp_width(s: str) -> int`, `_pad(s: str, width: int) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_slot_ingest_report.py` 새로 생성:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import slot_ingest as si


def test_disp_width_ascii():
    assert si._disp_width("abc") == 3


def test_disp_width_korean():
    assert si._disp_width("텔레그램") == 8


def test_pad_korean_label():
    assert si._pad("텔레그램", 10) == "텔레그램  "


def test_pad_ascii_label():
    assert si._pad("youtube", 10) == "youtube   "


def test_pad_already_over_width_no_truncate():
    assert si._pad("아주긴카테고리라벨", 4) == "아주긴카테고리라벨"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: FAIL — `AttributeError: module 'slot_ingest' has no attribute '_disp_width'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/slot_ingest.py` 상단 `import` 블록에 `re`, `unicodedata` 추가:

```python
import sys
import re
import json
import unicodedata
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta
```

`ROOT = Path(__file__).parent.parent` 줄 바로 아래(기존 `PY = sys.executable` 다음)에 추가:

```python
def _disp_width(s: str) -> int:
    """동아시아 넓은 문자(한글 등)를 폭 2로 계산 — 텔레그램 모노스페이스 표 정렬용."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    """오른쪽 공백 패딩(한글 폭 보정). 이미 목표폭 이상이면 그대로 반환."""
    return s + " " * max(0, width - _disp_width(s))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/slot_ingest.py tests/test_slot_ingest_report.py
git commit -m "feat(slot_ingest): 텔레그램 표용 한글폭 패딩 헬퍼 추가"
```

---

### Task 2: 서브프로세스 출력 파싱 (미처리 건수 / 에러 시그니처)

**Files:**
- Modify: `scripts/slot_ingest.py`
- Test: `tests/test_slot_ingest_report.py`

**Interfaces:**
- Consumes: 없음(순수 함수)
- Produces: `_extract_pending(text: str) -> int`, `_ERROR_SIGNS: tuple[str, ...]`,
  `_extract_error(text: str) -> str | None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_slot_ingest_report.py`에 추가:

```python
def test_extract_pending_korean_label():
    text = "[15/19] ...\n완료: 19개 채널, 124개 원자\n미처리 텔레그램: 6개\n"
    assert si._extract_pending(text) == 6


def test_extract_pending_english_label():
    text = "완료: 0개, 0개 원자\n미처리 youtube: 0개\n"
    assert si._extract_pending(text) == 0


def test_extract_pending_missing_pattern():
    assert si._extract_pending("아무 정보 없는 로그") == 0


def test_extract_error_quota():
    text = "google.api_core.exceptions.ResourceExhausted: 429 RESOURCE_EXHAUSTED"
    err = si._extract_error(text)
    assert err is not None
    assert "RESOURCE_EXHAUSTED" in err


def test_extract_error_traceback():
    text = "Traceback (most recent call last):\n  File x.py\nKeyError: 'x'"
    assert si._extract_error(text) is not None


def test_extract_error_none_on_clean_log():
    text = "[15/19] 2026-07-01_미래시황.md\n  → 13개 원자\n완료: 19개 채널, 124개 원자"
    assert si._extract_error(text) is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 6개 신규 테스트 FAIL — `AttributeError: ... no attribute '_extract_pending'`

- [ ] **Step 3: 최소 구현 작성**

`_pad` 함수 바로 아래에 추가:

```python
def _extract_pending(text: str) -> int:
    """서브프로세스 출력에서 '미처리 {라벨}: N개' 패턴의 N을 추출. 못 찾으면 0."""
    m = re.search(r"미처리[^:：]*[:：]\s*(\d+)개", text)
    return int(m.group(1)) if m else 0


_ERROR_SIGNS = ("Traceback", "RESOURCE_EXHAUSTED", "429", "quota",
                "Authentication", "invalid_api_key", "invalid api key",
                "ConnectionError", "run 오류")


def _extract_error(text: str) -> str | None:
    """서브프로세스 출력에서 에러 시그니처가 포함된 첫 줄을 찾아 반환. 없으면 None."""
    for line in text.splitlines():
        if any(sign in line for sign in _ERROR_SIGNS):
            return line.strip()[:200]
    return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 11 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/slot_ingest.py tests/test_slot_ingest_report.py
git commit -m "feat(slot_ingest): 서브프로세스 출력에서 미처리건수/에러시그니처 추출"
```

---

### Task 3: `run()`이 출력을 캡처하도록 수정 (launch 실패에도 안전)

**Files:**
- Modify: `scripts/slot_ingest.py:31-35` (기존 `run()` 함수 전체 교체)

**Interfaces:**
- Produces: `run(cmd: list[str], label: str) -> tuple[int, str]` (기존엔 `int`만 반환했음 —
  호출부는 Task 4에서 함께 수정)

- [ ] **Step 1: 기존 `run()` 교체**

기존:
```python
def run(cmd: list[str], label: str) -> int:
    print(f"\n{'='*50}\n[{label}] {' '.join(str(c) for c in cmd)}\n{'='*50}")
    r = subprocess.run(cmd, cwd=str(ROOT))
    print(f"[{label}] 완료 (exit={r.returncode})")
    return r.returncode
```

신규:
```python
def run(cmd: list[str], label: str) -> tuple[int, str]:
    """서브프로세스 실행. 출력은 화면에 그대로 찍고(기존 가시성 유지), 진단용으로도 반환.
    subprocess 자체 실행 실패(예: 인터프리터 경로 문제)도 예외를 던지지 않고
    에러 텍스트로 반환해 파이프라인이 죽지 않게 한다."""
    print(f"\n{'='*50}\n[{label}] {' '.join(str(c) for c in cmd)}\n{'='*50}")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
        output = (r.stdout or "") + (r.stderr or "")
        code = r.returncode
    except Exception as e:
        output = f"[run 오류] {e}"
        code = -1
    print(output)
    print(f"[{label}] 완료 (exit={code})")
    return code, output
```

이 시점에서 `main()`의 `run([...], "sync-yesterday")` / `"sync-today"` 호출부는
반환값을 쓰지 않으므로(튜플이 되어도) 그대로 동작한다. `ingest_cat()`은 아직
옛 방식대로 반환값 없이 `run()`을 호출 중이라 타입은 안 맞지만 신경 안 씀 —
Task 4에서 함께 고친다.

- [ ] **Step 2: 문법/임포트 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -c "import sys; sys.path.insert(0,'scripts'); import slot_ingest"`
Expected: 에러 없이 조용히 끝남(모듈 import만 확인, 아무 것도 실행 안 됨)

- [ ] **Step 3: 커밋**

```bash
git add scripts/slot_ingest.py
git commit -m "feat(slot_ingest): run()이 subprocess 출력을 캡처해 반환하도록 변경"
```

---

### Task 4: `ingest_cat()`이 캡처된 출력을 반환하도록 수정

**Files:**
- Modify: `scripts/slot_ingest.py:38-60` (기존 `ingest_cat()` 함수 전체 교체)

**Interfaces:**
- Consumes: `run(cmd, label) -> tuple[int, str]` (Task 3)
- Produces: `ingest_cat(cat: str, date: str, extra_date: str | None = None) -> str`
  (카테고리 처리 중 나온 subprocess 출력을 모두 이어붙인 문자열. telegram은
  extra_date 실행 + date 실행 두 출력을 이어붙임)

- [ ] **Step 1: 기존 `ingest_cat()` 교체**

기존:
```python
def ingest_cat(cat: str, date: str, extra_date: str | None = None) -> None:
    """카테고리별 인제스트.
    - 텔레는 날짜 단위 파일이라 date + extra_date(전날) 모두 --force-date 처리
    - 유튜브/블로그는 sync 후 파일 목록 기반이라 자동으로 전날분 포함
    """
    if cat == "telegram":
        # 전날 먼저 처리(공백 보완) → 당일 처리
        if extra_date:
            run([PY, "-m", "pipeline.atoms.telegram_ingest",
                 "--all", "--force-date", extra_date, "--limit", "40"], f"telegram-{extra_date[5:]}")
        run([PY, "-m", "pipeline.atoms.telegram_ingest",
             "--all", "--force-date", date, "--limit", "40"], f"telegram-{date[5:]}")
    elif cat == "youtube":
        run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "youtube",
             "--all", "--limit", "60"], "youtube")
    elif cat == "blog":
        run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "blog",
             "--all", "--limit", "60"], "blog")
    elif cat == "report":
        run([PY, "-m", "pipeline.atoms.report_ingest",
             "--all", "--limit", "40"], "report")
    else:
        print(f"[skip] 알 수 없는 카테고리: {cat}")
```

신규:
```python
def ingest_cat(cat: str, date: str, extra_date: str | None = None) -> str:
    """카테고리별 인제스트.
    - 텔레는 날짜 단위 파일이라 date + extra_date(전날) 모두 --force-date 처리
    - 유튜브/블로그는 sync 후 파일 목록 기반이라 자동으로 전날분 포함
    반환값: 이번 호출에서 실행된 서브프로세스 출력을 모두 이어붙인 문자열(진단용).
    """
    parts: list[str] = []
    if cat == "telegram":
        if extra_date:
            _, out = run([PY, "-m", "pipeline.atoms.telegram_ingest",
                          "--all", "--force-date", extra_date, "--limit", "40"],
                         f"telegram-{extra_date[5:]}")
            parts.append(out)
        _, out = run([PY, "-m", "pipeline.atoms.telegram_ingest",
                      "--all", "--force-date", date, "--limit", "40"],
                     f"telegram-{date[5:]}")
        parts.append(out)
    elif cat == "youtube":
        _, out = run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "youtube",
                      "--all", "--limit", "60"], "youtube")
        parts.append(out)
    elif cat == "blog":
        _, out = run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "blog",
                      "--all", "--limit", "60"], "blog")
        parts.append(out)
    elif cat == "report":
        _, out = run([PY, "-m", "pipeline.atoms.report_ingest",
                      "--all", "--limit", "40"], "report")
        parts.append(out)
    else:
        print(f"[skip] 알 수 없는 카테고리: {cat}")
    return "\n".join(parts)
```

- [ ] **Step 2: import 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -c "import sys; sys.path.insert(0,'scripts'); import slot_ingest"`
Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
git add scripts/slot_ingest.py
git commit -m "feat(slot_ingest): ingest_cat()이 캡처된 출력을 반환하도록 변경"
```

---

### Task 5: DB 헬퍼 (오늘 누적 / 이번슬롯 신규 / 최근7일 평균)

**Files:**
- Modify: `scripts/slot_ingest.py`
- Test: `tests/test_slot_ingest_report.py`

**Interfaces:**
- Produces: `_atoms_count_today(source_type: str, date: str) -> int`,
  `_atoms_count_since(source_type: str, since_iso: str) -> int`,
  `_trailing_avg(source_type: str, before_date: str, days: int = 7) -> float`

- [ ] **Step 1: 스모크 테스트 작성 (실제 atoms.db 대상 — 개수는 단언하지 않고 타입/무오류만 확인)**

`tests/test_slot_ingest_report.py`에 추가:

```python
def test_atoms_count_today_smoke():
    n = si._atoms_count_today("report", "2026-07-02")
    assert isinstance(n, int)
    assert n >= 0


def test_atoms_count_since_smoke():
    n = si._atoms_count_since("report", "2026-07-02T00:00:00")
    assert isinstance(n, int)
    assert n >= 0


def test_trailing_avg_smoke():
    avg = si._trailing_avg("report", "2026-07-02")
    assert isinstance(avg, float)
    assert avg >= 0.0


def test_trailing_avg_unknown_source_type_is_zero():
    avg = si._trailing_avg("존재하지않는소스타입", "2026-07-02")
    assert avg == 0.0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 4개 신규 FAIL — `AttributeError: ... no attribute '_atoms_count_today'`

- [ ] **Step 3: 최소 구현 작성**

`_extract_error` 함수 바로 아래에 추가:

```python
def _atoms_count_today(source_type: str, date: str) -> int:
    from pipeline.atoms.db import get_conn
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE source_type=? AND date=?",
            (source_type, date)).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _atoms_count_since(source_type: str, since_iso: str) -> int:
    from pipeline.atoms.db import get_conn
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE source_type=? AND created_at>=?",
            (source_type, since_iso)).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _trailing_avg(source_type: str, before_date: str, days: int = 7) -> float:
    """before_date 이전 최근 N일간 source_type 일평균 원자 수. 데이터 없으면 0.0."""
    from pipeline.atoms.db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT date, COUNT(*) c FROM atoms WHERE source_type=? AND date<? "
            "GROUP BY date ORDER BY date DESC LIMIT ?",
            (source_type, before_date, days)).fetchall()
        if not rows:
            return 0.0
        return sum(r[1] for r in rows) / len(rows)
    finally:
        conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 15 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/slot_ingest.py tests/test_slot_ingest_report.py
git commit -m "feat(slot_ingest): 오늘누적/슬롯신규/최근7일평균 DB 헬퍼 추가"
```

---

### Task 6: `diagnose()` — 카테고리별 판정 + 자동 재시도

**Files:**
- Modify: `scripts/slot_ingest.py`
- Test: `tests/test_slot_ingest_report.py`

**Interfaces:**
- Consumes: `_extract_pending`, `_extract_error`, `_atoms_count_since`,
  `_atoms_count_today`, `_trailing_avg` (위 태스크들), `ingest_cat` (Task 4)
- Produces: `diagnose(cat: str, date: str, extra_date: str, since_iso: str, output: str) -> dict`
  반환 dict 키: `cat, delta, total_today, icon, note, retried` (icon은 `"✅"/"⚠️"/"🔴"`)

- [ ] **Step 1: 실패하는 테스트 작성 (monkeypatch로 DB/subprocess 격리)**

`tests/test_slot_ingest_report.py`에 추가:

```python
def test_diagnose_normal_no_pending(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 0)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 9)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 5.0)

    def boom(*a, **k):
        raise AssertionError("원본 없으면 재시도하면 안 됨")
    monkeypatch.setattr(si, "ingest_cat", boom)

    output = "미처리 youtube: 0개\n완료: 0개, 0개 원자"
    r = si.diagnose("youtube", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r == {"cat": "youtube", "delta": 0, "total_today": 9,
                 "icon": "✅", "note": "정상", "retried": False}


def test_diagnose_pending_but_zero_atoms_retries_and_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_since(st, s):
        calls["n"] += 1
        return 0 if calls["n"] == 1 else 5

    monkeypatch.setattr(si, "_atoms_count_since", fake_since)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 46)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 10.0)
    monkeypatch.setattr(si, "ingest_cat",
                         lambda cat, date, extra_date=None: "재시도 완료, 에러없음")

    output = "미처리 리포트: 3개\n완료: 0개, 0개 원자"
    r = si.diagnose("report", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "✅"
    assert r["note"] == "재시도로 해결"
    assert r["delta"] == 5
    assert r["retried"] is True


def test_diagnose_retry_still_fails_flags_confirm_needed(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 0)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 46)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 10.0)
    monkeypatch.setattr(si, "ingest_cat",
                         lambda cat, date, extra_date=None: "RESOURCE_EXHAUSTED 429 quota")

    output = "미처리 리포트: 3개\n완료: 0개, 0개 원자"
    r = si.diagnose("report", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "🔴"
    assert "확인필요" in r["note"]
    assert "RESOURCE_EXHAUSTED" in r["note"]
    assert r["retried"] is True


def test_diagnose_error_signature_triggers_retry_even_without_pending(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 0)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 20)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 10.0)
    monkeypatch.setattr(si, "ingest_cat",
                         lambda cat, date, extra_date=None: "여전히 Traceback 있음")

    output = "미처리 텔레그램: 0개\nTraceback (most recent call last):\nKeyError"
    r = si.diagnose("telegram", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "🔴"
    assert r["retried"] is True


def test_diagnose_sharp_drop_warning_no_retry(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 3)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 3)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 40.0)

    def boom(*a, **k):
        raise AssertionError("급감은 재시도하면 안 됨")
    monkeypatch.setattr(si, "ingest_cat", boom)

    output = "미처리 텔레그램: 0개\n완료: 6개 채널, 3개 원자"
    r = si.diagnose("telegram", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "⚠️"
    assert "급감" in r["note"]
    assert r["retried"] is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 5개 신규 FAIL — `AttributeError: ... no attribute 'diagnose'`

- [ ] **Step 3: 최소 구현 작성**

`_trailing_avg` 함수 바로 아래에 추가:

```python
def diagnose(cat: str, date: str, extra_date: str, since_iso: str, output: str) -> dict:
    """카테고리 1개 진단. 문제로 판정되면 ingest_cat()을 1회만 재호출해 재시도한다."""
    source_type = cat
    pending = _extract_pending(output)
    error = _extract_error(output)
    delta = _atoms_count_since(source_type, since_iso)
    retried = False

    if error or (pending > 0 and delta == 0):
        retried = True
        retry_output = ingest_cat(cat, date, extra_date)
        retry_error = _extract_error(retry_output)
        delta = _atoms_count_since(source_type, since_iso)
        if delta > 0 and not retry_error:
            icon, note = "✅", "재시도로 해결"
        else:
            summary = retry_error or error or "원인 미상"
            icon, note = "🔴", f"확인필요 — {summary}"
    else:
        avg = _trailing_avg(source_type, date)
        if delta > 0 and avg > 0 and delta < avg * 0.3:
            icon, note = "⚠️", f"급감(평균 {avg:.0f} 대비 {delta})"
        else:
            icon, note = "✅", "정상"

    total_today = _atoms_count_today(source_type, date)
    return {"cat": cat, "delta": delta, "total_today": total_today,
            "icon": icon, "note": note, "retried": retried}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 20 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/slot_ingest.py tests/test_slot_ingest_report.py
git commit -m "feat(slot_ingest): 카테고리별 문제판정+자동재시도 diagnose() 추가"
```

---

### Task 7: `build_report()` — 텔레그램 표 생성

**Files:**
- Modify: `scripts/slot_ingest.py`
- Test: `tests/test_slot_ingest_report.py`

**Interfaces:**
- Consumes: `_pad` (Task 1)
- Produces: `CAT_LABEL: dict[str, str]`, `build_report(cats: list[str], date: str, results: list[dict]) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_slot_ingest_report.py`에 추가:

```python
def test_build_report_all_normal_no_issue_section():
    results = [
        {"cat": "telegram", "delta": 12, "total_today": 45, "icon": "✅", "note": "정상", "retried": False},
        {"cat": "youtube", "delta": 0, "total_today": 9, "icon": "✅", "note": "정상", "retried": False},
    ]
    text = si.build_report(["telegram", "youtube"], "2026-07-02", results)
    assert "45(+12)" in text
    assert "9(+0)" in text
    assert "확인 필요" not in text
    assert "<pre>" in text and "</pre>" in text


def test_build_report_with_critical_issue():
    results = [
        {"cat": "report", "delta": 0, "total_today": 46, "icon": "🔴",
         "note": "확인필요 — RESOURCE_EXHAUSTED 429", "retried": True},
    ]
    text = si.build_report(["report"], "2026-07-02", results)
    assert "🔴 확인 필요" in text
    assert "RESOURCE_EXHAUSTED" in text
    assert "46(+0)" in text


def test_build_report_with_warning_only_no_critical_header():
    results = [
        {"cat": "telegram", "delta": 3, "total_today": 3, "icon": "⚠️",
         "note": "급감(평균 40 대비 3)", "retried": False},
    ]
    text = si.build_report(["telegram"], "2026-07-02", results)
    assert "⚠️ 참고" in text
    assert "🔴 확인 필요" not in text
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 3개 신규 FAIL — `AttributeError: ... no attribute 'build_report'`

- [ ] **Step 3: 최소 구현 작성**

`diagnose` 함수 바로 아래에 추가:

```python
CAT_LABEL = {"telegram": "텔레그램", "youtube": "유튜브", "blog": "블로그", "report": "리포트"}


def build_report(cats: list[str], date: str, results: list[dict]) -> str:
    """오늘누적(+이번슬롯신규) 표 + 문제/경고 섹션을 텔레그램 HTML 메시지로 조립."""
    hhmm = datetime.now().strftime("%H:%M")
    lines = [f"{_pad('카테고리', 10)}{_pad('오늘누적', 10)}상태", "─" * 28]
    issues = []
    for r in results:
        label = CAT_LABEL.get(r["cat"], r["cat"])
        value = f"{r['total_today']}(+{r['delta']})"
        lines.append(f"{_pad(label, 10)}{_pad(value, 10)}{r['icon']} {r['note']}")
        if r["icon"] in ("🔴", "⚠️"):
            issues.append(f"· {label}: {r['note']}")

    table = "\n".join(lines)
    msg = f"📥 크롤 인제스트  {date[5:]} {hhmm}\n<pre>{table}</pre>"
    if issues:
        head = "🔴 확인 필요" if any(r["icon"] == "🔴" for r in results) else "⚠️ 참고"
        msg += f"\n\n{head} {len(issues)}건\n" + "\n".join(issues)
    return msg
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 23 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/slot_ingest.py tests/test_slot_ingest_report.py
git commit -m "feat(slot_ingest): 오늘누적 표 + 문제/경고 섹션 build_report() 추가"
```

---

### Task 8: 업무보고 전용 봇 발송 함수

**Files:**
- Modify: `scripts/slot_ingest.py`

**Interfaces:**
- Produces: `_send_ops_tg(text: str) -> None`

- [ ] **Step 1: 구현 작성 (기존 `_send_tg` 바로 아래에 추가)**

```python
def _send_ops_tg(text: str) -> None:
    """업무보고 전용 봇으로 발송 (.env OPS_BOT_TOKEN/OPS_CHAT_ID, t.me/parklotto13bot).
    기존 _send_tg()(BOT_TOKEN/CHAT_ID)는 다른 스크립트 브리핑용이라 건드리지 않는다."""
    import urllib.request
    import urllib.parse
    cfg = {}
    envp = ROOT / ".env"
    if envp.exists():
        for line in envp.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    token, chat = cfg.get("OPS_BOT_TOKEN", ""), cfg.get("OPS_CHAT_ID", "")
    if not token or not chat:
        print("[report] 업무보고 봇 설정 없음 (.env OPS_BOT_TOKEN/OPS_CHAT_ID)")
        return
    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=data), timeout=10) as r:
            ok = json.loads(r.read()).get("ok")
        print("[report] 업무보고 텔레 전송 " + ("완료" if ok else "실패"))
    except Exception as e:
        print(f"[report] 업무보고 텔레 전송 오류: {e}")
```

- [ ] **Step 2: import 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -c "import sys; sys.path.insert(0,'scripts'); import slot_ingest"`
Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
git add scripts/slot_ingest.py
git commit -m "feat(slot_ingest): 업무보고 전용 봇(OPS_BOT_TOKEN) 발송 함수 추가"
```

---

### Task 9: `main()` 연결 + 옛 `send_report()` 제거

**Files:**
- Modify: `scripts/slot_ingest.py` (기존 `send_report()` 함수 삭제, `main()` 수정)

**Interfaces:**
- Consumes: `ingest_cat`(Task 4), `diagnose`(Task 6), `build_report`(Task 7), `_send_ops_tg`(Task 8)

- [ ] **Step 1: 기존 `send_report()` 함수 전체 삭제**

`scripts/slot_ingest.py`에서 `def send_report(cats: list[str], since_iso: str, date: str) -> None:`
부터 그 함수 끝(다음 `def main():` 바로 전 빈 줄까지)을 통째로 삭제한다.

- [ ] **Step 2: `main()` 수정**

기존:
```python
    run([PY, "scripts/sync_crawling.py", "--date", yesterday, "--overwrite"], "sync-yesterday")
    run([PY, "scripts/sync_crawling.py", "--date", date, "--overwrite"], "sync-today")

    # 2) 카테고리별 원자화 (텔레는 전날 날짜도 함께 처리)
    for c in cats:
        ingest_cat(c, date, extra_date=yesterday)

    # 3) 텔레 보고
    if not args.no_report:
        send_report(cats, since_iso, date)

    print(f"\n[slot_ingest] 완료 — {date} {cats}")
```

신규:
```python
    run([PY, "scripts/sync_crawling.py", "--date", yesterday, "--overwrite"], "sync-yesterday")
    run([PY, "scripts/sync_crawling.py", "--date", date, "--overwrite"], "sync-today")

    # 2) 카테고리별 원자화 + 진단 (텔레는 전날 날짜도 함께 처리)
    results = []
    for c in cats:
        output = ingest_cat(c, date, extra_date=yesterday)
        try:
            results.append(diagnose(c, date, yesterday, since_iso, output))
        except Exception as e:
            results.append({"cat": c, "delta": 0, "total_today": 0,
                             "icon": "❔", "note": f"확인불가 — {e}", "retried": False})

    # 3) 업무보고 텔레 발송
    if not args.no_report:
        _send_ops_tg(build_report(cats, date, results))

    print(f"\n[slot_ingest] 완료 — {date} {cats}")
```

- [ ] **Step 3: 전체 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_slot_ingest_report.py -v`
Expected: 23 passed (기존 테스트 전부 여전히 통과 — `send_report` 삭제는 테스트 대상이
아니었으므로 영향 없음)

- [ ] **Step 4: 커밋**

```bash
git add scripts/slot_ingest.py
git commit -m "feat(slot_ingest): main()을 진단 파이프라인으로 교체, 옛 send_report() 제거"
```

---

### Task 10: 실제 슬롯 2회 연속 실행으로 "이어붙이기" 수동 검증

**Files:** 없음 (수동 검증만)

**Interfaces:** 없음

- [ ] **Step 1: 1차 실행 (오늘 리포트 카테고리만, 빠른 검증용)**

Run: `cd "C:\Users\TheRose\Desktop\로또의 주식" && "C:\Users\TheRose\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts/slot_ingest.py --cats report`
Expected: 콘솔에 `[report] 완료 (exit=0)` 등 로그 출력, 마지막에
`[report] 업무보고 텔레 전송 완료` 출력. t.me/parklotto13bot으로 표 형식 메시지 도착 —
"리포트 N(+M) 상태" 한 줄만 있는 표.

- [ ] **Step 2: 2차 실행 (같은 카테고리, 곧바로 다시)**

Run: 위와 동일 명령 재실행
Expected: 두 번째 메시지의 "오늘누적" 값이 **1차 메시지보다 크거나 같음**(같음은
새 원본이 없어 신규 0건일 때). 이번 슬롯 신규(`+M`)는 1차와 무관하게 이번 실행분만
반영됨 — 즉 두 메시지를 비교했을 때 누적값이 이어붙듯 커지는지 육안 확인.

- [ ] **Step 3: 결과를 사용자에게 보고**

두 메시지의 오늘누적 값을 비교해서 실제로 누적되고 있는지("이어붙이기") 확인한 내용을
대화로 보고한다. 문제 있으면(예: 값이 줄어들거나 리셋됨) Task 6/7 로직을 재검토한다.

---
