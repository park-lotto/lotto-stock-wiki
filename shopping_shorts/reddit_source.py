"""Reddit 공개 .json으로 서브레딧 급상승/오늘상위 영상 포스트를 무료 수집 →
정규화 dict. TikTok 무료 키워드검색이 없는 공백을 Reddit '정찰'이 메꾼다.
urllib만 사용(외부 의존성 0). User-Agent 없으면 429."""
from datetime import datetime, timezone

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


def _iso(unix_ts):
    if not unix_ts:
        return ""
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_children(children, category=""):
    """Reddit listing children → 영상 포스트만 정규화 dict 리스트.

    반환 dict 키: source, post_id, shortcode(=post_id), subreddit, title, permalink,
    media_url, media_platform, thumbnail, ups, num_comments, published_at, category."""
    out = []
    for ch in children or []:
        p = ch.get("data") or {}
        pid = str(p.get("id") or "")
        if not pid:
            continue
        media_url, platform = extract_media_url(p)
        if not media_url:
            continue
        thumb = p.get("thumbnail") or ""
        if thumb in ("self", "default", "nsfw", "spoiler", "image"):
            thumb = ""
        out.append({
            "source": "reddit",
            "post_id": pid,
            "shortcode": pid,
            "subreddit": p.get("subreddit", ""),
            "title": p.get("title", ""),
            "permalink": "https://www.reddit.com" + (p.get("permalink") or ""),
            "media_url": media_url,
            "media_platform": platform,
            "thumbnail": thumb,
            "ups": int(p.get("ups") or 0),
            "num_comments": int(p.get("num_comments") or 0),
            "published_at": _iso(p.get("created_utc")),
            "category": category,
        })
    return out
