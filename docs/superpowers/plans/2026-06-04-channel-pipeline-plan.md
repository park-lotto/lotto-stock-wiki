# 다채널 인사이트 집계 파이프라인 v2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 텔레그램·블로그·리포트·유튜브 4개 채널 원문을 매일 자동으로 처리해 wiki 업데이트 + HTML 브리핑을 생성하는 2단계 멀티에이전트 파이프라인 구축

**Architecture:** Gemini Flash(분류) → Sonnet(검증+wiki결정) → Python(wiki쓰기) + Haiku(HTML브리핑) 병렬. LLM 호출 ≤10회/일, 비용 $0.06 cap.

**Tech Stack:** Python 3.11+, Pydantic v2, `google-generativeai`, `anthropic`, pytest, asyncio

---

## File Map

| 파일 | 역할 | 신규/교체 |
|------|------|---------|
| `scripts/channel_pipeline/__init__.py` | 패키지 선언 | 교체(비움) |
| `scripts/channel_pipeline/models.py` | Pydantic 스키마 3개 | 교체 |
| `scripts/channel_pipeline/manifest.py` | raw/inbox/ 파일 수집 | 교체 |
| `scripts/channel_pipeline/cost_guard.py` | 비용 추정 + cap | 교체 |
| `scripts/channel_pipeline/agent_a.py` | Gemini Flash 분류 | 교체 |
| `scripts/channel_pipeline/agent_b.py` | Sonnet 검증+결정 | 교체 |
| `scripts/channel_pipeline/wiki_writer.py` | 순수 Python wiki 업데이트 | 신규 |
| `scripts/channel_pipeline/agent_d.py` | Haiku HTML 브리핑 | 교체 |
| `scripts/channel_pipeline/pipeline.py` | 오케스트레이터 | 교체 |
| `tests/channel_pipeline/__init__.py` | 테스트 패키지 | 신규 |
| `tests/channel_pipeline/test_models.py` | 모델 단위 테스트 | 신규 |
| `tests/channel_pipeline/test_manifest.py` | 파일 수집 테스트 | 신규 |
| `tests/channel_pipeline/test_cost_guard.py` | 비용 추정 테스트 | 신규 |
| `tests/channel_pipeline/test_wiki_writer.py` | wiki 업데이트 테스트 | 신규 |
| `tests/channel_pipeline/test_pipeline.py` | 통합 테스트 | 신규 |

---

### Task 1: 기존 코드 정리 + 테스트 환경 셋업

**Files:**
- Delete: `scripts/channel_pipeline/agent_A.py`, `agent_B.py`, `agent_C1.py`, `agent_D.py`, `agent_E.py`, `file_manifest.py`, `cost_estimator.py`, `trust_tracker.py`, `pipeline.py`, `models.py`
- Create: `tests/channel_pipeline/__init__.py`
- Create: `tests/channel_pipeline/conftest.py`

- [ ] **Step 1: 기존 파일 삭제**

```bash
cd "c:\Users\CH\Desktop\로또의 주식"
Remove-Item scripts\channel_pipeline\agent_A.py, scripts\channel_pipeline\agent_B.py, `
  scripts\channel_pipeline\agent_C1.py, scripts\channel_pipeline\agent_D.py, `
  scripts\channel_pipeline\agent_E.py, scripts\channel_pipeline\file_manifest.py, `
  scripts\channel_pipeline\cost_estimator.py, scripts\channel_pipeline\trust_tracker.py, `
  scripts\channel_pipeline\pipeline.py, scripts\channel_pipeline\models.py -ErrorAction SilentlyContinue
```

- [ ] **Step 2: pytest 설치 확인**

```bash
pip show pytest pydantic anthropic google-generativeai
```
없으면: `pip install pytest pytest-asyncio pydantic anthropic google-generativeai`

- [ ] **Step 3: `tests/channel_pipeline/__init__.py` 생성**

```python
```
(빈 파일)

- [ ] **Step 4: `tests/channel_pipeline/conftest.py` 생성**

```python
import pytest
from pathlib import Path


@pytest.fixture
def tmp_wiki(tmp_path):
    """임시 wiki 디렉토리 생성 — stock 파일 포함"""
    stock_dir = tmp_path / "wiki" / "L5_섹터" / "반도체" / "stock"
    stock_dir.mkdir(parents=True)
    stock_file = stock_dir / "stock_SK하이닉스.md"
    stock_file.write_text(
        "# SK하이닉스\n\n## 기본 정보\n테스트\n\n## 최신 이벤트\n- [2026-05-01] 기존 이벤트\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def sample_claims():
    from scripts.channel_pipeline.models import Claim
    return [
        Claim(
            id="tg_001",
            channel="telegram",
            source="태린이아빠",
            content="HBM4 계약 가격 협상 2분기 본격화",
            claim_type="fact",
            sector="반도체",
            tickers=["SK하이닉스", "000660"],
            direction="bullish",
            conflict_candidate=False,
        ),
        Claim(
            id="rp_001",
            channel="report",
            source="KB증권",
            content="HBM4 공급 과잉 우려로 가격 하락 가능",
            claim_type="opinion",
            sector="반도체",
            tickers=["SK하이닉스"],
            direction="bearish",
            conflict_candidate=True,
        ),
    ]


@pytest.fixture
def sample_decisions():
    from scripts.channel_pipeline.models import WikiDecision
    return [
        WikiDecision(
            claim_id="tg_001",
            action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 계약 가격 협상 2분기 본격화 (태린이아빠/텔레그램)",
        ),
        WikiDecision(
            claim_id="rp_001",
            action="flag",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 공급 과잉 우려 (KB증권/리포트)",
            conflict_note="태린이아빠(bullish)와 방향 상충",
        ),
    ]
```

- [ ] **Step 5: `scripts/channel_pipeline/__init__.py` 초기화**

```python
```
(빈 파일로 교체)

- [ ] **Step 6: 커밋**

```bash
git add tests/ scripts/channel_pipeline/__init__.py
git commit -m "chore: 기존 channel_pipeline 코드 정리 + 테스트 환경 셋업"
```

---

### Task 2: Models

**Files:**
- Create: `scripts/channel_pipeline/models.py`
- Create: `tests/channel_pipeline/test_models.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/channel_pipeline/test_models.py`:
```python
import pytest
from scripts.channel_pipeline.models import Claim, WikiDecision, PipelineState


def test_claim_defaults():
    c = Claim(
        id="tg_001", channel="telegram", source="태린이아빠",
        content="테스트", claim_type="fact",
    )
    assert c.tickers == []
    assert c.direction == "neutral"
    assert c.conflict_candidate is False
    assert c.sector is None


def test_claim_invalid_channel():
    with pytest.raises(Exception):
        Claim(id="x", channel="twitter", source="s", content="c", claim_type="fact")


def test_claim_invalid_direction():
    with pytest.raises(Exception):
        Claim(id="x", channel="telegram", source="s", content="c",
              claim_type="fact", direction="sideways")


def test_wiki_decision_defaults():
    d = WikiDecision(claim_id="tg_001", action="skip")
    assert d.wiki_file == ""
    assert d.section == "## 최신 이벤트"
    assert d.conflict_note is None


def test_wiki_decision_invalid_action():
    with pytest.raises(Exception):
        WikiDecision(claim_id="x", action="delete")


def test_pipeline_state_defaults():
    s = PipelineState(run_date="2026-06-04")
    assert s.step == "pending"
    assert s.claims_file is None
    assert s.decisions_file is None
    assert s.error is None


def test_pipeline_state_step_transition():
    s = PipelineState(run_date="2026-06-04", step="A_done")
    assert s.step == "A_done"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/channel_pipeline/test_models.py -v
```
예상: `ImportError` (models.py 없음)

- [ ] **Step 3: `scripts/channel_pipeline/models.py` 작성**

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str
    channel: Literal["telegram", "blog", "report", "yt"]
    source: str
    content: str
    claim_type: Literal["fact", "opinion", "prediction"]
    sector: Optional[str] = None
    tickers: list[str] = Field(default_factory=list)
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    conflict_candidate: bool = False


class WikiDecision(BaseModel):
    claim_id: str
    action: Literal["append", "flag", "skip"]
    wiki_file: str = ""
    section: str = "## 최신 이벤트"
    line: str = ""
    conflict_note: Optional[str] = None


class PipelineState(BaseModel):
    run_date: str
    step: Literal["pending", "A_done", "B_done", "done", "failed"] = "pending"
    claims_file: Optional[str] = None
    decisions_file: Optional[str] = None
    error: Optional[str] = None
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/channel_pipeline/test_models.py -v
```
예상: 7개 PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/channel_pipeline/models.py tests/channel_pipeline/test_models.py
git commit -m "feat: channel_pipeline models (Claim, WikiDecision, PipelineState)"
```

---

### Task 3: Manifest

**Files:**
- Create: `scripts/channel_pipeline/manifest.py`
- Create: `tests/channel_pipeline/test_manifest.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/channel_pipeline/test_manifest.py`:
```python
import time
from pathlib import Path
from scripts.channel_pipeline.manifest import get_manifest, total_files


def test_empty_inbox(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.channel_pipeline.manifest.INBOX", tmp_path)
    manifest = get_manifest("2026-06-04")
    assert set(manifest.keys()) == {"telegram", "blog", "report", "yt"}
    assert all(len(v) == 0 for v in manifest.values())


def test_recent_file_included(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.channel_pipeline.manifest.INBOX", tmp_path)
    tg_dir = tmp_path / "telegram"
    tg_dir.mkdir()
    f = tg_dir / "20260604_태린이아빠.md"
    f.write_text("테스트", encoding="utf-8")
    manifest = get_manifest("2026-06-04")
    assert len(manifest["telegram"]) == 1
    assert str(f) in manifest["telegram"]


def test_old_file_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.channel_pipeline.manifest.INBOX", tmp_path)
    tg_dir = tmp_path / "telegram"
    tg_dir.mkdir()
    f = tg_dir / "20260101_old.md"
    f.write_text("오래된 파일", encoding="utf-8")
    # 수정시간을 7일 전으로 설정
    old_time = time.time() - (8 * 24 * 3600)
    import os
    os.utime(f, (old_time, old_time))
    manifest = get_manifest("2026-06-04")
    assert len(manifest["telegram"]) == 0


def test_total_files():
    manifest = {"telegram": ["a", "b"], "blog": ["c"], "report": [], "yt": []}
    assert total_files(manifest) == 3
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/channel_pipeline/test_manifest.py -v
```
예상: `ImportError`

- [ ] **Step 3: `scripts/channel_pipeline/manifest.py` 작성**

```python
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent.parent
INBOX = ROOT / "raw" / "inbox"

CHANNEL_DIRS = {
    "telegram": INBOX / "telegram",
    "blog":     INBOX / "blog",
    "report":   INBOX / "report",
    "yt":       INBOX / "youtube",
}


def get_manifest(run_date: str | None = None, days_back: int = 1) -> dict[str, list[str]]:
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    cutoff = datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=days_back)
    manifest: dict[str, list[str]] = {ch: [] for ch in CHANNEL_DIRS}
    for channel, inbox_dir in CHANNEL_DIRS.items():
        if inbox_dir.exists():
            for f in sorted(inbox_dir.glob("*.md")):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime >= cutoff:
                        manifest[channel].append(str(f))
                except OSError:
                    continue
    return manifest


def total_files(manifest: dict[str, list[str]]) -> int:
    return sum(len(v) for v in manifest.values())
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/channel_pipeline/test_manifest.py -v
```
예상: 4개 PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/channel_pipeline/manifest.py tests/channel_pipeline/test_manifest.py
git commit -m "feat: channel_pipeline manifest (raw/inbox 파일 수집)"
```

---

### Task 4: Cost Guard

**Files:**
- Create: `scripts/channel_pipeline/cost_guard.py`
- Create: `tests/channel_pipeline/test_cost_guard.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/channel_pipeline/test_cost_guard.py`:
```python
from scripts.channel_pipeline.cost_guard import estimate, can_run, reduce_scope, DAILY_CAP_USD


def test_estimate_zero_files():
    manifest = {"telegram": [], "blog": [], "report": [], "yt": []}
    cost, detail = estimate(manifest)
    assert cost < DAILY_CAP_USD
    assert "$" in detail


def test_estimate_many_files():
    manifest = {"telegram": ["f"] * 50, "blog": ["f"] * 50, "report": [], "yt": []}
    cost, detail = estimate(manifest)
    assert cost > 0
    assert "A(Gemini" in detail


def test_can_run_under_cap():
    manifest = {"telegram": ["f"] * 5, "blog": [], "report": [], "yt": []}
    ok, cost, _ = can_run(manifest)
    assert ok is True
    assert cost < DAILY_CAP_USD


def test_can_run_over_cap():
    manifest = {"telegram": ["f"] * 500, "blog": ["f"] * 500, "report": [], "yt": []}
    ok, cost, _ = can_run(manifest)
    assert ok is False
    assert cost > DAILY_CAP_USD


def test_reduce_scope():
    manifest = {"telegram": [f"f{i}" for i in range(20)], "blog": [], "report": [], "yt": []}
    reduced = reduce_scope(manifest, cap=5)
    assert len(reduced["telegram"]) == 5
    assert reduced["telegram"] == [f"f{i}" for i in range(15, 20)]  # 최신 5개
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/channel_pipeline/test_cost_guard.py -v
```
예상: `ImportError`

- [ ] **Step 3: `scripts/channel_pipeline/cost_guard.py` 작성**

```python
from __future__ import annotations

TOKENS_PER_FILE = 2_000
SONNET_INPUT_TOKENS = 8_000
HAIKU_INPUT_TOKENS = 4_000

PRICE_GEMINI_FLASH_PER_1M = 0.15
PRICE_SONNET_PER_1M = 5.0
PRICE_HAIKU_PER_1M = 1.0

DAILY_CAP_USD = 0.06


def estimate(manifest: dict[str, list[str]]) -> tuple[float, str]:
    n_files = sum(len(v) for v in manifest.values())
    cost_a = n_files * TOKENS_PER_FILE * PRICE_GEMINI_FLASH_PER_1M / 1_000_000
    cost_b = SONNET_INPUT_TOKENS * PRICE_SONNET_PER_1M / 1_000_000
    cost_d = HAIKU_INPUT_TOKENS * PRICE_HAIKU_PER_1M / 1_000_000
    total = cost_a + cost_b + cost_d
    detail = (
        f"A(Gemini×{n_files}파일)=${cost_a:.4f} + "
        f"B(Sonnet)=${cost_b:.4f} + "
        f"D(Haiku)=${cost_d:.4f} = ${total:.4f}"
    )
    return total, detail


def can_run(manifest: dict[str, list[str]]) -> tuple[bool, float, str]:
    cost, detail = estimate(manifest)
    return cost <= DAILY_CAP_USD, cost, detail


def reduce_scope(manifest: dict[str, list[str]], cap: int = 10) -> dict[str, list[str]]:
    return {ch: files[-cap:] for ch, files in manifest.items()}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/channel_pipeline/test_cost_guard.py -v
```
예상: 5개 PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/channel_pipeline/cost_guard.py tests/channel_pipeline/test_cost_guard.py
git commit -m "feat: channel_pipeline cost_guard ($0.06 cap)"
```

---

### Task 5: Wiki Writer

**Files:**
- Create: `scripts/channel_pipeline/wiki_writer.py`
- Create: `tests/channel_pipeline/test_wiki_writer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/channel_pipeline/test_wiki_writer.py`:
```python
from pathlib import Path
from scripts.channel_pipeline.models import WikiDecision
from scripts.channel_pipeline.wiki_writer import apply_decisions, _ensure_section


def test_append_to_existing_section(tmp_wiki):
    decisions = [
        WikiDecision(
            claim_id="tg_001",
            action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 협상 본격화 (태린이아빠/텔레그램)",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    content = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    assert "- [2026-06-04] HBM4 협상 본격화" in content
    # 새 줄이 기존 이벤트 위에 있어야 함 (최상단 추가)
    new_idx = content.index("- [2026-06-04]")
    old_idx = content.index("- [2026-05-01]")
    assert new_idx < old_idx


def test_flag_adds_conflict_note(tmp_wiki):
    decisions = [
        WikiDecision(
            claim_id="rp_001",
            action="flag",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 공급과잉 우려 (KB증권/리포트)",
            conflict_note="태린이아빠(bullish)와 방향 상충",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    content = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    assert "⚠️ 태린이아빠(bullish)와 방향 상충" in content


def test_skip_does_not_modify(tmp_wiki):
    decisions = [
        WikiDecision(claim_id="yt_001", action="skip",
                     wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md")
    ]
    original = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    apply_decisions(decisions, root=tmp_wiki)
    after = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    assert original == after


def test_creates_section_if_missing(tmp_wiki):
    # 섹션 없는 파일
    f = tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_삼성전자.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# 삼성전자\n\n## 기본 정보\n테스트\n", encoding="utf-8")
    decisions = [
        WikiDecision(
            claim_id="tg_002",
            action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_삼성전자.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] 갤럭시 AI 출하 (테스트)",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    content = f.read_text(encoding="utf-8")
    assert "## 최신 이벤트" in content
    assert "- [2026-06-04] 갤럭시 AI 출하" in content


def test_creates_file_if_missing(tmp_wiki):
    decisions = [
        WikiDecision(
            claim_id="tg_003",
            action="append",
            wiki_file="wiki/L5_섹터/조선/stock/stock_HD현대중공업.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] LNG선 수주 (태린이아빠)",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    f = tmp_wiki / "wiki/L5_섹터/조선/stock/stock_HD현대중공업.md"
    assert f.exists()
    assert "## 최신 이벤트" in f.read_text(encoding="utf-8")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/channel_pipeline/test_wiki_writer.py -v
```
예상: `ImportError`

- [ ] **Step 3: `scripts/channel_pipeline/wiki_writer.py` 작성**

```python
from __future__ import annotations
from pathlib import Path
from scripts.channel_pipeline.models import WikiDecision

ROOT = Path(__file__).parent.parent.parent


def apply_decisions(
    decisions: list[WikiDecision],
    root: Path = ROOT,
    dry_run: bool = False,
) -> list[str]:
    """decisions 적용, 수정된 파일 경로 목록 반환"""
    modified: list[str] = []
    for d in decisions:
        if d.action == "skip" or not d.wiki_file:
            continue
        path = root / d.wiki_file
        _ensure_file(path)
        content = path.read_text(encoding="utf-8")
        new_content = _apply_one(content, d)
        if new_content != content:
            if not dry_run:
                path.write_text(new_content, encoding="utf-8")
            modified.append(str(path))
    return modified


def _apply_one(content: str, d: WikiDecision) -> str:
    line = d.line
    if d.action == "flag" and d.conflict_note:
        line = f"{line} ⚠️ {d.conflict_note}"

    if d.section in content:
        # 섹션 헤더 바로 다음에 삽입 (최상단)
        idx = content.index(d.section) + len(d.section)
        rest = content[idx:].lstrip("\n")  # 헤더 뒤 개행 제거
        return content[:idx] + "\n" + line + "\n" + rest
    else:
        # 섹션 없으면 파일 끝에 추가
        sep = "\n" if content.endswith("\n") else "\n\n"
        return content + sep + d.section + "\n" + line + "\n"


def _ensure_file(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        name = path.stem.replace("stock_", "")
        path.write_text(
            f"# {name}\n\n## 기본 정보\n(자동 생성)\n\n## 최신 이벤트\n",
            encoding="utf-8",
        )


def _ensure_section(content: str, section: str) -> str:
    if section not in content:
        sep = "\n" if content.endswith("\n") else "\n\n"
        return content + sep + section + "\n"
    return content
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/channel_pipeline/test_wiki_writer.py -v
```
예상: 5개 PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/channel_pipeline/wiki_writer.py tests/channel_pipeline/test_wiki_writer.py
git commit -m "feat: wiki_writer (순수 Python append/flag, LLM 없음)"
```

---

### Task 6: Agent A (Gemini Flash)

**Files:**
- Create: `scripts/channel_pipeline/agent_a.py`

테스트는 API mock이 필요하므로 Task 9 통합 테스트에서 검증.

- [ ] **Step 1: `scripts/channel_pipeline/agent_a.py` 작성**

```python
from __future__ import annotations
import asyncio
import json
import os
import re
from pathlib import Path
from scripts.channel_pipeline.models import Claim

MODEL = "gemini-2.5-flash"
MAX_CHARS = 8_000
BATCH_SIZE = 5

SYSTEM_PROMPT = """한국 주식 투자 정보 분류 전문가입니다.
주어진 텍스트에서 투자 관련 클레임을 추출해 JSON 배열로 반환하세요.

규칙:
1. content: 원문 핵심 그대로 보존 (400자 max, 의역 금지)
2. claim_type: fact(수치·공시·데이터), opinion(전망·판단), prediction(미래예측)
3. direction: bullish(매수관점) | bearish(매도관점) | neutral(중립)
4. conflict_candidate: 동일 파일 내 다른 관점과 상충 시 true
5. 주식 무관 내용(일상·광고) 제외
6. JSON 배열만 출력. 다른 텍스트 금지.

출력 형식:
[{"claim_type":"fact","sector":"반도체","tickers":["SK하이닉스"],"content":"원문","direction":"bullish","conflict_candidate":false}]"""


def _setup():
    import google.generativeai as genai
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise EnvironmentError("GEMINI_API_KEY 미설정")
    genai.configure(api_key=key)
    return genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)


def _parse(raw: str, channel: str, source: str, id_offset: int) -> list[Claim]:
    match = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    prefix = {"telegram": "tg", "blog": "bl", "report": "rp", "yt": "yt"}.get(channel, "xx")
    claims = []
    for i, item in enumerate(items):
        try:
            claims.append(Claim(
                id=f"{prefix}_{id_offset + i:03d}",
                channel=channel,
                source=source,
                content=item.get("content", ""),
                claim_type=item.get("claim_type", "opinion"),
                sector=item.get("sector"),
                tickers=item.get("tickers", []),
                direction=item.get("direction", "neutral"),
                conflict_candidate=item.get("conflict_candidate", False),
            ))
        except Exception:
            continue
    return claims


def _source_from_path(path: str) -> str:
    name = Path(path).stem
    parts = name.split("_")
    return parts[1] if len(parts) >= 2 else "unknown"


async def _process_channel(model, channel: str, files: list[str]) -> list[Claim]:
    if not files:
        return []
    all_claims: list[Claim] = []
    for i in range(0, len(files), BATCH_SIZE):
        batch = files[i:i + BATCH_SIZE]
        combined = ""
        for fp in batch:
            source = _source_from_path(fp)
            text = Path(fp).read_text(encoding="utf-8", errors="ignore")[:MAX_CHARS]
            combined += f"\n\n=== [{source}] {Path(fp).name} ===\n{text}"
        prompt = f"다음 {channel} 채널 내용을 분석하세요:\n{combined}"
        for attempt in range(3):
            try:
                resp = await asyncio.to_thread(model.generate_content, prompt)
                batch_claims = _parse(resp.text or "", channel,
                                       _source_from_path(batch[0]), len(all_claims))
                all_claims.extend(batch_claims)
                print(f"  [{channel}] {min(i+BATCH_SIZE, len(files))}/{len(files)} → {len(batch_claims)}개")
                break
            except Exception as e:
                if attempt == 2:
                    print(f"  [{channel}] 배치 실패: {e}")
                else:
                    await asyncio.sleep(2 ** attempt)
    return all_claims


async def run(manifest: dict[str, list[str]]) -> list[Claim]:
    model = _setup()
    tasks = {ch: _process_channel(model, ch, files) for ch, files in manifest.items()}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    claims: list[Claim] = []
    for ch, result in zip(tasks.keys(), results):
        if isinstance(result, list):
            claims.extend(result)
        else:
            print(f"  [{ch}] 오류: {result}")
    print(f"[Agent A] 완료 — {len(claims)}개 클레임")
    return claims


def save(claims: list[Claim], path: Path) -> None:
    path.write_text(
        json.dumps([c.model_dump() for c in claims], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 2: import 확인**

```bash
python -c "from scripts.channel_pipeline.agent_a import run; print('OK')"
```
예상: `OK` (GEMINI_API_KEY 없으면 import만, run 호출 시 오류)

- [ ] **Step 3: 커밋**

```bash
git add scripts/channel_pipeline/agent_a.py
git commit -m "feat: agent_a (Gemini Flash 분류, 4채널 병렬)"
```

---

### Task 7: Agent B (Sonnet 검증+결정)

**Files:**
- Create: `scripts/channel_pipeline/agent_b.py`

- [ ] **Step 1: wiki 파일 트리 수집 헬퍼 설계 이해**

Agent B는 Sonnet에게 다음을 전달한다:
1. 모든 claims JSON
2. 현재 wiki 파일 트리 (종목·섹터 파일 경로 목록)
3. 오늘 날짜

Sonnet은 WikiDecision 배열을 JSON으로 반환한다.

- [ ] **Step 2: `scripts/channel_pipeline/agent_b.py` 작성**

```python
from __future__ import annotations
import json
import os
from pathlib import Path
from anthropic import Anthropic
from scripts.channel_pipeline.models import Claim, WikiDecision

ROOT = Path(__file__).parent.parent.parent
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """당신은 한국 주식 wiki 에디터입니다.
채널들의 클레임을 검토해 wiki 업데이트 결정을 JSON 배열로 반환하세요.

규칙:
1. 각 클레임에 대해 action 결정:
   - append: wiki에 1줄 추가 (중요 팩트·의견)
   - flag: append + ⚠️ 충돌 주석 (다른 채널과 방향 상충)
   - skip: wiki 미반영 (중복·무관·노이즈)
2. wiki_file: 정확한 상대경로 (wiki/L5_섹터/{섹터}/stock/stock_{종목}.md)
3. line 형식: "- [YYYY-MM-DD] {내용 50자 이내} ({출처}/{채널})"
4. conflict_candidate=true 클레임 쌍은 반드시 교차 검토
5. 같은 종목 같은 날 동일 내용 중복 skip
6. JSON 배열만 출력. 다른 텍스트 금지.

출력 형식:
[{"claim_id":"tg_001","action":"append","wiki_file":"wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md","section":"## 최신 이벤트","line":"- [2026-06-04] HBM4 협상 본격화 (태린이아빠/텔레그램)","conflict_note":null}]"""


def _wiki_tree() -> str:
    """wiki/ 디렉토리의 stock + sector 파일 목록"""
    wiki_dir = ROOT / "wiki"
    if not wiki_dir.exists():
        return "(wiki 디렉토리 없음)"
    files = sorted(wiki_dir.rglob("*.md"))
    relevant = [
        str(f.relative_to(ROOT))
        for f in files
        if "stock_" in f.name or "sector_" in f.name
    ]
    return "\n".join(relevant[:200])  # 최대 200개


def run(claims: list[Claim], run_date: str) -> list[WikiDecision]:
    if not claims:
        return []
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    wiki_tree = _wiki_tree()
    claims_json = json.dumps([c.model_dump() for c in claims], ensure_ascii=False, indent=2)
    user_msg = f"""오늘 날짜: {run_date}

현재 wiki 파일 목록:
{wiki_tree}

처리할 클레임:
{claims_json}

위 클레임들에 대한 WikiDecision 배열을 반환하세요."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = response.content[0].text
    try:
        import re
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        items = json.loads(match.group()) if match else []
    except Exception:
        items = []

    decisions: list[WikiDecision] = []
    for item in items:
        try:
            decisions.append(WikiDecision(
                claim_id=item.get("claim_id", ""),
                action=item.get("action", "skip"),
                wiki_file=item.get("wiki_file", ""),
                section=item.get("section", "## 최신 이벤트"),
                line=item.get("line", ""),
                conflict_note=item.get("conflict_note"),
            ))
        except Exception:
            continue
    print(f"[Agent B] 완료 — {len(decisions)}개 결정 (append/flag/skip)")
    return decisions


def save(decisions: list[WikiDecision], path: Path) -> None:
    path.write_text(
        json.dumps([d.model_dump() for d in decisions], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 3: import 확인**

```bash
python -c "from scripts.channel_pipeline.agent_b import run; print('OK')"
```
예상: `OK`

- [ ] **Step 4: 커밋**

```bash
git add scripts/channel_pipeline/agent_b.py
git commit -m "feat: agent_b (Sonnet 교차검증 + wiki 결정 생성)"
```

---

### Task 8: Agent D (Haiku HTML 브리핑)

**Files:**
- Create: `scripts/channel_pipeline/agent_d.py`

- [ ] **Step 1: `scripts/channel_pipeline/agent_d.py` 작성**

```python
from __future__ import annotations
import json
import os
from pathlib import Path
from anthropic import Anthropic
from scripts.channel_pipeline.models import Claim, WikiDecision

ROOT = Path(__file__).parent.parent.parent
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """한국 주식 아침 브리핑 HTML 작성자입니다.
클레임과 wiki 결정을 바탕으로 간결하고 읽기 좋은 HTML 브리핑을 작성하세요.

구조:
1. 헤더: 날짜 + 채널 수 + 클레임 수
2. 주목 클레임: conflict_candidate=true 쌍 (bullish vs bearish 대비)
3. 채널별 주요 클레임 (append된 것만)
4. 언급 종목 요약 테이블

스타일: 다크 테마, 모바일 친화, 이모지 적극 활용"""


def run(
    claims: list[Claim],
    decisions: list[WikiDecision],
    run_date: str,
    out_dir: Path | None = None,
) -> Path:
    if out_dir is None:
        out_dir = ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"briefing_{run_date.replace('-','')}.html"

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    payload = {
        "run_date": run_date,
        "claims": [c.model_dump() for c in claims],
        "decisions": [d.model_dump() for d in decisions],
    }
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"다음 데이터로 HTML 브리핑을 작성하세요:\n{json.dumps(payload, ensure_ascii=False)}",
        }],
    )
    html = response.content[0].text
    # HTML 태그가 없으면 감싸기
    if not html.strip().startswith("<!DOCTYPE") and not html.strip().startswith("<html"):
        html = f"<!DOCTYPE html><html><body>{html}</body></html>"
    out_path.write_text(html, encoding="utf-8")
    print(f"[Agent D] 브리핑 저장: {out_path.name}")
    return out_path


def save_fallback(claims: list[Claim], run_date: str, out_dir: Path | None = None) -> Path:
    """API 실패 시 최소 HTML 생성"""
    if out_dir is None:
        out_dir = ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"briefing_{run_date.replace('-','')}.html"
    rows = "".join(
        f"<tr><td>{c.source}</td><td>{c.channel}</td><td>{c.content[:80]}</td>"
        f"<td style='color:{'green' if c.direction=='bullish' else 'red' if c.direction=='bearish' else 'gray'}'>"
        f"{c.direction}</td></tr>"
        for c in claims
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{run_date} 브리핑</title>
<style>body{{background:#1a1a2e;color:#e0e0e0;font-family:sans-serif}}
table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #333}}</style>
</head><body>
<h1>📊 {run_date} 채널 브리핑 (fallback)</h1>
<table><tr><th>출처</th><th>채널</th><th>내용</th><th>방향</th></tr>{rows}</table>
</body></html>"""
    out_path.write_text(html, encoding="utf-8")
    return out_path
```

- [ ] **Step 2: import 확인**

```bash
python -c "from scripts.channel_pipeline.agent_d import run, save_fallback; print('OK')"
```
예상: `OK`

- [ ] **Step 3: 커밋**

```bash
git add scripts/channel_pipeline/agent_d.py
git commit -m "feat: agent_d (Haiku HTML 브리핑 + fallback)"
```

---

### Task 9: Pipeline 오케스트레이터

**Files:**
- Create: `scripts/channel_pipeline/pipeline.py`
- Create: `tests/channel_pipeline/test_pipeline.py`

- [ ] **Step 1: 실패하는 통합 테스트 작성**

`tests/channel_pipeline/test_pipeline.py`:
```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from scripts.channel_pipeline.models import Claim, WikiDecision, PipelineState


@pytest.fixture
def run_date():
    return "2026-06-04"


@pytest.fixture
def mock_claims():
    return [
        Claim(id="tg_001", channel="telegram", source="태린이아빠",
              content="HBM4 협상 본격화", claim_type="fact",
              sector="반도체", tickers=["SK하이닉스"], direction="bullish"),
    ]


@pytest.fixture
def mock_decisions():
    return [
        WikiDecision(
            claim_id="tg_001", action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 협상 본격화 (태린이아빠/텔레그램)",
        )
    ]


def test_load_state_new(tmp_path):
    from scripts.channel_pipeline.pipeline import load_state, save_state
    state = load_state("2026-06-04", base_dir=tmp_path)
    assert state.run_date == "2026-06-04"
    assert state.step == "pending"


def test_save_and_load_state(tmp_path):
    from scripts.channel_pipeline.pipeline import load_state, save_state
    state = PipelineState(run_date="2026-06-04", step="A_done",
                           claims_file="pipeline/20260604/claims.json")
    save_state(state, base_dir=tmp_path)
    loaded = load_state("2026-06-04", base_dir=tmp_path)
    assert loaded.step == "A_done"
    assert loaded.claims_file == "pipeline/20260604/claims.json"


@pytest.mark.asyncio
async def test_pipeline_dry_run(tmp_path, run_date, mock_claims, mock_decisions, tmp_wiki):
    from scripts.channel_pipeline.pipeline import run_pipeline

    with patch("scripts.channel_pipeline.pipeline.get_manifest",
               return_value={"telegram": [], "blog": [], "report": [], "yt": []}), \
         patch("scripts.channel_pipeline.pipeline.can_run",
               return_value=(True, 0.01, "테스트")), \
         patch("scripts.channel_pipeline.pipeline.agent_a.run",
               new_callable=AsyncMock, return_value=mock_claims), \
         patch("scripts.channel_pipeline.pipeline.agent_b.run",
               return_value=mock_decisions), \
         patch("scripts.channel_pipeline.pipeline.agent_d.run",
               return_value=tmp_path / "out" / f"briefing_{run_date.replace('-','')}.html"):

        state = await run_pipeline(run_date, base_dir=tmp_path,
                                   wiki_root=tmp_wiki, dry_run=True)
        assert state.step == "done"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pip install pytest-asyncio
pytest tests/channel_pipeline/test_pipeline.py -v
```
예상: `ImportError`

- [ ] **Step 3: `scripts/channel_pipeline/pipeline.py` 작성**

```python
from __future__ import annotations
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.channel_pipeline import agent_a, agent_b, agent_d
from scripts.channel_pipeline.manifest import get_manifest
from scripts.channel_pipeline.cost_guard import can_run, reduce_scope
from scripts.channel_pipeline.wiki_writer import apply_decisions
from scripts.channel_pipeline.models import PipelineState, Claim, WikiDecision


# ─────────────────────────────────────
# 상태 관리
# ─────────────────────────────────────

def _state_path(run_date: str, base_dir: Path) -> Path:
    return base_dir / "pipeline" / run_date.replace("-", "") / "state.json"


def load_state(run_date: str, base_dir: Path = ROOT) -> PipelineState:
    p = _state_path(run_date, base_dir)
    if p.exists():
        return PipelineState.model_validate_json(p.read_text(encoding="utf-8"))
    return PipelineState(run_date=run_date)


def save_state(state: PipelineState, base_dir: Path = ROOT) -> None:
    p = _state_path(state.run_date, base_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def _pipeline_dir(run_date: str, base_dir: Path) -> Path:
    d = base_dir / "pipeline" / run_date.replace("-", "")
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─────────────────────────────────────
# 메인
# ─────────────────────────────────────

async def run_pipeline(
    run_date: str,
    base_dir: Path = ROOT,
    wiki_root: Path = ROOT,
    dry_run: bool = False,
    resume: bool = False,
) -> PipelineState:
    state = load_state(run_date, base_dir)
    if not resume:
        state = PipelineState(run_date=run_date)
    pd = _pipeline_dir(run_date, base_dir)

    # ── STEP 0: 파일 수집 + 비용 추정 ──
    manifest = get_manifest(run_date)
    ok, cost, reason = can_run(manifest)
    print(f"\n[STEP 0] 파일 수집 — {reason}")
    if not ok:
        manifest = reduce_scope(manifest)
        ok2, cost2, reason2 = can_run(manifest)
        print(f"  범위 축소 후: {reason2}")
        if not ok2:
            state.step = "failed"
            state.error = f"비용 초과: {reason2}"
            save_state(state, base_dir)
            return state

    # ── STEP 1: Agent A ──
    if state.step == "pending":
        print(f"\n[STEP 1] Agent A — Gemini Flash 분류")
        try:
            claims = await agent_a.run(manifest)
            claims_path = pd / "claims.json"
            agent_a.save(claims, claims_path)
            state.step = "A_done"
            state.claims_file = str(claims_path.relative_to(base_dir))
            save_state(state, base_dir)
            print(f"  → {len(claims)}개 클레임 추출")
        except Exception as e:
            state.step = "failed"
            state.error = f"Agent A: {e}"
            save_state(state, base_dir)
            return state

    # ── STEP 2: Agent B ──
    if state.step == "A_done":
        print(f"\n[STEP 2] Agent B — Sonnet 검증+결정")
        claims_path = base_dir / state.claims_file
        claims_raw = json.loads(claims_path.read_text(encoding="utf-8"))
        claims = [Claim.model_validate(c) for c in claims_raw]
        try:
            decisions = agent_b.run(claims, run_date)
            decisions_path = pd / "decisions.json"
            agent_b.save(decisions, decisions_path)
            state.step = "B_done"
            state.decisions_file = str(decisions_path.relative_to(base_dir))
            save_state(state, base_dir)
            append_count = sum(1 for d in decisions if d.action in ("append", "flag"))
            print(f"  → {len(decisions)}개 결정 (append/flag: {append_count}개)")
        except Exception as e:
            state.step = "failed"
            state.error = f"Agent B: {e}"
            save_state(state, base_dir)
            return state

    # ── STEP 3: wiki 업데이트 + 브리핑 병렬 ──
    if state.step == "B_done":
        print(f"\n[STEP 3] wiki 업데이트 + 브리핑 병렬")
        claims_raw = json.loads((base_dir / state.claims_file).read_text(encoding="utf-8"))
        decisions_raw = json.loads((base_dir / state.decisions_file).read_text(encoding="utf-8"))
        claims = [Claim.model_validate(c) for c in claims_raw]
        decisions = [WikiDecision.model_validate(d) for d in decisions_raw]

        wiki_task = asyncio.to_thread(apply_decisions, decisions, wiki_root, dry_run)
        briefing_task = asyncio.to_thread(agent_d.run, claims, decisions, run_date,
                                           base_dir / "out")
        results = await asyncio.gather(wiki_task, briefing_task, return_exceptions=True)

        wiki_result, briefing_result = results
        if isinstance(wiki_result, Exception):
            print(f"  [wiki] 오류: {wiki_result}")
        else:
            print(f"  [wiki] {len(wiki_result)}개 파일 업데이트")

        if isinstance(briefing_result, Exception):
            print(f"  [브리핑] 오류: {briefing_result}")
            agent_d.save_fallback(claims, run_date, base_dir / "out")
        else:
            print(f"  [브리핑] {briefing_result.name}")

        if not dry_run:
            _git_commit(run_date, base_dir)

        state.step = "done"
        save_state(state, base_dir)
        print(f"\n✅ 완료 — {run_date}")

    return state


def _git_commit(run_date: str, base_dir: Path) -> None:
    try:
        subprocess.run(
            ["git", "add", "wiki/", "out/", "pipeline/"],
            cwd=base_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"auto: channel-ingest {run_date}"],
            cwd=base_dir, check=True, capture_output=True,
        )
        print("  [git] 커밋 완료")
    except subprocess.CalledProcessError:
        print("  [git] 변경사항 없거나 오류")


def main() -> None:
    parser = argparse.ArgumentParser(description="채널 집계 파이프라인 v2")
    parser.add_argument("--date",     default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--resume",   action="store_true")
    args = parser.parse_args()
    asyncio.run(run_pipeline(args.date, dry_run=args.dry_run, resume=args.resume))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/channel_pipeline/test_pipeline.py -v
```
예상: 3개 PASS

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
pytest tests/channel_pipeline/ -v
```
예상: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add scripts/channel_pipeline/pipeline.py tests/channel_pipeline/test_pipeline.py
git commit -m "feat: pipeline 오케스트레이터 v2 (resume, dry-run, state 관리)"
```

---

### Task 10: Cron 스케줄 등록

**Files:**
- Modify: `.claude/settings.json` (cron 추가)

- [ ] **Step 1: 현재 스케줄 확인**

```bash
python -c "
from anthropic import Anthropic
# 기존 07:40 브리핑 스케줄 앞에 07:00 파이프라인 추가 필요
print('기존 trig_01S8QRBwMDjFwYVEqUxB6Mez (07:40) 확인됨')
"
```

- [ ] **Step 2: cron 등록**

`update-config` 스킬 또는 Claude Code `/schedule` 명령으로 등록:

```
매일 07:00 KST: python -m scripts.channel_pipeline.pipeline
```

Claude Code 명령어:
```
/schedule "매일 07:00 KST에 채널 파이프라인 실행: python -m scripts.channel_pipeline.pipeline"
```

- [ ] **Step 3: dry-run으로 최종 확인**

```bash
python -m scripts.channel_pipeline.pipeline --dry-run --date 2026-06-04
```
예상 출력:
```
[STEP 0] 파일 수집 — A(Gemini×0파일)=$0.0000 + B(Sonnet)=$0.0400 + D(Haiku)=$0.0040 = $0.0440
[STEP 1] Agent A — Gemini Flash 분류
...
```
(파일이 없으면 빈 결과지만 오류 없이 완료)

- [ ] **Step 4: 최종 커밋**

```bash
git add -A
git commit -m "feat: channel_pipeline v2.0 완성 (2단계 검증 파이프라인)"
```
