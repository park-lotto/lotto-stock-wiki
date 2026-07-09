"""Apify Instagram Hashtag Scraper(apify/instagram-hashtag-scraper)로 키워드
검색 → 정규화된 후보 리스트. apify_client.py의 토큰 로테이션을 재사용
(2026-07-09, "인스타도 실수집" 요청으로 추가).

주의: 우리가 기존에 쓰는 인스타 릴스 스크래퍼(apify~instagram-reel-scraper)는
username/directUrls만 지원하고 hashtags 필드가 없어 이 용도로 못 쓴다(실측
확인, 400 invalid-input). apify~instagram-scraper의 searchType=hashtag
모드는 구글 기반 매칭이라 결과가 부정확했음(실측 — "바닥청소" 검색에 전혀
무관한 해시태그가 매칭됨). 전용 해시태그 스크래퍼가 정확한 결과를 준다."""
from shopping_shorts.apify_client import _run_with_rotation
from shopping_shorts.config import APIFY_TOKENS

_ACTOR = "apify~instagram-hashtag-scraper"


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드(해시태그) → [{url, title, thumbnail}, ...]. 해시태그는 공백을
    포함할 수 없으므로 공백을 제거해 전달한다."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("instagram_search: APIFY_TOKEN이 설정되지 않았습니다")
    hashtag = keyword.replace(" ", "")
    payload = {"hashtags": [hashtag], "resultsLimit": max_results}
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        url = item.get("url")
        if not url:
            continue
        out.append({
            "url": url,
            "title": item.get("caption", ""),
            "thumbnail": item.get("displayUrl", ""),
        })
    return out
