"""종목명 → 코드 맵. 소스: raw/wisereport/*_parsed.json 의 '종목명[코드]' 컬럼."""
import json
import re
from pathlib import Path

_WISE = Path(__file__).parent.parent.parent / "raw" / "wisereport"
_CACHE: dict[str, str] = {}


def _build() -> dict[str, str]:
    m: dict[str, str] = {}
    for f in _WISE.glob("*_parsed.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for row in data.get("corp", []):
            if len(row) < 2:
                continue
            mt = re.match(r"\s*(.+?)\s*\[(\d{6})\]", str(row[1]))
            if mt:
                m[mt.group(1).strip()] = mt.group(2)
    return m


def _ensure() -> None:
    if not _CACHE:
        _CACHE.update(_build())


def code_for(name: str) -> str | None:
    if not name:
        return None
    _ensure()
    return _CACHE.get(name.strip())


def is_korean_stock(name: str) -> bool:
    return code_for(name) is not None
