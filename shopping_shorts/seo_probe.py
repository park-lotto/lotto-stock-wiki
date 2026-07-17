"""6단계 SEO — 키워드를 유튜브에서 실제로 재서 근거를 만든다(2026-07-17).

경쟁사 SEO 생성기는 대본만 보고 문구를 뱉는다. 우리는 뽑은 키워드를 실제로
검색해 '수요가 있나'와 '작은 채널도 뚫리나'를 재서 화면에 근거로 띄운다.

⚠️ youtube_client.py는 발굴 파이프라인이 쓰는 코드라 수정하지 않는다.
   순수 헬퍼만 재사용하고, 측정은 이 모듈이 따로 한다.
   (search_shorts()는 pageInfo.totalResults를 버리고 결과가 키워드별로 안 갈려 재사용 불가)
"""

import html
from datetime import datetime, timedelta, timezone

import requests

from shopping_shorts.config import YOUTUBE_API_KEYS
from shopping_shorts.youtube_client import _LANG_REGION, _title_lang_ok

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

# 판정 문턱.
# _VIEWS_FLOOR만 T8 실측(2026-07-17)으로 근거가 생겼다 — 나머지는 아직 추측이다.
# 실측 6키워드의 상위5 중앙값: 다이슨에어랩 19k · 캠핑의자 102k · 빨대텀블러 151k ·
# 무선청소기 233k · 주방수납 253k · 제습기 848k. 10만은 '90일간 아무도 안 본 키워드'
# (다이슨에어랩)와 나머지를 가르는 자리에 실제로 놓여 있었다.
_VIEWS_FLOOR = 100_000       # 상위권 조회수(_TOP_N 중앙값)가 이 밑이면 '수요 없음'
_TOP_N = 5                   # 수요를 재는 표본 — 상위 몇 편으로 보나
# ★뚫림 판정 = "소형채널이 이 키워드로 실제 조회수를 낸 적 있나"(사장님 결정 2026-07-17).
# 비율이 아니라 편수다. 비율로 재던 옛 방식은 두 번 틀렸다:
#  ① 20편 전체로 재니 꼬리(정의상 영세채널)가 비율을 부풀려 대형 독식 키워드가 blue로 뒤집혔다
#     — 실측 '빨대텀블러'는 상위권을 구독 59만·49만이 먹고 소형은 1.6만 조회에 그쳤는데 blue였다.
#  ② 상위 5편으로만 재니 이번엔 blue가 아예 안 나왔다(상위권은 어느 키워드든 대개 큰 채널이다)
#     — 실측 '주방수납'은 구독 3,730명이 23.5만을 냈는데도 red였다.
_SMALL_HITS_MIN = 1          # 10만+ 낸 소형채널이 이 편수 이상이면 '뚫린다'
_SMALL_SUBS = 10_000         # 이 미만이면 소형채널
_WINDOW_DAYS = 90            # 최근 N일 안에 올라온 영상만
_SAMPLE_MAX = 20             # 키워드당 검색 결과 수
_SAMPLE_MIN = 3              # 이 밑이면 판정하지 않는다
_MAX_PROBE = 6               # 생성 1회당 측정할 키워드 상한 (search.list = 100유닛/회)


def judge(views_top, small_hits, sample_n):
    """측정치 → blue/red/dead/unknown.

    조회수만으로는 '대형채널이 독식한 키워드'와 '작은 채널도 뚫리는 키워드'가
    구분되지 않는다. 우리한테 필요한 건 후자라 둘을 같이 본다.

    인자:
      views_top  — 상위권 조회수(summarize의 views_top). 20편 중앙값이 **아니다**.
      small_hits — 소형채널이 _VIEWS_FLOOR를 넘긴 **편수**. 비율이 아니다.
    둘 다 이름과 다른 값을 넣으면 조용히 틀린 판정이 나온다(실제로 두 번 그랬다).
    """
    if not sample_n or sample_n < _SAMPLE_MIN:
        return "unknown"          # 표본 부족 — 거짓 근거를 만들지 않는다
    if (views_top or 0) < _VIEWS_FLOOR:
        return "dead"             # 검색해도 사람이 안 본다
    if (small_hits or 0) >= _SMALL_HITS_MIN:
        return "blue"             # 나 같은 채널이 여기서 조회수를 낸 적이 있다
    return "red"                  # 수요는 있으나 소형채널은 아무도 못 뚫었다


def _median(sorted_vals):
    n = len(sorted_vals)
    mid = n // 2
    return sorted_vals[mid] if n % 2 else (sorted_vals[mid - 1] + sorted_vals[mid]) // 2


def summarize(items):
    """[{title, views, subs}] → 측정치 dict.

    수요는 **상위 _TOP_N편의 중앙값**(views_top)으로 잰다. 20편 전체의 중앙값이
    아니다 — T8 실측에서 검색 결과가 극단적 롱테일로 드러났기 때문이다.
    '빨대텀블러' 90일: 1,525,523 / 950,512 / 150,651 / 92,205 / 24,016 … 9위부터 1만 아래.
    20편 중앙값은 10,230이라 중앙값으로 재면 150만짜리가 두 편 터진 키워드가
    '아무도 안 본다(dead)'가 된다. 꼬리는 그 키워드의 수요가 아니라 검색이 긁어온
    변두리 영상이다.

    views_median(20편 중앙값)도 같이 돌려준다 — 상위권에 들었을 때의 기대치라
    수요와 다른 질문에 답한다. 판정에는 쓰지 않는다.

    뚫림(small_hits)은 **10만+ 낸 영상들 중** 소형채널 편수로 잰다. 20편 전체로 재면
    꼬리의 영세채널이 비율을 부풀리고, 상위 5편으로만 재면 큰 히트만 보여 뚫림을 놓친다
    (둘 다 실측으로 확인 — 모듈 상단 주석 참조).

    subs가 없는 항목은 '큰 채널'로 친다 — 못 받아온 걸 작다고 치면
    블루오션이 과대평가돼서 없는 기회를 있다고 보고하게 된다.
    """
    n = len(items)
    if not n:
        return {"views_top": 0, "views_median": 0, "small_ratio": 0.0,
                "small_hits": 0, "hit_n": 0,
                "sample_n": 0, "top_titles": [], "verdict": "unknown"}
    views = sorted(int(it.get("views") or 0) for it in items)
    views_median = _median(views)
    views_top = _median(views[-_TOP_N:])      # 상위 _TOP_N편(없으면 있는 것 전부)
    # '뚫었다'고 칠 영상 = 실제로 조회수를 낸 것만. 구독자가 적어도 아무도 안 본
    # 영상은 뚫림의 증거가 아니다.
    hits = [it for it in items if int(it.get("views") or 0) >= _VIEWS_FLOOR]
    small_hits = sum(1 for it in hits if 0 < int(it.get("subs") or 0) < _SMALL_SUBS)
    small_ratio = small_hits / len(hits) if hits else 0.0
    top = sorted(items, key=lambda it: int(it.get("views") or 0), reverse=True)[:3]
    return {
        "views_top": views_top,
        "views_median": views_median,
        "small_ratio": small_ratio,      # 10만+ 낸 영상 중 소형 비율(20편 전체 아님)
        "small_hits": small_hits,        # 판정에 쓰는 값
        "hit_n": len(hits),              # 분모 — 화면이 'N편 중 M편'으로 보여준다
        "sample_n": n,
        "top_titles": [it.get("title") or "" for it in top],
        "verdict": judge(views_top, small_hits, n),
    }


def _unknown(keyword, region):
    """측정 실패 — 판정하지 않는다. 캐시하지 않으므로 다음에 다시 시도된다."""
    return {"keyword": keyword, "region": region, "views_top": 0, "views_median": 0,
            "small_ratio": 0.0, "small_hits": 0, "hit_n": 0, "sample_n": 0,
            "top_titles": [], "verdict": "unknown", "checked_at": None}


def _search(kw, tok, region, lang):
    """(status, items|None). items = [{video_id, channel_id, title}].

    네트워크 예외(타임아웃·연결끊김 등)도 실패로 접어서 status=0, items=None으로
    돌려준다 — 예외를 밖으로 던지면 SEO 문구 생성 자체가 죽는다(계약 위반).
    """
    since = (datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)).isoformat()
    try:
        r = requests.get(_SEARCH_URL, params={
            "part": "snippet", "q": kw, "type": "video", "videoDuration": "short",
            "order": "viewCount", "publishedAfter": since,
            "regionCode": region, "relevanceLanguage": lang,
            "maxResults": _SAMPLE_MAX, "key": tok}, timeout=30)
        if r.status_code != 200:
            return r.status_code, None
        # ★.json()도 try 안이다 — 200인데 본문이 JSON이 아니면(프록시·잘린 응답)
        # JSONDecodeError가 나는데 그건 RequestException의 서브클래스다. 밖에 두면
        # 이 모듈이 선언한 계약("예외를 밖으로 던지면 SEO 생성 자체가 죽는다")이 깨져
        # 이미 지불한 Gemini 결과째로 500이 된다.
        payload = r.json()
    except requests.exceptions.RequestException:
        return 0, None
    items = []
    for it in payload.get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid or not _title_lang_ok(sn.get("title"), lang):
            continue      # 외국 영상 제거 — 섞이면 측정이 틀어진다
        # 유튜브는 제목을 HTML 이스케이프해서 준다(실측: "아직도 &#39;맹물 커피&#39;").
        # 이 제목은 화면에 근거로 그대로 뜨므로 여기서 푼다.
        items.append({"video_id": vid, "channel_id": sn.get("channelId"),
                      "title": html.unescape(sn.get("title") or "")})
    return r.status_code, items


def _fetch_stats(url, ids, tok, field):
    """videos/channels statistics → (out={id: int}, ok).

    ok=False면 최소 한 청크가 실패(HTTP 에러·네트워크 예외)했다는 뜻 — out에 든
    값(특히 빈 dict)을 "진짜 0"으로 신뢰하면 안 된다. 호출부가 용도별로 다르게
    쓴다: views 실패는 위험(허위 '수요없음')이라 unknown 처리, subs 실패는
    기존처럼 '큰 채널'로 보수적 처리해 무해하다.
    """
    out = {}
    ok = True
    for i in range(0, len(ids), 50):          # API 상한 50개/호출
        chunk = [x for x in ids[i:i + 50] if x]
        if not chunk:
            continue
        try:
            r = requests.get(url, params={
                "part": "statistics", "id": ",".join(chunk), "key": tok}, timeout=30)
            if r.status_code != 200:
                ok = False
                continue
            payload = r.json()      # ★try 안 — 이유는 _search 참조
        except requests.exceptions.RequestException:
            ok = False
            continue
        for it in payload.get("items", []):
            out[it["id"]] = int((it.get("statistics") or {}).get(field) or 0)
    return out, ok


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
        views, views_ok = _fetch_stats(_VIDEOS_URL, [i["video_id"] for i in items], tok, "viewCount")
        if not views_ok:
            # search는 성공했는데 videos.list만 실패 — 전부 0으로 잡히면 'dead'로
            # 오판되고 7일간 캐시된다. 측정 실패는 캐시하지 않는다.
            out.append(_unknown(kw, region))
            continue
        subs, subs_ok = _fetch_stats(_CHANNELS_URL, [i["channel_id"] for i in items], tok, "subscriberCount")
        stat = summarize([{"title": i["title"],
                           "views": views.get(i["video_id"], 0),
                           "subs": subs.get(i["channel_id"], 0)} for i in items])
        stat.update({"keyword": kw, "region": region})
        # ★subs 조회가 실패하면 구독자가 전부 0으로 잡혀 '소형채널 0편' = red가 된다.
        # 판정은 보수적이라 그대로 내보내도 되지만 **캐시하면 그 red가 7일간 굳는다** —
        # 진짜 blue 키워드가 일주일 내내 "이걸 메인으로 쓰지 마라"로 Gemini에 먹인다.
        # views 실패를 캐시 안 하는 것과 같은 이유다(재시도로 자가치유되게 둔다).
        if subs_ok:
            store.put_keyword_stats(stat)      # 성공만 캐시 — 실패를 캐시하면 7일간 갇힌다
        stat["checked_at"] = datetime.now(timezone.utc).isoformat()
        out.append(stat)
    return out
