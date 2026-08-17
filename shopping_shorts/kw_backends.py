"""한국어 키워드 검색 백엔드 3종 — 인스타·틱톡·유튜브(2026-08-17).

`cn_backends`(샤오홍슈·도우인)의 형제다. 계약도 정규화도 **똑같은 것을 쓴다**
(`cn_backends.normalize`) — 카드 스키마를 두 군데서 정하면 한쪽만 고쳐져
프론트가 조용히 깨진다(0순위-B).

계약: fn(keyword, max_results) -> [normalize된 row, ...] / 예외를 안 던진다.

비용
  유튜브   : $0 (YouTube Data API 무료쿼터. 검색 1회 = 100유닛)
  인스타   : $0 (Playwright + 우리 프록시. 바이트 요금은 프록시 쪽에서 나간다)
  틱톡     : Apify 유료 — 회당 실측값은 kw_search._COST 참조
"""
import re

from shopping_shorts import cn_backends

# 인스타는 '해시태그' 한 덩어리만 받는다(띄어쓰기·특수문자 불가).
# "에어프라이어 감자칩" → "에어프라이어감자칩"
_TAG_STRIP = re.compile(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_]+")


def to_hashtag(keyword):
    """검색어 → 인스타 해시태그. 못 만들면 빈 문자열."""
    return _TAG_STRIP.sub("", keyword or "")


def instagram(keyword, max_results):
    """인스타 해시태그 검색(무료 — Playwright+프록시).

    ⚠️ 해시태그 SERP엔 길이가 없다 → duration=None → normalize가 is_short=True로
    본다. 렌즈의 롱폼 컷은 '길이를 아는 것만' 자르므로 여기 결과는 안 잘린다
    (모르는 걸 자르면 멀쩡한 릴스가 통째로 사라진다 — 렌즈에서 이미 겪은 함정)."""
    tag = to_hashtag(keyword)
    if not tag:
        return []
    from shopping_shorts import instagram_playwright
    rows = instagram_playwright.search_hashtag(tag) or []
    out = []
    for r in rows[:max_results]:
        url = r.get("url")
        if not url:
            continue
        out.append(cn_backends.normalize({
            "url": url,
            # SERP엔 캡션이 없다(실측 스키마: username/code/참여도만) —
            # 제목을 지어내지 않고 계정명을 보여준다. 비면 프론트가 빈칸으로 둔다.
            "title": "",
            "thumbnail": r.get("thumbnail") or "",
            "channel": r.get("username") or "",
            "likes": r.get("like_count"),
            "views": r.get("play_count"),
            "duration": None,
        }, "instagram"))
    return out


def tiktok(keyword, max_results):
    """틱톡 키워드 검색(Apify — 유료). 토큰이 없으면 조용히 0건."""
    from shopping_shorts import tiktok_search
    try:
        rows = tiktok_search.search(keyword, max_results) or []
    except RuntimeError:
        return []          # 토큰 미설정 — 사슬이 다음으로 넘어가게 둔다
    out = []
    for r in rows[:max_results]:
        url = r.get("url")
        if not url:
            continue
        out.append(cn_backends.normalize({
            "url": url,
            "title": r.get("title") or "",
            "thumbnail": r.get("thumbnail") or "",
        }, "tiktok"))
    return out


def youtube(keyword, max_results):
    """유튜브 키워드 검색(무료 쿼터). 렌즈와 같은 조건 — 숏폼·한국어.

    ★`duration="short"`/`language="ko"`는 렌즈가 이미 쓰는 값이다(2026-08-16에
    '유튜브가 화면을 도배한다'를 고치며 넣은 것). 여기서 다르게 주면 같은 화면에
    기준이 두 개가 된다.

    ⚠️ `youtube_search.search`는 **키 풀이 전부 소진되면 예외를 던진다**(실측:
    독스트링 "키 풀 전체 소진 시 마지막 오류를 던진다"). 백엔드 계약은 '예외를
    안 던진다'이므로 여기서 삼켜 0건으로 만든다 — 안 그러면 유튜브 쿼터가
    마른 날 인스타·틱톡 결과까지 같이 안 보일 수 있다.
    ※ 응답에 채널명이 없다(_parse_items가 url/title/thumbnail만 만든다) —
      없는 값을 지어내지 않고 빈칸으로 둔다."""
    from shopping_shorts import youtube_search
    try:
        rows = youtube_search.search(keyword, max_results,
                                     duration="short", language="ko") or []
    except Exception:
        return []
    out = []
    for r in rows[:max_results]:
        url = r.get("url")
        if not url:
            continue
        out.append(cn_backends.normalize({
            "url": url,
            "title": r.get("title") or "",
            "thumbnail": r.get("thumbnail") or "",
        }, "youtube"))
    return out
