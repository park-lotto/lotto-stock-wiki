# 스탁브레인 SaaS 인사이트 대시보드 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 구독자가 로그인해 자기 맞춤 뉴스·리포트·유튜브·텔레·블로그를 보고 AI 일간 브리핑·통계를 얻는 웹 대시보드를, 기존 크롤링봇을 일절 건드리지 않고 새 파일로만 추가한다.

**Architecture:** 신규 FastAPI 앱(`api/dashboard_server.py`, 포트 8080)이 기존 `output/md/`(읽기 전용)와 `users.db`(설정 쓰기)를 재사용한다. 인증은 JWT(아이디/PW + 텔레그램 매직링크). 프론트는 빌드 도구 없는 순수 HTML/JS/CSS. systemd로 상시 구동.

**Tech Stack:** Python 3 / FastAPI 0.110 / uvicorn / PyJWT(설치됨) / passlib[bcrypt] / SQLite / 순수 HTML·JS·CSS(Chart.js CDN).

## Global Constraints

- **기존 파일 절대 수정 금지**: `main.py`, `main_v2.py`, `config_loader.py`, `crawlers/*`, `notifiers/*`, `processors/*`, `api/file_server.py`, `api/user_store.py` 는 읽기만 한다. 모든 신규 코드는 새 파일에 작성한다.
- **DB 스키마 변경은 가산(additive)만**: `ALTER TABLE ... ADD COLUMN`(nullable)만 사용. 기존 `SELECT *` 코드가 깨지지 않는다.
- **포트**: 대시보드는 `8080`. 기존 파일서버 `8888`과 분리.
- **작업 경로(서버)**: `/home/ubuntu/kmong/crawling_bot/`. SSH 키: `C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem`, 호스트 `ubuntu@3.39.179.148`.
- **개발 방식**: 코드는 로컬(`C:\Users\TheRose\Desktop\로또의 주식\` 외부 작업폴더 또는 임시)에서 작성 후 `scp`로 업로드. SSH heredoc로 직접 작성 금지(따옴표 깨짐).
- **JWT 시크릿**: `.env`에 `DASHBOARD_JWT_SECRET` 추가(없으면 기동 시 생성해 안내). `get_env`로 읽는다.
- **대시보드 베이스 URL**: `.env`에 `DASHBOARD_BASE_URL`(기본 `http://3.39.179.148:8080`). 텔레 매직링크 주소 생성에 사용. 도메인 연결 시 이 값만 교체.
- **MD 개별 기사 포맷**: `# {제목}` / `- **출처**:` / `- **날짜**:` / `- **링크**: [원문 보기]({url})` / `- **키워드**:` / `- **관련종목**:` / `## 본문 요약` 다음 본문.
- **MD 묶음 포맷**: `# [{kw}] 오늘의 주요 뉴스 묶음` / `## 종합 요약` / `## 수집된 기사 목록`.
- **카테고리 폴더**: `output/md/{YYYY-MM-DD}/{news|telegram|youtube|reports|blog|market}/`.

---

## 파일 구조 (신규 생성만)

```
api/
  dashboard_server.py   — FastAPI 앱(:8080), 라우트 등록, 정적 서빙, start()
  dash_auth.py          — 비밀번호 해시·검증, JWT 발급·검증, 매직링크 토큰
  dash_store.py         — users.db 가산 마이그레이션 + 인증/구독/관리 함수
  dash_feed.py          — output/md 파싱 → 구조화 피드 아이템, 유저 키워드 필터
  dash_briefing.py      — 일간 브리핑 생성(ai_summarizer 재사용) + 일자·유저별 캐시
  dash_stats.py         — 수집량·키워드 빈도 집계
  static/
    index.html          — 대시보드 셸(로그인 + 탭)
    app.js              — 인증·탭 라우팅·렌더링
    style.css           — 검정+골드+Instrument Serif
tests/
  conftest.py           — 테스트 DB 격리 픽스처
  test_dash_store.py
  test_dash_auth.py
  test_dash_feed.py
  test_dash_api.py
  test_dash_stats.py
```

- `dash_store.py`는 기존 `user_store.py`를 **import해 재사용**하고, 인증/구독/관리용 함수만 추가한다. `user_store.py` 자체는 수정하지 않는다.
- 모든 신규 모듈은 `api/` 하위에 두고 `from api import ...`로 참조한다.

---

## Task 1: 테스트 인프라 + dash_store 스키마 마이그레이션

**Files:**
- Create: `api/dash_store.py`
- Create: `tests/conftest.py`
- Create: `tests/test_dash_store.py`

**Interfaces:**
- Produces:
  - `migrate() -> None` — users 테이블에 `username TEXT`, `password_hash TEXT`, `is_admin INTEGER DEFAULT 0`, `expires_at TEXT`, `login_token TEXT`, `login_token_exp TEXT` 컬럼을 없으면 추가.
  - `set_credentials(user_id: int, username: str, password_hash: str) -> None`
  - `get_user_by_username(username: str) -> dict | None`
  - `set_admin(user_id: int, is_admin: bool) -> None`
  - `set_expiry(user_id: int, expires_at: str | None) -> None` — ISO 날짜 문자열 또는 None
  - `is_expired(user: dict) -> bool` — `expires_at`가 과거면 True (None이면 무기한 False)
  - `_conn()` — `user_store._conn` 재사용 래퍼

- [ ] **Step 1: 의존성 설치 (서버)**

Run:
```
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" -o StrictHostKeyChecking=no ubuntu@3.39.179.148 "pip install -q 'passlib[bcrypt]' 'pyjwt' 'httpx' 'pytest' 'python-multipart' && python3 -c 'import passlib,jwt,httpx,pytest,multipart;print(\"OK\")'"
```
Expected: `OK`

- [ ] **Step 2: conftest.py 작성 (테스트 DB 격리)**

`tests/conftest.py`:
```python
import os
import tempfile
import importlib
import pytest


@pytest.fixture()
def fresh_db(monkeypatch):
    """임시 users.db로 user_store와 dash_store를 격리 초기화한다."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    from pathlib import Path
    from api import user_store
    monkeypatch.setattr(user_store, "_DB_PATH", Path(tmp.name))
    user_store.init_db()
    from api import dash_store
    importlib.reload(dash_store)  # _DB_PATH 재바인딩
    dash_store.migrate()
    yield user_store, dash_store
    os.unlink(tmp.name)
```

- [ ] **Step 3: 실패 테스트 작성**

`tests/test_dash_store.py`:
```python
def test_migrate_adds_columns_and_credentials(fresh_db):
    us, ds = fresh_db
    us.add_user("빅팜", "111", "tok")
    u = us.get_user_by_name("빅팜")
    ds.set_credentials(u["id"], "bigfarm", "hashed")
    got = ds.get_user_by_username("bigfarm")
    assert got is not None
    assert got["username"] == "bigfarm"
    assert got["password_hash"] == "hashed"


def test_admin_and_expiry(fresh_db):
    us, ds = fresh_db
    us.add_user("나", "222", "tok")
    u = us.get_user_by_name("나")
    ds.set_admin(u["id"], True)
    ds.set_expiry(u["id"], "2020-01-01")
    fresh = us.get_user_by_name("나")
    assert ds.is_expired(fresh) is True
    ds.set_expiry(u["id"], None)
    assert ds.is_expired(us.get_user_by_name("나")) is False
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_store.py -v`
Expected: FAIL (`No module named 'api.dash_store'`)

- [ ] **Step 5: dash_store.py 구현**

`api/dash_store.py`:
```python
"""
대시보드용 users.db 확장.
기존 api/user_store.py를 재사용하고, 인증·구독·관리 컬럼/함수만 가산한다.
user_store.py 자체는 수정하지 않는다.
"""
from datetime import datetime
from api import user_store

_NEW_COLUMNS = {
    "username": "TEXT",
    "password_hash": "TEXT",
    "is_admin": "INTEGER DEFAULT 0",
    "expires_at": "TEXT",
    "login_token": "TEXT",
    "login_token_exp": "TEXT",
}


def _conn():
    return user_store._conn()


def migrate() -> None:
    """users 테이블에 없는 컬럼만 추가한다(가산 마이그레이션)."""
    with _conn() as con:
        cols = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
        for name, decl in _NEW_COLUMNS.items():
            if name not in cols:
                con.execute(f"ALTER TABLE users ADD COLUMN {name} {decl}")


def set_credentials(user_id: int, username: str, password_hash: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE users SET username=?, password_hash=? WHERE id=?",
            (username, password_hash, user_id),
        )


def get_user_by_username(username: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    return dict(row) if row else None


def set_admin(user_id: int, is_admin: bool) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE users SET is_admin=? WHERE id=?",
            (1 if is_admin else 0, user_id),
        )


def set_expiry(user_id: int, expires_at) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE users SET expires_at=? WHERE id=?", (expires_at, user_id)
        )


def is_expired(user: dict) -> bool:
    exp = user.get("expires_at")
    if not exp:
        return False
    try:
        return datetime.fromisoformat(exp) < datetime.now()
    except ValueError:
        return False


migrate()
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: 커밋**

```bash
git add api/dash_store.py tests/conftest.py tests/test_dash_store.py
git commit -m "feat(dash): users.db 가산 마이그레이션 + 인증/구독 컬럼"
```

---

## Task 2: 인증 모듈 (비밀번호 해시 + JWT)

**Files:**
- Create: `api/dash_auth.py`
- Create: `tests/test_dash_auth.py`

**Interfaces:**
- Consumes: `dash_store` (from Task 1)
- Produces:
  - `hash_password(plain: str) -> str`
  - `verify_password(plain: str, hashed: str) -> bool`
  - `make_token(user_id: int, is_admin: bool) -> str` — JWT, 만료 7일
  - `decode_token(token: str) -> dict | None` — `{"uid": int, "admin": bool}` 또는 만료/위조 시 None
  - `_secret() -> str` — `DASHBOARD_JWT_SECRET` env, 없으면 고정 개발용 기본값

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_dash_auth.py`:
```python
from api import dash_auth


def test_password_roundtrip():
    h = dash_auth.hash_password("secret123")
    assert h != "secret123"
    assert dash_auth.verify_password("secret123", h) is True
    assert dash_auth.verify_password("wrong", h) is False


def test_jwt_roundtrip():
    tok = dash_auth.make_token(7, True)
    payload = dash_auth.decode_token(tok)
    assert payload["uid"] == 7
    assert payload["admin"] is True


def test_jwt_garbage_returns_none():
    assert dash_auth.decode_token("not.a.token") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_auth.py -v`
Expected: FAIL (`No module named 'api.dash_auth'`)

- [ ] **Step 3: dash_auth.py 구현**

`api/dash_auth.py`:
```python
"""대시보드 인증: 비밀번호 해시(bcrypt) + JWT 발급/검증."""
from datetime import datetime, timedelta

import jwt
from passlib.context import CryptContext

from config_loader import get_env

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGO = "HS256"
_TTL_DAYS = 7


def _secret() -> str:
    return get_env("DASHBOARD_JWT_SECRET", "dev-only-change-me")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return _pwd.verify(plain, hashed)
    except ValueError:
        return False


def make_token(user_id: int, is_admin: bool) -> str:
    payload = {
        "uid": user_id,
        "admin": bool(is_admin),
        "exp": datetime.utcnow() + timedelta(days=_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_auth.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dash_auth.py tests/test_dash_auth.py
git commit -m "feat(dash): bcrypt 해시 + JWT 발급/검증"
```

---

## Task 3: 텔레그램 매직링크 토큰

**Files:**
- Modify: `api/dash_store.py` (함수 추가 — 본 계획에서 새로 만든 파일이므로 수정 허용)
- Create: `tests/test_dash_magiclink.py`

**Interfaces:**
- Produces (in `dash_store`):
  - `issue_login_token(user_id: int, ttl_min: int = 10) -> str` — 32자 hex 토큰 생성·저장(만료시간 포함), 토큰 반환
  - `consume_login_token(token: str) -> dict | None` — 유효하면 해당 user dict 반환 후 토큰 무효화, 아니면 None

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_dash_magiclink.py`:
```python
def test_magic_link_issue_and_consume(fresh_db):
    us, ds = fresh_db
    us.add_user("빅팜", "111", "tok")
    u = us.get_user_by_name("빅팜")
    token = ds.issue_login_token(u["id"], ttl_min=10)
    assert token and len(token) >= 16
    got = ds.consume_login_token(token)
    assert got["id"] == u["id"]
    # 1회용: 두 번째는 실패
    assert ds.consume_login_token(token) is None


def test_magic_link_expired(fresh_db):
    us, ds = fresh_db
    us.add_user("빅팜", "111", "tok")
    u = us.get_user_by_name("빅팜")
    token = ds.issue_login_token(u["id"], ttl_min=-1)  # 이미 만료
    assert ds.consume_login_token(token) is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_magiclink.py -v`
Expected: FAIL (`AttributeError: ... issue_login_token`)

- [ ] **Step 3: dash_store.py에 함수 추가**

`api/dash_store.py` 끝의 `migrate()` 호출 줄 **위에** 추가:
```python
import secrets


def issue_login_token(user_id: int, ttl_min: int = 10) -> str:
    token = secrets.token_hex(16)
    exp = (datetime.now() + timedelta(minutes=ttl_min)).isoformat()
    with _conn() as con:
        con.execute(
            "UPDATE users SET login_token=?, login_token_exp=? WHERE id=?",
            (token, exp, user_id),
        )
    return token


def consume_login_token(token: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM users WHERE login_token=?", (token,)
        ).fetchone()
        if not row:
            return None
        user = dict(row)
        exp = user.get("login_token_exp")
        con.execute(
            "UPDATE users SET login_token=NULL, login_token_exp=NULL WHERE id=?",
            (user["id"],),
        )
    if not exp or datetime.fromisoformat(exp) < datetime.now():
        return None
    return user
```
또한 파일 상단 import에 `from datetime import datetime, timedelta`로 `timedelta` 포함시킨다(Task 1에서는 `datetime`만 import했으므로 수정).

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_magiclink.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dash_store.py tests/test_dash_magiclink.py
git commit -m "feat(dash): 텔레그램 매직링크 1회용 토큰"
```

---

## Task 4: 피드 리더 (output/md 파싱 + 키워드 필터)

**Files:**
- Create: `api/dash_feed.py`
- Create: `tests/test_dash_feed.py`

**Interfaces:**
- Produces:
  - `parse_md_file(path: str) -> dict` — `{title, source, date, url, keyword, stocks, summary, category, filename}` 반환. 묶음 파일은 `is_bundle=True` 표시.
  - `list_feed(base_dir: str, date: str, categories: list[str] | None = None) -> list[dict]` — 해당 날짜 폴더의 모든 MD를 파싱해 최신순 리스트.
  - `filter_by_keywords(items: list[dict], keywords: list[str]) -> list[dict]` — keywords 비면 전체 반환. 아니면 `title/summary/keyword`에 키워드 포함된 것만.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_dash_feed.py`:
```python
import os
from api import dash_feed

SAMPLE = """# 이란, 호르무즈 재압박

- **출처**: 아시아경제
- **날짜**: 2026-06-21 00:48
- **링크**: [원문 보기](https://example.com/a)
- **키워드**: 호르무즈
- **관련종목**: -

## 본문 요약

[핵심 내용]
- 유가 상승 가능성.
"""


def test_parse_md_file(tmp_path):
    d = tmp_path / "2026-06-21" / "news"
    d.mkdir(parents=True)
    f = d / "2026-06-21_1000_test.md"
    f.write_text(SAMPLE, encoding="utf-8")
    item = dash_feed.parse_md_file(str(f))
    assert item["title"] == "이란, 호르무즈 재압박"
    assert item["source"] == "아시아경제"
    assert item["url"] == "https://example.com/a"
    assert item["keyword"] == "호르무즈"
    assert "유가" in item["summary"]
    assert item["category"] == "news"


def test_filter_by_keywords():
    items = [
        {"title": "삼성전자 신고가", "summary": "", "keyword": "삼성전자"},
        {"title": "이란 유가", "summary": "", "keyword": "호르무즈"},
    ]
    out = dash_feed.filter_by_keywords(items, ["삼성전자"])
    assert len(out) == 1 and out[0]["keyword"] == "삼성전자"
    assert len(dash_feed.filter_by_keywords(items, [])) == 2
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_feed.py -v`
Expected: FAIL (`No module named 'api.dash_feed'`)

- [ ] **Step 3: dash_feed.py 구현**

`api/dash_feed.py`:
```python
"""output/md 마크다운을 구조화 피드 아이템으로 파싱하고 키워드로 필터한다."""
import os
import re

_META = {
    "source": re.compile(r"^- \*\*출처\*\*:\s*(.+)$", re.M),
    "date": re.compile(r"^- \*\*날짜\*\*:\s*(.+)$", re.M),
    "keyword": re.compile(r"^- \*\*키워드\*\*:\s*(.+)$", re.M),
    "stocks": re.compile(r"^- \*\*관련종목\*\*:\s*(.+)$", re.M),
}
_URL = re.compile(r"^- \*\*링크\*\*:\s*\[원문 보기\]\((.+?)\)", re.M)
_TITLE = re.compile(r"^#\s+(.+)$", re.M)
_SUMMARY = re.compile(r"##\s*(?:본문 요약|종합 요약)\s*\n(.+)", re.S)


def parse_md_file(path: str) -> dict:
    text = open(path, encoding="utf-8").read()
    fname = os.path.basename(path)
    category = os.path.basename(os.path.dirname(path))
    title_m = _TITLE.search(text)
    title = title_m.group(1).strip() if title_m else fname
    is_bundle = "묶음" in title
    summary_m = _SUMMARY.search(text)
    summary = summary_m.group(1).strip() if summary_m else ""

    def g(rx):
        m = rx.search(text)
        return m.group(1).strip() if m else ""

    return {
        "title": title,
        "source": g(_META["source"]),
        "date": g(_META["date"]),
        "url": (_URL.search(text).group(1) if _URL.search(text) else ""),
        "keyword": g(_META["keyword"]),
        "stocks": g(_META["stocks"]),
        "summary": summary,
        "category": category,
        "filename": fname,
        "is_bundle": is_bundle,
    }


def list_feed(base_dir, date, categories=None):
    day_dir = os.path.join(base_dir, date)
    if not os.path.isdir(day_dir):
        return []
    items = []
    cats = categories or os.listdir(day_dir)
    for cat in cats:
        cat_dir = os.path.join(day_dir, cat)
        if not os.path.isdir(cat_dir):
            continue
        for fn in os.listdir(cat_dir):
            if not fn.endswith(".md"):
                continue
            fpath = os.path.join(cat_dir, fn)
            try:
                item = parse_md_file(fpath)
                item["mtime"] = os.path.getmtime(fpath)
                items.append(item)
            except Exception:
                continue
    items.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return items


def filter_by_keywords(items, keywords):
    if not keywords:
        return items
    out = []
    for it in items:
        hay = (it.get("title", "") + it.get("summary", "") + it.get("keyword", "")).lower()
        if any(kw.lower() in hay for kw in keywords):
            out.append(it)
    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_feed.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dash_feed.py tests/test_dash_feed.py
git commit -m "feat(dash): MD 피드 파서 + 키워드 필터"
```

---

## Task 5: 통계 집계

**Files:**
- Create: `api/dash_stats.py`
- Create: `tests/test_dash_stats.py`

**Interfaces:**
- Consumes: `dash_feed.list_feed`
- Produces:
  - `collection_counts(base_dir: str, days: list[str]) -> dict` — `{date: {category: count}}`
  - `keyword_frequency(items: list[dict], top_n: int = 20) -> list[tuple[str, int]]` — 키워드 등장 빈도 내림차순

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_dash_stats.py`:
```python
from api import dash_stats


def test_keyword_frequency():
    items = [
        {"keyword": "삼성전자"}, {"keyword": "삼성전자"}, {"keyword": "두산에너빌리티"},
    ]
    freq = dash_stats.keyword_frequency(items)
    assert freq[0] == ("삼성전자", 2)


def test_collection_counts(tmp_path):
    d = tmp_path / "2026-06-21" / "news"
    d.mkdir(parents=True)
    (d / "a.md").write_text("# 제목\n## 본문 요약\nx", encoding="utf-8")
    counts = dash_stats.collection_counts(str(tmp_path), ["2026-06-21"])
    assert counts["2026-06-21"]["news"] == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_stats.py -v`
Expected: FAIL (`No module named 'api.dash_stats'`)

- [ ] **Step 3: dash_stats.py 구현**

`api/dash_stats.py`:
```python
"""수집량·키워드 빈도 집계."""
import os
from collections import Counter

from api import dash_feed


def collection_counts(base_dir, days):
    result = {}
    for day in days:
        day_dir = os.path.join(base_dir, day)
        per_cat = {}
        if os.path.isdir(day_dir):
            for cat in os.listdir(day_dir):
                cat_dir = os.path.join(day_dir, cat)
                if os.path.isdir(cat_dir):
                    per_cat[cat] = len([f for f in os.listdir(cat_dir) if f.endswith(".md")])
        result[day] = per_cat
    return result


def keyword_frequency(items, top_n=20):
    c = Counter()
    for it in items:
        kw = it.get("keyword", "").strip()
        if kw and kw != "-":
            c[kw] += 1
    return c.most_common(top_n)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_stats.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dash_stats.py tests/test_dash_stats.py
git commit -m "feat(dash): 수집량·키워드 빈도 집계"
```

---

## Task 6: 일간 브리핑 (생성 + 캐시)

**Files:**
- Create: `api/dash_briefing.py`
- Create: `tests/test_dash_briefing.py`

**Interfaces:**
- Consumes: `dash_feed`, `processors.ai_summarizer._call`
- Produces:
  - `build_briefing(base_dir, date, keywords, summarize_fn=None) -> str` — 해당 날짜·키워드 피드를 모아 AI 종합요약. `summarize_fn` 주입 가능(테스트용).
  - `get_briefing(base_dir, date, user_id, keywords, force=False, summarize_fn=None) -> str` — 캐시(`output/dash_cache/{date}_{user_id}.txt`) 우선, 없거나 force면 생성·저장. `summarize_fn`은 테스트 주입용.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_dash_briefing.py`:
```python
import os
from api import dash_briefing


def _fake_summarize(system, content):
    return "종합요약: " + content[:20]


def test_build_briefing(tmp_path):
    d = tmp_path / "2026-06-21" / "news"
    d.mkdir(parents=True)
    (d / "a.md").write_text(
        "# 삼성전자 신고가\n- **키워드**: 삼성전자\n## 본문 요약\nHBM 수요 급증", encoding="utf-8"
    )
    out = dash_briefing.build_briefing(
        str(tmp_path), "2026-06-21", ["삼성전자"], summarize_fn=_fake_summarize
    )
    assert "종합요약" in out


def test_cache_roundtrip(tmp_path):
    base = str(tmp_path)
    d = tmp_path / "2026-06-21" / "news"
    d.mkdir(parents=True)
    (d / "a.md").write_text("# 삼성\n- **키워드**: 삼성\n## 본문 요약\nx", encoding="utf-8")
    first = dash_briefing.get_briefing(base, "2026-06-21", 1, ["삼성"], force=True, summarize_fn=_fake_summarize)
    cache = tmp_path / "dash_cache" / "2026-06-21_1.txt"
    assert cache.exists()
    cache.write_text("CACHED", encoding="utf-8")
    second = dash_briefing.get_briefing(base, "2026-06-21", 1, ["삼성"])
    assert second == "CACHED"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_briefing.py -v`
Expected: FAIL (`No module named 'api.dash_briefing'`)

- [ ] **Step 3: dash_briefing.py 구현**

`api/dash_briefing.py`:
```python
"""일간 종합 브리핑 생성 + 일자·유저별 파일 캐시."""
import os

from api import dash_feed


def _default_summarize(system, content):
    from processors.ai_summarizer import _call
    return _call(system, content)


def build_briefing(base_dir, date, keywords, summarize_fn=None):
    fn = summarize_fn or _default_summarize
    items = dash_feed.filter_by_keywords(
        dash_feed.list_feed(base_dir, date), keywords
    )
    if not items:
        return "오늘 수집된 관련 콘텐츠가 없습니다."
    joined = "\n\n".join(
        f"[{it['category']}] {it['title']}\n{it['summary']}" for it in items[:30]
    )
    system = (
        "주식·경제 콘텐츠 묶음을 종합 분석하는 전문가다. "
        "오늘의 핵심 흐름·수급·주도 테마를 4~6문장으로 한국어로 요약한다. "
        "불필요한 인사말 없이 결론부터 쓴다."
    )
    return fn(system, joined[:6000])


def get_briefing(base_dir, date, user_id, keywords, force=False, summarize_fn=None):
    cache_dir = os.path.join(base_dir, "dash_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{date}_{user_id}.txt")
    if not force and os.path.exists(cache_path):
        return open(cache_path, encoding="utf-8").read()
    result = build_briefing(base_dir, date, keywords, summarize_fn=summarize_fn)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(result)
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_briefing.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dash_briefing.py tests/test_dash_briefing.py
git commit -m "feat(dash): 일간 브리핑 생성 + 캐시"
```

---

## Task 7: FastAPI 앱 + 로그인 API (아이디/PW)

**Files:**
- Create: `api/dashboard_server.py`
- Create: `tests/test_dash_api.py`

**Interfaces:**
- Consumes: `dash_store`, `dash_auth`, `user_store`
- Produces:
  - FastAPI `app`
  - `POST /api/login` body `{username, password}` → `{token, name, is_admin}` 또는 401. 만료 계정은 403.
  - `current_user(authorization: Header)` 의존성 → user dict, 실패 시 401.
  - `start()` — uvicorn 포트 8080 구동.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_dash_api.py`:
```python
from fastapi.testclient import TestClient


def _client(fresh_db):
    us, ds = fresh_db
    from api import dashboard_server
    import importlib
    importlib.reload(dashboard_server)
    return TestClient(dashboard_server.app), us, ds


def test_login_success_and_fail(fresh_db):
    client, us, ds = _client(fresh_db)
    from api import dash_auth
    us.add_user("빅팜", "111", "tok")
    u = us.get_user_by_name("빅팜")
    ds.set_credentials(u["id"], "bigfarm", dash_auth.hash_password("pw1234"))
    ok = client.post("/api/login", json={"username": "bigfarm", "password": "pw1234"})
    assert ok.status_code == 200
    assert "token" in ok.json()
    bad = client.post("/api/login", json={"username": "bigfarm", "password": "x"})
    assert bad.status_code == 401


def test_expired_login_blocked(fresh_db):
    client, us, ds = _client(fresh_db)
    from api import dash_auth
    us.add_user("만료", "222", "tok")
    u = us.get_user_by_name("만료")
    ds.set_credentials(u["id"], "old", dash_auth.hash_password("pw"))
    ds.set_expiry(u["id"], "2020-01-01")
    r = client.post("/api/login", json={"username": "old", "password": "pw"})
    assert r.status_code == 403
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: FAIL (`No module named 'api.dashboard_server'`)

- [ ] **Step 3: dashboard_server.py 구현 (로그인 + 의존성)**

`api/dashboard_server.py`:
```python
"""스탁브레인 대시보드 API (포트 8080). 기존 크롤링봇과 분리된 신규 앱."""
import os

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config_loader import get_config, get_env
from api import user_store, dash_store, dash_auth

app = FastAPI(title="StockBrain Dashboard", docs_url=None)

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class LoginBody(BaseModel):
    username: str
    password: str


def _base_dir() -> str:
    return get_config()["server"]["output_dir"]


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.replace("Bearer ", "").strip()
    payload = dash_auth.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="인증 필요")
    with user_store._conn() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (payload["uid"],)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="유저 없음")
    user = dict(row)
    if dash_store.is_expired(user):
        raise HTTPException(status_code=403, detail="구독 만료")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="관리자 전용")
    return user


@app.post("/api/login")
def login(body: LoginBody):
    user = dash_store.get_user_by_username(body.username)
    if not user or not dash_auth.verify_password(body.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호 오류")
    if dash_store.is_expired(user):
        raise HTTPException(status_code=403, detail="구독이 만료되었습니다")
    token = dash_auth.make_token(user["id"], bool(user.get("is_admin")))
    return {"token": token, "name": user["name"], "is_admin": bool(user.get("is_admin"))}


@app.get("/health")
def health():
    return {"status": "ok"}


def start():
    import uvicorn
    if os.path.isdir(_STATIC):
        app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
```
주의: `StaticFiles` 마운트는 모든 `/api/*` 라우트 **등록 이후**에 `start()`에서 수행한다(루트 마운트가 API를 가리지 않도록).

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dashboard_server.py tests/test_dash_api.py
git commit -m "feat(dash): FastAPI 앱 + 아이디/PW 로그인 + JWT 의존성"
```

---

## Task 8: 피드·브리핑·통계 API + 텔레 매직링크 로그인

**Files:**
- Modify: `api/dashboard_server.py` (라우트 추가)
- Modify: `tests/test_dash_api.py` (테스트 추가)

**Interfaces:**
- Produces:
  - `GET /api/feed?date=&category=` (인증) → `{items: [...], date}`. category 생략 시 전체.
  - `GET /api/briefing?date=&force=` (인증) → `{briefing, date}`
  - `GET /api/stats?days=7` (인증) → `{counts, keyword_freq}`
  - `POST /api/login/telegram/request` body `{chat_id}` → 매직링크 발송용 토큰 생성(반환은 `{ok:true}`; 실제 텔레 발송은 Task 12에서 연결)
  - `GET /api/login/telegram/consume?token=` → `{token, name, is_admin}` 또는 401

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_dash_api.py`에 추가:
```python
def _auth_header(client, us, ds, kws):
    from api import dash_auth
    us.add_user("빅팜", "111", "tok")
    u = us.get_user_by_name("빅팜")
    ds.set_credentials(u["id"], "bf", dash_auth.hash_password("pw"))
    for k in kws:
        us.add_keyword(u["id"], k)
    tok = client.post("/api/login", json={"username": "bf", "password": "pw"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}, u


def test_feed_filtered_by_keywords(fresh_db, tmp_path, monkeypatch):
    client, us, ds = _client(fresh_db)
    from api import dashboard_server
    monkeypatch.setattr(dashboard_server, "_base_dir", lambda: str(tmp_path))
    d = tmp_path / "2026-06-21" / "news"
    d.mkdir(parents=True)
    (d / "a.md").write_text("# 삼성전자 신고가\n- **키워드**: 삼성전자\n## 본문 요약\nHBM", encoding="utf-8")
    (d / "b.md").write_text("# 이란 유가\n- **키워드**: 호르무즈\n## 본문 요약\n유가", encoding="utf-8")
    hdr, u = _auth_header(client, us, ds, ["삼성전자"])
    r = client.get("/api/feed?date=2026-06-21", headers=hdr)
    assert r.status_code == 200
    titles = [it["title"] for it in r.json()["items"]]
    assert any("삼성전자" in t for t in titles)
    assert not any("이란" in t for t in titles)


def test_telegram_magiclink_consume(fresh_db):
    client, us, ds = _client(fresh_db)
    us.add_user("빅팜", "111", "tok")
    u = us.get_user_by_name("빅팜")
    token = ds.issue_login_token(u["id"], ttl_min=10)
    r = client.get(f"/api/login/telegram/consume?token={token}")
    assert r.status_code == 200 and "token" in r.json()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: FAIL (피드/매직링크 라우트 404 또는 AttributeError)

- [ ] **Step 3: dashboard_server.py에 라우트 추가**

`@app.get("/health")` 위에 추가:
```python
from datetime import datetime
from api import dash_feed, dash_briefing, dash_stats


@app.get("/api/feed")
def feed(date: str = None, category: str = None, user: dict = Depends(current_user)):
    date = date or datetime.now().strftime("%Y-%m-%d")
    cats = [category] if category else None
    items = dash_feed.list_feed(_base_dir(), date, cats)
    kws = user_store.get_user_keywords(user["id"])
    items = dash_feed.filter_by_keywords(items, kws)
    return {"items": items, "date": date}


@app.get("/api/briefing")
def briefing(date: str = None, force: bool = False, user: dict = Depends(current_user)):
    date = date or datetime.now().strftime("%Y-%m-%d")
    kws = user_store.get_user_keywords(user["id"])
    text = dash_briefing.get_briefing(_base_dir(), date, user["id"], kws, force=force)
    return {"briefing": text, "date": date}


@app.get("/api/stats")
def stats(days: int = 7, user: dict = Depends(current_user)):
    from datetime import timedelta
    today = datetime.now()
    day_list = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    counts = dash_stats.collection_counts(_base_dir(), day_list)
    kws = user_store.get_user_keywords(user["id"])
    all_items = []
    for d in day_list:
        all_items += dash_feed.filter_by_keywords(dash_feed.list_feed(_base_dir(), d), kws)
    freq = dash_stats.keyword_frequency(all_items)
    return {"counts": counts, "keyword_freq": freq}


class TgRequest(BaseModel):
    chat_id: str


@app.post("/api/login/telegram/request")
def tg_request(body: TgRequest):
    u = user_store.get_user_by_chat_id(body.chat_id)
    if not u:
        raise HTTPException(status_code=404, detail="등록되지 않은 사용자")
    token = dash_store.issue_login_token(u["id"], ttl_min=10)
    base = get_env("DASHBOARD_BASE_URL", "http://3.39.179.148:8080")
    link = f"{base}/?magic={token}"
    try:
        from notifiers.telegram_sender_v2 import _run_async
        from telegram import Bot

        async def _send():
            await Bot(token=u["bot_token"]).send_message(
                chat_id=u["chat_id"],
                text=f"🔐 스탁브레인 로그인 링크 (10분 유효):\n{link}",
            )
        _run_async(_send())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"링크 발송 실패: {e}")
    return {"ok": True}


@app.get("/api/login/telegram/consume")
def tg_consume(token: str):
    u = dash_store.consume_login_token(token)
    if not u:
        raise HTTPException(status_code=401, detail="만료되었거나 잘못된 링크")
    if dash_store.is_expired(u):
        raise HTTPException(status_code=403, detail="구독 만료")
    jwt_token = dash_auth.make_token(u["id"], bool(u.get("is_admin")))
    return {"token": jwt_token, "name": u["name"], "is_admin": bool(u.get("is_admin"))}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dashboard_server.py tests/test_dash_api.py
git commit -m "feat(dash): 피드·브리핑·통계 API + 텔레 매직링크 로그인"
```

---

## Task 9: 설정 API (키워드·채널 CRUD + 수신 토글)

**Files:**
- Modify: `api/dashboard_server.py`
- Modify: `tests/test_dash_api.py`

**Interfaces:**
- Produces (모두 인증 필요, 본인 데이터만):
  - `GET /api/settings` → `{keywords, tg, yt, blog, receive}`
  - `POST /api/settings/keyword` `{keyword}` / `DELETE /api/settings/keyword` `{keyword}`
  - `POST /api/settings/channel` `{kind, name, url}` (kind: tg|yt|blog) / `DELETE /api/settings/channel` `{kind, name}`
  - `POST /api/settings/receive` `{field, value}` (field: news|telegram|youtube|blog|report|market)

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_dash_api.py`에 추가:
```python
def test_settings_keyword_crud(fresh_db):
    client, us, ds = _client(fresh_db)
    hdr, u = _auth_header(client, us, ds, [])
    add = client.post("/api/settings/keyword", json={"keyword": "에코프로"}, headers=hdr)
    assert add.status_code == 200
    got = client.get("/api/settings", headers=hdr).json()
    assert "에코프로" in got["keywords"]
    client.request("DELETE", "/api/settings/keyword", json={"keyword": "에코프로"}, headers=hdr)
    assert "에코프로" not in client.get("/api/settings", headers=hdr).json()["keywords"]


def test_settings_receive_toggle(fresh_db):
    client, us, ds = _client(fresh_db)
    hdr, u = _auth_header(client, us, ds, [])
    r = client.post("/api/settings/receive", json={"field": "youtube", "value": True}, headers=hdr)
    assert r.status_code == 200
    assert client.get("/api/settings", headers=hdr).json()["receive"]["youtube"] == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: FAIL (설정 라우트 404)

- [ ] **Step 3: dashboard_server.py에 설정 라우트 추가**

```python
class KeywordBody(BaseModel):
    keyword: str

class ChannelBody(BaseModel):
    kind: str
    name: str = ""
    url: str = ""

class ReceiveBody(BaseModel):
    field: str
    value: bool


@app.get("/api/settings")
def get_settings(user: dict = Depends(current_user)):
    uid = user["id"]
    return {
        "keywords": user_store.get_user_keywords(uid),
        "tg": user_store.get_user_tg_channels(uid),
        "yt": user_store.get_user_yt_channels(uid),
        "blog": user_store.get_user_blog_sites(uid),
        "receive": user_store.get_settings(uid),
    }


@app.post("/api/settings/keyword")
def add_kw(body: KeywordBody, user: dict = Depends(current_user)):
    ok = user_store.add_keyword(user["id"], body.keyword.strip())
    return {"ok": ok}


@app.delete("/api/settings/keyword")
def del_kw(body: KeywordBody, user: dict = Depends(current_user)):
    ok = user_store.remove_keyword(user["id"], body.keyword.strip())
    return {"ok": ok}


_ADDERS = {"tg": user_store.add_tg_channel, "yt": user_store.add_yt_channel, "blog": user_store.add_blog_site}
_REMOVERS = {"tg": user_store.remove_tg_channel, "yt": user_store.remove_yt_channel, "blog": user_store.remove_blog_site}


@app.post("/api/settings/channel")
def add_channel(body: ChannelBody, user: dict = Depends(current_user)):
    fn = _ADDERS.get(body.kind)
    if not fn:
        raise HTTPException(status_code=400, detail="잘못된 종류")
    name = body.name.strip() or body.url.strip()
    return {"ok": fn(user["id"], name, body.url.strip())}


@app.delete("/api/settings/channel")
def del_channel(body: ChannelBody, user: dict = Depends(current_user)):
    fn = _REMOVERS.get(body.kind)
    if not fn:
        raise HTTPException(status_code=400, detail="잘못된 종류")
    return {"ok": fn(user["id"], body.name.strip())}


@app.post("/api/settings/receive")
def set_receive(body: ReceiveBody, user: dict = Depends(current_user)):
    try:
        user_store.update_setting(user["id"], body.field, body.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dashboard_server.py tests/test_dash_api.py
git commit -m "feat(dash): 설정 API (키워드·채널 CRUD + 수신 토글)"
```

---

## Task 10: 관리자 API (구독자 관리)

**Files:**
- Modify: `api/dashboard_server.py`
- Modify: `tests/test_dash_api.py`

**Interfaces:**
- Produces (모두 `require_admin`):
  - `GET /api/admin/users` → 전체 유저 목록(민감정보 제외: password_hash·bot_token 마스킹)
  - `POST /api/admin/users` `{name, chat_id, bot_token, username, password, expires_at}` → 계정 생성 + 자격증명 설정
  - `POST /api/admin/users/{uid}/expiry` `{expires_at}` → 만료일 변경
  - `DELETE /api/admin/users/{uid}` → 삭제

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_dash_api.py`에 추가:
```python
def _admin_header(client, us, ds):
    from api import dash_auth
    us.add_user("관리자", "999", "tok")
    a = us.get_user_by_name("관리자")
    ds.set_credentials(a["id"], "admin", dash_auth.hash_password("adminpw"))
    ds.set_admin(a["id"], True)
    tok = client.post("/api/login", json={"username": "admin", "password": "adminpw"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_admin_create_and_list_user(fresh_db):
    client, us, ds = _client(fresh_db)
    hdr = _admin_header(client, us, ds)
    r = client.post("/api/admin/users", headers=hdr, json={
        "name": "신규고객", "chat_id": "555", "bot_token": "btok",
        "username": "newcust", "password": "pw", "expires_at": None})
    assert r.status_code == 200
    users = client.get("/api/admin/users", headers=hdr).json()["users"]
    assert any(u["name"] == "신규고객" for u in users)


def test_admin_blocked_for_normal_user(fresh_db):
    client, us, ds = _client(fresh_db)
    hdr, u = _auth_header(client, us, ds, [])
    assert client.get("/api/admin/users", headers=hdr).status_code == 403
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: FAIL (admin 라우트 404)

- [ ] **Step 3: dashboard_server.py에 관리자 라우트 추가**

```python
class AdminUserBody(BaseModel):
    name: str
    chat_id: str
    bot_token: str
    username: str
    password: str
    expires_at: str | None = None

class ExpiryBody(BaseModel):
    expires_at: str | None = None


def _mask(u: dict) -> dict:
    return {
        "id": u["id"], "name": u["name"], "chat_id": u["chat_id"],
        "username": u.get("username"), "is_admin": bool(u.get("is_admin")),
        "expires_at": u.get("expires_at"), "enabled": u.get("enabled"),
    }


@app.get("/api/admin/users")
def admin_list(_: dict = Depends(require_admin)):
    return {"users": [_mask(u) for u in user_store.get_all_users()]}


@app.post("/api/admin/users")
def admin_create(body: AdminUserBody, _: dict = Depends(require_admin)):
    if not user_store.add_user(body.name, body.chat_id, body.bot_token):
        raise HTTPException(status_code=409, detail="이미 등록된 chat_id")
    u = user_store.get_user_by_chat_id(body.chat_id)
    dash_store.set_credentials(u["id"], body.username, dash_auth.hash_password(body.password))
    if body.expires_at:
        dash_store.set_expiry(u["id"], body.expires_at)
    return {"ok": True, "id": u["id"]}


@app.post("/api/admin/users/{uid}/expiry")
def admin_expiry(uid: int, body: ExpiryBody, _: dict = Depends(require_admin)):
    dash_store.set_expiry(uid, body.expires_at)
    return {"ok": True}


@app.delete("/api/admin/users/{uid}")
def admin_delete(uid: int, _: dict = Depends(require_admin)):
    with user_store._conn() as con:
        cur = con.execute("DELETE FROM users WHERE id=?", (uid,))
    return {"ok": cur.rowcount > 0}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/test_dash_api.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/dashboard_server.py tests/test_dash_api.py
git commit -m "feat(dash): 관리자 API (구독자 생성·목록·만료·삭제)"
```

---

## Task 11: 프론트 — 셸·스타일·로그인 (검정+골드)

**Files:**
- Create: `api/static/index.html`
- Create: `api/static/style.css`
- Create: `api/static/app.js`

**Interfaces:**
- Consumes: 모든 `/api/*` 엔드포인트
- Produces: 브라우저에서 로그인 → 토큰 localStorage 저장 → 탭 표시

- [ ] **Step 1: index.html 작성**

`api/static/index.html`:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>로또의 스탁브레인</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <div id="login" class="login-screen">
    <h1 class="brand">로또의 스탁브레인</h1>
    <input id="username" placeholder="아이디" />
    <input id="password" type="password" placeholder="비밀번호" />
    <button onclick="doLogin()">로그인</button>
    <p id="login-error" class="error"></p>
  </div>

  <div id="dash" class="hidden">
    <header>
      <span class="brand-sm">로또의 스탁브레인</span>
      <nav>
        <button class="tab active" data-tab="briefing">🏠 브리핑</button>
        <button class="tab" data-tab="feed">📰 피드</button>
        <button class="tab" data-tab="stats">📊 통계</button>
        <button class="tab" data-tab="settings">⚙️ 설정</button>
        <button class="tab admin-only hidden" data-tab="admin">👑 관리자</button>
      </nav>
      <span class="user-box"><span id="who"></span> <a onclick="logout()">로그아웃</a></span>
    </header>
    <main id="view"></main>
  </div>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css 작성 (검정+골드)**

`api/static/style.css`:
```css
:root { --bg:#0a0a0a; --panel:#141414; --gold:#c8a24a; --text:#e8e8e8; --muted:#888; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:'Noto Sans KR',sans-serif; }
.hidden { display:none !important; }
.brand, .brand-sm { font-family:'Instrument Serif',serif; color:var(--gold); }
.login-screen { max-width:360px; margin:12vh auto; display:flex; flex-direction:column; gap:12px; padding:0 20px; }
.login-screen h1 { font-size:2rem; text-align:center; }
.login-screen input { padding:12px; background:var(--panel); border:1px solid #333; color:var(--text); border-radius:8px; }
.login-screen button, .tab, button { cursor:pointer; }
.login-screen button { padding:12px; background:var(--gold); color:#000; border:none; border-radius:8px; font-weight:700; }
.error { color:#e06; font-size:.85rem; text-align:center; }
header { display:flex; align-items:center; gap:20px; padding:14px 22px; border-bottom:1px solid #222; }
.brand-sm { font-size:1.3rem; }
nav { display:flex; gap:6px; flex:1; }
.tab { background:transparent; border:none; color:var(--muted); padding:8px 14px; border-radius:6px; font-size:.95rem; }
.tab.active { color:var(--gold); background:#1d1a10; }
.user-box { color:var(--muted); font-size:.85rem; }
.user-box a { color:var(--gold); cursor:pointer; }
main { padding:24px; max-width:1100px; margin:0 auto; }
.card { background:var(--panel); border:1px solid #222; border-radius:12px; padding:18px; margin-bottom:14px; }
.card h3 { margin:0 0 8px; }
.card .meta { color:var(--muted); font-size:.8rem; }
.briefing-hero { border-left:3px solid var(--gold); }
.kw-tag { display:inline-block; background:#1d1a10; color:var(--gold); padding:4px 10px; border-radius:20px; margin:3px; }
.kw-tag button { background:none; border:none; color:#e06; margin-left:6px; }
.row { display:flex; gap:8px; margin:8px 0; flex-wrap:wrap; }
input, select { background:var(--panel); border:1px solid #333; color:var(--text); padding:8px; border-radius:6px; }
.gold-btn { background:var(--gold); color:#000; border:none; padding:8px 14px; border-radius:6px; font-weight:700; }
table { width:100%; border-collapse:collapse; }
td, th { border-bottom:1px solid #222; padding:8px; text-align:left; font-size:.9rem; }
```

- [ ] **Step 3: app.js 작성 (인증 + 탭 라우팅)**

`api/static/app.js`:
```javascript
const API = "";
let TOKEN = localStorage.getItem("sb_token") || "";
let IS_ADMIN = localStorage.getItem("sb_admin") === "1";

function authHeaders() { return { "Content-Type": "application/json", "Authorization": "Bearer " + TOKEN }; }

async function api(path, opts = {}) {
  const r = await fetch(API + path, { headers: authHeaders(), ...opts });
  if (r.status === 401 || r.status === 403) { logout(); throw new Error("auth"); }
  return r.json();
}

async function doLogin() {
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
  if (!r.ok) { document.getElementById("login-error").textContent = "로그인 실패"; return; }
  const d = await r.json();
  TOKEN = d.token; IS_ADMIN = d.is_admin;
  localStorage.setItem("sb_token", TOKEN); localStorage.setItem("sb_admin", IS_ADMIN ? "1" : "0");
  localStorage.setItem("sb_name", d.name);
  showDash(d.name);
}

function logout() { localStorage.clear(); TOKEN = ""; location.reload(); }

function showDash(name) {
  document.getElementById("login").classList.add("hidden");
  document.getElementById("dash").classList.remove("hidden");
  document.getElementById("who").textContent = name || "";
  if (IS_ADMIN) document.querySelector(".admin-only").classList.remove("hidden");
  switchTab("briefing");
}

function switchTab(tab) {
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  RENDER[tab]();
}

document.addEventListener("click", e => {
  if (e.target.classList.contains("tab")) switchTab(e.target.dataset.tab);
});

const RENDER = {}; // 탭별 렌더 함수는 Task 12에서 채운다

window.addEventListener("load", async () => {
  const magic = new URLSearchParams(location.search).get("magic");
  if (magic) {
    const r = await fetch("/api/login/telegram/consume?token=" + encodeURIComponent(magic));
    if (r.ok) {
      const d = await r.json();
      TOKEN = d.token; IS_ADMIN = d.is_admin;
      localStorage.setItem("sb_token", TOKEN);
      localStorage.setItem("sb_admin", IS_ADMIN ? "1" : "0");
      localStorage.setItem("sb_name", d.name);
      history.replaceState({}, "", "/");
      showDash(d.name);
      return;
    }
  }
  if (TOKEN) showDash(localStorage.getItem("sb_name") || "");
});
```

- [ ] **Step 4: 수동 확인 (배포 후 Task 14에서 통합 검증)**

이 단계는 정적 파일 작성만이며 서버 기동(Task 14) 후 브라우저로 확인한다. 지금은 파일 존재만 확인:
Run(로컬): 세 파일이 `api/static/`에 생성되었는지 확인.

- [ ] **Step 5: 커밋**

```bash
git add api/static/index.html api/static/style.css api/static/app.js
git commit -m "feat(dash): 프론트 셸·검정골드 스타일·로그인·탭 라우팅"
```

---

## Task 12: 프론트 — 탭 렌더링 (브리핑·피드·통계·설정·관리자)

**Files:**
- Modify: `api/static/app.js` (RENDER 함수 채우기)

**Interfaces:**
- Consumes: `/api/briefing`, `/api/feed`, `/api/stats`, `/api/settings*`, `/api/admin/users`
- Produces: 각 탭 화면 렌더링

- [ ] **Step 1: app.js의 `const RENDER = {};` 줄을 아래로 교체**

```javascript
const RENDER = {
  async briefing() {
    const v = document.getElementById("view");
    v.innerHTML = `<div class="card briefing-hero"><h3>🏠 오늘의 브리핑</h3>
      <button class="gold-btn" onclick="RENDER.briefing(true)">다시 생성</button>
      <p id="brief-body" class="meta">불러오는 중…</p></div>`;
    const force = arguments[0] === true;
    const d = await api("/api/briefing" + (force ? "?force=true" : ""));
    document.getElementById("brief-body").textContent = d.briefing;
  },

  async feed() {
    const v = document.getElementById("view");
    v.innerHTML = `<div class="row">
      <select id="cat" onchange="RENDER.feed()">
        <option value="">전체</option><option value="news">뉴스</option>
        <option value="reports">리포트</option><option value="youtube">유튜브</option>
        <option value="telegram">텔레</option><option value="blog">블로그</option>
      </select></div><div id="feed-list">불러오는 중…</div>`;
    const cat = document.getElementById("cat") ? document.getElementById("cat").value : "";
    const d = await api("/api/feed" + (cat ? "?category=" + cat : ""));
    document.getElementById("feed-list").innerHTML = d.items.length
      ? d.items.map(it => `<div class="card"><h3>${esc(it.title)}</h3>
          <div class="meta">${esc(it.category)} · ${esc(it.source)} · ${esc(it.date)}</div>
          <p>${esc(it.summary).slice(0, 300)}</p>
          ${it.url ? `<a class="kw-tag" href="${esc(it.url)}" target="_blank">원문</a>` : ""}</div>`).join("")
      : `<p class="meta">표시할 콘텐츠가 없습니다.</p>`;
  },

  async stats() {
    const v = document.getElementById("view");
    v.innerHTML = `<div class="card"><h3>📊 키워드 빈도</h3><canvas id="kwc" height="120"></canvas></div>
      <div class="card"><h3>일자별 수집량</h3><canvas id="cc" height="120"></canvas></div>`;
    const d = await api("/api/stats?days=7");
    const kw = d.keyword_freq;
    new Chart(document.getElementById("kwc"), { type: "bar",
      data: { labels: kw.map(x => x[0]), datasets: [{ data: kw.map(x => x[1]), backgroundColor: "#c8a24a" }] },
      options: { plugins: { legend: { display: false } } } });
    const days = Object.keys(d.counts).sort();
    const totals = days.map(dd => Object.values(d.counts[dd]).reduce((a, b) => a + b, 0));
    new Chart(document.getElementById("cc"), { type: "line",
      data: { labels: days, datasets: [{ data: totals, borderColor: "#c8a24a" }] },
      options: { plugins: { legend: { display: false } } } });
  },

  async settings() {
    const v = document.getElementById("view");
    const s = await api("/api/settings");
    const tags = s.keywords.map(k => `<span class="kw-tag">${esc(k)}<button onclick="delKw('${esc(k)}')">✕</button></span>`).join("");
    v.innerHTML = `<div class="card"><h3>🔑 키워드</h3><div>${tags}</div>
      <div class="row"><input id="newkw" placeholder="키워드 추가"/><button class="gold-btn" onclick="addKw()">추가</button></div></div>
      <div class="card"><h3>🔔 수신 설정</h3>${["news","report","youtube","telegram","blog","market"].map(f =>
        `<label class="row"><input type="checkbox" ${s.receive[f] ? "checked" : ""} onchange="setRecv('${f}',this.checked)"/> ${f}</label>`).join("")}</div>`;
  },

  async admin() {
    const v = document.getElementById("view");
    const d = await api("/api/admin/users");
    v.innerHTML = `<div class="card"><h3>👑 구독자</h3>
      <table><tr><th>이름</th><th>아이디</th><th>만료일</th><th>관리자</th></tr>
      ${d.users.map(u => `<tr><td>${esc(u.name)}</td><td>${esc(u.username || "")}</td><td>${esc(u.expires_at || "무기한")}</td><td>${u.is_admin ? "✓" : ""}</td></tr>`).join("")}
      </table></div>`;
  },
};

function esc(s) { return (s || "").toString().replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
async function addKw() { const k = document.getElementById("newkw").value.trim(); if (!k) return; await api("/api/settings/keyword", { method: "POST", body: JSON.stringify({ keyword: k }) }); RENDER.settings(); }
async function delKw(k) { await api("/api/settings/keyword", { method: "DELETE", body: JSON.stringify({ keyword: k }) }); RENDER.settings(); }
async function setRecv(field, value) { await api("/api/settings/receive", { method: "POST", body: JSON.stringify({ field, value }) }); }
```
(이름 저장 `localStorage.setItem("sb_name", d.name)`은 Task 11의 `doLogin`·매직링크 핸들러에 이미 포함됨.)

- [ ] **Step 2: 커밋**

```bash
git add api/static/app.js
git commit -m "feat(dash): 탭 렌더링(브리핑·피드·통계·설정·관리자)"
```

---

## Task 13: 서버 배포 (systemd) + 통합 스모크 테스트

**Files:**
- Create: `deploy/stockbrain-dash.service` (로컬 작성 후 서버 업로드)
- Modify: `.env` (서버, `DASHBOARD_JWT_SECRET` 추가)

**Interfaces:**
- Produces: `:8080`에서 상시 구동되는 대시보드, 재부팅 자동 시작

- [ ] **Step 1: JWT 시크릿 생성·추가 (서버)**

Run:
```
ssh -i "...pem" ubuntu@3.39.179.148 "cd ~/kmong/crawling_bot && grep -q DASHBOARD_JWT_SECRET .env || echo \"DASHBOARD_JWT_SECRET=$(python3 -c 'import secrets;print(secrets.token_hex(32))')\" >> .env && grep DASHBOARD_JWT_SECRET .env | cut -d= -f1"
```
Expected: `DASHBOARD_JWT_SECRET`

- [ ] **Step 2: 전체 테스트 통과 확인 (서버)**

Run: `cd ~/kmong/crawling_bot && python3 -m pytest tests/ -v`
Expected: 모든 테스트 PASS

- [ ] **Step 3: 수동 기동 + 헬스체크**

Run:
```
ssh -i "...pem" ubuntu@3.39.179.148 "cd ~/kmong/crawling_bot && (nohup python3 -c 'from api.dashboard_server import start; start()' > /tmp/dash.log 2>&1 &) && sleep 4 && curl -s localhost:8080/health"
```
Expected: `{"status":"ok"}`

- [ ] **Step 4: 관리자 계정 1개 생성 (본인) + 로그인 확인**

로컬 스크립트 `make_admin.py` 작성 후 scp 실행:
```python
import sys; sys.path.insert(0, "/home/ubuntu/kmong/crawling_bot")
from api import user_store, dash_store, dash_auth
u = user_store.get_user_by_name("빅팜")  # 기존 유저 재사용
dash_store.set_credentials(u["id"], "admin", dash_auth.hash_password("CHANGE_ME"))
dash_store.set_admin(u["id"], True)
print("admin ready: id=admin")
```
Run: scp 후 `python3 /tmp/make_admin.py`, 그다음
```
curl -s -X POST localhost:8080/api/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"CHANGE_ME"}'
```
Expected: `{"token":"...","name":"빅팜","is_admin":true}`

- [ ] **Step 5: Lightsail 방화벽 8080 개방 확인 + 브라우저 접속**

`http://3.39.179.148:8080` 접속 → 로그인 → 4개 탭 + 관리자 탭 동작 육안 확인. (Lightsail 콘솔에서 8080 TCP 인바운드 규칙 추가 필요)

- [ ] **Step 6: systemd 서비스 등록**

`deploy/stockbrain-dash.service`:
```ini
[Unit]
Description=StockBrain Dashboard (:8080)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/kmong/crawling_bot
ExecStart=/usr/bin/python3 -c "from api.dashboard_server import start; start()"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Run:
```
scp -i "...pem" deploy/stockbrain-dash.service ubuntu@3.39.179.148:/tmp/
ssh -i "...pem" ubuntu@3.39.179.148 "sudo mv /tmp/stockbrain-dash.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now stockbrain-dash && sleep 4 && systemctl is-active stockbrain-dash && curl -s localhost:8080/health"
```
Expected: `active` + `{"status":"ok"}`
주의: Step 3에서 수동 기동한 프로세스가 8080을 점유 중이면 먼저 종료(`pkill -f dashboard_server`)한 뒤 서비스 기동.

- [ ] **Step 7: 커밋**

```bash
git add deploy/stockbrain-dash.service
git commit -m "feat(dash): systemd 서비스 등록 + 배포 스모크 테스트"
```

---

## 실행 후 검증 (전체 격리 테스트)

- 구독자 2명(서로 다른 키워드)을 만들고 각자 로그인 → `/api/feed`가 본인 키워드 콘텐츠만 반환하는지 확인.
- 일반 유저 토큰으로 `/api/admin/users` 호출 시 403.
- 구독 만료일을 과거로 설정 후 로그인 차단(403) 확인.
- 브리핑 같은 날 두 번 호출 시 두 번째가 캐시 즉시 반환(로그·응답속도)인지 확인.
