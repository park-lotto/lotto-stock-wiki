# -*- coding: utf-8 -*-
"""샥탬스토리 하이브리드 — 쿠팡 후보 상품 페이지를 열어 대본 근거(상품명·평점·리뷰 글·판매처 문구)를 받는다.

쿠팡은 데이터센터 IP·헤드리스를 막는다 → shopping_shorts/coupang_search.py 와 같은 방식
(이 PC 회선 + 화면 뜨는 크롬 + 같은 프로필 .coupang_profile, 요청 사이 간격).
실행: py channel/foreignshowshow/하이브리드/쿠팡상품.py (선례 hottemreport/현장썰하이브리드/쿠팡상품.py 와 같은 방식)
결과: 같은 폴더 쿠팡상품/<상품번호>.txt · .png · 쿠팡상품_2026-10-18.json
"""
import json
import os
import random
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

PRODUCTS = {
    "4 Spikeball": ["9572008898", "5329056323", "8277288137"],
    "5 Bala Bangles": ["9532009187", "9140455573"],
    "6 LARQ": ["9120520253", "9774366170"],
    "2 Squatty Potty": ["100936605", "1675980473"],
    "3 Drop Stop": ["8428979691", "9600273291"],
    "1 STORMBAG": ["8173850803", "9658499964"],
}
ONLY = sys.argv[1:]   # 상품번호 일부만 다시
GAP = (float(os.environ.get("COUPANG_GAP", 6)), float(os.environ.get("COUPANG_GAP", 6)) + 4)   # 막히면 간격을 늘려 다시(10-18 연달아 3개 뒤 403)
OUT = Path(__file__).with_name("쿠팡상품")
OUT.mkdir(exist_ok=True)

_GRAB_JS = r"""()=>{
  const t=s=>{const e=document.querySelector(s);return e?e.innerText.trim():''};
  const reviews=[...document.querySelectorAll('article, [class*=review] [class*=content], .sdp-review__article__list__review__content')]
     .map(e=>e.innerText.trim()).filter(x=>x.length>15).slice(0,30);
  return {title:document.title, h1:t('h1')||t('.prod-buy-header__title'),
          rating:t('[class*=rating-star-num]')||t('.rating-star-num'),
          review_count:t('.count')||t('[class*=review-count]'),
          body:document.body.innerText.slice(0,20000), reviews};
}"""


def main():
    from playwright.sync_api import sync_playwright
    profile = os.path.join(str(ROOT), ".coupang_profile")
    res = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, headless=False, channel="chrome", locale="ko-KR",
            viewport={"width": 1366, "height": 900},
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.coupang.com/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        for ep, ids in PRODUCTS.items():
            for pid in ids:
                if ONLY and pid not in ONLY:
                    continue
                url = f"https://www.coupang.com/vp/products/{pid}"
                try:
                    r = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    st = r.status if r else 0
                    page.wait_for_timeout(2500)
                    for _ in range(8):                      # 리뷰는 내려야 불러온다
                        page.mouse.wheel(0, 1600)
                        page.wait_for_timeout(700)
                    g = page.evaluate(_GRAB_JS)
                    page.screenshot(path=str(OUT / f"{pid}.png"), full_page=False)
                    (OUT / f"{pid}.txt").write_text(g["body"], encoding="utf-8")
                    res[pid] = {"ep": ep, "url": url, "status": st, "title": g["h1"] or g["title"],
                                "rating": g["rating"], "review_count": g["review_count"],
                                "reviews": g["reviews"]}
                    print(f"## {ep} {pid} status={st} | {(g['h1'] or g['title'])[:60]} | 리뷰 글 {len(g['reviews'])}개")
                except Exception as e:  # noqa: BLE001 — 한 상품 실패가 나머지를 막지 않게
                    res[pid] = {"ep": ep, "url": url, "error": f"{type(e).__name__}: {e}"[:200]}
                    print(f"## {ep} {pid} 실패 {type(e).__name__}")
                time.sleep(random.uniform(*GAP))        # 몰아치면 쿠팡이 막는다(검색 실측: 연달아 4/10 막힘)
        ctx.close()
    dst = Path(__file__).with_name(f"쿠팡상품_{time.strftime('%Y-%m-%d')}.json")
    # 다시 돌려도 앞서 받은 페이지를 잃지 않는다 — 이번에 200 으로 받은 것만 바꾼다(10-18 두 번째 실행이 403 두 개로 덮은 일)
    old = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
    for pid, v in res.items():
        if v.get("status") == 200 or pid not in old:
            old[pid] = v
    dst.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장:", dst)


if __name__ == "__main__":
    main()
