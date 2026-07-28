"""프로필 크롤러 오케스트레이션(진행률·실패격리·raw스키마매핑) 검증.

★실브라우저는 띄우지 않는다 — _scrape_one을 주입해 대체한다(instagram_playwright와 동일 원칙).
브라우저 내부 동작(로그인세션·실제 파싱)은 서버 실측으로 검증한다."""
from shopping_shorts import xiaohongshu_playwright as xhp


def _fake_ok(profile_url):
    """(notes, page_url, error) — 스크레이퍼 1계정 반환 계약."""
    return ([{"note_id": "abc123", "title": "t1", "published_at": "2026-07-29T10:00:00Z",
               "likes": 100, "comments": 10, "collects": 5, "shares": 2,
               "thumbnail": "th1", "url": "https://www.rednote.com/explore/abc123"}],
            profile_url, None)


def _fake_login_wall(profile_url):
    return ([], profile_url, "login_wall")


def _fake_error(profile_url):
    return ([], profile_url, "Timeout 20000ms")


def test_fetch_notes_returns_overseas_schema_dicts():
    items = xhp.fetch_notes(["https://www.rednote.com/user/profile/u1"], _scrape_one=_fake_ok)
    assert len(items) == 1
    it = items[0]
    assert it["video_id"] == "abc123"
    assert it["media_platform"] == "xiaohongshu"
    assert it["views"] == 0
    assert it["likes"] == 100 and it["comments"] == 10
    assert it["collects"] == 5 and it["shares"] == 2
    assert it["channel_title"] == "u1"


def test_one_channel_failure_does_not_kill_the_run():
    def _mixed(u):
        return _fake_error(u) if "bad" in u else _fake_ok(u)

    items = xhp.fetch_notes(
        ["https://www.rednote.com/user/profile/good1",
         "https://www.rednote.com/user/profile/bad",
         "https://www.rednote.com/user/profile/good2"], _scrape_one=_mixed)
    assert sorted(i["channel_title"] for i in items) == ["good1", "good2"]


def test_progress_callback_reports_every_channel():
    seen = []
    xhp.fetch_notes(
        ["https://www.rednote.com/user/profile/a",
         "https://www.rednote.com/user/profile/b",
         "https://www.rednote.com/user/profile/c"],
        on_progress=lambda *a: seen.append(a), _scrape_one=_fake_ok)
    assert len(seen) == 3
    done, total, items_so_far, tally = seen[-1]
    assert (done, total, items_so_far) == (3, 3, 3)
    assert tally["ok"] == 3


def test_tally_counts_each_classification():
    # ★"w"/"e" 전체문자열 포함검사는 안 된다 — 모든 URL이 "https://www.rednote.com/..."라
    # 도메인 자체에 w(www.)·e(rednote/profile)가 다 들어있어 세 계정이 구분 안 된다.
    # URL 마지막 세그먼트(계정 식별자)만 보고 분기한다.
    def _mixed(u):
        tail = u.rsplit("/", 1)[-1]
        if tail == "w":
            return _fake_login_wall(u)
        if tail == "e":
            return _fake_error(u)
        return _fake_ok(u)

    xhp.fetch_notes(
        ["https://www.rednote.com/user/profile/a",
         "https://www.rednote.com/user/profile/w",
         "https://www.rednote.com/user/profile/e"], _scrape_one=_mixed)
    assert xhp.LAST_TALLY["ok"] == 1
    assert xhp.LAST_TALLY["login_wall"] == 1
    assert xhp.LAST_TALLY["error"] == 1


def test_empty_input_returns_empty_without_calling_scraper():
    called = []
    xhp.fetch_notes([], _scrape_one=lambda u: called.append(u) or _fake_ok(u))
    assert called == []


# ── 아래는 순수 파싱 헬퍼 단위테스트(2026-07-29 추가) — 실서버 __INITIAL_STATE__ 실측 구조를
# 고정 fixture로 박아 회귀를 잡는다. 실측: rednote.com 프로필 페이지의 window.__INITIAL_STATE__는
# 클라이언트 하이드레이션 후 user.notes가 null로 리셋되므로(비소유 프로필 한정), 라이브 JS 객체가
# 아니라 page.content()의 <script> 원문 텍스트에서 균형괄호 스캔으로 파싱해야 한다.
_FIXTURE_HTML = """<html><body><script>
window.__INITIAL_STATE__={"user":{"loggedIn":true,"notes":[[{"id":"6a68b29000000000010336d5","noteCard":{"displayTitle":"t\\u002F1","interactInfo":{"likedCount":"5"},"cover":{"infoList":[{"url":"http://img1"}],"urlDefault":"http://imgdefault"},"user":{"nickname":"樱桃呆呆"},"noteId":"6a68b29000000000010336d5","xsecToken":"TOKEN1"},"xsecToken":"TOKEN1"}],[]],"pwaAddDesktopPrompt":undefined}};
</script></body></html>"""

_FIXTURE_HTML_LOGIN_WALL = """<html><body><script>
window.__INITIAL_STATE__={"user":{"loggedIn":false,"notes":[[{"id":"","noteCard":{"displayTitle":"t","interactInfo":{"likedCount":"5"},"cover":{},"user":{"nickname":""},"noteId":"","xsecToken":""},"xsecToken":""}]]}};
</script></body></html>"""

# 좋아요 축약 표기("1.2만"류) fixture — 실측은 순수 숫자 문자열만 봤지만, int(raw)가 이런
# 값에 크래시→0으로 뭉개지면 고참여 노트가 랭킹에서 유령처럼 사라진다(코드리뷰 지적). 순수
# 숫자 케이스만 있던 기존 fixture에 축약 표기 케이스를 추가한다.
_FIXTURE_HTML_ABBREVIATED_LIKES = """<html><body><script>
window.__INITIAL_STATE__={"user":{"loggedIn":true,"notes":[[{"id":"6a68b29000000000010336d5","noteCard":{"displayTitle":"popular","interactInfo":{"likedCount":"1.2만"},"cover":{"infoList":[{"url":"http://img1"}]},"user":{"nickname":"n"},"noteId":"6a68b29000000000010336d5","xsecToken":"T"},"xsecToken":"T"}],[]]}};
</script></body></html>"""

# 노트 제목/닉네임 문자열 값 안에 영어 단어 "undefined"가 그대로 들어있는 fixture(해외용
# rednote라 영어 캡션이 섞일 수 있다) — \bundefined\b 전체치환이었다면 이 문자열이 null로
# 깨졌을 것. 콜론 바로 뒤(따옴표 없이)의 JS undefined 리터럴만 치환하는 정규식으로 고쳤다.
_FIXTURE_HTML_UNDEFINED_IN_STRING = """<html><body><script>
window.__INITIAL_STATE__={"user":{"loggedIn":true,"notes":[[{"id":"6a68b29000000000010336d5","noteCard":{"displayTitle":"my undefined behavior review","interactInfo":{"likedCount":"3"},"cover":{"infoList":[{"url":"http://img1"}]},"user":{"nickname":"undefined_fan"},"noteId":"6a68b29000000000010336d5","xsecToken":"T"},"xsecToken":"T"}],[]],"pwaAddDesktopPrompt":undefined}};
</script></body></html>"""


def test_extract_state_survives_js_undefined_literal():
    # window.__INITIAL_STATE__는 유효한 JSON이 아니라 JS 리터럴(undefined 포함)이 섞여있다.
    data = xhp._extract_state_from_html(_FIXTURE_HTML)
    assert data["user"]["loggedIn"] is True


def test_extract_notes_flattens_paginated_structure_and_maps_fields():
    data = xhp._extract_state_from_html(_FIXTURE_HTML)
    notes = xhp._notes_from_state(data)
    assert len(notes) == 1
    n = notes[0]
    assert n["note_id"] == "6a68b29000000000010336d5"
    assert n["likes"] == 5
    assert n["thumbnail"] in ("http://img1", "http://imgdefault")
    # ObjectId 앞 8자리 hex = 유닉스초 타임스탬프 → 이 노트는 2026-07-28 근방이어야 한다.
    assert n["published_at"].startswith("2026-07-28")


def test_is_logged_in_false_flags_login_wall():
    data = xhp._extract_state_from_html(_FIXTURE_HTML_LOGIN_WALL)
    assert data["user"]["loggedIn"] is False


def test_abbreviated_like_count_does_not_silently_collapse_to_zero():
    # "1.2만" 같은 축약 표기는 int(raw)에 크래시한다 — None으로 구분되어야지, 그냥 0으로
    # 뭉개져 고참여 노트가 조회수 0짜리처럼 랭킹에서 사라지면 안 된다.
    assert xhp._num("1.2만") is None
    assert xhp._likes_from_interact_info({"likedCount": "1.2만"}) is None
    # 순수 숫자 문자열(실측된 실제 형식)은 여전히 정상 파싱된다(회귀 확인).
    assert xhp._num("5") == 5
    assert xhp._likes_from_interact_info({"likedCount": "5"}) == 5

    data = xhp._extract_state_from_html(_FIXTURE_HTML_ABBREVIATED_LIKES)
    notes = xhp._notes_from_state(data)
    assert notes[0]["likes"] is None   # "값 없음"과 "진짜 0"을 구분 — fetch_notes에서만 0으로 접는다
    items = xhp.fetch_notes(["https://www.rednote.com/user/profile/popular"],
                             _scrape_one=lambda u: ([notes[0]], u, None))
    assert items[0]["likes"] == 0   # 최종 스키마는 항상 int — None은 여기서만 0으로 접힌다


def test_undefined_english_word_inside_string_value_is_not_corrupted():
    # \bundefined\b 전체치환이었다면 이 타이틀/닉네임의 "undefined"까지 null로 깨졌을 것.
    # 콜론 뒤 JS리터럴 위치의 undefined만 치환하는 정규식으로 고쳐 문자열 값은 그대로 보존된다.
    data = xhp._extract_state_from_html(_FIXTURE_HTML_UNDEFINED_IN_STRING)
    assert data is not None
    notes = xhp._notes_from_state(data)
    assert notes[0]["title"] == "my undefined behavior review"
    note_card_user = data["user"]["notes"][0][0]["noteCard"]["user"]
    assert note_card_user["nickname"] == "undefined_fan"
    # 실측된 실제 undefined 리터럴(pwaAddDesktopPrompt)은 여전히 null로 정상 치환·파싱된다(회귀).
    assert data["user"]["pwaAddDesktopPrompt"] is None
