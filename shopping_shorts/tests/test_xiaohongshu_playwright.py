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
