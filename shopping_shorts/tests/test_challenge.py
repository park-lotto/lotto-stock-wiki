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


# ── 임베드 주소(2026-08-25) ───────────────────────────────────────────
# 관리 화면에서 카드를 누르면 플랫폼으로 튕겨 나가 탭이 100개 열리던 것을
# 화면 안 재생으로 바꿨다. 주소를 만드는 판단은 여기 한 곳에만 있다.

def test_embed_url_three_platforms():
    assert challenge.embed_url("https://www.youtube.com/shorts/xY12345",
                               "youtube") == "https://www.youtube.com/embed/xY12345"
    assert challenge.embed_url("https://www.instagram.com/reel/ABC123def/",
                               "instagram") == "https://www.instagram.com/p/ABC123def/embed"
    assert challenge.embed_url("https://www.tiktok.com/@a/video/7106594312292453675",
                               "tiktok") == "https://www.tiktok.com/embed/v2/7106594312292453675"


def test_embed_url_empty_when_no_code():
    """틱톡 단축링크엔 영상 id가 없다 → 빈 문자열. 화면은 원본 링크로 폴백한다."""
    assert challenge.embed_url("https://vt.tiktok.com/ZSabc/", "tiktok") == ""
    assert challenge.embed_url("https://example.com/x", "") == ""


def test_embed_url_reuses_given_code():
    """DB에 저장된 shortcode를 넘기면 그것을 쓴다 — 같은 판단을 두 번 하지 않는다."""
    assert challenge.embed_url("https://vt.tiktok.com/ZSabc/", "tiktok",
                               "999888777") == "https://www.tiktok.com/embed/v2/999888777"


# ── 달력 3칸 개편 (2026-08-29) ──────────────────────────────────────
class TestDayList:
    def test_기간_전체를_하루도_빠짐없이(self):
        days = challenge.day_list("2026-08-28", "2026-09-26")
        assert len(days) == 30
        assert days[0] == "2026-08-28"
        assert days[-1] == "2026-09-26"

    def test_월말_넘어가도_이어진다(self):
        days = challenge.day_list("2026-08-30", "2026-09-02")
        assert days == ["2026-08-30", "2026-08-31", "2026-09-01", "2026-09-02"]

    def test_하루짜리(self):
        assert challenge.day_list("2026-08-28", "2026-08-28") == ["2026-08-28"]

    def test_기간_미설정이면_빈목록(self):
        # 달력을 못 그린다 → 화면은 목록 탭으로 폴백한다(제출은 여전히 된다)
        assert challenge.day_list("", "2026-09-26") == []
        assert challenge.day_list("2026-08-28", "") == []
        assert challenge.day_list("", "") == []

    def test_거꾸로_된_기간은_빈목록(self):
        assert challenge.day_list("2026-09-26", "2026-08-28") == []


class TestStreak:
    def test_오늘까지_사흘_연속(self):
        by = {"2026-08-27": 2, "2026-08-28": 3, "2026-08-29": 2}
        assert challenge.streak(by, "2026-08-29", goal=2) == 3

    def test_오늘이_아직_미달성이면_어제부터_센다(self):
        # 오전에 열었다고 어제까지의 연속기록이 0으로 보이면 안 된다
        by = {"2026-08-27": 2, "2026-08-28": 2, "2026-08-29": 1}
        assert challenge.streak(by, "2026-08-29", goal=2) == 2

    def test_중간에_끊기면_끊긴_뒤부터(self):
        by = {"2026-08-26": 2, "2026-08-27": 0, "2026-08-28": 2, "2026-08-29": 2}
        assert challenge.streak(by, "2026-08-29", goal=2) == 2

    def test_하나도_없으면_0(self):
        assert challenge.streak({}, "2026-08-29", goal=2) == 0

    def test_오늘이_비면_0(self):
        assert challenge.streak({"2026-08-28": 2}, "", goal=2) == 0

    def test_목표_3이면_2개는_연속이_아니다(self):
        by = {"2026-08-28": 3, "2026-08-29": 2}
        assert challenge.streak(by, "2026-08-29", goal=3) == 1


def test_naverclip_code_and_no_embed():
    """네이버 클립: seedMediaId를 뽑고, 임베드 주소는 만들지 않는다.

    ★주소를 지어내면 404다(2026-08-31 실측 후보 7종 전부) — 빈 문자열이면
    화면이 링크로 폴백한다.
    """
    mid = "51782434BD964B039EA620B7933A170CBA14"
    u = ("https://m.naver.com/shorts?serviceType=CLIP&mediaType=VOD"
         "&seedMediaId=" + mid)
    assert challenge.video_code(u, "naverclip") == mid
    assert challenge.dedup_key(u, challenge.video_code(u, "naverclip")) == "sc:" + mid
    assert challenge.embed_url(u, "naverclip") == ""
