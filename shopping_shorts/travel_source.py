"""여행 소재 수집 — 숙소·항공 사이트의 주소 판정·베스트 목록·상세(사진·출처) (관제 239, 2026-10-19).

여행 쇼핑쇼츠는 원본 영상이 없다. 소재는 **예약 사이트의 숙소/항공 상품**이고, 장면은
그 상품 페이지의 공식 사진을 AI로 움직여 만든다(강의 6편 분석: channel/strategy/여행쇼핑쇼츠_프로그램설계.md).

이 파일이 주인인 판단(0순위-B — 다른 곳에 다시 적지 마라):
  · travel_site(url)    이 주소가 어느 여행 사이트의 어떤 상품(숙소/항공)인가 — 담기·랭킹·제작이 모두 이것만 부른다
  · best_items(kind, site)  사이트별 베스트(인기) 목록 — 레퍼런스랭킹 ✈️여행 탭
  · fetch(url)          상세 한 건 → 이름·가격·시설·공식 사진(분류 꼬리표 포함)·출처
  · source_label(site)  화면·영상에 박는 출처 문구("출처: 여기어때")

★사진은 **공식 사진만** 쓴다. 상세 페이지에는 투숙객 후기 사진도 같이 있지만 그건 손님 것이고
  얼굴이 나온다 — fetch 는 meta.newImages(숙소가 올린 사진)만 담는다.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

# 사이트 표 — 주소 판정·출처 문구·랭킹 필터 칩이 전부 이 표 하나를 읽는다.
#   kinds: 이 사이트에서 다루는 상품 종류(stay=숙소, air=항공)
SITES = {
    "yeogi":   {"name": "여기어때",     "hosts": ("yeogi.com", "goodchoice.kr"),        "kinds": ("stay",)},
    "coupang": {"name": "쿠팡트래블",   "hosts": ("trip.coupang.com",),                 "kinds": ("stay", "air")},
    "yanolja": {"name": "야놀자",       "hosts": ("yanolja.com", "nol.yanolja.com", "nol.interpark.com"), "kinds": ("stay", "air")},
    "mrt":     {"name": "마이리얼트립", "hosts": ("myrealtrip.com",),                   "kinds": ("stay", "air")},
    "tripcom": {"name": "트립닷컴",     "hosts": ("trip.com",),                         "kinds": ("stay", "air")},
    "agoda":   {"name": "아고다",       "hosts": ("agoda.com",),                        "kinds": ("stay",)},
    "naver":   {"name": "네이버 항공권", "hosts": ("flight.naver.com",),                "kinds": ("air",)},
    "nol":     {"name": "NOL 항공",     "hosts": ("tour.yanolja.com",),                 "kinds": ("air",)},
}
KINDS = {"stay": "숙소", "air": "항공"}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")
_TIMEOUT = 20

_YEOGI_STAY_RE = re.compile(r"/domestic-accommodations/(\d+)")
_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _site_of_host(host):
    host = (host or "").lower().split(":")[0]
    best, blen = None, 0
    for key, s in SITES.items():           # 가장 길게 맞는 주소가 이긴다(tour.yanolja.com=NOL 항공 > yanolja.com=야놀자)
        for h in s["hosts"]:
            if (host == h or host.endswith("." + h)) and len(h) > blen:
                best, blen = key, len(h)
    return best


def travel_site(url):
    """주소 → {"site","site_name","kind","id"} 또는 None(여행 사이트가 아님).

    kind 는 주소 모양으로 알 수 있을 때만 채운다(모르면 None — 사이트는 맞지만 상세가 아닌 화면).
    담기(app._grab_video)·레퍼런스랭킹·제작이 모두 이 함수 하나로 판정한다."""
    try:
        p = urllib.parse.urlparse((url or "").strip())
    except ValueError:
        return None
    if p.scheme not in ("http", "https"):
        return None
    site = _site_of_host(p.netloc)
    if not site:
        return None
    kind, pid = None, None
    if site == "yeogi":
        m = _YEOGI_STAY_RE.search(p.path)
        if m:
            kind, pid = "stay", m.group(1)
    elif site == "yanolja":
        m = re.search(r"/stay/domestic/(\d+)", p.path)
        if m:
            kind, pid = "stay", m.group(1)
    elif (site == "naver" and p.path.startswith("/flights/")) or (site == "nol" and p.path.startswith("/air/search/")):
        # 항공은 '노선+날짜'가 곧 상품이다 — 경로 그대로를 번호로 쓴다(같은 노선·날짜면 같은 키)
        kind, pid = "air", p.path.strip("/").split("/", 1)[-1]
    return {"site": site, "site_name": SITES[site]["name"], "kind": kind, "id": pid}


def item_key(t):
    """담기·목록의 고유 키 = 사이트:종류:상품번호. travel_site 결과에서만 만든다."""
    return "%s:%s:%s" % (t["site"], t.get("kind") or "", t.get("id") or "")


# 대표 사진 고르기 — 목록 카드·담기 썸네일용. 물놀이 > 전경 > 대표 사진 > 첫 장(강의 공식: 물놀이가 시선을 끈다).
_COVER_ORDER = ("수영장", "스파", "자쿠지", "노천", "전경", "대표")


def cover_photo(d):
    photos = (d or {}).get("photos") or []
    for word in _COVER_ORDER:
        for p in photos:
            if word in (p.get("label") or ""):
                return p["url"]
    return photos[0]["url"] if photos else ""


def source_label(site):
    """영상·화면에 박는 출처 문구. 사이트를 모르면 빈 문자열(지어내지 않는다)."""
    s = SITES.get(site or "")
    return ("출처: " + s["name"]) if s else ""


def _get(url):
    """★curl_cffi 크롬 위장으로 받는다. 여기어때는 Cloudflare 가 TLS 지문으로 거른다 — 실측 2026-10-19:
    PC requests 403 / PC curl 200 / 서버 curl 403 / **서버·PC curl_cffi(chrome) 200**.
    서버 서비스 파이썬(/usr/bin/python3)에 curl_cffi 가 이미 깔려 있다."""
    from curl_cffi import requests as cr
    r = cr.get(url, impersonate="chrome", timeout=_TIMEOUT,
               headers={"Accept-Language": "ko-KR,ko;q=0.9"})
    if r.status_code != 200:
        raise RuntimeError("%s 응답 %s (%s)" % (urllib.parse.urlparse(url).netloc, r.status_code, url))
    return r.text


def _next_data(html):
    m = _NEXT_RE.search(html or "")
    if not m:
        raise ValueError("페이지에 __NEXT_DATA__ 가 없다(사이트 구조가 바뀌었을 수 있다)")
    return json.loads(m.group(1))


def _plain(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()


def _yeogi_story_facts(pp, info):
    """대본 이야기 재료 — 숙소가 쓴 소개글·자주 묻는 질문·실제 리뷰(사진에 없어도 말해도 되는 사실, 2026-10-19 사장님 허락).
    실측: accommodationInfo.manager.comment(소개) / dehydratedState…faq_list(질문·답) / initialReviewInfo.reviews[].content."""
    intro = _plain((info.get("manager") or {}).get("comment"))
    faq, reviews = [], []
    for q in ((pp.get("dehydratedState") or {}).get("queries") or []):
        data = ((q or {}).get("state") or {}).get("data") or {}
        for f in (data.get("faq_list") or []) if isinstance(data, dict) else []:
            a = _plain((f or {}).get("answer"))
            if a:
                faq.append({"q": _plain((f or {}).get("question")), "a": a[:220]})
    for r in ((pp.get("initialReviewInfo") or {}).get("reviews") or []):
        c = _plain((r or {}).get("content"))
        if len(c) >= 20:
            reviews.append(c[:260])
    return {"intro": intro[:900], "faq": faq[:12], "reviews": reviews[:10]}


def _yeogi_stay(pid, html=None):
    """여기어때 숙소 상세 — 실측 2026-10-19: 일반 HTTP 200, __NEXT_DATA__.pageProps.accommodationInfo.
    meta.newImages = 숙소가 올린 사진(title 이 분류: '객실'·'야외 수영장'·'전경'·'레스토랑'… 없으면 None)."""
    url = "https://www.yeogi.com/domestic-accommodations/%s" % pid
    html = html if html is not None else _get(url)
    pp = _next_data(html)["props"]["pageProps"]
    info = pp["accommodationInfo"]
    meta = info.get("meta") or {}
    photos, seen = [], set()
    for im in meta.get("newImages") or []:
        src = (im or {}).get("image")
        if not src or src in seen:
            continue
        seen.add(src)
        photos.append({"url": src, "label": ((im.get("title") or "").strip() or None)})
    # 객실별 사진도 숙소가 올린 공식 사진이다 — 객실 후보가 모자라지 않게 '객실' 꼬리표로 붙인다(중복 주소는 뺀다)
    for r in info.get("rooms") or []:
        for im in (r or {}).get("newImages") or []:
            src = (im or {}).get("image")
            if src and src not in seen:
                seen.add(src)
                photos.append({"url": src, "label": "객실", "room": (r or {}).get("name") or ""})
    prices = []
    for r in info.get("rooms") or []:
        v = ((r or {}).get("stay") or {}).get("price") or {}
        p = v.get("discountPrice") or v.get("salePrice")
        if isinstance(p, (int, float)) and p > 0:
            prices.append(int(p))
    review = meta.get("review") or {}
    return {
        "site": "yeogi", "site_name": SITES["yeogi"]["name"], "kind": "stay", "id": str(pid), "url": url,
        "name": meta.get("name") or "",
        "grade": meta.get("grade") or "",
        "address": meta.get("address") or "",
        "price_from": min(prices) if prices else None,
        "rating": review.get("rate") if isinstance(review, dict) else None,       # 10점 만점
        "review_count": review.get("count") if isinstance(review, dict) else None,
        "facilities": [i.get("name") for i in ((info.get("theme") or {}).get("items") or []) if i.get("name")],
        "photos": photos,
        "story_facts": _yeogi_story_facts(pp, info),
        "source_label": source_label("yeogi"),
        "fetched_at": int(time.time()),
    }


def yeogi_reviews(pid, max_pages=None, delay=0.4, on_page=None):
    """여기어때 숙소 후기 전부(2026-10-20 사장님 "댓글을 모두 보고 꿀팁·볼거리·식사·서비스 활용").
    실측: 화면 스크립트 PDP_COMMON.REVIEW_LIST = /api/gateway/content-review/v2/<서비스>/<숙소>/reviews,
    서비스 = s.In.STAY_DOMESTIC = "STAY_DOMESTIC"('domestic' 은 "미지원 서비스"). 한 번에 20개가 최대(size 50·100도 20).
    robots.txt 금지 목록에 없는 경로. 쪽 사이 delay 초 쉬며 hasNext 가 False 일 때까지."""
    from curl_cffi import requests as cr
    url = "https://www.yeogi.com/api/gateway/content-review/v2/STAY_DOMESTIC/%s/reviews" % pid
    out, page = [], 0
    while max_pages is None or page < max_pages:
        r = cr.get(url, params={"sort": "highRankingScoreFirst", "page": page, "size": 20}, impersonate="chrome",
                   timeout=_TIMEOUT, headers={"Referer": "https://www.yeogi.com/domestic-accommodations/%s" % pid})
        j = r.json() if r.status_code == 200 else {}
        if j.get("code") != 200:
            raise RuntimeError("여기어때 후기 %s쪽 실패 http %s · %s" % (page, r.status_code, (j.get("msg") or r.text[:120])))
        d = j.get("data") or {}
        for x in d.get("reviews") or []:
            c = (x.get("content") or "").strip()
            if c:
                out.append({"id": x.get("reviewId"), "created": x.get("createdAt"), "rating": x.get("rating"),
                            "title": x.get("title") or "", "content": c, "likes": x.get("likeCount") or 0,
                            "best": bool(x.get("isBestReview")), "images": len(x.get("images") or [])})
        page += 1
        if on_page:
            on_page(page, len(out))
        if not d.get("hasNext"):
            break
        time.sleep(delay)
    return out


def fetch(url):
    """상세 한 건. 지원하지 않는 사이트·화면이면 ValueError(이유를 담아) — 조용히 빈 값을 돌려주지 않는다."""
    t = travel_site(url)
    if not t:
        raise ValueError("여행 사이트 주소가 아닙니다")
    if t["site"] == "yeogi" and t["kind"] == "stay":
        return _yeogi_stay(t["id"])
    raise ValueError("%s 상세 가져오기는 아직 지원하지 않습니다" % t["site_name"])


# ── 베스트 목록 수집기 ─────────────────────────────────────────────────────────
# ★robots.txt 가 허용하는 경로만 쓴다(2026-10-19 실측 조사: channel/strategy/여행쇼핑쇼츠_프로그램설계 참조).
#   트립닷컴(/restapi/soa2 금지)·마이리얼트립(api3·flights 전면 금지)은 받아지지만 넣지 않았다.
#   항목 모양(화면·담기가 이것만 읽는다): site, site_name, kind, rank, title, sub, price, price_note,
#   depart, return, airline, url, image, source_label

def _air_item(site, rank, origin, dest, country, price, note, depart, ret, airline, url, image):
    return {"site": site, "site_name": SITES[site]["name"], "kind": "air", "rank": rank,
            "title": "%s → %s" % (origin, dest), "sub": country or "", "price": price, "price_note": note,
            "depart": depart, "return": ret, "airline": airline or "", "url": url, "image": image or "",
            "source_label": source_label(site)}


_AIRPORT_KO = {"ICN": "인천", "GMP": "김포", "PUS": "부산", "CJU": "제주", "TAE": "대구", "CJJ": "청주", "KWJ": "광주"}


def _ymd(s):
    s = (s or "").replace("-", "")
    return "%s-%s-%s" % (s[:4], s[4:6], s[6:8]) if len(s) == 8 else ""


def _best_naver_air():
    """네이버 항공권 첫 화면(robots 허용 '/') 의 '예약 많은 여행지' 10곳 — __NEXT_DATA__ apolloState."""
    st = _next_data(_get("https://flight.naver.com/"))["props"]["apolloState"]["ROOT_QUERY"]
    rows = st.get('trendingBookedAirports({"category":"ALL"})') or []
    out = []
    for i, x in enumerate(rows, 1):
        f, a = x.get("flight") or {}, x.get("airport") or {}
        dd, rd = f.get("departureDate") or "", f.get("returnDate") or ""
        seg = "domestic" if f.get("isDomestic") else "international"
        url = "https://flight.naver.com/flights/%s/%s-%s-%s" % (seg, f.get("departureLocationCode"), f.get("arrivalLocationCode"), dd)
        if rd:
            url += "/%s-%s-%s" % (f.get("arrivalLocationCode"), f.get("departureLocationCode"), rd)
        url += "?adult=1&fareType=Y"
        _o = f.get("departureLocationCode") or ""
        out.append(_air_item("naver", x.get("rank") or i, _AIRPORT_KO.get(_o, _o), a.get("cityName"),
                             a.get("countryName"), f.get("minPrice"), "왕복 최저" if rd else "편도 최저",
                             _ymd(dd), _ymd(rd), "", url, (a.get("cityImage") or {}).get("imageUrl")))
    return out


def _best_nol_air():
    """NOL 항공(tour.yanolja.com, robots Allow: /) 추천 특가 — 가격대별 묶음, 항공사·도시 사진 포함."""
    from curl_cffi import requests as cr
    r = cr.get("https://tour.yanolja.com/air/air-api/nol-air-web-api/recommendations/theme-itineraries",
               params={"themeType": "PRICE_DETAIL", "routeType": "INTERNATIONAL"}, impersonate="chrome",
               headers={"Referer": "https://tour.yanolja.com/air", "Accept-Language": "ko-KR"}, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError("NOL 항공 응답 %s" % r.status_code)
    out = []
    for grp in r.json() or []:
        for it in grp.get("items") or []:
            o, d = it.get("originCity") or {}, it.get("destinationCity") or {}
            dd, rd = (it.get("outboundDate") or "").replace("-", ""), (it.get("inboundDate") or "").replace("-", "")
            url = "https://tour.yanolja.com/air/search/c:%s-c:%s-%s" % (o.get("code"), d.get("code"), dd)
            if rd:
                url += "/c:%s-c:%s-%s" % (d.get("code"), o.get("code"), rd)
            url += "?cabin=%s&infant=0&child=0&adult=1" % (it.get("cabinType") or "ECONOMY")
            out.append(_air_item("nol", len(out) + 1, o.get("name"), d.get("name"), grp.get("title") or "",
                                 it.get("totalPrice"), "왕복 총액" if rd else "편도", _ymd(dd), _ymd(rd),
                                 it.get("airlineCode"), url, it.get("backgroundImageUrl")))
    out.sort(key=lambda x: (x["price"] is None, x["price"] or 0))
    for i, x in enumerate(out, 1):
        x["rank"] = i
    return out


def _stay_item(site, rank, name, group, price, rating, scale, reviews, url, image, extra=""):
    return {"site": site, "site_name": SITES[site]["name"], "kind": "stay", "rank": rank,
            "title": name or "", "sub": " · ".join(x for x in (group, extra) if x), "price": price,
            "price_note": "1박~" if price else "", "rating": rating, "rating_scale": scale,
            "reviews": reviews, "depart": "", "return": "", "airline": "", "url": url, "image": image or "",
            "source_label": source_label(site)}


_YEOGI_CAT = {0: "전체 인기", 2: "호텔·리조트", 3: "펜션·풀빌라"}


def _best_yeogi_stay():
    """여기어때 메인 '인기 숙소' API(robots 금지 경로 아님) — 전체·호텔·펜션 각 20건(중복은 앞 묶음만)."""
    out, seen = [], set()
    for cat, label in _YEOGI_CAT.items():
        j = json.loads(_get("https://www.yeogi.com/api/gateway/web-product-api/recommendations/popular?category=%d" % cat))
        for i, it in enumerate(j.get("body") or [], 1):
            m = it.get("meta") or {}
            if not m.get("id") or m["id"] in seen:
                continue
            seen.add(m["id"])
            price = (((it.get("room") or {}).get("stay") or {}).get("price") or {})
            br, rv = it.get("braze") or {}, m.get("review") or {}
            imgs = m.get("newImages") or m.get("images") or []
            img = imgs[0] if imgs else ""
            if isinstance(img, dict):
                img = img.get("image") or ""
            region = " ".join(x for x in (br.get("region"), br.get("city")) if x)
            out.append(_stay_item("yeogi", i, m.get("name"), label, price.get("discountPrice") or price.get("strikePrice"),
                                  rv.get("rate"), 10, rv.get("count"),
                                  "https://www.yeogi.com/domestic-accommodations/%s" % m["id"], img, region))
    return out


def _nol_rsc(html):
    parts = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    txt = []
    for p in parts:
        try:
            txt.append(json.loads(p))
        except ValueError:
            pass
    rsc, dec, res = "".join(txt), json.JSONDecoder(), []
    for m in re.finditer(r'\{"data":\{"header":\{"title":', rsc):
        try:
            res.append(dec.raw_decode(rsc, m.start())[0]["data"])
        except ValueError:
            continue
    return res


def _best_yanolja_stay():
    """NOL(야놀자) 카테고리 홈(robots 허용) 의 '인기 펜션 BEST'(지역 탭)·'국내 여행 인기 호텔' 위젯."""
    out = []
    for kind in ("pension", "hotel"):
        for w in _nol_rsc(_get("https://nol.yanolja.com/sub-home/%s" % kind)):
            title = (w.get("header") or {}).get("title") or ""
            # 베스트 위젯만 — 테마·광고 위젯은 빼고, '강원도 여행 인기 숙소'는 탭이 경주·부산이라(사이트 쪽 제목 불일치, 실측) 뺀다
            if not ("BEST" in title or "인기 호텔" in title):
                continue
            blocks = w.get("items") or []
            tabs = [b for b in blocks if isinstance(b, dict) and "items" in b and "header" in b] or [{"header": {}, "items": blocks}]
            for b in tabs:
                tab = (b.get("header") or {}).get("title") or ""
                for i, it in enumerate([x for x in b.get("items") or [] if isinstance(x, dict) and x.get("id")], 1):
                    pg = ((it.get("logMeta") or {}).get("priceGroup") or {})
                    web = ((it.get("action") or {}).get("web") or "")
                    sc = it.get("score")
                    try:
                        sc = float(sc)
                    except (TypeError, ValueError):
                        sc = None
                    rc = int(re.sub(r"\D", "", str(it.get("reviewCount") or "")) or 0) or None
                    out.append(_stay_item("yanolja", i, it.get("title"), title, (pg.get("sellPrices") or [None])[0],
                                          sc, 5, rc, ("https://nol.yanolja.com" + web) if web.startswith("/") else web,
                                          it.get("imageUrl"), tab))
    return out


_BEST = {("stay", "yeogi"): _best_yeogi_stay, ("stay", "yanolja"): _best_yanolja_stay,
         ("air", "naver"): _best_naver_air, ("air", "nol"): _best_nol_air}
_BEST_TTL = 3 * 3600          # 사이트 부담·속도 — 같은 목록은 3시간 재사용
_best_cache = {}


def best_items(kind, site=None):
    """사이트별 베스트 목록. site 를 안 주면 그 종류의 모든 수집기를 합친다(사이트별 순위는 그대로).
    한 사이트가 실패해도 나머지는 돌려주고 실패 이유를 errors 에 남긴다(조용히 빈 목록 금지)."""
    if kind not in KINDS:
        raise ValueError("kind 는 stay|air")
    if site and site not in SITES:
        raise ValueError("모르는 사이트: %s" % site)
    keys = [k for k in _BEST if k[0] == kind and (not site or k[1] == site)]
    items, errors, now = [], {}, time.time()
    for k in keys:
        hit = _best_cache.get(k)
        if hit and now - hit[0] < _BEST_TTL:
            items += hit[1]
            continue
        try:
            rows = _BEST[k]()
            _best_cache[k] = (now, rows)
            items += rows
        except Exception as e:      # noqa: BLE001 — 한 사이트 장애가 탭 전체를 비우면 안 된다(이유는 남긴다)
            errors[SITES[k[1]]["name"]] = str(e)[:200]
            if hit:
                items += hit[1]      # 지난 목록이라도 보여 준다(언제 것인지는 fetched_at 으로)
    sites = [{"site": k[1], "site_name": SITES[k[1]]["name"]} for k in _BEST if k[0] == kind]
    return {"kind": kind, "site": site, "items": items, "sites": sites, "errors": errors}
