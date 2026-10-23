"""숙소 사진 모으기 — 사이트마다 한 함수. 모두 같은 모양으로 돌려준다: [{"file", "site", "src", "page", "w", "h"}].

실측(2026-10-23 스카이베이 경포):
  공식 홈(imweb 류)  일반 HTTP · 62쪽 전부 훑어 큰 사진 118장(1920px·세로 드론샷)      robots: 전체 허용
  트립닷컴 상세       일반 HTTP · 86장(공식 약 38 + 손님) · 확장자 앞 크기 꼬리 떼면 원본(최대 2000px)
                     robots: /hotels/<도시>-hotel-detail-<번호>/ 허용, /htls/restapi·/hotels/Detail/Get* 금지 → 상세 HTML 만 읽는다
  여기어때            일반 HTTP · travel_source._yeogi_stay(기존 주인 함수) 그대로 부른다
  아고다              일반 HTTP 는 사진 0 → 브라우저(playwright)로 열고 사진 응답을 모은다(21장). robots: 상세 허용
  안 되는 곳(같은 날 실측) 부킹닷컴 403·주소 다름 / 익스피디아·호텔스닷컴 429 / 트립어드바이저 로봇 확인 / 네이버 플레이스 썸네일만
"""
import concurrent.futures as cf
import hashlib
import re
import time
import urllib.parse as up
from pathlib import Path

import cv2
import numpy as np
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MIN_SIDE = 700          # 짧은 변이 이보다 작으면 세로 화면에 못 쓴다(1080 폭으로 1.5배 넘게 키우면 흐려진다)
_IMG = r'(?:https?:)?//[^"\'\s\\)<>]+?\.(?:jpg|jpeg|png|webp)'


def _get(url, referer=None, timeout=25):
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9", "Referer": referer or url}, timeout=timeout)
    r.raise_for_status()
    return r


def _save(content, out_dir, prefix, k, meta):
    """그림 바이트 → 파일. 작거나 깨진 그림은 None."""
    im = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if im is None or min(im.shape[:2]) < MIN_SIDE:
        return None
    f = Path(out_dir) / ("%s_%03d.jpg" % (prefix, k))
    cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 94])[1].tofile(str(f))
    return dict(meta, file=str(f), w=im.shape[1], h=im.shape[0])


def _download_all(items, out_dir, prefix, referer):
    """items = [(src, page)] → 받은 것만. 같은 그림(작게 줄인 지문 같음)은 한 번만."""
    def one(it):
        try:
            return it, _get(it[0], referer=referer).content
        except Exception:
            return it, None
    out, seen = [], set()
    with cf.ThreadPoolExecutor(8) as ex:
        for (src, page), c in ex.map(one, items):
            if not c:
                continue
            im = cv2.imdecode(np.frombuffer(c, np.uint8), cv2.IMREAD_COLOR)
            if im is None:
                continue
            fp = hashlib.md5(cv2.resize(im, (16, 16)).tobytes()).hexdigest()
            if fp in seen:
                continue
            seen.add(fp)
            got = _save(c, out_dir, prefix, len(out), {"site": prefix, "src": src, "page": page})
            if got:
                out.append(got)
    return out


def official(url, out_dir, max_pages=120):
    """공식 홈페이지 — 첫 화면의 같은 사이트 링크를 한 겹 모두 열어 그림 주소를 모은다."""
    base = "{0.scheme}://{0.netloc}".format(up.urlparse(url))
    home = _get(url).text
    pages = [url] + sorted({up.urljoin(base, h) for h in re.findall(r'href="(/[^"#]*)"', home)
                            if not re.search(r"\.(css|js|ico|png|jpe?g|pdf)$", h)})[:max_pages]
    found = {}

    def grab(p):
        try:
            return p, _get(p, referer=base).text
        except Exception:
            return p, ""
    with cf.ThreadPoolExecutor(6) as ex:
        for p, h in ex.map(grab, pages):
            for u in re.findall(_IMG, h):
                u = ("https:" + u) if u.startswith("//") else u
                found.setdefault(u, p)
            for u in re.findall(r'(?:src|data-src)="(/[^"]+?\.(?:jpg|jpeg|png|webp))"', h):
                found.setdefault(up.urljoin(base, u), p)
    return _download_all(list(found.items()), out_dir, "official", base)


def trip(url, out_dir):
    """트립닷컴 호텔 상세 HTML 의 tripcdn 그림 → 크기 꼬리를 떼면 원본(실측 1300~2000px)."""
    html = _get(url).text
    ids = list(dict.fromkeys(re.findall(r"tripcdn\.com/images/([0-9a-zA-Z]{15,}?)_[A-Z]_\d+_\d+", html)))
    items = [("https://ak-d.tripcdn.com/images/%s.jpg" % i, url) for i in ids]
    return _download_all(items, out_dir, "trip", "https://kr.trip.com/")


def yeogi(url, out_dir):
    """여기어때 — 주인 함수 travel_source.fetch 가 고른 공식 사진만."""
    from shopping_shorts import travel_source
    d = travel_source.fetch(url)
    got = _download_all([(p["url"], url) for p in d.get("photos") or []], out_dir, "yeogi", url)
    # 후기 사진(투숙객이 올린 것)도 받는다 — 숙소 사진에 '고기 굽는 장면' 같은 체험 컷이 없을 때가 있다(실측: 아이리스 촌캉스 숙소 사진 74장에 굽는 장면 0).
    # 고를 때는 SITE_BONUS 가 숙소 사진 뒤로 미룬다. 출처 표기 = '여기어때 후기'
    revs = travel_source.yeogi_reviews(d["id"])
    return got + _download_all([(i, url) for r in revs for i in r["images"]], out_dir, "yeogi_review", url)


def agoda(url, out_dir, scrolls=10):
    """아고다 — 화면이 스크립트로 사진을 불러온다(일반 HTTP 0장 실측). 브라우저로 열고 내려가며 사진 응답을 모은다."""
    from playwright.sync_api import sync_playwright
    found = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(locale="ko-KR", user_agent=UA, viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()

        def on(r):
            try:
                if r.request.resource_type == "image" and "hotelImages" in r.url:
                    found[re.sub(r"\?.*$", "", r.url)] = url        # 크기 꼬리(?s=…)를 떼면 큰 그림
            except Exception:
                pass
        pg.on("response", on)
        pg.goto(url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(4)
        for _ in range(scrolls):
            pg.mouse.wheel(0, 2500)
            time.sleep(0.8)
        b.close()
    return _download_all(list(found.items()), out_dir, "agoda", "https://www.agoda.com/")


ADAPTERS = {"official": official, "trip": trip, "yeogi": yeogi, "agoda": agoda}
