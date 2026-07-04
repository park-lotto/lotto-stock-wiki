"""유튜브 Data API 기반 터진 영상 탐지 — 채널 자체 평균 대비 % 계산.
2026-07-03: agent_plan.search_hot_clips()(Google검색+Gemini 추정)는 숫자가 부정확해서
실제 API 수치로 교체."""
import html
import os
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent.parent
API_BASE = "https://www.googleapis.com/youtube/v3"


def _api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if key:
        return key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("YOUTUBE_API_KEY=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip()
    return ""


def search_videos(query: str, max_results: int = 10) -> list[dict]:
    """유튜브 검색 — 관련도 높은 순, 최근 것 우선."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "regionCode": "KR",
        "relevanceLanguage": "ko",
        "order": "viewCount",
        "maxResults": max_results,
        "key": _api_key(),
    }
    r = requests.get(f"{API_BASE}/search", params=params)
    r.raise_for_status()
    out = []
    for item in r.json().get("items", []):
        sn = item["snippet"]
        out.append({
            "video_id": item["id"]["videoId"],
            "title": html.unescape(sn["title"]),
            "channel_id": sn["channelId"],
            "channel_title": html.unescape(sn["channelTitle"]),
            "published_at": sn["publishedAt"],
            "thumbnail": sn.get("thumbnails", {}).get("default", {}).get("url", ""),
        })
    return out


def get_video_stats(video_ids: list[str]) -> dict[str, dict]:
    if not video_ids:
        return {}
    params = {"part": "statistics", "id": ",".join(video_ids), "key": _api_key()}
    r = requests.get(f"{API_BASE}/videos", params=params)
    r.raise_for_status()
    out = {}
    for item in r.json().get("items", []):
        st = item["statistics"]
        out[item["id"]] = {
            "view_count": int(st.get("viewCount", 0)),
            "like_count": int(st.get("likeCount", 0)),
            "comment_count": int(st.get("commentCount", 0)),
        }
    return out


def get_channel_stats(channel_ids: list[str]) -> dict[str, dict]:
    """구독자·영상수 + 업로드 재생목록ID(contentDetails, 같은 호출에 묶어서 추가비용 없음)."""
    if not channel_ids:
        return {}
    params = {"part": "statistics,contentDetails", "id": ",".join(channel_ids), "key": _api_key()}
    r = requests.get(f"{API_BASE}/channels", params=params)
    r.raise_for_status()
    out = {}
    for item in r.json().get("items", []):
        st = item["statistics"]
        uploads_playlist_id = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
        out[item["id"]] = {
            "subscriber_count": int(st.get("subscriberCount", 0)),
            "video_count": int(st.get("videoCount", 0)),
            "uploads_playlist_id": uploads_playlist_id,
        }
    return out


def _get_channel_raw_videos(uploads_playlist_id: str, n: int = 10) -> list[dict]:
    """업로드 재생목록에서 최근 n개 영상의 raw 데이터 (ID, 조회수, 좋아요).
    2026-07-04: search.list(채널당 100 unit)를 playlistItems.list(1 unit)로 교체 —
    기존 방식은 검색 1건당 ~1000 unit(유튜브 일일 할당량 10,000 unit 중 9건/일밖에 안 됨)을
    태워 429 Too Many Requests가 바로 발생했음. playlistItems.list 기반으로 채널당
    비용을 100배 이상 줄임."""
    if not uploads_playlist_id:
        return []
    params = {
        "part": "contentDetails", "playlistId": uploads_playlist_id,
        "maxResults": n, "key": _api_key(),
    }
    r = requests.get(f"{API_BASE}/playlistItems", params=params)
    r.raise_for_status()
    video_ids = [item["contentDetails"]["videoId"] for item in r.json().get("items", [])]

    if not video_ids:
        return []
    stats = get_video_stats(video_ids)
    return [
        {
            "video_id": vid,
            "view_count": stats[vid]["view_count"],
            "like_count": stats[vid]["like_count"],
        }
        for vid in video_ids
    ]


def _grade(pct: float) -> str:
    if pct >= 700:
        return "Great"
    if pct >= 200:
        return "Good"
    return "Normal"


def find_hot_clips(query: str) -> list[dict]:
    """검색 → 통계 조회 → 채널 평균 대비 % 계산 → 등급 부여."""
    videos = search_videos(query)
    if not videos:
        return []
    stats = get_video_stats([v["video_id"] for v in videos])

    # 고유 channel_id 추출
    unique_channel_ids = list(set(v["channel_id"] for v in videos))

    # 채널 통계 배치 조회 (구독자수 + 업로드 재생목록ID)
    channel_stats = get_channel_stats(unique_channel_ids)

    # 채널별 raw 영상 데이터 캐시 (API 호출 최소화)
    # 각 채널의 최근 영상 리스트를 한 번만 fetch하고, 각 영상별로 exclusion 적용
    channel_raw_videos_cache = {}

    results = []
    for v in videos:
        st = stats.get(v["video_id"], {"view_count": 0, "like_count": 0, "comment_count": 0})
        ch_id = v["channel_id"]
        ch_stat = channel_stats.get(ch_id, {"subscriber_count": 0, "video_count": 0, "uploads_playlist_id": ""})

        # 채널별 raw 데이터를 캐시에서 조회, 없으면 API 호출하여 캐시에 저장
        if ch_id not in channel_raw_videos_cache:
            channel_raw_videos_cache[ch_id] = _get_channel_raw_videos(
                ch_stat.get("uploads_playlist_id", ""), n=10
            )

        # 이 영상 자신을 제외한 평균 계산 (Python에서 각 영상별로 개별 적용)
        raw_videos = channel_raw_videos_cache[ch_id]
        filtered = [rv for rv in raw_videos if rv["video_id"] != v["video_id"]]

        if filtered:
            avg_view = sum(rv["view_count"] for rv in filtered) / len(filtered)
            avg_like = sum(rv["like_count"] for rv in filtered) / len(filtered)
        else:
            avg_view = 0.0
            avg_like = 0.0

        view_pct = round((st["view_count"] - avg_view) / avg_view * 100, 1) if avg_view else 0.0
        like_pct = round((st["like_count"] - avg_like) / avg_like * 100, 1) if avg_like else 0.0

        results.append({
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_title": v["channel_title"],
            "thumbnail": v["thumbnail"],
            "view_count": st["view_count"],
            "view_pct_above_avg": view_pct,
            "contribution_grade": _grade(view_pct),
            "performance_grade": _grade(like_pct),
            "subscriber_count": ch_stat["subscriber_count"],
        })
    return results
