"""6단계 SEO — 키워드를 유튜브에서 실제로 재서 근거를 만든다(2026-07-17).

경쟁사 SEO 생성기는 대본만 보고 문구를 뱉는다. 우리는 뽑은 키워드를 실제로
검색해 '수요가 있나'와 '작은 채널도 뚫리나'를 재서 화면에 근거로 띄운다.

⚠️ youtube_client.py는 발굴 파이프라인이 쓰는 코드라 수정하지 않는다.
   순수 헬퍼만 재사용하고, 측정은 이 모듈이 따로 한다.
   (search_shorts()는 pageInfo.totalResults를 버리고 결과가 키워드별로 안 갈려 재사용 불가)
"""

from datetime import datetime, timedelta, timezone

import requests

from shopping_shorts.config import YOUTUBE_API_KEYS
from shopping_shorts.youtube_client import _LANG_REGION, _title_lang_ok

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

# 판정 문턱 — 실측 후 튜닝 대상. 이 숫자가 맞다는 근거는 아직 없다(설계 §10 리스크 1).
_VIEWS_FLOOR = 100_000       # 상위 쇼츠 조회수 중앙값이 이 밑이면 '수요 없음'
_SMALL_RATIO_FLOOR = 0.3     # 상위권 중 소형채널이 이 비율 이상이면 '뚫린다'
_SMALL_SUBS = 10_000         # 이 미만이면 소형채널
_WINDOW_DAYS = 90            # 최근 N일 안에 올라온 영상만
_SAMPLE_MAX = 20             # 키워드당 검색 결과 수
_SAMPLE_MIN = 3              # 이 밑이면 판정하지 않는다
_MAX_PROBE = 6               # 생성 1회당 측정할 키워드 상한 (search.list = 100유닛/회)


def judge(views_median, small_ratio, sample_n):
    """측정치 → blue/red/dead/unknown.

    조회수 중앙값만으로는 '대형채널이 독식한 키워드'와 '작은 채널도 뚫리는
    키워드'가 구분되지 않는다. 우리한테 필요한 건 후자라 둘을 같이 본다.
    """
    if not sample_n or sample_n < _SAMPLE_MIN:
        return "unknown"          # 표본 부족 — 거짓 근거를 만들지 않는다
    if (views_median or 0) < _VIEWS_FLOOR:
        return "dead"             # 검색해도 사람이 안 본다
    if (small_ratio or 0) >= _SMALL_RATIO_FLOOR:
        return "blue"             # 수요 있고 작은 채널도 상위권
    return "red"                  # 수요는 있으나 대형채널 독식


def summarize(items):
    """[{title, views, subs}] → 측정치 dict.

    subs가 없는 항목은 '큰 채널'로 친다 — 못 받아온 걸 작다고 치면
    블루오션이 과대평가돼서 없는 기회를 있다고 보고하게 된다.
    """
    n = len(items)
    if not n:
        return {"views_median": 0, "small_ratio": 0.0, "sample_n": 0,
                "top_titles": [], "verdict": "unknown"}
    views = sorted(int(it.get("views") or 0) for it in items)
    mid = n // 2
    views_median = views[mid] if n % 2 else (views[mid - 1] + views[mid]) // 2
    small = sum(1 for it in items if 0 < int(it.get("subs") or 0) < _SMALL_SUBS)
    small_ratio = small / n
    top = sorted(items, key=lambda it: int(it.get("views") or 0), reverse=True)[:3]
    return {
        "views_median": views_median,
        "small_ratio": small_ratio,
        "sample_n": n,
        "top_titles": [it.get("title") or "" for it in top],
        "verdict": judge(views_median, small_ratio, n),
    }


def _unknown(keyword, region):
    """측정 실패 — 판정하지 않는다. 캐시하지 않으므로 다음에 다시 시도된다."""
    return {"keyword": keyword, "region": region, "views_median": 0,
            "small_ratio": 0.0, "sample_n": 0, "top_titles": [],
            "verdict": "unknown", "checked_at": None}


def _search(kw, tok, region, lang):
    """(status, items|None). items = [{video_id, channel_id, title}]"""
    since = (datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)).isoformat()
    r = requests.get(_SEARCH_URL, params={
        "part": "snippet", "q": kw, "type": "video", "videoDuration": "short",
        "order": "viewCount", "publishedAfter": since,
        "regionCode": region, "relevanceLanguage": lang,
        "maxResults": _SAMPLE_MAX, "key": tok}, timeout=30)
    if r.status_code != 200:
        return r.status_code, None
    items = []
    for it in r.json().get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid or not _title_lang_ok(sn.get("title"), lang):
            continue      # 외국 영상 제거 — 섞이면 측정이 틀어진다
        items.append({"video_id": vid, "channel_id": sn.get("channelId"),
                      "title": sn.get("title") or ""})
    return r.status_code, items


def _fetch_stats(url, ids, tok, field):
    """videos/channels statistics → {id: int}. 실패는 조용히 건너뛴다(빈 dict)."""
    out = {}
    for i in range(0, len(ids), 50):          # API 상한 50개/호출
        chunk = [x for x in ids[i:i + 50] if x]
        if not chunk:
            continue
        r = requests.get(url, params={
            "part": "statistics", "id": ",".join(chunk), "key": tok}, timeout=30)
        if r.status_code != 200:
            continue
        for it in r.json().get("items", []):
            out[it["id"]] = int((it.get("statistics") or {}).get(field) or 0)
    return out


def probe_keywords(keywords, store, lang="ko"):
    """키워드별 유튜브 실측. 캐시 우선, _MAX_PROBE개까지만.

    비용: 키워드당 search.list(100u) + videos.list(1u) + channels.list(1u) = 102u.
    발굴 파이프라인과 같은 키풀을 나눠 쓰므로 상한과 캐시가 필수다.
    키 소진·실패는 verdict='unknown'으로 우아하게 꺼진다 — SEO 문구 생성이 측정보다 우선이다.
    """
    region = _LANG_REGION.get(lang, "KR")
    out = []
    tokens = list(YOUTUBE_API_KEYS)
    tok_idx = 0
    for kw in list(keywords)[:_MAX_PROBE]:
        cached = store.get_keyword_stats(kw, region)
        if cached:
            out.append(cached)
            continue
        if not tokens:
            out.append(_unknown(kw, region))
            continue
        items = None
        while tok_idx < len(tokens):
            status, items = _search(kw, tokens[tok_idx], region, lang)
            if status == 403:      # 쿼터 소진 — 다음 키로 이 키워드부터 재시도
                tok_idx += 1
                items = None
                continue
            break
        if items is None:
            out.append(_unknown(kw, region))
            continue
        tok = tokens[min(tok_idx, len(tokens) - 1)]
        views = _fetch_stats(_VIDEOS_URL, [i["video_id"] for i in items], tok, "viewCount")
        subs = _fetch_stats(_CHANNELS_URL, [i["channel_id"] for i in items], tok, "subscriberCount")
        stat = summarize([{"title": i["title"],
                           "views": views.get(i["video_id"], 0),
                           "subs": subs.get(i["channel_id"], 0)} for i in items])
        stat.update({"keyword": kw, "region": region})
        store.put_keyword_stats(stat)          # 성공만 캐시 — 실패를 캐시하면 7일간 갇힌다
        stat["checked_at"] = datetime.now(timezone.utc).isoformat()
        out.append(stat)
    return out
