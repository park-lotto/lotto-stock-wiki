"""유튜브 Data API 기반 터진 영상 탐지 — 채널 자체 평균 대비 % 계산.
2026-07-03: agent_plan.search_hot_clips()(Google검색+Gemini 추정)는 숫자가 부정확해서
실제 API 수치로 교체."""
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
            "title": sn["title"],
            "channel_id": sn["channelId"],
            "channel_title": sn["channelTitle"],
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
    if not channel_ids:
        return {}
    params = {"part": "statistics", "id": ",".join(channel_ids), "key": _api_key()}
    r = requests.get(f"{API_BASE}/channels", params=params)
    r.raise_for_status()
    out = {}
    for item in r.json().get("items", []):
        st = item["statistics"]
        out[item["id"]] = {
            "subscriber_count": int(st.get("subscriberCount", 0)),
            "video_count": int(st.get("videoCount", 0)),
        }
    return out


def get_channel_recent_avg_views(channel_id: str, n: int = 10, exclude_video_id: str | None = None) -> tuple[float, float]:
    """그 채널 최근 n개 영상의 평균 조회수·평균 좋아요. exclude_video_id면 그 영상 제외.
    영상 없으면 (0.0, 0.0)."""
    params = {
        "part": "snippet", "channelId": channel_id, "type": "video",
        "order": "date", "maxResults": n, "key": _api_key(),
    }
    r = requests.get(f"{API_BASE}/search", params=params)
    r.raise_for_status()
    all_video_ids = [item["id"]["videoId"] for item in r.json().get("items", [])]

    # exclude_video_id가 있으면 목록에서 제거 (필요하면 API 호출)
    video_ids = [vid for vid in all_video_ids if vid != exclude_video_id] if exclude_video_id else all_video_ids

    if not video_ids:
        return 0.0, 0.0
    stats = get_video_stats(video_ids)
    views = [s["view_count"] for s in stats.values()]
    likes = [s["like_count"] for s in stats.values()]
    return (sum(views) / len(views), sum(likes) / len(likes))


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

    # 채널 통계 배치 조회
    channel_stats = get_channel_stats(unique_channel_ids)

    # 채널 평균 조회수·좋아요 캐시 (API 호출 줄이기)
    channel_avg_cache = {}

    results = []
    for v in videos:
        st = stats.get(v["video_id"], {"view_count": 0, "like_count": 0, "comment_count": 0})
        ch_id = v["channel_id"]

        # 캐시에서 조회, 없으면 API 호출하여 캐시에 저장
        if ch_id not in channel_avg_cache:
            channel_avg_cache[ch_id] = get_channel_recent_avg_views(ch_id, exclude_video_id=v["video_id"])

        avg_view, avg_like = channel_avg_cache[ch_id]

        view_pct = round((st["view_count"] - avg_view) / avg_view * 100, 1) if avg_view else 0.0
        like_pct = round((st["like_count"] - avg_like) / avg_like * 100, 1) if avg_like else 0.0

        # 채널 구독자 수 (기본값 0)
        ch_stat = channel_stats.get(ch_id, {"subscriber_count": 0, "video_count": 0})
        subscriber_count = ch_stat["subscriber_count"]

        results.append({
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_title": v["channel_title"],
            "thumbnail": v["thumbnail"],
            "view_count": st["view_count"],
            "view_pct_above_avg": view_pct,
            "contribution_grade": _grade(view_pct),
            "performance_grade": _grade(like_pct),
            "subscriber_count": subscriber_count,
        })
    return results
