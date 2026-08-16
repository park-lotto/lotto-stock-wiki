"""CN 검색 백엔드 4종(Playwright·Apify × 샤오홍슈·도우인).

★계정과 프록시는 **함께** 정한다(0순위-B). 따로 정하면 어긋난다 —
2026-08-09 인스타 실사고(계정↔IP 불일치로 챌린지)와 같은 함정.

각 백엔드의 계약: (keyword, max_results) -> list[dict]
  - 성공: normalize()를 거친 dict 리스트
  - 실패/차단: 빈 리스트를 돌려준다(예외를 밖으로 던지지 않는다).
    폴백 판정은 cn_search가 한다 — 백엔드는 '못 가져왔다'만 알린다.
"""
import os

_SHORT_MAX_SECS = 90

_SCHEMA_KEYS = ("url", "title", "thumbnail", "play_url",
                "channel", "likes", "views", "duration")


def _num(v):
    """정수로 바꿀 수 있으면 int, 아니면 None. '1.2만' 같은 문자값은 버린다.

    ★OverflowError까지 잡는다 — float('inf')는 ValueError가 아니라 OverflowError다.
    normalize는 백엔드가 행마다 부르므로, 여기서 예외가 새면 그 백엔드 결과가
    통째로 죽는다(모듈 계약: 백엔드는 예외를 밖으로 던지지 않는다)."""
    if isinstance(v, bool):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError, OverflowError):
        return None


def normalize(row, platform):
    """백엔드 원본 dict → 프론트가 기대하는 고정 스키마.

    ★키를 항상 전부 채운다. 빠진 키가 있으면 프론트 카드가 조용히 깨지는데,
    화면에선 '결과가 안 나온다'로만 보여 원인을 못 찾는다."""
    out = {"platform": platform}
    for k in _SCHEMA_KEYS:
        out[k] = row.get(k)
    out["title"] = out["title"] or ""
    out["channel"] = out["channel"] or ""
    out["likes"] = _num(out["likes"])
    out["views"] = _num(out["views"])
    dur = _num(out["duration"])
    out["duration"] = dur
    out["is_short"] = dur is None or dur <= _SHORT_MAX_SECS
    return out
