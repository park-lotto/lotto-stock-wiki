"""'X시간 전' 실시간화(2026-08-03) — _attach_posted_at 계약.

age_hours는 수집 시점 스냅샷이라 화면 표기가 다음 수집까지 고정됐다('계속 0시간 전').
조회 경로에서 shortcode로 발행시각(posted_at)을 복원해 실어 주고, 프론트가 지금 기준으로
계산한다. 여기서는 서버 계약만 잠근다: 유효 shortcode엔 ISO UTC posted_at이 붙고,
빈/깨진 shortcode는 조용히 건너뛰며, 이미 있는 posted_at은 덮지 않는다.
"""
from shopping_shorts.app import _attach_posted_at


def test_valid_shortcode_gets_posted_at():
    # 2026-08-03 라이브 실측 릴스(집코드) — 발행 2026-08-03T00:14 UTC
    items = [{"shortcode": "DbjrYUDTx4f", "age_hours": 0.3}]
    _attach_posted_at(items)
    assert items[0]["posted_at"].startswith("2026-08-03T00:14")
    assert items[0]["posted_at"].endswith("Z")


def test_missing_or_bad_shortcode_skipped():
    items = [{"shortcode": "", "age_hours": 1}, {"age_hours": 2},
             {"shortcode": "한글불가", "age_hours": 3}]
    _attach_posted_at(items)
    assert all("posted_at" not in i for i in items)


def test_existing_posted_at_not_overwritten():
    items = [{"shortcode": "DbjrYUDTx4f", "posted_at": "keep"}]
    _attach_posted_at(items)
    assert items[0]["posted_at"] == "keep"
