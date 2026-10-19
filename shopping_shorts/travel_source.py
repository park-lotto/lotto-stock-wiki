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
}
KINDS = {"stay": "숙소", "air": "항공"}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")
_TIMEOUT = 20

_YEOGI_STAY_RE = re.compile(r"/domestic-accommodations/(\d+)")
_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _site_of_host(host):
    host = (host or "").lower().split(":")[0]
    for key, s in SITES.items():
        for h in s["hosts"]:
            if host == h or host.endswith("." + h):
                return key
    return None


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
    return {"site": site, "site_name": SITES[site]["name"], "kind": kind, "id": pid}


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


def _yeogi_stay(pid, html=None):
    """여기어때 숙소 상세 — 실측 2026-10-19: 일반 HTTP 200, __NEXT_DATA__.pageProps.accommodationInfo.
    meta.newImages = 숙소가 올린 사진(title 이 분류: '객실'·'야외 수영장'·'전경'·'레스토랑'… 없으면 None)."""
    url = "https://www.yeogi.com/domestic-accommodations/%s" % pid
    html = html if html is not None else _get(url)
    info = _next_data(html)["props"]["pageProps"]["accommodationInfo"]
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
        "source_label": source_label("yeogi"),
        "fetched_at": int(time.time()),
    }


def fetch(url):
    """상세 한 건. 지원하지 않는 사이트·화면이면 ValueError(이유를 담아) — 조용히 빈 값을 돌려주지 않는다."""
    t = travel_site(url)
    if not t:
        raise ValueError("여행 사이트 주소가 아닙니다")
    if t["site"] == "yeogi" and t["kind"] == "stay":
        return _yeogi_stay(t["id"])
    raise ValueError("%s 상세 가져오기는 아직 지원하지 않습니다" % t["site_name"])


def best_items(kind, site=None):
    """사이트별 베스트 목록 — 사이트 수집기가 붙는 대로 채운다. 지금은 빈 목록과 이유를 돌려준다."""
    if kind not in KINDS:
        raise ValueError("kind 는 stay|air")
    return {"kind": kind, "site": site, "items": [], "note": "수집기 준비 중"}
