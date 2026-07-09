"""YouTube Data API v3로 키워드 검색 → 정규화된 후보 리스트."""
import requests
from shopping_shorts.config import YOUTUBE_API_KEY

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def search(keyword, max_results=10):
    """키워드 → [{url, title, thumbnail}, ...]."""
    if not YOUTUBE_API_KEY:
        raise RuntimeError("youtube_search: YOUTUBE_API_KEY가 설정되지 않았습니다")
    resp = requests.get(_SEARCH_URL, params={
        "part": "snippet", "q": keyword, "type": "video",
        "maxResults": max_results, "key": YOUTUBE_API_KEY,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    out = []
    for item in data.get("items", []):
        vid = item.get("id", {}).get("videoId")
        if not vid:
            continue
        snippet = item.get("snippet", {})
        thumb = snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
        out.append({
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": snippet.get("title", ""),
            "thumbnail": thumb,
        })
    return out
