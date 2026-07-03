# 일일 검증 에이전트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 크론으로 크롤링 신선도(요일별 평균)+pytest 회귀+stockbrain 서비스 상태를 점검하고 텔레그램으로 통합 보고하는 스크립트를 원격서버에 배포한다.

**Architecture:** `pipeline/atoms/daily_health.py`의 검증된 패턴(수집→비교→카드→발송, 히스토리 JSON)을 그대로 따라 `scripts/daily_verify.py` 신규 작성. 3개 체크는 순수함수(입력→결과 dict), 부수효과(서비스 재시작, 텔레그램 발송)는 별도 함수로 분리.

**Tech Stack:** Python stdlib(os/subprocess/json/datetime), 기존 `calc_oscillator.send_telegram` 재사용.

## Global Constraints

- 서버 외부 도달성 체크는 이 계획 범위 밖 — 온서버 체커로는 원리적으로 감지 불가(오늘 실증됨). 구현 안 함.
- AI가 발견한 코드버그를 자동으로 고치지 않는다 — pytest 실패는 목록만 보고.
- 크롤링 신선도 판정은 "어제 대비"가 아니라 "같은 요일 최근 4주 평균 대비" — 주말/공휴일 오탐 방지가 목적.
- 서비스 재시작은 `stockbrain`만, 최대 1회 자동 시도 후 재확인, 실패해도 예외 없이 상태만 기록.
- 텔레그램 발송은 기존 `.env`의 BOT_TOKEN/CHAT_ID 사용(신규 키 불필요).

---

### Task 1: 크롤링 신선도 체커 (요일별 평균)

**Files:**
- Create: `scripts/daily_verify.py`
- Test: `tests/test_daily_verify.py`

**Interfaces:**
- Produces:
  - `count_today_files(raw_dir: str, source: str, date_str: str) -> int` — `raw/{source}/`(예: `telegram`)에서 `date_str`로 시작하는 파일 개수를 센다. `telegram`은 파일명이 `{date}_{채널}.md`(raw/telegram/ 바로 아래, 서브폴더 없음), `news`/`report`는 `raw/{source}/{date}/` 서브폴더 존재 시 그 안의 파일 개수, 없으면 `raw/{source}/{date}_*.md` 패턴. 폴더/파일 없으면 0.
  - `weekday_average(history: dict, source: str, weekday: int, weeks: int = 4) -> float | None` — `history`(날짜별 `{source: count}` 딕셔너리, `daily_verify_history.json` 로드결과)에서 지정 요일(0=월)의 최근 `weeks`개 표본 평균. 표본 없으면 `None`.
  - `check_crawl_freshness(raw_root: str, sources: list[str], history: dict, today_date: str) -> list[dict]` — 각 source에 대해 오늘 카운트와 요일평균을 비교, 평균의 30% 미만이면(그리고 평균 자체가 3건 이상일 때만 — 원래 적은 소스의 노이즈 방지) `{"source":..., "today":..., "avg":..., "level":"orange"}` 경보 추가. `weekday_average`가 `None`(표본 부족)이면 그 source는 건너뜀(경보 없음 — 히스토리 쌓일 때까지는 판단 보류).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_daily_verify.py` 새로 생성:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from daily_verify import count_today_files, weekday_average, check_crawl_freshness


def test_count_today_files_flat_pattern(tmp_path):
    d = tmp_path / "telegram"
    d.mkdir()
    (d / "2026-07-03_주식픽.md").write_text("x", encoding="utf-8")
    (d / "2026-07-03_그로스리서치.md").write_text("x", encoding="utf-8")
    (d / "2026-07-02_주식픽.md").write_text("x", encoding="utf-8")
    assert count_today_files(str(tmp_path), "telegram", "2026-07-03") == 2


def test_count_today_files_subfolder_pattern(tmp_path):
    d = tmp_path / "news" / "2026-07-03"
    d.mkdir(parents=True)
    (d / "a.md").write_text("x", encoding="utf-8")
    (d / "b.md").write_text("x", encoding="utf-8")
    assert count_today_files(str(tmp_path), "news", "2026-07-03") == 2


def test_count_today_files_missing_returns_zero(tmp_path):
    assert count_today_files(str(tmp_path), "report", "2026-07-03") == 0


def test_weekday_average_computes_from_matching_weekday_only():
    # 2026-07-03(금)=weekday 4. 같은 금요일 표본만 평균에 들어가야 함.
    history = {
        "2026-06-19": {"telegram": 10},  # 금
        "2026-06-26": {"telegram": 20},  # 금
        "2026-06-20": {"telegram": 999},  # 토(다른 요일, 제외돼야 함)
    }
    avg = weekday_average(history, "telegram", weekday=4, weeks=4)
    assert avg == 15.0


def test_weekday_average_returns_none_when_no_samples():
    assert weekday_average({}, "telegram", weekday=4, weeks=4) is None


def test_check_crawl_freshness_flags_source_below_30pct_of_average(tmp_path):
    d = tmp_path / "telegram"
    d.mkdir()
    (d / "2026-07-03_a.md").write_text("x", encoding="utf-8")  # 오늘 1건
    history = {"2026-06-26": {"telegram": 10}}  # 지난주 같은 요일 10건 -> 평균 10
    alerts = check_crawl_freshness(str(tmp_path), ["telegram"], history, "2026-07-03")
    assert len(alerts) == 1
    assert alerts[0]["source"] == "telegram"
    assert alerts[0]["level"] == "orange"


def test_check_crawl_freshness_skips_when_no_history_yet(tmp_path):
    d = tmp_path / "telegram"
    d.mkdir()
    alerts = check_crawl_freshness(str(tmp_path), ["telegram"], {}, "2026-07-03")
    assert alerts == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_daily_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daily_verify'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/daily_verify.py` 새로 생성:

```python
"""일일 검증 에이전트 — pipeline/atoms/daily_health.py 패턴 확장.
크롤링 신선도(요일별 평균)+pytest 회귀+stockbrain 서비스 상태를 점검하고
텔레그램으로 통합 보고. 서버 외부 도달성 체크는 범위 밖(온서버 체커로는
원리적으로 감지 불가 — 2026-07-03 원격서버 네트워크 장애로 실증됨)."""
import glob
import os
from datetime import datetime


def count_today_files(raw_root: str, source: str, date_str: str) -> int:
    flat = glob.glob(os.path.join(raw_root, source, f"{date_str}_*"))
    if flat:
        return len(flat)
    sub = os.path.join(raw_root, source, date_str)
    if os.path.isdir(sub):
        return len([f for f in os.listdir(sub) if os.path.isfile(os.path.join(sub, f))])
    return 0


def weekday_average(history: dict, source: str, weekday: int, weeks: int = 4) -> float | None:
    samples = []
    for date_str, counts in history.items():
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if d.weekday() == weekday and source in counts:
            samples.append(counts[source])
    if not samples:
        return None
    samples = samples[-weeks:]
    return sum(samples) / len(samples)


def check_crawl_freshness(raw_root: str, sources: list[str], history: dict,
                            today_date: str) -> list[dict]:
    weekday = datetime.strptime(today_date, "%Y-%m-%d").weekday()
    alerts = []
    for source in sources:
        avg = weekday_average(history, source, weekday)
        if avg is None or avg < 3:
            continue   # 표본 부족하거나 원래 적은 소스는 판단 보류
        today_count = count_today_files(raw_root, source, today_date)
        if today_count < avg * 0.3:
            alerts.append({"source": source, "today": today_count, "avg": avg,
                            "level": "orange"})
    return alerts
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_daily_verify.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/daily_verify.py tests/test_daily_verify.py
git commit -m "feat(verify): 크롤링 신선도 체커(요일별 평균 기반)"
```

---

### Task 2: pytest 회귀 체커 + 서비스 상태 체커

**Files:**
- Modify: `scripts/daily_verify.py`
- Test: `tests/test_daily_verify.py`

**Interfaces:**
- Consumes: 없음(독립)
- Produces:
  - `run_pytest_check(root: str, timeout: int = 300) -> dict` — `python -m pytest` 전체 실행(subprocess), `{"ok": bool, "failed_tests": list[str]}` 반환. 실패시 stdout에서 `FAILED tests/...::test_name` 라인만 추출. 타임아웃/예외 시 `{"ok": True, "failed_tests": [], "error": "측정 실패: ..."}`(daily_health.py와 동일 원칙 — 측정 실패는 경보 아님).
  - `check_service_health(service_name: str = "stockbrain") -> dict` — `systemctl is-active {service_name}` 실행. `active`면 `{"active": True, "restarted": False}`. 아니면 `systemctl restart {service_name}` 1회 시도 후 재확인해서 `{"active": bool, "restarted": True}`. subprocess 호출은 모두 `subprocess.run(..., capture_output=True, timeout=15)`로 감싸고 예외 시 `{"active": None, "restarted": False, "error": str(e)}`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_daily_verify.py`에 추가:

```python
from unittest.mock import patch, MagicMock


def test_run_pytest_check_parses_failed_test_names():
    fake_output = (
        b"===== FAILURES =====\n"
        b"FAILED tests/test_a.py::test_one - AssertionError\n"
        b"FAILED tests/test_b.py::test_two - ValueError\n"
    )
    with patch("daily_verify.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout=fake_output, stderr=b"")
        result = run_pytest_check("/fake/root")
    assert result["ok"] is False
    assert result["failed_tests"] == [
        "tests/test_a.py::test_one", "tests/test_b.py::test_two"]


def test_run_pytest_check_ok_when_returncode_zero():
    with patch("daily_verify.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = run_pytest_check("/fake/root")
    assert result == {"ok": True, "failed_tests": []}


def test_run_pytest_check_exception_is_not_an_alert():
    with patch("daily_verify.subprocess.run", side_effect=Exception("timeout")):
        result = run_pytest_check("/fake/root")
    assert result["ok"] is True
    assert "측정 실패" in result["error"]


def test_check_service_health_active_no_restart():
    with patch("daily_verify.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"active\n", stderr=b"")
        result = check_service_health("stockbrain")
    assert result == {"active": True, "restarted": False}
    assert mock_run.call_count == 1   # is-active만 호출, restart는 안 함


def test_check_service_health_inactive_triggers_restart_attempt():
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "is-active" in cmd and len(calls) == 1:
            return MagicMock(returncode=3, stdout=b"inactive\n", stderr=b"")
        if "restart" in cmd:
            return MagicMock(returncode=0, stdout=b"", stderr=b"")
        return MagicMock(returncode=0, stdout=b"active\n", stderr=b"")  # 재확인
    with patch("daily_verify.subprocess.run", side_effect=fake_run):
        result = check_service_health("stockbrain")
    assert result == {"active": True, "restarted": True}
    assert calls[0] == ["systemctl", "is-active", "stockbrain"]
    assert calls[1] == ["sudo", "systemctl", "restart", "stockbrain"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_daily_verify.py -v -k "pytest_check or service_health"`
Expected: FAIL — `ImportError: cannot import name 'run_pytest_check'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/daily_verify.py`의 `import` 줄 아래에 `import re, subprocess` 추가, 파일 끝에 추가:

```python
def run_pytest_check(root: str, timeout: int = 300) -> dict:
    try:
        r = subprocess.run(["python", "-m", "pytest", "-q"], cwd=root,
                            capture_output=True, timeout=timeout)
    except Exception as e:
        return {"ok": True, "failed_tests": [], "error": f"측정 실패: {e}"}
    if r.returncode == 0:
        return {"ok": True, "failed_tests": []}
    out = r.stdout.decode("utf-8", errors="replace")
    failed = re.findall(r"^FAILED (\S+)", out, re.MULTILINE)
    return {"ok": False, "failed_tests": failed}


def check_service_health(service_name: str = "stockbrain") -> dict:
    try:
        r = subprocess.run(["systemctl", "is-active", service_name],
                            capture_output=True, timeout=15)
        active = r.stdout.decode().strip() == "active"
        if active:
            return {"active": True, "restarted": False}
        subprocess.run(["sudo", "systemctl", "restart", service_name],
                        capture_output=True, timeout=15)
        r2 = subprocess.run(["systemctl", "is-active", service_name],
                             capture_output=True, timeout=15)
        return {"active": r2.stdout.decode().strip() == "active", "restarted": True}
    except Exception as e:
        return {"active": None, "restarted": False, "error": str(e)}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_daily_verify.py -v`
Expected: 11 passed (Task1의 6개 + 이번 5개)

- [ ] **Step 5: 커밋**

```bash
git add scripts/daily_verify.py tests/test_daily_verify.py
git commit -m "feat(verify): pytest 회귀 체커 + stockbrain 서비스 상태(자동재시작 1회)"
```

---

### Task 3: 통합 리포트 조립 + main() + 히스토리 저장

**Files:**
- Modify: `scripts/daily_verify.py`
- Test: `tests/test_daily_verify.py`

**Interfaces:**
- Consumes: Task1의 `check_crawl_freshness`, Task2의 `run_pytest_check`/`check_service_health`
- Produces:
  - `render_verify_card(date_str: str, freshness_alerts: list[dict], pytest_result: dict, service_result: dict) -> str` — 전부 정상이면 1줄, 하나라도 이상이면 상세(daily_health.py의 `render_card`와 같은 포맷 원칙: ✅/⚠️ + 🔴🟠🟡 아이콘).
  - `load_verify_history(path: str) -> dict` / `save_verify_counts(path: str, date_str: str, counts: dict) -> None` — `pipeline/atoms/daily_verify_history.json`에 날짜별 `{source: count}` 저장, 14일만 보관(`daily_health.py`의 `save_snapshot`과 동일 패턴).
  - `main()` — 오늘 날짜로 전체 체크 실행 → 카드 생성 → `calc_oscillator.send_telegram` 발송 → 히스토리 저장. `if __name__=="__main__": main()`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_daily_verify.py`에 추가:

```python
def test_render_verify_card_all_ok_is_one_line():
    card = render_verify_card("2026-07-03", [], {"ok": True, "failed_tests": []},
                               {"active": True, "restarted": False})
    assert card.startswith("✅")
    assert "\n" not in card


def test_render_verify_card_shows_freshness_alert():
    card = render_verify_card(
        "2026-07-03",
        [{"source": "telegram", "today": 1, "avg": 10.0, "level": "orange"}],
        {"ok": True, "failed_tests": []}, {"active": True, "restarted": False})
    assert "⚠️" in card
    assert "telegram" in card


def test_render_verify_card_shows_pytest_failures():
    card = render_verify_card(
        "2026-07-03", [],
        {"ok": False, "failed_tests": ["tests/test_a.py::test_one"]},
        {"active": True, "restarted": False})
    assert "test_one" in card


def test_render_verify_card_shows_service_restart():
    card = render_verify_card(
        "2026-07-03", [], {"ok": True, "failed_tests": []},
        {"active": True, "restarted": True})
    assert "재시작" in card


def test_save_and_load_verify_history_roundtrip(tmp_path):
    path = str(tmp_path / "hist.json")
    save_verify_counts(path, "2026-07-03", {"telegram": 5, "news": 10})
    hist = load_verify_history(path)
    assert hist["2026-07-03"] == {"telegram": 5, "news": 10}


def test_save_verify_counts_keeps_only_14_days(tmp_path):
    path = str(tmp_path / "hist.json")
    for i in range(1, 20):
        save_verify_counts(path, f"2026-06-{i:02d}", {"telegram": i})
    hist = load_verify_history(path)
    assert len(hist) == 14
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_daily_verify.py -v -k "render_verify_card or verify_history"`
Expected: FAIL — `ImportError: cannot import name 'render_verify_card'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/daily_verify.py`에 `import json` 추가(이미 없다면), 파일 끝에 추가:

```python
def render_verify_card(date_str: str, freshness_alerts: list[dict],
                         pytest_result: dict, service_result: dict) -> str:
    problems = bool(freshness_alerts) or not pytest_result.get("ok", True) \
        or service_result.get("restarted") or service_result.get("active") is False

    if not problems:
        return f"✅ 일일검증 {date_str} 정상 — pytest ok, stockbrain active"

    lines = [f"⚠️ 일일검증 {date_str} — 확인 필요"]
    for a in freshness_alerts:
        lines.append(f"🟠 {a['source']} 신선도 저하: 오늘 {a['today']}건"
                      f"(평균 {a['avg']:.1f}건)")
    if not pytest_result.get("ok", True):
        lines.append(f"🔴 pytest 실패: {', '.join(pytest_result['failed_tests'])}")
    if service_result.get("restarted"):
        status = "복구됨" if service_result.get("active") else "재시작해도 실패"
        lines.append(f"🟡 stockbrain 서비스 재시작 시도됨 — {status}")
    elif service_result.get("active") is False:
        lines.append("🔴 stockbrain 서비스 비활성 상태(재시작 시도 안 됨)")
    return "\n".join(lines)


def load_verify_history(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_verify_counts(path: str, date_str: str, counts: dict) -> None:
    hist = load_verify_history(path)
    hist[date_str] = counts
    for d in sorted(hist)[:-14]:
        del hist[d]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    history_path = os.path.join(root, "pipeline", "atoms", "daily_verify_history.json")
    raw_root = os.path.join(root, "raw")
    sources = ["telegram", "news", "report"]
    today = datetime.now().strftime("%Y-%m-%d")

    history = load_verify_history(history_path)
    freshness_alerts = check_crawl_freshness(raw_root, sources, history, today)
    pytest_result = run_pytest_check(root)
    service_result = check_service_health("stockbrain")

    card = render_verify_card(today, freshness_alerts, pytest_result, service_result)
    print(card)
    try:
        import sys as _sys
        _sys.path.insert(0, root)
        from calc_oscillator import send_telegram
        send_telegram(card)
    except Exception as e:
        print(f"  [일일검증] 텔레 발송 생략: {e}")

    today_counts = {s: count_today_files(raw_root, s, today) for s in sources}
    save_verify_counts(history_path, today, today_counts)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_daily_verify.py -v`
Expected: 17 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/daily_verify.py tests/test_daily_verify.py
git commit -m "feat(verify): 통합 리포트+히스토리 저장+main() 완성"
```

---

### Task 4: 원격서버 배포 + 크론 등록 + 실제 실행 검증

**Files:**
- 없음(코드 변경 없음 — 배포/설정 작업)

**Interfaces:**
- Consumes: Task 1-3에서 완성된 `scripts/daily_verify.py`
- Produces: 없음(최종 배포 태스크)

- [ ] **Step 1: 로컬에서 전체 테스트 재확인**

Run: `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" -m pytest tests/test_daily_verify.py -v`
Expected: 17 passed

- [ ] **Step 2: main() 실제 동작 1회 로컬 확인(텔레 발송은 실제로 됨에 유의)**

Run: `cd "C:\Users\TheRose\Desktop\로또의 주식" && "C:\Users\TheRose\AppData\Local\Python\bin\python.exe" scripts/daily_verify.py`
Expected: 콘솔에 카드 텍스트 출력, 텔레그램에 실제 카드 1건 수신 확인(정상이면 1줄, 히스토리 부족으로 크롤링 경보는 없을 가능성 높음 — 정상 동작).

- [ ] **Step 3: 원격서버에 git pull로 배포**

원격서버에서 `git branch --show-current`로 main 확인 후, uncommitted 변경 있으면 `git stash push -m ...`, `git pull --no-rebase`, 필요시 `git stash pop`. (이 저장소의 표준 배포 절차 — 다른 세션과 공유 워킹트리이므로 매번 필수.)

- [ ] **Step 4: 원격서버에서 sudo 권한 확인(서비스 재시작에 필요)**

Run(원격서버 SSH): `sudo -n systemctl is-active stockbrain`
Expected: `active` 출력, 비밀번호 프롬프트 없이 성공(ubuntu 유저가 systemctl에 대해 NOPASSWD sudo 권한이 있는지 확인 — 없으면 Task2의 `check_service_health`가 재시작 시도 시 계속 실패하므로, 이 경우 crontab을 `sudo`로 등록하거나 `/etc/sudoers.d/`에 `ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart stockbrain` 한 줄 추가 필요 — 있으면 다음 스텝으로).

- [ ] **Step 5: 원격서버 크론에 등록**

Run(원격서버 SSH): `crontab -e`로 기존 7줄 유지한 채 아래 한 줄 추가(21시 인제스트 직후):
```
30 21 * * * cd /home/ubuntu/lotto-stock-wiki && /home/ubuntu/venv/bin/python scripts/daily_verify.py >> /tmp/daily_verify.log 2>&1
```
Run: `crontab -l`로 8줄 모두 있는지 확인.

- [ ] **Step 6: 원격서버에서 1회 수동 실행으로 최종 검증**

Run(원격서버 SSH): `cd /home/ubuntu/lotto-stock-wiki && /home/ubuntu/venv/bin/python scripts/daily_verify.py`
Expected: 에러 없이 완료, 텔레그램에 카드 수신, `pipeline/atoms/daily_verify_history.json` 생성 확인(`cat` 또는 `ls`).

- [ ] **Step 7: 커밋(크론 등록은 코드가 아니므로 커밋 대상 없음 — 생략하고 세션 로그에만 기록)**
