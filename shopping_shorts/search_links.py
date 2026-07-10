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
    {platform: {lang: [{"keyword": k, "url": u}, ...]}} — 언어별 키워드 후보
    전부에 대해 링크 생성.

    2026-07-10 링크전용 UI로 재설계: Apify로 결과를 직접 긁어와 임베드하는
    방식은 액터 품질 한계(실측: 정확한 키워드로도 관련성 30~50%대, zh/ja/ru
    키워드 자체가 비어 중국어 플랫폼에 영어 문구로 검색되는 문제)에 부딪혀
    포기 — 대신 경쟁사(tubefactory)처럼 언어별 키워드 후보 전부를 그 플랫폼
    자체 검색 링크로 만들어 사용자가 직접 클릭해서 확인하는 방식으로 전환.
    이전엔 언어당 첫 키워드 하나만 썼는데, 이제 후보 전부를 보여준다."""
    result = {}
    for platform, builder in _URL_BUILDERS.items():
        result[platform] = {}
        for lang in _LANGS:
            kw_list = keywords.get(lang) or []
            if kw_list:
                result[platform][lang] = [{"keyword": kw, "url": builder(kw)} for kw in kw_list]
    return result


def lens_search_url(frame_public_url):
    """프레임 이미지의 공개 URL → Google Lens 역검색 링크."""
    return f"https://lens.google.com/uploadbyurl?url={_q_full(frame_public_url)}"
