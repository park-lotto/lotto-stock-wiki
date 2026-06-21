"""텔레그램 채널 레지스트리 + 종목명 별칭."""
import json
from pathlib import Path

_DIR = Path(__file__).parent
_CHANNELS = json.loads((_DIR / "telegram_channels.json").read_text(encoding="utf-8"))
_ALIASES_RAW = json.loads((_DIR / "stock_aliases.json").read_text(encoding="utf-8"))
_ALIASES = {k.lower(): v for k, v in _ALIASES_RAW.items()}

_EXCLUDED = {"리포트요약", "투경현황"}


def channel_info(name: str) -> dict | None:
    return _CHANNELS.get((name or "").strip())


def is_excluded(name: str) -> bool:
    return (name or "").strip() in _EXCLUDED


def resolve_alias(name: str) -> str:
    if not name:
        return name
    return _ALIASES.get(name.strip().lower(), name.strip())
