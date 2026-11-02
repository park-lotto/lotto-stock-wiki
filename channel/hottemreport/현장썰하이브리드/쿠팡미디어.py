# -*- coding: utf-8 -*-
"""현장썰 하이브리드 — 쿠팡 상품 페이지의 상품 사진·리뷰 사진·리뷰 영상을 받는다(뒤 화면 재료 = 그 상품만).

쿠팡상품.py 와 같은 방식(이 PC 회선 + 화면 뜨는 크롬 + .coupang_profile). 받기도 같은 브라우저 세션(page.request)으로.
실행: py channel/hottemreport/현장썰하이브리드/쿠팡미디어.py <상품번호> [<상품번호> …]
결과: C:/숏템_칼카피/hottemreport/현장썰하이브리드/coupang_media/<상품번호>/{img_NN.jpg, rv_NN.jpg, vid_NN.mp4, list.json}
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[3]
OUT = Path("C:/숏템_칼카피/hottemreport/현장썰하이브리드/coupang_media")

_JS = r"""()=>{
  const abs=u=>u&&u.startsWith('//')?'https:'+u:u;
  const imgs=[...document.querySelectorAll('img')].map(i=>abs(i.getAttribute('data-src')||i.currentSrc||i.src)).filter(Boolean);
  const vids=[...document.querySelectorAll('video, video source')].map(v=>abs(v.currentSrc||v.src||v.getAttribute('src'))).filter(Boolean);
  return {imgs, vids};
}"""


def big(u: str) -> str:
    # 쿠팡 썸네일 경로의 크기 칸(…/thumbnails/remote/230x230ex/…)을 큰 것으로
    return re.sub(r"/remote/\d+x\d+ex/", "/remote/1000x1000ex/", u)


def _eval(page):
    """페이지가 중간에 다시 불러와지면(쿠팡이 한 번 더 이동, 10-18 실측) 문맥이 사라진다 — 기다렸다 한 번 더."""
    for _ in range(3):
        try:
            return page.evaluate(_JS)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(2500)
    return {"imgs": [], "vids": []}


def main(ids):
    from playwright.sync_api import sync_playwright
    profile = os.path.join(str(ROOT), ".coupang_profile_hr")   # 다른 세션(샥탬 하이브리드)이 .coupang_profile 을 쓰고 있으면 같이 못 연다(10-18 실측) — 이 실행기 전용
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile, headless=False, channel="chrome", locale="ko-KR",
                                                   viewport={"width": 1366, "height": 900},
                                                   args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        net = []   # 화면 DOM 만 보면 리뷰 사진·영상을 놓친다(10-18 실측: 상품평 영상 2개가 있는데 0개) → 오가는 응답 주소를 다 적는다
        page.on("response", lambda r: net.append((r.url, r.headers.get("content-type", ""))))
        try:                                          # 홈을 한 번 밟아 쿠키(사람 동선) — 실패해도 상품으로 간다(coupang_search 와 같음)
            page.goto("https://www.coupang.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
        except Exception:  # noqa: BLE001
            pass
        for pid in ids:
            d = OUT / pid
            d.mkdir(parents=True, exist_ok=True)
            try:
                r = page.goto(f"https://www.coupang.com/vp/products/{pid}", wait_until="domcontentloaded", timeout=45000)
            except Exception as e:  # noqa: BLE001
                print(f"## {pid} 열기 실패 {type(e).__name__}"); continue
            print(f"## {pid} status={r.status if r else 0}")
            page.wait_for_timeout(2500)
            net.clear()
            seen_i, seen_v = [], []
            for _ in range(14):                       # 상세·리뷰는 내려야 불러온다
                g = _eval(page)
                seen_i += [u for u in g["imgs"] if u not in seen_i]
                seen_v += [u for u in g["vids"] if u not in seen_v]
                page.mouse.wheel(0, 1400)
                page.wait_for_timeout(800)
            # 상품평 영상: 재생 표시(0:21 같은 길이 글자)가 붙은 썸네일을 눌러야 영상 주소가 오간다
            for k in range(page.locator("text=/^\\d+:\\d\\d$/").count()):
                try:
                    page.locator("text=/^\\d+:\\d\\d$/").nth(k).click(timeout=4000)
                    page.wait_for_timeout(3000)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(800)
                except Exception:  # noqa: BLE001 — 한 개 실패가 나머지를 막지 않게
                    pass
            g = _eval(page)
            seen_v += [u for u in g["vids"] if u not in seen_v]
            for u, ct in net:
                if ct.startswith("image/") and u not in seen_i:
                    seen_i.append(u)
                elif (ct.startswith("video/") or ".mp4" in u or ".m3u8" in u) and u not in seen_v:
                    seen_v.append(u)
            (d / "net.json").write_text(json.dumps(net, ensure_ascii=False, indent=0), encoding="utf-8")
            prod = [big(u) for u in seen_i if "thumbnail" in u and ("vendor_inventory" in u or "/product/" in u or "retail" in u)]
            rev = [u for u in seen_i if "review" in u.lower()]
            got = {"product": [], "review": [], "video": []}
            for kind, urls, ext, pre in (("product", prod, "jpg", "img"), ("review", rev, "jpg", "rv"), ("video", seen_v, "mp4", "vid")):
                k = 0
                for u in dict.fromkeys(urls):
                    if u.startswith("blob:"):
                        got[kind].append({"url": u, "skip": "blob"}); continue
                    try:
                        resp = page.request.get(u, timeout=30000)
                        if resp.ok and len(resp.body()) > 8000:
                            f = d / f"{pre}_{k:02d}.{ext}"
                            f.write_bytes(resp.body())
                            got[kind].append({"url": u, "file": f.name, "bytes": len(resp.body())}); k += 1
                    except Exception as e:  # noqa: BLE001 — 한 장 실패가 나머지를 막지 않게
                        got[kind].append({"url": u, "error": type(e).__name__})
                    time.sleep(0.3)
            (d / "list.json").write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
            print("   상품 사진", len([x for x in got["product"] if "file" in x]), "리뷰 사진", len([x for x in got["review"] if "file" in x]),
                  "영상", len([x for x in got["video"] if "file" in x]), "(blob", len([x for x in got["video"] if x.get("skip")]), ")")
            time.sleep(7)
        ctx.close()


if __name__ == "__main__":
    main(sys.argv[1:])
