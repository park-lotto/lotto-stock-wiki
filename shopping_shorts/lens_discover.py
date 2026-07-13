"""SerpApi Google Lens로 프레임을 역검색해 유사 동영상(5개 플랫폼)만 추린다.

visual_matches에는 동영상 여부 필드가 없어(2026-07-14 실측: link/source/title/
thumbnail만) link 도메인 화이트리스트로 판별한다. product_identify.py와 같은
google_lens 엔진이지만 용도가 달라(제품명 추론 X, 유사영상 발굴 O) 분리."""
import requests
from urllib.parse import urlparse
from shopping_shorts.config import SERPAPI_KEY

_LENS_ENDPOINT = "https://serpapi.com/search"

# 플랫폼 판별 — 도메인 접미사 매칭(서브도메인·www 무관). 순서=표시 우선순위.
_PLATFORM_DOMAINS = [
    ("youtube", ("youtube.com", "youtu.be")),
    ("tiktok", ("tiktok.com",)),
    ("instagram", ("instagram.com",)),
    ("xiaohongshu", ("xiaohongshu.com", "xhslink.com")),
    ("douyin", ("douyin.com", "iesdouyin.com")),
]


def _platform_of(link):
    host = urlparse(link or "").netloc.lower()
    for name, domains in _PLATFORM_DOMAINS:
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    return None


def search_similar_videos(image_url, api_key=None, timeout=60):
    """공개 이미지 URL → [{platform, url, title, thumbnail}]. 5개 동영상 플랫폼만.
    키 없음·호출 실패 시 []."""
    key = api_key or SERPAPI_KEY
    if not key:
        return []
    params = {"engine": "google_lens", "url": image_url, "api_key": key}
    try:
        r = requests.get(_LENS_ENDPOINT, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return []
    out = []
    for m in data.get("visual_matches") or []:
        platform = _platform_of(m.get("link"))
        if not platform:
            continue
        out.append({
            "platform": platform,
            "url": m.get("link", ""),
            "title": m.get("title", ""),
            "thumbnail": m.get("thumbnail", ""),
        })
    return out
