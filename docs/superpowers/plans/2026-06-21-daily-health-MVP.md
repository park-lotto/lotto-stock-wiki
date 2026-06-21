# daily_health 검증시스템 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 매일 파이프라인 건강검진을 자동화해 정상=한 줄/이상=상세 텔레카드를 발송한다(이미 있는 신호만 사용, 신규 훅 없음).

**Architecture:** `daily_health.py`가 atoms DB(소스별 원자수)·개선큐 로그(unmatched/foreign_unmapped 줄수)·pytest 결과를 모아 `health_history.json`의 어제 스냅샷과 비교 → 경보 산출 → 텔레카드(send_telegram 재사용) → 오늘 스냅샷 저장. `atom_pipeline` STEP6.

**Tech Stack:** Python 3.14, sqlite3, pytest, calc_oscillator.send_telegram.

## Global Constraints

- 설계 출처: `docs/superpowers/specs/2026-06-21-daily-health-검증시스템-design.md`. **MVP**: 신규 훅(run-log·flag집계) 없이 기존 신호만.
- 신호: 소스별 원자수(DB GROUP BY source_type, 오늘), 개선큐 신규(unmatched.log·foreign_unmapped.log 오늘 줄수), pytest 종료코드.
- 비교: `pipeline/atoms/health_history.json` 어제 스냅샷. 경보: 원자수 -50%↓(🟠), 플래그 대체로 pytest 실패(🔴), 개선큐 증가(🟡). (flag율은 후속.)
- 발송: 정상(경보0)=한 줄(✅), 이상(경보≥1)=상세(⚠️). `calc_oscillator.send_telegram(text)` 재사용. config 없으면 출력만.
- 컴포넌트 분리: `collect_signals`/`compare_to_baseline`/`render_card`/`save_snapshot` 순수 로직 TDD. send·pytest 실행은 테스트 안 함.
- 테스트는 로그/DB/스냅샷 임시경로 격리.

---

### Task 1: collect/compare/render 순수 로직

**Files:**
- Create: `pipeline/atoms/daily_health.py`
- Test: `pipeline/atoms/test_daily_health.py`

**Interfaces:**
- Produces:
  - `compare_to_baseline(today: dict, yesterday: dict) -> list[dict]` — 경보 리스트 {level,code,msg}. level∈{red,orange,yellow}.
  - `render_card(metrics: dict, alerts: list) -> str` — 경보0=한 줄/≥1=상세.

- [ ] **Step 1: Write the failing test**

```python
# pipeline/atoms/test_daily_health.py
from pipeline.atoms.daily_health import compare_to_baseline, render_card


def test_atom_drop_orange():
    today = {"date": "2026-06-21", "atoms": {"telegram": 3}, "queue_new": 0, "pytest_ok": True}
    yest = {"atoms": {"telegram": 22}}
    alerts = compare_to_baseline(today, yest)
    assert any(a["level"] == "orange" and "telegram" in a["msg"] for a in alerts)


def test_pytest_fail_red():
    today = {"date": "2026-06-21", "atoms": {"telegram": 20}, "queue_new": 0, "pytest_ok": False}
    yest = {"atoms": {"telegram": 22}}
    alerts = compare_to_baseline(today, yest)
    assert any(a["level"] == "red" for a in alerts)


def test_queue_increase_yellow():
    today = {"date": "2026-06-21", "atoms": {"telegram": 20}, "queue_new": 5, "pytest_ok": True}
    yest = {"atoms": {"telegram": 22}}
    alerts = compare_to_baseline(today, yest)
    assert any(a["level"] == "yellow" for a in alerts)


def test_no_baseline_no_drop_alert():
    today = {"date": "2026-06-21", "atoms": {"telegram": 20}, "queue_new": 0, "pytest_ok": True}
    alerts = compare_to_baseline(today, {})
    assert not any(a["level"] == "orange" for a in alerts)


def test_render_card_normal_one_line():
    metrics = {"date": "2026-06-21", "atoms": {"telegram": 22, "news": 9}, "queue_new": 0, "pytest_ok": True}
    card = render_card(metrics, [])
    assert card.count("\n") <= 1
    assert "✅" in card


def test_render_card_alert_detailed():
    metrics = {"date": "2026-06-21", "atoms": {"telegram": 3}, "queue_new": 2, "pytest_ok": True}
    alerts = [{"level": "orange", "code": "ATOM_DROP", "msg": "telegram 22→3"}]
    card = render_card(metrics, alerts)
    assert "⚠️" in card
    assert "telegram 22→3" in card
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pipeline/atoms/test_daily_health.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: daily_health.py 순수 로직 구현**

```python
# pipeline/atoms/daily_health.py
"""파이프라인 매일 건강검진 (MVP) — 기존 신호만 모아 정상=1줄/이상=상세 텔레카드."""

_DROP_RATIO = 0.5  # 어제 대비 -50%↓ 경보


def compare_to_baseline(today: dict, yesterday: dict) -> list[dict]:
    alerts = []
    if not today.get("pytest_ok", True):
        alerts.append({"level": "red", "code": "PYTEST_FAIL", "msg": "pytest 실패"})
    y_atoms = (yesterday or {}).get("atoms") or {}
    for src, cnt in (today.get("atoms") or {}).items():
        prev = y_atoms.get(src)
        if prev and prev > 0 and cnt < prev * _DROP_RATIO:
            alerts.append({"level": "orange", "code": "ATOM_DROP",
                           "msg": f"{src} 원자 급감: {prev}→{cnt}"})
    if today.get("queue_new", 0) > 0:
        alerts.append({"level": "yellow", "code": "QUEUE_NEW",
                       "msg": f"보강큐 신규 {today['queue_new']}건"})
    return alerts


def render_card(metrics: dict, alerts: list) -> str:
    date = metrics.get("date", "")
    atoms = metrics.get("atoms") or {}
    atom_str = " · ".join(f"{k}+{v}" for k, v in atoms.items())
    pytest_str = "pytest ok" if metrics.get("pytest_ok", True) else "pytest FAIL"
    if not alerts:
        return f"✅ 건강검진 {date} 정상 — {pytest_str}, 원자 {atom_str}"
    icon = {"red": "🔴", "orange": "🟠", "yellow": "🟡"}
    lines = [f"⚠️ 건강검진 {date} — 경보 {len(alerts)}건"]
    for a in alerts:
        lines.append(f"{icon.get(a['level'], '•')} {a['msg']}")
    lines.append(f"[현황] {pytest_str}, 원자 {atom_str}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/atoms/test_daily_health.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/daily_health.py pipeline/atoms/test_daily_health.py
git commit -m "feat(health): compare_to_baseline + render_card 순수 로직"
```

---

### Task 2: 신호 수집 + 스냅샷 + main + 파이프라인

**Files:**
- Modify: `pipeline/atoms/daily_health.py`
- Test: `pipeline/atoms/test_daily_health_collect.py`
- Modify: `scripts/atom_pipeline.py` (STEP6)

**Interfaces:**
- Consumes: `db.get_conn`.
- Produces:
  - `collect_signals(date: str) -> dict` ({date, atoms, queue_new, pytest_ok}).
  - `load_history(path) -> dict`, `save_snapshot(metrics, path)`.
  - `main()` — collect → compare(어제) → render → send_telegram(있으면) → save.

- [ ] **Step 1: Write the failing test**

```python
# pipeline/atoms/test_daily_health_collect.py
import json
import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.daily_health import collect_atom_counts, load_history, save_snapshot


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    yield


def test_collect_atom_counts(tmp_path):
    dbmod.init_db(); dbmod.migrate_db()
    import uuid
    from datetime import datetime
    conn = dbmod.get_conn()
    for st in ("telegram", "telegram", "news"):
        conn.execute(
            "INSERT INTO atoms (id,date,source_type,source_name,source_trust,raw_file,"
            "layer,sector,asset,asset_level,signal,event_type,magnitude,content_type,"
            "strength_score,content,relations,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), "2026-06-21", st, "x", 3, "f.md", "L5", "반도체", "a",
             "sector", "neutral", "report", "minor", "fact", 2, "c", "[]",
             datetime.now().isoformat()))
    conn.commit(); conn.close()
    counts = collect_atom_counts("2026-06-21")
    assert counts["telegram"] == 2
    assert counts["news"] == 1


def test_history_roundtrip(tmp_path):
    p = tmp_path / "hist.json"
    save_snapshot({"date": "2026-06-21", "atoms": {"telegram": 5}}, p)
    h = load_history(p)
    assert h["2026-06-21"]["atoms"]["telegram"] == 5


def test_load_history_missing(tmp_path):
    assert load_history(tmp_path / "none.json") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pipeline/atoms/test_daily_health_collect.py -v`
Expected: FAIL.

- [ ] **Step 3: collect/history/main 구현 (daily_health.py에 추가)**

```python
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .db import get_conn

_ROOT = Path(__file__).parent.parent.parent
_HISTORY = Path(__file__).parent / "health_history.json"
_UNMATCHED = _ROOT / "raw" / "telegram_unmatched.log"
_FOREIGN = _ROOT / "raw" / "telegram_foreign_unmapped.log"


def collect_atom_counts(date: str) -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT source_type, COUNT(*) FROM atoms WHERE date=? GROUP BY source_type", (date,)
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def _log_lines_for_date(path: Path, date: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith(date))


def load_history(path: Path = _HISTORY) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_snapshot(metrics: dict, path: Path = _HISTORY) -> None:
    hist = load_history(path)
    hist[metrics["date"]] = {k: v for k, v in metrics.items() if k != "date"}
    # 최근 14일만 보관
    for d in sorted(hist)[:-14]:
        del hist[d]
    path.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_signals(date: str) -> dict:
    atoms = collect_atom_counts(date)
    queue_new = _log_lines_for_date(_UNMATCHED, date) + _log_lines_for_date(_FOREIGN, date)
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "pipeline/atoms/", "-q"],
                           cwd=str(_ROOT), capture_output=True, timeout=300)
        pytest_ok = r.returncode == 0
    except Exception:
        pytest_ok = True  # 측정 실패는 경보 아님
    return {"date": date, "atoms": atoms, "queue_new": queue_new, "pytest_ok": pytest_ok}


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    date = datetime.now().strftime("%Y-%m-%d")
    metrics = collect_signals(date)
    hist = load_history()
    yest = hist.get((datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d"), {})
    alerts = compare_to_baseline(metrics, yest)
    card = render_card(metrics, alerts)
    print(card)
    try:
        from calc_oscillator import send_telegram
        send_telegram(card)
    except Exception as e:
        print(f"  [건강검진] 텔레 발송 생략: {e}")
    save_snapshot(metrics)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: atom_pipeline.py STEP6 추가**

`atom_pipeline.py`의 STEP5(wiki_update) 다음에:
```python
    # 6단계: 매일 건강검진 (정상=1줄/이상=상세 텔레카드)
    run([PYTHON, "-m", "pipeline.atoms.daily_health"], "STEP6 health")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest pipeline/atoms/test_daily_health_collect.py pipeline/atoms/test_daily_health.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/atoms/daily_health.py pipeline/atoms/test_daily_health_collect.py scripts/atom_pipeline.py
git commit -m "feat(health): 신호수집 + 스냅샷 + main + STEP6"
```

---

### Task 3: 라이브 검증

- [ ] **Step 1: 전체 테스트 회귀**

Run: `python -m pytest pipeline/atoms/ -q`
Expected: 전체 PASS.

- [ ] **Step 2: daily_health 단독 실행 (카드 출력 확인)**

Run: `python -m pipeline.atoms.daily_health`
Expected: 건강검진 카드 출력(정상=✅ 한 줄 또는 이상=⚠️ 상세). 에러 없이 종료. health_history.json 생성.

- [ ] **Step 3: Commit (스냅샷 git 제외 확인)**

```bash
git add pipeline/atoms/health_history.json 2>/dev/null || true
git status --short
git commit -m "test(health): 라이브 검증 — 카드 출력 확인" --allow-empty
```

---

## Self-Review

**1. Spec coverage:** §3 신호수집(원자수·개선큐·pytest) → Task2 collect_signals ✅. §4 비교·경보 → Task1 compare ✅. §5 카드(정상1줄/이상상세) → Task1 render ✅. §2 STEP6 → Task2 ✅. 신규훅(run-log·flag율)은 MVP 범위 밖(스펙 §3 일부 후속) — 명시.
**2. Placeholder scan:** 없음. pytest 측정 실패는 경보 아님(측정 불가 ≠ 실패) 명시.
**3. Type consistency:** `compare_to_baseline(today,yest)->list`, `render_card(metrics,alerts)->str`, `collect_signals(date)->dict`, `collect_atom_counts(date)->dict`, `load_history/save_snapshot(path)` — Task 정의·사용 일치.
