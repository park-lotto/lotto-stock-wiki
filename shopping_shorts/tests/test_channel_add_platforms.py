"""채널수집 버튼(2026-08-18): 인스타·틱톡에 이어 유튜브·쓰레드도 등록되는가.

왜 이 테스트가 필요한가: 플랫폼마다 '어디에 넣어야 수집이 잡느냐'가 다르다
(인스타=discovered_channels / 나머지=platform_seeds account). 한 군데라도 엉뚱한
표에 들어가면 버튼은 '✅ 등록 완료'라고 뜨는데 수집은 영영 안 도는, 가장 알아채기
어려운 실패가 된다. 그래서 '어느 표에 무슨 값이 들어갔나'를 못박아 둔다.
"""
from unittest.mock import patch

import pytest

from shopping_shorts import app as ap
from shopping_shorts.store import Store


@pytest.fixture()
def db(tmp_path):
    # tmp_path를 쓴다 — TemporaryDirectory는 윈도우에서 sqlite 핸들이 남아 teardown이 깨진다.
    path = str(tmp_path / "t.db")
    Store(path)
    return path


def _call(db_path, url="", username=""):
    with patch.object(ap, "DB_PATH", db_path), \
         patch.object(ap, "_require_admin", lambda req: None):
        return ap.api_discover_add_by_url(request=None, url=url, username=username)


def _body(resp):
    return resp.body.decode("utf-8")


def test_threads_post_url_becomes_threads_account_seed(db):
    resp = _call(db, url="https://www.threads.com/@shop_lotto/post/DcAbCdEf")
    assert "등록 완료" in _body(resp)
    seeds = [s for s in Store(db).list_seeds("threads") if s["kind"] == "account"]
    assert [s["value"] for s in seeds] == ["shop_lotto"], "쓰레드는 핸들만 시드로 들어간다"


def test_threads_profile_url_and_duplicate_is_reported(db):
    _call(db, url="https://www.threads.net/@shop_lotto")
    resp = _call(db, url="https://www.threads.net/@shop_lotto")
    assert "이미 등록된 채널" in _body(resp)
    assert len([s for s in Store(db).list_seeds("threads") if s["kind"] == "account"]) == 1


def test_threads_never_lands_in_instagram_table(db):
    """쓰레드 핸들이 인스타 추적목록에 섞이면 인스타 수집이 헛돈다 — 그 경로 차단 확인."""
    _call(db, url="https://www.threads.com/@shop_lotto/post/DcAbCdEf")
    assert Store(db).discovered_channels() == []


def test_youtube_channel_page_uses_handle_url_without_api(db):
    # 채널 페이지는 URL만으로 결정 — API(yt_channels_from_videos)를 안 부른다.
    with patch.object(ap, "yt_channels_from_videos",
                      lambda urls: pytest.fail("채널 페이지에서 API를 부르면 안 된다")):
        resp = _call(db, url="https://www.youtube.com/@ssulpulda/shorts")
    assert "등록 완료" in _body(resp)
    seeds = [s for s in Store(db).list_seeds("youtube") if s["kind"] == "account"]
    assert [s["value"] for s in seeds] == ["https://www.youtube.com/@ssulpulda"]


def test_youtube_shorts_url_resolves_channel_via_shared_helper(db):
    with patch.object(ap, "yt_channels_from_videos",
                      lambda urls: [{"channel_url": "https://www.youtube.com/channel/UC123",
                                     "channel_title": "썰풀다"}]):
        resp = _call(db, url="https://www.youtube.com/shorts/AbCdEfGhIjK")
    assert "등록 완료" in _body(resp) and "썰풀다" in _body(resp)
    seeds = [s for s in Store(db).list_seeds("youtube") if s["kind"] == "account"]
    assert [s["value"] for s in seeds] == ["https://www.youtube.com/channel/UC123"], \
        "값 형식은 /api/seeds/from_youtube_videos와 같아야 같은 채널로 본다"


def test_youtube_unresolvable_video_reports_failure_not_silent_success(db):
    with patch.object(ap, "yt_channels_from_videos", lambda urls: []):
        resp = _call(db, url="https://www.youtube.com/shorts/AbCdEfGhIjK")
    assert "못 찾았어요" in _body(resp)
    assert Store(db).list_seeds("youtube") == []
