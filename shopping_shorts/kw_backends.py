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
import os
import re

from shopping_shorts import cn_backends, config
from shopping_shorts.channel_archive import block_heavy_assets, playwright_proxy_kw

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


_TIKTOK_EXTRACT = """
() => [...document.querySelectorAll('a[href*="/video/"]')].map(a => {
  const card = a.closest('[data-e2e="search_top-item"], [data-e2e*="search"], div');
  const img = card ? card.querySelector('img') : null;
  const t = card ? card.querySelector('[data-e2e*="desc"], [class*=desc]') : null;
  return {
    url: a.href,
    title: (t ? t.innerText : '').trim(),
    thumb: img ? img.getAttribute('src') : null,
  };
})
"""


def pw_tiktok(keyword, max_results):
    """틱톡 검색을 프록시+세션으로 긁는다. 비용 0.

    ⚠️2026-08-17 현재 **세션 파일이 없어 항상 빈손**이고 Apify로 폴백된다.
    도우인(pw_douyin)과 같은 상태다 — 세션이 생기면 이 경로가 그대로 살아나
    비용이 0이 되고, _CHAIN도 엔드포인트도 프론트도 안 고친다.

    ★서버 실측(2026-08-17)으로 갈라둔 것 — "프록시가 막힌다"가 아니다:
      · 프록시(kr)로 검색 페이지 도달 O, 제목도 한국어로 정상
      · `/api/search/general/full/` 도 **200** 으로 온다
      · 그런데 **본문이 비어** 있고 로그인 모달이 뜬다 → 세션 문제
    그래서 세션 없이 부르면 브라우저를 띄우지 않고 즉시 0건으로 접는다
    (괜히 띄우면 프록시 바이트만 버린다)."""
    session = getattr(config, "TIKTOK_SESSION_PATH", "")
    if not session or not os.path.exists(session):
        return []
    from urllib.parse import quote
    url = "https://www.tiktok.com/search?q=" + quote(keyword)
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(storage_state=session, locale="ko-KR",
                                      **_tiktok_proxy_kw())
            page = ctx.new_page()
            block_heavy_assets(page)
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(9000)      # 검색 카드가 채워질 여유(샤오홍슈와 같은 값)
            cards = page.evaluate(_TIKTOK_EXTRACT)
            ctx.close()
            browser.close()
    except Exception:
        return []
    out = []
    seen = set()
    for c in cards or []:
        u = (c or {}).get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(cn_backends.normalize({
            "url": u, "title": c.get("title"), "thumbnail": c.get("thumb"),
        }, "tiktok"))
    return out[:max_results]


def _tiktok_proxy_kw():
    """틱톡 출구 프록시(한국). 프록시 설정이 없으면 직결.

    ★계정(세션)과 프록시를 **한 함수에서 같이** 정한다 — 따로 정하면 어긋난다
    (2026-08-09 인스타 실사고: 계정↔IP 불일치가 본인확인 챌린지로 나타났다).
    """
    user, pw = os.getenv("WEBSHARE_USER", ""), os.getenv("WEBSHARE_PASS", "")
    if not (user and pw):
        return {}
    host = os.getenv("WEBSHARE_HOST", "p.webshare.io:80")
    cc = os.getenv("TIKTOK_PROXY_COUNTRY", "kr")
    proxy = playwright_proxy_kw(f"http://{user}-{cc}-1:{pw}@{host}")
    return {"proxy": proxy} if proxy else {}


def apify_tiktok(keyword, max_results):
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
