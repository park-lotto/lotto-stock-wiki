"""Dynamically load Gemini API keys from .env by scanning numbered suffixes (_2, _3, ...)."""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from google import genai

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
    """파일 락(Windows=msvcrt, POSIX=fcntl) — 상태 파일 read-modify-write 동시성 보호.
    이전엔 msvcrt만 써서 리눅스 서버에서 키 로테이션마다 ModuleNotFoundError로 죽었었다
    (2026-07-05 실서버 인제스트 크래시로 발견 — 원격 서버 pytest 회귀에 이미 잡혀있었으나
    v1 daily_verify가 "발견만" 하고 고치지 않아 며칠간 방치됨)."""

    def __init__(self, path: Path, timeout: float = 5.0):
        self._path = path
        self._timeout = timeout
        self._fh = None

    def __enter__(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "a+")
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() > deadline:
                    return self  # 타임아웃 시 락 없이 진행(최선 시도, 완전 원자성 포기)
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            if sys.platform == "win32":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
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
            tmp_path = _STATE_PATH.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp_path, _STATE_PATH)


def get_live_keys(group: str) -> list[str]:
    """당일 소진 기록된 키를 제외한 그룹의 키 목록."""
    state = _load_state()
    exhausted = set(state["exhausted"].get(group, []))
    return [k for i, k in enumerate(get_keys(group)) if i not in exhausted]


def _cascade_groups(group: str) -> list[str]:
    """폴백 순서: 해당 그룹 먼저 → 나머지 그룹(정의 순서)."""
    return [group] + [g for g in _GROUP_ENV_PREFIX if g != group]


def _owner_group(key: str) -> str | None:
    """키가 속한 그룹을 찾는다(cross-group 소진 기록용)."""
    for g in _GROUP_ENV_PREFIX:
        if key in get_keys(g):
            return g
    return None


def get_live_keys_cascade(group: str) -> list[str]:
    """primary 그룹 라이브 키 우선, 소진 시 다른 그룹 라이브 키로 순차 폴백(18개 전체 풀).
    한 작업의 그룹이 다 말라도 놀고 있는 다른 그룹 키를 빌려 쓴다."""
    seen: set[str] = set()
    out: list[str] = []
    for g in _cascade_groups(group):
        for k in get_live_keys(g):
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out


_client_cache: dict[str, genai.Client] = {}
_active_idx: dict[str, int] = {}


def get_client_for_key(key: str) -> genai.Client:
    # 키마다 클라이언트를 캐시 — 중복 생성 방지
    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def get_client(group: str) -> genai.Client:
    """그룹의 현재 활성 키로 클라이언트 반환. 그룹이 다 소진되면 다른 그룹 키로 폴백."""
    all_keys = get_keys(group)
    if not all_keys:
        raise RuntimeError(f"key_vault: '{group}' 그룹에 설정된 Gemini 키가 없습니다 (.env 확인)")
    live = get_live_keys_cascade(group)  # cross-group 폴백
    if not live:
        live = all_keys[-1:]  # 전체 소진 시 최후로 마지막 키 시도
    idx = min(_active_idx.get(group, 0), len(live) - 1) if live else 0
    key = live[idx] if live else ""
    return get_client_for_key(key)


client = get_client  # 드롭인 헬퍼 별칭 — genai.Client(api_key=...) 대체용


def reset(group: str) -> None:
    """세션 시작 시 인덱스 초기화(당일 소진 기록 자체는 유지)."""
    _active_idx[group] = 0


def rotate(group: str) -> bool:
    """현재 활성 키를 소진 처리하고 다음 살아있는 키로 교체(그룹 소진 시 다른 그룹으로 폴백).
    18개 전체 풀에 살아있는 키가 남으면 True, 전부 소진이면 알림 후 False."""
    live_before = get_live_keys_cascade(group)
    total = sum(len(get_keys(g)) for g in _GROUP_ENV_PREFIX)
    if not live_before:
        _tg_alert(f"🚨 <b>[{group}] Gemini 키 전체 소진</b>\n전 그룹 총 {total}개 모두 일일 한도 초과")
        return False

    idx = min(_active_idx.get(group, 0), len(live_before) - 1)
    old_key = live_before[idx]
    owner = _owner_group(old_key) or group
    old_num = get_keys(owner).index(old_key) + 1
    mark_exhausted(owner, old_key)  # 빌려 쓴 키는 소유 그룹에 소진 기록

    live_after = get_live_keys_cascade(group)
    if live_after:
        _active_idx[group] = 0
        note = "" if owner == group else f" [{owner} 그룹 키 차용]"
        _tg_alert(
            f"⚠️ <b>[{group}] Gemini 키 #{old_num}{note} 일일 한도 소진</b>\n"
            f"→ 다음 키로 교체 (전체 풀 잔여 {len(live_after)}개)"
        )
        return True
    _tg_alert(f"🚨 <b>[{group}] Gemini 키 전체 소진</b>\n전 그룹 총 {total}개 모두 일일 한도 초과")
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
