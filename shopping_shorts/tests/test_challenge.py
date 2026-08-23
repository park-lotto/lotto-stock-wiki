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


def test_video_code_per_platform():
    """★플랫폼마다 영상 코드를 뽑는다.

    app.py의 _media_code는 **인스타 전용**이고, 매칭 실패 시 빈 문자열이 아니라
    URL을 통째로 돌려준다(실측: 'https://youtu.be/xyz' → 'https://youtu.be/xyz').
    그걸 그대로 shortcode로 쓰면 dedup_key가 'sc:<URL>'이 되어 같은 영상의
    다른 URL 형태를 중복으로 못 잡는다. 그래서 여기서 직접 뽑는다.
    """
    ig = "https://www.instagram.com/reel/ABC123/?igsh=zz"
    assert challenge.video_code(ig, "instagram") == "ABC123"
    assert challenge.video_code("https://instagram.com/p/ABC123/", "instagram") == "ABC123"
    # 유튜브 — 짧은주소·shorts·watch 전부 같은 코드
    assert challenge.video_code("https://youtu.be/xyz789", "youtube") == "xyz789"
    assert challenge.video_code("https://www.youtube.com/shorts/xyz789", "youtube") == "xyz789"
    assert challenge.video_code("https://www.youtube.com/watch?v=xyz789", "youtube") == "xyz789"
    # 틱톡 — 긴 주소는 영상 id가 있다
    assert challenge.video_code("https://www.tiktok.com/@who/video/7412345678901234567",
                                "tiktok") == "7412345678901234567"
    # 틱톡 단축주소는 코드가 없다 → 빈 문자열(dedup_key가 URL 폴백으로 간다)
    assert challenge.video_code("https://vt.tiktok.com/ZSabc123/", "tiktok") == ""


def test_dedup_key_prefers_shortcode():
    """shortcode가 있으면 그것을 쓴다 — 같은 영상의 다른 URL 형태도 한 건으로 잡힌다."""
    a = challenge.dedup_key("https://www.instagram.com/reel/ABC123/", "ABC123")
    b = challenge.dedup_key("https://instagram.com/reel/ABC123/?igsh=xyz", "ABC123")
    assert a == b == "sc:ABC123"


def test_dedup_key_falls_back_to_normalized_url():
    """shortcode를 못 뽑으면(틱톡 단축링크 등) 정규화한 URL로."""
    a = challenge.dedup_key("https://VT.TikTok.com/ZSabc123/", "")
    b = challenge.dedup_key("https://vt.tiktok.com/ZSabc123?_r=1", "")
    assert a == b
    assert a.startswith("url:")


def test_dedup_key_different_videos_differ():
    assert challenge.dedup_key("https://vt.tiktok.com/AAA/", "") != \
           challenge.dedup_key("https://vt.tiktok.com/BBB/", "")


def test_summarize_counts_per_day():
    """제출 목록 → 날짜별 개수와 달성 여부."""
    subs = [
        {"submit_day": "2026-08-24"},
        {"submit_day": "2026-08-24"},
        {"submit_day": "2026-08-25"},
    ]
    got = challenge.summarize(subs, goal=2)
    assert got["by_day"] == {"2026-08-24": 2, "2026-08-25": 1}
    assert got["done_days"] == 1        # 8/24만 2개 달성
    assert got["total"] == 3


def test_summarize_empty():
    got = challenge.summarize([], goal=2)
    assert got["by_day"] == {}
    assert got["done_days"] == 0
    assert got["total"] == 0
