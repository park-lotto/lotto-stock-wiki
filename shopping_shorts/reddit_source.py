"""Reddit 공개 .json으로 서브레딧 급상승/오늘상위 영상 포스트를 무료 수집 →
정규화 dict. TikTok 무료 키워드검색이 없는 공백을 Reddit '정찰'이 메꾼다.
urllib만 사용(외부 의존성 0). User-Agent 없으면 429."""
_IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")


def extract_media_url(post):
    """Reddit 포스트 dict → (영상URL, 플랫폼) 또는 (None, None).

    플랫폼: 'reddit'(v.redd.it) | 'tiktok' | 'youtube' | 'other'.
    이미지/텍스트 포스트는 (None, None)."""
    media = post.get("media") or {}
    if post.get("is_video") and media.get("reddit_video", {}).get("fallback_url"):
        return media["reddit_video"]["fallback_url"], "reddit"
    url = (post.get("url") or "").strip()
    if not url:
        return None, None
    low = url.lower()
    if "tiktok.com" in low:
        return url, "tiktok"
    if "youtube.com" in low or "youtu.be" in low:
        return url, "youtube"
    if "v.redd.it" in low:
        return url, "reddit"
    if any(h in low for h in ("streamable.com", "redgifs.com")):
        return url, "other"
    return None, None
