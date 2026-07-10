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


def _candidate_hashtags(keyword):
    """키워드 → 시도할 해시태그 후보 리스트(구체적인 것부터).

    전체를 붙인 해시태그가 실제 존재하지 않으면(예: "무선헤어드라이어" 0건),
    앞쪽 수식어를 하나씩 떼어 뒷부분(핵심 명사 쪽)만 남긴 해시태그로 재시도한다
    (2026-07-09/10 실측: "무선 헤어드라이어" 전체=0건이지만 "헤어드라이어"만
    떼면 5건 — 한국어 명사구는 핵심 명사가 보통 맨 뒤에 온다는 점 이용).
    """
    words = keyword.split()
    seen = []
    for i in range(len(words)):
        tag = "".join(words[i:])
        if tag and tag not in seen:
            seen.append(tag)
    return seen or [keyword.replace(" ", "")]


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드(해시태그) → [{url, title, thumbnail}, ...]. 해시태그는 공백을
    포함할 수 없으므로 공백을 제거해 전달하고, 결과가 없으면 더 짧은/일반적인
    후보로 순차 재시도한다."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("instagram_search: APIFY_TOKEN이 설정되지 않았습니다")
    for hashtag in _candidate_hashtags(keyword):
        # resultsType 기본값은 "posts"(사진·캐러셀 위주) — "reels"를 명시해야 실제
        # 영상이 나온다(2026-07-09 실측: 기본값으로는 5~20개 다 Image/Sidecar였고
        # videoUrl이 전부 비어있었음. "짜집기" 목적상 사진은 무의미해서 필수 지정).
        payload = {"hashtags": [hashtag], "resultsLimit": max_results, "resultsType": "reels"}
        items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
        out = []
        for item in items:
            url = item.get("url")
            if not url or not item.get("videoUrl"):
                continue  # resultsType=reels로도 사진이 섞여 나올 가능성 대비 이중 확인
            out.append({
                "url": url,
                "title": item.get("caption", ""),
                "thumbnail": item.get("displayUrl", ""),
            })
        if out:
            return out
    return []
