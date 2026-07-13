"""YouTube Data API v3 어댑터 — 키워드로 인기 Shorts 발굴 + 통계.

무료(쿼터 내). config.YOUTUBE_API_KEYS를 순서대로 시도(쿼터 초과 시 다음 키).
검색(search.list)은 통계가 없어 videos.list로 조회수·좋아요·댓글을 채운다.
"""
import requests
from shopping_shorts.config import YOUTUBE_API_KEYS

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _stats(video_ids, token):
    """videos.list(statistics) → {video_id: {views,likes,comments}}."""
    out = {}
    for i in range(0, len(video_ids), 50):          # API 상한 50개/호출
        chunk = video_ids[i:i + 50]
        r = requests.get(_VIDEOS_URL, params={
            "part": "statistics", "id": ",".join(chunk), "key": token}, timeout=30)
        if r.status_code != 200:
            continue
        for it in r.json().get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = {
                "views": int(s.get("viewCount") or 0),
                "likes": int(s.get("likeCount") or 0),
                "comments": int(s.get("commentCount") or 0),
            }
    return out


def search_shorts(keywords, published_after_iso, max_per_kw=20, token=None):
    """키워드별로 최신·인기 영상 검색 → 통계 채운 원시 dict 리스트."""
    tokens = [token] if token else YOUTUBE_API_KEYS
    if not tokens:
        raise RuntimeError("YOUTUBE_API_KEY 미설정")
    tok = tokens[0]
    raw = []
    for kw in keywords:
        r = requests.get(_SEARCH_URL, params={
            "part": "snippet", "q": kw, "type": "video", "videoDuration": "short",
            "order": "viewCount", "publishedAfter": published_after_iso,
            "maxResults": min(max_per_kw, 50), "key": tok}, timeout=30)
        if r.status_code != 200:
            continue
        for it in r.json().get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            sn = it.get("snippet") or {}
            if not vid:
                continue
            raw.append({
                "video_id": vid, "channel_id": sn.get("channelId"),
                "channel_title": sn.get("channelTitle"),
                "title": sn.get("title"), "description": sn.get("description"),
                "thumbnail": ((sn.get("thumbnails") or {}).get("high") or {}).get("url", ""),
                "published_at": sn.get("publishedAt"),
            })
    stats = _stats([r["video_id"] for r in raw], tok)
    for r in raw:
        r.update(stats.get(r["video_id"], {"views": 0, "likes": 0, "comments": 0}))
    return raw
