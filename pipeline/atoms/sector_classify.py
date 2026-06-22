"""섹터 택소노미(sectors.json) + 종목 섹터 결정.

우선순위: 외국 오버라이드 map → Gemini hint(목록 정규화)
         → asset 자체 정규화 → 국내 종목→섹터 맵 → 기타.
"""
import json
from pathlib import Path

from .stock_resolve import foreign_sectors

_SECTORS = json.loads(
    (Path(__file__).parent / "sectors.json").read_text(encoding="utf-8")
)["sectors"]

# 국내 종목 → 섹터 맵 (build_stock_sector_map.py로 생성). 모듈 1회 로드.
_STOCK_MAP_FILE = Path(__file__).parent / "stock_sector_map.json"
_STOCK_MAP: dict[str, str] = (
    json.loads(_STOCK_MAP_FILE.read_text(encoding="utf-8"))
    if _STOCK_MAP_FILE.exists() else {}
)


def stock_sector(name: str) -> str | None:
    """종목명 → 섹터 (국내 큐레이션 맵). 없으면 None."""
    if not name:
        return None
    return _STOCK_MAP.get(name.strip())


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
    # hint 실패 → asset 이름 자체가 섹터명인지 (예: asset="반도체")
    norm_name = _norm_to_taxonomy(name)
    if norm_name:
        return [norm_name], "asset_norm"
    # 국내 종목명 → 큐레이션 맵
    sm = stock_sector(name)
    if sm:
        return [sm], "stock_map"
    return ["기타"], "fallback"
