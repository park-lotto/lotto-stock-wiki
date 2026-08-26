"""1기 챌린지 — 제출 API·권한."""
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store

_REAL_CHALLENGE_FETCH = appmod._challenge_fetch   # env 픽스처가 no-op로 덮기 전의 진짜 구현


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    st = Store(str(tmp_path / "t.db"))
    st.ensure_paywall_schema()
    # 수집은 Task5에서 붙인다 — 여기서는 아무 일도 안 하게 막아둔다.
    monkeypatch.setattr(appmod, "_challenge_fetch", lambda *a, **k: None,
                        raising=False)
    return st


def _client():
    return TestClient(appmod.app)


def test_submit_requires_membership(env):
    """참가자가 아니면 403 — 아무 회원이나 제출하면 명단이 더러워진다."""
    c = _client()
    r = c.post("/api/challenge/submit", params={"url": "https://youtu.be/abc"},
               cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 403


def test_submit_saves_and_counts(env):
    env.add_challenge_member(77)
    c = _client()
    # ★challenge.video_code의 유튜브 정규식은 코드 6자 이상만 뽑는다({6,}) — 'abc'는
    #   못 뽑힌다(실측: video_code('.../abc','youtube') == ''). shortcode 값을 검증하려면
    #   6자 이상을 써야 한다.
    r = c.post("/api/challenge/submit", params={"url": "https://youtu.be/abc123"},
               cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["today"] == 1
    rows = env.list_challenge_submissions(customer_id=77)
    assert len(rows) == 1
    assert rows[0]["platform"] == "youtube"
    assert rows[0]["shortcode"] == "abc123"       # video_code가 뽑은 것


def test_submit_duplicate_rejected(env):
    env.add_challenge_member(77)
    c = _client()
    p = {"url": "https://youtu.be/abc"}
    ck = {"dash_auth": _cookie(77)}
    assert c.post("/api/challenge/submit", params=p, cookies=ck).status_code == 200
    r2 = c.post("/api/challenge/submit", params=p, cookies=ck)
    assert r2.status_code == 422
    assert "이미" in r2.json()["error"]
    assert len(env.list_challenge_submissions(customer_id=77)) == 1


def test_submit_same_video_other_url_form_is_duplicate(env):
    """★같은 영상을 다른 주소 형태로 내도 중복이다(video_code가 같은 코드를 뽑는다)."""
    env.add_challenge_member(77)
    c = _client()
    ck = {"dash_auth": _cookie(77)}
    assert c.post("/api/challenge/submit",
                  params={"url": "https://youtu.be/abc123"}, cookies=ck).status_code == 200
    r2 = c.post("/api/challenge/submit",
                params={"url": "https://www.youtube.com/shorts/abc123"}, cookies=ck)
    assert r2.status_code == 422
    assert len(env.list_challenge_submissions(customer_id=77)) == 1


def test_submit_rejects_unsupported_url(env):
    env.add_challenge_member(77)
    c = _client()
    r = c.post("/api/challenge/submit", params={"url": "https://example.com/x"},
               cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 422
    assert len(env.list_challenge_submissions(customer_id=77)) == 0


def test_submit_rejects_other_platform(env):
    """샤오홍슈·도우인 등은 챌린지 대상이 아니다(인스타·유튜브·틱톡만)."""
    env.add_challenge_member(77)
    c = _client()
    r = c.post("/api/challenge/submit",
               params={"url": "https://www.xiaohongshu.com/explore/abc"},
               cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 422


def test_submit_outside_period_rejected(env):
    """기간 밖이면 422. ★고정 날짜를 쓰지 않는다 — 상대 날짜로 만든다."""
    env.add_challenge_member(77)
    yesterday = (datetime.now(timezone.utc) + timedelta(days=-40)).strftime("%Y-%m-%d")
    long_ago = (datetime.now(timezone.utc) + timedelta(days=-70)).strftime("%Y-%m-%d")
    env.set_setting("challenge_start", long_ago)
    env.set_setting("challenge_end", yesterday)      # 이미 끝난 챌린지
    c = _client()
    r = c.post("/api/challenge/submit", params={"url": "https://youtu.be/abc"},
               cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 422
    assert "기간" in r.json()["error"]


def test_submit_inside_period_ok(env):
    env.add_challenge_member(77)
    start = (datetime.now(timezone.utc) + timedelta(days=-1)).strftime("%Y-%m-%d")
    end = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    env.set_setting("challenge_start", start)
    env.set_setting("challenge_end", end)
    c = _client()
    r = c.post("/api/challenge/submit", params={"url": "https://youtu.be/abc"},
               cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 200, r.text


def test_submit_with_no_period_set_is_open(env):
    """기간을 아직 설정 안 했으면 막지 않는다 — 설정 누락이 제출을 막으면 안 된다."""
    env.add_challenge_member(77)
    c = _client()
    r = c.post("/api/challenge/submit", params={"url": "https://youtu.be/abc"},
               cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 200, r.text


def test_mine_returns_today_count_and_list(env):
    env.add_challenge_member(77)
    c = _client()
    ck = {"dash_auth": _cookie(77)}
    c.post("/api/challenge/submit", params={"url": "https://youtu.be/a1b2c3"}, cookies=ck)
    c.post("/api/challenge/submit", params={"url": "https://youtu.be/d4e5f6"}, cookies=ck)
    r = c.get("/api/challenge/mine", cookies=ck)
    assert r.status_code == 200
    d = r.json()
    assert d["today"] == 2
    assert d["goal"] == 2
    assert len(d["items"]) == 2
    assert d["is_member"] is True


def test_mine_for_non_member_says_so(env):
    """참가자가 아니어도 200으로 안내한다 — 화면이 깨지면 안 된다."""
    r = _client().get("/api/challenge/mine", cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 200
    assert r.json()["is_member"] is False
    assert r.json()["items"] == []


def test_fetch_fills_meta_on_success(env, monkeypatch):
    """수집이 되면 썸네일·조회수가 채워지고 ok가 된다.

    ★키 이름 주의: probe_grab_meta는 yt-dlp의 view_count를 **views로 바꿔서**
    준다(media_download.py:141-145). view_count로 읽으면 조용히 항상 None이다.
    """
    env.add_challenge_member(77)
    monkeypatch.setattr(appmod, "probe_grab_meta",
                        lambda u: {"title": "제목", "thumbnail": "https://x/t.jpg",
                                   "channel": "채널", "views": 1234,
                                   "likes": 10, "comments": 3},
                        raising=False)
    monkeypatch.setattr(appmod, "_challenge_fetch", _REAL_CHALLENGE_FETCH)   # env가 덮은 no-op을 되돌린다
    sid = env.add_challenge_submission(77, "https://youtu.be/abc123", "youtube",
                                       "abc123", "sc:abc123", "2026-08-24")
    appmod._challenge_fetch(sid, "https://youtu.be/abc123", "youtube")
    row = env.list_challenge_submissions(customer_id=77)[0]
    assert row["fetch_status"] == "ok"
    assert row["title"] == "제목"
    assert row["thumb"] == "https://x/t.jpg"
    assert row["channel"] == "채널"
    assert row["views"] == 1234


def test_fetch_failure_keeps_submission(env, monkeypatch):
    """★수집이 터져도 제출은 남고 카운트는 유지된다 — 이게 가장 중요하다."""
    env.add_challenge_member(77)

    def _boom(u):
        raise RuntimeError("수집 실패")

    monkeypatch.setattr(appmod, "probe_grab_meta", _boom, raising=False)
    monkeypatch.setattr(appmod, "_challenge_fetch", _REAL_CHALLENGE_FETCH)   # env가 덮은 no-op을 되돌린다
    sid = env.add_challenge_submission(77, "https://youtu.be/abc123", "youtube",
                                       "abc123", "sc:abc123", "2026-08-24")
    appmod._challenge_fetch(sid, "https://youtu.be/abc123", "youtube")   # 예외가 새면 안 된다
    rows = env.list_challenge_submissions(customer_id=77)
    assert len(rows) == 1
    assert rows[0]["fetch_status"] == "failed"


def test_fetch_empty_meta_marks_failed(env, monkeypatch):
    """yt-dlp가 빈 값을 주면(비공개·삭제된 영상) failed — 링크는 남는다."""
    env.add_challenge_member(77)
    monkeypatch.setattr(appmod, "probe_grab_meta", lambda u: {}, raising=False)
    monkeypatch.setattr(appmod, "_challenge_fetch", _REAL_CHALLENGE_FETCH)   # env가 덮은 no-op을 되돌린다
    sid = env.add_challenge_submission(77, "https://youtu.be/abc123", "youtube",
                                       "abc123", "sc:abc123", "2026-08-24")
    appmod._challenge_fetch(sid, "https://youtu.be/abc123", "youtube")
    rows = env.list_challenge_submissions(customer_id=77)
    assert len(rows) == 1
    assert rows[0]["fetch_status"] == "failed"


def test_tiktok_is_fetched_like_others(env, monkeypatch):
    """틱톡도 수집을 **시도한다**(2026-08-25 정정).

    예전엔 "단건 조회 함수가 없다"며 통째로 skipped였는데, probe_grab_meta는
    이미 틱톡 oEmbed 폴백을 갖고 있다(media_download.py). 실측으로 썸네일·제목·
    채널이 나온다 — 조회수만 None이다.
    """
    env.add_challenge_member(77)
    called = []
    monkeypatch.setattr(appmod, "probe_grab_meta",
                        lambda u: called.append(u) or {"thumbnail": "https://t/x.jpg",
                                                       "title": "틱톡 영상",
                                                       "channel": "@someone"},
                        raising=False)
    monkeypatch.setattr(appmod, "_challenge_fetch", _REAL_CHALLENGE_FETCH)
    url = "https://www.tiktok.com/@a/video/7106594312292453675"
    sid = env.add_challenge_submission(77, url, "tiktok",
                                       "7106594312292453675",
                                       "sc:7106594312292453675", "2026-08-24")
    appmod._challenge_fetch(sid, url, "tiktok")
    row = env.list_challenge_submissions(customer_id=77)[0]
    assert called == [url]                    # 시도했다
    assert row["fetch_status"] == "ok"
    assert row["thumb"] == "https://t/x.jpg"  # 썸네일이 채워진다
    assert row["views"] is None               # 조회수는 안 나온다 — 그래도 ok다


def test_tiktok_empty_meta_is_failed(env, monkeypatch):
    """수집이 빈손이면 failed — 링크는 남는다(카운트와 무관)."""
    env.add_challenge_member(78)
    monkeypatch.setattr(appmod, "probe_grab_meta", lambda u: {}, raising=False)
    monkeypatch.setattr(appmod, "_challenge_fetch", _REAL_CHALLENGE_FETCH)
    sid = env.add_challenge_submission(78, "https://vt.tiktok.com/x", "tiktok",
                                       "", "url:vt.tiktok.com/x", "2026-08-24")
    appmod._challenge_fetch(sid, "https://vt.tiktok.com/x", "tiktok")
    assert env.list_challenge_submissions(customer_id=78)[0]["fetch_status"] == "failed"


def test_submit_schedules_background_fetch(env, monkeypatch):
    """제출하면 수집이 백그라운드 작업으로 예약된다(응답을 막지 않는다)."""
    env.add_challenge_member(77)
    seen = []
    monkeypatch.setattr(appmod, "_challenge_fetch",
                        lambda *a: seen.append(a), raising=False)
    r = _client().post("/api/challenge/submit",
                       params={"url": "https://youtu.be/abc123"},
                       cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 200, r.text
    assert len(seen) == 1
    assert seen[0][1] == "https://youtu.be/abc123"
    assert seen[0][2] == "youtube"


def _admin_env(env, monkeypatch):
    """cid 5를 관리자로 만든다.

    ★_is_admin(0)은 항상 True다(사장님 계정) — '비관리자' 역할에 cid 0을
    쓰면 통과해버려 거짓 green이 된다. 그래서 5(관리자)·77(일반)을 쓴다.

    ★access_level도 "full"로 고정한다 — 5·77·11·22는 customers 테이블에 없는
    가짜 cid라 access_level이 기본 "ranking_only"를 주고, 관리 API는
    _FREE_EXACT_ANY에 없으므로(의도적으로 안 넣음) 유료게이트가 _require_admin보다
    먼저 402로 막아버린다. 여기서 고정해야 실제로 테스트하려는
    "_require_admin이 403으로 막는지"를 검증할 수 있다.
    """
    monkeypatch.setattr(appmod, "_is_admin", lambda cid: cid == 5)
    monkeypatch.setattr(appmod, "access_level", lambda cid, now=None: "full")
    return env


def test_board_requires_admin(env, monkeypatch):
    _admin_env(env, monkeypatch)
    r = _client().get("/api/challenge/board", cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 403


def test_board_shows_each_member_per_day(env, monkeypatch):
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    env.add_challenge_member(22)
    env.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-24")
    env.add_challenge_submission(11, "https://youtu.be/b", "youtube", "b", "sc:b", "2026-08-24")
    env.add_challenge_submission(22, "https://youtu.be/c", "youtube", "c", "sc:c", "2026-08-24")
    r = _client().get("/api/challenge/board", cookies={"dash_auth": _cookie(5)})
    assert r.status_code == 200, r.text
    d = r.json()
    rows = {m["customer_id"]: m for m in d["members"]}
    assert rows[11]["by_day"]["2026-08-24"] == 2
    assert rows[11]["done_days"] == 1        # 목표 2 달성
    assert rows[22]["by_day"]["2026-08-24"] == 1
    assert rows[22]["done_days"] == 0        # 1개는 미달성
    assert d["goal"] == 2


def test_board_member_without_customer_row_still_shows(env, monkeypatch):
    """★get_customer가 None이어도 500이 나면 안 된다(참가자만 등록된 경우)."""
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    r = _client().get("/api/challenge/board", cookies={"dash_auth": _cookie(5)})
    assert r.status_code == 200, r.text
    assert r.json()["members"][0]["name"]      # 빈 문자열이 아니라 뭔가는 있어야 한다


def test_board_counts_only_period_when_set(env, monkeypatch):
    """기간을 설정하면 그 밖의 제출은 집계에서 빠진다."""
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    env.set_setting("challenge_start", "2026-08-23")
    env.set_setting("challenge_end", "2026-08-25")
    env.add_challenge_submission(11, "https://youtu.be/x", "youtube", "x", "sc:x", "2026-08-20")
    env.add_challenge_submission(11, "https://youtu.be/y", "youtube", "y", "sc:y", "2026-08-24")
    r = _client().get("/api/challenge/board", cookies={"dash_auth": _cookie(5)})
    m = r.json()["members"][0]
    assert m["total"] == 1                      # 8/20은 기간 밖
    assert "2026-08-20" not in m["by_day"]


def test_videos_requires_admin(env, monkeypatch):
    _admin_env(env, monkeypatch)
    r = _client().get("/api/challenge/videos", cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 403


def test_videos_sorted_by_views(env, monkeypatch):
    """★s1(먼저 넣음=낮은 id)이 더 높은 조회수를 갖게 해야 한다 — id DESC 기본순서와
    조회수순이 우연히 같아지면(나중 넣은 게 조회수도 높으면) 정렬을 꺼도 테스트가 속아 통과한다."""
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    s1 = env.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-24")
    s2 = env.add_challenge_submission(11, "https://youtu.be/b", "youtube", "b", "sc:b", "2026-08-24")
    env.update_challenge_submission_meta(s1, views=999, fetch_status="ok")
    env.update_challenge_submission_meta(s2, views=10, fetch_status="ok")
    r = _client().get("/api/challenge/videos", params={"sort": "views"},
                      cookies={"dash_auth": _cookie(5)})
    assert [i["views"] for i in r.json()["items"]] == [999, 10]


def test_videos_sort_by_views_handles_missing_views(env, monkeypatch):
    """★조회수가 아직 없는 항목(수집 전·실패)이 섞여도 정렬이 터지면 안 된다."""
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    s1 = env.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-24")
    env.add_challenge_submission(11, "https://vt.tiktok.com/b", "tiktok", "", "url:vt.tiktok.com/b", "2026-08-24")
    env.update_challenge_submission_meta(s1, views=5, fetch_status="ok")
    r = _client().get("/api/challenge/videos", params={"sort": "views"},
                      cookies={"dash_auth": _cookie(5)})
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 2


def test_videos_filter_by_member(env, monkeypatch):
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    env.add_challenge_member(22)
    env.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-24")
    env.add_challenge_submission(22, "https://youtu.be/b", "youtube", "b", "sc:b", "2026-08-24")
    r = _client().get("/api/challenge/videos", params={"member": 11},
                      cookies={"dash_auth": _cookie(5)})
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["customer_id"] == 11


def test_videos_filter_by_platform(env, monkeypatch):
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    env.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-24")
    env.add_challenge_submission(11, "https://vt.tiktok.com/b", "tiktok", "", "url:vt.tiktok.com/b", "2026-08-24")
    r = _client().get("/api/challenge/videos", params={"platform": "tiktok"},
                      cookies={"dash_auth": _cookie(5)})
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["platform"] == "tiktok"


def test_videos_include_member_name(env, monkeypatch):
    """카드에 누가 올렸는지 표시해야 하므로 이름이 실려야 한다."""
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    env.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-24")
    r = _client().get("/api/challenge/videos", cookies={"dash_auth": _cookie(5)})
    assert r.json()["items"][0]["member_name"]


def test_members_requires_admin(env, monkeypatch):
    _admin_env(env, monkeypatch)
    r = _client().get("/api/challenge/members", cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 403


def test_add_member_requires_admin(env, monkeypatch):
    _admin_env(env, monkeypatch)
    r = _client().post("/api/challenge/member", params={"customer_id": 11},
                       cookies={"dash_auth": _cookie(77)})
    assert r.status_code == 403
    assert env.list_challenge_members() == []


def test_admin_can_add_and_remove_member(env, monkeypatch):
    _admin_env(env, monkeypatch)
    ck = {"dash_auth": _cookie(5)}
    c = _client()
    assert c.post("/api/challenge/member", params={"customer_id": 11},
                  cookies=ck).status_code == 200
    assert env.is_challenge_member(11) is True
    assert c.post("/api/challenge/member",
                  params={"customer_id": 11, "active": 0},
                  cookies=ck).status_code == 200
    assert env.is_challenge_member(11) is False


def test_members_list_includes_inactive(env, monkeypatch):
    """해제한 사람도 목록엔 보여야 한다(다시 넣을 수 있게)."""
    _admin_env(env, monkeypatch)
    env.add_challenge_member(11)
    env.set_challenge_member_active(11, False)
    r = _client().get("/api/challenge/members", cookies={"dash_auth": _cookie(5)})
    ms = r.json()["members"]
    assert len(ms) == 1 and ms[0]["active"] == 0


def test_challenge_settings_are_admin_settable():
    """기간·목표를 admin 설정으로 저장할 수 있다 — 2기·3기를 코드 수정 없이 연다."""
    assert "challenge_start" in appmod._ADMIN_SETTING_KEYS
    assert "challenge_end" in appmod._ADMIN_SETTING_KEYS
    assert "challenge_daily_goal" in appmod._ADMIN_SETTING_KEYS
