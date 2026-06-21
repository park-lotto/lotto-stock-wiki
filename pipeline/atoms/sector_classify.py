"""섹터 택소노미(sectors.json) + 종목 섹터 결정.

우선순위: 외국 오버라이드 map → Gemini hint(목록 정규화) → 기타.
"""
import json
from pathlib import Path

from .stock_resolve import foreign_sectors

_SECTORS = json.loads(
    (Path(__file__).parent / "sectors.json").read_text(encoding="utf-8")
)["sectors"]


def sectors_list() -> list[str]:
    return list(_SECTORS)


def _norm_to_taxonomy(hint: str) -> str | None:
    """hint를 택소노미 1개로 정규화. 정확매칭 → 부분매칭 → None."""
    if not hint:
        return None
    h = hint.strip()
    if h in _SECTORS:
        return h
    for s in _SECTORS:
        if s != "기타" and (s in h or h in s):
            return s
    return None


def resolve_sector(name: str, hint: str, *, is_foreign: bool) -> tuple[list[str], str]:
    if is_foreign:
        fs = foreign_sectors(name)
        if fs:
            return list(fs), "map"
    if hint and hint.strip() in _SECTORS:
        return [hint.strip()], "gemini"
    norm = _norm_to_taxonomy(hint)
    if norm:
        return [norm], "gemini_norm"
    return ["기타"], "fallback"
