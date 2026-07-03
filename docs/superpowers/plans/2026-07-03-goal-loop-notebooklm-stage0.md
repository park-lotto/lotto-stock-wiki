# 골루프 Stage0 NotebookLM 교체 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 아침 브리핑 골-루프의 Stage0(콘텐츠 생성)을 daily_scenario.py(단일 Gemini, 저품질)에서 NotebookLM 기반(실제 오늘자 크롤링 소스에 근거, 인용 강제)으로 교체하고, 매일 카드(A)+심층리포트(B) 링크를 함께 만든다.

**Architecture:** 기존 `dashboard/server.py`에 흩어져 있던 NLM CLI 순수함수를 `scripts/nlm_bridge.py`로 추출(부작용 없음, import 안전)하고 신규 고수준 함수(create_notebook/add_source_file/notebook_query/create_report)를 추가한다. `scripts/goal_loop/notebook_stage0.py`가 이를 조합해 Stage0을 구현하고, `morning_brief.py`의 `_ensure_scenario`가 daily_scenario 서브프로세스 호출 대신 이를 호출하도록 교체한다. 오케스트레이터(품질루프·게이트·에스컬레이션·데몬)는 무수정.

**Tech Stack:** Python 3.12, `nlm` CLI(subprocess), sqlite3(atoms.db), pytest, monkeypatch 기반 단위테스트(실제 nlm/네트워크 호출 없음).

## Global Constraints

- 파일 인코딩 UTF-8. 한국어 주석/문자열 유지.
- `nlm_bridge.py`는 `dashboard/server.py`를 import하지 않는다(순환/부작용 위험). 반대 방향(server.py가 nlm_bridge를 import)만 허용.
- 기존 3개 엔드포인트(`/api/insights/to_notebook`, `/api/insights/notebook_query`, `/api/insights/notebook_card`)의 **HTTP 응답 스키마는 절대 변경 금지** — 내부 구현만 nlm_bridge 호출로 교체.
- `_ensure_scenario`/`_escalate`/`run_morning_brief`의 기존 시그니처는 **하위호환 유지**: `_ensure_scenario`가 `None` 리턴하도록 monkeypatch된 기존 테스트가 그대로 통과해야 함(`stage0 = _ensure_scenario(date) or {}` 방어).
- 로컬 파이썬: `C:/Users/TheRose/AppData/Local/Python/bin/python.exe` (Windows Store stub 아님). pytest: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest`.
- `dashboard/server.py`는 동시에 다른 세션이 편집 중일 수 있다 — **줄번호로 확정하지 말고 각 Task 실행 직전 `grep -n`으로 현재 위치를 재확인**할 것.
- 카드 콘텐츠 파서 호환: `notebook_query`의 질문이 요구하는 출력 포맷은 `scripts/studio_data.py`의 `_MARKERS`(📌🔴🔵⚠️📅💡🎯)와 **정확히 일치**해야 함(변경 금지, 이 파서는 무수정).

---

## File Structure

- Create: `scripts/nlm_bridge.py` — NLM CLI 저수준 래퍼 + atoms.db 검색/번들 + 고수준 notebook 함수(순수, side-effect-free import)
- Modify: `dashboard/server.py` — 기존 NLM 관련 로컬 함수 제거, `from nlm_bridge import ...`로 교체. 3개 엔드포인트 내부 구현을 nlm_bridge 호출로 교체
- Create: `scripts/goal_loop/notebook_stage0.py` — `build_notebook(date)`, `query_card_content(nb_id, date)`, `generate_deep_report(nb_id, date)`
- Modify: `scripts/goal_loop/morning_brief.py` — `_ensure_scenario` 교체, `_escalate`/`run_morning_brief`에 링크 전파
- Test: `tests/nlm_bridge/test_pure_helpers.py`, `tests/nlm_bridge/test_notebook_calls.py`, `tests/goal_loop/test_notebook_stage0.py`, `tests/goal_loop/test_orchestrator.py`(기존 파일 보강)

---

### Task 1: `scripts/nlm_bridge.py` 생성 — 저수준 추출 + 고수준 래퍼

**Files:**
- Create: `scripts/nlm_bridge.py`
- Test: `tests/nlm_bridge/__init__.py`(빈 파일), `tests/nlm_bridge/test_pure_helpers.py`, `tests/nlm_bridge/test_notebook_calls.py`

**Interfaces:**
- Produces (기존 dashboard/server.py에서 동작 그대로 이동):
  - `_nlm_exe() -> str|None`, `_run_nlm(args, timeout=90, _auth_retry=True) -> (bool, str, str)`, `_friendly_nlm_err(msg) -> str`
  - `_valid_period(period) -> str`, `_tokenize_query(q) -> list`, `_nb_cat_of(st) -> str`, `_nb_cats_types(cats) -> list`, `_nb_period_min(period) -> str|None`
  - `_nb_fetch_rows(conn, q, cats=None, period="all", limit=200) -> (rows, toks, label)`, `_nb_md_for_rows(title_label, rows, today) -> str`, `_nb_scope_label(cats, period) -> str`
  - `_build_notebook_bundle(q, cats=None, period="all", limit=200, split=False, include_urls=True) -> dict|None`
- Produces (신규 고수준 함수, Task 2·3에서 사용):
  - `create_notebook(title: str) -> dict` — `{"ok": bool, "notebook_id": str|None, "error": str}`
  - `add_source_file(nb_id: str, file_path: str, title: str) -> dict` — `{"ok": bool, "error": str}`
  - `add_source_urls(nb_id: str, yt_urls: list, web_urls: list) -> dict` — `{"ok": bool, "error": str}`
  - `notebook_query(nb_id: str, question: str, conv: str = "", timeout: int = 180) -> dict` — `{"ok": bool, "answer": str, "conversation_id": str, "error": str}`
  - `create_report(nb_id: str, fmt: str = "Briefing Doc", language: str = "ko", out_dir: str = None) -> dict` — `{"ok": bool, "markdown": str, "ready": bool, "url": str, "error": str}`

- [ ] **Step 1: 저수준 함수 위치 재확인(동시편집 대비)**

Run: `grep -n "^_SEARCH_STOP\|^def _tokenize_query\|^def _nlm_exe\|^_CAT_LABEL\|^def _ins_conn\|^def _nlm_relogin_locked\|^def _run_nlm\|^def _friendly_nlm_err\|^def _nb_cat_of\|^def _nb_period_min\|^def _valid_period\|^def _nb_cats_types\|^def _nb_fetch_rows\|^def _nb_md_for_rows\|^def _nb_scope_label\|^def _build_notebook_bundle" dashboard/server.py`

각 함수의 현재 본문을 이 계획서 아래 Step 2의 코드와 대조해 동일한지 확인(동시 세션이 수정했으면 그 내용 기준으로 옮길 것).

- [ ] **Step 2: `scripts/nlm_bridge.py` 작성 — 저수준부**

```python
"""NotebookLM CLI 브리지 — 순수 함수만(부작용 없음, dashboard.server를 import하지 않음).
dashboard/server.py의 인사이트허브 NLM 엔드포인트와 골루프 Stage0(notebook_stage0.py)가
동일한 함수를 공유한다."""
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── atoms.db 연결 ──────────────────────────────────────────
def _ins_conn():
    """atoms.db 연결. 없으면 None."""
    db_path = ROOT / "pipeline" / "atoms" / "atoms.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── 검색 키워드 토크나이저 ──────────────────────────────────
_SEARCH_STOP = {
    "오늘", "내일", "어제", "지금", "요즘", "최근", "관련", "어떤", "무슨", "무엇",
    "있는", "있는지", "없는", "인지", "그리고", "정리", "정리해줘", "알려줘", "알려",
    "해줘", "보여줘", "대해", "대한", "이슈", "이슈가", "소식", "현황", "상황",
    "어때", "어떻게", "이게", "저게", "그게", "정도", "관해",
}


def _tokenize_query(q):
    """자연어 문장에서 검색 키워드 토큰 추출. 못 뽑으면 원문만."""
    raw = re.split(r"[\s,./·…]+", (q or "").strip())
    toks, seen = [], set()
    for t in raw:
        t = re.sub(r"(은|는|이|가|을|를|의|에|에서|으로|로|와|과|도|만|관련|이슈가|이슈|에대해|에대한)$", "", t.strip())
        if len(t) >= 2 and t not in _SEARCH_STOP and t not in seen:
            seen.add(t)
            toks.append(t)
    return toks or [(q or "").strip()]


# ── nlm CLI 저수준 ──────────────────────────────────────────
def _nlm_exe():
    """nlm 실행 파일 경로. PATH 우선, 없으면 None."""
    return shutil.which("nlm") or shutil.which("nlm.exe")


_NLM_AUTH_SIGNS = ("Authentication expired", "AuthenticationError", "Authentication Error",
                   "re-authenticate", "Could not retrieve notebook")
_NLM_LOGIN_LOCK = threading.Lock()


def _nlm_relogin_locked():
    """nlm 재로그인 — 락으로 직렬화(동시 Chrome 프로필 충돌 방지). 이미 유효하면 스킵."""
    with _NLM_LOGIN_LOCK:
        cok, cout, _ = _run_nlm(["login", "--check"], timeout=40, _auth_retry=False)
        if cok and "valid" in (cout or "").lower():
            return True
        lok, _o, _e = _run_nlm(["login"], timeout=320, _auth_retry=False)
        return lok


def _run_nlm(args, timeout=90, _auth_retry=True):
    """nlm CLI 호출. (ok, stdout, stderr) 반환.
    인증 만료로 실패하면 자동 재로그인 후 1회 재시도(self-healing)."""
    exe = _nlm_exe()
    if not exe:
        return False, "", "nlm CLI를 찾을 수 없음 (PATH 확인)"
    try:
        p = subprocess.run(
            [exe] + args,
            capture_output=True, text=True, encoding="utf-8",
            timeout=timeout, cwd=str(ROOT),
        )
        ok, out, err = (p.returncode == 0), (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "", f"nlm 타임아웃({timeout}s)"
    except Exception as e:
        return False, "", str(e)
    is_login = bool(args) and args[0] == "login"
    if _auth_retry and not is_login and any(s in (out + " " + err) for s in _NLM_AUTH_SIGNS):
        if _nlm_relogin_locked():
            return _run_nlm(args, timeout=timeout, _auth_retry=False)
    if not ok:
        return False, out, (err or out or f"exit {p.returncode}")
    return True, out, err


def _friendly_nlm_err(msg):
    """nlm 에러를 사용자 친화적으로 — 특히 인증 만료."""
    m = msg or ""
    if any(s in m for s in ("Authentication expired", "Could not retrieve notebook",
                            "re-authenticate", "AuthenticationError")):
        return "⚠️ NotebookLM 로그인이 만료됐습니다. 터미널에서 'nlm login' 실행 후 다시 시도하세요."
    return m[:200]


# ── 카테고리/기간 필터 ───────────────────────────────────────
_CAT_LABEL = {
    "youtube":  ("유튜브",   "📺"),
    "telegram": ("텔레그램", "💬"),
    "blog":     ("블로그",   "📝"),
    "report":   ("리포트",   "📰"),
    "news":     ("뉴스",     "🗞️"),
}


def _nb_cat_of(st):
    st = st or ""
    if st in ("youtube", "yt"):
        return "youtube"
    if st == "telegram":
        return "telegram"
    if st in ("blog", "report", "news"):
        return st
    return st


def _nb_period_min(period):
    """기간 프리셋 → 시작 날짜(YYYY-MM-DD) 또는 None(전체).
    today=오늘, dN=N일 전(오늘 포함 N+1일 창)."""
    p = (period or "all").strip()
    if p in ("", "all"):
        return None
    if p == "today":
        return datetime.now().strftime("%Y-%m-%d")
    m = re.match(r"^d(\d+)$", p)
    if m:
        return (datetime.now() - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    return None


def _valid_period(period):
    p = (period or "all").strip()
    return p if (p in ("all", "today") or re.match(r"^d(\d+)$", p)) else "all"


def _nb_cats_types(cats):
    """카테고리 id 리스트 → source_type 리스트(youtube는 yt 포함)."""
    types = []
    for c in (cats or []):
        if c == "youtube":
            types += ["youtube", "yt"]
        elif c in ("telegram", "report", "blog", "news"):
            types.append(c)
    return types


def _nb_fetch_rows(conn, q, cats=None, period="all", limit=200):
    """토큰 매칭 + 카테고리/기간 필터 + 토큰겹침 랭킹. (rows, toks, label)."""
    toks = _tokenize_query(q)
    label = " ".join(toks)
    clauses = ["(" + " OR ".join(["content LIKE ? OR asset LIKE ?"] * len(toks)) + ")"]
    params = []
    for t in toks:
        params += [f"%{t}%", f"%{t}%"]
    types = _nb_cats_types(cats) if cats else None
    if types:
        clauses.append("source_type IN (" + ",".join(["?"] * len(types)) + ")")
        params += types
    dmin = _nb_period_min(period)
    if dmin:
        clauses.append("date >= ?")
        params.append(dmin)
    sql = ("SELECT source_type, source_name, raw_file, date, content, asset, "
           "stance_key, deeplink FROM atoms WHERE " + " AND ".join(clauses) +
           " ORDER BY date DESC LIMIT 500")
    rows = conn.execute(sql, params).fetchall()

    def _score(r):
        text = (r["content"] or "") + " " + (r["asset"] or "")
        return sum(1 for t in toks if t in text)
    cap = max(1, min(int(limit or 200), 500))
    rows = sorted(rows, key=lambda r: (_score(r), r["date"] or ""), reverse=True)[:cap]
    return rows, toks, label


def _nb_md_for_rows(title_label, rows, today):
    """rows → 마크다운 (카테고리/소스별 그룹)."""
    order = ["youtube", "telegram", "report", "blog", "news"]
    groups = {}
    for r in rows:
        groups.setdefault((_nb_cat_of(r["source_type"]), r["source_name"] or "?"), []).append(r)
    lines = [
        f"# {title_label} — 인사이트 허브 가로검색 묶음 ({today})",
        f"_총 {len(rows)}개 발언 · 소스 {len(groups)}개 · 로또의 주식 인사이트 허브 추출_",
        "",
    ]
    for key in sorted(groups.keys(),
                      key=lambda k: (order.index(k[0]) if k[0] in order else 99, k[1])):
        cat, src = key
        clabel, icon = _CAT_LABEL.get(cat, (cat, "•"))
        lines.append(f"## {icon} [{clabel}] {src}")
        for r in groups[key]:
            stance = f" `{r['stance_key']}`" if r["stance_key"] else ""
            asset = f" ({r['asset']})" if r["asset"] else ""
            dl = (r["deeplink"] or "").strip()
            src_tag = f" — {dl}" if dl.startswith("http") else ""
            lines.append(f"- {(r['content'] or '').strip()}{asset}{stance}  ·{r['date'] or ''}{src_tag}")
        lines.append("")
    return "\n".join(lines)


def _nb_scope_label(cats, period):
    """키워드 없을 때 소스+기간 기반 라벨."""
    names = "·".join(_CAT_LABEL.get(c, (c,))[0] for c in (cats or [])) or "전체"
    pl = {"today": "오늘", "d3": "최근3일", "d7": "최근7일"}.get(period, "")
    return (names + (" " + pl if pl else "")).strip()


def _build_notebook_bundle(q, cats=None, period="all", limit=200, split=False, include_urls=True):
    """필터 적용 수집 → dict(label, atoms_n, md_files[(title,text)], yt_urls, web_urls).
    키워드 매칭이 그 소스+기간 범위 전체 대비 너무 빈약하면 소스+기간 전체를 담는
    '정리 모드'로 폴백."""
    conn = _ins_conn()
    if conn is None:
        return None
    try:
        rows, toks, label = _nb_fetch_rows(conn, q, cats, period, limit)
        full_rows, _, _ = _nb_fetch_rows(conn, "", cats, period, limit)
        if len(rows) < min(15, max(1, len(full_rows) * 0.3)):
            rows = full_rows
            label = _nb_scope_label(cats, period)
    finally:
        conn.close()
    if not (label or "").strip():
        label = _nb_scope_label(cats, period)

    yt_urls, web_urls = [], []
    if include_urls:
        for r in rows:
            dl = (r["deeplink"] or "").strip()
            if not dl.startswith("http"):
                continue
            if _nb_cat_of(r["source_type"]) == "youtube" or "youtu" in dl:
                if dl not in yt_urls:
                    yt_urls.append(dl)
            elif dl not in web_urls:
                web_urls.append(dl)

    today = datetime.now().strftime("%Y-%m-%d")
    md_files = []
    if split:
        bycat = {}
        for r in rows:
            bycat.setdefault(_nb_cat_of(r["source_type"]), []).append(r)
        order = ["youtube", "telegram", "report", "blog", "news"]
        for cat in sorted(bycat.keys(), key=lambda c: order.index(c) if c in order else 99):
            clabel = _CAT_LABEL.get(cat, (cat, ""))[0]
            md_files.append((f"[허브:{clabel}] {label} {len(bycat[cat])}건",
                             _nb_md_for_rows(f"{label} · {clabel}", bycat[cat], today)))
    else:
        md_files.append((f"[허브추출] {label} 발언 {len(rows)}건",
                         _nb_md_for_rows(label, rows, today)))

    return {
        "label": label, "atoms_n": len(rows), "md_files": md_files,
        "yt_urls": yt_urls[:20], "web_urls": web_urls[:20],
    }
```

- [ ] **Step 3: `scripts/nlm_bridge.py`에 고수준 래퍼 함수 이어서 작성**

파일 끝에 이어 붙인다:

```python
# ── 고수준 함수 (노트북 생성/소스추가/질의/리포트) ─────────────
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def create_notebook(title: str) -> dict:
    """새 NotebookLM 노트북 생성. {"ok","notebook_id","error"}."""
    import json as _json
    ok, out, err = _run_nlm(["notebook", "create", title, "--json"])
    if not ok:
        return {"ok": False, "notebook_id": None, "error": _friendly_nlm_err(err)}
    nb_id = None
    try:
        nb_id = _json.loads(out.strip().splitlines()[-1]).get("id")
    except Exception:
        pass
    if not nb_id:
        m = _UUID_RE.search(out)
        nb_id = m.group(0) if m else None
    if not nb_id:
        return {"ok": False, "notebook_id": None, "error": f"노트북 ID 파싱 실패: {out[:200]}"}
    return {"ok": True, "notebook_id": nb_id, "error": ""}


def add_source_file(nb_id: str, file_path: str, title: str) -> dict:
    """노트북에 파일 소스 추가. {"ok","error"}."""
    ok, _out, err = _run_nlm(["source", "add", nb_id, "--file", file_path, "--title", title])
    return {"ok": ok, "error": "" if ok else _friendly_nlm_err(err)}


def add_source_urls(nb_id: str, yt_urls: list, web_urls: list) -> dict:
    """노트북에 유튜브/웹 URL 소스 추가(있는 것만). {"ok","error"}."""
    url_args = []
    for u in (yt_urls or []):
        url_args += ["--youtube", u]
    for u in (web_urls or []):
        url_args += ["--url", u]
    if not url_args:
        return {"ok": True, "error": ""}
    ok, _out, err = _run_nlm(["source", "add", nb_id] + url_args, timeout=150)
    return {"ok": ok, "error": "" if ok else _friendly_nlm_err(err)}


def notebook_query(nb_id: str, question: str, conv: str = "", timeout: int = 180) -> dict:
    """노트북에 질문 → 인용 강제 답변. {"ok","answer","conversation_id","error"}.
    질문이 특정 구조를 지정하면 그 구조를 따르고, 아니면 기본 브리핑 구조로 답한다."""
    import json as _json
    guarded = (
        f"{question}\n\n"
        "[답변 규칙 — 반드시 지켜라]\n"
        "1. 모든 주장·수치·목표가·투자의견에는 반드시 (출처명, 날짜)를 괄호로 붙여라. "
        "출처·날짜를 못 붙이는 문장은 쓰지 마라.\n"
        "2. 소스가 실제로 한 말만 직접 인용·요약하라. 네 추측·일반지식·시황 창작은 금지. "
        "소스에 없는 내용은 '자료 없음'이라고 명시하라.\n"
        "3. 같은 방향 소스가 여럿이면 '합의(N건)', 엇갈리면 '⚠️충돌'로 표시하고 양쪽을 다 보여줘라.\n"
        "4. '지켜봐야 한다'식 양면론·관망으로 끝내지 마라. 수치 근거로 방향을 분명히 하되, "
        "'A면 B' 식 조건부로 써라.\n\n"
        "[구조] 질문이 특정 구조·항목을 지정했으면 그 구조를 그대로 따르라. "
        "지정이 없으면 이 기본 브리핑 구조로: ①한 줄 결론 ②핵심 팩트(종목/이슈별 소제목+직접인용+출처·날짜) "
        "③수급·모멘텀(목표가·투자의견 변화, 합의 vs 충돌) ④최근 리포트(증권사별로 실제 언급된 종목마다 "
        "목표가·투자의견·핵심 근거를 ③과 동일한 수준으로 각각 직접인용하라 — 이미 ③에서 다룬 종목이라도 "
        "생략하지 말고 반복 기재. 종목명만 나열하거나 '자료 없음'이라고 뭉뚱그리지 마라 — "
        "소스에 있는 내용을 안 찾은 것과 진짜 없는 것을 구분해서, 안 찾았으면 다시 찾아라) "
        "⑤관전 포인트(조건부 전략).\n\n"
        "[형식] 한국어. 이 노트북에 연결된 모든 소스를 교차 활용. "
        "새 리포트·문서·노트 같은 아티팩트는 만들지 말고 채팅 답변으로만, "
        "영어 사고과정 설명 없이 결과만 써라."
    )
    args = ["notebook", "query", nb_id, guarded, "--json"]
    if conv:
        args += ["-c", conv]
    ok, out, errm = _run_nlm(args, timeout=timeout)
    if not ok:
        return {"ok": False, "answer": "", "conversation_id": "", "error": _friendly_nlm_err(errm)}
    answer, conv_id = out.strip(), ""
    try:
        d = _json.loads(out)
        answer = d.get("answer") or answer
        conv_id = d.get("conversation_id") or ""
    except Exception:
        pass
    return {"ok": True, "answer": answer, "conversation_id": conv_id, "error": ""}


def create_report(nb_id: str, fmt: str = "Briefing Doc", language: str = "ko", out_dir: str = None) -> dict:
    """노트북 소스로 NotebookLM Studio 리포트 생성(비동기 폴링, 최대 ~150초).
    {"ok","markdown","ready","url","error"}. 저장 위치: out_dir/report_{nb_id}.md."""
    import json as _json
    if fmt not in ("Briefing Doc", "Study Guide", "Blog Post"):
        fmt = "Briefing Doc"
    ok, out, errm = _run_nlm(
        ["report", "create", nb_id, "--format", fmt, "--language", language, "--confirm"],
        timeout=180)
    if not ok:
        return {"ok": False, "markdown": "", "ready": False, "url": "", "error": _friendly_nlm_err(errm)}

    art_id = None
    for _ in range(30):
        ok_s, out_s, _ = _run_nlm(["studio", "status", nb_id])
        try:
            reps = [a for a in _json.loads(out_s) if a.get("type") == "report"]
            if reps and reps[-1].get("status") not in ("in_progress", "pending", None):
                art_id = reps[-1].get("id")
                break
        except Exception:
            pass
        time.sleep(5)

    base_dir = Path(out_dir) if out_dir else (ROOT / "out" / "insights_notebook")
    base_dir.mkdir(parents=True, exist_ok=True)
    rp = base_dir / f"report_{re.sub(r'[^0-9a-fA-F-]', '', nb_id)}.md"
    dargs = ["download", "report", nb_id, "-o", str(rp)]
    if art_id:
        dargs += ["--id", art_id]
    ok_d, _od, _ed = _run_nlm(dargs, timeout=60)
    md = ""
    if ok_d and rp.exists():
        try:
            md = rp.read_text(encoding="utf-8")
        except Exception:
            md = ""
    return {"ok": True, "markdown": md, "ready": bool(md),
            "url": f"https://notebooklm.google.com/notebook/{nb_id}", "error": ""}
```

- [ ] **Step 4: 순수 헬퍼 단위테스트 작성**

```python
# tests/nlm_bridge/test_pure_helpers.py
from scripts import nlm_bridge as nb


def test_valid_period():
    assert nb._valid_period("today") == "today"
    assert nb._valid_period("d3") == "d3"
    assert nb._valid_period("garbage") == "all"
    assert nb._valid_period(None) == "all"


def test_tokenize_query_empty_returns_wildcard_token():
    assert nb._tokenize_query("") == [""]


def test_tokenize_query_strips_particles_and_stopwords():
    toks = nb._tokenize_query("삼성전자 관련 이슈 정리해줘")
    assert "삼성전자" in toks
    assert "이슈" not in toks
    assert "정리해줘" not in toks


def test_nb_cat_of():
    assert nb._nb_cat_of("yt") == "youtube"
    assert nb._nb_cat_of("youtube") == "youtube"
    assert nb._nb_cat_of("telegram") == "telegram"
    assert nb._nb_cat_of("report") == "report"


def test_nb_scope_label_today():
    assert nb._nb_scope_label(["telegram", "report"], "today") == "텔레그램·리포트 오늘"


def test_nlm_exe_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(nb.shutil, "which", lambda name: None)
    assert nb._nlm_exe() is None
```

- [ ] **Step 5: 실패 확인 → 구현 → 통과 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/nlm_bridge/test_pure_helpers.py -v`
Expected(구현 전): FAIL(ModuleNotFoundError: nlm_bridge)
Step 2·3 구현 후 재실행 → 6 passed.

- [ ] **Step 6: 고수준 함수 단위테스트(실제 nlm 미호출, `_run_nlm` monkeypatch)**

```python
# tests/nlm_bridge/test_notebook_calls.py
import json
from scripts import nlm_bridge as nb


def test_create_notebook_parses_json_id(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=90, _auth_retry=True:
                        (True, json.dumps({"id": "abc-123"}), ""))
    r = nb.create_notebook("[골루프] 아침브리핑 2026-07-03")
    assert r["ok"] is True and r["notebook_id"] == "abc-123"


def test_create_notebook_fails_returns_error(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=90, _auth_retry=True:
                        (False, "", "Authentication expired"))
    r = nb.create_notebook("x")
    assert r["ok"] is False and "로그인" in r["error"]


def test_add_source_file(monkeypatch):
    calls = {}
    def fake(args, timeout=90, _auth_retry=True):
        calls["args"] = args
        return True, "", ""
    monkeypatch.setattr(nb, "_run_nlm", fake)
    r = nb.add_source_file("nb1", "/tmp/x.md", "제목")
    assert r["ok"] is True
    assert calls["args"] == ["source", "add", "nb1", "--file", "/tmp/x.md", "--title", "제목"]


def test_notebook_query_parses_answer(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=180, _auth_retry=True:
                        (True, json.dumps({"answer": "본문", "conversation_id": "c1"}), ""))
    r = nb.notebook_query("nb1", "질문")
    assert r["ok"] is True and r["answer"] == "본문" and r["conversation_id"] == "c1"


def test_notebook_query_fails(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=180, _auth_retry=True:
                        (False, "", "timeout"))
    r = nb.notebook_query("nb1", "질문")
    assert r["ok"] is False and r["answer"] == ""


def test_create_report_no_artifact_returns_ready_false(monkeypatch, tmp_path):
    def fake(args, timeout=90, _auth_retry=True):
        if args[0] == "report":
            return True, "", ""
        if args[0] == "studio":
            return True, json.dumps([]), ""
        if args[0] == "download":
            return False, "", "no artifact"
        return True, "", ""
    monkeypatch.setattr(nb, "_run_nlm", fake)
    monkeypatch.setattr(nb.time, "sleep", lambda s: None)   # 폴링 대기 skip
    r = nb.create_report("nb1", out_dir=str(tmp_path))
    assert r["ok"] is True and r["ready"] is False and r["markdown"] == ""
```

- [ ] **Step 7: 실행 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/nlm_bridge/ -v`
Expected: 11 passed (5 pure helper + 6 notebook calls, Step4의 6개 포함).
(주의: `test_create_report_no_artifact_returns_ready_false`의 30회 폴링 루프가 `nb.time.sleep`을 monkeypatch로 무력화했는지 확인 — 안 하면 테스트가 150초 걸림.)

- [ ] **Step 8: 커밋**

```bash
mkdir -p tests/nlm_bridge
git add scripts/nlm_bridge.py tests/nlm_bridge/
git commit -m "feat(nlm-bridge): NLM CLI 순수함수 추출 + 고수준 래퍼(create_notebook/add_source/query/report)"
```

---

### Task 2: `dashboard/server.py` 재배선 — nlm_bridge 사용, 로컬 정의 제거

**Files:**
- Modify: `dashboard/server.py`

**Interfaces:**
- Consumes: Task 1의 `scripts/nlm_bridge.py` 전체 함수
- Produces: 기존 3개 엔드포인트(`/api/insights/to_notebook`, `/api/insights/notebook_query`, `/api/insights/notebook_card`)의 **응답 스키마 무변경**

- [ ] **Step 1: 현재 위치 재확인(동시편집 대비)**

Run: `grep -n "^_SEARCH_STOP\|^def _tokenize_query\|^def _nlm_exe\|^_NLM_AUTH_SIGNS\|^_NLM_LOGIN_LOCK\|^def _nlm_relogin_locked\|^def _run_nlm\|^def _friendly_nlm_err\|^_CAT_LABEL\|^def _ins_conn\|^def _nb_cat_of\|^def _nb_period_min\|^def _valid_period\|^def _nb_cats_types\|^def _nb_fetch_rows\|^def _nb_md_for_rows\|^def _nb_scope_label\|^def _build_notebook_bundle\|^async def api_insights_to_notebook\|^async def api_insights_notebook_query\|^async def api_insights_notebook_card" dashboard/server.py`

- [ ] **Step 2: import 추가**

`dashboard/server.py` 상단(`sys.path.insert(0, os.path.join(ROOT, "scripts"))` 직후, 기존 다른 `from X import Y` 임포트들 근처)에 추가:

```python
from nlm_bridge import (
    _nlm_exe, _run_nlm, _friendly_nlm_err, _build_notebook_bundle,
    _valid_period, _tokenize_query, _nb_cat_of, _CAT_LABEL,
    create_notebook, add_source_file, add_source_urls, notebook_query as nlm_notebook_query,
    create_report as nlm_create_report,
)
```

- [ ] **Step 3: 로컬 정의 제거**

Step 1에서 확인한 다음 로컬 정의들을 `dashboard/server.py`에서 **삭제**(Task 1에서 이미 nlm_bridge.py로 옮겨졌으므로):
`_SEARCH_STOP`, `_tokenize_query`, `_nlm_exe`, `_NLM_AUTH_SIGNS`, `_NLM_LOGIN_LOCK`, `_nlm_relogin_locked`,
`_run_nlm`, `_friendly_nlm_err`, `_CAT_LABEL`, `_nb_cat_of`, `_nb_period_min`, `_valid_period`,
`_nb_cats_types`, `_nb_fetch_rows`, `_nb_md_for_rows`, `_nb_scope_label`, `_build_notebook_bundle`.

⚠️ `_ins_conn`은 **삭제하지 말 것** — `/api/insights/*` 다른 엔드포인트(NLM과 무관한 `_has_summary` 등)가 계속 사용 중.
⚠️ `_CAT_TYPE_MAP`은 nlm_bridge로 옮기지 않았으므로(사용처 없음 확인됨, Task1 조사 결과) 그대로 둘 것.

- [ ] **Step 4: `api_insights_notebook_query` 엔드포인트 내부를 nlm_bridge 호출로 교체**

기존 `_do()` 클로저 전체(guarded 프롬프트 조립 + `_run_nlm(["notebook","query",...])` + JSON 파싱)를 다음으로 교체:

```python
    def _do():
        r = nlm_notebook_query(nb_id, question, conv=conv, timeout=180)
        if not r["ok"]:
            return {"error": f"질문 실패: {r['error']}"}
        return {"ok": True, "answer": r["answer"], "conversation_id": r["conversation_id"]}
```

(함수 시그니처·앞부분 파라미터 파싱(`nb_id`, `question`, `conv` 추출, 400 검증)은 그대로 유지, `_do()` 본문만 교체.)

- [ ] **Step 5: `api_insights_notebook_card` 엔드포인트 내부를 nlm_bridge 호출로 교체**

기존 `_do()`(report create + 폴링 + 다운로드) 전체를 다음으로 교체:

```python
    def _do():
        r = nlm_create_report(nb_id, fmt=fmt, language="ko")
        if not r["ok"]:
            return {"error": f"카드 생성 실패: {r['error']}"}
        return {"ok": True, "format": fmt, "markdown": r["markdown"],
                "ready": r["ready"], "url": r["url"]}
```

- [ ] **Step 6: `api_insights_to_notebook`의 노트북 생성/소스추가 부분을 nlm_bridge 호출로 교체**

기존 `_do()` 안의 다음 블록:
```python
        ok, out, err = _run_nlm(["notebook", "create", title, "--json"])
        if not ok:
            return {"error": f"노트북 생성 실패: {_friendly_nlm_err(err)}"}
        nb_id = None
        try:
            nb_id = json.loads(out.strip().splitlines()[-1]).get("id")
        except Exception:
            pass
        if not nb_id:
            m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out)
            nb_id = m.group(0) if m else None
        if not nb_id:
            return {"error": f"노트북 ID 파싱 실패: {out[:200]}"}

        added, last_err = 0, ""
        for src_title, mp in file_specs:
            ok2, _o2, err2 = _run_nlm(["source", "add", nb_id, "--file", mp,
                                       "--title", src_title])
            if ok2:
                added += 1
            else:
                last_err = err2
        url_args = []
        for u in yt_urls:
            url_args += ["--youtube", u]
        for u in web_urls:
            url_args += ["--url", u]
        if url_args:
            ok3, _o3, _e3 = _run_nlm(["source", "add", nb_id] + url_args, timeout=150)
            if ok3:
                added += 1
```

를 다음으로 교체(뒤이어 나오는 `research` 블록과 `return {...}`는 **그대로 유지**):

```python
        cr = create_notebook(title)
        if not cr["ok"]:
            return {"error": f"노트북 생성 실패: {cr['error']}"}
        nb_id = cr["notebook_id"]

        added, last_err = 0, ""
        for src_title, mp in file_specs:
            r2 = add_source_file(nb_id, mp, src_title)
            if r2["ok"]:
                added += 1
            else:
                last_err = r2["error"]
        if yt_urls or web_urls:
            r3 = add_source_urls(nb_id, yt_urls, web_urls)
            if r3["ok"]:
                added += 1
```

- [ ] **Step 7: import/구문 검증**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -c "import ast; ast.parse(open('dashboard/server.py', encoding='utf-8').read()); print('syntax OK')"`
Expected: `syntax OK`

Run: `cd dashboard && "C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -c "import sys; sys.path.insert(0,'..'); sys.path.insert(0,'../scripts'); import server; print('import OK')"`
Expected: `import OK` (서버 모듈이 import 시점에 에러 없이 로드됨 — 단, 이 모듈은 import시 daemon 스레드가 실제로 시작되므로 **명령 실행 후 바로 Ctrl+C 또는 프로세스 종료**할 것. 목적은 SyntaxError/ImportError/NameError 여부 확인.)

- [ ] **Step 8: 커밋**

```bash
git add dashboard/server.py
git commit -m "refactor(server): NLM 엔드포인트를 nlm_bridge 호출로 재배선(응답 스키마 무변경)"
```

---

### Task 3: `scripts/goal_loop/notebook_stage0.py` 생성

**Files:**
- Create: `scripts/goal_loop/notebook_stage0.py`
- Test: `tests/goal_loop/test_notebook_stage0.py`

**Interfaces:**
- Consumes: `nlm_bridge._build_notebook_bundle`, `nlm_bridge.create_notebook`, `nlm_bridge.add_source_file`, `nlm_bridge.notebook_query`, `nlm_bridge.create_report` (Task 1)
- Produces:
  - `build_notebook(date: str) -> dict` — `{"notebook_id": str|None, "atoms_n": int, "url": str|None}`
  - `query_card_content(notebook_id: str, date: str) -> str` — daily_scenario 포맷과 동일한 텍스트, 실패 시 `""`
  - `generate_deep_report(notebook_id: str, date: str) -> str|None` — 저장된 리포트 마크다운 경로 또는 None(비차단)

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/goal_loop/test_notebook_stage0.py
from scripts.goal_loop import notebook_stage0 as ns


def test_build_notebook_no_atoms_returns_zero(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "_build_notebook_bundle",
                        lambda **kw: {"label": "x", "atoms_n": 0, "md_files": [], "yt_urls": [], "web_urls": []})
    r = ns.build_notebook("2026-07-03")
    assert r["atoms_n"] == 0 and r["notebook_id"] is None


def test_build_notebook_success(monkeypatch, tmp_path):
    monkeypatch.setattr(ns.nlm_bridge, "_build_notebook_bundle",
                        lambda **kw: {"label": "오늘", "atoms_n": 12,
                                      "md_files": [("[허브추출] 오늘 발언 12건", "본문내용")],
                                      "yt_urls": [], "web_urls": []})
    monkeypatch.setattr(ns, "OUT_DIR", tmp_path)
    monkeypatch.setattr(ns.nlm_bridge, "create_notebook",
                        lambda title: {"ok": True, "notebook_id": "nb-1", "error": ""})
    created = {}
    monkeypatch.setattr(ns.nlm_bridge, "add_source_file",
                        lambda nb_id, fp, title: created.setdefault("called", (nb_id, fp, title)) or {"ok": True, "error": ""})
    r = ns.build_notebook("2026-07-03")
    assert r["notebook_id"] == "nb-1" and r["atoms_n"] == 12
    assert r["url"] == "https://notebooklm.google.com/notebook/nb-1"
    assert created["called"][0] == "nb-1"


def test_build_notebook_create_fails_returns_none_id(monkeypatch, tmp_path):
    monkeypatch.setattr(ns.nlm_bridge, "_build_notebook_bundle",
                        lambda **kw: {"label": "오늘", "atoms_n": 5,
                                      "md_files": [("t", "본문")], "yt_urls": [], "web_urls": []})
    monkeypatch.setattr(ns, "OUT_DIR", tmp_path)
    monkeypatch.setattr(ns.nlm_bridge, "create_notebook",
                        lambda title: {"ok": False, "notebook_id": None, "error": "실패"})
    r = ns.build_notebook("2026-07-03")
    assert r["notebook_id"] is None


def test_query_card_content_returns_answer(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "notebook_query",
                        lambda nb_id, q, timeout=180: {"ok": True, "answer": "📌 오늘 핵심\n• 테스트", "error": ""})
    text = ns.query_card_content("nb-1", "2026-07-03")
    assert "📌" in text


def test_query_card_content_fails_returns_empty(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "notebook_query",
                        lambda nb_id, q, timeout=180: {"ok": False, "answer": "", "error": "x"})
    assert ns.query_card_content("nb-1", "2026-07-03") == ""


def test_generate_deep_report_success(monkeypatch, tmp_path):
    monkeypatch.setattr(ns.nlm_bridge, "create_report",
                        lambda nb_id, fmt="Briefing Doc", language="ko", out_dir=None:
                        {"ok": True, "markdown": "본문", "ready": True, "url": "https://x", "error": ""})
    p = ns.generate_deep_report("nb-1", "2026-07-03")
    assert p is not None


def test_generate_deep_report_failure_returns_none(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_report",
                        lambda nb_id, fmt="Briefing Doc", language="ko", out_dir=None:
                        (_ for _ in ()).throw(RuntimeError("nlm down")))
    assert ns.generate_deep_report("nb-1", "2026-07-03") is None
```

- [ ] **Step 2: 실패 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_notebook_stage0.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 구현**

```python
# scripts/goal_loop/notebook_stage0.py
"""골루프 Stage0 — NotebookLM 기반 아침 브리핑 콘텐츠 생성.
A(구조화 카드용 텍스트)와 B(심층 리포트)를 각각 만든다. B는 비차단(실패해도 A 발행에 영향 없음)."""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT_DIR = ROOT / "out"

import nlm_bridge  # noqa: E402

_CARD_FORMAT_INSTRUCTIONS = """\
아래 형식을 그대로 써라. 형식 밖으로 나오지 마라.

규칙:
- 한 줄 = 한 문장. 절대 길게 쓰지 마라.
- 숫자 없으면 쓰지 마라. 막연한 표현 금지.
- 종목 표는 칸 맞춰서.
- 주식 1년차도 바로 이해하는 쉬운 말로 써라.
- 전문용어 변환 규칙 (반드시 지켜라):
  ETF → 펀드 / TP → 목표주가 / 리밸런싱 → 비중 조정
  Capex → 설비 투자 / 지정학 → 전쟁·분쟁 / 역성장 → 판매 감소
  수급 → 돈 흐름 / 자금 쏠림 → 돈이 몰리는 중
- 말투: "~야", "~있어", "~중", "~예정" 처럼 자연스럽게. 딱딱한 명사형 금지.
- 핵심 이유는 "왜 중요한지" 한 줄로. "~해서 주가 오를 수 있어" 처럼.

━━━ {date} 시장 브리핑 ━━━

📌 오늘 핵심
• (자금 흐름 한 줄 — 어디서 빠져서 어디로)
• (오늘 가장 중요한 이슈 한 줄)
• (시장 분위기 한 줄)

🔴 강세 종목
종목명        TP·수치          핵심 이유
(종목1)       TP XXX만 (+XX%) 이유 10자
(종목2)       TP XXX만 (+XX%) 이유 10자
(종목3)       수치             이유 10자

🔵 리스크 종목 (있으면)
종목명        수치             이유 10자

⚠️ 리스크
• (리스크1 — 수치 포함)
• (리스크2 — 수치 포함)
• (리스크3 — 수치 포함)

📅 챙길 일정
• (날짜/시점 + 이벤트)
• (날짜/시점 + 이벤트)

💡 시나리오
강세: (조건) → (흐름)
약세: (조건) → (흐름)

🎯 오늘 한 줄
(행동 지침 포함, 20자 이내)
"""


def build_notebook(date: str) -> dict:
    """오늘 텔레·리포트·블로그 원자 → 새 노트북 생성+소스추가.
    원자 0건이거나 생성 실패 시 notebook_id=None (호출측이 C1 가드로 처리)."""
    bundle = nlm_bridge._build_notebook_bundle(
        q="", cats=["telegram", "report", "blog"], period="today", limit=200)
    if not bundle or bundle.get("atoms_n", 0) == 0:
        return {"notebook_id": None, "atoms_n": 0, "url": None}

    cr = nlm_bridge.create_notebook(f"[골루프] 아침브리핑 {date}")
    if not cr["ok"]:
        return {"notebook_id": None, "atoms_n": bundle["atoms_n"], "url": None}
    nb_id = cr["notebook_id"]

    out_dir = OUT_DIR / "goal_loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, (src_title, md_text) in enumerate(bundle["md_files"]):
        mp = out_dir / f"stage0_{date}_{i}.md"
        mp.write_text(md_text, encoding="utf-8")
        nlm_bridge.add_source_file(nb_id, str(mp), src_title)

    return {"notebook_id": nb_id, "atoms_n": bundle["atoms_n"],
            "url": f"https://notebooklm.google.com/notebook/{nb_id}"}


def query_card_content(notebook_id: str, date: str) -> str:
    """A: 카드용 구조화 텍스트(daily_scenario 포맷). 실패 시 빈 문자열(C1 가드로 처리)."""
    question = _CARD_FORMAT_INSTRUCTIONS.replace("{date}", date)
    r = nlm_bridge.notebook_query(notebook_id, question, timeout=180)
    if not r["ok"]:
        return ""
    return r["answer"]


def generate_deep_report(notebook_id: str, date: str) -> str:
    """B: 심층 리포트(NotebookLM Briefing Doc). 비차단 — 실패하면 None만 반환, 예외 전파 안 함."""
    try:
        r = nlm_bridge.create_report(notebook_id, fmt="Briefing Doc", language="ko",
                                     out_dir=str(OUT_DIR / "insights_notebook"))
        if r.get("ok") and r.get("ready"):
            return r.get("url") or None
        return None
    except Exception:
        return None
```

- [ ] **Step 4: 통과 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_notebook_stage0.py -v`
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/goal_loop/notebook_stage0.py tests/goal_loop/test_notebook_stage0.py
git commit -m "feat(goal-loop): NotebookLM 기반 Stage0(build_notebook/query_card_content/generate_deep_report)"
```

---

### Task 4: `morning_brief.py` 통합 — `_ensure_scenario` 교체 + 링크 전파

**Files:**
- Modify: `scripts/goal_loop/morning_brief.py`
- Modify: `tests/goal_loop/test_orchestrator.py`

**Interfaces:**
- Consumes: `notebook_stage0.build_notebook`, `notebook_stage0.query_card_content`, `notebook_stage0.generate_deep_report` (Task 3)
- Produces: `_ensure_scenario(date) -> dict`(`{"notebook_url": str|None, "report_url": str|None}`, 하위호환: 기존 테스트가 `lambda date: None`으로 monkeypatch해도 `run_morning_brief`는 안 죽음)
  `_escalate(png, reasons, date, links=None)`, `run_morning_brief(date, gemini_fn=None, max_iter=3)`(반환 스키마 동일)

- [ ] **Step 1: 실패 테스트 작성(신규 링크 전파 동작)**

`tests/goal_loop/test_orchestrator.py`의 `_patch()` 헬퍼가 `_ensure_scenario`를 `lambda date: None`으로 고정하고 있어, 신규 동작(링크 전파)을 검증하려면 그 monkeypatch를 오버라이드하는 테스트를 추가한다. 파일 맨 아래에 추가:

```python
def test_stage0_links_appended_to_caption_on_send(monkeypatch, tmp_path):
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setattr(mb, "_ensure_scenario",
                        lambda date: {"notebook_url": "https://notebooklm.google.com/notebook/nb1",
                                      "report_url": "https://notebooklm.google.com/notebook/nb1"})
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
    assert "captions" in sent and "notebooklm.google.com/notebook/nb1" in sent["captions"][0]


def test_stage0_returns_none_no_crash(monkeypatch, tmp_path):
    """하위호환: _ensure_scenario가 None을 리턴해도(기존 테스트 monkeypatch 방식) 죽지 않음."""
    monkeypatch.setattr(mb.pending, "PENDING_PATH", tmp_path / "p.json")
    sent = _patch(monkeypatch, {"kospi": -0.5, "kosdaq": 0.3})   # _patch가 _ensure_scenario→None으로 설정
    r = mb.run_morning_brief("2026-07-02", gemini_fn=lambda p: "{}")
    assert r["status"] == "sent"
```

`_patch()` 헬퍼도 캡션을 기록하도록 아래처럼 갱신한다(기존 `sent = {"photo": [], "msg": []}` 라인과 `send_telegram_photo`/`send_telegram_message` monkeypatch 두 줄을 교체):

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

- [ ] **Step 2: 실패 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_orchestrator.py -v`
Expected: `test_stage0_links_appended_to_caption_on_send` FAIL (`sent`에 `"captions"` 키 자체는 있으나 `_ensure_scenario`의 반환값이 아직 무시됨 → 캡션에 링크 없음, assert 실패)

- [ ] **Step 3: `_ensure_scenario` 교체**

`scripts/goal_loop/morning_brief.py`의 다음 블록:
```python
def _ensure_scenario(date: str) -> None:
    """Stage 0: daily_scenario로 out/scenario_{date}.md 생성(없을 때만). best-effort."""
    scen = ROOT / "out" / f"scenario_{date}.md"
    if scen.exists():
        return
    try:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "daily_scenario.py"), "--date", date],
                       cwd=str(ROOT), capture_output=True, timeout=300)
    except Exception:
        pass
```

를 다음으로 교체:

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

- [ ] **Step 4: `_escalate`와 `run_morning_brief`에 링크 전파 추가**

`_escalate` 함수를 다음으로 교체:

```python
def _escalate(png, reasons: list, date: str, links: dict = None) -> dict:
    """이상/실패 시: 대기 저장 + (OWNER_CHAT_ID 있을 때만) 사장님 개인 텔레 알림. 채널로는 절대 안 보냄(fail-closed)."""
    pending.write({"date": date, "png": png or "", "reasons": reasons,
                   "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
    owner = (os.environ.get("OWNER_CHAT_ID") or "").strip()
    if owner:
        text = "⚠️ 확인 필요: " + " / ".join(reasons)
        if links and links.get("notebook_url"):
            text += f"\n🔗 {links['notebook_url']}"
        try:
            if png:
                viz_card.send_telegram_photo(png, text, chat_id=owner)
            else:
                viz_card.send_telegram_message(text, chat_id=owner)
        except Exception:
            pass
    return {"status": "escalated", "reasons": reasons, "png": png or ""}
```

`run_morning_brief`를 다음으로 교체:

```python
def run_morning_brief(date: str, gemini_fn=None, max_iter: int = 3) -> dict:
    try:
        gfn = gemini_fn or _default_gemini()

        links = _ensure_scenario(date) or {}          # Stage 0: 데이터·1차 드래프트 생성
        data = studio_data.get_briefing_data(date)
        data.setdefault("date", date)

        # ── 빈 데이터 가드: 헛소리 생성·발행 원천 차단 ──
        if not (str(data.get("headline") or "").strip() or data.get("lines")):
            return _escalate(None, ["브리핑 데이터 없음(Stage0 실패) — 발행 중단, 수동 확인 필요"], date, links)

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

        if flags:
            return _escalate(png, flags, date, links)

        caption = f"📊 {date} 아침 브리핑\n{data.get('headline', '')}"
        if links.get("notebook_url"):
            caption += f"\n🔗 더 깊게 보기: {links['notebook_url']}"
        viz_card.send_telegram_photo(png, caption)
        return {"status": "sent", "reasons": [], "png": png}
    except Exception as e:
        return _escalate(None, [f"브리핑 실패: {str(e)[:200]}"], date)
```

- [ ] **Step 5: 통과 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/test_orchestrator.py -v`
Expected: 7 passed (기존 5개 전부 재통과 + 신규 2개: `test_stage0_links_appended_to_caption_on_send`, `test_stage0_returns_none_no_crash`)

- [ ] **Step 6: 전체 goal_loop + nlm_bridge 스위트 회귀 확인**

Run: `"C:/Users/TheRose/AppData/Local/Python/bin/python.exe" -m pytest tests/goal_loop/ tests/nlm_bridge/ -v`
Expected: 전부 PASS, 실패 0.

- [ ] **Step 7: 커밋**

```bash
git add scripts/goal_loop/morning_brief.py tests/goal_loop/test_orchestrator.py
git commit -m "feat(goal-loop): Stage0을 NotebookLM 기반으로 교체, 캡션에 노트북/리포트 링크 전파

daily_scenario.py 서브프로세스 대신 notebook_stage0(build_notebook+query_card_content+
generate_deep_report) 사용. _ensure_scenario가 링크 dict 반환, _escalate/run_morning_brief가
정상발행·에스컬레이션 캡션에 노트북 링크 첨부. 기존 품질루프·게이트·데몬 무수정."
```

---

## Self-Review

- **스펙 커버리지**: §3 아키텍처(Stage0/nlm_bridge/notebook_stage0/morning_brief 4블록) → Task1~4 각각 매핑됨. §4 프롬프트 설계 → Task3 Step3 `_CARD_FORMAT_INSTRUCTIONS`(daily_scenario PROMPT 100% 동일 문구). §5 에러처리표 → C1가드 재사용(신규코드 불필요, Task4에서 `if not nb.get("notebook_id"): return`류로 자연히 만족), B 비차단(Task3 `generate_deep_report`의 try/except). §6 범위 → nlm_bridge 추출+Stage0 교체만, 오케스트레이터 무수정(실제로 품질루프·게이트·데몬 코드 한 줄도 안 건드림, 확인됨).
- **플레이스홀더 스캔**: 없음 — 전 스텝 실제 코드·명령·기대결과 포함.
- **타입 일관성**: `nlm_bridge.create_notebook/add_source_file/notebook_query/create_report`(Task1) ↔ `notebook_stage0.py`(Task3) 호출부 일치. `notebook_stage0.build_notebook/query_card_content/generate_deep_report`(Task3) ↔ `morning_brief._ensure_scenario`(Task4) 호출부 일치. `_escalate(png,reasons,date,links=None)` ↔ 3곳 호출부(빈데이터가드·게이트·except) 전부 갱신 확인.
- **동시편집 리스크**: Task1·2 Step1에 `grep -n` 재확인 스텝 명시(다른 세션이 server.py를 계속 편집 중이므로 줄번호 대신 함수명 기준 위치 확인).

## 알려진 확인 항목(구현 중)
- `notebook_query`가 daily_scenario 포맷을 얼마나 안정적으로 지키는지는 실제 nlm 호출 전까지 미지수 — Task4 완료 후 서버에서 실전 스모크 테스트 필요(Task 5 범위 밖, 별도 배포 검증 단계).
- `_build_notebook_bundle(cats=["telegram","report","blog"])`의 source_type 문자열이 실제 atoms.db 값과 일치하는지 Task3 구현 직후 실제 DB로 1회 확인 권장.
