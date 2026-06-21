"""종목명 정규화: 별칭 → codemap. 한국주 추정 매칭 실패는 로그."""
import re
from pathlib import Path

from .telegram_registry import resolve_alias
from .codemap import code_for, is_korean_stock

UNMATCHED_LOG = Path(__file__).parent.parent.parent / "raw" / "telegram_unmatched.log"

# 한글이 포함되면 한국 종목일 가능성 — 외국주(영문/숫자)와 구분
_HANGUL = re.compile(r"[가-힣]")


def resolve_stock(name: str, *, date: str, channel: str) -> dict:
    """종목명을 정규화하고 코드 매칭.

    Args:
        name: 원본 종목명
        date: 날짜 (YYYY-MM-DD)
        channel: 텔레그램 채널명

    Returns:
        {
            "name": 정규화명,
            "code": 종목코드 또는 None,
            "is_korean": 한국주 여부,
            "matched": 매칭 성공 여부
        }

    부작용: 한글 포함인데 코드 없으면 raw/telegram_unmatched.log에 기록
    """
    norm = resolve_alias(name)
    code = code_for(norm)
    if code:
        return {"name": norm, "code": code, "is_korean": True, "matched": True}

    # 코드 없음: 한글 포함 = 한국주 추정인데 미매칭 → 로그
    looks_korean = bool(_HANGUL.search(norm))
    if looks_korean:
        UNMATCHED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with UNMATCHED_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{date}\t{channel}\t{norm}\n")
    # 한글 음차 외국주(마이크론 등)도 미매칭 로그에 들어옴 — 리뷰 큐는 노이즈 허용
    return {"name": norm, "code": None,
            "is_korean": looks_korean, "matched": False}
