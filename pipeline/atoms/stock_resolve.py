"""종목명 정규화: 별칭 → codemap. 외국주는 섹터 매핑. 미매칭은 로그."""
import re
import json
from pathlib import Path

from .telegram_registry import resolve_alias
from .codemap import code_for

UNMATCHED_LOG = Path(__file__).parent.parent.parent / "raw" / "telegram_unmatched.log"
FOREIGN_UNMAPPED_LOG = Path(__file__).parent.parent.parent / "raw" / "telegram_foreign_unmapped.log"

# 한글이 포함되면 한국 종목일 가능성 — 외국주(영문/숫자)와 구분
_HANGUL = re.compile(r"[가-힣]")

# 외국주 → 한국 섹터 매핑 (마이크론=DRAM→반도체, 애플=반도체+IT 등)
_FOREIGN_MAP = json.loads(
    (Path(__file__).parent / "foreign_sector_map.json").read_text(encoding="utf-8")
)


def _append_log(log_path: Path, date: str, channel: str, name: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{date}\t{channel}\t{name}\n")


def foreign_sectors(name: str) -> list[str]:
    """외국주명 → 매핑된 한국 섹터 리스트. 없으면 []. '비셰이(VSH)'처럼 괄호 표기 허용."""
    if not name:
        return []
    n = name.strip()
    if n in _FOREIGN_MAP:
        return _FOREIGN_MAP[n]
    base = re.sub(r"\(.*?\)", "", n).strip()  # 비셰이(VSH) → 비셰이
    return _FOREIGN_MAP.get(base, [])


def log_foreign_unmapped(name: str, date: str, channel: str) -> None:
    """매핑에 없는 외국주 → 큐레이션용 로그 (foreign_sector_map.json 보강 대상)."""
    _append_log(FOREIGN_UNMAPPED_LOG, date, channel, name)


def resolve_stock(name: str, *, date: str, channel: str, skip_log: bool = False) -> dict:
    """종목명을 정규화하고 코드 매칭.

    Returns:
        {"name": 정규화명, "code": 코드|None, "is_korean": looks_korean, "matched": bool}

    부작용: 한글 포함인데 코드 없으면 raw/telegram_unmatched.log에 기록.
            skip_log=True면 로그 생략 (호출부가 외국주 매핑을 직접 처리할 때).
    """
    norm = resolve_alias(name)
    code = code_for(norm)
    if code:
        return {"name": norm, "code": code, "is_korean": True, "matched": True}

    # 코드 없음: 한글 포함 = 한국주 추정
    looks_korean = bool(_HANGUL.search(norm))
    if looks_korean and not skip_log:
        _append_log(UNMATCHED_LOG, date, channel, norm)
    return {"name": norm, "code": None, "is_korean": looks_korean, "matched": False}
