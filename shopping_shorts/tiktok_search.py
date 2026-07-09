"""Apify TikTok Scraper(clockworks/tiktok-scraper)로 키워드 검색 → 정규화된
후보 리스트. apify_client.py의 토큰 로테이션(_run_with_rotation)을 그대로
재사용 — 인스타 릴스 스크래퍼와 다른 액터를 쓰지만 같은 토큰 풀·재시도
로직 공유(2026-07-09, "틱톡도 실수집" 요청으로 추가)."""
from shopping_shorts.apify_client import _run_with_rotation
from shopping_shorts.config import APIFY_TOKENS

_ACTOR = "clockworks~tiktok-scraper"


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드 → [{url, title, thumbnail}, ...]."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("tiktok_search: APIFY_TOKEN이 설정되지 않았습니다")
    payload = {
        "searchQueries": [keyword],
        "resultsPerPage": max_results,
        "shouldDownloadCovers": False,  # coverUrl은 이미 메타데이터에 포함, 다운로드 불필요
        "shouldDownloadVideos": False,
        "shouldDownloadAvatars": False,
    }
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        url = item.get("webVideoUrl")
        if not url:
            continue
        cover = (item.get("videoMeta") or {}).get("coverUrl") or (item.get("videoMeta") or {}).get("originalCoverUrl", "")
        out.append({
            "url": url,
            "title": item.get("text", ""),
            "thumbnail": cover,
        })
    return out
