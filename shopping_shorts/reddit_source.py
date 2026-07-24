"""Reddit 공개 RSS(.rss)로 서브레딧 top/rising 영상 포스트를 무료 수집 → 정규화 dict.

익명 .json은 2024년 이후 403 Blocked라 RSS(Atom)를 쓴다(실측 2026-07-25: .json은 403,
.rss는 정상). TikTok 무료 키워드검색이 없는 공백을 Reddit '정찰'이 메꾼다.
RSS엔 업보트 숫자가 없어(제목·시각·원본URL·썸네일만 옴) 랭킹 신호는 'Reddit이 이미
정렬해준 순위(rank_points)'로 대체한다 — top.rss는 오늘의 상위, rising.rss는 급상승 순.
순위가 오르면(스냅샷 비교) 그게 곧 가속이라 build_reddit_items의 speed/accel이 그대로 산다.
stdlib(urllib·xml)만 사용 — 외부 의존성 0."""
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

_ATOM = "{http://www.w3.org/2005/Atom}"
_IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")
# RSS는 브라우저 UA에서 정상 응답(실측). 봇틱한 UA는 .json처럼 막힐 여지가 있어 브라우저로.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


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


def _http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def _post_id_from(entry_id, permalink):
    """Atom <id>(예: 't3_1v4nk4g') 또는 permalink(.../comments/1v4nk4g/...)에서 포스트 id."""
    if entry_id and "_" in entry_id:
        return entry_id.rsplit("_", 1)[-1]
    m = re.search(r"/comments/([a-z0-9]+)/", permalink or "")
    return m.group(1) if m else ""


def _first_external_url(content_html):
    """RSS content HTML 안의 첫 외부(비-reddit) 링크 = 원본영상 URL 후보."""
    for href in re.findall(r'href="([^"]+)"', content_html or ""):
        if "reddit.com" not in href and "/comments/" not in href:
            return href
    return ""


def _first_img(content_html):
    m = re.search(r'<img[^>]+src="([^"]+)"', content_html or "")
    return m.group(1) if m else ""


def normalize_entries(xml_text, subreddit="", category="", sort="top"):
    """Reddit RSS(Atom) 텍스트 → 영상 포스트만 정규화 dict 리스트.

    반환 dict 키: source, post_id, shortcode(=post_id), subreddit, title, permalink,
    media_url, media_platform, thumbnail, ups(=rank_points), num_comments(=0),
    published_at, category, rss_sort. ups는 RSS에 업보트가 없어 순위점수로 대체
    (상단일수록 높음) — build_reddit_items가 이 값을 upvote처럼 소비한다."""
    root = ET.fromstring(xml_text)
    out = []
    for idx, e in enumerate(root.findall(_ATOM + "entry")):
        title = (e.findtext(_ATOM + "title") or "").strip()
        entry_id = e.findtext(_ATOM + "id") or ""
        link_el = e.find(_ATOM + "link")
        permalink = link_el.get("href") if link_el is not None else ""
        pid = _post_id_from(entry_id, permalink)
        if not pid:
            continue
        content = e.findtext(_ATOM + "content") or ""
        media_url, platform = extract_media_url({"url": _first_external_url(content)})
        if not media_url:
            continue  # 이미지/텍스트/갤러리 = 영상 아님 → 제외
        out.append({
            "source": "reddit",
            "post_id": pid,
            "shortcode": pid,
            "subreddit": subreddit,
            "title": title,
            "permalink": permalink,
            "media_url": media_url,
            "media_platform": platform,
            "thumbnail": _first_img(content),
            "ups": max(0, 1000 - idx * 10),   # RSS엔 업보트 없음 → 순위점수(상단=높음)
            "num_comments": 0,
            "published_at": (e.findtext(_ATOM + "published") or e.findtext(_ATOM + "updated") or ""),
            "category": category,
            "rss_sort": sort,
        })
    return out


def fetch_subreddit(subreddit, category="", sort="rising", limit=50, retries=2, pause=1.0):
    """서브레딧의 rising/top-day 영상 포스트 정규화 리스트. 실패 시 빈 리스트(부분실패 허용).

    sort='top'→ top.rss?t=day(오늘 상위), 그 외→ {sort}.rss(rising 등). limit은 RSS가
    무시하지만 시그니처 호환 위해 유지."""
    suffix = "top.rss?t=day" if sort == "top" else "%s.rss" % sort
    url = "https://www.reddit.com/r/%s/%s" % (subreddit, suffix)
    for attempt in range(retries + 1):
        try:
            return normalize_entries(_http_get(url), subreddit=subreddit, category=category, sort=sort)
        except Exception:
            if attempt < retries:
                time.sleep(pause * (attempt + 1))
    return []
