"""Reddit에서 서브레딧 top/rising 영상 포스트를 수집 → 정규화 dict. 두 경로:

1) **OAuth(application-only)** — REDDIT_CLIENT_ID/SECRET가 있으면 oauth.reddit.com JSON.
   업보트·댓글 실데이터가 오고 rate-limit이 100 req/분이라 배치가 안정적이다(권장).
2) **익명 RSS(.rss) 폴백** — 크레덴셜이 없으면 공개 Atom 피드. 익명 .json은 2024년
   이후 403 Blocked라 RSS를 쓴다(실측 2026-07-25). RSS엔 업보트가 없어 랭킹 신호를
   Reddit 순위(rank_points)로 대체하고, 익명 rate-limit이 낮아 배치가 429로 자주
   빈손이 된다(실측) — 그래서 OAuth가 권장 경로다.

어느 경로든 build_reddit_items가 소비하는 동일 스키마(ups/num_comments/post_id/…)를
반환한다. OAuth는 실업보트, RSS는 순위점수를 ups에 담는다."""
import html
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import requests
from shopping_shorts.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET

_ATOM = "{http://www.w3.org/2005/Atom}"
_IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")
# 브라우저 UA(실측: RSS는 브라우저 UA에서 정상). OAuth는 UA에 앱명이 권장되나 무방.
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


# ─────────────────────────── OAuth(권장) ───────────────────────────
_TOKEN = {"token": None, "exp": 0.0}


def _has_oauth():
    return bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)


def _oauth_token():
    """application-only 액세스토큰(client_credentials). 만료 60s 전까지 캐시 재사용."""
    now = time.time()
    if _TOKEN["token"] and now < _TOKEN["exp"] - 60:
        return _TOKEN["token"]
    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": _UA}, timeout=15)
    resp.raise_for_status()
    d = resp.json()
    _TOKEN["token"] = d["access_token"]
    _TOKEN["exp"] = now + int(d.get("expires_in", 3600))
    return _TOKEN["token"]


def _iso(unix_ts):
    if not unix_ts:
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_children(children, category=""):
    """oauth.reddit.com JSON의 listing children → 영상 포스트만 정규화 dict 리스트.

    RSS와 동일 스키마 + 업보트/댓글 실값. thumbnail은 preview URL이 &amp; 이스케이프된
    경우가 있어 unescape한다."""
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
            "thumbnail": html.unescape(thumb),
            "ups": int(p.get("ups") or 0),
            "num_comments": int(p.get("num_comments") or 0),
            "published_at": _iso(p.get("created_utc")),
            "category": category,
        })
    return out


def _fetch_oauth(subreddit, category, sort, limit):
    """oauth.reddit.com JSON — 업보트 실데이터. rate-limit 100 req/분."""
    tok = _oauth_token()
    if sort == "top":
        path = "/r/%s/top?t=day&limit=%d" % (subreddit, limit)
    else:
        path = "/r/%s/%s?limit=%d" % (subreddit, sort, limit)
    resp = requests.get(
        "https://oauth.reddit.com" + path,
        headers={"Authorization": "bearer " + tok, "User-Agent": _UA}, timeout=15)
    resp.raise_for_status()
    children = (resp.json().get("data") or {}).get("children") or []
    return normalize_children(children, category=category)


# ─────────────────────────── RSS(폴백) ───────────────────────────
class RateLimited(Exception):
    """익명 RSS가 429를 반환 — 백오프 후 재시도 대상."""


def _http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(url) from e
        raise


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
    published_at, category, rss_sort. ups는 RSS에 업보트가 없어 순위점수로 대체."""
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
        # RSS content는 XML+HTML 이중 이스케이프 — ET가 XML 한 겹만 풀어 &amp;가 남는다.
        # 그대로면 서명 썸네일(?...&s=서명)이 깨져 → HTML 겹까지 unescape.
        content = html.unescape(e.findtext(_ATOM + "content") or "")
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


def _fetch_rss(subreddit, category, sort):
    suffix = "top.rss?t=day" if sort == "top" else "%s.rss" % sort
    url = "https://www.reddit.com/r/%s/%s" % (subreddit, suffix)
    return normalize_entries(_http_get(url), subreddit=subreddit, category=category, sort=sort)


# 익명 RSS 429 백오프 — 데이터센터 IP(AWS)는 Reddit이 익명 요청을 강하게 조여
# 첫 요청만 통과하고 직후 429가 잦다(실측 2026-07-25: 15/30/45초 간격에도 간헐 429).
# 영구차단은 아니라 넉넉히 벌려 재시도하면 대부분 통과한다. 일일 크론이 20분 걸려도
# 무방하므로 429일 때만 긴 백오프로 재시도한다(일반 예외는 짧게).
# 환경변수로 무재배포 튜닝: REDDIT_RL_RETRIES, REDDIT_RL_BACKOFF(콤마구분 초).
_RL_RETRIES = int(os.getenv("REDDIT_RL_RETRIES", "3"))
_RL_BACKOFF = [
    float(x) for x in os.getenv("REDDIT_RL_BACKOFF", "20,35,50").split(",") if x.strip()
] or [20.0, 35.0, 50.0]


def fetch_subreddit(subreddit, category="", sort="rising", limit=50, retries=2, pause=1.0):
    """서브레딧의 rising/top-day 영상 포스트 정규화 리스트. 실패 시 빈 리스트(부분실패 허용).

    크레덴셜이 있으면 OAuth(JSON·업보트 실값·100 req/분), 없으면 익명 RSS 폴백.
    익명 RSS가 429면 긴 백오프(_RL_BACKOFF)로 최대 _RL_RETRIES회 추가 재시도한다."""
    attempt = 0        # 일반 예외용 카운터
    rl_attempt = 0     # 429 전용 카운터(일반 예외와 독립)
    while True:
        try:
            if _has_oauth():
                return _fetch_oauth(subreddit, category, sort, limit)
            return _fetch_rss(subreddit, category, sort)
        except RateLimited:
            # 429 전용: 긴 백오프로 재시도. 소진되면 빈손(부분실패 허용).
            if rl_attempt >= _RL_RETRIES:
                return []
            time.sleep(_RL_BACKOFF[min(rl_attempt, len(_RL_BACKOFF) - 1)])
            rl_attempt += 1
        except Exception:
            # 그 외 오류: 짧은 백오프로 retries회까지.
            if attempt >= retries:
                return []
            time.sleep(pause * (attempt + 1))
            attempt += 1
