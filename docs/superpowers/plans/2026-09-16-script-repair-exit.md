# Script Repair Exit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영상 재료가 있으면 생성·검사 실패에도 장면 근거 대본을 최소 1개 반환한다.

**Architecture:** 기존 생성 및 문장 교정 재시도는 유지한다. 모든 스타일이 실패했을 때만 새 `script_fallback` 모듈이 `claim_evidence()`의 원본 발화와 장면 관측으로 최소 대본을 만들며, 실패한 AI 초안은 사용하지 않는다.

**Tech Stack:** Python, FastAPI, pytest, 기존 `script_generate`·`script_gate` 계약

---

### Task 1: 장면 근거 최소 대본 생성기

**Files:**
- Create: `shopping_shorts/script_fallback.py`
- Create: `shopping_shorts/tests/test_script_fallback.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_fallback_uses_only_product_and_canonical_evidence():
    evidence = {"items": [
        {"kind": "visual", "text": "정수기에서 얼음이 컵으로 떨어진다."},
        {"kind": "transcript", "text": "물을 받고 얼음을 꺼냅니다."},
    ]}
    result = build_grounded_fallback(
        "올인원 얼음정수기", evidence,
        {"id": 7, "name": "발견형", "beat_roles": ["hook", "show", "cta"]},
        "사실 검사 실패")
    assert result["beats"]
    assert "올인원 얼음정수기" in result["script"]
    assert "얼음이 컵으로 떨어진다" in result["script"]
    assert result["fallback_reason"] == "사실 검사 실패"
    assert result["needs_review"] is True
```

추가 테스트는 빈 항목에서도 제품명으로 1안이 생기는지, 가격·품절 같은 문장을 함수가 새로 만들지 않는지, 중복 관측이 한 번만 들어가는지 검사한다.

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `py -m pytest shopping_shorts/tests/test_script_fallback.py -q`

Expected: `ModuleNotFoundError: shopping_shorts.script_fallback`

- [ ] **Step 3: 최소 생성기 구현**

```python
def build_grounded_fallback(product, evidence, style=None, reason=""):
    observations = canonical_observations(evidence)
    roles = list((style or {}).get("beat_roles") or [])
    texts = [f"영상에서 확인한 제품은 {product}입니다."]
    texts.extend(f"영상에서는 {row}" for row in observations[:4])
    keyword = compact_keyword(product)
    texts.append(f"더 자세히 보고 싶다면 댓글에 '{keyword}' 남겨주세요.")
    beats = assign_roles(texts, roles)
    return {
        "style_id": (style or {}).get("id"),
        "style_name": (style or {}).get("name"),
        "beats": beats,
        "script": "\n".join(row["text"] for row in beats),
        "hook": beats[0]["text"],
        "checks": [{"name": "자동 교정", "ok": False, "detail": reason}],
        "passed": False,
        "needs_review": True,
        "fallback_reason": reason or "생성 결과를 장면 근거 대본으로 복구했습니다",
        "made_by": "장면근거",
    }
```

`canonical_observations()`는 `evidence.items`의 `visual`·`transcript`·`product_fact` 텍스트만 읽고 공백 정규화·중복 제거·길이 제한을 한다. 스타일 예문, `use_point`, 실패한 AI 초안은 입력으로 받지 않는다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -m pytest shopping_shorts/tests/test_script_fallback.py -q`

Expected: all passed

- [ ] **Step 5: 커밋**

```bash
git add shopping_shorts/script_fallback.py shopping_shorts/tests/test_script_fallback.py
git commit -m "feat: add scene-grounded script fallback"
```

### Task 2: 생성 출구에서 빈 배열 제거

**Files:**
- Modify: `shopping_shorts/script_generate.py:generate_by_styles`
- Modify: `shopping_shorts/tests/test_script_claim_grounding.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_all_failed_styles_return_grounded_fallback(monkeypatch):
    monkeypatch.setattr(sg, "generate_one_style", lambda *a, **k: None)
    result = sg.generate_by_styles(sources(), [{"id": 1, "name": "발견형"}], reasons=[])
    assert len(result) == 1
    assert result[0]["made_by"] == "장면근거"
    assert PRODUCT in result[0]["script"]

def test_passed_draft_wins_without_fallback(monkeypatch):
    passed = {"beats": [{"role": "hook", "text": "정상"}], "passed": True}
    monkeypatch.setattr(sg, "generate_one_style", lambda *a, **k: passed)
    assert sg.generate_by_styles(sources(), [{"id": 1}], reasons=[]) == [passed]
```

기존 테스트의 “사실 실패 검토 후보를 그대로 반환” 기대는 “실패 초안 대신 장면 근거 폴백 반환”으로 바꾼다. 소재 이탈 초안의 문장이 폴백에 섞이지 않는 주장도 추가한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest shopping_shorts/tests/test_script_claim_grounding.py -q -k "grounded_fallback or passed_draft_wins"`

Expected: 빈 리스트 또는 기존 검토 후보가 반환되어 실패

- [ ] **Step 3: 단일 폴백 출구 연결**

```python
    if out:
        return out
    if sources:
        from shopping_shorts import script_fallback
        reason = next((r.get("detail") or r.get("kind") for r in reasons or []
                       if r.get("detail") or r.get("kind")), "")
        style = next(iter(styles or []), {})
        evidence = claim_evidence(sources, facts_block)
        return [script_fallback.build_grounded_fallback(
            _sources_product(sources) or product or "영상 속 제품",
            evidence, style, reason)]
    return []
```

기존 `review_candidate`는 실패한 AI 주장을 그대로 노출하므로 제거한다. 정상 결과가 있으면 즉시 반환해 폴백이 섞이지 않게 한다.

- [ ] **Step 4: 관련 테스트 통과 확인**

Run: `py -m pytest shopping_shorts/tests/test_script_claim_grounding.py shopping_shorts/tests/test_script_fallback.py shopping_shorts/tests/test_generate_success_path.py -q`

Expected: all passed

- [ ] **Step 5: 커밋**

```bash
git add shopping_shorts/script_generate.py shopping_shorts/tests/test_script_claim_grounding.py
git commit -m "fix: always return grounded draft when styles fail"
```

### Task 3: API·화면 계약과 실제 검증

**Files:**
- Modify: `shopping_shorts/static/produce.html:s2DraftHtml`
- Modify: `shopping_shorts/tests/test_s2_review_fallback_ui.py`
- Create: `handoff/대본교정출구.md`
- Create: `wiki/log.d/대본교정출구.md`

- [ ] **Step 1: 화면 계약 실패 테스트 작성**

```python
def test_scene_fallback_explains_that_a_draft_was_recovered():
    block = function_block("s2DraftHtml")
    assert "dr.made_by==='장면근거'" in block
    assert "장면에서 확인된 내용으로 자동 복구" in block
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -m pytest shopping_shorts/tests/test_s2_review_fallback_ui.py -q`

Expected: 새 안내 문구가 없어 실패

- [ ] **Step 3: 화면 안내 구현**

`s2DraftHtml()`의 검토 배너는 `made_by==='장면근거'`일 때 “생성·검사 실패로 장면에서 확인된 내용만 사용해 자동 복구했습니다”라고 표시한다. 정상 초안 및 직접 작성 초안 UI는 바꾸지 않는다.

- [ ] **Step 4: 정적·관련 회귀 검사**

Run:

```bash
py -m pytest shopping_shorts/tests/test_script_fallback.py shopping_shorts/tests/test_script_claim_grounding.py shopping_shorts/tests/test_claim_grounding_wiring.py shopping_shorts/tests/test_generate_success_path.py shopping_shorts/tests/test_s2_review_fallback_ui.py -q
py -m pytest shopping_shorts/tests/test_fx_wizard_js.py::test_produce_html_script_parses -q
py -m py_compile shopping_shorts/script_fallback.py shopping_shorts/script_generate.py shopping_shorts/app.py
git diff --check
```

Expected: all selected tests pass, JavaScript parses, Python compiles, diff check has no output

- [ ] **Step 5: 기록과 커밋**

```bash
git add shopping_shorts/static/produce.html shopping_shorts/tests/test_s2_review_fallback_ui.py handoff/대본교정출구.md wiki/log.d/대본교정출구.md
git commit -m "fix: explain scene-grounded script recovery"
```

- [ ] **Step 6: 트랙 병합과 라이브 확인**

Run: `py tools/track.py finish 대본교정출구`

Expected: 신규 실패 없이 main 병합·push. 배포 후 서버 커밋과 서비스 재시작 시간을 확인하고, 실제 얼음정수기 또는 QA 작업에서 대본 생성 응답이 HTTP 200이며 `drafts`가 1개 이상인지 확인한다.
