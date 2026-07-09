"""SerpApi Google Lens 엔진으로 프레임 이미지 → 실제 구매처(쇼핑몰) 링크
검색(2026-07-09, 인스타 실수집 대안 기술검증 중 추가).

실측(2026-07-09): 프레임 5장 중 4장에서 시각적 매칭 50~60건 확인, 전부
Amazon/eBay/Etsy 등 쇼핑몰 — 릴스·틱톡 등 소셜 영상은 안 나온다. 즉 "짜집기
소스 추가 수집"이 아니라 "이 제품 실제 판매처 찾기" 용도로 쓴다."""
import requests

from shopping_shorts.config import SERPAPI_KEY

_ENDPOINT = "https://serpapi.com/search"


def search(image_url, api_key=None, max_results=10, timeout=60):
    """공개 이미지 URL → [{source, title, link, thumbnail}, ...]."""
    key = api_key or SERPAPI_KEY
    if not key:
        raise RuntimeError("lens_shopping: SERPAPI_KEY가 설정되지 않았습니다")
    params = {"engine": "google_lens", "url": image_url, "api_key": key}
    r = requests.get(_ENDPOINT, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    matches = data.get("visual_matches") or []
    out = []
    for m in matches[:max_results]:
        link = m.get("link")
        if not link:
            continue
        out.append({
            "source": m.get("source", ""),
            "title": m.get("title", ""),
            "link": link,
            "thumbnail": m.get("thumbnail", ""),
        })
    return out
