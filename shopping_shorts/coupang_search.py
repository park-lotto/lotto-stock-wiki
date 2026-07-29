"""쿠팡 상품검색 크롤(2026-07-29) — 파트너스 오픈API 승인 전까지 쓰는 대체 경로.

coupang_partners.search_products()가 승인 전엔 items=[]만 돌려주므로(사장님이 새 탭에서
직접 고르고 URL을 복사) 손이 많이 간다. 그 중간 단계로, 검색 결과를 **화면 안 카드**로
가져와 클릭 한 번에 상품이 확정되게 한다. 반환 형태는 승인 후 API와 같은 계약을 쓴다 —
`{"ok", "items":[{product_id,name,url,image,price,...}], "search_url", "source"}`.

★실측(2026-07-29, 이 파일을 만들며 직접 확인):

| 경로 | 결과 |
|---|---|
| httpx / curl_cffi(chrome124 위장), 로컬 | 403 Access Denied (홈페이지조차) |
| Playwright **헤드리스**, 로컬 | 403 |
| Playwright **헤드풀 + channel="chrome"**, 로컬(주거용 IP) | **200 · 상품 58건** |
| 서버(AWS) 직결, xvfb + 헤드풀 chrome | 403 |
| 서버 + Webshare `YTDLP_PROXY`(데이터센터 플랜) | 403 |

즉 쿠팡(Akamai)은 **데이터센터 IP를 통째로 막고, 헤드리스도 막는다**. 유튜브 쇼츠·Reddit
때와 같은 패턴(memory: reference_youtube_shorts_datacenter_block). 그래서 이 모듈은
**주거용 프록시(COUPANG_PROXY) + 헤드풀 Chrome**을 전제로 한다. 프록시가 비어 있으면
직결로 가는데, 그건 로컬 개발 PC(주거용 IP)에서만 통한다.

실패하면 예외를 던지지 않고 `ok:False + notice`로 접는다 — 이 기능이 죽어도 기존 수동
흐름(검색 링크 새 탭 + URL 붙여넣기)이 그대로 남아 있어야 한다.
"""
import urllib.parse

from shopping_shorts import config, coupang_partners

# 검색결과 카드에서 필요한 것만 뽑는다. 클래스명은 해시가 붙은 CSS 모듈이라
# (`ProductUnit_productUnit__Qd6sv`) 정확히 일치시키지 않고 접두사로 잡는다 —
# 배포마다 해시가 바뀐다.
_EXTRACT_JS = r"""(limit)=>{
  const out=[];
  const units=document.querySelectorAll('li[class*=ProductUnit_productUnit]');
  for(const li of units){
    const a=li.querySelector('a[href*="/vp/products/"]');
    if(!a) continue;
    const m=(a.getAttribute('href')||'').match(/\/vp\/products\/(\d+)/);
    if(!m) continue;
    const img=li.querySelector('img');
    const info=li.querySelector('div[class*=productInfo]');
    const priceEl=li.querySelector('div[class*=PriceArea]');
    const ratingEl=li.querySelector('[class*=ProductRating_productRating]');
    out.push({
      product_id:m[1],
      href:a.getAttribute('href')||'',
      name:((img&&img.getAttribute('alt'))||'').trim(),
      image:(img&&img.getAttribute('src'))||'',
      price_text:priceEl?priceEl.innerText.trim():'',
      rating_text:ratingEl?ratingEl.innerText.trim():'',
      info_text:info?info.innerText.trim():'',
    });
    if(out.length>=limit) break;
  }
  return out;
}"""


def _pick_price(price_text):
    """PriceArea innerText → 판매가 문자열. 정가·할인율·판매가가 줄바꿈으로 쌓여
    있어(예: "210,000원\n9%\n190,000원") **마지막 '원'**이 실제 판매가다."""
    prices = [ln.strip() for ln in (price_text or "").splitlines()
              if ln.strip().endswith("원")]
    return prices[-1] if prices else ""


def parse_items(raw, limit=24):
    """브라우저에서 뽑은 raw 리스트 → 저장 계약에 맞춘 상품 후보(순수 함수).

    상품 URL은 coupang_partners.parse_product_url로 정규화한다 — 검색 유입 추적값
    (searchId·rank·clickEventId)이 그대로 저장되면 같은 상품인지 비교가 안 된다.
    광고 카드는 버리지 않고 표시만 한다(광고가 곧 잘 팔리는 상품인 경우가 많다)."""
    items, seen = [], set()
    for r in raw or []:
        pid = (r.get("product_id") or "").strip()
        if not pid or pid in seen:
            continue
        href = r.get("href") or ""
        absolute = urllib.parse.urljoin("https://www.coupang.com", href)
        parsed = coupang_partners.parse_product_url(absolute)
        if parsed is None:
            continue
        seen.add(pid)
        info = r.get("info_text") or ""
        items.append({
            "product_id": pid,
            "name": (r.get("name") or "").strip(),
            "url": parsed["url"],
            "image": r.get("image") or "",
            "price": _pick_price(r.get("price_text")),
            "rating": (r.get("rating_text") or "").strip(),
            "rocket": ("로켓" in info),
            "is_ad": ("광고" in info),
        })
        if len(items) >= limit:
            break
    return items


def _proxy_arg(raw):
    """"http://user:pass@host:port" → Playwright proxy dict. 비어 있으면 None."""
    if not raw:
        return None
    u = urllib.parse.urlparse(raw)
    if not u.hostname:
        return None
    server = f"{u.scheme or 'http'}://{u.hostname}"
    if u.port:
        server += f":{u.port}"
    proxy = {"server": server}
    if u.username:
        proxy["username"] = urllib.parse.unquote(u.username)
    if u.password:
        proxy["password"] = urllib.parse.unquote(u.password)
    return proxy


def search(keyword, limit=None, timeout_ms=None):
    """키워드 → 상품 후보. 실패해도 예외 없이 ok:False로 접는다(수동 흐름 보존)."""
    kw = (keyword or "").strip()
    search_link = coupang_partners.search_url(kw)
    if not kw:
        return {"ok": False, "items": [], "search_url": "", "source": "crawl",
                "notice": "검색어가 비어있습니다"}
    if not config.COUPANG_SEARCH_ENABLED:
        return {"ok": False, "items": [], "search_url": search_link, "source": "crawl",
                "notice": "쿠팡 자동검색이 꺼져 있습니다(COUPANG_SEARCH_ENABLED)"}

    limit = limit or config.COUPANG_SEARCH_LIMIT
    timeout_ms = timeout_ms or config.COUPANG_SEARCH_TIMEOUT_MS
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return {"ok": False, "items": [], "search_url": search_link, "source": "crawl",
                "notice": "Playwright가 설치되어 있지 않습니다"}

    proxy = _proxy_arg(config.COUPANG_PROXY)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                # ★headless=False가 필수다 — 헤드리스는 403으로 막힌다(실측).
                # 서버에서는 xvfb-run으로 가상 디스플레이를 붙여 띄운다.
                headless=False,
                channel="chrome",
                proxy=proxy,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"],
            )
            try:
                ctx = browser.new_context(
                    locale="ko-KR", viewport={"width": 1366, "height": 900},
                    extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
                )
                page = ctx.new_page()
                resp = page.goto(search_link, wait_until="domcontentloaded",
                                 timeout=timeout_ms)
                status = resp.status if resp else 0
                try:
                    page.wait_for_selector("li[class*=ProductUnit_productUnit]",
                                           timeout=min(timeout_ms, 15000))
                except Exception:
                    pass
                raw = page.evaluate(_EXTRACT_JS, limit)
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "items": [], "search_url": search_link, "source": "crawl",
                "notice": f"쿠팡 검색 실패: {type(exc).__name__}"}

    items = parse_items(raw, limit=limit)
    if not items:
        # 403(Access Denied)이면 IP가 막힌 것 — 주거용 프록시가 필요하다는 뜻이다.
        blocked = status == 403
        return {"ok": False, "items": [], "search_url": search_link, "source": "crawl",
                "notice": ("쿠팡이 이 IP를 막았습니다 — 주거용 프록시(COUPANG_PROXY)가 "
                           "필요합니다" if blocked else "검색 결과를 찾지 못했습니다")}
    return {"ok": True, "items": items, "search_url": search_link, "source": "crawl",
            "notice": ""}
