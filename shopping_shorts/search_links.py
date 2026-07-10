"""키워드 → 플랫폼별 검색링크 URL. 순수 함수, 외부 API 불필요."""
import urllib.parse


def _q(text):
    return urllib.parse.quote(text)


def _q_full(text):
    """완전 인코딩 (슬래시 포함)."""
    return urllib.parse.quote(text, safe="")


_LANGS = ("ko", "en", "zh", "ja", "ru")

_URL_BUILDERS = {
    "youtube": lambda k: f"https://www.youtube.com/results?search_query={_q(k)}",
    "tiktok": lambda k: f"https://www.tiktok.com/search?q={_q(k)}",
    "instagram": lambda k: f"https://www.instagram.com/explore/search/keyword/?q={_q(k)}",
    "xiaohongshu": lambda k: f"https://www.xiaohongshu.com/search_result?keyword={_q(k)}",
    "douyin": lambda k: f"https://www.douyin.com/search/{_q(k)}",
}


def build_search_links(keywords):
    """keywords: {"ko":[...], "en":[...], "zh":[...], "ja":[...], "ru":[...]} →
    {platform: {lang: url}} — 5개 언어 × 5개 플랫폼 전부 조합, 언어별 첫
    키워드(product_identify가 확인한 정확한 제품명이 있으면 그게 맨 앞) 사용.

    2026-07-10 재설계: 이전엔 platform당 URL 리스트를 그냥 나열했는데, 실제
    사용해보니 플랫폼 자체 자유텍스트 검색(이 링크)이 우리 해시태그 기반
    실수집보다 훨씬 정확했음("여기 나온건 의미가 없다" 피드백) — 언어/사이트
    드롭다운으로 사용자가 골라 링크 하나만 바로 보게 딕셔너리 구조로 변경."""
    result = {}
    for platform, builder in _URL_BUILDERS.items():
        result[platform] = {}
        for lang in _LANGS:
            kw_list = keywords.get(lang) or []
            if kw_list:
                result[platform][lang] = builder(kw_list[0])
    return result


def lens_search_url(frame_public_url):
    """프레임 이미지의 공개 URL → Google Lens 역검색 링크."""
    return f"https://lens.google.com/uploadbyurl?url={_q_full(frame_public_url)}"
