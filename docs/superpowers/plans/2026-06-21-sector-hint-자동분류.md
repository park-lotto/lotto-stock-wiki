# 종목 섹터 자동분류 (sector_hint) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gemini가 텔레그램 추출 시 모든 종목에 섹터를 태깅하고, fan-out이 그 hint로 종목 원자의 섹터를 결정해 "기타" 고정과 모르는 외국주 코멘트 손실을 해결한다.

**Architecture:** 섹터 택소노미를 `sectors.json` config로 단일화. 질문지 프롬프트에 목록을 주입해 Gemini가 그 중 하나를 고르게 함. fan-out은 `resolve_sector()`로 (외국 오버라이드 map → Gemini hint → 기타) 우선순위 결정. foreign_sector_map은 오버라이드로 강등.

**Tech Stack:** Python 3.14, google-genai(gemini-3.1-flash-lite), pytest. 기존 모듈: telegram_questionnaire.py, stock_resolve.py.

## Global Constraints

- 설계 출처: `docs/superpowers/specs/2026-06-21-sector-hint-자동분류-design.md`.
- 섹터 택소노미는 `pipeline/atoms/sectors.json` **단일 소스**. Gemini 프롬프트·fan-out 정규화 둘 다 여기서 읽는다. 섹터 추가 = 이 JSON만 편집.
- `resolve_sector(name, hint, *, is_foreign) -> tuple[list[str], str]` — **항상 list 반환**(단일도 길이1). 종목원자는 sectors[0], 외국 컨텍스트원자는 각 sector마다 1개.
- 우선순위: 외국 오버라이드 map → Gemini hint(목록 정규화) → 기타+로그.
- foreign_sector_map.json은 **오버라이드**(외국주 교정용). 모르는 외국주는 hint로 살린다(코멘트 손실 방지).
- 테스트는 운영 로그/DB 절대 안 건드림 — 기존 격리 fixture 패턴(monkeypatch) 준수.
- Gemini 호출은 테스트하지 않는다(프롬프트 구조만). 골든셋=tg_spike.json.
- 이 plan은 **텔레그램만**. 리포트 파이프라인 통일은 범위 밖(후속).

---

### Task 1: sectors.json + sector_classify.py

**Files:**
- Create: `pipeline/atoms/sectors.json`
- Create: `pipeline/atoms/sector_classify.py`
- Test: `pipeline/atoms/test_sector_classify.py`

**Interfaces:**
- Consumes: `stock_resolve.foreign_sectors(name) -> list[str]` (기존).
- Produces:
  - `sectors_list() -> list[str]` — 택소노미 전체.
  - `resolve_sector(name: str, hint: str, *, is_foreign: bool) -> tuple[list[str], str]` — (섹터리스트, source∈{"map","gemini","gemini_norm","fallback"}).

- [ ] **Step 1: sectors.json 작성**

```json
{
  "sectors": [
    "반도체", "2차전지", "자동차", "조선", "방산", "로봇",
    "전력", "원전", "신재생", "바이오", "통신", "철강",
    "IT", "양자보안", "화장품미용", "소비내수", "중국", "기타"
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# pipeline/atoms/test_sector_classify.py
from pipeline.atoms.sector_classify import sectors_list, resolve_sector


def test_sectors_list_loads():
    s = sectors_list()
    assert "반도체" in s and "양자보안" in s and "기타" in s


def test_korean_uses_hint():
    # 한국주: 오버라이드 map 안 봄, hint 그대로
    secs, src = resolve_sector("삼성전자", "반도체", is_foreign=False)
    assert secs == ["반도체"]
    assert src == "gemini"


def test_foreign_map_overrides_hint():
    # 애플: foreign map [반도체,IT]가 hint보다 우선
    secs, src = resolve_sector("애플", "IT", is_foreign=True)
    assert secs == ["반도체", "IT"]
    assert src == "map"


def test_foreign_unmapped_uses_hint():
    # 모르는 외국주: map 없으면 hint로 살림 (코멘트 손실 방지)
    secs, src = resolve_sector("ZZZChip", "반도체", is_foreign=True)
    assert secs == ["반도체"]
    assert src == "gemini"


def test_hint_partial_match_normalized():
    # "반도체장비" → 부분매칭 → 반도체
    secs, src = resolve_sector("어떤외국주", "반도체장비", is_foreign=True)
    assert secs == ["반도체"]
    assert src == "gemini_norm"


def test_no_hint_falls_back():
    secs, src = resolve_sector("ZZZChip", None, is_foreign=True)
    assert secs == ["기타"]
    assert src == "fallback"


def test_hint_off_taxonomy_falls_back():
    # 목록에도 부분매칭도 안 되는 값
    secs, src = resolve_sector("X", "완전이상한섹터명123", is_foreign=False)
    assert secs == ["기타"]
    assert src == "fallback"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest pipeline/atoms/test_sector_classify.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 4: sector_classify.py 구현**

```python
# pipeline/atoms/sector_classify.py
"""섹터 택소노미(sectors.json) + 종목 섹터 결정.

우선순위: 외국 오버라이드 map → Gemini hint(목록 정규화) → 기타.
"""
import json
from pathlib import Path

from .stock_resolve import foreign_sectors

_SECTORS = json.loads(
    (Path(__file__).parent / "sectors.json").read_text(encoding="utf-8")
)["sectors"]


def sectors_list() -> list[str]:
    return list(_SECTORS)


def _norm_to_taxonomy(hint: str) -> str | None:
    """hint를 택소노미 1개로 정규화. 정확매칭 → 부분매칭 → None."""
    if not hint:
        return None
    h = hint.strip()
    if h in _SECTORS:
        return h
    for s in _SECTORS:
        if s != "기타" and (s in h or h in s):
            return s
    return None


def resolve_sector(name: str, hint: str, *, is_foreign: bool) -> tuple[list[str], str]:
    if is_foreign:
        fs = foreign_sectors(name)
        if fs:
            return list(fs), "map"
    if hint and hint.strip() in _SECTORS:
        return [hint.strip()], "gemini"
    norm = _norm_to_taxonomy(hint)
    if norm:
        return [norm], "gemini_norm"
    return ["기타"], "fallback"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest pipeline/atoms/test_sector_classify.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add pipeline/atoms/sectors.json pipeline/atoms/sector_classify.py pipeline/atoms/test_sector_classify.py
git commit -m "feat(sector): sectors.json 택소노미 + resolve_sector"
```

---

### Task 2: 질문지에 sector 슬롯 + 목록 주입

**Files:**
- Modify: `pipeline/atoms/telegram_questionnaire.py` (QUESTIONNAIRES·_COMMON)
- Test: `pipeline/atoms/test_telegram_prompts.py` (기존 파일에 추가)

**Interfaces:**
- Consumes: `sector_classify.sectors_list()`.
- Produces: QUESTIONNAIRES의 stock 슬롯(stocks_mentioned/stocks/reports)에 `sector` 칸 추가, 모든 프롬프트에 섹터 목록 문자열 포함.

- [ ] **Step 1: Write the failing test (기존 test_telegram_prompts.py에 추가)**

```python
def test_prompts_inject_sector_taxonomy():
    from pipeline.atoms.telegram_questionnaire import QUESTIONNAIRES
    from pipeline.atoms.sector_classify import sectors_list
    sample = sectors_list()[0]  # "반도체"
    for ctype, p in QUESTIONNAIRES.items():
        assert "sector" in p
        assert sample in p  # 택소노미 목록이 프롬프트에 주입됨


def test_stock_slots_have_sector():
    from pipeline.atoms.telegram_questionnaire import QUESTIONNAIRES
    # 종목 멘션 있는 타입은 sector 칸 안내 포함
    for ctype in ("sector", "stock_tips", "insight", "report_relay"):
        assert "sector" in QUESTIONNAIRES[ctype]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pipeline/atoms/test_telegram_prompts.py::test_prompts_inject_sector_taxonomy -v`
Expected: FAIL — 목록 미주입(또는 sector 키 없음).

- [ ] **Step 3: _COMMON에 섹터 지침 + 목록 주입, 슬롯에 sector 추가**

`telegram_questionnaire.py` 상단 import에 추가:
```python
from .sector_classify import sectors_list
```

`_COMMON` 정의 바로 뒤에 섹터 지침 추가(문자열 결합):
```python
_SECTOR_RULE = (
    "각 종목에는 sector를 붙여라. 아래 목록에서 정확히 하나만 고른다(모르면 \"기타\"): "
    + " / ".join(sectors_list()) + "\n"
)
_COMMON = _COMMON + _SECTOR_RULE
```

QUESTIONNAIRES의 종목 슬롯에 `sector` 추가 (해당 라인만 교체):
- sector: `stocks_mentioned:[{name, comment, ts, quote, sector}],`
- stock_tips: `stocks:[{name, signal(bull/bear/neutral), reason, ts, quote, sector}],`
- insight: `stocks_mentioned:[{name, comment, ts, quote, sector}],`
- report_relay: `reports:[{broker, stock, rating, tp, ts, quote, sector}],`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/atoms/test_telegram_prompts.py -v`
Expected: PASS (기존 + 신규 2개).

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/telegram_questionnaire.py pipeline/atoms/test_telegram_prompts.py
git commit -m "feat(sector): 질문지에 sector 슬롯 + 택소노미 목록 주입"
```

---

### Task 3: fan-out에 섹터 결정 연결

**Files:**
- Modify: `pipeline/atoms/telegram_questionnaire.py` (_stock_atom·add_stocks·_norm_sector·_SECTOR_KEYS)
- Test: `pipeline/atoms/test_telegram_fanout.py` (기존에 추가)

**Interfaces:**
- Consumes: `sector_classify.resolve_sector`, `sector_classify.sectors_list`.
- Produces: 종목원자 sector = hint 기반(더이상 "기타" 기본 아님). 외국주는 map/hint 섹터 컨텍스트원자.

- [ ] **Step 1: Write the failing test (test_telegram_fanout.py에 추가)**

```python
def test_korean_stock_gets_hint_sector():
    # stock_tips 한국주가 "기타" 아닌 hint 섹터를 받는다
    q = {"stocks": [{"name": "삼성전자", "signal": "bull", "reason": "x",
                     "ts": "10:00", "quote": "q", "sector": "반도체"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집",
            "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    sams = [a for a in atoms if a["asset"] == "삼성전자" and a["asset_level"] == "stock"]
    assert sams and sams[0]["sector"] == "반도체"


def test_unmapped_foreign_with_hint_preserved():
    # map에 없는 외국주라도 hint로 섹터 컨텍스트 원자 생성 (손실 X)
    q = {"stocks": [{"name": "ZZZChip", "signal": "bull", "reason": "신규칩",
                     "ts": "10:00", "quote": "q", "sector": "반도체"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집",
            "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    fgn = [a for a in atoms if a["asset_level"] == "sector" and a["sector"] == "반도체"]
    assert fgn and "ZZZChip" in fgn[0]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pipeline/atoms/test_telegram_fanout.py::test_korean_stock_gets_hint_sector -v`
Expected: FAIL — 종목원자 sector가 "기타"(또는 meta값).

- [ ] **Step 3: _SECTOR_KEYS·_norm_sector를 config로, _stock_atom에 sector 추가**

`telegram_questionnaire.py` 상단 import에 추가:
```python
from .sector_classify import resolve_sector, sectors_list
```

`_SECTOR_KEYS = [...]` 줄을 교체:
```python
_SECTOR_KEYS = sectors_list()
```

`_stock_atom` 시그니처에 `sector` 추가:
```python
def _stock_atom(meta, name_info, content, *, ts, i, sector, layer_tag="fact"):
    return _base(
        meta,
        id=_mk_id(meta["channel"], meta["date"], "stk", i),
        sector=sector,
        asset=name_info["name"], asset_level="stock",
        content_type="fact", msg_ts=ts,
        strength_score=_strength(meta.get("trust", "C"), layer_tag, 1),
        content=content,
    )
```

- [ ] **Step 4: add_stocks를 resolve_sector 기반으로 재작성**

`add_stocks` 내부 전체를 교체:
```python
    def add_stocks(items, key_name, key_text):
        """한국주(매칭)=종목원자(hint 섹터) / 비매칭=외국주 경로(map→hint→기타 컨텍스트원자)."""
        for s in items or []:
            raw = (s.get(key_name) or "").strip()
            if not raw:
                continue
            info = resolve_stock(raw, date=meta["date"], channel=meta["channel"], skip_log=True)
            quote = s.get("quote") or s.get(key_text) or ""
            comment = s.get(key_text) or quote
            hint = s.get("sector")
            if info["matched"]:
                secs, _ = resolve_sector(info["name"], hint, is_foreign=False)
                atoms.append(_stock_atom(meta, info, quote, ts=s.get("ts"),
                                         i=len(atoms), sector=secs[0]))
                continue
            # 비매칭 = 외국주 경로 (codemap이 KRX 전종목이라 미매칭 한국주는 희소)
            secs, src = resolve_sector(info["name"], hint, is_foreign=True)
            for sec in secs:
                atoms.append(_foreign_sector_atom(
                    meta, sec, info["name"], comment, ts=s.get("ts"), i=len(atoms)))
            if src == "fallback":
                log_foreign_unmapped(info["name"], meta["date"], meta["channel"])
```

> 주의: 기존 `elif info["is_korean"]: _append_log(UNMATCHED_LOG...)` 분기는 **제거**된다
> (codemap이 KRX 전종목이라 미매칭 한국주는 드물고, 비매칭은 외국주 경로로 통일).
> `from .stock_resolve import _append_log, UNMATCHED_LOG` 줄도 더이상 쓰지 않으면 제거.

- [ ] **Step 5: report_relay 종목원자에 sector 반영**

`report_relay` 분기의 `_stock_atom` 호출에 sector 추가:
```python
    elif ctype == "report_relay":
        for i, rp in enumerate(q.get("reports") or []):
            raw = (rp.get("stock") or "").strip()
            if not raw:
                continue
            info = resolve_stock(raw, date=meta["date"], channel=meta["channel"], skip_log=True)
            if info["matched"]:
                secs, _ = resolve_sector(info["name"], rp.get("sector"), is_foreign=False)
                atoms.append(_stock_atom(
                    meta, info,
                    f"[중계:{rp.get('broker')}] 목표가 {rp.get('tp')} {rp.get('rating')} / {rp.get('quote') or ''}",
                    ts=rp.get("ts"), i=len(atoms), sector=secs[0]))
```

- [ ] **Step 6: 기존 fanout 테스트 보존 확인 + 신규 통과**

Run: `python -m pytest pipeline/atoms/test_telegram_fanout.py -v`
Expected: 기존 테스트 + 신규 2개 PASS. (기존 `test_sector_korean_stock_only` 등은 sector 필드가 없는 픽스처라 hint=None → resolve_sector fallback이지만, 한국주 SK하이닉스는 여전히 stock 원자 생성됨. 외국주는 map으로 잡힘. 단언 유지.)

만약 기존 테스트가 sector 단언으로 깨지면, 그 테스트의 기대값을 새 동작(hint 없으면 기타)에 맞게 갱신하되 **종목원자 생성 여부 단언은 유지**.

- [ ] **Step 7: Commit**

```bash
git add pipeline/atoms/telegram_questionnaire.py pipeline/atoms/test_telegram_fanout.py
git commit -m "feat(sector): fan-out 종목원자 섹터를 resolve_sector로 결정"
```

---

### Task 4: 골든셋 보강 + 전체 회귀 + 라이브 검증

**Files:**
- Modify: `pipeline/atoms/fixtures/tg_spike.json` (종목에 sector 필드)
- (코드 변경 없음 — 검증·정리)

- [ ] **Step 1: 골든셋 픽스처에 sector 필드 보강**

`pipeline/atoms/fixtures/tg_spike.json`의 종목 멘션(stocks_mentioned/stocks)에 `sector` 추가.
예: 하나반도체 stocks_mentioned의 SK하이닉스 → `"sector": "반도체"`, 잠실개미 stocks의 삼성전자 → `"sector": "반도체"`, 마이크론 → `"sector": "반도체"`, 애플 → `"sector": "IT"`. 각 종목에 적절한 섹터를 sectors.json 목록에서 부여.

- [ ] **Step 2: 전체 atoms 테스트 회귀**

Run: `python -m pytest pipeline/atoms/ -q`
Expected: 전체 PASS (sector_classify + 기존 텔레그램/리포트/codemap).

- [ ] **Step 3: 라이브 검증 (1채널 재인제스트)**

기존 2026-06-19 텔레그램 원자 삭제 후 1채널 재인제스트:
```bash
python -c "from pipeline.atoms.db import get_conn; c=get_conn(); c.execute(\"DELETE FROM atoms WHERE source_type='telegram' AND date='2026-06-19' AND source_name='잠실개미고급수집'\"); c.commit(); c.close()"
python -m pipeline.atoms.telegram_ingest "raw/telegram/2026-06-19_잠실개미고급수집.md"
```
Expected: 에러 없음, 원자 생성.

- [ ] **Step 4: 섹터 분류 결과 확인**

```bash
python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); from pipeline.atoms.db import get_conn; c=get_conn(); [print(r) for r in c.execute(\"SELECT asset, asset_level, sector FROM atoms WHERE source_type='telegram' AND date='2026-06-19' AND source_name='잠실개미고급수집'\").fetchall()]; c.close()"
```
Expected: 한국주(삼성전자·SK하이닉스)가 **"기타"가 아닌 "반도체"** 섹터를 받음. 외국주(마이크론)는 반도체 컨텍스트.

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/fixtures/tg_spike.json
git commit -m "test(sector): 골든셋 sector 필드 보강 + 라이브 검증 완료"
```

---

## Self-Review

**1. Spec coverage:**
- §2 택소노미 config → Task 1 sectors.json ✅
- §3 resolve_sector 우선순위 → Task 1 (map→hint→기타) ✅
- §4 질문지 sector 슬롯 + 목록주입 → Task 2 ✅
- §5 fan-out: 한국주 hint 섹터·외국주 map/hint·기타+로그 → Task 3 ✅
- §5 외국주 손실 해결(모르는 외국주 hint로 살림) → Task 3 test_unmapped_foreign_with_hint_preserved ✅
- §6 검증/테스트(정규화·한국주 섹터·오버라이드 우선·회귀) → Task 1·3·4 ✅
- §7 foreign_sector_map 오버라이드 강등 → Task 1 resolve_sector(map 우선) ✅
- §7 _norm_sector/_SECTOR_KEYS → config → Task 3 ✅

**갭/결정:**
- 리포트 파이프라인 통일은 스펙 §8 범위 밖 — plan도 텔레그램만. 정합.
- 기존 `elif is_korean: unmatched 로그` 제거 → 비매칭은 외국주 경로로 통일. codemap이 KRX 전종목이라 미매칭 한국주 희소이므로 수용(Task 3 주석 명시). **사용자 확인 권장 항목.**

**2. Placeholder scan:** TBD/TODO 없음. 모든 코드 단계 실제 코드 포함. Task 4 Step 1은 "적절한 섹터 부여"가 다소 열려있으나 예시 명시(SK하이닉스→반도체 등).

**3. Type consistency:** `resolve_sector(...) -> (list[str], str)` Task 1 정의 ↔ Task 3 사용 일치. `_stock_atom(..., sector=...)` Task 3 정의·호출 일치. `sectors_list()` Task 1·2·3 일치.
