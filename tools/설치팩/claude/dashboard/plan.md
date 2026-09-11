# 일일 프로젝트 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 5개 진행 프로젝트(스탁브레인, 유튜브 자동화, 쇼핑쇼츠 자동화, SEO 워드프레스 자동화, 위키창고)의 일일 진행상황을 세션 종료 시 자동 기록하고, 카드 그리드 Artifact 대시보드로 보여준다.

**Architecture:** `~/.claude/dashboard/`에 `config.json`(카테고리+경로힌트+Artifact URL)과 `log.json`(날짜별 요약 로그)을 두고, 순수 함수 `render_dashboard.build_html()`이 이 둘로부터 `dashboard.html`을 생성한다. `dashboard_cli.py`가 로그 추가+정리+렌더링을 한 번에 처리하고, 전역 Stop 훅(`stop_hook.py`)이 세션 종료 시 cwd로 카테고리를 매칭해 Claude에게 CLI 실행 + Artifact 재발행을 지시한다.

**Tech Stack:** Python 표준 라이브러리만 사용(외부 의존성 없음), Windows에서 `py` 런처로 실행, pytest로 테스트.

## Global Constraints

- 모든 파일 I/O는 `encoding="utf-8"` 명시, JSON 직렬화는 `ensure_ascii=False` (한글 그대로 저장).
- Python 실행은 `py` 런처 사용 (이 환경에서 검증된 방식, [[project-lotto-stock-gemini-keys]] 관련 메모 참고).
- 외부 패키지 설치 없음 — 표준 라이브러리(`json`, `argparse`, `pathlib`, `datetime`, `html`)만.
- 카테고리 이름은 `config.json`의 5개 문자열과 정확히 일치해야 함 (오타/변형 불허).
- 7일 보관 기준은 ISO 날짜 문자열(`YYYY-MM-DD`) 비교로 계산.
- 테스트는 `C:\Users\TheRose\.claude\dashboard` 디렉토리에서 `py -m pytest` 로 실행.
- 이 위치는 git 저장소가 아니므로 커밋 단계는 생략.

---

### Task 1: 디렉토리·데이터 스캐폴딩

**Files:**
- Create: `C:\Users\TheRose\.claude\dashboard\config.json`
- Create: `C:\Users\TheRose\.claude\dashboard\log.json`

**Interfaces:**
- Produces: `config.json` 스키마 `{"categories": [{"name": str, "path_hints": [str]}], "artifact_url": str|null}`, `log.json` 스키마 `[{"date": "YYYY-MM-DD", "category": str, "summary": str, "next": str}]` — 이후 모든 태스크가 이 스키마에 의존.

- [ ] **Step 1: `config.json` 작성**

```json
{
  "categories": [
    {"name": "스탁브레인", "path_hints": ["C:\\Users\\TheRose\\Desktop\\로또의 주식"]},
    {"name": "유튜브 자동화", "path_hints": []},
    {"name": "쇼핑쇼츠 자동화", "path_hints": []},
    {"name": "SEO 워드프레스 자동화", "path_hints": []},
    {"name": "위키창고", "path_hints": ["C:\\Users\\TheRose\\knowledge-wiki"]}
  ],
  "artifact_url": null
}
```

- [ ] **Step 2: `log.json` 작성**

```json
[]
```

- [ ] **Step 3: JSON 유효성 확인**

Run: `py -c "import json,pathlib; json.loads(pathlib.Path('C:/Users/TheRose/.claude/dashboard/config.json').read_text(encoding='utf-8')); json.loads(pathlib.Path('C:/Users/TheRose/.claude/dashboard/log.json').read_text(encoding='utf-8')); print('ok')"`
Expected: `ok`

---

### Task 2: `render_dashboard.py` — HTML 렌더링

**Files:**
- Create: `C:\Users\TheRose\.claude\dashboard\render_dashboard.py`
- Test: `C:\Users\TheRose\.claude\dashboard\test_render_dashboard.py`

**Interfaces:**
- Consumes: Task 1의 `config.json`/`log.json` 스키마.
- Produces: `build_html(config: dict, log: list) -> str` — Task 3의 `dashboard_cli.render()`가 이 함수를 그대로 호출.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
from datetime import date
from render_dashboard import build_html


def test_build_html_shows_latest_summary_and_next():
    config = {"categories": [{"name": "스탁브레인", "path_hints": []}]}
    log = [{"date": date.today().isoformat(), "category": "스탁브레인", "summary": "요약1", "next": "다음1"}]
    result = build_html(config, log)
    assert "요약1" in result
    assert "다음1" in result
    assert "스탁브레인" in result


def test_build_html_missing_entry_shows_placeholder():
    config = {"categories": [{"name": "위키창고", "path_hints": []}]}
    result = build_html(config, [])
    assert "(기록 없음)" in result


def test_build_html_minilog_marks_todays_entry():
    config = {"categories": [{"name": "스탁브레인", "path_hints": []}]}
    log = [{"date": date.today().isoformat(), "category": "스탁브레인", "summary": "s", "next": "n"}]
    result = build_html(config, log)
    assert "●" in result
```

Save as `test_render_dashboard.py`.

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest test_render_dashboard.py -v` (in `C:\Users\TheRose\.claude\dashboard`)
Expected: FAIL — `ModuleNotFoundError: No module named 'render_dashboard'`

- [ ] **Step 3: `render_dashboard.py` 구현**

```python
"""Pure HTML rendering for the daily project dashboard."""
from datetime import date, timedelta
import html


def _mini_log(log, category, days=7):
    today = date.today()
    marks = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        has_entry = any(e["date"] == d and e["category"] == category for e in log)
        marks.append("●" if has_entry else "○")
    return "".join(marks)


def _latest_entry(log, category):
    matches = [e for e in log if e["category"] == category]
    if not matches:
        return None
    return sorted(matches, key=lambda e: e["date"])[-1]


def build_html(config, log):
    cards = []
    for cat in config["categories"]:
        name = cat["name"]
        latest = _latest_entry(log, name)
        summary = html.escape(latest["summary"]) if latest else "(기록 없음)"
        next_step = html.escape(latest["next"]) if latest else "(기록 없음)"
        mini = _mini_log(log, name)
        cards.append(f"""
<section class="card">
  <h2>{html.escape(name)}</h2>
  <p class="summary"><strong>현재:</strong> {summary}</p>
  <p class="next"><strong>다음:</strong> {next_step}</p>
  <p class="minilog">{mini}</p>
</section>""")
    body = "\n".join(cards)
    return f"""<title>프로젝트 대시보드</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: system-ui, sans-serif; margin: 0; padding: 2rem; background: #fff; color: #111; }}
@media (prefers-color-scheme: dark) {{ body {{ background: #111; color: #eee; }} }}
:root[data-theme="dark"] body {{ background: #111; color: #eee; }}
:root[data-theme="light"] body {{ background: #fff; color: #111; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; max-width: 100%; }}
.card {{ border: 1px solid #8888; border-radius: 8px; padding: 1rem; overflow-x: auto; }}
.card h2 {{ margin: 0 0 0.5rem; font-size: 1.1rem; }}
.minilog {{ font-size: 1.2rem; letter-spacing: 0.2rem; }}
</style>
<div class="grid">
{body}
</div>
"""
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest test_render_dashboard.py -v`
Expected: 3 passed

---

### Task 3: `dashboard_cli.py` — 로그 추가·정리·렌더링

**Files:**
- Create: `C:\Users\TheRose\.claude\dashboard\dashboard_cli.py`
- Test: `C:\Users\TheRose\.claude\dashboard\test_dashboard_cli.py`

**Interfaces:**
- Consumes: `render_dashboard.build_html(config, log)` (Task 2).
- Produces: `add_entry(category: str, summary: str, next_step: str) -> None`, `render() -> None` — Task 6이 커맨드라인에서 `add` 서브커맨드로 이 함수를 호출.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import json
from datetime import date, timedelta

import dashboard_cli as cli


def _init_files(tmp_path, monkeypatch):
    config = {
        "categories": [
            {"name": "스탁브레인", "path_hints": []},
            {"name": "위키창고", "path_hints": []},
        ],
        "artifact_url": None,
    }
    config_path = tmp_path / "config.json"
    log_path = tmp_path / "log.json"
    html_path = tmp_path / "dashboard.html"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    log_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(cli, "CONFIG_PATH", config_path)
    monkeypatch.setattr(cli, "LOG_PATH", log_path)
    monkeypatch.setattr(cli, "HTML_PATH", html_path)
    return config_path, log_path, html_path


def test_add_entry_appends_and_renders(tmp_path, monkeypatch):
    _config, log_path, html_path = _init_files(tmp_path, monkeypatch)
    cli.add_entry("스탁브레인", "오늘 요약", "다음 할일")
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(log) == 1
    assert log[0]["category"] == "스탁브레인"
    assert log[0]["summary"] == "오늘 요약"
    assert html_path.exists()
    assert "오늘 요약" in html_path.read_text(encoding="utf-8")


def test_add_entry_same_day_replaces_not_duplicates(tmp_path, monkeypatch):
    _config, log_path, _html = _init_files(tmp_path, monkeypatch)
    cli.add_entry("스탁브레인", "첫 요약", "첫 다음")
    cli.add_entry("스탁브레인", "수정된 요약", "수정된 다음")
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(log) == 1
    assert log[0]["summary"] == "수정된 요약"


def test_add_entry_unknown_category_raises(tmp_path, monkeypatch):
    _init_files(tmp_path, monkeypatch)
    try:
        cli.add_entry("존재안함", "s", "n")
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_prune_removes_entries_older_than_7_days(tmp_path, monkeypatch):
    _config, log_path, _html = _init_files(tmp_path, monkeypatch)
    old_date = (date.today() - timedelta(days=10)).isoformat()
    log_path.write_text(json.dumps([
        {"date": old_date, "category": "스탁브레인", "summary": "old", "next": "old"}
    ], ensure_ascii=False), encoding="utf-8")
    cli.add_entry("스탁브레인", "새 요약", "새 다음")
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert all(e["date"] != old_date for e in log)
```

Save as `test_dashboard_cli.py`.

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest test_dashboard_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard_cli'`

- [ ] **Step 3: `dashboard_cli.py` 구현**

```python
"""CLI to append a daily log entry and regenerate the dashboard HTML."""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from render_dashboard import build_html

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
LOG_PATH = BASE / "log.json"
HTML_PATH = BASE / "dashboard.html"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_log():
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def save_log(log):
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def prune(log, days=7):
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    return [e for e in log if e["date"] >= cutoff]


def category_names(config):
    return [c["name"] for c in config["categories"]]


def add_entry(category, summary, next_step):
    config = load_config()
    if category not in category_names(config):
        raise SystemExit(f"unknown category: {category!r}, must be one of {category_names(config)}")
    log = load_log()
    today = date.today().isoformat()
    log = [e for e in log if not (e["date"] == today and e["category"] == category)]
    log.append({"date": today, "category": category, "summary": summary, "next": next_step})
    log = prune(log)
    save_log(log)
    render()


def render():
    config = load_config()
    log = load_log()
    HTML_PATH.write_text(build_html(config, log), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add")
    add_p.add_argument("--category", required=True)
    add_p.add_argument("--summary", required=True)
    add_p.add_argument("--next", required=True, dest="next_step")

    sub.add_parser("render")

    args = parser.parse_args(argv)
    if args.command == "add":
        add_entry(args.category, args.summary, args.next_step)
    elif args.command == "render":
        render()


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest test_dashboard_cli.py -v`
Expected: 4 passed

---

### Task 4: `stop_hook.py` — 카테고리 매칭 + Stop 차단 로직

**Files:**
- Create: `C:\Users\TheRose\.claude\dashboard\stop_hook.py`
- Test: `C:\Users\TheRose\.claude\dashboard\test_stop_hook.py`

**Interfaces:**
- Consumes: Task 1의 `config.json` 스키마 (`categories[].path_hints`).
- Produces: `match_category(cwd: str, config: dict) -> str | None` — Task 5 이후 실제 훅 실행시 `main()`이 내부적으로 호출.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import stop_hook


def test_match_category_returns_name_for_exact_path(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    config = {"categories": [{"name": "스탁브레인", "path_hints": [str(project_dir)]}]}
    assert stop_hook.match_category(str(project_dir), config) == "스탁브레인"


def test_match_category_returns_name_for_subdirectory(tmp_path):
    project_dir = tmp_path / "project"
    sub_dir = project_dir / "sub"
    sub_dir.mkdir(parents=True)
    config = {"categories": [{"name": "스탁브레인", "path_hints": [str(project_dir)]}]}
    assert stop_hook.match_category(str(sub_dir), config) == "스탁브레인"


def test_match_category_returns_none_for_unrelated_path(tmp_path):
    project_dir = tmp_path / "project"
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    config = {"categories": [{"name": "스탁브레인", "path_hints": [str(project_dir)]}]}
    assert stop_hook.match_category(str(other_dir), config) is None
```

Save as `test_stop_hook.py`.

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest test_stop_hook.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stop_hook'`

- [ ] **Step 3: `stop_hook.py` 구현**

```python
"""Stop hook: prompts a per-session dashboard log entry for known project paths."""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"


def match_category(cwd, config):
    cwd_norm = str(Path(cwd).resolve()).lower()
    for cat in config["categories"]:
        for hint in cat.get("path_hints", []):
            hint_norm = str(Path(hint).resolve()).lower()
            if cwd_norm == hint_norm or cwd_norm.startswith(hint_norm + "\\"):
                return cat["name"]
    return None


def main():
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    category = match_category(payload.get("cwd", ""), config)
    if category is None:
        return
    artifact_url = config.get("artifact_url")
    cli_path = BASE / "dashboard_cli.py"
    html_path = BASE / "dashboard.html"
    if artifact_url:
        publish_step = f'2) Artifact 도구로 `{html_path}` 를 url="{artifact_url}" 로 재발행'
    else:
        publish_step = f"2) Artifact 도구로 `{html_path}` 를 새로 발행하고, 반환된 url을 config.json의 artifact_url에 저장"
    reason = (
        f"이 세션은 '{category}' 프로젝트 작업입니다. 종료 전에 다음을 하세요: "
        f'1) `py "{cli_path}" add --category "{category}" --summary "<오늘 한 일 1~3줄>" --next "<다음 할 일>"` 실행 '
        f"{publish_step}."
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest test_stop_hook.py -v`
Expected: 3 passed

---

### Task 5: `install_hook.py` — 전역 Stop 훅 등록

**Files:**
- Create: `C:\Users\TheRose\.claude\dashboard\install_hook.py`
- Test: `C:\Users\TheRose\.claude\dashboard\test_install_hook.py`

**Interfaces:**
- Consumes: Task 4의 `stop_hook.py` 경로.
- Produces: `~/.claude/settings.json`에 `hooks.Stop` 항목 추가 (idempotent).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import json

import install_hook


def test_install_hook_adds_stop_entry_when_missing(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"other": "value"}), encoding="utf-8")
    monkeypatch.setattr(install_hook, "SETTINGS_PATH", settings_path)
    install_hook.main()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["other"] == "value"
    assert len(settings["hooks"]["Stop"]) == 1
    assert settings["hooks"]["Stop"][0]["hooks"][0]["command"] == install_hook.HOOK_COMMAND


def test_install_hook_is_idempotent(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(install_hook, "SETTINGS_PATH", settings_path)
    install_hook.main()
    install_hook.main()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert len(settings["hooks"]["Stop"]) == 1
```

Save as `test_install_hook.py`.

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest test_install_hook.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'install_hook'`

- [ ] **Step 3: `install_hook.py` 구현**

```python
"""Idempotently register the dashboard Stop hook in the global Claude Code settings."""
import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
HOOK_COMMAND = f'py "{Path(__file__).resolve().parent / "stop_hook.py"}"'


def main():
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8")) if SETTINGS_PATH.exists() else {}
    hooks = settings.setdefault("hooks", {})
    stop_entries = hooks.setdefault("Stop", [])
    for entry in stop_entries:
        for h in entry.get("hooks", []):
            if h.get("command") == HOOK_COMMAND:
                print("already installed")
                return
    stop_entries.append({
        "matcher": "",
        "hooks": [{"type": "command", "command": HOOK_COMMAND}],
    })
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    print("installed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest test_install_hook.py -v`
Expected: 2 passed

---

### Task 6: 초기 데이터 세팅 + 첫 발행 + 훅 설치 (인터랙티브 — 메인 대화에서 직접 수행, 서브에이전트에 위임 금지)

이 태스크는 실제 사용자에게 정보를 묻고, `Artifact` 도구를 호출해야 하므로 컨텍스트 없는 서브에이전트가 아니라 메인 대화 진행자가 직접 수행한다.

**Files:**
- Modify: `C:\Users\TheRose\.claude\dashboard\config.json` (유튜브 자동화/쇼핑쇼츠 자동화/SEO 워드프레스 자동화의 `path_hints` 채우기, `artifact_url` 채우기)
- Modify: `C:\Users\TheRose\.claude\dashboard\log.json` (5개 카테고리 초기 항목)
- Create: `C:\Users\TheRose\.claude\dashboard\dashboard.html` (렌더링 결과, Artifact 소스)
- Modify: `C:\Users\TheRose\.claude\settings.json` (Task 5의 `install_hook.py` 실행 결과)

- [ ] **Step 1: 3개 카테고리(유튜브 자동화/쇼핑쇼츠 자동화/SEO 워드프레스 자동화)의 실제 프로젝트 경로와 현재 상태·다음 할 일을 사용자에게 확인**

`AskUserQuestion` 또는 대화로 직접 질문. 확인된 경로를 `config.json`의 해당 `path_hints`에 채워 넣는다.

- [ ] **Step 2: 5개 카테고리 전부 초기 로그 항목 기록**

각 카테고리에 대해 실행 (스탁브레인/위키창고는 이번 세션에서 회수한 메모리 내용 기반, 나머지 3개는 Step 1에서 받은 내용 기반):

```
py "C:\Users\TheRose\.claude\dashboard\dashboard_cli.py" add --category "스탁브레인" --summary "<메모리 기반 현재상태>" --next "<다음 할일>"
```

5개 카테고리 모두 동일하게 반복.

- [ ] **Step 3: `dashboard.html` 생성 확인**

Run: `py -c "import pathlib; print(pathlib.Path('C:/Users/TheRose/.claude/dashboard/dashboard.html').exists())"`
Expected: `True`

- [ ] **Step 4: Artifact로 최초 발행**

`Artifact` 도구를 `file_path: C:\Users\TheRose\.claude\dashboard\dashboard.html`, `favicon`(이모지 1~2개, 예: "📋"), `description`으로 호출. 반환된 URL을 `config.json`의 `artifact_url`에 저장.

- [ ] **Step 5: 전역 Stop 훅 설치**

Run: `py "C:\Users\TheRose\.claude\dashboard\install_hook.py"`
Expected: `installed`

- [ ] **Step 6: 훅 동작 수동 검증**

Run (스탁브레인 경로를 cwd로 가정한 stdin 시뮬레이션):
`echo {"cwd": "C:\\Users\\TheRose\\Desktop\\로또의 주식", "stop_hook_active": false} | py "C:\Users\TheRose\.claude\dashboard\stop_hook.py"`
Expected: `{"decision": "block", "reason": "..."}` 형태의 JSON 한 줄 출력 (category가 "스탁브레인"으로 매칭됨을 reason 텍스트에서 확인)

Run (무관한 경로):
`echo {"cwd": "C:\\Users\\TheRose", "stop_hook_active": false} | py "C:\Users\TheRose\.claude\dashboard\stop_hook.py"`
Expected: 출력 없음 (카테고리 불일치 시 조용히 통과)
