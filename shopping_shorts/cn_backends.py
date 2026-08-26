"""CN 검색 백엔드 4종(Playwright·Apify × 샤오홍슈·도우인).

★계정과 프록시는 **함께** 정한다(0순위-B). 따로 정하면 어긋난다 —
2026-08-09 인스타 실사고(계정↔IP 불일치로 챌린지)와 같은 함정.

각 백엔드의 계약: (keyword, max_results) -> list[dict]
  - 성공: normalize()를 거친 dict 리스트
  - 실패/차단: 빈 리스트를 돌려준다(예외를 밖으로 던지지 않는다).
    폴백 판정은 cn_search가 한다 — 백엔드는 '못 가져왔다'만 알린다.
"""
import os

from shopping_shorts import config, douyin_search, xiaohongshu_search
from shopping_shorts.channel_archive import block_heavy_assets, playwright_proxy_kw

_SHORT_MAX_SECS = 90

_SCHEMA_KEYS = ("url", "title", "thumbnail", "play_url",
                "channel", "likes", "views", "duration")


def _num(v):
    """정수로 바꿀 수 있으면 int, 아니면 None. '1.2만' 같은 문자값은 버린다.

    ★OverflowError까지 잡는다 — float('inf')는 ValueError가 아니라 OverflowError다.
    normalize는 백엔드가 행마다 부르므로, 여기서 예외가 새면 그 백엔드 결과가
    통째로 죽는다(모듈 계약: 백엔드는 예외를 밖으로 던지지 않는다)."""
    if isinstance(v, bool):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError, OverflowError):
        return None


def normalize(row, platform):
    """백엔드 원본 dict → 프론트가 기대하는 고정 스키마.

    ★키를 항상 전부 채운다. 빠진 키가 있으면 프론트 카드가 조용히 깨지는데,
    화면에선 '결과가 안 나온다'로만 보여 원인을 못 찾는다."""
    out = {"platform": platform}
    for k in _SCHEMA_KEYS:
        out[k] = row.get(k)
    out["title"] = out["title"] or ""
    out["channel"] = out["channel"] or ""
    out["likes"] = _num(out["likes"])
    out["views"] = _num(out["views"])
    dur = _num(out["duration"])
    out["duration"] = dur
    out["is_short"] = dur is None or dur <= _SHORT_MAX_SECS
    return out


def _apify(mod, platform, keyword, max_results):
    """Apify 액터 1회 실행. 실패는 빈 리스트로 삼킨다(계약).

    비용(2026-08-17 실측): 도우인 $0.04005/회 · 샤오홍슈 $0.098/회.
    무료 한도는 계정당 월 $5이고 **이월되지 않는다**(안 쓰면 소멸)."""
    try:
        rows = mod.search(keyword, max_results=max_results) or []
        return [normalize(r, platform) for r in rows]
    except Exception:
        return []


def apify_douyin(keyword, max_results):
    return _apify(douyin_search, "douyin", keyword, max_results)


def apify_xiaohongshu(keyword, max_results):
    return _apify(xiaohongshu_search, "xiaohongshu", keyword, max_results)


_XHS_BASE = "https://www.rednote.com"

# rednote.com 검색결과 카드에서 뽑을 것. 셀렉터는 2026-08-17 서버 실측으로 확정
# (section.note-item 18개 중 a.cover[href] 17개). xiaohongshu.com(중국 내수 도메인)은
# 비중국 IP를 하드 차단하므로 국제용 rednote.com만 쓴다(2026-07-29 실측).
_XHS_EXTRACT = """
() => [...document.querySelectorAll('section.note-item')].map(el => {
  const a = el.querySelector('a.cover[href]') || el.querySelector('a[href]');
  const img = el.querySelector('img');
  const t = el.querySelector('.title, [class*=title]');
  const like = el.querySelector('.like-wrapper, [class*=like]');
  return {
    url: a ? a.getAttribute('href') : null,
    title: (t ? t.innerText : (el.innerText || '').split('\\n')[0] || '').trim(),
    thumb: img ? img.getAttribute('src') : null,
    likes: like ? (like.innerText || '').trim() : null,
  };
})
"""


def _pw_xhs_rows(cards):
    """추출된 카드 배열 → 스키마 dict. URL 없는 카드는 버린다."""
    out = []
    for c in cards or []:
        href = (c or {}).get("url")
        if not href:
            continue
        url = href if href.startswith("http") else _XHS_BASE + href
        out.append(normalize({"url": url, "title": c.get("title"),
                              "thumbnail": c.get("thumb"),
                              "likes": c.get("likes")}, "xiaohongshu"))
    return out


def pw_xiaohongshu(keyword, max_results):
    """로그인 세션으로 rednote 검색결과를 긁는다. 비용 0.

    세션이 죽으면 카드가 0개가 되고, cn_search가 Apify로 폴백한다.
    ⚠️세션 판정을 `"loggedIn":false` 문자열로 하지 마라 — HTML 다른 곳에도 그 문자열이
    있어 오탐한다(2026-08-17 실측). 판정은 **카드 수**로 한다."""
    from urllib.parse import quote

    session = getattr(config, "XIAOHONGSHU_SESSION_PATH", "")
    if not session or not os.path.exists(session):
        return []
    url = f"{_XHS_BASE}/search_result?keyword={quote(keyword)}"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(storage_state=session)
            page = ctx.new_page()
            # 샤오홍슈는 **직결**(프록시 없음)이라 과금 대상은 아니지만, 이미지를 안 받으면
            # 그만큼 빨라진다. _XHS_EXTRACT는 img의 **src 속성 문자열**만 읽으므로
            # 본체 로드와 무관하다 — 실측(2026-08-17 Playwright): 차단 ON에서도
            # img의 src속성 1/1 유지, image·font 응답만 사라지고 xhr·document·CSS는 통과.
            block_heavy_assets(page)
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(9000)      # SSR 카드가 채워질 여유(서버 실측값)
            cards = page.evaluate(_XHS_EXTRACT)
            ctx.close()
            browser.close()
    except Exception:
        return []
    return _pw_xhs_rows(cards)[:max_results]


# 도우인 전용 출구 국가. 한국 IP로는 캡차+로그인벽이 뜨고, CN/HK면 사라진다(2026-08-17 실측).
_DOUYIN_CC = os.getenv("DOUYIN_PROXY_COUNTRY", "cn")


def douyin_context_kw(session_path):
    """★계정(세션)과 프록시를 **함께** 돌려준다.

    따로 정하면 어긋난다 — 2026-08-09 인스타 실사고에서 계정은 로테이션이 고르고
    프록시는 다른 코드가 정해 계정↔IP가 틀어졌고, 그게 본인확인 챌린지로 나타났다.
    한 함수에서 같이 정하면 그 사고가 성립하지 않는다."""
    kw = {"storage_state": session_path, "locale": "zh-CN",
          "timezone_id": "Asia/Shanghai"}
    user, pw = os.getenv("WEBSHARE_USER", ""), os.getenv("WEBSHARE_PASS", "")
    if user and pw:
        host = os.getenv("WEBSHARE_HOST", "p.webshare.io:80")
        kw["proxy"] = playwright_proxy_kw(f"http://{user}-{_DOUYIN_CC}-1:{pw}@{host}")
    return kw


def _douyin_rows(payloads):
    """검색 API 응답 → 스키마 dict(중복 aweme_id 제거).

    ★DOM이 아니라 네트워크 응답을 쓴다 — 도우인 검색카드에는 href도 aweme_id도
    없어서(2026-07-19·08-17 실측) DOM 파싱이 원리적으로 불가능하다."""
    seen, out = set(), []
    for data in payloads or []:
        if not isinstance(data, dict):
            continue
        lst = data.get("data") or data.get("aweme_list") or []
        if not isinstance(lst, list):
            continue
        for it in lst:
            if not isinstance(it, dict):
                continue
            aw = it.get("aweme_info") or it.get("aweme") or it
            if not isinstance(aw, dict):
                continue
            aid = aw.get("aweme_id")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            stats = aw.get("statistics") or {}
            out.append(normalize({
                "url": f"https://www.douyin.com/video/{aid}",
                "title": aw.get("desc"),
                "channel": (aw.get("author") or {}).get("nickname"),
                "likes": stats.get("digg_count"),
                "views": stats.get("play_count"),
            }, "douyin"))
    return out


def pw_douyin(keyword, max_results):
    """도우인 검색을 CN프록시+세션으로 긁는다.

    ⚠️2026-08-17 현재 도우인 세션이 없어 항상 빈손이고 Apify로 폴백된다.
    세션이 생기면(QR 로그인) 이 경로가 그대로 살아나 비용이 0이 된다 —
    _CHAIN도 호출부도 프론트도 고칠 필요가 없다."""
    from urllib.parse import quote

    session = getattr(config, "DOUYIN_SESSION_PATH", "")
    if not session or not os.path.exists(session):
        return []

    captured = []

    def _on_response(resp):
        try:
            if "/aweme/" in resp.url and "search" in resp.url:
                captured.append(resp.json())
        except Exception:
            pass          # 응답 하나가 JSON이 아니어도 수집은 계속된다

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(**douyin_context_kw(session))
            ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
            page = ctx.new_page()
            # ★프록시 대역폭 절감(2026-08-17) — 도우인은 CN 주거용 프록시로 나가는데
            #   검색 결과는 아래 _on_response(API 응답)로만 받는다. 카드 썸네일·영상은
            #   URL 문자열만 저장하므로 이미지·미디어 본체를 받을 이유가 없다.
            #   판단은 channel_archive.block_heavy_assets 한 벌뿐이다(0순위-B).
            block_heavy_assets(page)
            page.on("response", _on_response)
            page.goto(f"https://www.douyin.com/search/{quote(keyword)}",
                      timeout=70000, wait_until="domcontentloaded")
            page.wait_for_timeout(12000)
            ctx.close()
            browser.close()
    except Exception:
        return []
    return _douyin_rows(captured)[:max_results]
