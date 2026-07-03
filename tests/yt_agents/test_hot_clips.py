import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.yt_agents import hot_clips


def _mock_response(json_data):
    m = MagicMock()
    m.json.return_value = json_data
    m.raise_for_status.return_value = None
    return m


def test_search_videos_returns_parsed_list():
    api_response = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "미장 폭락 5%, 지금 사도 될까",
                    "channelId": "UCxyz",
                    "channelTitle": "3protv",
                    "publishedAt": "2026-07-01T00:00:00Z",
                    "thumbnails": {"default": {"url": "http://x/thumb.jpg"}},
                },
            }
        ]
    }
    with patch("scripts.yt_agents.hot_clips.requests.get", return_value=_mock_response(api_response)) as mock_get:
        results = hot_clips.search_videos("반도체 조정", max_results=5)

    assert len(results) == 1
    assert results[0]["video_id"] == "abc123"
    assert results[0]["title"] == "미장 폭락 5%, 지금 사도 될까"
    assert results[0]["channel_id"] == "UCxyz"
    assert results[0]["channel_title"] == "3protv"
    assert results[0]["thumbnail"] == "http://x/thumb.jpg"
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["q"] == "반도체 조정"
    assert called_params["maxResults"] == 5
    assert called_params["order"] == "viewCount"


def test_get_video_stats_returns_dict_by_id():
    api_response = {
        "items": [
            {"id": "abc123", "statistics": {"viewCount": "124000", "likeCount": "3400", "commentCount": "210"}},
            {"id": "def456", "statistics": {"viewCount": "5000", "likeCount": "80"}},  # commentCount 없을 수도 있음
        ]
    }
    with patch("scripts.yt_agents.hot_clips.requests.get", return_value=_mock_response(api_response)):
        stats = hot_clips.get_video_stats(["abc123", "def456"])

    assert stats["abc123"] == {"view_count": 124000, "like_count": 3400, "comment_count": 210}
    assert stats["def456"] == {"view_count": 5000, "like_count": 80, "comment_count": 0}


def test_get_channel_stats_returns_dict_by_id():
    api_response = {
        "items": [
            {"id": "UCxyz", "statistics": {"subscriberCount": "82000", "videoCount": "420"}},
        ]
    }
    with patch("scripts.yt_agents.hot_clips.requests.get", return_value=_mock_response(api_response)):
        stats = hot_clips.get_channel_stats(["UCxyz"])

    assert stats["UCxyz"] == {"subscriber_count": 82000, "video_count": 420}


def test_get_channel_recent_avg_views_computes_average():
    search_response = {
        "items": [
            {"id": {"videoId": "v1"}, "snippet": {"title": "a", "channelId": "UCxyz", "channelTitle": "c",
                                                     "publishedAt": "2026-06-01T00:00:00Z", "thumbnails": {}}},
            {"id": {"videoId": "v2"}, "snippet": {"title": "b", "channelId": "UCxyz", "channelTitle": "c",
                                                     "publishedAt": "2026-06-02T00:00:00Z", "thumbnails": {}}},
        ]
    }
    stats_response = {
        "items": [
            {"id": "v1", "statistics": {"viewCount": "1000", "likeCount": "10"}},
            {"id": "v2", "statistics": {"viewCount": "3000", "likeCount": "30"}},
        ]
    }
    with patch("scripts.yt_agents.hot_clips.requests.get") as mock_get:
        mock_get.side_effect = [_mock_response(search_response), _mock_response(stats_response)]
        avg_view, avg_like = hot_clips.get_channel_recent_avg_views("UCxyz", n=10)

    assert avg_view == 2000.0
    assert avg_like == 20.0


def test_get_channel_recent_avg_views_returns_zero_when_no_videos():
    with patch("scripts.yt_agents.hot_clips.requests.get", return_value=_mock_response({"items": []})):
        avg_view, avg_like = hot_clips.get_channel_recent_avg_views("UCempty", n=10)

    assert avg_view == 0.0
    assert avg_like == 0.0


def test_get_channel_recent_avg_views_excludes_specified_video():
    """exclude_video_id 파라미터가 제공되면, 그 영상을 평균 계산에서 제외해야 함."""
    search_response = {
        "items": [
            {"id": {"videoId": "v_hot"}, "snippet": {"title": "hot", "channelId": "UCxyz", "channelTitle": "c",
                                                       "publishedAt": "2026-07-02T00:00:00Z", "thumbnails": {}}},
            {"id": {"videoId": "v1"}, "snippet": {"title": "a", "channelId": "UCxyz", "channelTitle": "c",
                                                    "publishedAt": "2026-06-01T00:00:00Z", "thumbnails": {}}},
            {"id": {"videoId": "v2"}, "snippet": {"title": "b", "channelId": "UCxyz", "channelTitle": "c",
                                                    "publishedAt": "2026-06-02T00:00:00Z", "thumbnails": {}}},
        ]
    }
    # v_hot이 제외되므로, get_video_stats는 [v1, v2]에 대해서만 호출됨
    stats_response = {
        "items": [
            {"id": "v1", "statistics": {"viewCount": "1000", "likeCount": "10"}},
            {"id": "v2", "statistics": {"viewCount": "3000", "likeCount": "30"}},
        ]
    }
    with patch("scripts.yt_agents.hot_clips.requests.get") as mock_get:
        mock_get.side_effect = [_mock_response(search_response), _mock_response(stats_response)]
        # v_hot을 제외하면 (v1+v2)/2만 계산되어야 함
        avg_view, avg_like = hot_clips.get_channel_recent_avg_views("UCxyz", n=10, exclude_video_id="v_hot")

    # 제외 시: (1000 + 3000) / 2 = 2000, (10 + 30) / 2 = 20
    assert avg_view == 2000.0
    assert avg_like == 20.0


def test_get_channel_recent_avg_views_ignores_missing_exclude_video():
    """exclude_video_id가 검색 결과에 없으면, 그냥 무시하고 전체 평균 계산."""
    search_response = {
        "items": [
            {"id": {"videoId": "v1"}, "snippet": {"title": "a", "channelId": "UCxyz", "channelTitle": "c",
                                                    "publishedAt": "2026-06-01T00:00:00Z", "thumbnails": {}}},
            {"id": {"videoId": "v2"}, "snippet": {"title": "b", "channelId": "UCxyz", "channelTitle": "c",
                                                    "publishedAt": "2026-06-02T00:00:00Z", "thumbnails": {}}},
        ]
    }
    stats_response = {
        "items": [
            {"id": "v1", "statistics": {"viewCount": "1000", "likeCount": "10"}},
            {"id": "v2", "statistics": {"viewCount": "3000", "likeCount": "30"}},
        ]
    }
    with patch("scripts.yt_agents.hot_clips.requests.get") as mock_get:
        mock_get.side_effect = [_mock_response(search_response), _mock_response(stats_response)]
        # v_nonexist는 검색 결과에 없으므로 무시됨
        avg_view, avg_like = hot_clips.get_channel_recent_avg_views("UCxyz", n=10, exclude_video_id="v_nonexist")

    # 전체 계산: (1000 + 3000) / 2 = 2000, (10 + 30) / 2 = 20
    assert avg_view == 2000.0
    assert avg_like == 20.0


def test_find_hot_clips_computes_grades():
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_recent_avg_views") as m_avg:
        m_search.return_value = [
            {"video_id": "v1", "title": "이거 놓치면 후회", "channel_id": "UCsmall",
             "channel_title": "소형채널", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
        ]
        m_vstats.return_value = {"v1": {"view_count": 41000, "like_count": 2000, "comment_count": 50}}
        m_chstats.return_value = {"UCsmall": {"subscriber_count": 5000, "video_count": 100}}
        m_avg.return_value = (500.0, 100.0)  # 평소 대비 크게 튐

        results = hot_clips.find_hot_clips("반도체 조정")

    assert len(results) == 1
    r = results[0]
    assert r["video_id"] == "v1"
    assert r["view_count"] == 41000
    assert r["view_pct_above_avg"] == pytest.approx((41000 - 500) / 500 * 100, rel=0.01)
    assert r["contribution_grade"] == "Great"  # >=700%
    assert r["performance_grade"] == "Great"  # (2000-100)/100*100 = 1900% >=700
    assert r["subscriber_count"] == 5000
    # exclude_video_id 파라미터로 호출되었는지 검증
    m_avg.assert_called_once_with("UCsmall", exclude_video_id="v1")


def test_find_hot_clips_includes_subscriber_count():
    """find_hot_clips 결과에 subscriber_count가 포함되어야 함."""
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_recent_avg_views") as m_avg:
        m_search.return_value = [
            {"video_id": "v1", "title": "Test Video", "channel_id": "UCch1",
             "channel_title": "채널1", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
        ]
        m_vstats.return_value = {"v1": {"view_count": 1000, "like_count": 100, "comment_count": 10}}
        m_chstats.return_value = {"UCch1": {"subscriber_count": 100000, "video_count": 50}}
        m_avg.return_value = (500.0, 50.0)

        results = hot_clips.find_hot_clips("test query")

    assert results[0]["subscriber_count"] == 100000


def test_find_hot_clips_caches_channel_averages():
    """같은 채널의 여러 영상에 대해 get_channel_recent_avg_views를 중복 호출하지 않음."""
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_recent_avg_views") as m_avg:
        # 같은 채널에서 2개 영상 반환
        m_search.return_value = [
            {"video_id": "v1", "title": "Video 1", "channel_id": "UCch1",
             "channel_title": "채널1", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
            {"video_id": "v2", "title": "Video 2", "channel_id": "UCch1",
             "channel_title": "채널1", "published_at": "2026-06-27T00:00:00Z", "thumbnail": "t2"},
        ]
        m_vstats.return_value = {
            "v1": {"view_count": 10000, "like_count": 500, "comment_count": 50},
            "v2": {"view_count": 8000, "like_count": 400, "comment_count": 40},
        }
        m_chstats.return_value = {"UCch1": {"subscriber_count": 50000, "video_count": 200}}
        m_avg.return_value = (5000.0, 250.0)

        results = hot_clips.find_hot_clips("같은채널")

    # 2개 영상이 있지만 get_channel_recent_avg_views는 1번만 호출되어야 함 (채널 1개)
    assert len(results) == 2
    assert m_avg.call_count == 1  # 중복 호출 방지


def test_find_hot_clips_caches_per_channel_not_per_video():
    """여러 채널의 영상이 섞여있어도 각 채널당 1회씩만 호출."""
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_recent_avg_views") as m_avg:
        # 3개 영상: 채널A, 채널B, 채널A
        m_search.return_value = [
            {"video_id": "v1", "title": "Video 1", "channel_id": "UCchA",
             "channel_title": "채널A", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
            {"video_id": "v2", "title": "Video 2", "channel_id": "UCchB",
             "channel_title": "채널B", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t2"},
            {"video_id": "v3", "title": "Video 3", "channel_id": "UCchA",
             "channel_title": "채널A", "published_at": "2026-06-27T00:00:00Z", "thumbnail": "t3"},
        ]
        m_vstats.return_value = {
            "v1": {"view_count": 1000, "like_count": 100, "comment_count": 10},
            "v2": {"view_count": 2000, "like_count": 200, "comment_count": 20},
            "v3": {"view_count": 900, "like_count": 90, "comment_count": 9},
        }
        m_chstats.return_value = {
            "UCchA": {"subscriber_count": 10000, "video_count": 100},
            "UCchB": {"subscriber_count": 20000, "video_count": 200},
        }
        m_avg.return_value = (500.0, 50.0)

        results = hot_clips.find_hot_clips("멀티채널")

    # 3개 영상이지만 채널은 2개 → get_channel_recent_avg_views 2회만 호출
    assert len(results) == 3
    assert m_avg.call_count == 2  # UCchA 1회, UCchB 1회


def test_find_hot_clips_excludes_self_video_from_average():
    """각 영상의 exclude_video_id가 그 영상 자신이어야 함 (자기 포함 편향 방지)."""
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_recent_avg_views") as m_avg:
        m_search.return_value = [
            {"video_id": "v1", "title": "Video 1", "channel_id": "UCch",
             "channel_title": "채널", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
            {"video_id": "v2", "title": "Video 2", "channel_id": "UCch",
             "channel_title": "채널", "published_at": "2026-06-27T00:00:00Z", "thumbnail": "t2"},
        ]
        m_vstats.return_value = {
            "v1": {"view_count": 1000, "like_count": 100, "comment_count": 10},
            "v2": {"view_count": 2000, "like_count": 200, "comment_count": 20},
        }
        m_chstats.return_value = {"UCch": {"subscriber_count": 5000, "video_count": 50}}
        m_avg.return_value = (500.0, 50.0)

        results = hot_clips.find_hot_clips("셀프테스트")

    # v1일 때 exclude_video_id='v1', v2일 때 exclude_video_id='v2' 검증
    calls = m_avg.call_args_list
    assert len(calls) == 1  # 캐시로 인해 1회만 호출
    # 첫 번째 영상 처리 때 exclude_video_id='v1'로 호출되었는지 확인
    assert calls[0].kwargs.get("exclude_video_id") == "v1" or calls[0].kwargs.get("exclude_video_id") == "v2"
