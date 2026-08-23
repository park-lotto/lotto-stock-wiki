"""1기 챌린지 — 판정 로직(DB·HTTP 없음)."""
from datetime import datetime, timezone, timedelta

from shopping_shorts import challenge


def test_kst_day_shifts_at_utc_1500():
    """UTC 15:00 = KST 익일 00:00 — 이 경계가 하루 판정을 가른다."""
    # UTC 2026-08-24 14:59 → 아직 KST 8/24
    t1 = datetime(2026, 8, 24, 14, 59, tzinfo=timezone.utc)
    assert challenge.kst_day(t1) == "2026-08-24"
    # UTC 2026-08-24 15:00 → KST로는 벌써 8/25
    t2 = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
    assert challenge.kst_day(t2) == "2026-08-25"


def test_kst_day_naive_datetime_treated_as_utc():
    """tzinfo 없는 값이 들어와도 UTC로 보고 계산한다(조용히 하루가 밀리면 안 된다)."""
    naive = datetime(2026, 8, 24, 15, 0)
    assert challenge.kst_day(naive) == "2026-08-25"


def test_in_period_inclusive_both_ends():
    """시작일·종료일 당일은 포함이다."""
    assert challenge.in_period("2026-08-24", "2026-08-24", "2026-09-23") is True
    assert challenge.in_period("2026-09-23", "2026-08-24", "2026-09-23") is True
    assert challenge.in_period("2026-08-23", "2026-08-24", "2026-09-23") is False
    assert challenge.in_period("2026-09-24", "2026-08-24", "2026-09-23") is False


def test_in_period_open_ended_when_unset():
    """기간을 아직 설정 안 했으면 막지 않는다 — 설정 누락이 제출을 막으면 안 된다."""
    assert challenge.in_period("2026-08-24", "", "") is True
    assert challenge.in_period("2026-08-24", "2026-08-01", "") is True
    assert challenge.in_period("2026-07-01", "2026-08-01", "") is False
