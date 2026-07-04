"""Dynamically load Gemini API keys from .env by scanning numbered suffixes (_2, _3, ...)."""
import json
import os
import time
from datetime import datetime
from pathlib import Path

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
_STATE_PATH = Path(__file__).parent / ".gemini_key_state.json"
_LOCK_PATH = Path(__file__).parent / ".gemini_key_state.lock"

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
