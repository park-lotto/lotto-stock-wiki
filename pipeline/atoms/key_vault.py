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
