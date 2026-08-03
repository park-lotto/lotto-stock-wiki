"""shortcode → 발행시각 복원 검증(2026-07-30 429 해소).

기준 데이터는 **라이브 실측**이다: 2026-07-30 10:36 KST 수집(job cab6059f4ffe)에 담긴
릴스의 shortcode와, 그때 인스타 REST가 준 실제 taken_at으로 계산된 age_hours.
저장된 age_hours가 0.1시간(6분) 단위 반올림이라 오차 허용치를 ±6분으로 둔다.
"""
from datetime import datetime, timezone, timedelta

from shopping_shorts.instagram_parse import (
    parse_reel_node, shortcode_to_pk, shortcode_to_timestamp,
)

_COLLECTED_AT = datetime(2026, 7, 30, 1, 36, 17, tzinfo=timezone.utc)
# (shortcode, 수집 당시 age_hours) — 라이브 실측값
_REAL = [
    ("DbZPKc2TKHC", 2.7),
    ("DbYjTrYyPV7", 9.1),
    ("DbX_PSKS0ZH", 14.3),
    ("DbXaa1HyJPe", 19.7),
    ("DbVi1H9TkSt", 37.0),
    ("DbZSoILyLgB", 2.1),
]


def test_shortcode_timestamp_matches_live_taken_at():
    for sc, age in _REAL:
        expected = _COLLECTED_AT - timedelta(hours=age)
        got = datetime.fromisoformat(shortcode_to_timestamp(sc).replace("Z", "+00:00"))
        assert abs((got - expected).total_seconds()) <= 360, (sc, got, expected)


def test_shortcode_timestamps_keep_relative_order():
    # 랭킹은 순서에 민감하다 — 복원값이 서로 뒤집히면 안 된다
    ts = [shortcode_to_timestamp(sc) for sc, _ in _REAL]
    ages = [age for _, age in _REAL]
    pairs = sorted(zip(ages, ts))
    assert [t for _, t in pairs] == sorted([t for _, t in pairs], reverse=True)


def test_bad_shortcode_returns_none_not_garbage():
    # 인코딩이 바뀌면 엉뚱한 시각으로 통과시키느니 비워서 필터에 걸리게 둔다
    assert shortcode_to_timestamp("") is None
    assert shortcode_to_timestamp("한글아님") is None
    assert shortcode_to_pk("!!!") is None
    assert shortcode_to_timestamp("A") is None            # 1970년대 → 범위 밖
    assert shortcode_to_timestamp("zzzzzzzzzzz") is None  # 먼 미래 → 범위 밖


def test_parse_reel_node_fills_timestamp_without_taken_at():
    # 목록 응답 그대로(= taken_at 없음)여도 시각이 채워져야 한다.
    # 이게 비면 ranking.build_items가 릴스를 통째로 버린다(2026-07-30 실사고).
    node = {"code": "DbZPKc2TKHC", "comment_count": 12, "like_count": 300}
    out = parse_reel_node(node, "someone")
    assert out["timestamp"], "shortcode에서 발행시각을 못 채웠다"


def test_parse_reel_node_prefers_real_taken_at():
    node = {"code": "DbZPKc2TKHC", "taken_at": 1700000000}
    out = parse_reel_node(node, "someone")
    assert out["timestamp"].startswith("2023-")
