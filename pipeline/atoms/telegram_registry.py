"""텔레그램 채널 레지스트리 + 종목명 별칭."""
import json
from pathlib import Path

_DIR = Path(__file__).parent
_CHANNELS = json.loads((_DIR / "telegram_channels.json").read_text(encoding="utf-8"))
_ALIASES_RAW = json.loads((_DIR / "stock_aliases.json").read_text(encoding="utf-8"))
_ALIASES = {k.lower(): v for k, v in _ALIASES_RAW.items()}

_EXCLUDED = {"리포트요약", "투경현황"}


def channel_info(name: str) -> dict | None:
    """채널 정보 조회. 편집페이지에서 표시명이 줄여지는 경우(예: 독학주식첵터정리→독학주식)를
    대비해 접두 매칭 폴백을 둔다."""
    name = (name or "").strip()
    if name in _CHANNELS:
        return _CHANNELS[name]
    for k, v in _CHANNELS.items():
        if k and (name.startswith(k) or k.startswith(name)):
            return v
    return None


def is_excluded(name: str) -> bool:
    return (name or "").strip() in _EXCLUDED


def resolve_alias(name: str) -> str:
    if not name:
        return name
    return _ALIASES.get(name.strip().lower(), name.strip())
