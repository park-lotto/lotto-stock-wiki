# 인스타 수집 Playwright 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 인스타 레퍼런스 수집을 Apify에서 Playwright + 주거용 프록시로 갈아끼워, 403 실패와 28~50분 소요를 없애고 진행률을 화면에 노출한다.

**Architecture:** 새 모듈 `instagram_playwright.py`가 기존 `apify_client.fetch_reels(usernames)`와 **동일한 시그니처·동일한 10키 계약**을 제공한다. `service.py`는 config 플래그로 둘 중 하나를 고른다(즉시 롤백 가능). 스크레이핑은 DOM 파싱이 아니라 Playwright 네트워크 응답 가로채기로 인스타 자체 JSON을 받는다. 수집 중 채널마다 job의 `result_json`에 부분 진행률을 써서 폴링 화면에 노출한다.

**Tech Stack:** Python 3.12, Playwright(Chromium), FastAPI, SQLite, pytest

## Global Constraints

- **10키 계약 불변**: 스크레이퍼가 돌려주는 dict는 반드시 `shortcode, url, timestamp, caption, commentsCount, likesCount, videoViewCount, displayUrl, videoUrl, ownerUsername` 키를 갖는다. 이 계약은 `apify_client._normalize_apidojo_item`(`shopping_shorts/apify_client.py:190-207`)이 이미 확정한 것이며, 하류(`ranking.build_items` → `apply_grades` → `save_last_run` → 화면)를 무변경으로 유지하는 유일한 조건이다.
- **`timestamp` 필수**: 값이 없으면 `ranking.py:32-34`의 `age_hours` 계산이 실패해 항목이 통째로 드롭된다. ISO8601 문자열(예: `2026-07-27T10:11:12.000Z`).
- **숫자 키는 int**: `commentsCount, likesCount, videoViewCount`는 `int`. 값이 없으면 `0`.
- **문자열 키는 빈 문자열 폴백**: `url, caption, displayUrl, videoUrl`은 없으면 `""`(None 금지).
- **기본값은 Apify**: `INSTAGRAM_SCRAPER` 기본값은 `"apify"`. Playwright는 명시적으로 켤 때만 돈다. Apify 코드는 삭제하지 않는다.
- **Apify 경로 회귀 0**: 기존 `apify_client.py`의 함수 시그니처·동작을 바꾸지 않는다.
- **채널당 릴스 수·기간은 기존 상수 사용**: `RESULTS_PER_CHANNEL = 3`, `ONLY_NEWER_THAN = "2 days"` (`shopping_shorts/config.py:126-127`).
- **트랙 폴더에서만 작업**: 모든 경로는 `C:\Users\TheRose\Desktop\로또의 주식\.tracks\AI픽자동적재\` 기준. main 폴더의 코드 파일은 건드리지 않는다.
- **테스트는 네트워크 없이 통과해야 한다**: Playwright 실브라우저를 띄우는 테스트는 만들지 않는다. 파서는 순수 함수로 분리해 fixture로 검증한다.

---

### Task 1: 파서 — 인스타 JSON 응답을 10키 계약으로 정규화

인스타 응답 파싱을 **네트워크·브라우저와 완전히 분리된 순수 함수**로 먼저 만든다. 이 함수만 테스트로 고정해두면, 나중에 인스타가 응답 스키마를 바꿔도 여기서 먼저 깨져서 원인이 즉시 드러난다.

**Files:**
- Create: `shopping_shorts/instagram_parse.py`
- Test: `shopping_shorts/tests/test_instagram_parse.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `parse_reel_node(node: dict, username: str) -> dict | None` — 릴스 노드 1개 → 10키 dict. `shortcode`를 못 찾으면 `None`.
  - `extract_reel_nodes(payload: dict) -> list[dict]` — 인스타 응답 전체 → 릴스 노드 리스트. 못 찾으면 `[]`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`shopping_shorts/tests/test_instagram_parse.py`:

```python
"""인스타 JSON 응답 → 10키 계약 정규화(네트워크 없음).

이 계약은 apify_client._normalize_apidojo_item(apify_client.py:190-207)이 확정한 것이다.
Playwright 경로가 같은 키를 못 채우면 ranking.build_items 이후가 통째로 깨진다.
특히 timestamp가 없으면 age_hours 계산이 실패해 항목이 드롭된다(ranking.py:32-34).
"""
from shopping_shorts.instagram_parse import extract_reel_nodes, parse_reel_node

# 인스타 응답에서 실제로 관찰되는 모양(중첩·별칭 포함)을 축약한 것.
_NODE = {
    "code": "DbMmu39Sph9",
    "taken_at": 1769500000,
    "caption": {"text": "다이소 이거 꼭 사세요"},
    "comment_count": 3388,
    "like_count": 12045,
    "play_count": 508549,
    "image_versions2": {"candidates": [{"url": "https://cdn/thumb.jpg", "width": 640}]},
    "video_versions": [{"url": "https://cdn/video.mp4", "width": 720}],
}


def test_parse_reel_node_fills_all_ten_keys():
    d = parse_reel_node(_NODE, "homeinon")
    assert set(d) == {
        "shortcode", "url", "timestamp", "caption", "commentsCount",
        "likesCount", "videoViewCount", "displayUrl", "videoUrl", "ownerUsername",
    }
    assert d["shortcode"] == "DbMmu39Sph9"
    assert d["url"] == "https://www.instagram.com/reel/DbMmu39Sph9/"
    assert d["caption"] == "다이소 이거 꼭 사세요"
    assert d["commentsCount"] == 3388
    assert d["likesCount"] == 12045
    assert d["videoViewCount"] == 508549
    assert d["displayUrl"] == "https://cdn/thumb.jpg"
    assert d["videoUrl"] == "https://cdn/video.mp4"
    assert d["ownerUsername"] == "homeinon"


def test_parse_reel_node_timestamp_is_iso_utc():
    """★timestamp 없으면 항목이 드롭된다(ranking.py:32-34) — unix초를 ISO로."""
    d = parse_reel_node(_NODE, "homeinon")
    assert d["timestamp"].startswith("2026-")
    assert d["timestamp"].endswith("Z")


def test_parse_reel_node_missing_numbers_become_zero():
    d = parse_reel_node({"code": "X1", "taken_at": 1769500000}, "u")
    assert d["commentsCount"] == 0
    assert d["likesCount"] == 0
    assert d["videoViewCount"] == 0


def test_parse_reel_node_missing_strings_become_empty_not_none():
    d = parse_reel_node({"code": "X1", "taken_at": 1769500000}, "u")
    for k in ("caption", "displayUrl", "videoUrl"):
        assert d[k] == "", f"{k}가 None이면 하류에서 터진다"


def test_parse_reel_node_without_shortcode_returns_none():
    assert parse_reel_node({"taken_at": 1769500000}, "u") is None


def test_parse_reel_node_accepts_plain_caption_string():
    """caption이 dict가 아니라 문자열로 오는 응답도 있다."""
    d = parse_reel_node({"code": "X1", "taken_at": 1, "caption": "그냥 문자열"}, "u")
    assert d["caption"] == "그냥 문자열"


def test_extract_reel_nodes_from_items_shape():
    payload = {"items": [_NODE, {"code": "B2", "taken_at": 1769500001}]}
    assert [n["code"] for n in extract_reel_nodes(payload)] == ["DbMmu39Sph9", "B2"]


def test_extract_reel_nodes_from_media_wrapper_shape():
    """항목이 {"media": {...}}로 한 겹 싸여 오는 응답 모양."""
    payload = {"items": [{"media": _NODE}]}
    assert [n["code"] for n in extract_reel_nodes(payload)] == ["DbMmu39Sph9"]


def test_extract_reel_nodes_unknown_shape_returns_empty():
    assert extract_reel_nodes({"data": {"something_else": 1}}) == []
    assert extract_reel_nodes({}) == []
```

- [ ] **Step 2: 실패하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_instagram_parse.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'shopping_shorts.instagram_parse'`

- [ ] **Step 3: 파서를 구현한다**

`shopping_shorts/instagram_parse.py`:

```python
"""인스타 응답 JSON → 수집 표준 스키마(10키) 정규화. **순수 함수만** — 네트워크·브라우저 없음.

왜 따로 두나: 스크레이핑에서 제일 자주 깨지는 곳이 응답 파싱인데, 브라우저와 얽혀 있으면
실패 원인이 "인스타가 막았나 / 파싱이 틀렸나"로 뒤섞여 진단이 안 된다. 파서를 순수 함수로
떼어 fixture로 고정해두면 스키마 변경이 테스트에서 먼저 드러난다.

계약은 apify_client._normalize_apidojo_item(apify_client.py:190-207)이 확정한 10키다 —
이것만 지키면 ranking/화면/DB가 전부 무변경이다.
"""
from datetime import datetime, timezone

_TEN_KEYS_NUM = ("commentsCount", "likesCount", "videoViewCount")


def _first(d, *names, default=None):
    """여러 후보 키 중 먼저 존재하는 값. 인스타는 같은 값을 여러 이름으로 준다."""
    for n in names:
        if isinstance(d, dict) and d.get(n) is not None:
            return d[n]
    return default


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _iso(ts):
    """unix초(또는 이미 ISO 문자열) → ISO8601 UTC 문자열.

    ★비어 있으면 안 된다 — ranking.py:32-34가 age_hours를 못 구해 항목을 드롭한다."""
    if not ts:
        return ""
    if isinstance(ts, str):
        return ts
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _caption_text(node):
    """caption은 {"text": ...} 또는 문자열로 온다(응답 종류에 따라 다름)."""
    cap = _first(node, "caption", "edge_media_to_caption", default="")
    if isinstance(cap, dict):
        return cap.get("text") or ""
    if isinstance(cap, str):
        return cap
    return ""


def _best_image(node):
    iv = _first(node, "image_versions2", "image_versions", default={}) or {}
    cands = iv.get("candidates") if isinstance(iv, dict) else None
    if isinstance(cands, list) and cands:
        return cands[0].get("url") or ""
    return _first(node, "display_url", "thumbnail_url", default="") or ""


def _best_video(node):
    vv = _first(node, "video_versions", default=[]) or []
    if isinstance(vv, list) and vv:
        return vv[0].get("url") or ""
    return _first(node, "video_url", default="") or ""


def parse_reel_node(node, username):
    """릴스 노드 1개 → 10키 dict. shortcode를 못 찾으면 None(호출부가 건너뛴다)."""
    if not isinstance(node, dict):
        return None
    code = _first(node, "code", "shortcode", default="")
    if not code:
        return None
    return {
        "shortcode": code,
        "url": f"https://www.instagram.com/reel/{code}/",
        "timestamp": _iso(_first(node, "taken_at", "taken_at_timestamp", "device_timestamp")),
        "caption": _caption_text(node),
        "commentsCount": _int(_first(node, "comment_count", "commentCount", default=0)),
        "likesCount": _int(_first(node, "like_count", "likeCount", default=0)),
        "videoViewCount": _int(_first(node, "play_count", "view_count", "playCount", default=0)),
        "displayUrl": _best_image(node),
        "videoUrl": _best_video(node),
        "ownerUsername": username,
    }


def extract_reel_nodes(payload):
    """인스타 응답 → 릴스 노드 리스트. 모르는 모양이면 []."""
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # 항목이 {"media": {...}}로 한 겹 싸여 오는 응답 모양이 있다.
        node = it.get("media") if isinstance(it.get("media"), dict) else it
        out.append(node)
    return out
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_instagram_parse.py -q`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add shopping_shorts/instagram_parse.py shopping_shorts/tests/test_instagram_parse.py
git commit -m "feat(수집): 인스타 응답 파서 — 10키 계약 정규화(순수 함수)"
```

---

### Task 2: config — 스크레이퍼 선택 플래그와 인스타 프록시

라이브가 인스타 수집에 묶여 있으므로, 코드를 넣기 전에 **되돌릴 스위치부터** 만든다.

**Files:**
- Modify: `shopping_shorts/config.py` (Apify 블록 뒤, 대략 `APIFY_ACTOR` 정의 아래)
- Test: `shopping_shorts/tests/test_config_instagram_scraper.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `config.INSTAGRAM_SCRAPER: str` — `"apify"`(기본) 또는 `"playwright"`
  - `config.INSTAGRAM_PROXY: str` — `http://user:pass@host:port` 형식, 미설정 시 `""`
  - `config.INSTAGRAM_PW_CONTEXTS: int` — 동시 컨텍스트 수, 기본 5
  - `config.INSTAGRAM_PW_TIMEOUT_MS: int` — 채널 1개 처리 상한(ms), 기본 20000

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`shopping_shorts/tests/test_config_instagram_scraper.py`:

```python
"""인스타 스크레이퍼 선택 플래그 — 기본값이 apify여야 한다(라이브 안전).

★기본값이 playwright면, 이 브랜치가 병합되는 순간 검증도 안 된 새 경로로
라이브 수집이 통째로 넘어간다. 전환은 서버 환경변수로 명시적으로만 한다.
"""
import importlib


def test_default_scraper_is_apify(monkeypatch):
    monkeypatch.delenv("INSTAGRAM_SCRAPER", raising=False)
    from shopping_shorts import config
    importlib.reload(config)
    assert config.INSTAGRAM_SCRAPER == "apify"


def test_scraper_switchable_by_env(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_SCRAPER", "playwright")
    from shopping_shorts import config
    importlib.reload(config)
    assert config.INSTAGRAM_SCRAPER == "playwright"
    monkeypatch.delenv("INSTAGRAM_SCRAPER", raising=False)
    importlib.reload(config)


def test_proxy_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("INSTAGRAM_PROXY", raising=False)
    from shopping_shorts import config
    importlib.reload(config)
    assert config.INSTAGRAM_PROXY == ""


def test_context_and_timeout_defaults():
    from shopping_shorts import config
    assert config.INSTAGRAM_PW_CONTEXTS == 5
    assert config.INSTAGRAM_PW_TIMEOUT_MS == 20000
```

- [ ] **Step 2: 실패하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_config_instagram_scraper.py -q`
Expected: FAIL — `AttributeError: module 'shopping_shorts.config' has no attribute 'INSTAGRAM_SCRAPER'`

- [ ] **Step 3: config에 추가한다**

`shopping_shorts/config.py`의 `APIFY_ACTOR = "apify~instagram-reel-scraper"  # actor id (~ 형식)` 줄 **바로 아래**에 삽입:

```python
# ── 인스타 수집 경로 선택(2026-07-28) ──
# Apify는 성공해도 28분이 걸리고 403 Forbidden으로 통째로 죽는 사례가 이틀 새 2건이었다
# (서버 collect_jobs 실측). Playwright + 주거용 프록시로 대체하되, 라이브 대시보드가
# 인스타 수집에 묶여 있으므로 **환경변수 하나로 즉시 되돌릴 수 있게** 둔다.
# ★기본값은 apify다 — 검증 전 병합만으로 라이브 경로가 바뀌면 안 된다.
INSTAGRAM_SCRAPER = os.getenv("INSTAGRAM_SCRAPER", "apify")   # apify | playwright

# 인스타 전용 주거용 프록시(형식은 REDDIT_PROXY와 동일: http://user:pass@host:port).
# 서버 데이터센터 IP로 직접 긁으면 인스타가 막는다 — Reddit이 429로 막혔던 것과 같은 이유.
# 미설정이면 직결(로컬 개발용).
INSTAGRAM_PROXY = os.getenv("INSTAGRAM_PROXY", "")

# 동시에 여는 브라우저 컨텍스트 수. 크로미움은 메모리를 먹으므로 서버 여유를 보고 조정한다.
INSTAGRAM_PW_CONTEXTS = int(os.getenv("INSTAGRAM_PW_CONTEXTS", "5"))
# 채널 1개 처리 상한(ms). 넘으면 그 채널만 error로 접고 다음으로 간다(전체가 죽지 않게).
INSTAGRAM_PW_TIMEOUT_MS = int(os.getenv("INSTAGRAM_PW_TIMEOUT_MS", "20000"))
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_config_instagram_scraper.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add shopping_shorts/config.py shopping_shorts/tests/test_config_instagram_scraper.py
git commit -m "feat(수집): INSTAGRAM_SCRAPER 플래그 + 인스타 프록시 설정(기본 apify 유지)"
```

---

### Task 3: 채널 결과 분류 — 성공/로그인벽/없음/오류

**차단 비율을 숫자로 남기는 것**이 이번 작업의 핵심 산출물 중 하나다(부계정 도입 여부 판단 근거). 분류 로직도 순수 함수로 분리해 브라우저 없이 테스트한다.

**Files:**
- Modify: `shopping_shorts/instagram_parse.py`
- Modify: `shopping_shorts/tests/test_instagram_parse.py`

**Interfaces:**
- Consumes: Task 1의 `shopping_shorts/instagram_parse.py`
- Produces:
  - `classify_channel_result(nodes: list, page_url: str, error: str | None) -> str` — `"ok" | "login_wall" | "not_found" | "error"` 중 하나

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`shopping_shorts/tests/test_instagram_parse.py` **끝에 추가**:

```python
from shopping_shorts.instagram_parse import classify_channel_result


def test_classify_ok_when_nodes_found():
    assert classify_channel_result([{"code": "A"}], "https://www.instagram.com/u/reels/", None) == "ok"


def test_classify_login_wall_by_redirect():
    """인스타가 막으면 /accounts/login/ 으로 튕긴다 — 이게 부계정 필요 신호다."""
    assert classify_channel_result(
        [], "https://www.instagram.com/accounts/login/?next=/u/reels/", None) == "login_wall"


def test_classify_error_takes_priority_over_empty():
    assert classify_channel_result([], "https://www.instagram.com/u/reels/", "Timeout") == "error"


def test_classify_not_found_when_empty_without_error():
    """비공개·삭제 계정 — 로그인벽과 구분해야 한다(부계정을 붙여도 안 되는 쪽)."""
    assert classify_channel_result([], "https://www.instagram.com/u/reels/", None) == "not_found"
```

- [ ] **Step 2: 실패하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_instagram_parse.py -q`
Expected: FAIL — `ImportError: cannot import name 'classify_channel_result'`

- [ ] **Step 3: 분류 함수를 구현한다**

`shopping_shorts/instagram_parse.py` **끝에 추가**:

```python
def classify_channel_result(nodes, page_url, error):
    """채널 1개의 수집 결과를 4가지로 분류한다.

    왜 나누나: "실패 30건"만으로는 부계정(로그인 세션)이 필요한지 알 수 없다.
    로그인벽이면 부계정으로 뚫리고, 비공개·삭제면 부계정으로도 안 된다.
    이 분류의 집계가 B안 도입 판단의 근거다(설계문서 참조).
    """
    if error:
        return "error"
    if nodes:
        return "ok"
    if "/accounts/login" in (page_url or ""):
        return "login_wall"
    return "not_found"
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_instagram_parse.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: 커밋**

```bash
git add shopping_shorts/instagram_parse.py shopping_shorts/tests/test_instagram_parse.py
git commit -m "feat(수집): 채널 결과 4분류(ok/login_wall/not_found/error) — 부계정 판단 근거"
```

---

### Task 4: Playwright 스크레이퍼 — fetch_reels 동일 계약

브라우저를 실제로 다루는 유일한 모듈. 여기는 **실브라우저 테스트를 만들지 않는다**(CI에서 못 돌고 인스타에 의존). 대신 파서·분류는 Task 1·3에서 이미 고정했고, 여기서는 **진행률 콜백과 결과 합산 로직**만 가짜 스크레이퍼로 검증한다.

**Files:**
- Create: `shopping_shorts/instagram_playwright.py`
- Test: `shopping_shorts/tests/test_instagram_playwright.py`

**Interfaces:**
- Consumes: Task 1·3의 `instagram_parse.parse_reel_node`, `extract_reel_nodes`, `classify_channel_result`; Task 2의 config 값
- Produces:
  - `fetch_reels(usernames: list[str], on_progress=None, _scrape_one=None) -> list[dict]` — `apify_client.fetch_reels`와 동일 계약(10키 dict 리스트)
  - `on_progress(done: int, total: int, items_so_far: int, tally: dict) -> None` — 채널 1개 끝날 때마다 호출. `tally`는 `{"ok": n, "login_wall": n, "not_found": n, "error": n}`
  - `LAST_TALLY: dict` — 마지막 실행의 분류 집계(호출부가 job 결과에 담는다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`shopping_shorts/tests/test_instagram_playwright.py`:

```python
"""Playwright 스크레이퍼의 오케스트레이션(진행률·집계·실패격리) 검증.

★실브라우저는 띄우지 않는다 — _scrape_one을 주입해 대체한다. 브라우저를 띄우면
테스트가 인스타 상태에 좌우돼 회귀 신호로 못 쓴다. 파싱은 test_instagram_parse가,
브라우저 동작은 서버 실측(10채널 게이트)이 각각 맡는다.
"""
from shopping_shorts import instagram_playwright as ipw


def _fake_ok(username):
    """(nodes, page_url, error) — 스크레이퍼 1채널 반환 계약."""
    return ([{"code": f"C_{username}", "taken_at": 1769500000}],
            f"https://www.instagram.com/{username}/reels/", None)


def _fake_login_wall(username):
    return ([], "https://www.instagram.com/accounts/login/?next=/x/", None)


def _fake_error(username):
    return ([], f"https://www.instagram.com/{username}/reels/", "Timeout 20000ms")


def test_fetch_reels_returns_ten_key_items():
    items = ipw.fetch_reels(["homeinon"], _scrape_one=_fake_ok)
    assert len(items) == 1
    assert set(items[0]) == {
        "shortcode", "url", "timestamp", "caption", "commentsCount",
        "likesCount", "videoViewCount", "displayUrl", "videoUrl", "ownerUsername",
    }
    assert items[0]["ownerUsername"] == "homeinon"


def test_one_channel_failure_does_not_kill_the_run():
    """★Apify 403이 전체를 죽이던 문제의 재발 방지 — 한 채널이 죽어도 나머지는 온다."""
    def _mixed(u):
        return _fake_error(u) if u == "bad" else _fake_ok(u)

    items = ipw.fetch_reels(["good1", "bad", "good2"], _scrape_one=_mixed)
    assert sorted(i["ownerUsername"] for i in items) == ["good1", "good2"]


def test_progress_callback_reports_every_channel():
    """★50분간 아무 표시가 없어 사장님이 취소했다 — 채널마다 진행률이 나가야 한다."""
    seen = []
    ipw.fetch_reels(["a", "b", "c"], on_progress=lambda *a: seen.append(a), _scrape_one=_fake_ok)
    assert len(seen) == 3
    done, total, items_so_far, tally = seen[-1]
    assert (done, total, items_so_far) == (3, 3, 3)
    assert tally["ok"] == 3


def test_tally_counts_each_classification():
    def _mixed(u):
        return {"w": _fake_login_wall, "e": _fake_error}.get(u, _fake_ok)(u)

    ipw.fetch_reels(["a", "w", "e"], _scrape_one=_mixed)
    assert ipw.LAST_TALLY["ok"] == 1
    assert ipw.LAST_TALLY["login_wall"] == 1
    assert ipw.LAST_TALLY["error"] == 1


def test_username_at_prefix_is_stripped():
    items = ipw.fetch_reels(["@homeinon"], _scrape_one=_fake_ok)
    assert items[0]["ownerUsername"] == "homeinon"


def test_empty_input_returns_empty_without_calling_scraper():
    called = []
    ipw.fetch_reels([], _scrape_one=lambda u: called.append(u) or _fake_ok(u))
    assert called == []
```

- [ ] **Step 2: 실패하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_instagram_playwright.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'shopping_shorts.instagram_playwright'`

- [ ] **Step 3: 스크레이퍼를 구현한다**

`shopping_shorts/instagram_playwright.py`:

```python
"""인스타 릴스 수집 — Playwright + 주거용 프록시(2026-07-28).

apify_client.fetch_reels와 **같은 계약**(10키 dict 리스트)을 돌려준다. 그래서
service.py는 어느 쪽을 쓰든 하류가 무변경이다.

설계 요점:
- DOM을 파싱하지 않는다. page.on("response")로 인스타가 스스로 부르는 JSON을 가로챈다.
  DOM에는 조회수·댓글수가 축약("1.2만")으로만 나오고, 인스타가 마크업을 수시로 바꾼다.
- 채널 하나가 실패해도 전체가 죽지 않는다(Apify 403이 통째로 죽이던 문제).
- 채널마다 on_progress를 부른다 — 50분간 아무 표시가 없어 사장님이 취소한 게 발단이다.

테스트는 _scrape_one을 주입해 브라우저 없이 돈다(test_instagram_playwright.py).
"""
from shopping_shorts import config
from shopping_shorts.instagram_parse import (
    classify_channel_result, extract_reel_nodes, parse_reel_node,
)

# 마지막 실행의 분류 집계 — 호출부(service/app)가 job 결과에 담아 화면·보고에 쓴다.
# ★이 숫자가 부계정(B안) 도입 여부의 판단 근거다.
LAST_TALLY = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}

# 인스타가 릴스 목록을 채울 때 부르는 내부 API 경로 조각. 이 중 하나가 들어간
# 응답만 JSON으로 읽는다(이미지·폰트 등 나머지는 무시).
_REEL_API_HINTS = ("/api/v1/clips/user/", "/api/v1/feed/reels_media", "/graphql")


def _scrape_one_playwright(username):
    """채널 1개 → (nodes, page_url, error). 브라우저를 실제로 띄우는 유일한 함수.

    반환 계약을 (nodes, page_url, error) 세 값으로 고정한 이유: 분류(classify_channel_result)가
    이 세 가지만 있으면 판정할 수 있어, 테스트에서 통째로 대체하기 쉽다.
    """
    from playwright.sync_api import sync_playwright   # 지연 import — 미설치 환경에서 모듈 로드가 죽지 않게

    url = f"https://www.instagram.com/{username}/reels/"
    captured = []
    launch_kw = {"headless": True}
    ctx_kw = {}
    if config.INSTAGRAM_PROXY:
        ctx_kw["proxy"] = {"server": config.INSTAGRAM_PROXY}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kw)
            ctx = browser.new_context(**ctx_kw)
            page = ctx.new_page()

            def _on_response(resp):
                if not any(h in resp.url for h in _REEL_API_HINTS):
                    return
                try:
                    captured.extend(extract_reel_nodes(resp.json()))
                except Exception:      # noqa: BLE001 — JSON이 아니거나 모양이 다르면 그냥 무시
                    pass

            page.on("response", _on_response)
            page.goto(url, timeout=config.INSTAGRAM_PW_TIMEOUT_MS,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(2500)          # 릴스 목록 XHR이 도착할 여유
            final_url = page.url
            ctx.close()
            browser.close()
        return captured, final_url, None
    except Exception as e:                        # noqa: BLE001 — 채널 하나의 실패로 전체가 죽지 않게
        return [], url, str(e)[:200]


def fetch_reels(usernames, on_progress=None, _scrape_one=None):
    """usernames → 10키 reel dict 리스트. apify_client.fetch_reels와 동일 계약.

    on_progress(done, total, items_so_far, tally): 채널 1개 끝날 때마다 호출(선택).
    _scrape_one: 테스트 주입용. 기본은 실제 Playwright 스크레이퍼.
    """
    scrape = _scrape_one or _scrape_one_playwright
    names = [(u or "").strip().lstrip("@") for u in (usernames or [])]
    names = [u for u in names if u]
    total = len(names)
    tally = {"ok": 0, "login_wall": 0, "not_found": 0, "error": 0}
    items = []
    for i, uname in enumerate(names, start=1):
        nodes, page_url, error = scrape(uname)
        verdict = classify_channel_result(nodes, page_url, error)
        tally[verdict] = tally.get(verdict, 0) + 1
        if verdict == "ok":
            for n in nodes[:config.RESULTS_PER_CHANNEL]:
                d = parse_reel_node(n, uname)
                if d:
                    items.append(d)
        if on_progress:
            on_progress(i, total, len(items), dict(tally))
    LAST_TALLY.clear()
    LAST_TALLY.update(tally)
    return items
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_instagram_playwright.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add shopping_shorts/instagram_playwright.py shopping_shorts/tests/test_instagram_playwright.py
git commit -m "feat(수집): Playwright 인스타 스크레이퍼 — 실패격리·진행률·분류집계"
```

---

### Task 5: service 배선 — 플래그로 스크레이퍼 선택 + 진행률 전달

**Files:**
- Modify: `shopping_shorts/service.py:246` (`reels = fetch_reels(usernames)`)
- Modify: `shopping_shorts/service.py:216` (`collect` 시그니처에 `on_progress` 추가)
- Test: `shopping_shorts/tests/test_service_scraper_switch.py`

**Interfaces:**
- Consumes: Task 2의 `config.INSTAGRAM_SCRAPER`; Task 4의 `instagram_playwright.fetch_reels`, `LAST_TALLY`
- Produces:
  - `service.collect(platform="instagram", categories=None, limit_channels=None, on_progress=None) -> list[dict]` — `on_progress`는 인스타+playwright 경로에서만 전달된다
  - `service.LAST_COLLECT_TALLY: dict` — 마지막 인스타 수집의 분류 집계(apify 경로면 빈 dict)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`shopping_shorts/tests/test_service_scraper_switch.py`:

```python
"""collect()가 config 플래그로 스크레이퍼를 고르는지 — 롤백 스위치의 실동작 검증.

★이 스위치가 없으면 새 경로에 문제가 생겼을 때 라이브 인스타 수집을 되돌릴 방법이
코드 revert밖에 없다. 서버 환경변수 하나로 돌아갈 수 있어야 한다.
"""
from shopping_shorts import service


def _stub_channels(monkeypatch, usernames):
    chans = [{"username": u, "name": u, "inpock": "", "followers": 0} for u in usernames]
    monkeypatch.setattr(service, "load_channels", lambda: chans)
    monkeypatch.setattr(service, "select_tracked", lambda c, *a, **k: c)


def test_apify_path_used_by_default(monkeypatch):
    _stub_channels(monkeypatch, ["a"])
    called = {}
    monkeypatch.setattr(service.config, "INSTAGRAM_SCRAPER", "apify")
    monkeypatch.setattr(service, "fetch_reels", lambda u: called.setdefault("apify", u) or [])
    monkeypatch.setattr(service, "_pw_fetch_reels",
                        lambda u, on_progress=None: called.setdefault("pw", u) or [])
    service.collect(platform="instagram")
    assert "apify" in called and "pw" not in called


def test_playwright_path_used_when_flag_set(monkeypatch):
    _stub_channels(monkeypatch, ["a"])
    called = {}
    monkeypatch.setattr(service.config, "INSTAGRAM_SCRAPER", "playwright")
    monkeypatch.setattr(service, "fetch_reels", lambda u: called.setdefault("apify", u) or [])
    monkeypatch.setattr(service, "_pw_fetch_reels",
                        lambda u, on_progress=None: called.setdefault("pw", u) or [])
    service.collect(platform="instagram")
    assert "pw" in called and "apify" not in called


def test_progress_callback_forwarded_to_playwright(monkeypatch):
    _stub_channels(monkeypatch, ["a"])
    got = {}
    monkeypatch.setattr(service.config, "INSTAGRAM_SCRAPER", "playwright")

    def _pw(usernames, on_progress=None):
        got["cb"] = on_progress
        return []
    monkeypatch.setattr(service, "_pw_fetch_reels", _pw)
    marker = lambda *a: None
    service.collect(platform="instagram", on_progress=marker)
    assert got["cb"] is marker
```

- [ ] **Step 2: 실패하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_service_scraper_switch.py -q`
Expected: FAIL — `AttributeError: module 'shopping_shorts.service' has no attribute '_pw_fetch_reels'`

- [ ] **Step 3: service.py를 배선한다**

3-1. `shopping_shorts/service.py` **import 블록에 추가**:

```python
from shopping_shorts import config
from shopping_shorts.instagram_playwright import fetch_reels as _pw_fetch_reels
from shopping_shorts.instagram_playwright import LAST_TALLY as _PW_TALLY
```

3-2. 모듈 최상단(함수 밖)에 추가:

```python
# 마지막 인스타 수집의 채널 분류 집계(app.py가 job 결과에 담는다). apify 경로면 빈 dict.
LAST_COLLECT_TALLY = {}
```

3-3. `def collect(platform="instagram", categories=None, limit_channels=None):`(`service.py:216`)를 다음으로 바꾼다:

```python
def collect(platform="instagram", categories=None, limit_channels=None, on_progress=None):
```

그리고 docstring 끝에 한 줄 추가:

```python
    on_progress(done, total, items_so_far, tally): 인스타+Playwright 경로에서만 채널마다
    호출된다(수집이 도는지 화면에 보여주기 위함). Apify 경로는 진행률을 알 수 없어 무시된다.
```

3-4. `reels = fetch_reels(usernames)  # 전체 채널 릴스 원본`(`service.py:246`)을 다음으로 교체:

```python
    # ── 스크레이퍼 선택(2026-07-28) ──
    # Apify는 성공해도 28분, 403으로 통째로 죽는 사례 2건(서버 collect_jobs 실측).
    # Playwright 경로는 채널별 실패 격리 + 진행률 보고가 된다. 라이브가 이 수집에
    # 묶여 있으므로 환경변수 하나로 즉시 되돌릴 수 있게 분기로 남긴다.
    global LAST_COLLECT_TALLY
    if config.INSTAGRAM_SCRAPER == "playwright":
        reels = _pw_fetch_reels(usernames, on_progress=on_progress)
        LAST_COLLECT_TALLY = dict(_PW_TALLY)
    else:
        reels = fetch_reels(usernames)      # 전체 채널 릴스 원본(Apify)
        LAST_COLLECT_TALLY = {}
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_service_scraper_switch.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: 기존 수집 테스트가 안 깨졌는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/ -q -k "collect or service or ranking"`
Expected: 기존과 동일한 통과/실패 (새로 깨진 항목 0)

- [ ] **Step 6: 커밋**

```bash
git add shopping_shorts/service.py shopping_shorts/tests/test_service_scraper_switch.py
git commit -m "feat(수집): collect가 INSTAGRAM_SCRAPER 플래그로 경로 선택 + 진행률 전달"
```

---

### Task 6: 진행률을 job에 기록 — "37/200 채널" 노출

DB 스키마를 바꾸지 않고 `result_json`에 부분 payload를 써서 폴링 화면에 진행률을 보여준다.

**Files:**
- Modify: `shopping_shorts/app.py:221-232` (`_run_collect_job`)
- Modify: `shopping_shorts/app.py:259` (`_COLLECT_STALE_MIN`)
- Test: `shopping_shorts/tests/test_collect_progress.py`

**Interfaces:**
- Consumes: Task 5의 `service.collect(..., on_progress=...)`, `service.LAST_COLLECT_TALLY`
- Produces: 수집 중 `/api/collect/status/{job_id}` 응답의 `result_json`이 `{"phase": "collecting", "done": int, "total": int, "items_so_far": int, "tally": dict}` 를 담는다. 완료 시엔 기존대로 `{"count", "items", "collected_at"}` + `"tally"`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`shopping_shorts/tests/test_collect_progress.py`:

```python
"""수집 진행률이 job에 기록되는지 — "멈춘 건가?"를 없애는 장치.

★2026-07-27 실사고: 사장님이 50분을 기다리다 취소했다. 서버 collect_jobs를 보니
updated_at이 생성 시각에서 한 번도 안 바뀌어 있었다(진행률을 쓰는 코드가 없었음).
"""
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def test_progress_written_to_job_during_collect(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    store = Store(db)
    store.create_collect_job("J1")

    def _fake_collect(platform=None, categories=None, limit_channels=None, on_progress=None):
        on_progress(1, 3, 2, {"ok": 1, "login_wall": 0, "not_found": 0, "error": 0})
        snap = store.get_collect_job("J1")
        assert snap["status"] == "running"
        import json
        prog = json.loads(snap["result_json"])
        assert prog["phase"] == "collecting"
        assert (prog["done"], prog["total"], prog["items_so_far"]) == (1, 3, 2)
        on_progress(3, 3, 5, {"ok": 3, "login_wall": 0, "not_found": 0, "error": 0})
        return []

    monkeypatch.setattr(app_module, "collect", _fake_collect)
    monkeypatch.setattr(app_module, "_attach_vision_tags", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "generate_missing_drafts", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "next_draft_targets", lambda *a, **k: [])
    monkeypatch.setattr(app_module, "_tag_new_items", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_translate_new_subjects", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_bank_ingest_collected_bg", lambda *a, **k: None)

    app_module._run_collect_job("J1", "instagram", None, None, 0)
    assert store.get_collect_job("J1")["status"] == "done"


def test_tally_included_in_done_payload(monkeypatch, tmp_path):
    """★차단 비율이 결과에 남아야 부계정(B안) 필요 여부를 숫자로 판단할 수 있다."""
    import json
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    store = Store(db)
    store.create_collect_job("J2")

    monkeypatch.setattr(app_module, "collect",
                        lambda **k: [])
    monkeypatch.setattr(app_module.service, "LAST_COLLECT_TALLY",
                        {"ok": 180, "login_wall": 15, "not_found": 3, "error": 2})
    monkeypatch.setattr(app_module, "_attach_vision_tags", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "generate_missing_drafts", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "next_draft_targets", lambda *a, **k: [])
    monkeypatch.setattr(app_module, "_tag_new_items", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_translate_new_subjects", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "_bank_ingest_collected_bg", lambda *a, **k: None)

    app_module._run_collect_job("J2", "instagram", None, None, 0)
    payload = json.loads(store.get_collect_job("J2")["result_json"])
    assert payload["tally"]["login_wall"] == 15
```

- [ ] **Step 2: 실패하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_collect_progress.py -q`
Expected: FAIL — `TypeError: collect() got an unexpected keyword argument 'on_progress'` 또는 `KeyError: 'tally'`

- [ ] **Step 3: `_run_collect_job`을 고친다**

3-1. `shopping_shorts/app.py`의 import에 추가(이미 `from shopping_shorts.service import collect` 형태라면 모듈도 함께):

```python
from shopping_shorts import service
```

3-2. `shopping_shorts/app.py:221-232`의 `_run_collect_job` 앞부분을 다음으로 교체:

```python
def _run_collect_job(job_id, platform, category, limit, cid):
    """background: collect() 실행 → (인스타)last_run 저장 → 결과를 job에 담아 done.
    실패는 민감정보 마스킹 후 error로 기록. 프론트는 status 폴링으로 결과/에러를 받는다.

    ★진행률(2026-07-28): 채널마다 result_json에 부분 payload를 쓴다. 예전엔 아무것도
    안 써서 50분간 화면이 그대로였고 사장님이 "멈췄다"고 판단해 취소했다(실사고).
    스키마 변경 없이 기존 폴링 경로에 그대로 실린다.
    """
    store = Store(DB_PATH)

    def _on_progress(done, total, items_so_far, tally):
        store.update_collect_job(job_id, result={
            "phase": "collecting", "done": done, "total": total,
            "items_so_far": items_so_far, "tally": tally,
        })

    try:
        items = collect(platform=platform,
                        categories=([category] if category else None),
                        limit_channels=limit, on_progress=_on_progress)
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        store.update_collect_job(job_id, status="error", error=msg)
        return
```

3-3. 같은 함수의 `payload = {...}` 줄을 다음으로 교체:

```python
        # tally(채널별 성공/로그인벽/오류)를 결과에 남긴다 — 부계정(B안) 도입 판단 근거.
        payload = {"count": len(items), "items": items, "collected_at": collected_at,
                   "tally": dict(getattr(service, "LAST_COLLECT_TALLY", {}) or {})}
```

3-4. `_COLLECT_STALE_MIN = 60`(`app.py:259`)을 다음으로 교체:

```python
# Playwright 경로는 채널마다 진행률을 써서 updated_at이 갱신된다 — 진짜로 멈춘 경우만
# stale로 잡히게 짧게 둔다(2026-07-28). Apify 시절엔 갱신이 아예 없어 60분이 필요했다.
_COLLECT_STALE_MIN = 15
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_collect_progress.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add shopping_shorts/app.py shopping_shorts/tests/test_collect_progress.py
git commit -m "feat(수집): 진행률을 job result_json에 기록 + 분류집계 결과 노출"
```

---

### Task 7: 화면에 진행률 표시

**Files:**
- Modify: `shopping_shorts/static/index.html` (수집 폴링 처리부 — `collectProgress` 엘리먼트를 갱신하는 곳)
- Test: `shopping_shorts/tests/test_collect_progress_ui.py`

**Interfaces:**
- Consumes: Task 6이 만드는 `{"phase": "collecting", "done", "total", "items_so_far", "tally"}`
- Produces: 없음 (최종 소비자)

- [ ] **Step 1: 폴링 처리부의 정확한 위치를 찾는다**

Run: `grep -n "collect/status\|collectProgress" shopping_shorts/static/index.html`

찾은 폴링 콜백 안에서 응답 `d`를 다루는 지점을 확인한다. 다음 스텝의 코드를 그 자리에 넣는다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`shopping_shorts/tests/test_collect_progress_ui.py`:

```python
"""수집 진행률이 화면에 붙어 있는지(정적 검사).

★2026-07-27 실사고: 50분간 화면에 아무 변화가 없어 사장님이 취소했다.
서버가 진행률을 보내도 화면이 안 읽으면 같은 일이 반복된다.
"""
import pathlib

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_ui_reads_collecting_phase():
    assert "collecting" in HTML, "진행률 phase를 화면이 안 읽는다"


def test_ui_shows_done_over_total():
    assert "items_so_far" in HTML and "d.total" in HTML, \
        "진행 카운트(37/200 · N건)를 화면에 안 그린다"
```

- [ ] **Step 3: 실패하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_collect_progress_ui.py -q`
Expected: FAIL — `AssertionError: 진행률 phase를 화면이 안 읽는다`

- [ ] **Step 4: 화면에 진행률을 붙인다**

Step 1에서 찾은 폴링 콜백에서, 상태가 `running`일 때 처리하는 자리에 다음을 넣는다(`d`는 status 응답, `el`은 `collectProgress` 엘리먼트):

```javascript
    // ★수집 진행률(2026-07-28): 서버가 채널마다 result_json에 부분 payload를 쓴다.
    //   예전엔 표시가 없어 50분간 화면이 그대로였고 "멈췄다"고 판단해 취소하는 일이 있었다.
    if (d && d.result && d.result.phase === 'collecting') {
      const t = d.result.tally || {};
      const blocked = (t.login_wall || 0) + (t.error || 0);
      const el = document.getElementById('collectProgress');
      if (el) {
        el.style.display = '';
        el.textContent = `채널 ${d.result.done}/${d.result.total} · ${d.result.items_so_far}건 수집`
          + (blocked ? ` · 건너뜀 ${blocked}` : '');
      }
    }
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

Run: `python -m pytest shopping_shorts/tests/test_collect_progress_ui.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: JS 문법을 확인한다**

```bash
python -c "
import re
s=open('shopping_shorts/static/index.html',encoding='utf-8').read()
b=re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', s, re.S)
open('/tmp/idx.js','w',encoding='utf-8').write('\n;\n'.join(b))
"
node --check /tmp/idx.js
```
Expected: 출력 없음(문법 정상)

- [ ] **Step 7: 커밋**

```bash
git add shopping_shorts/static/index.html shopping_shorts/tests/test_collect_progress_ui.py
git commit -m "feat(수집): 화면에 '채널 37/200 · N건 수집' 진행률 표시"
```

---

### Task 8: 서버에 Playwright 설치 + 10채널 실측 게이트

**이 태스크는 코드가 아니라 측정이다.** 여기 숫자가 나오기 전에는 200채널로 전환하지 않는다.

**Files:**
- Create: `docs/superpowers/plans/2026-07-28-인스타-playwright-10채널-실측.md` (결과 기록)

**Interfaces:**
- Consumes: Task 1~7 전부
- Produces: 성공률·소요시간·`login_wall` 비율 실측치 — 200채널 개방과 B안(부계정) 도입 판단의 근거

- [ ] **Step 1: 서버 여유를 확인한다**

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "df -h / | tail -1; free -m | head -2"
```
Expected: 디스크 여유 2GB 이상, 메모리 여유 1GB 이상. 부족하면 **여기서 멈추고 사장님께 보고한다**(크로미움 설치가 서버를 마르게 하면 라이브 전체가 위험하다).

- [ ] **Step 2: Playwright를 설치한다**

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "cd /home/ubuntu/lotto-stock-wiki && pip install playwright && python3 -m playwright install --with-deps chromium"
```
Expected: 설치 성공. 실패하면 로그를 그대로 보고한다(우분투 라이브러리 의존성 문제가 흔하다).

- [ ] **Step 3: 설치를 검증한다**

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "cd /home/ubuntu/lotto-stock-wiki && python3 -c \"
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page()
    pg.goto('https://example.com', timeout=15000); print('TITLE:', pg.title()); b.close()
\""
```
Expected: `TITLE: Example Domain`

- [ ] **Step 4: 프록시 경유로 인스타에 닿는지 확인한다**

`INSTAGRAM_PROXY`를 서버 환경파일(`/etc/shopping-shorts.env`)에 넣고 재시작한 뒤:

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && python3 -c \"
from shopping_shorts import instagram_playwright as ipw
nodes, url, err = ipw._scrape_one_playwright('homeinon')
print('NODES:', len(nodes), 'URL:', url, 'ERR:', err)
\""
```
Expected: `NODES:`가 1 이상. 0이면 `URL`에 `/accounts/login`이 들어 있는지 본다(=로그인벽).

- [ ] **Step 5: 10채널 실측을 돌린다**

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && INSTAGRAM_SCRAPER=playwright python3 -c \"
import time
from shopping_shorts import service
t0 = time.time()
items = service.collect(platform='instagram', limit_channels=10,
                        on_progress=lambda d,t,i,ta: print(f'{d}/{t} items={i} {ta}', flush=True))
print('ELAPSED_SEC:', round(time.time()-t0, 1))
print('ITEMS:', len(items))
print('TALLY:', service.LAST_COLLECT_TALLY)
\""
```
Expected: `TALLY`에 `ok`가 몇인지, `login_wall`이 몇인지 숫자로 나온다.

- [ ] **Step 6: 결과를 기록하고 판단을 사장님께 넘긴다**

`docs/superpowers/plans/2026-07-28-인스타-playwright-10채널-실측.md`에 다음을 기록한다:

```markdown
# 인스타 Playwright 10채널 실측 (2026-07-28)

| 항목 | 값 |
|---|---|
| 성공(ok) | ?/10 |
| 로그인벽(login_wall) | ? |
| 없음(not_found) | ? |
| 오류(error) | ? |
| 수집 건수 | ? |
| 소요 | ?초 (채널당 평균 ?초) |
| 200채널 환산 | 약 ?분 |

## 판단
- ok ≥ 8/10 → 200채널 개방 진행
- ok 4~7/10 → 사장님께 보고 후 부계정(B안) 도입 여부 결정
- ok ≤ 3/10 → 비로그인 경로로는 부족. Apify 유지 + B안 설계 착수
```

빈칸을 실측치로 채운 뒤 커밋한다.

```bash
git add docs/superpowers/plans/2026-07-28-인스타-playwright-10채널-실측.md
git commit -m "docs(수집): 인스타 Playwright 10채널 실측 결과"
```

- [ ] **Step 7: 사장님께 숫자를 보고하고 멈춘다**

**★여기서 자동으로 200채널을 열지 않는다.** 실측 표를 그대로 보고하고, 위 판단 기준에 따라 사장님의 결정을 받는다.

---

### Task 9: 200채널 전환 (게이트 통과 후에만)

**Files:**
- Modify: 서버 `/etc/shopping-shorts.env` (코드 변경 없음)

**Interfaces:**
- Consumes: Task 8의 실측 결과와 사장님 승인
- Produces: 라이브 인스타 수집이 Playwright 경로로 동작

- [ ] **Step 1: 사장님 승인을 확인한다**

Task 8 Step 7에서 승인을 받았는지 확인한다. **승인이 없으면 이 태스크를 시작하지 않는다.**

- [ ] **Step 2: 서버 환경파일에 플래그를 넣는다**

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "grep -q INSTAGRAM_SCRAPER /etc/shopping-shorts.env || echo 'INSTAGRAM_SCRAPER=playwright' | sudo tee -a /etc/shopping-shorts.env"
```

- [ ] **Step 3: 서비스를 재시작하고 반영을 확인한다**

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "sudo systemctl restart shopping-shorts && sleep 5 && sudo tr '\0' '\n' < /proc/\$(pgrep -f 'shopping_shorts' | head -1)/environ | grep INSTAGRAM_"
```
Expected: `INSTAGRAM_SCRAPER=playwright`와 `INSTAGRAM_PROXY=...`가 실제 프로세스 환경에 보인다.

- [ ] **Step 4: 화면에서 전체 수집을 한 번 돌린다**

브라우저에서 「지금 수집」을 누르고 다음을 눈으로 확인한다.

- 진행률이 **"채널 N/200 · M건 수집"**으로 올라간다
- 끝까지 완주한다

- [ ] **Step 5: Apify 시절과 대조해 기록한다**

```bash
ssh -i "C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148 \
  "cd /home/ubuntu/lotto-stock-wiki && python3 -c \"
import sqlite3, json
c = sqlite3.connect('shopping_shorts/data/reference.db')
for r in c.execute('SELECT job_id,status,created_at,updated_at FROM collect_jobs ORDER BY rowid DESC LIMIT 3'):
    print(r)
\""
```

`created_at`→`updated_at` 차이가 소요시간이다. Apify 기준선은 **28분/345건**. 이보다 느리면 컨텍스트 수(`INSTAGRAM_PW_CONTEXTS`)를 조정한다.

- [ ] **Step 6: 롤백 방법을 사장님께 알린다**

문제가 생기면 서버에서 `INSTAGRAM_SCRAPER=apify`로 바꾸고 재시작하면 즉시 되돌아간다는 것을 명시적으로 전달한다. 코드 revert가 필요 없다.

---

## Self-Review

**1. 스펙 커버리지**

| 스펙 요구 | 담당 태스크 |
|---|---|
| `fetch_reels` 한 곳만 교체, 10키 계약 유지 | Task 1(파서), Task 4(스크레이퍼), Task 5(배선) |
| config 롤백 플래그 | Task 2, Task 9 Step 6 |
| DOM 대신 JSON 가로채기 | Task 4 (`_scrape_one_playwright`의 `page.on("response")`) |
| 브라우저 1 + 컨텍스트 N, 프록시 | Task 2(설정), Task 4(구현) |
| 진행률 `result_json` 부분 write | Task 6(서버), Task 7(화면) |
| `_COLLECT_STALE_MIN` 조정 | Task 6 Step 3-4 |
| 채널별 4분류 집계 | Task 3(분류), Task 4(집계), Task 6(결과 노출) |
| 파서 단위테스트(네트워크 없음) | Task 1, Task 3 |
| 10채널 실측 게이트 | Task 8 |
| 전환 | Task 9 |
| Playwright 서버 설치 | Task 8 Step 2~3 |
| 부계정 안 만듦 / Apify 삭제 안 함 | 계획 전체에 해당 태스크 없음 (의도적) |

빠진 요구 없음.

**2. 플레이스홀더 스캔**

Task 7 Step 1이 `grep`으로 위치를 찾는 단계인데, 이는 "TBD"가 아니라 **실행 가능한 탐색 명령**이고 넣을 코드는 Step 4에 완전한 형태로 있다. Task 8 Step 6의 표에 `?`가 있는 것은 **실측으로 채울 자리**이며 채우는 방법(Step 5의 명령)이 명시돼 있다. 그 외 미정 항목 없음.

**3. 타입 일관성**

- `parse_reel_node(node, username) -> dict | None` — Task 1 정의, Task 4에서 동일 시그니처로 호출 ✓
- `extract_reel_nodes(payload) -> list` — Task 1 정의, Task 4의 `_on_response`에서 호출 ✓
- `classify_channel_result(nodes, page_url, error) -> str` — Task 3 정의, Task 4에서 동일 인자 순서로 호출 ✓
- `_scrape_one(username) -> (nodes, page_url, error)` — Task 4에서 정의·주입, 테스트 fake도 동일 3튜플 ✓
- `on_progress(done, total, items_so_far, tally)` — Task 4 정의, Task 5 전달, Task 6 구현, Task 7 소비 — 4개 인자 일관 ✓
- `LAST_TALLY`(Task 4) → `service.LAST_COLLECT_TALLY`(Task 5) → `payload["tally"]`(Task 6) → 화면 `d.result.tally`(Task 7) ✓
