"""Apify RedNote(Xiaohongshu/샤오홍슈) Search Scraper(zen-studio/rednote-search-scraper)로
키워드 검색 → 정규화된 후보 리스트. apify_client.py의 토큰 로테이션을 재사용
(2026-07-10, 5대 플랫폼 확장 요청으로 추가).

실측(2026-07-10): noteType="video"로 요청하면 실제 재생 가능한 영상 노트만
나옴(video.streams에 실 mp4 URL 포함) — 사진 노트가 섞여 나오는 문제는 없었음.
같이 조사한 더우인(douyin-scraper 액터)은 흔한 키워드로도 0건이 나와 신뢰도가
낮다고 판단, 우선 샤오홍슈만 연동한다."""
from shopping_shorts.apify_client import _run_with_rotation
from shopping_shorts.config import APIFY_TOKENS

_ACTOR = "zen-studio~rednote-search-scraper"


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드 → [{url, title, thumbnail}, ...]."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("xiaohongshu_search: APIFY_TOKEN이 설정되지 않았습니다")
    payload = {
        "keywords": [keyword],
        "maxResults": max_results,
        "noteType": "video",
        "topUpFromOtherSorts": False,
    }
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        url = item.get("url")
        video = item.get("video") or {}
        if not url or item.get("type") != "video" or not video.get("url_720p"):
            continue  # noteType=video로도 사진 노트가 섞여 나올 가능성 대비 이중 확인
        out.append({
            "url": url,
            "title": item.get("title") or item.get("desc", ""),
            "thumbnail": video.get("thumbnail", ""),
        })
    return out
