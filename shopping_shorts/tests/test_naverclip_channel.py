# -*- coding: utf-8 -*-
"""네이버 클립 **채널** 수집(2026-08-31) — 벤치마킹 채널을 매일 훑기 위한 것.

키워드 검색(naverclip_search.search)과 다른 축이다:
  · 키워드 = "뷰티에서 뭐가 터지나"(넓게)
  · 채널   = "이 15명이 오늘 뭘 올렸나"(좁게·매일)

실측으로 확인한 경로(2026-08-31, 브라우저 네트워크 관찰):
  ① 핸들 → 프로필   /clip/profiles?clipId=<핸들>       ← 헤더 없이 200
  ② 프로필 → 세션   /feed/content  (단수)              ← body.session.id
  ③ 세션 → 목록     /feed/contents (복수) + sessionId  ← 61건/회

★②를 건너뛰고 ③을 바로 부르면 400 `Session not found or expired`다.
★③에는 `x-creator-hub-sid: clip` 헤더가 필요하다.
"""
import json

import pytest

from shopping_shorts import naverclip_search as nc


# ── 실제 응답에서 뜬 모양(2026-08-31 temtembara) ────────────────────────
_PROFILE_BODY = {
    "profileId": "esHccUUDtdehHkz8NEcI",
    "nickname": "템템바라",
    "endUrl": "https://clip.naver.com/@temtembara",
    "profileImageUrl": "https://clip-service-phinf.pstatic.net/x.jpg",
    "summary": {"numberOfPosts": 332, "numberOfFollowers": 363,
                "numberOfFollowings": 33},
    "tabCounts": {"ALL": {"total": 332, "video": 307, "post": 25}},
}


def _content(mid, desc, views, when="2026-08-30T21:46:36.000+0900"):
    return {"mediaId": mid, "mediaType": "SHORT_FORM", "description": desc,
            "publishedTime": when, "vod": {"count": views},
            "profile": {"nickname": "템템바라", "profileId": "esHccUUDtdehHkz8NEcI",
                        "endUrl": "https://clip.naver.com/@temtembara"}}


@pytest.fixture()
def api(monkeypatch):
    """URL → 응답(dict)을 정해두고 _get을 그걸로 답하게 한다. 호출 URL도 기록."""
    calls = []

    def _fake(url, referer, headers=None):
        calls.append(url)
        if "/clip/profiles" in url:
            return {"header": {"code": 0}, "body": _PROFILE_BODY}
        if "/feed/content?" in url:          # 단수 — 세션 발급
            return {"header": {"code": 0}, "body": {
                "session": {"id": "sess-1", "hasMore": True, "pageSize": 18},
                "card": {"content": _content("M0", "첫 영상", 3)}}}
        if "/feed/contents?" in url:         # 복수 — 목록
            assert "sessionId=sess-1" in url, "세션을 안 넘기면 서버가 400을 준다"
            return {"header": {"code": 0}, "body": {"cards": [
                {"content": _content("M1", "두번째", 51)},
                {"content": _content("M2", "세번째", 110)},
            ]}}
        raise AssertionError(f"예상 못 한 URL: {url}")

    monkeypatch.setattr(nc, "_get", _fake)
    return calls


def test_profile_by_handle(api):
    p = nc.profile_by_handle("temtembara")
    assert p["profile_id"] == "esHccUUDtdehHkz8NEcI"
    assert p["nickname"] == "템템바라"
    assert p["handle"] == "temtembara"
    assert p["followers"] == 363
    assert p["videos"] == 307


def test_profile_missing_returns_empty(monkeypatch):
    """없는 핸들 — 예외가 아니라 빈 dict. 한 채널이 사라져도 나머지는 돌아야 한다."""
    monkeypatch.setattr(nc, "_get", lambda *a, **k: {"header": {"code": 0}, "body": {}})
    assert nc.profile_by_handle("없는핸들") == {}


def test_channel_videos_uses_session(api):
    """★세션 발급(단수)을 **먼저** 부르고 그 id로 목록(복수)을 불러야 한다."""
    rows = nc.channel_videos("esHccUUDtdehHkz8NEcI", want=30)
    single = [u for u in api if "/feed/content?" in u]
    plural = [u for u in api if "/feed/contents?" in u]
    assert single and plural, "두 호출이 다 있어야 한다"
    assert api.index(single[0]) < api.index(plural[0]), "세션을 먼저 받아야 한다"
    # 단수 응답의 카드 1건 + 복수 응답 2건 = 3건. 첫 카드를 버리면 안 된다.
    assert [r["media_id"] for r in rows] == ["M0", "M1", "M2"]


def test_channel_videos_row_shape(api):
    rows = nc.channel_videos("esHccUUDtdehHkz8NEcI")
    r = rows[-1]
    assert r["views"] == 110
    assert r["channel"] == "템템바라"
    # ★주소는 clip_url 한 곳에서만 만든다 — 검색 경로와 같은 형식이어야 한다.
    #   clip.naver.com/clips/... 꼴을 지어내면 전부 404다(2026-08-31 실측).
    assert r["url"] == nc.clip_url("M2")
    assert "seedMediaId=M2" in r["url"] and "m.naver.com/shorts" in r["url"]
    assert r["posted_at"].startswith("2026-08-30")


def test_channel_videos_dedups(monkeypatch):
    """같은 mediaId가 두 번 오면 한 번만 남긴다(페이징이 겹칠 수 있다)."""
    def _fake(url, referer, headers=None):
        if "/feed/content?" in url:
            return {"header": {"code": 0}, "body": {
                "session": {"id": "s"}, "card": {"content": _content("SAME", "a", 1)}}}
        return {"header": {"code": 0}, "body": {"cards": [
            {"content": _content("SAME", "a", 1)},
            {"content": _content("OTHER", "b", 2)}]}}
    monkeypatch.setattr(nc, "_get", _fake)
    rows = nc.channel_videos("PID")
    assert [r["media_id"] for r in rows] == ["SAME", "OTHER"]


def test_get_sends_creator_hub_header():
    """★`x-creator-hub-sid: clip`이 빠지면 목록 API가 400이다(실측).

    _get이 헤더를 실어 보낼 수 있어야 채널 경로가 성립한다.
    """
    import inspect
    src = inspect.getsource(nc._get)
    assert "headers" in src, "_get이 추가 헤더를 못 받으면 채널 API를 못 부른다"


def test_handle_from_url():
    assert nc.handle_from_url("https://clip.naver.com/@temtembara") == "temtembara"
    assert nc.handle_from_url("https://clip.naver.com/@a_b-1?tab=all") == "a_b-1"
    assert nc.handle_from_url("") == ""
    assert nc.handle_from_url("https://clip.naver.com/nothandle") == ""


def test_clip_url_is_single_source():
    """★검색과 채널이 **같은 함수**로 주소를 만들어야 한다(0순위-B).

    2026-08-31: 채널 경로를 새로 짜면서 `clip.naver.com/clips/mv/video/<id>`라는
    주소를 지어냈는데 **404**였다(후보 7종 전부 404). 검색 경로에는 이미 되는
    주소가 있었으므로, 지어내지 말고 그걸 쓴다.
    """
    import inspect
    assert "m.naver.com/shorts" in nc.clip_url("X")
    assert "seedMediaId=X" in nc.clip_url("X")
    # 채널 행 생성기가 주소를 직접 조립하면 안 된다
    src = inspect.getsource(nc._row_from_content)
    assert "clip_url(" in src
    assert "https://" not in src.split('"url"')[1].split(",")[0]


# ── API 배선 (2026-08-31) ──────────────────────────────────────────────
# ★import만 통과하는 테스트는 의미가 없다(메모리 reference_모듈import_런타임NameError).
#   실제로 엔드포인트를 **호출해서** 응답을 본다.

def test_channel_collect_endpoint_wired(monkeypatch):
    """/api/naverclip/channels/collect 가 실제로 돌고 저장 계약을 지키는가."""
    from fastapi.testclient import TestClient
    from shopping_shorts import app as ss

    monkeypatch.setattr(ss, "_require_admin", lambda r: None)
    monkeypatch.setattr(nc, "profile_by_handle",
                        lambda h: {"profile_id": "P" + h, "nickname": h,
                                   "followers": 100, "handle": h})
    monkeypatch.setattr(nc, "channel_videos", lambda pid, want=60: [
        {"media_id": "M" + pid, "url": nc.clip_url("M" + pid), "title": "t",
         "channel": "ch", "channel_id": pid, "channel_url": "",
         "views": 7, "posted_at": "2026-08-30T00:00:00+00:00"}])
    monkeypatch.setattr(nc, "_fetch_card", lambda mid: {
        "views": 7, "likes": 1, "comments": 2, "duration": 15,
        "thumbnail": "http://t/x.jpg", "play_url": "http://v/x.mp4"})

    saved = {}

    class _FakeStore:
        def __init__(self, *a, **k):
            pass

        def list_seeds(self, platform):
            return []

        def merge_last_run_platform(self, platform, items, now):
            saved["platform"] = platform
            saved["items"] = items
            return len(items), len(items)

    monkeypatch.setattr(ss, "Store", _FakeStore)

    r = TestClient(ss.app).post("/api/naverclip/channels/collect",
                                json={"handles": ["a", "b"], "per_channel": 10})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] and d["channels"] == 2
    assert saved["platform"] == "naverclip", "키워드 수집과 같은 platform이어야 랭킹에 뜬다"
    it = saved["items"][0]
    # 상세 보강이 실제로 실렸는가 — 목록엔 조회수만 오므로 이게 비면 지표가 죽는다
    assert it["likes"] == 1 and it["comments"] == 2 and it["duration"] == 15
    assert it["thumbnail"] and it["video_url"]
    assert it["keyword"].startswith("@"), "어느 채널에서 왔는지 남아야 한다"
    assert it["shortcode"] and it["url"]


def test_seed_rejects_unknown_handle(monkeypatch):
    """★없는 핸들은 심지 않는다 — 오타를 심으면 매일 0건을 긁는다."""
    from fastapi.testclient import TestClient
    from shopping_shorts import app as ss

    monkeypatch.setattr(ss, "_require_admin", lambda r: None)
    monkeypatch.setattr(nc, "profile_by_handle",
                        lambda h: {"profile_id": "P"} if h == "good" else {})
    added = []

    class _FakeStore:
        def __init__(self, *a, **k):
            pass

        def add_seed(self, platform, kind, value):
            added.append((platform, kind, value))

    monkeypatch.setattr(ss, "Store", _FakeStore)
    r = TestClient(ss.app).post("/api/naverclip/channels/seed",
                                json={"handles": ["good", "@오타채널"]})
    d = r.json()
    assert d["added"] == ["good"]
    assert d["not_found"] == ["@오타채널"]
    assert added == [("naverclip", "account", "good")]
