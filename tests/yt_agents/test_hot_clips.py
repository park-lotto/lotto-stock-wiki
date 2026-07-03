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
    # _get_channel_raw_videos를 직접 테스트 (이미 내부에서 get_video_stats를 호출)
    with patch("scripts.yt_agents.hot_clips._get_channel_raw_videos") as m_raw:
        # 채널에 v_hot, v1, v2 있음 (raw 데이터)
        m_raw.return_value = [
            {"video_id": "v_hot", "view_count": 5000, "like_count": 50},
            {"video_id": "v1", "view_count": 1000, "like_count": 10},
            {"video_id": "v2", "view_count": 3000, "like_count": 30},
        ]
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
         patch("scripts.yt_agents.hot_clips._get_channel_raw_videos") as m_raw:
        m_search.return_value = [
            {"video_id": "v1", "title": "이거 놓치면 후회", "channel_id": "UCsmall",
             "channel_title": "소형채널", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
        ]
        m_vstats.return_value = {"v1": {"view_count": 41000, "like_count": 2000, "comment_count": 50}}
        m_chstats.return_value = {"UCsmall": {"subscriber_count": 5000, "video_count": 100}}
        # 채널의 최근 영상 데이터 (v1과 다른 영상들)
        m_raw.return_value = [
            {"video_id": "v1", "view_count": 41000, "like_count": 2000},
            {"video_id": "v_old1", "view_count": 500, "like_count": 100},
            {"video_id": "v_old2", "view_count": 500, "like_count": 100},
        ]

        results = hot_clips.find_hot_clips("반도체 조정")

    assert len(results) == 1
    r = results[0]
    assert r["video_id"] == "v1"
    assert r["view_count"] == 41000
    # v1을 제외한 평균: (500 + 500) / 2 = 500
    # 다만 검색 결과에는 v1만 있으므로, 평균은 (500+500)/2 = 500
    assert r["view_pct_above_avg"] == pytest.approx((41000 - 500) / 500 * 100, rel=0.01)
    assert r["contribution_grade"] == "Great"  # >=700%
    assert r["performance_grade"] == "Great"  # (2000-100)/100*100 = 1900% >=700
    assert r["subscriber_count"] == 5000


def test_find_hot_clips_includes_subscriber_count():
    """find_hot_clips 결과에 subscriber_count가 포함되어야 함.

    또한 view_pct_above_avg와 contribution_grade도 검증하여
    평균 계산 로직이 올바르게 실행되고 있음을 확인.
    """
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips._get_channel_raw_videos") as m_raw:
        m_search.return_value = [
            {"video_id": "v1", "title": "Test Video", "channel_id": "UCch1",
             "channel_title": "채널1", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
        ]
        m_vstats.return_value = {"v1": {"view_count": 1000, "like_count": 100, "comment_count": 10}}
        m_chstats.return_value = {"UCch1": {"subscriber_count": 100000, "video_count": 50}}
        # 채널의 최근 영상: v1과 2개의 다른 영상 (평균 계산용)
        m_raw.return_value = [
            {"video_id": "v1", "view_count": 1000, "like_count": 100},
            {"video_id": "v_old1", "view_count": 500, "like_count": 50},
            {"video_id": "v_old2", "view_count": 500, "like_count": 50},
        ]

        results = hot_clips.find_hot_clips("test query")

    assert len(results) == 1
    r = results[0]

    # 구독자 수 검증
    assert r["subscriber_count"] == 100000

    # 평균 계산 검증: v1을 제외한 (v_old1 + v_old2)/2 = 500
    # view_pct_above_avg = (1000 - 500) / 500 * 100 = 100.0%
    expected_avg_view = (500 + 500) / 2
    expected_pct = round((1000 - expected_avg_view) / expected_avg_view * 100, 1)
    assert r["view_pct_above_avg"] == pytest.approx(expected_pct, rel=0.01)
    assert r["view_pct_above_avg"] == 100.0  # 정확히 100%

    # contribution_grade 검증: 100% >= 200% ? No → "Normal"
    # (100은 200 미만이므로)
    assert r["contribution_grade"] == "Normal"


def test_find_hot_clips_caches_channel_averages():
    """같은 채널의 여러 영상에 대해 _get_channel_raw_videos를 중복 호출하지 않음."""
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips._get_channel_raw_videos") as m_raw:
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
        m_raw.return_value = [
            {"video_id": "v1", "view_count": 10000, "like_count": 500},
            {"video_id": "v2", "view_count": 8000, "like_count": 400},
        ]

        results = hot_clips.find_hot_clips("같은채널")

    # 2개 영상이 있지만 _get_channel_raw_videos는 1번만 호출되어야 함 (채널 1개)
    assert len(results) == 2
    assert m_raw.call_count == 1  # 중복 호출 방지


def test_find_hot_clips_caches_per_channel_not_per_video():
    """여러 채널의 영상이 섞여있어도 각 채널당 1회씩만 호출."""
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips._get_channel_raw_videos") as m_raw:
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
        # 채널별 raw 비디오 데이터
        def raw_side_effect(ch_id, n=10):
            if ch_id == "UCchA":
                return [
                    {"video_id": "v1", "view_count": 1000, "like_count": 100},
                    {"video_id": "v3", "view_count": 900, "like_count": 90},
                ]
            elif ch_id == "UCchB":
                return [
                    {"video_id": "v2", "view_count": 2000, "like_count": 200},
                ]
            return []

        m_raw.side_effect = raw_side_effect

        results = hot_clips.find_hot_clips("멀티채널")

    # 3개 영상이지만 채널은 2개 → _get_channel_raw_videos 2회만 호출
    assert len(results) == 3
    assert m_raw.call_count == 2  # UCchA 1회, UCchB 1회


def test_find_hot_clips_excludes_self_video_from_average():
    """같은 채널의 여러 영상에서 각 영상이 정확히 '자신을 제외한' 평균을 사용해야 함.

    Scenario: 채널 UCch에 3개 영상
    - v1: 50000 views
    - v2: 40000 views
    - v3: 1000 views

    Expected:
    - v1의 평균 = (v2+v3)/2 = (40000+1000)/2 = 20500 (v1 제외)
    - v2의 평균 = (v1+v3)/2 = (50000+1000)/2 = 25500 (v2 제외)
    - v3의 평균 = (v1+v2)/2 = (50000+40000)/2 = 45000 (v3 제외)

    v1, v2는 다른 평균을 사용해야 함 (버그: 기존 코드는 같은 캐시값을 재사용했음).
    """
    with patch("scripts.yt_agents.hot_clips.search_videos") as m_search, \
         patch("scripts.yt_agents.hot_clips.get_video_stats") as m_vstats, \
         patch("scripts.yt_agents.hot_clips.get_channel_stats") as m_chstats, \
         patch("scripts.yt_agents.hot_clips._get_channel_raw_videos") as m_raw:

        # 검색 결과: v1과 v2 (v3는 검색 결과에 없음, 하지만 채널의 최근 10개에는 포함)
        m_search.return_value = [
            {"video_id": "v1", "title": "Video 1", "channel_id": "UCch",
             "channel_title": "채널", "published_at": "2026-06-28T00:00:00Z", "thumbnail": "t1"},
            {"video_id": "v2", "title": "Video 2", "channel_id": "UCch",
             "channel_title": "채널", "published_at": "2026-06-27T00:00:00Z", "thumbnail": "t2"},
        ]

        # 검색된 영상의 통계
        m_vstats.return_value = {
            "v1": {"view_count": 50000, "like_count": 1000, "comment_count": 50},
            "v2": {"view_count": 40000, "like_count": 800, "comment_count": 40},
        }

        m_chstats.return_value = {"UCch": {"subscriber_count": 5000, "video_count": 50}}

        # 채널 UCch의 최근 영상 데이터 (v1, v2, v3 모두 포함)
        m_raw.return_value = [
            {"video_id": "v1", "view_count": 50000, "like_count": 1000},
            {"video_id": "v2", "view_count": 40000, "like_count": 800},
            {"video_id": "v3", "view_count": 1000, "like_count": 20},
        ]

        results = hot_clips.find_hot_clips("셀프테스트")

    # 2개 영상 결과 (v1, v2)
    assert len(results) == 2

    # v1 검증
    r1 = next(r for r in results if r["video_id"] == "v1")
    # v1의 평균 = (40000 + 1000) / 2 = 20500 (v1 자신 제외)
    expected_v1_avg = (40000 + 1000) / 2  # 20500
    expected_v1_pct = round((50000 - expected_v1_avg) / expected_v1_avg * 100, 1)  # (50000-20500)/20500*100 ≈ 143.9%
    assert r1["view_pct_above_avg"] == pytest.approx(expected_v1_pct, rel=0.01)

    # v2 검증
    r2 = next(r for r in results if r["video_id"] == "v2")
    # v2의 평균 = (50000 + 1000) / 2 = 25500 (v2 자신 제외)
    expected_v2_avg = (50000 + 1000) / 2  # 25500
    expected_v2_pct = round((40000 - expected_v2_avg) / expected_v2_avg * 100, 1)  # (40000-25500)/25500*100 ≈ 56.9%
    assert r2["view_pct_above_avg"] == pytest.approx(expected_v2_pct, rel=0.01)

    # 핵심: v1과 v2가 서로 다른 평균을 사용했음을 확인
    # v1_pct != v2_pct 이어야 함 (버그 있으면 같았을 것)
    assert abs(r1["view_pct_above_avg"] - r2["view_pct_above_avg"]) > 1  # 차이가 1% 이상 (143.9% vs 56.9%)

    # _get_channel_raw_videos는 채널당 1회만 호출되어야 함 (캐시 확인)
    assert m_raw.call_count == 1
