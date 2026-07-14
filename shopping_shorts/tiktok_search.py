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


def search_full(keyword, max_results=60, token=None, timeout=180, poll_interval=5):
    """키워드 → 랭킹 파이프라인(build_tiktok_items)이 그대로 소비하는 풀 raw dict 리스트.

    minimal search()가 {url,title,thumbnail}만 뽑는 것과 달리 조회수·좋아요·댓글·
    게시시각·작성자까지 채워 build_tiktok_items → apply_grades로 바로 흘려보낸다
    (2026-07-13 필드매핑 실증: id/text/createTimeISO/webVideoUrl/playCount/diggCount/
    commentCount/authorMeta.name/videoMeta.coverUrl). video_id(id) 없는 행은 랭킹 키가
    없어 제외."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("tiktok_search: APIFY_TOKEN이 설정되지 않았습니다")
    payload = {
        "searchQueries": [keyword],
        "resultsPerPage": max_results,
        "shouldDownloadCovers": False,
        "shouldDownloadVideos": False,
        "shouldDownloadAvatars": False,
    }
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        vid = str(item.get("id") or "")
        if not vid:
            continue
        meta = item.get("videoMeta") or {}
        author = item.get("authorMeta") or {}
        out.append({
            "video_id": vid,
            "url": item.get("webVideoUrl", ""),
            "channel_title": author.get("name", ""),
            "title": item.get("text", ""),
            "thumbnail": meta.get("coverUrl") or meta.get("originalCoverUrl", ""),
            "published_at": item.get("createTimeISO", ""),
            "views": int(item.get("playCount") or 0),
            "likes": int(item.get("diggCount") or 0),
            "comments": int(item.get("commentCount") or 0),
        })
    return out
