"""키워드 → 플랫폼별 검색링크 URL 템플릿. 순수 함수, 외부 API 불필요."""
import urllib.parse


def _q(text):
    return urllib.parse.quote(text)


def _q_full(text):
    """완전 인코딩 (슬래시 포함)."""
    return urllib.parse.quote(text, safe="")


def build_search_links(keywords):
    """keywords: {"ko":[...], "en":[...], "zh":[...]} → 플랫폼별 검색 URL 리스트.

    한국어권 플랫폼(유튭·구글·인스타·틱톡)은 ko+en 키워드, 중국어권(더우인·샤오홍슈)은
    zh 키워드로 검색 URL을 만든다.
    """
    ko = keywords.get("ko", [])
    en = keywords.get("en", [])
    zh = keywords.get("zh", [])
    kr_terms = ko + en
    cn_terms = zh

    return {
        "youtube": [f"https://www.youtube.com/results?search_query={_q(k)}" for k in kr_terms],
        "google": [f"https://www.google.com/search?q={_q(k)}" for k in kr_terms],
        "tiktok": [f"https://www.tiktok.com/search?q={_q(k)}" for k in kr_terms],
        "instagram": [f"https://www.instagram.com/explore/search/keyword/?q={_q(k)}" for k in kr_terms],
        "douyin": [f"https://www.douyin.com/search/{_q(k)}" for k in cn_terms],
        "xiaohongshu": [f"https://www.xiaohongshu.com/search_result?keyword={_q(k)}" for k in cn_terms],
    }


def lens_search_url(frame_public_url):
    """프레임 이미지의 공개 URL → Google Lens 역검색 링크."""
    return f"https://lens.google.com/uploadbyurl?url={_q_full(frame_public_url)}"
