"""YouTube Data API v3 어댑터 — 키워드로 인기 Shorts 발굴 + 통계.

무료(쿼터 내). config.YOUTUBE_API_KEYS를 순서대로 시도(쿼터 초과 시 다음 키).
검색(search.list)은 통계가 없어 videos.list로 조회수·좋아요·댓글을 채운다.
"""
import requests
from shopping_shorts.config import YOUTUBE_API_KEYS

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _stats(video_ids, token):
    """videos.list(statistics) → {video_id: {views,likes,comments}}."""
    out = {}
    for i in range(0, len(video_ids), 50):          # API 상한 50개/호출
        chunk = video_ids[i:i + 50]
        r = requests.get(_VIDEOS_URL, params={
            "part": "statistics", "id": ",".join(chunk), "key": token}, timeout=30)
        if r.status_code != 200:
            continue
        for it in r.json().get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = {
                "views": int(s.get("viewCount") or 0),
                "likes": int(s.get("likeCount") or 0),
                "comments": int(s.get("commentCount") or 0),
            }
    return out


# 언어코드 → YouTube regionCode(검색 지역 편향). 없는 언어는 기본 KR.
_LANG_REGION = {"ko": "KR", "en": "US", "ja": "JP", "zh": "TW", "ru": "RU"}


def _search_page(kw, published_after_iso, max_per_kw, tok, region="KR", lang="ko"):
    """키워드 하나를 토큰 하나로 검색. 반환: (status_code, items_or_None).
    region/lang로 지역·언어를 편향(기본 한국/한국어) — 외국 영상 혼입 방지."""
    r = requests.get(_SEARCH_URL, params={
        "part": "snippet", "q": kw, "type": "video", "videoDuration": "short",
        "order": "viewCount", "publishedAfter": published_after_iso,
        "regionCode": region, "relevanceLanguage": lang,
        "maxResults": min(max_per_kw, 50), "key": tok}, timeout=30)
    if r.status_code != 200:
        return r.status_code, None
    items = []
    for it in r.json().get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid:
            continue
        items.append({
            "video_id": vid, "channel_id": sn.get("channelId"),
            "channel_title": sn.get("channelTitle"),
            "title": sn.get("title"), "description": sn.get("description"),
            "thumbnail": ((sn.get("thumbnails") or {}).get("high") or {}).get("url", ""),
            "published_at": sn.get("publishedAt"),
        })
    return r.status_code, items


def search_shorts(keywords, published_after_iso, max_per_kw=20, token=None, lang="ko"):
    """키워드별로 최신·인기 영상 검색 → 통계 채운 원시 dict 리스트.

    lang: 검색 언어(ko/en/ja/zh/ru). 지역(regionCode)은 언어에 매핑(기본 한국/한국어)
    → 외국 영상 혼입 방지. 키워드는 이미 해당 언어로 번역돼 들어온다고 가정.

    쿼터 초과(403) 시 다음 키로 로테이션: 검색 요청이 403이면 그 토큰은
    이후 검색에도 다시 시도하지 않고 다음 토큰으로 전체 검색을 재시도한다.
    모든 토큰이 실패해야 포기(마지막 실패 결과로 빈 처리). 호출부가 명시적으로
    token=을 넘기면(단일 토큰) 로테이션 없이 그 토큰만 사용하는 기존 동작 유지."""
    tokens = [token] if token else list(YOUTUBE_API_KEYS)
    if not tokens:
        raise RuntimeError("YOUTUBE_API_KEY 미설정")
    region = _LANG_REGION.get(lang, "KR")

    tok = tokens[0]
    tok_idx = 0
    raw = []
    for kw in keywords:
        while True:
            status, items = _search_page(kw, published_after_iso, max_per_kw, tok, region, lang)
            if status == 403 and tok_idx + 1 < len(tokens):
                tok_idx += 1
                tok = tokens[tok_idx]
                continue  # 다음 키로 이 키워드부터 재시도
            break
        if items:
            raw.extend(items)
    stats = _stats([r["video_id"] for r in raw], tok)
    for r in raw:
        r.update(stats.get(r["video_id"], {"views": 0, "likes": 0, "comments": 0}))
    return raw
