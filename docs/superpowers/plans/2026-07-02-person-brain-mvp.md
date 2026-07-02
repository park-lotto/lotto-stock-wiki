# 사람 브레인 MVP (1단계) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 태린이아빠의 "브레인 페이지"(사고 골격 + 자동 갱신 섹션)를 만들고, 사람 단위로 원자를 조회하는 레지스트리·조회 레이어를 구축한다.

**Architecture:** 새 패키지 `pipeline/people/`. ① `people.json` 레지스트리(사람→source_name 매핑) ② `registry.py` 로더 ③ `people_query.py`(atoms.db를 source_name으로 필터 조회) ④ `build_brain.py`(브레인 페이지의 AUTO 마커 섹션만 갱신 — 수동 뼈대 보존) ⑤ `wiki/people/태린이아빠.md`(수동 뼈대 씨앗 + 자동 섹션). 새 크롤링·DB 없음, 기존 `atoms.db`·인제스트 재사용.

**Tech Stack:** Python 3, sqlite3(기존 `pipeline/atoms/db.py`), pytest. 마크다운 페이지. LLM/엔진 없음(2단계).

## Global Constraints

- 파이썬 모듈 경로는 패키지 절대 임포트 사용: `from pipeline.people.registry import ...` (기존 `pipeline.atoms.*` 관례).
- 원자 조회는 `active_only=True`(is_active=1) 기본. 소스는 `source_name IN (...)` 정확 매칭(LIKE 아님).
- 브레인 페이지 자동 갱신은 **AUTO 마커 사이만** 교체. 마커 밖(수동 뼈대)은 절대 건드리지 않는다.
- 출처 표기: 자동 섹션의 각 항목은 원자의 `date` + `source_name`을 포함(추적 가능성).
- 테스트는 `tests/atoms/test_db.py`의 `fresh_db` 패턴(`monkeypatch.setattr(db_module,"DB_PATH", tmp_path/...)` + `init_db()`) 재사용.
- 인코딩: 모든 파일 read/write `encoding="utf-8"`.
- 커밋 브랜치: `feat/person-brain` (이미 생성됨).

---

## File Structure

- Create `pipeline/people/__init__.py` — 빈 패키지 마커.
- Create `pipeline/people/people.json` — 사람 레지스트리 데이터.
- Create `pipeline/people/registry.py` — 레지스트리 로더(`load_registry`, `get_person`, `source_names`).
- Create `pipeline/people/people_query.py` — 사람별 원자 조회(`atoms_for`) + CLI.
- Create `pipeline/people/build_brain.py` — 페이지 AUTO 섹션 렌더·마커 갱신(`render_live_stance`, `render_speech_log`, `update_markers`, `build`) + CLI.
- Create `wiki/people/태린이아빠.md` — 수동 뼈대 + AUTO 마커.
- Create `tests/people/__init__.py`, `tests/people/test_registry.py`, `tests/people/test_people_query.py`, `tests/people/test_build_brain.py`.

---

### Task 1: 사람 레지스트리 (데이터 + 로더)

**Files:**
- Create: `pipeline/people/__init__.py`
- Create: `pipeline/people/people.json`
- Create: `pipeline/people/registry.py`
- Create: `tests/people/__init__.py`
- Test: `tests/people/test_registry.py`

**Interfaces:**
- Produces:
  - `load_registry() -> dict` — people.json 전체를 dict로.
  - `get_person(name: str) -> dict` — 해당 사람 설정 dict. 없으면 `KeyError`.
  - `source_names(name: str) -> list[str]` — 그 사람의 atoms `source_name` 목록.

- [ ] **Step 1: 빈 패키지 마커 생성**

Create `pipeline/people/__init__.py` (빈 파일) 과 `tests/people/__init__.py` (빈 파일).

- [ ] **Step 2: 레지스트리 데이터 작성**

Create `pipeline/people/people.json`:

```json
{
  "태린이아빠": {
    "display": "태린이아빠",
    "sources": ["태린이아빠 주식투자", "태린이아빠"],
    "trust": "B",
    "tracking_since": "2026-05-01",
    "data_files": ["taerini_stock.json", "taerini_consensus.json"],
    "brain_page": "wiki/people/태린이아빠.md"
  }
}
```

- [ ] **Step 3: 실패하는 테스트 작성**

Create `tests/people/test_registry.py`:

```python
import pytest
from pipeline.people.registry import load_registry, get_person, source_names


def test_load_registry_has_taerini():
    reg = load_registry()
    assert "태린이아빠" in reg


def test_get_person_returns_config():
    p = get_person("태린이아빠")
    assert p["trust"] == "B"
    assert p["brain_page"] == "wiki/people/태린이아빠.md"


def test_source_names_includes_telegram_and_youtube():
    names = source_names("태린이아빠")
    assert "태린이아빠 주식투자" in names   # 텔레그램
    assert "태린이아빠" in names            # 유튜브


def test_get_person_unknown_raises():
    with pytest.raises(KeyError):
        get_person("없는사람")
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `python -m pytest tests/people/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.people.registry'`

- [ ] **Step 5: 로더 구현**

Create `pipeline/people/registry.py`:

```python
"""registry.py — 사람 레지스트리 로더 (people.json)."""
import json
from pathlib import Path

_REGISTRY_PATH = Path(__file__).parent / "people.json"


def load_registry() -> dict:
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


def get_person(name: str) -> dict:
    reg = load_registry()
    if name not in reg:
        raise KeyError(f"사람 레지스트리에 없음: {name}")
    return reg[name]


def source_names(name: str) -> list[str]:
    return list(get_person(name).get("sources", []))
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/people/test_registry.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: 커밋**

```bash
git add pipeline/people/__init__.py pipeline/people/people.json pipeline/people/registry.py tests/people/__init__.py tests/people/test_registry.py
git commit -m "feat(people): 사람 레지스트리(people.json)+로더"
```

---

### Task 2: 사람별 원자 조회 (people_query.py)

**Files:**
- Create: `pipeline/people/people_query.py`
- Test: `tests/people/test_people_query.py`

**Interfaces:**
- Consumes: `pipeline.people.registry.source_names`, `pipeline.atoms.db.get_conn`.
- Produces:
  - `atoms_for(person: str, content_type: str | None = None, days: int = 30, limit: int = 50, active_only: bool = True) -> list[dict]`
    — 그 사람의 `source_name IN sources` 원자를 최신순 반환. `content_type`(fact/stance/method) 필터 옵션.

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/people/test_people_query.py`:

```python
import pytest
from datetime import date
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, insert_atom
from pipeline.people.people_query import atoms_for


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_atoms.db")
    init_db()


def _atom(overrides=None):
    base = {
        "id": "a1", "date": date.today().isoformat(),
        "source_type": "telegram", "source_name": "태린이아빠 주식투자",
        "source_trust": "B", "raw_file": "raw/x.md",
        "sector": "조선", "asset": "HD현대중공업",
        "signal": "bullish", "content_type": "stance", "strength_score": 3,
        "is_active": 1, "content": "조선 비중 확대 유지.", "relations": [],
    }
    if overrides:
        base.update(overrides)
    return base


def test_atoms_for_returns_only_person_sources():
    insert_atom(_atom({"id": "mine1"}))
    insert_atom(_atom({"id": "mine2", "source_name": "태린이아빠"}))  # 유튜브
    insert_atom(_atom({"id": "other", "source_name": "신한리서치"}))
    got = atoms_for("태린이아빠")
    ids = {a["id"] for a in got}
    assert ids == {"mine1", "mine2"}


def test_atoms_for_filters_content_type():
    insert_atom(_atom({"id": "s1", "content_type": "stance"}))
    insert_atom(_atom({"id": "m1", "content_type": "method"}))
    got = atoms_for("태린이아빠", content_type="method")
    assert [a["id"] for a in got] == ["m1"]


def test_atoms_for_active_only():
    insert_atom(_atom({"id": "act", "is_active": 1}))
    insert_atom(_atom({"id": "dead", "is_active": 0}))
    ids = {a["id"] for a in atoms_for("태린이아빠")}
    assert ids == {"act"}


def test_atoms_for_ordered_newest_first():
    insert_atom(_atom({"id": "old", "date": "2026-06-01"}))
    insert_atom(_atom({"id": "new", "date": "2026-06-30"}))
    got = atoms_for("태린이아빠", days=3650)
    assert got[0]["id"] == "new"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/people/test_people_query.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.people.people_query'`

- [ ] **Step 3: 조회 구현**

Create `pipeline/people/people_query.py`:

```python
"""people_query.py — 사람별 원자 조회 (source_name IN sources).

CLI:
    python -m pipeline.people.people_query 태린이아빠
    python -m pipeline.people.people_query 태린이아빠 --content-type method --days 60
"""
import sys
import io
import json
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pipeline.atoms.db import get_conn
from pipeline.people.registry import source_names


def atoms_for(person, content_type=None, days=30, limit=50, active_only=True):
    sources = source_names(person)
    if not sources:
        return []
    conds = ["date >= date('now', ? || ' days')"]
    params = [f"-{days}"]
    placeholders = ",".join("?" * len(sources))
    conds.append(f"source_name IN ({placeholders})")
    params.extend(sources)
    if active_only:
        conds.append("is_active = 1")
    if content_type:
        conds.append("content_type = ?")
        params.append(content_type)
    sql = (
        f"SELECT * FROM atoms WHERE {' AND '.join(conds)} "
        f"ORDER BY date DESC, strength_score DESC LIMIT ?"
    )
    params.append(limit)
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("relations"):
            try:
                d["relations"] = json.loads(d["relations"])
            except (json.JSONDecodeError, TypeError):
                d["relations"] = []
        else:
            d["relations"] = []
        result.append(d)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="사람별 원자 조회")
    ap.add_argument("person")
    ap.add_argument("--content-type", default=None, help="fact|stance|method")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    atoms = atoms_for(args.person, content_type=args.content_type,
                      days=args.days, limit=args.limit)
    print(f"[{args.person}] 원자 {len(atoms)}개 (최근 {args.days}일)")
    for a in atoms:
        print(f"  {a['date']} [{a.get('content_type','')}] {a['source_name']} | "
              f"{a.get('sector','')}/{a.get('asset','')} | {a['content'][:80]}")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/people/test_people_query.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add pipeline/people/people_query.py tests/people/test_people_query.py
git commit -m "feat(people): 사람별 원자 조회 atoms_for + CLI"
```

---

### Task 3: 브레인 페이지 자동 섹션 생성기 (build_brain.py)

**Files:**
- Create: `pipeline/people/build_brain.py`
- Test: `tests/people/test_build_brain.py`

**Interfaces:**
- Consumes: `pipeline.people.registry.get_person`, `pipeline.people.people_query.atoms_for`.
- Produces:
  - `render_live_stance(atoms: list[dict]) -> str` — stance 원자 → 마크다운 불릿.
  - `render_speech_log(atoms: list[dict]) -> str` — 최근 원자 → 날짜별 로그 마크다운.
  - `update_markers(page_text: str, sections: dict[str, str]) -> str` — `<!-- AUTO:key -->`~`<!-- /AUTO:key -->` 사이만 교체.
  - `build(person: str) -> str` — 페이지 파일 읽어 자동 섹션 갱신 후 저장, 최종 텍스트 반환.

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/people/test_build_brain.py`:

```python
import pytest
from pipeline.people.build_brain import render_live_stance, render_speech_log, update_markers


def _atom(**kw):
    base = {"date": "2026-06-30", "source_name": "태린이아빠 주식투자",
            "sector": "조선", "asset": "HD현대중공업",
            "content_type": "stance", "signal": "bullish",
            "content": "조선 비중 확대 유지."}
    base.update(kw)
    return base


def test_render_live_stance_includes_asset_and_date():
    out = render_live_stance([_atom()])
    assert "HD현대중공업" in out
    assert "2026-06-30" in out


def test_render_speech_log_includes_content():
    out = render_speech_log([_atom(content="현금 30%까지 늘렸다.")])
    assert "현금 30%까지 늘렸다." in out


def test_update_markers_replaces_only_inside_marker():
    page = (
        "# 태린이아빠\n\n## 1. 철학\n수급빈집(수동 뼈대).\n\n"
        "## 5. 라이브 스탠스\n"
        "<!-- AUTO:live_stance -->\n(옛 내용)\n<!-- /AUTO:live_stance -->\n"
    )
    out = update_markers(page, {"live_stance": "- 새 스탠스"})
    assert "수급빈집(수동 뼈대)." in out       # 수동 뼈대 보존
    assert "- 새 스탠스" in out                # 자동 갱신됨
    assert "(옛 내용)" not in out              # 옛 자동내용 제거


def test_update_markers_idempotent():
    page = "<!-- AUTO:x -->\nold\n<!-- /AUTO:x -->\n"
    once = update_markers(page, {"x": "content"})
    twice = update_markers(once, {"x": "content"})
    assert once == twice


def test_update_markers_missing_key_unchanged():
    page = "<!-- AUTO:a -->\nkeep\n<!-- /AUTO:a -->\n"
    out = update_markers(page, {"b": "irrelevant"})
    assert "keep" in out
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/people/test_build_brain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.people.build_brain'`

- [ ] **Step 3: 생성기 구현**

Create `pipeline/people/build_brain.py`:

```python
"""build_brain.py — 브레인 페이지의 AUTO 마커 섹션만 갱신 (수동 뼈대 보존).

CLI:
    python -m pipeline.people.build_brain 태린이아빠
"""
import sys
import io
import re
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pipeline.people.registry import get_person
from pipeline.people.people_query import atoms_for

_ROOT = Path(__file__).parent.parent.parent


def render_live_stance(atoms):
    if not atoms:
        return "_(활성 스탠스 없음)_"
    lines = []
    for a in atoms:
        asset = a.get("asset") or a.get("sector") or "?"
        lines.append(f"- **{asset}** ({a.get('signal','')}) — {a['content']} "
                     f"·{a['date']} {a['source_name']}")
    return "\n".join(lines)


def render_speech_log(atoms):
    if not atoms:
        return "_(발언 없음)_"
    lines = []
    for a in atoms:
        lines.append(f"- `{a['date']}` [{a.get('content_type','')}] "
                     f"{a.get('sector','')}/{a.get('asset','')}: {a['content']}")
    return "\n".join(lines)


def update_markers(page_text, sections):
    out = page_text
    for key, body in sections.items():
        pattern = re.compile(
            rf"(<!-- AUTO:{re.escape(key)} -->)(.*?)(<!-- /AUTO:{re.escape(key)} -->)",
            re.DOTALL,
        )
        out = pattern.sub(rf"\1\n{body}\n\3", out)
    return out


def build(person):
    cfg = get_person(person)
    page_path = _ROOT / cfg["brain_page"]
    text = page_path.read_text(encoding="utf-8")
    stance = atoms_for(person, content_type="stance", days=30)
    log = atoms_for(person, days=14, limit=40)
    updated = update_markers(text, {
        "live_stance": render_live_stance(stance),
        "speech_log": render_speech_log(log),
    })
    page_path.write_text(updated, encoding="utf-8")
    return updated


if __name__ == "__main__":
    person = sys.argv[1] if len(sys.argv) > 1 else "태린이아빠"
    build(person)
    print(f"[{person}] 브레인 페이지 자동 섹션 갱신 완료.")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/people/test_build_brain.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add pipeline/people/build_brain.py tests/people/test_build_brain.py
git commit -m "feat(people): 브레인 페이지 AUTO 마커 갱신기(수동 뼈대 보존)"
```

---

### Task 4: 태린이아빠 브레인 페이지 시드 + 자동 채우기

이 태스크의 산출물은 **읽을 수 있는 브레인 페이지**다(= MVP 쓸모 게이트). 뼈대(섹션 1~4)는
실제 원자에서 근거를 뽑아 손으로 쓰고, 자동 섹션(5·8)은 생성기로 채운다.

**Files:**
- Create: `wiki/people/태린이아빠.md`

**Interfaces:**
- Consumes: `pipeline.people.build_brain.build`, `pipeline.people.people_query`(CLI).

- [ ] **Step 1: 뼈대 근거 원자 수집 (분석 입력)**

Run: `python -m pipeline.people.people_query 태린이아빠 --content-type method --days 90`
Run: `python -m pipeline.people.people_query 태린이아빠 --content-type stance --days 30`
이 출력을 읽고 섹션 1~4(철학·프레임워크·판단규칙·어휘)의 근거로 사용한다.
(참고: `pipeline/atoms/telegram_channels.json`·`youtube_registry.json`에 채널 URL,
`docs/superpowers/specs/2026-07-02-태린이아빠-브레인-design.md`에 프레임워크 원자재.)

- [ ] **Step 2: 브레인 페이지 작성 (수동 뼈대 + AUTO 마커)**

Create `wiki/people/태린이아빠.md`. 아래 구조를 따르되, 섹션 1~4 본문은 Step 1의 원자 근거로
채운다(아래는 씨앗 예시 — 실제 원자로 검증·보강할 것). 섹션 5·8은 마커만 두고 비운다.

```markdown
# 태린이아빠 — 브레인

> 채널 운영자의 사고 골격 + 매일 자동 갱신. 자동 섹션은 `python -m pipeline.people.build_brain 태린이아빠`로 갱신.
> 마지막 자동 갱신: (build_brain 실행 시 기록)

## 0. 프로필
- 텔레그램: 태린이아빠 주식투자 (https://t.me/+E9KqzA7DYVA0OGY1)
- 유튜브: @Taerins_Dad
- 신뢰등급: B · 추적 시작: 2026-05-01

## 1. 철학 / 세계관  _(수동 뼈대)_
- **수급빈집**: 수급이 아직 안 들어온 자리를 먼저 본다.
- **주도섹터강도**: 시장을 이끄는 섹터(RS 상위)에 집중. "가는 놈이 더 간다."
- **대장주**: 섹터 내 1등에 무게.
- (Step 1 원자로 보강)

## 2. 분석 프레임워크 (보는 순서)  _(수동 뼈대)_
수급오실레이터(빈집) → RS(상대강도) → 가속화모멘텀 → 컨센(추정이익 변화) → 쏠림지수 → 액티브ETF 비중.
- (각 도구의 실제 파일: pipeline/taerini_stock.json 지표들)

## 3. 판단 규칙 (IF-THEN)  _(수동 뼈대)_
- IF 수급빈집 ∧ RS 상위 ∧ 컨센 상향 → 탑픽 후보.
- IF 시장 과열/현금 언급 증가 → 비중 축소 신호.
- (Step 1 method 원자로 보강)

## 4. 어휘 / 말투  _(수동 뼈대)_
- 빈집, 대장, 순환매, 비중, 관망, 늘릴 시기 …

## 5. 라이브 스탠스 (현재 포지션)  _(자동)_
<!-- AUTO:live_stance -->
<!-- /AUTO:live_stance -->

## 8. 발언 로그 (최근 14일)  _(자동)_
<!-- AUTO:speech_log -->
<!-- /AUTO:speech_log -->
```

- [ ] **Step 3: 자동 섹션 채우기**

Run: `python -m pipeline.people.build_brain 태린이아빠`
Expected: "브레인 페이지 자동 섹션 갱신 완료." 출력. `wiki/people/태린이아빠.md`의 두 AUTO 마커
사이가 원자 내용으로 채워짐(수동 섹션 1~4는 그대로).

- [ ] **Step 4: 멱등성 수동 확인**

Run: `python -m pipeline.people.build_brain 태린이아빠` (재실행)
Expected: 수동 섹션 1~4 불변, 자동 섹션만 최신으로 재채움(중복 누적 없음).

- [ ] **Step 5: 전체 테스트 실행**

Run: `python -m pytest tests/people/ -v`
Expected: PASS (13 passed)

- [ ] **Step 6: 커밋**

```bash
git add wiki/people/태린이아빠.md
git commit -m "feat(people): 태린이아빠 브레인 페이지(뼈대 시드+자동 섹션)"
```

---

## MVP 쓸모 게이트 (다음 단계 진입 조건)

Task 4 완료 후 `wiki/people/태린이아빠.md`를 며칠 읽어본다. "이 페이지가 실제로 그의 사고를
빠르게 파악하게 해주나?" — YES면 2단계(질의 엔진), NO면 뼈대/자동 섹션 재설계.

## Self-Review (작성자 체크 결과)

- **스펙 커버리지**: 스펙 §5 ①(레지스트리)=Task1, 조회레이어=Task2, ②(브레인페이지 자동섹션5·8)=Task3+4, 뼈대(1~4)=Task4. 스펙 §7 "1단계(MVP)" 범위와 일치. ③저널·④질의엔진·⑤대시보드·§6시장자세·§7트랙레코드는 **2·3단계**(이 계획 범위 밖, 의도적).
- **플레이스홀더**: 코드 스텝은 전부 실제 코드 포함. Task4 Step2의 섹션 1~4 본문은 "실제 원자로 채움"이 분석 작업이라 씨앗 예시+수집 커맨드(Step1)로 대체 — 근거 커맨드가 명시됨.
- **타입 일관성**: `atoms_for`(Task2 정의) 시그니처를 Task3 `build`가 동일하게 호출(`content_type=`, `days=`). `update_markers(page_text, sections: dict)` 명명 Task3 내부 일관. `source_names`(Task1)→people_query(Task2) 일관.
