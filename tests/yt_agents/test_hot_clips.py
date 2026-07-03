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


def test_find_hot_clips_computes_grades():
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_recent_avg_views") as m_avg:
        m_search.return_value = [
            {"video_id": "v1", "title": "이거 놓치면 후회", "channel_id": "UCsmall",
             "channel_title": "소형채널", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
        ]
        m_vstats.return_value = {"v1": {"view_count": 41000, "like_count": 2000, "comment_count": 50}}
        m_avg.return_value = (500.0, 100.0)  # 평소 대비 크게 튐

        results = hot_clips.find_hot_clips("반도체 조정")

    assert len(results) == 1
    r = results[0]
    assert r["video_id"] == "v1"
    assert r["view_count"] == 41000
    assert r["view_pct_above_avg"] == pytest.approx((41000 - 500) / 500 * 100, rel=0.01)
    assert r["contribution_grade"] == "Great"  # >=700%
    assert r["performance_grade"] == "Great"  # (2000-100)/100*100 = 1900% >=700
