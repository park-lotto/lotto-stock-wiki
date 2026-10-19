# -*- coding: utf-8 -*-
"""✈️ 여행 탭 결과물 검사(관제 239) — 진짜 레퍼런스랭킹 화면(index.html)을 브라우저로 열어 탭을 눌러 본다.

잰다: 숙소·항공 베스트 카드 수 / 카드마다 '출처: …' 배지가 있나 / 사이트 칩 수 / 📥 담기 → '내가 담은 것'에 생기나 /
      다른 탭으로 돌아가면 영상 랭킹 줄(정렬·카테고리·검색)이 원래대로 보이나 / 페이지 오류 0.
사용: py tools/travel/check_travel_tab.py <기본주소> [스크린샷 폴더]
      예) py tools/travel/check_travel_tab.py http://127.0.0.1:8873 out/travel_check
      라이브는 tools.live_admin.admin_page 로 같은 동작을 한다(--live).
"""
import os
import sys

from playwright.sync_api import sync_playwright


_IMG_JS = ("() => [...document.querySelectorAll('#tvList .card img')].slice(0, 8)"
           ".filter(i => i.complete && i.naturalWidth > 0).length")


def _imgs(page):
    """첫 8장(첫 화면)이 실제로 그려졌나 — 검은 카드는 결과물 결함이다."""
    try:
        page.wait_for_function(_IMG_JS.replace("=> [", "=> [") + " >= 8", timeout=45000)
    except Exception:      # noqa: BLE001 — 시간 안에 다 안 떠도 몇 장인지는 센다
        pass
    return page.evaluate(_IMG_JS)


def run(page, shots):
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.wait_for_timeout(1500)
    tab = page.locator('#platformTabs [data-platform="travel"]')
    res = {"tab_visible": tab.is_visible()}
    tab.click()
    page.wait_for_selector("#tvList .card", timeout=60000)
    cards = page.locator("#tvList .card")
    res["stay_cards"] = cards.count()
    res["stay_badges"] = page.locator("#tvList .card >> text=/^출처: /").count()
    res["site_chips"] = page.locator("#tvSites button").count()
    res["video_rows_hidden"] = all(not page.locator("#" + i).is_visible() for i in ("tabs", "spanTabs", "cats", "rankSearchRow"))
    res["stay_imgs_loaded_of8"] = _imgs(page)
    page.screenshot(path=os.path.join(shots, "travel_stay.png"), full_page=False)
    page.locator("#travelRoot button", has_text="✈️ 항공").click()
    page.wait_for_timeout(500)
    page.wait_for_selector("#tvList .card", timeout=60000)
    res["air_cards"] = page.locator("#tvList .card").count()
    res["air_imgs_loaded_of8"] = _imgs(page)
    page.screenshot(path=os.path.join(shots, "travel_air.png"), full_page=False)
    # 담기 → 내가 담은 것
    page.locator("#travelRoot button", has_text="🏨 숙소").click()
    page.wait_for_selector("#tvList .card", timeout=60000)
    page.locator("#tvList .card button", has_text="담기").first.click()
    page.wait_for_function("document.getElementById('tvMsg').textContent.indexOf('담') >= 0 && document.getElementById('tvMsg').textContent.indexOf('중') < 0", timeout=30000)
    res["grab_msg"] = page.locator("#tvMsg").text_content()
    page.locator("#travelRoot button", has_text="내가 담은 것").click()
    page.wait_for_timeout(4000)                      # 보강(상세 가져오기)은 뒤에서 돈다
    page.locator("#travelRoot button", has_text="내가 담은 것").click()
    page.wait_for_selector("#tvList .card", timeout=30000)
    res["mine_cards"] = page.locator("#tvList .card").count()
    page.screenshot(path=os.path.join(shots, "travel_mine.png"), full_page=False)
    # 다른 탭으로 돌아가면 영상 랭킹 줄이 다시 보이나
    page.locator('#platformTabs [data-platform="instagram"]').click()
    page.wait_for_timeout(800)
    res["video_rows_back"] = all(page.locator("#" + i).is_visible() for i in ("tabs", "spanTabs", "rankSearchRow"))
    res["travel_root_hidden"] = not page.locator("#travelRoot").is_visible()
    res["page_errors"] = errs
    return res


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8873"
    shots = sys.argv[2] if len(sys.argv) > 2 else "travel_check"
    os.makedirs(shots, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.goto(base + "/", wait_until="domcontentloaded")
        res = run(pg, shots)
        b.close()
    for k, v in res.items():
        print("%-20s %s" % (k, v))
    ok = (res["tab_visible"] and res["stay_cards"] > 0 and res["stay_badges"] == res["stay_cards"]
          and res["air_cards"] > 0 and res["stay_imgs_loaded_of8"] == 8 and res["air_imgs_loaded_of8"] == 8 and res["mine_cards"] >= 1 and res["video_rows_hidden"]
          and res["video_rows_back"] and res["travel_root_hidden"] and not res["page_errors"])
    print("결과:", "통과" if ok else "실패")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
