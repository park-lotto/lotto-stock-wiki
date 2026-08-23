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


def test_tiktok_is_skipped_not_failed(env, monkeypatch):
    """틱톡은 단건 조회 함수가 없다 — 시도하지 않고 skipped로 둔다."""
    env.add_challenge_member(77)
    called = []
    monkeypatch.setattr(appmod, "probe_grab_meta",
                        lambda u: called.append(u) or {}, raising=False)
    monkeypatch.setattr(appmod, "_challenge_fetch", _REAL_CHALLENGE_FETCH)   # env가 덮은 no-op을 되돌린다
    sid = env.add_challenge_submission(77, "https://vt.tiktok.com/x", "tiktok",
                                       "", "url:vt.tiktok.com/x", "2026-08-24")
    appmod._challenge_fetch(sid, "https://vt.tiktok.com/x", "tiktok")
    assert env.list_challenge_submissions(customer_id=77)[0]["fetch_status"] == "skipped"
    assert called == []          # 시도조차 안 했다


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
