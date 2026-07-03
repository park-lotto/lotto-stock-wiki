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
    """nlm 재로그인 — 락으로 직렬화(동시 Chrome 프로필 충돌 방지). 이미 유효하면 스킵.
    `nlm login --check`는 실제 로그인 직후에도 만료라고 오탐하는 버그가 있어(2026-07-03 확인)
    실제 API 호출(notebook list)로 유효성을 판단한다."""
    with _NLM_LOGIN_LOCK:
        cok, _o, _ = _run_nlm(["notebook", "list", "--quiet"], timeout=40, _auth_retry=False)
        if cok:
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


# ── nlm 수동 로그인(VNC) — 자동 재로그인이 안 먹힐 때 사람이 직접 구글 로그인 ──
# 원격(Linux) 전용. Xvfb 가상 디스플레이 위에 Chrome을 띄우고 x11vnc+websockify로
# 브라우저 화면을 노출, nlm login --cdp-url로 그 Chrome의 로그인 상태를 그대로 채간다.
_LOGIN_DISPLAY = ":99"
_LOGIN_CDP_PORT = 9333
_LOGIN_VNC_PORT = 5901
_LOGIN_WS_PORT = 6081
_LOGIN_VNC_PASSWORD = "nlmlogin2026"
_LOGIN_PROFILE_DIR = "/tmp/nlm-login-chrome-profile"
_MANUAL_LOGIN_PROC = {"proc": None}


def _port_open(port, host="127.0.0.1"):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def _ensure_login_browser():
    """Xvfb+Chrome(CDP)+x11vnc+websockify가 안 떠있으면 띄운다. 이미 떠있으면 그대로 재사용."""
    import time as _time
    if not _port_open(_LOGIN_CDP_PORT):
        subprocess.Popen(
            ["Xvfb", _LOGIN_DISPLAY, "-screen", "0", "1280x800x24"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _time.sleep(2)
        env = dict(os.environ, DISPLAY=_LOGIN_DISPLAY)
        subprocess.Popen(
            ["google-chrome", f"--remote-debugging-port={_LOGIN_CDP_PORT}",
             "--no-first-run", "--no-default-browser-check",
             f"--user-data-dir={_LOGIN_PROFILE_DIR}", "https://accounts.google.com"],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _time.sleep(3)
    if not _port_open(_LOGIN_VNC_PORT):
        subprocess.Popen(
            ["x11vnc", "-display", _LOGIN_DISPLAY, "-forever", "-shared",
             "-rfbport", str(_LOGIN_VNC_PORT), "-passwd", _LOGIN_VNC_PASSWORD],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _time.sleep(1)
    if not _port_open(_LOGIN_WS_PORT):
        subprocess.Popen(
            ["websockify", "--web=/usr/share/novnc", f"127.0.0.1:{_LOGIN_WS_PORT}",
             f"127.0.0.1:{_LOGIN_VNC_PORT}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _time.sleep(1)


def start_manual_login():
    """수동 로그인 시작 — 브라우저 인프라 기동 + 백그라운드로 nlm login 실행(사람 대기).
    반환: 사용자가 열어야 할 노트북LM 로그인 화면 URL."""
    exe = _nlm_exe()
    if not exe:
        return {"error": "nlm CLI를 찾을 수 없음"}
    _ensure_login_browser()
    if _MANUAL_LOGIN_PROC["proc"] is None or _MANUAL_LOGIN_PROC["proc"].poll() is not None:
        _MANUAL_LOGIN_PROC["proc"] = subprocess.Popen(
            [exe, "login", "--provider", "openclaw",
             "--cdp-url", f"http://127.0.0.1:{_LOGIN_CDP_PORT}", "--force"],
            cwd=str(ROOT), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    return {
        "ok": True,
        "vnc_url": (f"/vnc-login/vnc.html?path=vnc-login/websockify"
                    f"&password={_LOGIN_VNC_PASSWORD}&autoconnect=true"),
    }


def manual_login_status():
    """수동 로그인 진행 상태 확인. proc가 없으면 아직 시작 안 함."""
    proc = _MANUAL_LOGIN_PROC["proc"]
    if proc is None:
        return {"state": "idle"}
    rc = proc.poll()
    if rc is None:
        return {"state": "waiting"}
    if rc == 0:
        return {"state": "done"}
    return {"state": "failed", "code": rc}


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


# 리모션(채널) 브랜드 디자인 지침 — 인포그래픽 등 시각 결과물에 적용(dashboard/server.py와 공유)
_BRAND_DESIGN = (
    "[디자인 지침] 순수 블랙(#000000) 배경에 라임그린(#AAFF00)을 메인 액센트로 핵심 수치·"
    "키워드·그래프 라인·테두리에 사용하고, 골드/앰버(#C8921A)는 고급 포인트로, 텍스트는 흰색. "
    "미니멀하면서 데이터가 빛나는 HUD/프리미엄 금융 대시보드 느낌. 큰 숫자와 핵심을 강하게 강조하고 "
    "정보 밀도 높게, 디테일하고 세련되게 구성."
)

# 대안 브랜드 스타일 실험용 — brand= 키를 주면 _BRAND_DESIGN(라임그린 HUD)을 완전히
# 대체한다(섞이지 않음). getdesign.md 등 실제 브랜드 CI/BI를 참고해 텍스트로 요약.
# 새 스타일 추가 시 여기 dict에 항목만 늘리면 됨(애플/구글 등 후속 실험 대비).
BRAND_STYLE_PRESETS = {
    "claude": (
        "[디자인 지침] Anthropic의 Claude AI 공식 브랜드 아이덴티티(CI/BI)를 그대로 참고해서 "
        "디자인해라 — 실제 Anthropic/Claude 공식 웹사이트·브랜드 자료에서 쓰는 것과 동일한 "
        "룩앤필로 재현해라. Claude 특유의 따뜻한 크림색(#faf9f5) 배경, 코랄/테라코타(#cc785c) "
        "포인트 컬러, 세리프 디스플레이 타이포그래피, 미니멀하고 에디토리얼한 레이아웃을 "
        "실제 Anthropic 브랜드처럼 정확하게 구현해라. 라임그린이나 네온 계열 색은 절대 쓰지 마라."
    ),
    "claude_terminal": (
        "[디자인 지침] 첨부된 소스 이미지(Claude Code CLI 터미널 시작화면)를 그대로 재현해라 — "
        "배경은 순수 블랙에 가까운 아주 어두운 차콜(#181715~#141413). 전체 카드/섹션을 브라우저나 "
        "터미널 창처럼 얇은 코랄색(#cc785c) 둥근 테두리로 감싸고, 왼쪽 위 모서리에 작은 원 점 3개를 "
        "찍어 macOS 창 컨트롤 버튼처럼 연출해라. 큰 제목/헤드라인은 굵은 픽셀·블록 스타일 아웃라인 "
        "폰트(레트로 8비트 게임 로고 느낌)로, 글자 속은 배경색으로 비우고 테두리만 코랄색으로 그려라 "
        "(속이 빈 아웃라인 글자). 본문·라벨 텍스트는 모노스페이스 폰트를 쓰고 연한 코랄/살몬 톤으로. "
        "절대 크림색이나 밝은 배경을 쓰지 마라 — 이건 다크 터미널 테마다. 라임그린도 금지."
    ),
}


def create_infographic(nb_id: str, out_dir: str = None, focus: str = "", brand: str = None) -> dict:
    """노트북 소스로 NotebookLM 인포그래픽(PNG) 생성(동기 폴링, 최대 ~150초).
    {"ok","path","error"}. 다운로드된 파일이 실제 존재해야 ok=True(카드 발행 필수조건이라 엄격 판정).
    brand=None(기본): 기존 라임그린 HUD(_BRAND_DESIGN) 적용, focus는 보조 지침으로 덧붙음(기존 동작 그대로).
    brand="claude" 등: BRAND_STYLE_PRESETS[brand]가 _BRAND_DESIGN을 완전히 대체(안 섞임).
    저장 위치: out_dir/infographic_{nb_id}.png (brand 지정 시 infographic_{nb_id}_{brand}.png)."""
    import json as _json
    if brand:
        base_design = BRAND_STYLE_PRESETS[brand]
    else:
        base_design = _BRAND_DESIGN
    parts = ([focus] if focus else []) + [base_design]
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
            # studio status는 최신순(0번=방금 만든 것)으로 옴 — arts[-1](최고참)을 보면
            # 그 노트북에 예전 완료본이 하나라도 있을 때 새로 만든 게 아직 in_progress여도
            # 즉시 "완료"로 오판해 옛날 이미지를 재다운로드하게 됨.
            if arts and arts[0].get("status") not in ("in_progress", "pending", None):
                art_id = arts[0].get("id")
                break
        except Exception:
            pass
        time.sleep(5)

    base_dir = Path(out_dir) if out_dir else (ROOT / "out" / "insights_notebook")
    base_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{brand}" if brand else ""
    ip = base_dir / f"infographic_{re.sub(r'[^0-9a-fA-F-]', '', nb_id)}{suffix}.png"
    dargs = ["download", "infographic", nb_id, "-o", str(ip)]
    if art_id:
        dargs += ["--id", art_id]
    ok_d, _od, _ed = _run_nlm(dargs, timeout=60)
    if ok_d and ip.exists():
        return {"ok": True, "path": str(ip), "error": ""}
    return {"ok": False, "path": "", "error": "다운로드 실패"}
