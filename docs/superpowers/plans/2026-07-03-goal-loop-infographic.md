# 골루프 카드 — NotebookLM 인포그래픽 추가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 아침 브리핑 텍스트 카드의 그라데이션 히어로 이미지를 없애고, NotebookLM 인포그래픽을 별도 사진으로 추가 발송한다. 인포그래픽 생성 실패 시 텍스트카드도 발행 보류하고 에스컬레이션한다.

**Architecture:** `card_render.render_briefing_card`의 `hero_path`를 선택 인자로 만들어 히어로 없이도 렌더 가능하게 하고(기존 studio_pipeline.py 호출부는 무수정 하위호환), `nlm_bridge.py`에 `create_report`와 동일한 동기 폴링 패턴으로 `create_infographic`을 추가한다. `notebook_stage0.py`가 이를 감싸고, `morning_brief.py`가 정상 발행 조건에 인포그래픽 성공을 포함시킨다.

**Tech Stack:** Python 3.12, `nlm` CLI(subprocess, 기존 `nlm_bridge._run_nlm` 재사용), pytest, monkeypatch 기반 단위테스트.

## Global Constraints

- 파일 인코딩 UTF-8. 한국어 주석/문자열 유지.
- `card_render.render_briefing_card(data, hero_path=None)` — **하위호환 필수**: `scripts/studio_pipeline.py`와 `tests/studio/test_card_render.py`가 실제 hero를 넘겨 호출하는 기존 동작이 **그대로** 유지돼야 함(신호: 이 파일들은 이번 계획에서 손대지 않음).
- `dashboard/server.py`는 동시에 다른 세션이 편집 중일 수 있다 — Task 3 실행 직전 반드시 `grep -n "^_BRAND_DESIGN"`으로 현재 위치 재확인.
- 로컬 파이썬: `C:/Users/TheRose/AppData/Local/Python/bin/python.exe`. pytest: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest`.
- ⚠️ **알려진 제한(수정 대상 아님, YAGNI)**: `_ensure_scenario`가 `out/scenario_{date}.md`를 이미 발견하면 노트북을 새로 안 만들고 즉시 반환하므로 `notebook_id`가 없다 — 이 경우 인포그래픽 생성은 스킵되어 에스컬레이션된다. 이는 하루 1회 도는 08시 데몬(정상 경로)에는 영향 없고, 같은 날 수동 재실행(테스트) 시에만 해당하는 의도된 동작이다.

---

## File Structure

- Modify: `scripts/card_render.py` — `hero_path` 선택 인자화
- Modify: `scripts/nlm_bridge.py` — `_BRAND_DESIGN` 추가, `create_infographic()` 추가
- Modify: `dashboard/server.py` — 로컬 `_BRAND_DESIGN` 삭제, nlm_bridge import에 추가
- Modify: `scripts/goal_loop/notebook_stage0.py` — `generate_infographic()` 추가
- Modify: `scripts/goal_loop/morning_brief.py` — 히어로 생성 제거, notebook_id 전달, 인포그래픽 게이트+2차 발송
- Test: `tests/studio/test_card_render.py`(보강), `tests/nlm_bridge/test_notebook_calls.py`(보강), `tests/goal_loop/test_notebook_stage0.py`(보강), `tests/goal_loop/test_orchestrator.py`(보강)

---

### Task 1: `card_render.py` — 히어로 선택 인자화

**Files:**
- Modify: `scripts/card_render.py`
- Test: `tests/studio/test_card_render.py`

**Interfaces:**
- Produces: `render_briefing_card(data: dict, hero_path: Path = None) -> str` — `hero_path`가 None이면
  `<img class="hero">` 태그 없이 헤드라인부터 렌더. 기존 호출부(`studio_pipeline.py`, hero 전달)는 무변경 동작.

- [ ] **Step 1: 실패 테스트 추가**

`tests/studio/test_card_render.py` 파일 끝에 추가:

```python
def test_render_without_hero_omits_img_tag():
    html = cr.render_briefing_card(DATA)   # hero_path 생략
    assert 'class="hero"' not in html
    assert 'class="card"' in html
    assert "반도체 강세 지속" in html   # 텍스트는 정상 렌더
```

- [ ] **Step 2: 실패 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/studio/test_card_render.py::test_render_without_hero_omits_img_tag -v`
Expected: FAIL (`TypeError: render_briefing_card() missing 1 required positional argument: 'hero_path'`)

- [ ] **Step 3: 구현**

`scripts/card_render.py`의 다음 블록:
```python
def render_briefing_card(data: dict, hero_path: Path) -> str:
    hero_uri = Path(hero_path).as_uri()
    sectors = " · ".join(html.escape(s) for s in data.get("lead_sectors", [])[:4])
```

를 다음으로 교체:
```python
def render_briefing_card(data: dict, hero_path: Path = None) -> str:
    hero_html = f'<img class="hero" src="{Path(hero_path).as_uri()}" alt="">' if hero_path else ""
    sectors = " · ".join(html.escape(s) for s in data.get("lead_sectors", [])[:4])
```

그리고 다음 블록:
```python
  <div class="card">
    <img class="hero" src="{hero_uri}" alt="">
    <div class="body">
```

를 다음으로 교체:
```python
  <div class="card">
    {hero_html}
    <div class="body">
```

- [ ] **Step 4: 통과 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/studio/test_card_render.py -v`
Expected: 5 passed (기존 4개 + 신규 1개, 기존 4개는 hero 전달 케이스라 무변경 통과)

- [ ] **Step 5: 커밋**

```bash
git add scripts/card_render.py tests/studio/test_card_render.py
git commit -m "feat(card-render): hero_path 선택 인자화 — 히어로 없이도 카드 렌더 가능(하위호환 유지)"
```

---

### Task 2: `nlm_bridge.py` — `_BRAND_DESIGN` 이전 + `create_infographic` 추가

**Files:**
- Modify: `scripts/nlm_bridge.py`
- Test: `tests/nlm_bridge/test_notebook_calls.py`

**Interfaces:**
- Consumes: `_run_nlm`, `_friendly_nlm_err`(기존, 무변경)
- Produces: `_BRAND_DESIGN`(str 상수), `create_infographic(nb_id: str, out_dir: str = None, focus: str = "") -> dict`
  — `{"ok": bool, "path": str, "error": str}`. 다운로드된 파일이 실제 존재해야 `ok=True`(리포트와 달리
  인포그래픽은 "정상 발행" 필수조건이라 성공 기준을 엄격히: 파일 없으면 무조건 `ok=False`).

- [ ] **Step 1: 실패 테스트 작성**

`tests/nlm_bridge/test_notebook_calls.py` 파일 끝에 추가:

```python
def test_brand_design_constant_exists():
    assert "라임그린" in nb._BRAND_DESIGN
    assert "블랙" in nb._BRAND_DESIGN


def test_create_infographic_success(monkeypatch, tmp_path):
    import json
    def fake(args, timeout=90, _auth_retry=True):
        if args[0] == "infographic":
            return True, "", ""
        if args[0] == "studio":
            return True, json.dumps([{"type": "infographic", "id": "art-1", "status": "completed"}]), ""
        if args[0] == "download":
            # 다운로드 성공 시늉: 실제 파일 생성
            out_idx = args.index("-o") + 1
            Path(args[out_idx]).write_bytes(b"\x89PNG")
            return True, "", ""
        return True, "", ""
    monkeypatch.setattr(nb, "_run_nlm", fake)
    monkeypatch.setattr(nb.time, "sleep", lambda s: None)
    r = nb.create_infographic("nb1", out_dir=str(tmp_path))
    assert r["ok"] is True
    assert r["path"].endswith(".png")
    assert Path(r["path"]).exists()


def test_create_infographic_create_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=90, _auth_retry=True: (False, "", "실패"))
    r = nb.create_infographic("nb1", out_dir=str(tmp_path))
    assert r["ok"] is False and r["path"] == ""


def test_create_infographic_download_fails_no_file(monkeypatch, tmp_path):
    import json
    def fake(args, timeout=90, _auth_retry=True):
        if args[0] == "infographic":
            return True, "", ""
        if args[0] == "studio":
            return True, json.dumps([]), ""   # 상태 계속 안 나옴 → art_id 못 찾음
        if args[0] == "download":
            return False, "", "no artifact"   # 다운로드 자체 실패, 파일 안 생김
        return True, "", ""
    monkeypatch.setattr(nb, "_run_nlm", fake)
    monkeypatch.setattr(nb.time, "sleep", lambda s: None)
    r = nb.create_infographic("nb1", out_dir=str(tmp_path))
    assert r["ok"] is False and r["path"] == ""
```

이 테스트 파일 상단에 `from pathlib import Path`가 없으면 추가한다(기존 import 목록 확인 후, 없을 시에만 추가).

- [ ] **Step 2: 실패 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/nlm_bridge/test_notebook_calls.py -v -k infographic`
Expected: FAIL (`AttributeError: module 'nlm_bridge' has no attribute 'create_infographic'` / `_BRAND_DESIGN`)

- [ ] **Step 3: `scripts/nlm_bridge.py`에 `_BRAND_DESIGN` + `create_infographic` 추가**

파일 끝(`create_report` 함수 뒤)에 이어 붙인다:

```python
# 리모션(채널) 브랜드 디자인 지침 — 인포그래픽 등 시각 결과물에 적용(dashboard/server.py와 공유)
_BRAND_DESIGN = (
    "[디자인 지침] 순수 블랙(#000000) 배경에 라임그린(#AAFF00)을 메인 액센트로 핵심 수치·"
    "키워드·그래프 라인·테두리에 사용하고, 골드/앰버(#C8921A)는 고급 포인트로, 텍스트는 흰색. "
    "미니멀하면서 데이터가 빛나는 HUD/프리미엄 금융 대시보드 느낌. 큰 숫자와 핵심을 강하게 강조하고 "
    "정보 밀도 높게, 디테일하고 세련되게 구성."
)


def create_infographic(nb_id: str, out_dir: str = None, focus: str = "") -> dict:
    """노트북 소스로 NotebookLM 인포그래픽(PNG) 생성(동기 폴링, 최대 ~150초).
    {"ok","path","error"}. 다운로드된 파일이 실제 존재해야 ok=True(카드 발행 필수조건이라 엄격 판정).
    저장 위치: out_dir/infographic_{nb_id}.png."""
    import json as _json
    parts = ([focus] if focus else []) + [_BRAND_DESIGN]
    focus_text = " / ".join(parts)
    ok, out, errm = _run_nlm(
        ["infographic", "create", nb_id, "--confirm", "--language", "ko",
         "--style", "professional", "--focus", focus_text],
        timeout=180)
    if not ok:
        return {"ok": False, "path": "", "error": _friendly_nlm_err(errm)}

    art_id = None
    for _ in range(30):
        ok_s, out_s, _ = _run_nlm(["studio", "status", nb_id])
        try:
            arts = [a for a in _json.loads(out_s) if a.get("type") == "infographic"]
            if arts and arts[-1].get("status") not in ("in_progress", "pending", None):
                art_id = arts[-1].get("id")
                break
        except Exception:
            pass
        time.sleep(5)

    base_dir = Path(out_dir) if out_dir else (ROOT / "out" / "insights_notebook")
    base_dir.mkdir(parents=True, exist_ok=True)
    ip = base_dir / f"infographic_{re.sub(r'[^0-9a-fA-F-]', '', nb_id)}.png"
    dargs = ["download", "infographic", nb_id, "-o", str(ip)]
    if art_id:
        dargs += ["--id", art_id]
    ok_d, _od, _ed = _run_nlm(dargs, timeout=60)
    if ok_d and ip.exists():
        return {"ok": True, "path": str(ip), "error": ""}
    return {"ok": False, "path": "", "error": "다운로드 실패"}
```

- [ ] **Step 4: 통과 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/nlm_bridge/ -v`
Expected: 18 passed (기존 14 + 신규 4)

- [ ] **Step 5: 커밋**

```bash
git add scripts/nlm_bridge.py tests/nlm_bridge/test_notebook_calls.py
git commit -m "feat(nlm-bridge): create_infographic 추가(create_report 패턴 재사용) + _BRAND_DESIGN 이전"
```

---

### Task 3: `dashboard/server.py` — `_BRAND_DESIGN` 재배선

**Files:**
- Modify: `dashboard/server.py`

**Interfaces:**
- Consumes: Task 2의 `nlm_bridge._BRAND_DESIGN`
- Produces: 기존 인포그래픽/슬라이드 생성 동작 **무변경**(참조하는 값이 동일 상수로 바뀔 뿐)

- [ ] **Step 1: 현재 위치 재확인(동시편집 대비)**

Run: `grep -n "^_BRAND_DESIGN\|^from nlm_bridge import" dashboard/server.py`

- [ ] **Step 2: import 블록에 `_BRAND_DESIGN` 추가**

`from nlm_bridge import (` 로 시작하는 블록(Step1에서 확인한 정확한 위치)의 마지막 줄
`create_report as nlm_create_report,` 다음 줄에 추가:
```python
    _BRAND_DESIGN,
```

- [ ] **Step 3: 로컬 `_BRAND_DESIGN` 정의 삭제**

Step1에서 확인한 로컬 정의 블록(형태는 다음과 동일해야 함 — 다르면 실제 현재 내용 기준으로 삭제):
```python
_BRAND_DESIGN = (
    "[디자인 지침] 순수 블랙(#000000) 배경에 라임그린(#AAFF00)을 메인 액센트로 핵심 수치·"
    "키워드·그래프 라인·테두리에 사용하고, 골드/앰버(#C8921A)는 고급 포인트로, 텍스트는 흰색. "
    "미니멀하면서 데이터가 빛나는 HUD/프리미엄 금융 대시보드 느낌. 큰 숫자와 핵심을 강하게 강조하고 "
    "정보 밀도 높게, 디테일하고 세련되게 구성."
)
```
을 삭제.

- [ ] **Step 4: import/구문 검증**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -c "import ast; ast.parse(open('dashboard/server.py', encoding='utf-8').read()); print('syntax OK')"`
Expected: `syntax OK`

Run: `grep -c "_BRAND_DESIGN" dashboard/server.py`
Expected: `3` (import 1줄 + 사용처 2곳, 로컬 정의는 삭제됐으므로 정의 블록의 6줄은 사라짐)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/server.py
git commit -m "refactor(server): _BRAND_DESIGN을 nlm_bridge에서 import(동작 무변경)"
```

---

### Task 4: `notebook_stage0.py` — `generate_infographic` 추가

**Files:**
- Modify: `scripts/goal_loop/notebook_stage0.py`
- Test: `tests/goal_loop/test_notebook_stage0.py`

**Interfaces:**
- Consumes: `nlm_bridge.create_infographic`(Task 2)
- Produces: `generate_infographic(notebook_id: str, date: str) -> str|None` — 성공 시 PNG 경로,
  `notebook_id`가 falsy이거나 생성 실패 시 `None`(예외 전파 안 함).

- [ ] **Step 1: 실패 테스트 작성**

`tests/goal_loop/test_notebook_stage0.py` 파일 끝에 추가:

```python
def test_generate_infographic_success(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": {"ok": True, "path": "/x/info.png", "error": ""})
    p = ns.generate_infographic("nb-1", "2026-07-03")
    assert p == "/x/info.png"


def test_generate_infographic_failure_returns_none(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": {"ok": False, "path": "", "error": "실패"})
    assert ns.generate_infographic("nb-1", "2026-07-03") is None


def test_generate_infographic_no_notebook_id_returns_none_without_calling(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": called.__setitem__("n", called["n"] + 1) or {"ok": True, "path": "x", "error": ""})
    assert ns.generate_infographic(None, "2026-07-03") is None
    assert called["n"] == 0


def test_generate_infographic_exception_returns_none(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": (_ for _ in ()).throw(RuntimeError("nlm down")))
    assert ns.generate_infographic("nb-1", "2026-07-03") is None
```

- [ ] **Step 2: 실패 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_notebook_stage0.py -v -k infographic`
Expected: FAIL (`AttributeError: module 'scripts.goal_loop.notebook_stage0' has no attribute 'generate_infographic'`)

- [ ] **Step 3: 구현**

`scripts/goal_loop/notebook_stage0.py` 파일 끝(`generate_deep_report` 함수 뒤)에 추가:

```python
def generate_infographic(notebook_id: str, date: str) -> str:
    """카드용 인포그래픽 PNG(NotebookLM 생성). notebook_id 없거나 실패 시 None(예외 전파 안 함)."""
    if not notebook_id:
        return None
    try:
        r = nlm_bridge.create_infographic(notebook_id,
                                          out_dir=str(OUT_DIR / "insights_notebook"))
        return r.get("path") or None if r.get("ok") else None
    except Exception:
        return None
```

- [ ] **Step 4: 통과 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_notebook_stage0.py -v`
Expected: 11 passed (기존 7 + 신규 4)

- [ ] **Step 5: 커밋**

```bash
git add scripts/goal_loop/notebook_stage0.py tests/goal_loop/test_notebook_stage0.py
git commit -m "feat(goal-loop): notebook_stage0.generate_infographic 추가"
```

---

### Task 5: `morning_brief.py` 통합 — 히어로 제거 + 인포그래픽 게이트 + 2차 발송

**Files:**
- Modify: `scripts/goal_loop/morning_brief.py`
- Modify: `tests/goal_loop/test_orchestrator.py`

**Interfaces:**
- Consumes: `notebook_stage0.generate_infographic`(Task 4), `card_render.render_briefing_card(data, hero_path=None)`(Task 1)
- Produces: `_ensure_scenario(date) -> dict`(`{"notebook_id","notebook_url","report_url"}` — `notebook_id` 필드 신규 추가),
  `run_morning_brief`는 인포그래픽 생성 성공까지 확인해야 `status="sent"` 가능. 실패 시 기존 `_escalate` 경로로.

- [ ] **Step 1: `_patch()` 헬퍼에 인포그래픽 목킹 추가 + 실패 테스트 작성**

`tests/goal_loop/test_orchestrator.py`의 `_patch()` 함수:
```python
def _patch(monkeypatch, index_moves, critique_pass=True, data=None):
    monkeypatch.setattr(mb, "_ensure_scenario", lambda date: None)   # Stage0 서브프로세스 우회
    monkeypatch.setattr(mb.studio_data, "get_briefing_data",
                        lambda d: (data if data is not None else {"headline": "h", "date": d}))
    monkeypatch.setattr(mb, "_render_card", lambda data, date: "x.png")   # 렌더 우회
    monkeypatch.setattr(mb, "_get_index_moves", lambda: index_moves)
    sent = {"photo": [], "msg": [], "captions": []}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: sent["photo"].append(chat_id) or sent["captions"].append(caption) or True)
    monkeypatch.setattr(mb.viz_card, "send_telegram_message",
                        lambda text, chat_id=None: sent["msg"].append(chat_id) or sent["captions"].append(text) or True)
    monkeypatch.setattr(mb.quality, "critique", lambda data, fn: {"pass": critique_pass, "issues": []})
    return sent
```

를 다음으로 교체(인포그래픽 성공을 기본값으로 목킹 — 기존 5개 테스트가 인포그래픽을 신경 안 써도 통과하도록):
```python
def _patch(monkeypatch, index_moves, critique_pass=True, data=None, infographic_path="ig.png"):
    monkeypatch.setattr(mb, "_ensure_scenario", lambda date: None)   # Stage0 서브프로세스 우회
    monkeypatch.setattr(mb.studio_data, "get_briefing_data",
                        lambda d: (data if data is not None else {"headline": "h", "date": d}))
    monkeypatch.setattr(mb, "_render_card", lambda data, date: "x.png")   # 렌더 우회
    monkeypatch.setattr(mb, "_get_index_moves", lambda: index_moves)
    monkeypatch.setattr(mb.notebook_stage0, "generate_infographic",
                        lambda nb_id, date: infographic_path)
    sent = {"photo": [], "msg": [], "captions": []}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: sent["photo"].append((chat_id, png)) or sent["captions"].append(caption) or True)
    monkeypatch.setattr(mb.viz_card, "send_telegram_message",
                        lambda text, chat_id=None: sent["msg"].append(chat_id) or sent["captions"].append(text) or True)
    monkeypatch.setattr(mb.quality, "critique", lambda data, fn: {"pass": critique_pass, "issues": []})
    return sent
```

⚠️ `sent["photo"]`가 이제 `chat_id` 단독이 아니라 `(chat_id, png)` 튜플 리스트로 바뀐다 — 기존 테스트의
`assert sent["photo"] == [None]` 류 단언문을 아래처럼 **모두** 갱신해야 한다(파일 내 모든 `sent["photo"]`
비교 단언을 확인하고 튜플 형태에 맞게 고칠 것. 예: `assert sent["photo"] == [None]` →
`assert [c for c, _p in sent["photo"]] == [None]` 또는 정확한 튜플 비교로 변경. 각 기존 테스트를 열어
실제 필요한 검증이 chat_id뿐이면 `[c for c, _p in sent["photo"]]` 형태로 추출해 비교하는 방식을 권장).

파일 끝에 추가:
```python
def test_infographic_success_sends_second_photo(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setattr(mb, "_ensure_scenario",
                        lambda date: {"notebook_id": "nb-1", "notebook_url": "https://notebooklm.google.com/notebook/nb-1", "report_url": None})
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3}, infographic_path="ig.png")
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    pngs = [p for _c, p in sent["photo"]]
    assert "x.png" in pngs and "ig.png" in pngs   # 텍스트카드 + 인포그래픽 둘 다 전송


def test_infographic_failure_escalates_holds_text_card(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.delenv("OWNER_CHAT_ID", raising=False)
    monkeypatch.setattr(mb, "_ensure_scenario",
                        lambda date: {"notebook_id": "nb-1", "notebook_url": None, "report_url": None})
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3}, infographic_path=None)   # 인포그래픽 실패
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert any("인포그래픽" in reason for reason in r["reasons"])
    assert sent["photo"] == []   # 텍스트카드도 발행 안 됨(둘 다 준비돼야 발행)
```

- [ ] **Step 2: 실패 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_orchestrator.py -v`
Expected: 다수 FAIL — `_patch`가 아직 `mb.notebook_stage0`를 모름(import 안 됨) + 기존 테스트의
`sent["photo"]` 튜플 불일치 + 신규 2개 테스트가 `run_morning_brief`에 인포그래픽 로직이 없어서 실패.

- [ ] **Step 3: `morning_brief.py` — 상단 import에 `notebook_stage0` 추가**

파일 상단(현재):
```python
"""아침 브리핑 오케스트레이터: 생성→품질루프→이상징후 게이트→발송/에스컬레이션."""
import os, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import studio_data, card_render, viz_card, gemini_image  # noqa: E402
from scripts.goal_loop import verify, quality, pending  # noqa: E402
```

를 다음으로 교체(`gemini_image` import는 `_default_gemini`가 아직 쓰므로 유지, `notebook_stage0`을
모듈 레벨로 추가해 테스트가 `mb.notebook_stage0`로 monkeypatch할 수 있게 함):

```python
"""아침 브리핑 오케스트레이터: 생성→품질루프→이상징후 게이트→발송/에스컬레이션."""
import os, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import studio_data, card_render, viz_card, gemini_image  # noqa: E402
from scripts.goal_loop import verify, quality, pending, notebook_stage0  # noqa: E402
```

- [ ] **Step 4: `_render_card`에서 히어로 생성 제거**

현재:
```python
def _render_card(data: dict, date: str) -> str:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    hero = STUDIO_DIR / "img" / f"{date}_hero.png"
    hero.parent.mkdir(parents=True, exist_ok=True)
    try:
        gemini_image.generate_hero(gemini_image.build_prompt(data), hero)
    except Exception:
        pass
    html = card_render.render_briefing_card(data, hero)
    html_path = STUDIO_DIR / f"{date}_브리핑.html"
    card_render.save_card_html(html, html_path)
    png_path = STUDIO_DIR / f"{date}_브리핑.png"
    viz_card.save_png(html_path, png_path)
    return str(png_path)
```

를 다음으로 교체:
```python
def _render_card(data: dict, date: str) -> str:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    html = card_render.render_briefing_card(data)   # 히어로 없이 텍스트만
    html_path = STUDIO_DIR / f"{date}_브리핑.html"
    card_render.save_card_html(html, html_path)
    png_path = STUDIO_DIR / f"{date}_브리핑.png"
    viz_card.save_png(html_path, png_path)
    return str(png_path)
```

- [ ] **Step 5: `_ensure_scenario`에 `notebook_id` 필드 추가**

현재:
```python
def _ensure_scenario(date: str) -> dict:
    """Stage 0: NotebookLM으로 out/scenario_{date}.md 생성(없을 때만) + 심층리포트 시도(비차단).
    반환: {"notebook_url": str|None, "report_url": str|None}. 실패해도 예외 없이 빈 값 반환."""
    from scripts.goal_loop import notebook_stage0
    links = {"notebook_url": None, "report_url": None}
    scen = ROOT / "out" / f"scenario_{date}.md"
    if scen.exists():
        return links
    try:
        nb = notebook_stage0.build_notebook(date)
        if not nb or not nb.get("notebook_id"):
            return links
        links["notebook_url"] = nb.get("url")
        text = notebook_stage0.query_card_content(nb["notebook_id"], date)
        if not text:
            return links
        scen.parent.mkdir(parents=True, exist_ok=True)
        scen.write_text(text, encoding="utf-8")
        report_url = notebook_stage0.generate_deep_report(nb["notebook_id"], date)
        if report_url:
            links["report_url"] = report_url
    except Exception:
        pass
    return links
```

를 다음으로 교체(마지막 줄의 `import`를 지우고 모듈레벨 `notebook_stage0` 사용, `notebook_id` 필드 추가):
```python
def _ensure_scenario(date: str) -> dict:
    """Stage 0: NotebookLM으로 out/scenario_{date}.md 생성(없을 때만) + 심층리포트 시도(비차단).
    반환: {"notebook_id": str|None, "notebook_url": str|None, "report_url": str|None}.
    실패해도 예외 없이 빈 값 반환."""
    links = {"notebook_id": None, "notebook_url": None, "report_url": None}
    scen = ROOT / "out" / f"scenario_{date}.md"
    if scen.exists():
        return links
    try:
        nb = notebook_stage0.build_notebook(date)
        if not nb or not nb.get("notebook_id"):
            return links
        links["notebook_id"] = nb.get("notebook_id")
        links["notebook_url"] = nb.get("url")
        text = notebook_stage0.query_card_content(nb["notebook_id"], date)
        if not text:
            return links
        scen.parent.mkdir(parents=True, exist_ok=True)
        scen.write_text(text, encoding="utf-8")
        report_url = notebook_stage0.generate_deep_report(nb["notebook_id"], date)
        if report_url:
            links["report_url"] = report_url
    except Exception:
        pass
    return links
```

- [ ] **Step 6: `run_morning_brief` — 인포그래픽 게이트 + 2차 발송**

현재:
```python
        png = _render_card(data, date)

        flags = verify.detect_anomalies(data, date, _get_index_moves())
        if not quality_ok:
            flags.append("품질 기준 미달(3회 개선 후에도)")

        if flags:                                    # fail-closed: 채널 발행 안 하고 에스컬레이션
            return _escalate(png, flags, date, links)

        caption = f"📊 {date} 아침 브리핑\n{data.get('headline', '')}"
        if links.get("notebook_url"):
            caption += f"\n🔗 더 깊게 보기: {links['notebook_url']}"
        viz_card.send_telegram_photo(png, caption)
        return {"status": "sent", "reasons": [], "png": png}
```

를 다음으로 교체:
```python
        png = _render_card(data, date)

        flags = verify.detect_anomalies(data, date, _get_index_moves())
        if not quality_ok:
            flags.append("품질 기준 미달(3회 개선 후에도)")

        infographic_path = notebook_stage0.generate_infographic(links.get("notebook_id"), date)
        if not infographic_path:
            flags.append("인포그래픽 생성 실패")

        if flags:                                    # fail-closed: 채널 발행 안 하고 에스컬레이션
            return _escalate(png, flags, date, links)

        caption = f"📊 {date} 아침 브리핑\n{data.get('headline', '')}"
        if links.get("notebook_url"):
            caption += f"\n🔗 더 깊게 보기: {links['notebook_url']}"
        viz_card.send_telegram_photo(png, caption)
        viz_card.send_telegram_photo(infographic_path, "")
        return {"status": "sent", "reasons": [], "png": png}
```

- [ ] **Step 7: 기존 5개 테스트의 `sent["photo"]` 단언문 갱신**

`tests/goal_loop/test_orchestrator.py`에서 `_patch`를 호출하는 기존 5개 테스트를 하나씩 열어
`sent["photo"]`를 비교하는 줄을 찾아 튜플 리스트에 맞게 고친다:

- `test_normal_day_sends_to_channel`: `assert sent["photo"] == [None]` →
  `assert [c for c, _p in sent["photo"]] == [None, None]`
  (텍스트카드+인포그래픽 2번 전송되므로 채널 chat_id=None이 2번 나옴 — `_patch`의 기본
  `infographic_path="ig.png"`가 성공 목킹이라 정상 발행 경로를 그대로 탄다)

- `test_anomaly_escalates_to_owner`: `assert sent["photo"] == ["999"]` →
  `assert [c for c, _p in sent["photo"]] == ["999"]`
  (에스컬레이션 경로는 인포그래픽 게이트 이전에 이미 flags가 있어 `_escalate`로 빠지므로 사진 1장만)

- `test_failclosed_no_owner_never_sends_to_channel`: `assert sent["photo"] == []` → 그대로 유지(튜플이든
  아니든 빈 리스트 비교는 동일하게 통과하므로 수정 불필요)

- `test_empty_data_escalates_never_fabricates`: `assert sent["photo"] == []` → 위와 동일, 수정 불필요

- `test_error_escalates_not_silent`: `sent["photo"]` 단언 없음(해당 테스트는 `_patch`를 안 씀) → 수정 불필요

- [ ] **Step 8: 통과 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_orchestrator.py -v`
Expected: 9 passed (기존 5 + 신규 2 + Task4 이전 세션의 `test_stage0_links_appended_to_caption_on_send`,
`test_stage0_returns_none_no_crash` 포함 총 9개 — 두 테스트도 `_ensure_scenario` 반환값에 `notebook_id`
필드가 추가됐으니 필요 시 `links` 딕셔너리에 `"notebook_id"` 키를 넣어 최신 스키마와 맞출 것,
`links.get("notebook_id")` 형태로 읽으므로 키가 없어도 `None`이 되어 안전하게 통과함)

- [ ] **Step 9: 전체 회귀 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/ tests/nlm_bridge/ tests/studio/test_card_render.py -v`
Expected: 전부 PASS, 실패 0 (nlm_bridge 18 + notebook_stage0 11 + orchestrator 9 + daemon_gate 2 +
pending 1 + verify 3 + quality 4 + publish_endpoint 2 + viz_chatid 1 + card_render 5 = 56 근방,
정확한 합은 실행 결과로 확인)

- [ ] **Step 10: 커밋**

```bash
git add scripts/goal_loop/morning_brief.py tests/goal_loop/test_orchestrator.py
git commit -m "feat(goal-loop): 히어로 이미지 제거 + NotebookLM 인포그래픽 병행발송(실패시 에스컬레이션)

card_render 히어로 없이 렌더. _ensure_scenario가 notebook_id 반환. 정상발행 조건에
인포그래픽 생성 성공 포함 — 실패하면 텍스트카드도 보류하고 에스컬레이션(둘 다
준비돼야 발행). 텔레그램에 텍스트카드+인포그래픽 순서로 2장 전송."
```

---

## Self-Review

- **스펙 커버리지**: §2 결정표(히어로제거/병행발송/실패시에스컬레이션/create_infographic신규/브랜드톤재사용) → Task1(히어로), Task2(create_infographic+BRAND_DESIGN), Task4(generate_infographic), Task5(게이트+2차발송) 전부 매핑. §3 아키텍처 A~D 블록 → Task1/2·3/4/5 순서대로 대응. §4 에러처리표(인포그래픽실패→에스컬레이션, 타임아웃→동일취급) → Task5 Step6의 `if not infographic_path: flags.append(...)`가 두 경우 다 흡수(생성함수가 타임아웃도 실패로 정규화해서 반환하므로 별도 분기 불필요).
- **플레이스홀더 스캔**: 없음 — 전 스텝 실제 코드·명령·기대결과 포함.
- **타입 일관성**: `nlm_bridge.create_infographic(nb_id, out_dir=None, focus="") -> dict`(Task2) ↔
  `notebook_stage0.generate_infographic`(Task4) 호출부 일치. `generate_infographic(notebook_id, date) -> str|None`
  ↔ `morning_brief.run_morning_brief`(Task5) 호출부 일치. `_ensure_scenario`의 `links["notebook_id"]`(Task5
  Step5) ↔ Step6에서 `links.get("notebook_id")`로 소비 — 일치.
- **하위호환**: `render_briefing_card(data, hero_path=None)`(Task1)의 기본값이 기존 호출부(`studio_pipeline.py`,
  hero 항상 전달)와 기존 테스트(hero 항상 전달) 동작을 그대로 보존함을 Step1에서 명시적으로 확인.
- **`sent["photo"]` 스키마 변경 파급**: Task5 Step1에서 `_patch`의 반환 구조를 튜플로 바꾸는 결정이
  기존 5개 테스트 전부에 영향을 준다는 것을 Step7에서 하나하나 짚어 빠짐없이 갱신 지시함(암묵적 누락 방지).

## 알려진 확인 항목(구현 중)
- `create_infographic`의 실제 CLI 인자(`--style professional --focus ...`)가 `nlm` 최신 버전과 정확히
  맞는지는 Task2 완료 후 실서버 스모크 테스트로 확인 필요(단위테스트는 `_run_nlm` 자체를 monkeypatch하므로
  CLI 문법 오류를 못 잡음 — 이는 Task1의 스펙에서도 동일하게 이미 감수한 리스크).
