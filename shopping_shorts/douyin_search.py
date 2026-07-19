"""Apify Douyin Search Scraper(zen-studio/douyin-search-scraper)로 키워드
검색 → 정규화된 후보 리스트. apify_client.py의 토큰 로테이션을 재사용
(2026-07-10, 5대 플랫폼 확장 요청으로 추가).

실측(2026-07-10): 먼저 조사했던 natanielsantos~douyin-scraper 액터는 흔한
영어 키워드("iphone")로도 0건이 나와 신뢰도가 낮다고 판단해 보류했음.
같은 개발자(zen-studio)의 샤오홍슈 액터가 실제로 잘 작동했던 것에 착안해
zen-studio~douyin-search-scraper로 재시도 — "iphone" 키워드로 실제 영상
3건(재생 URL·썸네일 포함) 확인됨.

2026-07-18: 렌즈 유사영상 개편으로 채널명·조회수·좋아요·영상길이·숏폼여부 메타 추가.
이 액터는 TikTok(clockworks) 스키마(itemTitle/text/videoMeta/type)를 따르므로
authorMeta.name · playCount · diggCount · videoMeta.duration 을 우선 후보로 쓴다."""
from shopping_shorts.apify_client import _run_with_rotation
from shopping_shorts.config import APIFY_TOKENS

_ACTOR = "zen-studio~douyin-search-scraper"
_SHORT_MAX_SECS = 90   # 이 이하(또는 길이 불명)면 숏폼으로 본다


def _num(v):
    """정수로 변환 가능하면 int, 아니면 None('1.2만' 같은 문자 값은 버린다)."""
    if isinstance(v, bool):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _first(item, *paths):
    """후보 경로들(문자열 키 또는 (키,키...) 튜플)을 순서대로 훑어 첫 비어있지 않은 값 반환."""
    for p in paths:
        keys = p if isinstance(p, tuple) else (p,)
        cur = item
        ok = True
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and cur not in (None, "", {}, []):
            return cur
    return None


def _duration_secs(item):
    """영상 길이(초). 초 또는 밀리초로 올 수 있어 큰 값이면 ms로 보고 환산."""
    n = _num(_first(item, ("videoMeta", "duration"), "duration", "videoDuration"))
    if n is None:
        return None
    return n // 1000 if n > 6000 else n


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드 → [{url, title, thumbnail, play_url, channel, likes, views, duration, is_short}, ...]."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("douyin_search: APIFY_TOKEN이 설정되지 않았습니다")
    payload = {"keywords": [keyword], "maxResultsPerQuery": max_results, "sort": "general"}
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        url = item.get("url")
        if not url or item.get("type") != "video":
            continue
        video_meta = item.get("videoMeta") or {}
        dur = _duration_secs(item)
        out.append({
            "url": url,
            "title": item.get("itemTitle") or item.get("previewTitle") or item.get("text", ""),
            "thumbnail": video_meta.get("cover", ""),
            "play_url": _first(item, ("videoMeta", "playUrl"),
                               ("videoMeta", "downloadUrl")) or "",   # 미리보기용 직접 mp4
            "channel": _first(item, ("authorMeta", "nickName"), ("authorMeta", "name")) or "",
            "likes": _num(_first(item, ("statistics", "diggCount"))),
            "views": _num(_first(item, ("statistics", "playCount"))),
            "duration": dur,
            "is_short": dur is None or dur <= _SHORT_MAX_SECS,
        })
    return out
