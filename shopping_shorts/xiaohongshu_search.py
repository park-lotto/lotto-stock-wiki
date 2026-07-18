"""Apify RedNote(Xiaohongshu/샤오홍슈) Search Scraper(zen-studio/rednote-search-scraper)로
키워드 검색 → 정규화된 후보 리스트. apify_client.py의 토큰 로테이션을 재사용
(2026-07-10, 5대 플랫폼 확장 요청으로 추가).

실측(2026-07-10): noteType="video"로 요청하면 실제 재생 가능한 영상 노트만
나옴(video.streams에 실 mp4 URL 포함) — 사진 노트가 섞여 나오는 문제는 없었음.
같이 조사한 더우인(douyin-scraper 액터)은 흔한 키워드로도 0건이 나와 신뢰도가
낮다고 판단, 우선 샤오홍슈만 연동한다.

2026-07-18: 렌즈 유사영상 개편으로 채널명·좋아요·조회수·영상길이·숏폼여부 메타 추가.
실제 액터 응답의 정확한 필드명을 라이브로 확인하지 못해 여러 후보 경로를 방어적으로
훑고, 없으면 빈칸/None으로 둔다(그 칸만 표시 안 됨). url/title/thumbnail은 기존과 동일."""
from shopping_shorts.apify_client import _run_with_rotation
from shopping_shorts.config import APIFY_TOKENS

_ACTOR = "zen-studio~rednote-search-scraper"
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
    """후보 경로들(문자열 키 또는 (키,키...) 튜플)을 순서대로 훑어 첫 비어있지 않은 값 반환.
    실제 액터 필드명이 확실치 않아 스키마 변형에 방어적으로 대응한다."""
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


def _duration_secs(item, video):
    """영상 길이(초). rednote는 video.duration_seconds(초). 혹시 ms면 큰 값을 환산."""
    n = _num(_first(video, "duration_seconds", "duration") or _first(item, "duration"))
    if n is None:
        return None
    return n // 1000 if n > 6000 else n


def _cover(item, video):
    """노트 커버 이미지. ★video.thumbnail은 스크러빙 스프라이트(격자 몽타주)라 쓰면 안 된다
    (2026-07-18 라이브 실측). images[cover_image_index].url 이 진짜 커버. 없으면 순차 폴백."""
    imgs = item.get("images") or []
    idx = item.get("cover_image_index")
    if isinstance(idx, int) and 0 <= idx < len(imgs):
        u = (imgs[idx] or {}).get("url")
        if u:
            return u
    if imgs:
        u = (imgs[0] or {}).get("url")
        if u:
            return u
    return video.get("first_frame") or video.get("thumbnail") or ""


def search(keyword, max_results=10, token=None, timeout=180, poll_interval=5):
    """키워드 → [{url, title, thumbnail, play_url, channel, likes, views, duration, is_short}, ...]."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("xiaohongshu_search: APIFY_TOKEN이 설정되지 않았습니다")
    payload = {
        "keywords": [keyword],
        "maxResults": max_results,
        "noteType": "video",
        "topUpFromOtherSorts": False,
    }
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_ACTOR)
    out = []
    for item in items:
        url = item.get("url")
        video = item.get("video") or {}
        if not url or item.get("type") != "video" or not video.get("url_720p"):
            continue  # noteType=video로도 사진 노트가 섞여 나올 가능성 대비 이중 확인
        dur = _duration_secs(item, video)
        out.append({
            "url": url,
            "title": item.get("title") or item.get("desc", ""),
            "thumbnail": _cover(item, video),        # ★images 커버(스프라이트 아님)
            "play_url": video.get("url_720p", ""),   # 인라인 미리보기용 직접 mp4
            "channel": _first(item, ("author", "nickname"), ("author", "name")) or "",
            "likes": _num(_first(item, ("engagement", "liked_count"),
                                 ("engagement", "likedCount"))),
            "views": _num(_first(item, ("engagement", "view_count"),
                                 ("engagement", "viewed_count"))),
            "duration": dur,
            "is_short": dur is None or dur <= _SHORT_MAX_SECS,
        })
    return out
