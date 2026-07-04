# Gemini 키 보관함(Key Vault) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 5 divergent Gemini-key-rotation implementations with one central `key_vault.py` module, re-split the key pool into 4 groups (general/ingest/embed/briefing) backed by the 18 keys now in `.env`, and prove with real (not just paper) tests that today's embedding bottleneck is actually resolved.

**Architecture:** `pipeline/atoms/key_vault.py` dynamically reads `GEMINI_<GROUP>_KEY`, `_2`, `_3`... from `.env` per group, tracks per-group daily-exhaustion state in a lock-protected JSON file, and exposes `get_client(group)` / `rotate(group)` (index-based, for atomize-style single-active-key consumers) and `get_live_keys(group)` / `mark_exhausted(group, key)` (pool-scan-based, for embed-style RPM consumers). Five existing call sites migrate to consume it; two dead-code/security cleanups ride along; a live smoke test and a burst-load test validate the design against real API behavior.

**Tech Stack:** Python 3.14, `google-genai` SDK, pytest + `unittest.mock`, Windows `msvcrt` file locking (project runs on Windows only).

## Global Constraints

- Keep `atomizer.py`'s existing public names (`_get_client`, `_rotate_key`, `_load_gemini_key`, `_load_gemini_keys`, `_tg_alert`) working unchanged — `telegram_questionnaire.py:286` and `post_questionnaire.py:67` import `_get_client`/`_rotate_key` directly and must not need changes.
- Ingest (atomize) and embed pools are now fully separate key sets — do not reintroduce cross-group fallback (that coupling was the root cause of the 2026-07-04 incident).
- No new third-party dependencies. `msvcrt` is stdlib on Windows.
- All new code follows existing style: no docstrings beyond one-line WHY comments, Korean comments matching the surrounding file's convention.

---

### Task 1: `key_vault.py` — dynamic key loading per group

**Files:**
- Create: `pipeline/atoms/key_vault.py`
- Test: `tests/atoms/test_key_vault.py`

**Interfaces:**
- Produces: `get_keys(group: str) -> list[str]` — reads `.env`, returns ordered list of non-empty keys for the group. Groups: `"general"` (`GEMINI_API_KEY*`), `"ingest"` (`GEMINI_INGEST_KEY*`), `"embed"` (`GEMINI_EMBED_KEY*`), `"briefing"` (`GEMINI_BRIEFING_KEY*`).

- [ ] **Step 1: Write the failing test**

```python
# tests/atoms/test_key_vault.py
import pipeline.atoms.key_vault as kv


def test_get_keys_reads_numbered_env_vars(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_EMBED_KEY_2=e2\nGEMINI_EMBED_KEY_3=e3\n"
        "GEMINI_API_KEY=g1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    assert kv.get_keys("embed") == ["e1", "e2", "e3"]
    assert kv.get_keys("general") == ["g1"]


def test_get_keys_skips_missing_numbers_without_stopping(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_INGEST_KEY=i1\nGEMINI_INGEST_KEY_3=i3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    assert kv.get_keys("ingest") == ["i1", "i3"]


def test_get_keys_prefers_os_environ_over_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from_file\n", encoding="utf-8")
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setenv("GEMINI_API_KEY", "from_environ")
    assert kv.get_keys("general") == ["from_environ"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/atoms/test_key_vault.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.atoms.key_vault'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/atoms/key_vault.py
"""
key_vault.py — Gemini API 키 중앙 관리.

그룹별로 .env의 GEMINI_<GROUP>_KEY, _2, _3... 넘버링을 동적으로 읽어들이고,
일일소진(daily)과 분당(RPM) 두 실패 모델을 그룹 단위 공유 상태에서 추적한다.
키를 .env에 한 줄 추가하면 코드 수정 없이 풀에 편입된다.
"""
import os
from pathlib import Path

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"

_GROUP_ENV_PREFIX = {
    "general": "GEMINI_API_KEY",
    "ingest": "GEMINI_INGEST_KEY",
    "embed": "GEMINI_EMBED_KEY",
    "briefing": "GEMINI_BRIEFING_KEY",
}

_MAX_KEYS_PER_GROUP = 30  # 안전 상한 — 이 이상은 .env에 추가해도 무시


def _read_env_file() -> dict[str, str]:
    vals: dict[str, str] = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def _env(name: str, env_vals: dict[str, str]) -> str:
    return os.environ.get(name) or env_vals.get(name, "")


def get_keys(group: str) -> list[str]:
    """그룹의 활성 키 전부(존재하는 _N 넘버링을 동적으로 스캔, 순서 보존)."""
    prefix = _GROUP_ENV_PREFIX[group]
    env_vals = _read_env_file()
    keys = []
    for i in range(1, _MAX_KEYS_PER_GROUP + 1):
        name = prefix if i == 1 else f"{prefix}_{i}"
        v = _env(name, env_vals)
        if v:
            keys.append(v)
    return keys
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/atoms/test_key_vault.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/key_vault.py tests/atoms/test_key_vault.py
git commit -m "feat: add key_vault module with dynamic per-group key loading"
```

---

### Task 2: `key_vault.py` — daily-exhaustion state with file locking

**Files:**
- Modify: `pipeline/atoms/key_vault.py`
- Test: `tests/atoms/test_key_vault.py`

**Interfaces:**
- Consumes: `get_keys(group)` from Task 1.
- Produces: `mark_exhausted(group: str, key: str) -> None`, `get_live_keys(group: str) -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/atoms/test_key_vault.py
def test_mark_exhausted_removes_key_from_live_keys(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_EMBED_KEY_2=e2\nGEMINI_EMBED_KEY_3=e3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    assert kv.get_live_keys("embed") == ["e1", "e2", "e3"]
    kv.mark_exhausted("embed", "e2")
    assert kv.get_live_keys("embed") == ["e1", "e3"]


def test_mark_exhausted_is_scoped_per_group(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_INGEST_KEY=i1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    kv.mark_exhausted("embed", "e1")
    assert kv.get_live_keys("embed") == []
    assert kv.get_live_keys("ingest") == ["i1"]  # 다른 그룹은 영향 없음


def test_state_resets_on_new_day(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"date": "2020-01-01", "exhausted": {"embed": [0]}}', encoding="utf-8"
    )
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_EMBED_KEY=e1\n", encoding="utf-8")
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", state_path)
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")

    assert kv.get_live_keys("embed") == ["e1"]  # 어제자 소진 기록은 무시됨
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/atoms/test_key_vault.py -v`
Expected: FAIL with `AttributeError: module 'pipeline.atoms.key_vault' has no attribute '_STATE_PATH'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to pipeline/atoms/key_vault.py
import json
import time
from datetime import datetime

_STATE_PATH = Path(__file__).parent / ".gemini_key_state.json"
_LOCK_PATH = Path(__file__).parent / ".gemini_key_state.lock"


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load_state() -> dict:
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
        if state.get("date") == _today_str() and isinstance(state.get("exhausted"), dict):
            return state
    except Exception:
        pass
    return {"date": _today_str(), "exhausted": {}}


class _FileLock:
    """Windows msvcrt 기반 간단 파일 락 — 상태 파일 read-modify-write 동시성 보호."""

    def __init__(self, path: Path, timeout: float = 5.0):
        self._path = path
        self._timeout = timeout
        self._fh = None

    def __enter__(self):
        import msvcrt
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "a+")
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.monotonic() > deadline:
                    return self  # 타임아웃 시 락 없이 진행(최선 시도, 완전 원자성 포기)
                time.sleep(0.05)

    def __exit__(self, *exc):
        import msvcrt
        try:
            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self._fh.close()


def mark_exhausted(group: str, key: str) -> None:
    """키를 당일 소진으로 기록(그룹별). 이후 프로세스는 재시도하지 않는다."""
    with _FileLock(_LOCK_PATH):
        keys = get_keys(group)
        if key not in keys:
            return
        idx = keys.index(key)
        state = _load_state()
        bucket = state["exhausted"].setdefault(group, [])
        if idx not in bucket:
            bucket.append(idx)
            with open(_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f)


def get_live_keys(group: str) -> list[str]:
    """당일 소진 기록된 키를 제외한 그룹의 키 목록."""
    state = _load_state()
    exhausted = set(state["exhausted"].get(group, []))
    return [k for i, k in enumerate(get_keys(group)) if i not in exhausted]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/atoms/test_key_vault.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/key_vault.py tests/atoms/test_key_vault.py
git commit -m "feat: add per-group daily-exhaustion tracking with file lock to key_vault"
```

---

### Task 3: `key_vault.py` — rotating client + telegram alerts

**Files:**
- Modify: `pipeline/atoms/key_vault.py`
- Test: `tests/atoms/test_key_vault.py`

**Interfaces:**
- Consumes: `get_keys`, `get_live_keys`, `mark_exhausted` from Tasks 1-2.
- Produces: `get_client_for_key(key: str) -> genai.Client`, `get_client(group: str) -> genai.Client`, `rotate(group: str) -> bool`, `reset(group: str) -> None`, `is_daily_exhausted_error(exc) -> bool`, `is_quota_error(exc) -> bool`, `client = get_client` (alias for drop-in migration).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/atoms/test_key_vault.py
from unittest.mock import patch, MagicMock


def test_get_client_for_key_caches_by_key():
    with patch("pipeline.atoms.key_vault.genai.Client") as MockClient:
        MockClient.return_value = MagicMock()
        c1 = kv.get_client_for_key("same-key")
        c2 = kv.get_client_for_key("same-key")
        assert c1 is c2
        MockClient.assert_called_once_with(api_key="same-key")


def test_rotate_marks_current_key_exhausted_and_advances(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_EMBED_KEY=e1\nGEMINI_EMBED_KEY_2=e2\n", encoding="utf-8"
    )
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")
    monkeypatch.setattr(kv, "_tg_alert", lambda text: None)
    kv.reset("embed")

    assert kv.rotate("embed") is True
    assert kv.get_live_keys("embed") == ["e2"]


def test_rotate_returns_false_and_alerts_when_all_exhausted(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_EMBED_KEY=e1\n", encoding="utf-8")
    monkeypatch.setattr(kv, "_ENV_PATH", env_file)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")
    alerts = []
    monkeypatch.setattr(kv, "_tg_alert", lambda text: alerts.append(text))
    kv.reset("embed")

    assert kv.rotate("embed") is False
    assert any("전체 소진" in a for a in alerts)


def test_is_daily_exhausted_error_vs_rpm_error():
    daily = Exception("429 RESOURCE_EXHAUSTED PerDay limit: 500")
    rpm = Exception("429 RESOURCE_EXHAUSTED PerMinute limit: 15")
    assert kv.is_daily_exhausted_error(daily) is True
    assert kv.is_daily_exhausted_error(rpm) is False
    assert kv.is_quota_error(rpm) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/atoms/test_key_vault.py -v`
Expected: FAIL with `AttributeError: module 'pipeline.atoms.key_vault' has no attribute 'get_client_for_key'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to pipeline/atoms/key_vault.py
import urllib.request
import urllib.parse
from google import genai

_client_cache: dict[str, genai.Client] = {}
_active_idx: dict[str, int] = {}


def get_client_for_key(key: str) -> genai.Client:
    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def get_client(group: str) -> genai.Client:
    """그룹의 현재 활성(인덱스 기반) 키로 클라이언트 반환."""
    live = get_live_keys(group)
    if not live:
        all_keys = get_keys(group)
        live = all_keys[-1:] if all_keys else []
    idx = min(_active_idx.get(group, 0), len(live) - 1) if live else 0
    key = live[idx] if live else ""
    return get_client_for_key(key)


client = get_client  # 드롭인 헬퍼 별칭 — genai.Client(api_key=...) 대체용


def reset(group: str) -> None:
    """세션 시작 시 인덱스 초기화(당일 소진 기록 자체는 유지)."""
    _active_idx[group] = 0


def rotate(group: str) -> bool:
    """현재 활성 키를 소진 처리하고 다음 살아있는 키로 교체.
    교체 성공 시 True, 그룹 전체 소진이면 알림 발송 후 False."""
    live_before = get_live_keys(group)
    if not live_before:
        _tg_alert(f"🚨 <b>[{group}] Gemini 키 전체 소진</b>\n총 {len(get_keys(group))}개 모두 일일 한도 초과")
        return False

    idx = min(_active_idx.get(group, 0), len(live_before) - 1)
    old_key = live_before[idx]
    old_num = get_keys(group).index(old_key) + 1
    mark_exhausted(group, old_key)

    live_after = get_live_keys(group)
    if live_after:
        _active_idx[group] = 0
        _tg_alert(
            f"⚠️ <b>[{group}] Gemini 키 #{old_num} 일일 한도 소진</b>\n"
            f"→ 다음 키로 교체 (잔여 {len(live_after)}개)"
        )
        return True
    _tg_alert(f"🚨 <b>[{group}] Gemini 키 전체 소진</b>\n총 {len(get_keys(group))}개 모두 일일 한도 초과")
    return False


def is_daily_exhausted_error(exc: Exception) -> bool:
    m = str(exc)
    return ("429" in m or "RESOURCE_EXHAUSTED" in m) and ("PerDay" in m or "limit: 500" in m)


def is_quota_error(exc: Exception) -> bool:
    m = str(exc)
    return "429" in m or "RESOURCE_EXHAUSTED" in m


def _tg_alert(text: str) -> None:
    """API 에러·키 소진 등을 텔레그램으로 즉시 발송. 실패해도 호출부 중단 없음."""
    env_vals = _read_env_file()
    token = _env("BOT_TOKEN", env_vals)
    chat_id = _env("CHAT_ID", env_vals)
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/atoms/test_key_vault.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/key_vault.py tests/atoms/test_key_vault.py
git commit -m "feat: add rotating client, alerts and error classifiers to key_vault"
```

---

### Task 4: Migrate `atomizer.py` to `key_vault` (ingest group)

**Files:**
- Modify: `pipeline/atoms/atomizer.py:1-140`

**Interfaces:**
- Consumes: `key_vault.get_client`, `key_vault.rotate`, `key_vault.get_keys`, `key_vault._tg_alert` from Tasks 1-3.
- Produces: `_get_client()`, `_rotate_key()`, `_load_gemini_key()`, `_load_gemini_keys()`, `_tg_alert(text)` — **unchanged signatures**, so `telegram_questionnaire.py:286`, `post_questionnaire.py:67` need no edits.

- [ ] **Step 1: Replace lines 1-140 of `atomizer.py`**

```python
import re
import json
import time
import hashlib
from pathlib import Path
from google import genai
from google.genai import types

from pipeline.atoms import key_vault

_GEMINI_MODEL = "gemini-3.1-flash-lite"
_GROUP = "ingest"


def _load_gemini_keys() -> list[str]:
    return key_vault.get_keys(_GROUP)


def _load_gemini_key() -> str:
    keys = _load_gemini_keys()
    return keys[0] if keys else ""


def _get_client() -> genai.Client:
    return key_vault.get_client(_GROUP)


def _rotate_key() -> bool:
    return key_vault.rotate(_GROUP)


def _tg_alert(text: str) -> None:
    key_vault._tg_alert(text)
```

Delete the old `_load_gemini_keys`/`_load_gemini_key`/`_GEMINI_KEYS`/`_client_cache`/`_KEY_STATE_PATH`/`_today_str`/`_load_key_state`/`_mark_key_exhausted`/`_first_live_key_idx`/`_key_idx`/`_get_client`/`_rotate_key`/`_reset_key_idx`/`_tg_alert` definitions (former lines 1-140) — replaced entirely by the block above. `os` and `json` imports: `json` is still used later in the file (`json.loads(response.text)`), keep it; `os` is no longer used directly in this file after removing `_load_gemini_keys`' manual `.env` parsing — remove the `import os` line.

**Note on behavior change:** the old `_load_gemini_keys()` combined ingest keys with an API-key fallback tail ("전체 4개 rotation" comment). This fallback is intentionally dropped — `ingest` is now a fully separate 5-key pool with ~2500/day capacity against ~180/day actual atomize volume, so cross-group fallback is unnecessary and was part of the original coupling bug.

- [ ] **Step 2: Update the two callers inside this same file that reference `_reset_key_idx`**

Run: `grep -n "_reset_key_idx\|_key_idx\|_GEMINI_KEYS" pipeline/atoms/atomizer.py`
Expected: no matches (confirms the removed names aren't referenced elsewhere in the file). If any match remains, delete that call site — `_reset_key_idx` had no external callers per the current codebase (only defined, never invoked from another module).

- [ ] **Step 3: Run the full atomizer test suite (if any) and the ingest-adjacent tests**

Run: `python -m pytest tests/atoms/ -v -k "atomizer or questionnaire"`
Expected: PASS (no existing atomizer-specific test file was found in `tests/atoms/`; this step confirms nothing else references the removed private names)

- [ ] **Step 4: Manual import sanity check**

Run: `python -c "from pipeline.atoms.atomizer import _get_client, _rotate_key, _load_gemini_key, _load_gemini_keys, atomize_text; print('ok')"`
Expected: prints `ok`

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/atomizer.py
git commit -m "refactor: delegate atomizer.py key rotation to key_vault (ingest group)"
```

---

### Task 5: Migrate `vector_db.py::embed_text` to `key_vault` (embed group)

**Files:**
- Modify: `pipeline/atoms/vector_db.py:1-101`
- Modify: `tests/atoms/test_vector_db.py:82-103` (existing tests patch names this task removes)

**Interfaces:**
- Consumes: `key_vault.get_live_keys`, `key_vault.get_client_for_key`, `key_vault.mark_exhausted`, `key_vault.is_daily_exhausted_error`, `key_vault._tg_alert` from Tasks 1-3.

- [ ] **Step 1: Update the failing tests first (they currently patch names we're about to delete)**

```python
# replace lines 75-103 of tests/atoms/test_vector_db.py
def test_embed_text_returns_3072_floats():
    """실제 API를 mock하여 반환 형식 검증."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.embeddings = [MagicMock(values=[0.1] * 3072)]
    mock_client.models.embed_content.return_value = mock_resp

    with patch("pipeline.atoms.vector_db.key_vault.get_live_keys", return_value=["fake-key"]), \
         patch("pipeline.atoms.vector_db.key_vault.get_client_for_key", return_value=mock_client):
        result = vdb_module.embed_text("테스트 텍스트")

    assert len(result) == 3072
    assert isinstance(result[0], float)


def test_embed_text_calls_correct_model():
    """gemini-embedding-001 모델로 호출되는지 확인."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.embeddings = [MagicMock(values=[0.0] * 3072)]
    mock_client.models.embed_content.return_value = mock_resp

    with patch("pipeline.atoms.vector_db.key_vault.get_live_keys", return_value=["fake-key"]), \
         patch("pipeline.atoms.vector_db.key_vault.get_client_for_key", return_value=mock_client):
        vdb_module.embed_text("hello")
        mock_client.models.embed_content.assert_called_once_with(
            model="gemini-embedding-001",
            contents="hello",
        )


def test_embed_text_marks_key_exhausted_on_daily_limit_and_tries_next(monkeypatch):
    """일일 한도(429+PerDay) 키는 mark_exhausted 후 다음 키로 넘어간다."""
    daily_exceeded = Exception("429 RESOURCE_EXHAUSTED PerDay limit: 500")
    ok_client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.embeddings = [MagicMock(values=[0.2] * 3072)]
    ok_client.models.embed_content.return_value = ok_resp
    bad_client = MagicMock()
    bad_client.models.embed_content.side_effect = daily_exceeded

    marked = []
    monkeypatch.setattr(vdb_module.key_vault, "get_live_keys", lambda g: ["bad-key", "ok-key"])
    monkeypatch.setattr(vdb_module.key_vault, "mark_exhausted", lambda g, k: marked.append((g, k)))
    monkeypatch.setattr(
        vdb_module.key_vault, "get_client_for_key",
        lambda k: bad_client if k == "bad-key" else ok_client,
    )

    result = vdb_module.embed_text("hello")
    assert len(result) == 3072
    assert marked == [("embed", "bad-key")]


def test_embed_text_raises_after_both_attempts_fail(monkeypatch):
    """RPM성 429가 두 번의 전체 순회(20초 간격) 후에도 실패하면 명확한 예외를 낸다."""
    rpm_exceeded = Exception("429 RESOURCE_EXHAUSTED PerMinute limit: 15")
    bad_client = MagicMock()
    bad_client.models.embed_content.side_effect = rpm_exceeded

    monkeypatch.setattr(vdb_module.key_vault, "get_live_keys", lambda g: ["k1"])
    monkeypatch.setattr(vdb_module.key_vault, "get_client_for_key", lambda k: bad_client)
    monkeypatch.setattr(vdb_module.key_vault, "mark_exhausted", lambda g, k: None)
    monkeypatch.setattr(vdb_module.key_vault, "_tg_alert", lambda text: None)
    monkeypatch.setattr(vdb_module.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="RPM"):
        vdb_module.embed_text("hello")
```

Also add `import pytest` and `import time` to the top of `tests/atoms/test_vector_db.py` if not already present (check first — `pytest` is already imported at line 1; add `import pipeline.atoms.key_vault` is not required since we access it via `vdb_module.key_vault`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/atoms/test_vector_db.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.atoms.vector_db' has no attribute 'key_vault'` (module not yet imported) and old patch targets (`_load_gemini_keys`, `_get_embed_client_for`) no longer exist in `vector_db.py` after Step 3, but right now (before Step 3) they still exist — so the *new* tests fail while old ones still reference now-removed behavior. Confirm the new 4 tests fail for the "no attribute key_vault" reason.

- [ ] **Step 3: Replace `embed_text` and its imports in `vector_db.py`**

```python
# replace line 12 of pipeline/atoms/vector_db.py
from pipeline.atoms import key_vault
```

Remove line 19 (`_embed_clients: dict[str, genai.Client] = {}`) and the `_get_embed_client_for` function (lines 63-66) — no longer needed, `key_vault.get_client_for_key` owns client caching now.

```python
# replace embed_text (former lines 79-101) of pipeline/atoms/vector_db.py
def embed_text(text: str) -> list[float]:
    """텍스트를 gemini-embedding-001로 임베딩 (3072차원).
    429는 대부분 분당 요청수(RPM) 제한이라 짧으면 1분 내 회복된다 — 일일 소진이 아니다.
    embed 전용 키 풀(key_vault 'embed' 그룹)을 한 바퀴 돌고,
    그래도 다 막히면 20초 대기 후 한 번 더 전체를 재시도한다."""
    for attempt in range(2):
        keys = key_vault.get_live_keys("embed")
        for key in keys:
            try:
                resp = key_vault.get_client_for_key(key).models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                )
                return list(resp.embeddings[0].values)
            except Exception as e:
                if key_vault.is_daily_exhausted_error(e):
                    key_vault.mark_exhausted("embed", key)
                    continue
                if key_vault.is_quota_error(e):
                    continue
                raise
        if attempt == 0:
            time.sleep(20)
    key_vault._tg_alert("🚨 <b>[embed] Gemini 임베딩 키 전체 소진(RPM)</b> — 20초 재시도 후에도 실패")
    raise RuntimeError("모든 Gemini 임베딩 키 한도 초과(RPM) — 20초 재시도 후에도 실패")
```

Add `import time` at the top of `vector_db.py` (module-level, replacing the inline `import time as _time` that was local to the old function) and update the `time.sleep(20)` call above to match (already using the module-level name).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/atoms/test_vector_db.py -v`
Expected: PASS (all tests, including the pre-existing `embed_and_store`/`query_similar` tests which still patch `vdb_module.embed_text` directly and are unaffected)

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/vector_db.py tests/atoms/test_vector_db.py
git commit -m "refactor: migrate vector_db.embed_text to key_vault embed group"
```

---

### Task 6: Fix `pdf_ingest.py` — stop pinning key index 0, add rotation

**Files:**
- Modify: `pipeline/atoms/pdf_ingest.py:24-30, 136-164`

**Interfaces:**
- Consumes: `key_vault.get_client`, `key_vault.rotate`, `key_vault.is_daily_exhausted_error`, `key_vault.is_quota_error` from Tasks 1-3.

- [ ] **Step 1: Change the import (line 27)**

```python
# pipeline/atoms/pdf_ingest.py line 27, replace:
from .atomizer import _load_gemini_key, _make_id, _calc_strength
# with:
from pipeline.atoms import key_vault
from .atomizer import _make_id, _calc_strength
```

- [ ] **Step 2: Replace `_pdf_to_atoms` (lines 136-164) with a retrying, rotating version**

```python
def _pdf_to_atoms(pdf_path: Path, meta: dict) -> list[dict]:
    """Gemini로 PDF 읽어 원자 리스트 반환."""
    import json as _json
    import time as _time

    raw_atoms = None
    for _attempt in range(4):
        client = key_vault.get_client("ingest")
        file_obj = None
        try:
            with open(pdf_path, "rb") as fh:
                file_obj = client.files.upload(
                    file=fh,
                    config=types.UploadFileConfig(mime_type="application/pdf"),
                )
            response = client.models.generate_content(
                model=_MODEL,
                contents=[file_obj, _PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            raw_atoms = _json.loads(response.text)
            break
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) and key_vault.rotate("ingest"):
                continue
            if key_vault.is_quota_error(e):
                _time.sleep(62)
                continue
            print(f"  [WARN] Gemini PDF 처리 실패: {e}")
            return []
        finally:
            if file_obj is not None:
                try:
                    client.files.delete(name=file_obj.name)
                except Exception:
                    pass

    if raw_atoms is None:
        print("  [WARN] Gemini PDF 처리 실패: 재시도 소진")
        return []

    atoms = []
    for i, a in enumerate(raw_atoms):
        content = a.get("content", "").strip()
        if not content:
            continue
        atoms.append({
            "id": _make_id(meta["date"], meta["broker"], i),
            "date": meta["date"],
            "source_type": "report",
            "source_name": meta["broker"],
            "source_trust": "A",
            "raw_file": str(pdf_path),
            "layer": "L5",
            "sector": a.get("sector", "기타"),
            "asset": a.get("asset", ""),
            "asset_level": a.get("asset_level", "stock"),
            "signal": a.get("signal", "neutral"),
            "event_type": a.get("event_type", "report"),
            "magnitude": a.get("magnitude", "minor"),
            "content_type": a.get("content_type", "analysis"),
            "strength_score": _calc_strength(a, "A"),
            "validity_type": a.get("validity_type", "permanent"),
            "validity_until": a.get("validity_until"),
            "is_active": 1,
            "content": content,
            "relations": [],
        })
    return atoms
```

- [ ] **Step 3: Write a test for the rotation behavior**

```python
# tests/atoms/test_pdf_ingest.py (new file)
from unittest.mock import patch, MagicMock
import pipeline.atoms.pdf_ingest as pdf_module


def test_pdf_to_atoms_rotates_on_daily_exhaustion(monkeypatch, tmp_path):
    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    meta = {"date": "2026-07-04", "broker": "테스트증권"}

    bad_client = MagicMock()
    bad_client.files.upload.return_value = MagicMock(name="file1")
    bad_client.models.generate_content.side_effect = Exception(
        "429 RESOURCE_EXHAUSTED PerDay limit: 500"
    )
    good_client = MagicMock()
    good_client.files.upload.return_value = MagicMock(name="file2")
    good_resp = MagicMock()
    good_resp.text = '[{"content": "삼성전자 목표가 상향, 근거는 메모리 업황 개선."}]'
    good_client.models.generate_content.return_value = good_resp

    clients = [bad_client, good_client]
    monkeypatch.setattr(pdf_module.key_vault, "get_client", lambda g: clients.pop(0))
    monkeypatch.setattr(pdf_module.key_vault, "rotate", lambda g: True)
    monkeypatch.setattr(pdf_module.key_vault, "is_daily_exhausted_error",
                         lambda e: "PerDay" in str(e))
    monkeypatch.setattr(pdf_module.key_vault, "is_quota_error", lambda e: "429" in str(e))

    atoms = pdf_module._pdf_to_atoms(pdf_path, meta)
    assert len(atoms) == 1
    assert "메모리 업황" in atoms[0]["content"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/atoms/test_pdf_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/atoms/pdf_ingest.py tests/atoms/test_pdf_ingest.py
git commit -m "fix: rotate Gemini key on daily exhaustion in pdf_ingest instead of pinning key 0"
```

---

### Task 7: Remove dead `_load_gemini_key` import from `osc_ingest.py`

**Files:**
- Modify: `pipeline/atoms/osc_ingest.py:35`

Verified via `grep -n "_load_gemini_key\|genai.Client" pipeline/atoms/osc_ingest.py` that the import is never called anywhere in this file (it does no Gemini calls at all — purely numeric oscillator-to-atom transform). This is dead code, not a live key-pinning bug.

- [ ] **Step 1: Remove the unused import**

```python
# pipeline/atoms/osc_ingest.py line 35, replace:
from .atomizer import _make_id, _load_gemini_key
# with:
from .atomizer import _make_id
```

- [ ] **Step 2: Confirm the module still imports cleanly**

Run: `python -c "import pipeline.atoms.osc_ingest; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add pipeline/atoms/osc_ingest.py
git commit -m "chore: remove unused _load_gemini_key import from osc_ingest.py"
```

---

### Task 8: Migrate `dashboard/server.py` key pools to `key_vault`

**Files:**
- Modify: `dashboard/server.py:119-188`
- Modify: `tests/test_briefing_api.py:64-73`

**Interfaces:**
- Consumes: `key_vault.get_keys`, `key_vault.get_client_for_key` from Tasks 1-3.

- [ ] **Step 1: Update the two tests that patch `_env_key` directly**

```python
# replace tests/test_briefing_api.py lines 64-73
def test_briefing_keys_uses_dedicated_key_when_set(monkeypatch):
    monkeypatch.setattr(server.key_vault, "get_keys", lambda group: (
        ["dedicated-key-1"] if group == "briefing" else []))
    assert server._briefing_keys() == ["dedicated-key-1"]


def test_briefing_keys_falls_back_to_summary_keys_when_no_dedicated_key(monkeypatch):
    monkeypatch.setattr(server.key_vault, "get_keys", lambda group: [])
    monkeypatch.setattr(server, "_summary_keys", lambda: ["shared-key-1", "shared-key-2"])
    assert server._briefing_keys() == ["shared-key-1", "shared-key-2"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_briefing_api.py -v -k briefing_keys`
Expected: FAIL — `AttributeError: module 'dashboard.server' has no attribute 'key_vault'`

- [ ] **Step 3: Add the import and replace the three key-pool functions (lines 119-145)**

```python
# add near the top of dashboard/server.py, alongside other pipeline imports
from pipeline.atoms import key_vault
```

```python
# replace dashboard/server.py lines 119-145
def _gemini_interactive_keys():
    """대화형(리서치·이미지·비전) Gemini 키 — key_vault 'general' 그룹."""
    return key_vault.get_keys("general")


def _summary_keys():
    """뉴스요약용 키 풀 — 대화형(general) + 인제스트(ingest) 키까지 총동원해 429 쿼터 여유 확보.
    프리워밍이 여러 섹터를 도는 만큼 키가 많아야 무료 쿼터가 안 터진다."""
    seen, out = set(), []
    for k in key_vault.get_keys("general") + key_vault.get_keys("ingest"):
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _briefing_keys():
    """실시간 시장 브리핑 종합 전용 키 풀 — key_vault 'briefing' 그룹, 없으면 요약 풀로 폴백."""
    dedicated = key_vault.get_keys("briefing")
    return dedicated or _summary_keys()
```

- [ ] **Step 4: Update `_gemini_text` (former line 166) to reuse the vault's client cache**

```python
# dashboard/server.py, inside _gemini_text, replace:
client = genai.Client(api_key=k)   # 변수 유지 — GC가 호출 중 닫지 않게
# with:
client = key_vault.get_client_for_key(k)  # key_vault 캐시 재사용, 매 호출 새 클라이언트 생성 안 함
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_briefing_api.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 6: Commit**

```bash
git add dashboard/server.py tests/test_briefing_api.py
git commit -m "refactor: migrate dashboard/server.py Gemini key pools to key_vault"
```

---

### Task 9: Migrate `daily_scenario.py` to `key_vault`

**Files:**
- Modify: `daily_scenario.py:99-140`

**Interfaces:**
- Consumes: `key_vault.get_keys`, `key_vault.get_client_for_key` from Tasks 1-3.

- [ ] **Step 1: Replace `_gemini_keys`, `get_gemini`, `generate_with_rotation` (lines 99-140)**

```python
from pipeline.atoms import key_vault


def _gemini_keys():
    """등록된 모든 Gemini 키(general + ingest, key_vault 경유).
    쿼터를 키 여러 개로 분산해 429를 줄인다."""
    seen, out = set(), []
    for k in key_vault.get_keys("general") + key_vault.get_keys("ingest"):
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def get_gemini():
    """하위호환: 첫 번째 키로 클라이언트 생성(단발 호출용)."""
    keys = _gemini_keys()
    api_key = keys[0] if keys else ""
    return key_vault.get_client_for_key(api_key)


def generate_with_rotation(prompt: str, models=('gemini-3-flash-preview', 'gemini-2.5-flash')) -> str:
    """등록된 키 × 모델을 순회하며 시도 — 429(쿼터초과) 등 실패 시 다음 키/모델로 자동 전환."""
    keys = _gemini_keys()
    last_err = None
    for key in keys:
        client = key_vault.get_client_for_key(key)
        for model in models:
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                text = getattr(resp, 'text', '') or ''
                if text:
                    return text
            except Exception as e:
                last_err = e
                continue
    raise RuntimeError(f"모든 Gemini 키/모델 실패: {last_err}")
```

Remove the now-unused `from google import genai` local imports inside the deleted function bodies (lines that read `from google import genai` at the top of `_gemini_keys`/`generate_with_rotation`) — `key_vault` owns the `genai` dependency now.

- [ ] **Step 2: Manual sanity check**

Run: `python -c "import daily_scenario; print(daily_scenario._gemini_keys()[:1] != [])"`
Expected: prints `True` (confirms at least one key loads without error)

- [ ] **Step 3: Commit**

```bash
git add daily_scenario.py
git commit -m "refactor: migrate daily_scenario.py Gemini key rotation to key_vault"
```

---

### Task 10: Update `scripts/daily_gemini_report.py` key-status section for 4 groups

**Files:**
- Modify: `scripts/daily_gemini_report.py:70-112`

**Interfaces:**
- Consumes: `key_vault.get_keys`, `key_vault.get_live_keys` from Tasks 1-2.

- [ ] **Step 1: Replace `section_key_status` (lines 70-112)**

```python
def section_key_status():
    lines = ["## 2. Gemini API 키 상태 (그룹별, key_vault 기준)\n"]
    from pipeline.atoms import key_vault

    lines.append("| 그룹 | 총 키 수 | 당일 소진(무비용 확인) | 실시간 재확인 |")
    lines.append("|---|---|---|---|")
    try:
        from google import genai
    except Exception:
        genai = None

    any_group_fully_exhausted = []
    for group in ("general", "ingest", "embed", "briefing"):
        all_keys = key_vault.get_keys(group)
        live_keys = key_vault.get_live_keys(group)
        exhausted_count = len(all_keys) - len(live_keys)
        if not all_keys:
            lines.append(f"| {group} | 0 | (미설정) | - |")
            continue
        live = "-"
        if genai and live_keys:
            try:
                client = key_vault.get_client_for_key(live_keys[0])
                resp = client.models.generate_content(model="gemini-3.1-flash-lite", contents="hi")
                live = "🟢 OK" if (resp.text or "").strip() else "⚠️빈응답"
            except Exception as e:
                m = str(e)
                live = "🔴 429소진" if ("429" in m or "RESOURCE_EXHAUSTED" in m) else f"⚠️{m[:40]}"
        elif not live_keys:
            live = "🔴 그룹 전체 소진"
            any_group_fully_exhausted.append(group)
        lines.append(f"| {group} | {len(all_keys)} | {exhausted_count}/{len(all_keys)} | {live} |")

    if any_group_fully_exhausted:
        lines.append(f"\n⚠️ **다음 그룹이 오늘 전부 소진됨: {', '.join(any_group_fully_exhausted)}**")
    return "\n".join(lines)
```

- [ ] **Step 2: Manual run to confirm no crash**

Run: `python scripts/daily_gemini_report.py`
Expected: exits without traceback; prints/sends a report containing a "## 2. Gemini API 키 상태" section listing all 4 groups with counts summing to 18 total keys across groups (4 general + 5 ingest + 6 embed + 3 briefing)

- [ ] **Step 3: Commit**

```bash
git add scripts/daily_gemini_report.py
git commit -m "refactor: report Gemini key status per key_vault group (adds embed group)"
```

---

### Task 11: Remove hardcoded API key literal from `generate_jh_images.py`

**Files:**
- Modify: `scripts/generate_jh_images.py:10`

- [ ] **Step 1: Remove the leaked-credential fallback**

```python
# scripts/generate_jh_images.py line 10, replace:
API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyBnXfHkFh5YCOZdHYmKwqWXwVh7mrtF7U0"
# with:
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError(".env에 GEMINI_API_KEY 없음")
```

- [ ] **Step 2: Confirm the script still parses**

Run: `python -c "import ast; ast.parse(open('scripts/generate_jh_images.py', encoding='utf-8').read())"`
Expected: no output (parses cleanly)

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_jh_images.py
git commit -m "security: remove hardcoded Gemini API key literal from generate_jh_images.py"
```

**Note:** the literal key `AIzaSyBnXfHkFh5YCOZdHYmKwqWXwVh7mrtF7U0` was committed to git history in this file. Removing it from the working copy does not remove it from history — flag to the user separately whether that key (a `YOUTUBE_API_KEY`-style key, unrelated to the `AQ.Ab8R...` Gemini keys) needs to be revoked in Google Cloud Console.

---

### Task 12: Live smoke test — confirm all 18 keys authenticate

**Files:**
- Create: `scripts/smoke_test_key_vault.py`

**Interfaces:**
- Consumes: `key_vault.get_keys`, `key_vault.get_client_for_key` from Tasks 1-3.

- [ ] **Step 1: Write the smoke test script**

```python
"""
smoke_test_key_vault.py — 18개 Gemini 키가 전부 실제로 인증되는지 1콜씩 확인.
사용법: python scripts/smoke_test_key_vault.py
"""
import sys
import time
sys.path.insert(0, ".")
from pipeline.atoms import key_vault

GROUPS = ["general", "ingest", "embed", "briefing"]


def check_key(group: str, idx: int, key: str) -> str:
    client = key_vault.get_client_for_key(key)
    try:
        if group == "embed":
            resp = client.models.embed_content(model="gemini-embedding-001", contents="ping")
            ok = bool(resp.embeddings and resp.embeddings[0].values)
        else:
            resp = client.models.generate_content(model="gemini-3.1-flash-lite", contents="ping")
            ok = bool((resp.text or "").strip())
        return "OK" if ok else "빈 응답"
    except Exception as e:
        return f"FAIL: {str(e)[:100]}"


def main():
    total = 0
    failures = []
    for group in GROUPS:
        keys = key_vault.get_keys(group)
        print(f"\n[{group}] {len(keys)}개 키")
        for i, key in enumerate(keys):
            total += 1
            result = check_key(group, i, key)
            print(f"  #{i+1}: {result}")
            if result != "OK":
                failures.append(f"{group}#{i+1}: {result}")
            time.sleep(1)  # 연속 호출로 인한 자체 RPM 유발 방지

    print(f"\n총 {total}개 키 확인, 실패 {len(failures)}개")
    for f in failures:
        print(f"  - {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it for real against the actual `.env`**

Run: `python scripts/smoke_test_key_vault.py`
Expected: `총 18개 키 확인, 실패 0개` — every one of the 10 new keys plus the 8 existing ones returns `OK`. If any key fails, capture the exact error text (invalid key vs quota vs network) before proceeding — do not claim the vault is done until this passes or failures are explained.

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_test_key_vault.py
git commit -m "test: add live smoke test confirming all 18 Gemini keys authenticate"
```

---

### Task 13: Burst-load test — validate the embed group survives today's peak volume

**Files:**
- Create: `scripts/loadtest_embed_pool.py`

**Interfaces:**
- Consumes: `key_vault.get_live_keys`, `pipeline.atoms.vector_db.embed_text` from Tasks 1-5.

- [ ] **Step 1: Write the load test script**

```python
"""
loadtest_embed_pool.py — 2026-07-01 실측 피크(1,171건)에 준하는 임베딩 부하를
EMBED 풀(6키)에 실제로 흘려서 "전체 소진" 없이 버티는지, 실제 소요 시간이
07:00 단일 배치 실행 시간 안에 들어오는지 확인한다.

사용법: python scripts/loadtest_embed_pool.py --n 1200
"""
import argparse
import sys
import time
sys.path.insert(0, ".")
from pipeline.atoms import key_vault
from pipeline.atoms.vector_db import embed_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1200, help="오늘 피크(1,171)보다 약간 많게 기본값 설정")
    args = ap.parse_args()

    live_before = key_vault.get_live_keys("embed")
    print(f"시작 시점 살아있는 embed 키: {len(live_before)}/{len(key_vault.get_keys('embed'))}")

    start = time.monotonic()
    failures = 0
    for i in range(args.n):
        try:
            embed_text(f"부하테스트 텍스트 {i} — 반도체 업황 개선 관련 더미 문장.")
        except RuntimeError as e:
            failures += 1
            print(f"  [{i}] 실패: {e}")
        if (i + 1) % 100 == 0:
            elapsed = time.monotonic() - start
            print(f"  {i+1}/{args.n} 처리, 경과 {elapsed:.1f}s")

    elapsed = time.monotonic() - start
    live_after = key_vault.get_live_keys("embed")
    print(f"\n총 {args.n}건, 실패 {failures}건, 소요 {elapsed:.1f}s ({elapsed/60:.1f}분)")
    print(f"종료 시점 살아있는 embed 키: {len(live_after)}/{len(key_vault.get_keys('embed'))}")
    if failures:
        print("⚠️ 일부 실패 발생 — embed 풀이 오늘 피크 물량을 완전히 커버하지 못함")
        return 1
    print("✅ 전체 소진 없이 완료 — embed 풀이 오늘 피크 물량을 커버함")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against real keys with `--n 1200` (slightly above the observed 1,171 peak)**

Run: `python scripts/loadtest_embed_pool.py --n 1200`
Expected: `총 1200건, 실패 0건` and a reported elapsed time. **Read the actual elapsed time and failure count from the output — do not report this task as passing without pasting/quoting the real numbers.** If failures occur, that means 6 keys are NOT enough for today's peak and the allocation in the design spec needs revisiting (e.g., shift 1-2 more keys from `ingest` to `embed`, since Task 4's migration proved `ingest` has large surplus headroom).

- [ ] **Step 3: Record the result in the design spec**

Add a `## 검증 결과` section to `docs/superpowers/specs/2026-07-04-gemini-key-vault-design.md` with the actual smoke-test and load-test output (pass/fail counts, elapsed time, date run).

- [ ] **Step 4: Commit**

```bash
git add scripts/loadtest_embed_pool.py docs/superpowers/specs/2026-07-04-gemini-key-vault-design.md
git commit -m "test: add embed-pool burst load test and record verification results"
```

---

## Self-Review Notes

- **Spec coverage:** all 4 groups (Task 1), central vault (Tasks 1-3), all "필수" tier migrations from the spec (Tasks 4-9 cover atomizer/vector_db/dashboard/daily_scenario/pdf_ingest; Task 7 corrects osc_ingest which the spec assumed was a live bug but is actually dead code), daily_gemini_report reporting update (Task 10, not in original "필수" list but needed since it hardcodes the old 6-key list), the two flagged cleanups (Tasks 6/11), and both requested tests (Tasks 12-13). "권장"-tier scripts (briefing/*, yt_*, sector_*, etc.) are intentionally deferred to a follow-up plan per YAGNI — they already work via the unchanged `GEMINI_API_KEY` name and aren't part of today's bottleneck.
- **Type consistency:** `key_vault.get_client(group)`, `key_vault.rotate(group)`, `key_vault.get_live_keys(group)`, `key_vault.mark_exhausted(group, key)`, `key_vault.get_client_for_key(key)`, `key_vault.get_keys(group)` are used with identical signatures across Tasks 4-10.
- **3pro_corner_test.py's dead `GEMINI_API_KEY_3` reference:** no task needed — the key vault design already added `GEMINI_API_KEY_3` to `.env`, so this previously-broken script now resolves correctly as a side effect.
