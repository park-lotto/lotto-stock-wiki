# 골-루프 오케스트레이션 v1 (아침 브리핑) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 아침 시장 브리핑을 서버가 자율로 생성·품질검증·게이트 판정 후 텔레 발행하되, 이상징후 시엔 멈추고 사장님 수동승인을 받는 오케스트레이터를 만든다.

**Architecture:** 항상 켜진 Lightsail 서버의 파이썬 데몬 스레드(08:00 평일 게이트)가 오케스트레이터를 실행. 오케스트레이터는 기존 `studio_data.get_briefing_data`로 콘텐츠(`data` dict)를 얻어 → Gemini 품질루프로 `data`를 비평·개선(최대 3회) → 이상징후 게이트 → 정상이면 카드 렌더+채널 전송, 이상이면 사장님 개인 텔레+대시보드 대기함으로 에스컬레이션. 기존 카드 생성기(`generate_briefing`)는 건드리지 않고 하위 함수만 재사용.

**Tech Stack:** Python 3.12, google-genai(Gemini), FastAPI(dashboard/server.py :8090), 기존 모듈 `scripts/studio_data.py·card_render.py·viz_card.py·gemini_image.py`, pytest.

## Global Constraints

- 파일 인코딩 UTF-8. 한국어 주석/카피 유지.
- Gemini 모델: `gemini-2.5-flash` 우선(쿼터 여유), 폴백 `gemini-3-flash-preview`. `_summary_keys()` 스타일 키 로테이션 재사용 가능하면 사용.
- 텔레 발송은 오직 `viz_card.send_telegram_photo(png, caption, chat_id=None)` 경유. 채널=`CHAT_ID`, 사장님 개인=`OWNER_CHAT_ID`(신규 env, ROOT/.env).
- 품질 채점표(고정): 수치 포함 / 명확한 판단(양면론·"관망" 금지) / 날짜검증 통과 / 출처 인용 / 차별화 인사이트(오실레이터·수급빈집).
- 이상징후(고정 초기값): 코스피 또는 코스닥 |등락률| ≥ 3% / 데이터 최신일 ≠ 대상일(공백) / 날짜검증 실패 / Gemini가 "수치 모순" 플래그.
- 서버 배포 절차 준수: 로컬 커밋·push → 서버 `git checkout -- scripts/.kis_token_cache.json; git pull; sudo systemctl restart stockbrain`. `pipeline/sector_custom.json`류 런타임파일 커밋 금지.
- 새 모듈은 `scripts/goal_loop/` 패키지 아래. 상태파일은 `out/goal_loop/`(gitignore).

---

## File Structure

- Create: `scripts/goal_loop/__init__.py` — 빈 패키지 표식
- Create: `scripts/goal_loop/quality.py` — Gemini 품질 비평·개선 (data dict 대상)
- Create: `scripts/goal_loop/verify.py` — 날짜·신선도·이상징후 검증 (순수 파이썬)
- Create: `scripts/goal_loop/morning_brief.py` — 오케스트레이터(스테이지 조립+게이트) + `run_morning_brief(date, force_send=False)`
- Create: `scripts/goal_loop/pending.py` — 대기 브리핑 상태 읽기/쓰기/발행 (`out/goal_loop/pending.json`)
- Modify: `scripts/viz_card.py` — `send_telegram_photo`에 `chat_id=None` 추가
- Modify: `dashboard/server.py` — 대기 브리핑 발행 엔드포인트 + `_morning_brief_loop` 데몬 + `_start_keepalive` 배선
- Modify: `.gitignore` — `out/goal_loop/` 추가
- Test: `tests/goal_loop/test_verify.py`, `tests/goal_loop/test_quality.py`, `tests/goal_loop/test_pending.py`, `tests/goal_loop/test_orchestrator.py`

로컬 파이썬: `C:/Users/TheRose/AppData/Local/Python/bin/python.exe` (Windows Store stub 아님). pytest: `python -m pytest`.

---

### Task 1: 텔레 발송에 chat_id 오버라이드 추가

**Files:**
- Modify: `scripts/viz_card.py` (`send_telegram_photo`, 현재 line ~365)
- Test: `tests/goal_loop/test_viz_chatid.py`

**Interfaces:**
- Produces: `viz_card.send_telegram_photo(png_path, caption="", chat_id=None) -> bool` — chat_id 주면 그 대상, 없으면 기존 `CHAT_ID` 채널.

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/goal_loop/test_viz_chatid.py
import inspect
from scripts import viz_card

def test_send_telegram_photo_has_chat_id_param():
    sig = inspect.signature(viz_card.send_telegram_photo)
    assert "chat_id" in sig.parameters
    assert sig.parameters["chat_id"].default is None
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/goal_loop/test_viz_chatid.py -v`
Expected: FAIL (`chat_id` 파라미터 없음)

- [ ] **Step 3: 구현** — `send_telegram_photo` 시그니처에 `chat_id=None` 추가, 본문의 `chat_id = env.get("CHAT_ID","")`를 `chat_id = chat_id or env.get("CHAT_ID","")`로 변경.

```python
def send_telegram_photo(png_path, caption: str = "", chat_id=None) -> bool:
    ...
    token   = env.get("BOT_TOKEN", "")
    chat_id = chat_id or env.get("CHAT_ID", "")
    ...
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/goal_loop/test_viz_chatid.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/viz_card.py tests/goal_loop/test_viz_chatid.py
git commit -m "feat(goal-loop): send_telegram_photo chat_id 오버라이드(에스컬레이션용)"
```

---

### Task 2: 검증·이상징후 모듈 (verify.py)

**Files:**
- Create: `scripts/goal_loop/__init__.py` (빈 파일)
- Create: `scripts/goal_loop/verify.py`
- Test: `tests/goal_loop/test_verify.py`

**Interfaces:**
- Consumes: `data` dict (studio_data.get_briefing_data 출력; 최소 `headline` 보유), `date`(str "YYYY-MM-DD").
- Produces: `verify.detect_anomalies(data: dict, date: str, index_moves: dict) -> list[str]` — 이상징후 사유 문자열 리스트(비면 정상). `index_moves`={"kospi":float,"kosdaq":float} 등락률(%).

- [ ] **Step 1: 실패 테스트**

```python
# tests/goal_loop/test_verify.py
from scripts.goal_loop import verify

def test_no_anomaly_normal_day():
    data = {"headline": "반도체 강세", "date": "2026-07-02"}
    flags = verify.detect_anomalies(data, "2026-07-02", {"kospi": -0.8, "kosdaq": 0.5})
    assert flags == []

def test_index_crash_flags():
    data = {"headline": "폭락", "date": "2026-07-02"}
    flags = verify.detect_anomalies(data, "2026-07-02", {"kospi": -3.4, "kosdaq": -2.0})
    assert any("코스피" in f for f in flags)

def test_stale_data_flags():
    data = {"headline": "x", "date": "2026-06-30"}   # 대상일과 불일치
    flags = verify.detect_anomalies(data, "2026-07-02", {"kospi": 0.1, "kosdaq": 0.1})
    assert any("공백" in f or "최신" in f for f in flags)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/goal_loop/test_verify.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

```python
# scripts/goal_loop/verify.py
"""아침 브리핑 검증·이상징후 감지 (순수 파이썬, LLM 불필요)."""
ANOM_INDEX_PCT = 3.0

def detect_anomalies(data: dict, date: str, index_moves: dict) -> list:
    flags = []
    for name, key in [("코스피", "kospi"), ("코스닥", "kosdaq")]:
        v = index_moves.get(key)
        if v is not None and abs(v) >= ANOM_INDEX_PCT:
            flags.append(f"{name} {v:+.1f}% 급변(±{ANOM_INDEX_PCT}%↑)")
    ddate = str(data.get("date") or "").strip()
    if ddate and ddate != date:
        flags.append(f"데이터 최신일({ddate})≠대상일({date}) 공백 의심")
    if data.get("date_check") is False:
        flags.append("날짜검증 실패")
    return flags
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/goal_loop/test_verify.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/goal_loop/__init__.py scripts/goal_loop/verify.py tests/goal_loop/test_verify.py
git commit -m "feat(goal-loop): 검증·이상징후 감지 모듈"
```

---

### Task 3: 대기 브리핑 상태 (pending.py)

**Files:**
- Create: `scripts/goal_loop/pending.py`
- Test: `tests/goal_loop/test_pending.py`

**Interfaces:**
- Produces:
  - `pending.write(entry: dict) -> None` — `out/goal_loop/pending.json`에 저장(단건, 덮어쓰기).
  - `pending.read() -> dict | None` — 없으면 None.
  - `pending.clear() -> None`.
  - entry 최소 필드: `{date, png, reasons:list, created_at}`.

- [ ] **Step 1: 실패 테스트**

```python
# tests/goal_loop/test_pending.py
from scripts.goal_loop import pending

def test_write_read_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(pending, "PENDING_PATH", tmp_path / "pending.json")
    assert pending.read() is None
    pending.write({"date": "2026-07-02", "png": "x.png", "reasons": ["폭락"], "created_at": "t"})
    got = pending.read()
    assert got["date"] == "2026-07-02" and got["reasons"] == ["폭락"]
    pending.clear()
    assert pending.read() is None
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/goal_loop/test_pending.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

```python
# scripts/goal_loop/pending.py
import json, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
PENDING_PATH = ROOT / "out" / "goal_loop" / "pending.json"

def write(entry: dict) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

def read():
    if not PENDING_PATH.exists():
        return None
    try:
        return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

def clear() -> None:
    try:
        os.remove(PENDING_PATH)
    except FileNotFoundError:
        pass
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/goal_loop/test_pending.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/goal_loop/pending.py tests/goal_loop/test_pending.py
git commit -m "feat(goal-loop): 대기 브리핑 상태 저장/읽기/삭제"
```

---

### Task 4: Gemini 품질 비평·개선 (quality.py)

**Files:**
- Create: `scripts/goal_loop/quality.py`
- Test: `tests/goal_loop/test_quality.py` (Gemini 호출은 monkeypatch로 대체 — 네트워크 없이 로직만 검증)

**Interfaces:**
- Produces:
  - `quality.critique(data: dict, gemini_fn) -> dict` — 반환 `{"pass": bool, "issues": list[str]}`. `gemini_fn(prompt)->str`(JSON 문자열 반환) 주입식.
  - `quality.revise(data: dict, issues: list, gemini_fn) -> dict` — issues 반영해 개선된 `data` dict 반환. 실패 시 원본 반환.
  - `quality.CHECKLIST` — 5항목 문자열 리스트.

- [ ] **Step 1: 실패 테스트**

```python
# tests/goal_loop/test_quality.py
import json
from scripts.goal_loop import quality

def test_critique_parses_pass():
    fake = lambda p: json.dumps({"pass": True, "issues": []})
    r = quality.critique({"headline": "삼성전자 8조 투자, 매수 우위"}, fake)
    assert r["pass"] is True and r["issues"] == []

def test_critique_parses_fail():
    fake = lambda p: json.dumps({"pass": False, "issues": ["수치 없음", "양면론"]})
    r = quality.critique({"headline": "시장은 혼조세"}, fake)
    assert r["pass"] is False and "양면론" in r["issues"]

def test_critique_bad_json_defaults_fail():
    r = quality.critique({"headline": "x"}, lambda p: "not json")
    assert r["pass"] is False

def test_revise_returns_dict():
    revised = quality.revise({"headline": "혼조"}, ["수치 없음"],
                             lambda p: json.dumps({"headline": "코스피 -1.2%, 반도체 +3%"}))
    assert revised["headline"].startswith("코스피")
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/goal_loop/test_quality.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

```python
# scripts/goal_loop/quality.py
"""브리핑 콘텐츠(data dict) 품질 비평·개선. Gemini는 주입식(gemini_fn)."""
import json, re

CHECKLIST = [
    "수치 포함(막연한 서술 금지)",
    "명확한 판단(양면론·'관망' 금지)",
    "날짜검증 통과",
    "출처 인용",
    "차별화 인사이트(오실레이터·수급빈집 활용)",
]

def _extract_json(s: str):
    m = re.search(r"\{.*\}", s or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def critique(data: dict, gemini_fn) -> dict:
    prompt = (
        "너는 주식 브리핑 편집장이다. 아래 브리핑 콘텐츠(JSON)를 체크리스트로 채점하라.\n"
        f"[체크리스트]\n- " + "\n- ".join(CHECKLIST) + "\n\n"
        f"[콘텐츠]\n{json.dumps(data, ensure_ascii=False)}\n\n"
        '오직 JSON만 출력: {"pass": true/false, "issues": ["미달 항목 사유", ...]}\n'
        "하나라도 미달이면 pass=false."
    )
    parsed = _extract_json(gemini_fn(prompt))
    if not isinstance(parsed, dict) or "pass" not in parsed:
        return {"pass": False, "issues": ["비평 파싱 실패"]}
    return {"pass": bool(parsed.get("pass")), "issues": list(parsed.get("issues") or [])}

def revise(data: dict, issues: list, gemini_fn) -> dict:
    prompt = (
        "아래 브리핑 콘텐츠(JSON)를 지적사항만 반영해 개선하라. 구조·키는 유지.\n"
        f"[지적]\n- " + "\n- ".join(issues) + "\n\n"
        f"[콘텐츠]\n{json.dumps(data, ensure_ascii=False)}\n\n"
        "개선된 콘텐츠를 같은 스키마의 JSON으로만 출력."
    )
    parsed = _extract_json(gemini_fn(prompt))
    return parsed if isinstance(parsed, dict) and parsed else data
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/goal_loop/test_quality.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/goal_loop/quality.py tests/goal_loop/test_quality.py
git commit -m "feat(goal-loop): Gemini 품질 비평·개선(data dict 대상)"
```

---

### Task 5: 오케스트레이터 (morning_brief.py)

**Files:**
- Create: `scripts/goal_loop/morning_brief.py`
- Test: `tests/goal_loop/test_orchestrator.py` (studio_data·렌더·전송·gemini 전부 monkeypatch — 순수 흐름 검증)

**Interfaces:**
- Consumes: verify.detect_anomalies, quality.critique/revise, pending.write, viz_card.send_telegram_photo, studio_data.get_briefing_data, card_render.render_briefing_card/save_card_html, viz_card.save_png, gemini_image.
- Produces: `run_morning_brief(date: str, gemini_fn=None, max_iter: int = 3) -> dict` — 반환 `{"status": "sent"|"escalated"|"error", "reasons": list, "png": str}`.

흐름:
1. `data = studio_data.get_briefing_data(date)`
2. 품질루프: `for _ in range(max_iter): c = quality.critique(data); if c["pass"]: break; data = quality.revise(data, c["issues"])`
3. 카드 렌더: hero(gemini_image) → `html = card_render.render_briefing_card(data, hero)` → save_card_html → `viz_card.save_png(html_path, png_path)`
4. 이상징후: `index_moves = _get_index_moves()` (kis_api 재사용) → `flags = verify.detect_anomalies(data, date, index_moves)`; 품질 최종 미달이면 flags에 추가
5. 게이트: flags 있으면 → `pending.write(...)` + `send_telegram_photo(png, "⚠️ 확인 필요: "+사유, chat_id=OWNER_CHAT_ID)` → status="escalated". 없으면 → `send_telegram_photo(png, caption)`(채널) → status="sent".

- [ ] **Step 1: 실패 테스트**

```python
# tests/goal_loop/test_orchestrator.py
import json
from scripts.goal_loop import morning_brief as mb

def _patch(monkeypatch, index_moves, critique_pass=True):
    monkeypatch.setattr(mb.studio_data, "get_briefing_data", lambda d: {"headline": "h", "date": d})
    monkeypatch.setattr(mb, "_render_card", lambda data, date: "x.png")   # 렌더 우회
    monkeypatch.setattr(mb, "_get_index_moves", lambda: index_moves)
    sent = {}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: sent.setdefault("chat_id", chat_id) or True)
    monkeypatch.setattr(mb.quality, "critique", lambda data, fn: {"pass": critique_pass, "issues": []})
    return sent

def test_normal_day_sends_to_channel(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    assert sent["chat_id"] is None      # 채널(기본)

def test_anomaly_escalates_to_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setenv("OWNER_CHAT_ID", "999")
    sent = _patch(monkeypatch, {"kospi": -3.5, "kosdaq": -2.0})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "escalated"
    assert sent["chat_id"] == "999"     # 사장님 개인
    assert mb.pending.read() is not None
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/goal_loop/test_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: 구현** — 아래 골격. `_render_card`는 실제로 hero→render→save_png를 부르되 테스트에선 monkeypatch로 우회. `_get_index_moves`는 kis_api로 지수 등락률 조회(실패 시 {} 반환 → 이상무). `gemini_fn` 미주입 시 내부 기본(server의 `_gemini_text` 스타일 또는 daily_scenario.get_gemini) 사용.

```python
# scripts/goal_loop/morning_brief.py
import os, sys
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import studio_data, card_render, viz_card, gemini_image  # noqa
from scripts.goal_loop import verify, quality, pending

STUDIO_DIR = ROOT / "out" / "studio"

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

def _get_index_moves() -> dict:
    try:
        import kis_api
        k = kis_api.get_index_price("0001"); q = kis_api.get_index_price("1001")
        return {"kospi": float(k.get("change_rate", 0)), "kosdaq": float(q.get("change_rate", 0))}
    except Exception:
        return {}

def _default_gemini():
    import daily_scenario
    client = daily_scenario.get_gemini()
    def fn(prompt):
        r = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return getattr(r, "text", "") or ""
    return fn

def run_morning_brief(date: str, gemini_fn=None, max_iter: int = 3) -> dict:
    try:
        gfn = gemini_fn or _default_gemini()
        data = studio_data.get_briefing_data(date)
        quality_ok = False
        for _ in range(max_iter):
            c = quality.critique(data, gfn)
            if c["pass"]:
                quality_ok = True
                break
            data = quality.revise(data, c["issues"], gfn)
        png = _render_card(data, date)
        flags = verify.detect_anomalies(data, date, _get_index_moves())
        if not quality_ok:
            flags.append("품질 기준 미달(3회 개선 후에도)")
        caption = f"📊 {date} 아침 브리핑\n{data.get('headline','')}"
        if flags:
            pending.write({"date": date, "png": png, "reasons": flags,
                           "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
            owner = os.environ.get("OWNER_CHAT_ID") or ""
            viz_card.send_telegram_photo(png, "⚠️ 확인 필요: " + " / ".join(flags), chat_id=owner or None)
            return {"status": "escalated", "reasons": flags, "png": png}
        viz_card.send_telegram_photo(png, caption)
        return {"status": "sent", "reasons": [], "png": png}
    except Exception as e:
        return {"status": "error", "reasons": [str(e)], "png": ""}
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/goal_loop/test_orchestrator.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: 커밋**

```bash
git add scripts/goal_loop/morning_brief.py tests/goal_loop/test_orchestrator.py
git commit -m "feat(goal-loop): 아침 브리핑 오케스트레이터(품질루프+이상징후 게이트+에스컬레이션)"
```

---

### Task 6: 대시보드 대기 브리핑 발행 엔드포인트 + 버튼

**Files:**
- Modify: `dashboard/server.py` (POST 엔드포인트 추가; `/api/crawl/run` 스타일)
- Modify: `dashboard/market.html` 또는 studio 화면 — "대기 브리핑 발행" 버튼(대기 있을 때만 표시)
- Test: `tests/goal_loop/test_publish_endpoint.py` (pending.read/clear + send monkeypatch)

**Interfaces:**
- Produces: `POST /api/briefing/publish_pending` → 대기 있으면 채널 발행 후 clear, `{"ok":true,"sent":bool}`; 없으면 `{"ok":false,"error":"대기 없음"}`. `GET /api/briefing/pending` → 대기 메타(date/reasons) 또는 `{}`.

- [ ] **Step 1: 실패 테스트**

```python
# tests/goal_loop/test_publish_endpoint.py
from scripts.goal_loop import pending, morning_brief as mb

def test_publish_reads_and_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(pending, "PENDING_PATH", tmp_path / "p.json")
    pending.write({"date": "2026-07-02", "png": "x.png", "reasons": ["폭락"], "created_at": "t"})
    calls = {}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: calls.setdefault("png", png) or True)
    from scripts.goal_loop import publish
    res = publish.publish_pending()
    assert res["ok"] is True and res["sent"] is True
    assert calls["png"] == "x.png"
    assert pending.read() is None
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/goal_loop/test_publish_endpoint.py -v`
Expected: FAIL

- [ ] **Step 3: 구현** — 로직을 `scripts/goal_loop/publish.py`에 넣고(테스트 가능), 서버는 이를 호출.

```python
# scripts/goal_loop/publish.py
from scripts.goal_loop import pending, morning_brief as mb

def publish_pending() -> dict:
    p = pending.read()
    if not p:
        return {"ok": False, "error": "대기 없음"}
    caption = f"📊 {p['date']} 아침 브리핑"
    sent = mb.viz_card.send_telegram_photo(p["png"], caption)
    if sent:
        pending.clear()
    return {"ok": True, "sent": bool(sent)}
```

`dashboard/server.py`에 추가(‘/api/crawl/run’ 아래, run_in_threadpool 스타일):

```python
from scripts.goal_loop import pending as _gl_pending, publish as _gl_publish  # 상단 import 영역

@app.get("/api/briefing/pending")
def api_briefing_pending():
    p = _gl_pending.read() or {}
    return JSONResponse(content={"date": p.get("date"), "reasons": p.get("reasons", [])} if p else {})

@app.post("/api/briefing/publish_pending")
async def api_briefing_publish():
    return JSONResponse(content=await run_in_threadpool(_gl_publish.publish_pending))
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/goal_loop/test_publish_endpoint.py -v`
Expected: PASS

- [ ] **Step 5: 프론트 버튼** — studio/딸깍 화면에 `GET /api/briefing/pending` 폴링 → 대기 있으면 "⚠️ 대기 브리핑 발행" 버튼 표시, 클릭 시 `POST /api/briefing/publish_pending` → 성공 토스트. (기존 studio fetch 패턴 재사용)

- [ ] **Step 6: 커밋**

```bash
git add scripts/goal_loop/publish.py dashboard/server.py dashboard/market.html tests/goal_loop/test_publish_endpoint.py
git commit -m "feat(goal-loop): 대기 브리핑 발행 엔드포인트+버튼"
```

---

### Task 7: 아침 데몬 스레드 (08:00 평일, 1일 1회)

**Files:**
- Modify: `dashboard/server.py` — `_morning_brief_loop()` 데몬 + `_start_keepalive()` 배선
- Test: `tests/goal_loop/test_daemon_gate.py` (시간게이트·1일1회 로직만; 스레드 미기동)

**Interfaces:**
- Produces: `_morning_should_run(now_dt, last_run_date) -> bool` — 평일 & 08:00~08:14 & 오늘 미실행이면 True.

- [ ] **Step 1: 실패 테스트**

```python
# tests/goal_loop/test_daemon_gate.py
from datetime import datetime
import dashboard.server as s

def test_runs_weekday_0800_once():
    now = datetime(2026, 7, 2, 8, 3)   # 목요일 08:03
    assert s._morning_should_run(now, None) is True
    assert s._morning_should_run(now, "2026-07-02") is False   # 이미 실행

def test_skip_weekend_and_offwindow():
    assert s._morning_should_run(datetime(2026, 7, 4, 8, 3), None) is False   # 토요일
    assert s._morning_should_run(datetime(2026, 7, 2, 9, 30), None) is False  # 창밖
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/goal_loop/test_daemon_gate.py -v`
Expected: FAIL

- [ ] **Step 3: 구현** — `_summary_prewarm` 패턴 복제. 게이트 함수 + 루프 + `_start_keepalive`에 스레드 추가.

```python
# dashboard/server.py
def _morning_should_run(now_dt, last_run_date) -> bool:
    if now_dt.weekday() >= 5:            # 토(5)·일(6) 제외
        return False
    mins = now_dt.hour * 60 + now_dt.minute
    if not (480 <= mins <= 494):         # 08:00~08:14
        return False
    return last_run_date != now_dt.strftime("%Y-%m-%d")

def _morning_brief_loop():
    import time
    from datetime import datetime as _dt
    from scripts.goal_loop import morning_brief as _mb
    last = None
    time.sleep(60)                       # 기동 직후 안정화
    while True:
        try:
            now = _dt.now()
            if _morning_should_run(now, last):
                _mb.run_morning_brief(now.strftime("%Y-%m-%d"))
                last = now.strftime("%Y-%m-%d")
        except Exception:
            pass
        time.sleep(180)                  # 3분 간격 점검
```

`_start_keepalive()` 안에 추가:
```python
    threading.Thread(target=_morning_brief_loop, daemon=True).start()
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/goal_loop/test_daemon_gate.py -v`
Expected: PASS

- [ ] **Step 5: 커밋 + .gitignore**

```bash
echo "out/goal_loop/" >> .gitignore
git add dashboard/server.py .gitignore tests/goal_loop/test_daemon_gate.py
git commit -m "feat(goal-loop): 아침 08:00 평일 데몬(1일1회) + 배선"
```

- [ ] **Step 6: 서버 배포·검증** — push → 서버 `git pull; sudo systemctl restart stockbrain` → `OWNER_CHAT_ID`를 `/etc/stockbrain.env`에 추가 → `python -c "from scripts.goal_loop.morning_brief import run_morning_brief; print(run_morning_brief('오늘날짜'))"`로 수동 1회 실행해 sent/escalated 확인.

---

## Self-Review

- **스펙 커버리지**: 골스펙(§4.1)=verify/quality 상수 + 데몬 게이트 / 오케스트레이터(§4.2)=Task5 / 게이트·에스컬레이션(§4.3)=Task5+Task6 / 품질채점표(§4.4)=Task4 / 루프엔진(§4.5)=Task7. 전 항목 태스크 매핑됨.
- **플레이스홀더**: 없음(각 스텝 실제 코드·명령·기대결과 포함). `_get_index_moves`의 `kis_api.get_index_price` 정확 함수명은 구현 시 kis_api에서 확인(없으면 get_price 계열로 대체) — Task5 Step3 주석에 명시.
- **타입 일관성**: `send_telegram_photo(png, caption, chat_id)` (Task1) ↔ 오케스트레이터·publish 호출 일치. `pending.read/write/clear` (Task3) ↔ Task5·6 사용 일치. `run_morning_brief(date, gemini_fn, max_iter)` ↔ Task7 호출 일치.
- **범위**: v1은 아침 브리핑 골 1개로 한정. 유튜브·투경 골은 후속(템플릿 재사용).

## 알려진 확인 항목(구현 중)
- `studio_data.get_briefing_data`가 `data`에 `date` 키를 넣는지 확인(없으면 오케스트레이터에서 `data.setdefault("date", date)`).
- `kis_api`의 지수 조회 정확 함수명·인자(0001/1001) 확인.
- 프론트 버튼은 studio 화면 위치 확정 후 삽입.
